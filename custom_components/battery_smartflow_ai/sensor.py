from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    INTEGRATION_NAME,
    INTEGRATION_MANUFACTURER,
    INTEGRATION_MODEL,
    INTEGRATION_VERSION,
    STATUS_ENUMS,
    AI_STATUS_ENUMS,
    RECO_ENUMS,
    NEXT_ACTION_STATE_ENUMS,
    CELL_VOLTAGE_STATUS_ENUMS,
    CELL_VOLTAGE_SOC_PLAUSIBILITY_ENUMS,
    FORECAST_STATUS_ENUMS,
    PV_OUTLOOK_ENUMS,
    CHARGE_STRATEGY_ENUMS,
    STRATEGY_STATE_ENUMS,
    VISIBLE_STATE_ENUMS,
    TECHNICAL_REASON_ENUMS,
    CHARGE_COMMIT_TYPE_ENUMS,
    CHARGE_COMMIT_ABORT_REASON_ENUMS,
    AUTOMATIC_WEIGHTING_ENUMS,
)
from .device_profiles import DEVICE_PROFILES

_LOGGER = logging.getLogger(__name__)

SEASON_MODE_ENUMS = ["winter", "summer", "manual"]

SOC_LIMIT_ENUMS = [
    "not_configured",
    "no_limit",
    "upper_limit_active",
    "lower_limit_active",
]

FAULT_LEVEL_ENUMS = ["normal", "warning", "error"]

DEVICE_PROFILE_ENUMS = list(DEVICE_PROFILES.keys())

LEARNED_PLANNING_STATUS_ENUMS = [
    "not_started",
    "collecting",
    "insufficient_data",
    "ready",
    "active",
]

LEARNED_PLANNING_MODE_ENUMS = [
    "disabled",
    "collecting",
    "classic_fallback",
    "ready",
    "wait",
    "charge",
    "classic",
    "learned_wait",
    "learned_active",
]

LEARNED_PLANNING_BLOCKING_REASON_ENUMS = [
    "none",
    "not_started",
    "not_ready",
    "not_enough_days",
    "not_enough_usable_days",
    "night_window_coverage_too_low",
    "morning_window_coverage_too_low",
    "evening_window_coverage_too_low",
    "data_quality_too_low",
    "no_price_data",
    "no_deadline",
    "no_charge_needed",
    "invalid_search_space",
    "deadline_too_close_start_now",
    "latest_start_reached",
]

OFFGRID_MODE_ENUMS = [
    "not_configured",
    "unknown",
    "off",
    "normal",
    "eco",
]

OFFGRID_RULE_REASON_ENUMS = [
    "none",
    "offgrid_load_active_blocks_ac_charge",
    "offgrid_load_support",
]

CHARGE_SOURCE_ALLOCATION_REASON_ENUMS = [
    "no_active_charge_binding",
    "no_charge_target",
    "pv_blend_disabled",
    "grid_only_no_pv_surplus",
    "pv_covers_total_charge_target",
    "mixed_charge_grid_limit_reached",
    "mixed_pv_grid_charge",
]


@dataclass(frozen=True, kw_only=True)
class ZendureSensorEntityDescription(SensorEntityDescription):
    runtime_key: str


SENSORS: tuple[ZendureSensorEntityDescription, ...] = (
    # --------------------------------------------------
    # SYSTEM STATUS
    # --------------------------------------------------
    ZendureSensorEntityDescription(
        key="status",
        translation_key="status",
        runtime_key="status",
        device_class=SensorDeviceClass.ENUM,
        options=STATUS_ENUMS,
        icon="mdi:power-plug",
    ),
    ZendureSensorEntityDescription(
        key="ai_status",
        translation_key="ai_status",
        runtime_key="ai_status",
        device_class=SensorDeviceClass.ENUM,
        options=AI_STATUS_ENUMS,
        icon="mdi:robot",
    ),
    ZendureSensorEntityDescription(
        key="recommendation",
        translation_key="recommendation",
        runtime_key="recommendation",
        device_class=SensorDeviceClass.ENUM,
        options=RECO_ENUMS,
        icon="mdi:lightbulb-outline",
    ),
    ZendureSensorEntityDescription(
        key="fault_level_status",
        translation_key="fault_level_status",
        runtime_key="fault_level_status",
        device_class=SensorDeviceClass.ENUM,
        options=FAULT_LEVEL_ENUMS,
        icon="mdi:alert-circle-outline",
    ),

    # --------------------------------------------------
    # ACTION STATE
    # --------------------------------------------------
    ZendureSensorEntityDescription(
        key="next_action_state",
        translation_key="next_action_state",
        runtime_key="next_action_state",
        device_class=SensorDeviceClass.ENUM,
        options=NEXT_ACTION_STATE_ENUMS,
        icon="mdi:clock-outline",
    ),
    ZendureSensorEntityDescription(
        key="next_action_time",
        translation_key="next_action_time",
        runtime_key="next_action_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-start",
    ),
    
    ZendureSensorEntityDescription(
        key="strategy_state",
        translation_key="strategy_state",
        runtime_key="strategy_state",
        device_class=SensorDeviceClass.ENUM,
        options=STRATEGY_STATE_ENUMS,
        icon="mdi:strategy",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ZendureSensorEntityDescription(
        key="visible_state",
        translation_key="visible_state",
        runtime_key="visible_state",
        device_class=SensorDeviceClass.ENUM,
        options=VISIBLE_STATE_ENUMS,
        icon="mdi:eye-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ZendureSensorEntityDescription(
        key="automatic_weighting",
        translation_key="automatic_weighting",
        runtime_key="automatic_weighting",
        device_class=SensorDeviceClass.ENUM,
        options=AUTOMATIC_WEIGHTING_ENUMS,
        icon="mdi:tune-variant",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ZendureSensorEntityDescription(
        key="strategic_reason",
        translation_key="strategic_reason",
        runtime_key="strategic_reason",
        icon="mdi:head-question-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ZendureSensorEntityDescription(
        key="technical_reason",
        translation_key="technical_reason",
        runtime_key="technical_reason",
        device_class=SensorDeviceClass.ENUM,
        options=TECHNICAL_REASON_ENUMS,
        icon="mdi:cog-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ZendureSensorEntityDescription(
        key="strategy_priority",
        translation_key="strategy_priority",
        runtime_key="strategy_priority",
        icon="mdi:sort-numeric-descending",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ZendureSensorEntityDescription(
        key="source_reason",
        translation_key="source_reason",
        runtime_key="source_reason",
        icon="mdi:source-branch",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    ZendureSensorEntityDescription(
        key="source_action",
        translation_key="source_action",
        runtime_key="source_action",
        icon="mdi:play-box-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    ZendureSensorEntityDescription(
        key="source_ac_mode",
        translation_key="source_ac_mode",
        runtime_key="source_ac_mode",
        icon="mdi:swap-horizontal",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    ZendureSensorEntityDescription(
        key="charge_commit_active",
        translation_key="charge_commit_active",
        runtime_key="charge_commit_active",
        icon="mdi:lock-check-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ZendureSensorEntityDescription(
        key="charge_commit_type",
        translation_key="charge_commit_type",
        runtime_key="charge_commit_type",
        device_class=SensorDeviceClass.ENUM,
        options=CHARGE_COMMIT_TYPE_ENUMS,
        icon="mdi:battery-clock-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ZendureSensorEntityDescription(
        key="charge_commit_reason",
        translation_key="charge_commit_reason",
        runtime_key="charge_commit_reason",
        icon="mdi:message-text-clock-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ZendureSensorEntityDescription(
        key="charge_commit_source_reason",
        translation_key="charge_commit_source_reason",
        runtime_key="charge_commit_source_reason",
        icon="mdi:source-branch",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    ZendureSensorEntityDescription(
        key="charge_commit_target_soc",
        translation_key="charge_commit_target_soc",
        runtime_key="charge_commit_target_soc",
        native_unit_of_measurement="%",
        icon="mdi:battery-charging-80",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ZendureSensorEntityDescription(
        key="charge_commit_started_at",
        translation_key="charge_commit_started_at",
        runtime_key="charge_commit_started_at",
        icon="mdi:clock-start",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    ZendureSensorEntityDescription(
        key="charge_commit_valid_until",
        translation_key="charge_commit_valid_until",
        runtime_key="charge_commit_valid_until",
        icon="mdi:clock-end",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    ZendureSensorEntityDescription(
        key="charge_commit_abort_reason",
        translation_key="charge_commit_abort_reason",
        runtime_key="charge_commit_abort_reason",
        device_class=SensorDeviceClass.ENUM,
        options=CHARGE_COMMIT_ABORT_REASON_ENUMS,
        icon="mdi:cancel",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ZendureSensorEntityDescription(
        key="charge_commit_requested_power_w",
        translation_key="charge_commit_requested_power_w",
        runtime_key="charge_commit_requested_power_w",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        icon="mdi:flash",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ZendureSensorEntityDescription(
        key="charge_commit_allow_pv_blend",
        translation_key="charge_commit_allow_pv_blend",
        runtime_key="charge_commit_allow_pv_blend",
        icon="mdi:solar-power-variant",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    ZendureSensorEntityDescription(
        key="charge_source_allocation",
        translation_key="charge_source_allocation",
        runtime_key="charge_source_allocation_reason",
        device_class=SensorDeviceClass.ENUM,
        options=CHARGE_SOURCE_ALLOCATION_REASON_ENUMS,
        icon="mdi:transmission-tower-import",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),

    # --------------------------------------------------
    # ENGINE TRANSPARENCY
    # --------------------------------------------------
    ZendureSensorEntityDescription(
        key="decision_reason",
        translation_key="decision_reason",
        runtime_key="decision_reason",
        icon="mdi:head-question-outline",
    ),
    ZendureSensorEntityDescription(
        key="charge_strategy",
        translation_key="charge_strategy",
        runtime_key="charge_strategy",
        device_class=SensorDeviceClass.ENUM,
        options=CHARGE_STRATEGY_ENUMS,
        icon="mdi:strategy",
    ),
    ZendureSensorEntityDescription(
        key="adaptive_peak_active",
        translation_key="adaptive_peak_active",
        runtime_key="adaptive_peak_active",
        icon="mdi:chart-line",
    ),
    ZendureSensorEntityDescription(
        key="engine_health",
        translation_key="engine_health",
        runtime_key="engine_health",
        icon="mdi:heart-pulse",
    ),

    # --------------------------------------------------
    # FORECAST TRANSPARENCY (V4.0.0, optional)
    # --------------------------------------------------
    ZendureSensorEntityDescription(
        key="forecast_status",
        translation_key="forecast_status",
        runtime_key="forecast_status",
        device_class=SensorDeviceClass.ENUM,
        options=FORECAST_STATUS_ENUMS,
        icon="mdi:cloud-search-outline",
    ),
    ZendureSensorEntityDescription(
        key="pv_outlook",
        translation_key="pv_outlook",
        runtime_key="pv_outlook",
        device_class=SensorDeviceClass.ENUM,
        options=PV_OUTLOOK_ENUMS,
        icon="mdi:weather-partly-cloudy",
    ),
    ZendureSensorEntityDescription(
        key="forecast_remaining_today_kwh",
        translation_key="forecast_remaining_today_kwh",
        runtime_key="forecast_remaining_today_kwh",
        native_unit_of_measurement="kWh",
        icon="mdi:solar-power-variant",
    ),
    ZendureSensorEntityDescription(
        key="forecast_tomorrow_kwh",
        translation_key="forecast_tomorrow_kwh",
        runtime_key="forecast_tomorrow_kwh",
        native_unit_of_measurement="kWh",
        icon="mdi:weather-sunset-up",
    ),
    ZendureSensorEntityDescription(
        key="forecast_next_3h_kwh",
        translation_key="forecast_next_3h_kwh",
        runtime_key="forecast_next_3h_kwh",
        native_unit_of_measurement="kWh",
        icon="mdi:clock-fast",
    ),
    ZendureSensorEntityDescription(
        key="forecast_next_6h_kwh",
        translation_key="forecast_next_6h_kwh",
        runtime_key="forecast_next_6h_kwh",
        native_unit_of_measurement="kWh",
        icon="mdi:clock-outline",
    ),

    # --------------------------------------------------
    # LEARNED CHARGE-WINDOW PLANNING (V4.1.0)
    # visible main sensors
    # --------------------------------------------------
    ZendureSensorEntityDescription(
        key="learned_planning_status",
        translation_key="learned_planning_status",
        runtime_key="learned_planning_status",
        device_class=SensorDeviceClass.ENUM,
        options=LEARNED_PLANNING_STATUS_ENUMS,
        icon="mdi:brain",
    ),
    ZendureSensorEntityDescription(
        key="learned_planning_mode",
        translation_key="learned_planning_mode",
        runtime_key="learned_planning_mode",
        device_class=SensorDeviceClass.ENUM,
        options=LEARNED_PLANNING_MODE_ENUMS,
        icon="mdi:calendar-clock",
    ),
    ZendureSensorEntityDescription(
        key="learned_planning_optimal_charge_start",
        translation_key="learned_planning_optimal_charge_start",
        runtime_key="learned_planning_optimal_charge_start",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-start",
    ),
    ZendureSensorEntityDescription(
        key="learned_planning_deadline",
        translation_key="learned_planning_deadline",
        runtime_key="learned_planning_deadline",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-alert-outline",
    ),
    ZendureSensorEntityDescription(
        key="learned_planning_required_charge_energy_kwh",
        translation_key="learned_planning_required_charge_energy_kwh",
        runtime_key="learned_planning_required_charge_energy_kwh",
        native_unit_of_measurement="kWh",
        icon="mdi:battery-plus-variant",
    ),
    ZendureSensorEntityDescription(
        key="learned_planning_effective_window_minutes",
        translation_key="learned_planning_effective_window_minutes",
        runtime_key="learned_planning_effective_window_minutes",
        native_unit_of_measurement="min",
        icon="mdi:timer-outline",
    ),

    # --------------------------------------------------
    # LEARNED CHARGE-WINDOW PLANNING (V4.1.0)
    # diagnostic sensors
    # --------------------------------------------------
    ZendureSensorEntityDescription(
        key="learned_planning_blocking_reason",
        translation_key="learned_planning_blocking_reason",
        runtime_key="learned_planning_blocking_reason",
        device_class=SensorDeviceClass.ENUM,
        options=LEARNED_PLANNING_BLOCKING_REASON_ENUMS,
        icon="mdi:alert-circle-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ZendureSensorEntityDescription(
        key="learned_planning_history_days",
        translation_key="learned_planning_history_days",
        runtime_key="learned_planning_history_days",
        native_unit_of_measurement="d",
        icon="mdi:calendar-range",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ZendureSensorEntityDescription(
        key="learned_planning_usable_days",
        translation_key="learned_planning_usable_days",
        runtime_key="learned_planning_usable_days",
        native_unit_of_measurement="d",
        icon="mdi:calendar-check-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ZendureSensorEntityDescription(
        key="learned_planning_data_coverage",
        translation_key="learned_planning_data_coverage",
        runtime_key="learned_planning_data_coverage",
        native_unit_of_measurement="%",
        icon="mdi:database-check-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ZendureSensorEntityDescription(
        key="learned_planning_sample_count",
        translation_key="learned_planning_sample_count",
        runtime_key="learned_planning_sample_count",
        icon="mdi:counter",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    ZendureSensorEntityDescription(
        key="learned_planning_expected_consumption_kwh",
        translation_key="learned_planning_expected_consumption_kwh",
        runtime_key="learned_planning_expected_consumption_kwh",
        native_unit_of_measurement="kWh",
        icon="mdi:home-lightning-bolt-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ZendureSensorEntityDescription(
        key="learned_planning_available_battery_energy_kwh",
        translation_key="learned_planning_available_battery_energy_kwh",
        runtime_key="learned_planning_available_battery_energy_kwh",
        native_unit_of_measurement="kWh",
        icon="mdi:battery-high",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ZendureSensorEntityDescription(
        key="learned_planning_reserve_margin_kwh",
        translation_key="learned_planning_reserve_margin_kwh",
        runtime_key="learned_planning_reserve_margin_kwh",
        native_unit_of_measurement="kWh",
        icon="mdi:shield-battery-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ZendureSensorEntityDescription(
        key="learned_planning_forecast_adjustment_kwh",
        translation_key="learned_planning_forecast_adjustment_kwh",
        runtime_key="learned_planning_forecast_adjustment_kwh",
        native_unit_of_measurement="kWh",
        icon="mdi:weather-cloudy-alert",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ZendureSensorEntityDescription(
        key="learned_planning_effective_charge_power_w",
        translation_key="learned_planning_effective_charge_power_w",
        runtime_key="learned_planning_effective_charge_power_w",
        native_unit_of_measurement="W",
        icon="mdi:ev-station",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ZendureSensorEntityDescription(
        key="learned_planning_effective_window_slots",
        translation_key="learned_planning_effective_window_slots",
        runtime_key="learned_planning_effective_window_slots",
        icon="mdi:view-grid-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    ZendureSensorEntityDescription(
        key="learned_planning_window_score",
        translation_key="learned_planning_window_score",
        runtime_key="learned_planning_window_score",
        native_unit_of_measurement="€/kWh",
        icon="mdi:chart-bell-curve",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ZendureSensorEntityDescription(
        key="learned_profile_typical_daily_consumption_kwh",
        translation_key="learned_profile_typical_daily_consumption_kwh",
        runtime_key="learned_profile_typical_daily_consumption_kwh",
        native_unit_of_measurement="kWh",
        icon="mdi:home-lightning-bolt-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ZendureSensorEntityDescription(
        key="learned_profile_average_house_load_w",
        translation_key="learned_profile_average_house_load_w",
        runtime_key="learned_profile_average_house_load_w",
        native_unit_of_measurement="W",
        icon="mdi:home-analytics",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ZendureSensorEntityDescription(
        key="learned_profile_current_slot_consumption_kwh",
        translation_key="learned_profile_current_slot_consumption_kwh",
        runtime_key="learned_profile_current_slot_consumption_kwh",
        native_unit_of_measurement="kWh",
        icon="mdi:clock-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ZendureSensorEntityDescription(
        key="learned_profile_current_slot_average_w",
        translation_key="learned_profile_current_slot_average_w",
        runtime_key="learned_profile_current_slot_average_w",
        native_unit_of_measurement="W",
        icon="mdi:clock-fast",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),

    # --------------------------------------------------
    # PRICE TRANSPARENCY
    # --------------------------------------------------
    ZendureSensorEntityDescription(
        key="price_daily_average",
        translation_key="price_daily_average",
        runtime_key="price_daily_average",
        native_unit_of_measurement="€/kWh",
        icon="mdi:chart-line",
    ),
    ZendureSensorEntityDescription(
        key="current_peak_threshold",
        translation_key="current_peak_threshold",
        runtime_key="current_peak_threshold",
        native_unit_of_measurement="€/kWh",
        icon="mdi:chart-bell-curve",
    ),
    ZendureSensorEntityDescription(
        key="current_valley_threshold",
        translation_key="current_valley_threshold",
        runtime_key="current_valley_threshold",
        native_unit_of_measurement="€/kWh",
        icon="mdi:chart-bell-curve-cumulative",
    ),
    ZendureSensorEntityDescription(
        key="economic_discharge_threshold",
        translation_key="economic_discharge_threshold",
        runtime_key="economic_discharge_threshold",
        native_unit_of_measurement="€/kWh",
        icon="mdi:cash-clock",
    ),
    ZendureSensorEntityDescription(
        key="effective_discharge_threshold",
        translation_key="effective_discharge_threshold",
        runtime_key="effective_discharge_threshold",
        native_unit_of_measurement="€/kWh",
        icon="mdi:chart-line-variant",
    ),
    ZendureSensorEntityDescription(
        key="house_load",
        translation_key="house_load",
        runtime_key="house_load",
        icon="mdi:home-lightning-bolt",
        native_unit_of_measurement="W",
    ),
    ZendureSensorEntityDescription(
        key="price_now",
        translation_key="price_now",
        runtime_key="price_now",
        native_unit_of_measurement="€/kWh",
        icon="mdi:currency-eur",
    ),

    # --------------------------------------------------
    # OFF-GRID / INSELSTECKDOSE (V4.2.x, optional)
    # --------------------------------------------------
    ZendureSensorEntityDescription(
        key="offgrid_power_w",
        translation_key="offgrid_power_w",
        runtime_key="offgrid_power_w",
        native_unit_of_measurement="W",
        icon="mdi:power-socket-de",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ZendureSensorEntityDescription(
        key="offgrid_mode",
        translation_key="offgrid_mode",
        runtime_key="offgrid_mode",
        device_class=SensorDeviceClass.ENUM,
        options=OFFGRID_MODE_ENUMS,
        icon="mdi:power-socket-de",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ZendureSensorEntityDescription(
        key="offgrid_load_active",
        translation_key="offgrid_load_active",
        runtime_key="offgrid_load_active",
        icon="mdi:power-plug-battery",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ZendureSensorEntityDescription(
        key="offgrid_rule_reason",
        translation_key="offgrid_rule_reason",
        runtime_key="offgrid_rule_reason",
        device_class=SensorDeviceClass.ENUM,
        options=OFFGRID_RULE_REASON_ENUMS,
        icon="mdi:shield-power",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ZendureSensorEntityDescription(
        key="offgrid_source_active",
        translation_key="offgrid_source_active",
        runtime_key="offgrid_source_active",
        icon="mdi:solar-power-variant",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
        ZendureSensorEntityDescription(
        key="charge_source",
        translation_key="charge_source",
        runtime_key="charge_source",
        icon="mdi:source-branch",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    ZendureSensorEntityDescription(
        key="charge_price_applied",
        translation_key="charge_price_applied",
        runtime_key="charge_price_applied",
        native_unit_of_measurement="€/kWh",
        icon="mdi:cash-clock",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    ZendureSensorEntityDescription(
        key="charge_grid_part_w",
        translation_key="charge_grid_part_w",
        runtime_key="charge_grid_part_w",
        native_unit_of_measurement="W",
        icon="mdi:transmission-tower-import",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    ZendureSensorEntityDescription(
        key="charge_pv_part_w",
        translation_key="charge_pv_part_w",
        runtime_key="charge_pv_part_w",
        native_unit_of_measurement="W",
        icon="mdi:solar-power-variant",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    ZendureSensorEntityDescription(
        key="charge_mixed_price_active",
        translation_key="charge_mixed_price_active",
        runtime_key="charge_mixed_price_active",
        icon="mdi:scale-balance",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),

    # --------------------------------------------------
    # ECONOMICS
    # --------------------------------------------------

    # --------------------------------------------------
    # ECONOMICS
    # --------------------------------------------------
    ZendureSensorEntityDescription(
        key="avg_charge_price",
        translation_key="avg_charge_price",
        runtime_key="avg_charge_price",
        native_unit_of_measurement="€/kWh",
        icon="mdi:scale-balance",
    ),
    ZendureSensorEntityDescription(
        key="profit_eur",
        translation_key="profit_eur",
        runtime_key="profit_eur",
        native_unit_of_measurement="€",
        icon="mdi:cash",
    ),

    # --------------------------------------------------
    # CELL VOLTAGE (V3.5.0)
    # --------------------------------------------------
    ZendureSensorEntityDescription(
        key="global_lowest_cell_voltage",
        translation_key="global_lowest_cell_voltage",
        runtime_key="global_lowest_cell_voltage",
        native_unit_of_measurement="V",
        icon="mdi:battery-heart-variant",
    ),
    ZendureSensorEntityDescription(
        key="cell_voltage_status",
        translation_key="cell_voltage_status",
        runtime_key="cell_voltage_status",
        device_class=SensorDeviceClass.ENUM,
        options=CELL_VOLTAGE_STATUS_ENUMS,
        icon="mdi:battery-alert-variant-outline",
    ),
    ZendureSensorEntityDescription(
        key="cell_voltage_soc_plausibility",
        translation_key="cell_voltage_soc_plausibility",
        runtime_key="cell_voltage_soc_plausibility",
        device_class=SensorDeviceClass.ENUM,
        options=CELL_VOLTAGE_SOC_PLAUSIBILITY_ENUMS,
        icon="mdi:battery-sync",
    ),
    ZendureSensorEntityDescription(
        key="cell_voltage_emergency_active",
        translation_key="cell_voltage_emergency_active",
        runtime_key="cell_voltage_emergency_active",
        icon="mdi:battery-sync-outline",
    ),
    ZendureSensorEntityDescription(
        key="cell_voltage_discharge_blocked",
        translation_key="cell_voltage_discharge_blocked",
        runtime_key="cell_voltage_discharge_blocked",
        icon="mdi:battery-lock",
    ),

    # --------------------------------------------------
    # DEVICE / MODE
    # --------------------------------------------------
    ZendureSensorEntityDescription(
        key="device_profile",
        translation_key="device_profile",
        runtime_key="device_profile",
        device_class=SensorDeviceClass.ENUM,
        options=DEVICE_PROFILE_ENUMS,
        icon="mdi:battery-outline",
    ),
    ZendureSensorEntityDescription(
        key="season_mode",
        translation_key="season_mode",
        runtime_key="season_mode",
        device_class=SensorDeviceClass.ENUM,
        options=SEASON_MODE_ENUMS,
        icon="mdi:weather-partly-snowy",
    ),
    ZendureSensorEntityDescription(
        key="soc_limit_status",
        translation_key="soc_limit_status",
        runtime_key="soc_limit_status",
        device_class=SensorDeviceClass.ENUM,
        options=SOC_LIMIT_ENUMS,
        icon="mdi:shield-alert-outline",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [ZendureSmartFlowSensor(entry, coordinator, d) for d in SENSORS]
    add_entities(entities)


class ZendureSmartFlowSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, entry, coordinator, description):
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry

        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{description.key}"

        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": INTEGRATION_NAME,
            "manufacturer": INTEGRATION_MANUFACTURER,
            "model": INTEGRATION_MODEL,
            "sw_version": INTEGRATION_VERSION,
        }

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def native_value(self):
        data = self.coordinator.data or {}
        details = data.get("details") or {}
        key = self.entity_description.runtime_key

        if self.device_class == SensorDeviceClass.TIMESTAMP:
            val = details.get(key, data.get(key))
            if val is None:
                return None
            if hasattr(val, "tzinfo"):
                return dt_util.as_utc(val)
            if isinstance(val, str):
                dt = dt_util.parse_datetime(val)
                return dt_util.as_utc(dt) if dt else None
            return None

        if self.device_class == SensorDeviceClass.ENUM:
            val = details.get(key, data.get(key))
            options = self.entity_description.options or []
            if val in options:
                return val
            return options[0] if options else None

        val = details.get(key, data.get(key))

        if val is None:
            return None

        if key == "learned_planning_data_coverage":
            try:
                return round(float(val) * 100.0, 1)
            except Exception:
                return None

        if self.entity_description.native_unit_of_measurement:
            try:
                return float(val)
            except Exception:
                return None

        return val
        
    def _build_automatic_weighting_attributes(self) -> dict:
        """Return diagnostics for the unified automatic strategy context."""

        data = self.coordinator.data or {}
        details = data.get("details") or {}

        return {
            "active": details.get(
                "automatic_strategy_active",
                data.get("automatic_strategy_active"),
            ),
            "season_context": details.get(
                "automatic_season_context",
                data.get("automatic_season_context"),
            ),
            "pv_weight": details.get(
                "automatic_pv_weight",
                data.get("automatic_pv_weight"),
            ),
            "price_weight": details.get(
                "automatic_price_weight",
                data.get("automatic_price_weight"),
            ),
            "reserve_weight": details.get(
                "automatic_reserve_weight",
                data.get("automatic_reserve_weight"),
            ),
            "forecast_weight": details.get(
                "automatic_forecast_weight",
                data.get("automatic_forecast_weight"),
            ),
            "reason": details.get(
                "automatic_strategy_reason",
                data.get("automatic_strategy_reason"),
            ),
            "pv_weight_reason": details.get(
                "automatic_pv_weight_reason",
                data.get("automatic_pv_weight_reason"),
            ),
            "price_weight_reason": details.get(
                "automatic_price_weight_reason",
                data.get("automatic_price_weight_reason"),
            ),
            "reserve_weight_reason": details.get(
                "automatic_reserve_weight_reason",
                data.get("automatic_reserve_weight_reason"),
            ),
            "forecast_weight_reason": details.get(
                "automatic_forecast_weight_reason",
                data.get("automatic_forecast_weight_reason"),
            ),
            "discharge_allowed": details.get(
                "automatic_discharge_allowed",
                data.get("automatic_discharge_allowed"),
            ),
            "discharge_reason": details.get(
                "automatic_discharge_reason",
                data.get("automatic_discharge_reason"),
            ),
            "discharge_latch_reason": details.get(
                "automatic_discharge_latch_reason",
                data.get("automatic_discharge_latch_reason"),
            ),
            "peak_reserve_allowed": details.get(
                "automatic_peak_reserve_allowed",
                data.get("automatic_peak_reserve_allowed"),
            ),
            "peak_reserve_reason": details.get(
                "automatic_peak_reserve_reason",
                data.get("automatic_peak_reserve_reason"),
            ),
            "pv_handover_policy": details.get(
                "regulation_pv_handover_policy",
                data.get("regulation_pv_handover_policy"),
            ),
            "load_coverage_priority": details.get(
                "regulation_load_coverage_priority",
                data.get("regulation_load_coverage_priority"),
            ),
            "valley_charge_allowed": details.get(
                "automatic_valley_charge_allowed",
                data.get("automatic_valley_charge_allowed"),
            ),
            "valley_charge_reason": details.get(
                "automatic_valley_charge_reason",
                data.get("automatic_valley_charge_reason"),
            ),
        }

    def _build_charge_source_allocation_attributes(self) -> dict:
        """Return diagnostic attributes for the charge source allocation."""

        data = self.coordinator.data or {}
        details = data.get("details") or {}

        return {
            "active": details.get(
                "charge_source_allocation_active",
                data.get("charge_source_allocation_active"),
            ),
            "total_target_w": details.get(
                "charge_total_target_w",
                data.get("charge_total_target_w"),
            ),
            "pv_available_w": details.get(
                "charge_pv_available_w",
                data.get("charge_pv_available_w"),
            ),
            "pv_allocated_w": details.get(
                "charge_pv_allocated_w",
                data.get("charge_pv_allocated_w"),
            ),
            "grid_requested_w": details.get(
                "charge_grid_requested_w",
                data.get("charge_grid_requested_w"),
            ),
            "unfilled_w": details.get(
                "charge_unfilled_w",
                data.get("charge_unfilled_w"),
            ),
            "pv_share_pct": details.get(
                "charge_pv_share_pct",
                data.get("charge_pv_share_pct"),
            ),
            "grid_share_pct": details.get(
                "charge_grid_share_pct",
                data.get("charge_grid_share_pct"),
            ),
            "reason": details.get(
                "charge_source_allocation_reason",
                data.get("charge_source_allocation_reason"),
            ),
        }

    def _build_device_profile_attributes(self) -> dict:
        data = self.coordinator.data or {}
        details = data.get("details") or {}

        base_profile = details.get("device_profile")
        installed_pv_wp = details.get("installed_pv_wp")

        profile_overrides = self._entry.options.get("profile_overrides", {})
        if not isinstance(profile_overrides, dict):
            profile_overrides = {}

        season_thresholds = self.coordinator._persist.get("season_thresholds", {})
        if not isinstance(season_thresholds, dict):
            season_thresholds = {}

        attrs = {
            "base_profile": base_profile,
            "profile_overrides_active": bool(profile_overrides),
            "profile_override_count": len(profile_overrides),
            "installed_pv_wp": installed_pv_wp,
            "effective_target_import_w": details.get("effective_target_import_w"),
            "effective_deadband_w": details.get("effective_deadband_w"),
            "effective_export_guard_w": details.get("effective_export_guard_w"),
            "effective_kp_up": details.get("effective_kp_up"),
            "effective_kp_down": details.get("effective_kp_down"),
            "effective_max_step_up": details.get("effective_max_step_up"),
            "effective_max_step_down": details.get("effective_max_step_down"),
            "effective_keepalive_min_deficit_w": details.get("effective_keepalive_min_deficit_w"),
            "effective_keepalive_min_output_w": details.get("effective_keepalive_min_output_w"),
            "effective_soc_discharge_resume_margin": details.get("effective_soc_discharge_resume_margin"),
            "season_summer_pv_threshold": season_thresholds.get("summer_pv_threshold"),
            "season_summer_export_threshold": season_thresholds.get("summer_export_threshold"),
            "season_winter_pv_threshold": season_thresholds.get("winter_pv_threshold"),
            "season_winter_export_threshold": season_thresholds.get("winter_export_threshold"),
            "season_counter": season_thresholds.get("counter"),

            # V3.5.0 cell voltage transparency
            "expert_mode_enabled": details.get("expert_mode_enabled"),
            "cell_voltage_protection_enabled": details.get("cell_voltage_protection_enabled"),
            "configured_lowest_cell_voltage_sensor_count": details.get(
                "configured_lowest_cell_voltage_sensor_count"
            ),
            "global_lowest_cell_voltage": details.get("global_lowest_cell_voltage"),
        }

        attrs["profile_overrides"] = profile_overrides

        return attrs

    def _handle_coordinator_update(self) -> None:
        """Update sensor attributes without duplicating the full details block.

        Important for Home Assistant Recorder:
        The coordinator details dictionary can be large and changes often.
        Attaching it to every sensor causes massive database growth because
        every sensor state stores its own copy of the attributes.
        """

        attrs: dict | None = None

        if self.entity_description.runtime_key == "device_profile":
            attrs = self._build_device_profile_attributes()

        elif self.entity_description.key == "charge_source_allocation":
            attrs = self._build_charge_source_allocation_attributes()

        elif self.entity_description.key == "automatic_weighting":
            attrs = self._build_automatic_weighting_attributes()

        self._attr_extra_state_attributes = attrs
        super()._handle_coordinator_update()
