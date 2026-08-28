from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    INTEGRATION_MANUFACTURER,
    INTEGRATION_MODEL,
    INTEGRATION_VERSION,
    virtual_device_model,
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
    BOOLEAN_STATE_ENUMS,
    SOURCE_ACTION_ENUMS,
    SOURCE_AC_MODE_ENUMS,
    STRATEGY_REASON_ENUMS,
    DECISION_REASON_ENUMS,
    CHARGE_COMMIT_TYPE_ENUMS,
    CHARGE_COMMIT_ABORT_REASON_ENUMS,
    AUTOMATIC_WEIGHTING_ENUMS,
)
from .device_profiles import DEVICE_PROFILES
from .diagnostic_values import safe_diagnostic_sensor_value
from .price_currency import price_input_profile

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

PRICE_SENSOR_KEYS = frozenset(
    {
        "learned_planning_window_score",
        "price_daily_average",
        "current_peak_threshold",
        "current_valley_threshold",
        "economic_discharge_threshold",
        "effective_discharge_threshold",
        "price_now",
        "charge_price_applied",
        "avg_charge_price",
        "feed_in_tariff",
    }
)

ECONOMICS_MONETARY_SENSOR_KEYS = frozenset(
    f"economics_{period}_{value}"
    for period in ("daily", "total")
    for value in (
        "grid_charge_cost",
        "pv_opportunity_cost",
        "export_revenue",
        "avoided_grid_import_cost",
        "battery_benefit",
    )
)

ECONOMICS_PRICE_SENSOR_KEYS = frozenset(
    {
        "economics_average_grid_charge_price",
        "economics_average_pv_opportunity_value",
        "economics_average_export_price",
        "economics_average_battery_discharge_value",
    }
)

MONETARY_SENSOR_KEYS = frozenset({"profit_eur"}) | ECONOMICS_MONETARY_SENSOR_KEYS
PRICE_SENSOR_KEYS = PRICE_SENSOR_KEYS | ECONOMICS_PRICE_SENSOR_KEYS

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
    "effective_charge_power_too_low",
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
    "offgrid_load_observed",
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
    economics_device: bool = False


_SENSOR_DESCRIPTIONS: tuple[ZendureSensorEntityDescription, ...] = (
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
        device_class=SensorDeviceClass.ENUM,
        options=STRATEGY_REASON_ENUMS,
        icon="mdi:head-question-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ZendureSensorEntityDescription(
        key="technical_reason",
        translation_key="technical_reason",
        runtime_key="technical_reason",
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
        device_class=SensorDeviceClass.ENUM,
        options=STRATEGY_REASON_ENUMS,
        icon="mdi:source-branch",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    ZendureSensorEntityDescription(
        key="source_action",
        translation_key="source_action",
        runtime_key="source_action",
        device_class=SensorDeviceClass.ENUM,
        options=SOURCE_ACTION_ENUMS,
        icon="mdi:play-box-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    ZendureSensorEntityDescription(
        key="source_ac_mode",
        translation_key="source_ac_mode",
        runtime_key="source_ac_mode",
        device_class=SensorDeviceClass.ENUM,
        options=SOURCE_AC_MODE_ENUMS,
        icon="mdi:swap-horizontal",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    ZendureSensorEntityDescription(
        key="charge_commit_active",
        translation_key="charge_commit_active",
        runtime_key="charge_commit_active",
        device_class=SensorDeviceClass.ENUM,
        options=BOOLEAN_STATE_ENUMS,
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
        device_class=SensorDeviceClass.ENUM,
        options=STRATEGY_REASON_ENUMS,
        icon="mdi:message-text-clock-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ZendureSensorEntityDescription(
        key="charge_commit_source_reason",
        translation_key="charge_commit_source_reason",
        runtime_key="charge_commit_source_reason",
        device_class=SensorDeviceClass.ENUM,
        options=STRATEGY_REASON_ENUMS,
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
        device_class=SensorDeviceClass.ENUM,
        options=BOOLEAN_STATE_ENUMS,
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
        device_class=SensorDeviceClass.ENUM,
        options=DECISION_REASON_ENUMS,
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
        device_class=SensorDeviceClass.ENUM,
        options=BOOLEAN_STATE_ENUMS,
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
        icon="mdi:chart-line",
        state_class=SensorStateClass.MEASUREMENT,
        economics_device=True,
    ),
    ZendureSensorEntityDescription(
        key="current_peak_threshold",
        translation_key="current_peak_threshold",
        runtime_key="current_peak_threshold",
        icon="mdi:chart-bell-curve",
        state_class=SensorStateClass.MEASUREMENT,
        economics_device=True,
    ),
    ZendureSensorEntityDescription(
        key="current_valley_threshold",
        translation_key="current_valley_threshold",
        runtime_key="current_valley_threshold",
        icon="mdi:chart-bell-curve-cumulative",
        state_class=SensorStateClass.MEASUREMENT,
        economics_device=True,
    ),
    ZendureSensorEntityDescription(
        key="economic_discharge_threshold",
        translation_key="economic_discharge_threshold",
        runtime_key="economic_discharge_threshold",
        icon="mdi:cash-clock",
        state_class=SensorStateClass.MEASUREMENT,
        economics_device=True,
    ),
    ZendureSensorEntityDescription(
        key="effective_discharge_threshold",
        translation_key="effective_discharge_threshold",
        runtime_key="effective_discharge_threshold",
        icon="mdi:chart-line-variant",
        state_class=SensorStateClass.MEASUREMENT,
        economics_device=True,
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
        icon="mdi:cash",
        state_class=SensorStateClass.MEASUREMENT,
        economics_device=True,
    ),
    ZendureSensorEntityDescription(
        key="feed_in_tariff",
        translation_key="feed_in_tariff",
        runtime_key="feed_in_tariff",
        icon="mdi:transmission-tower-export",
        state_class=SensorStateClass.MEASUREMENT,
        economics_device=True,
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
        device_class=SensorDeviceClass.ENUM,
        options=BOOLEAN_STATE_ENUMS,
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
        device_class=SensorDeviceClass.ENUM,
        options=BOOLEAN_STATE_ENUMS,
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
        icon="mdi:cash-clock",
        state_class=SensorStateClass.MEASUREMENT,
        economics_device=True,
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
        device_class=SensorDeviceClass.ENUM,
        options=BOOLEAN_STATE_ENUMS,
        icon="mdi:scale-balance",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),

    # --------------------------------------------------
    # ECONOMICS
    # --------------------------------------------------
    ZendureSensorEntityDescription(
        key="economics_daily_grid_charge_cost",
        translation_key="economics_daily_grid_charge_cost",
        runtime_key="economics_daily_grid_charge_cost",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:transmission-tower-import",
        economics_device=True,
    ),
    ZendureSensorEntityDescription(
        key="economics_daily_pv_opportunity_cost",
        translation_key="economics_daily_pv_opportunity_cost",
        runtime_key="economics_daily_pv_opportunity_cost",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:solar-power-variant",
        economics_device=True,
    ),
    ZendureSensorEntityDescription(
        key="economics_daily_export_revenue",
        translation_key="economics_daily_export_revenue",
        runtime_key="economics_daily_export_revenue",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:transmission-tower-export",
        economics_device=True,
    ),
    ZendureSensorEntityDescription(
        key="economics_daily_avoided_grid_import_cost",
        translation_key="economics_daily_avoided_grid_import_cost",
        runtime_key="economics_daily_avoided_grid_import_cost",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:home-lightning-bolt-outline",
        economics_device=True,
    ),
    ZendureSensorEntityDescription(
        key="economics_daily_battery_benefit",
        translation_key="economics_daily_battery_benefit",
        runtime_key="economics_daily_battery_benefit",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:battery-check-outline",
        economics_device=True,
    ),
    ZendureSensorEntityDescription(
        key="economics_total_grid_charge_cost",
        translation_key="economics_total_grid_charge_cost",
        runtime_key="economics_total_grid_charge_cost",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:transmission-tower-import",
        economics_device=True,
    ),
    ZendureSensorEntityDescription(
        key="economics_total_pv_opportunity_cost",
        translation_key="economics_total_pv_opportunity_cost",
        runtime_key="economics_total_pv_opportunity_cost",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:solar-power-variant",
        economics_device=True,
    ),
    ZendureSensorEntityDescription(
        key="economics_total_export_revenue",
        translation_key="economics_total_export_revenue",
        runtime_key="economics_total_export_revenue",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:transmission-tower-export",
        economics_device=True,
    ),
    ZendureSensorEntityDescription(
        key="economics_total_avoided_grid_import_cost",
        translation_key="economics_total_avoided_grid_import_cost",
        runtime_key="economics_total_avoided_grid_import_cost",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:home-lightning-bolt-outline",
        economics_device=True,
    ),
    ZendureSensorEntityDescription(
        key="economics_total_battery_benefit",
        translation_key="economics_total_battery_benefit",
        runtime_key="economics_total_battery_benefit",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:battery-check-outline",
        economics_device=True,
    ),
    ZendureSensorEntityDescription(
        key="economics_total_economic_efficiency_pct",
        translation_key="economics_total_economic_efficiency_pct",
        runtime_key="economics_total_economic_efficiency_pct",
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        icon="mdi:finance",
        economics_device=True,
    ),
    ZendureSensorEntityDescription(
        key="economics_daily_grid_to_battery_kwh",
        translation_key="economics_daily_grid_to_battery_kwh",
        runtime_key="economics_daily_grid_to_battery_kwh",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:battery-arrow-up-outline",
        economics_device=True,
    ),
    ZendureSensorEntityDescription(
        key="economics_daily_pv_to_battery_kwh",
        translation_key="economics_daily_pv_to_battery_kwh",
        runtime_key="economics_daily_pv_to_battery_kwh",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:solar-power-variant",
        economics_device=True,
    ),
    ZendureSensorEntityDescription(
        key="economics_daily_grid_export_kwh",
        translation_key="economics_daily_grid_export_kwh",
        runtime_key="economics_daily_grid_export_kwh",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:transmission-tower-export",
        economics_device=True,
    ),
    ZendureSensorEntityDescription(
        key="economics_daily_battery_to_home_kwh",
        translation_key="economics_daily_battery_to_home_kwh",
        runtime_key="economics_daily_battery_to_home_kwh",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:home-battery-outline",
        economics_device=True,
    ),
    ZendureSensorEntityDescription(
        key="economics_daily_battery_to_grid_kwh",
        translation_key="economics_daily_battery_to_grid_kwh",
        runtime_key="economics_daily_battery_to_grid_kwh",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:battery-arrow-down-outline",
        economics_device=True,
    ),
    ZendureSensorEntityDescription(
        key="economics_total_grid_to_battery_kwh",
        translation_key="economics_total_grid_to_battery_kwh",
        runtime_key="economics_total_grid_to_battery_kwh",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:battery-arrow-up-outline",
        economics_device=True,
    ),
    ZendureSensorEntityDescription(
        key="economics_total_pv_to_battery_kwh",
        translation_key="economics_total_pv_to_battery_kwh",
        runtime_key="economics_total_pv_to_battery_kwh",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:solar-power-variant",
        economics_device=True,
    ),
    ZendureSensorEntityDescription(
        key="economics_total_grid_export_kwh",
        translation_key="economics_total_grid_export_kwh",
        runtime_key="economics_total_grid_export_kwh",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:transmission-tower-export",
        economics_device=True,
    ),
    ZendureSensorEntityDescription(
        key="economics_total_battery_to_home_kwh",
        translation_key="economics_total_battery_to_home_kwh",
        runtime_key="economics_total_battery_to_home_kwh",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:home-battery-outline",
        economics_device=True,
    ),
    ZendureSensorEntityDescription(
        key="economics_total_battery_to_grid_kwh",
        translation_key="economics_total_battery_to_grid_kwh",
        runtime_key="economics_total_battery_to_grid_kwh",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:battery-arrow-down-outline",
        economics_device=True,
    ),
    ZendureSensorEntityDescription(
        key="economics_average_grid_charge_price",
        translation_key="economics_average_grid_charge_price",
        runtime_key="economics_average_grid_charge_price",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:transmission-tower-import",
        economics_device=True,
    ),
    ZendureSensorEntityDescription(
        key="economics_average_pv_opportunity_value",
        translation_key="economics_average_pv_opportunity_value",
        runtime_key="economics_average_pv_opportunity_value",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:solar-power-variant",
        economics_device=True,
    ),
    ZendureSensorEntityDescription(
        key="economics_average_export_price",
        translation_key="economics_average_export_price",
        runtime_key="economics_average_export_price",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:transmission-tower-export",
        economics_device=True,
    ),
    ZendureSensorEntityDescription(
        key="economics_average_battery_discharge_value",
        translation_key="economics_average_battery_discharge_value",
        runtime_key="economics_average_battery_discharge_value",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:battery-arrow-down-outline",
        economics_device=True,
    ),

    # --------------------------------------------------
    # ECONOMICS
    # --------------------------------------------------
    ZendureSensorEntityDescription(
        key="avg_charge_price",
        translation_key="avg_charge_price",
        runtime_key="avg_charge_price",
        icon="mdi:scale-balance",
        state_class=SensorStateClass.MEASUREMENT,
        economics_device=True,
    ),
    ZendureSensorEntityDescription(
        key="profit_eur",
        translation_key="profit_eur",
        runtime_key="profit_eur",
        icon="mdi:cash",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        economics_device=True,
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
        device_class=SensorDeviceClass.ENUM,
        options=BOOLEAN_STATE_ENUMS,
        icon="mdi:battery-sync-outline",
    ),
    ZendureSensorEntityDescription(
        key="cell_voltage_discharge_blocked",
        translation_key="cell_voltage_discharge_blocked",
        runtime_key="cell_voltage_discharge_blocked",
        device_class=SensorDeviceClass.ENUM,
        options=BOOLEAN_STATE_ENUMS,
        icon="mdi:battery-lock",
    ),

    # --------------------------------------------------
    # DEBUG RECORDING (V4.4.0)
    # --------------------------------------------------
    ZendureSensorEntityDescription(
        key="debug_recording_active",
        translation_key="debug_recording_active",
        runtime_key="debug_recording_active",
        device_class=SensorDeviceClass.ENUM,
        options=BOOLEAN_STATE_ENUMS,
        icon="mdi:bug-play-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ZendureSensorEntityDescription(
        key="debug_recording_ends_at",
        translation_key="debug_recording_ends_at",
        runtime_key="debug_recording_ends_at",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:timer-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ZendureSensorEntityDescription(
        key="debug_sample_count",
        translation_key="debug_sample_count",
        runtime_key="debug_sample_count",
        icon="mdi:counter",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ZendureSensorEntityDescription(
        key="debug_last_package",
        translation_key="debug_last_package",
        runtime_key="debug_last_package",
        icon="mdi:file-code-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ZendureSensorEntityDescription(
        key="debug_last_error",
        translation_key="debug_last_error",
        runtime_key="debug_last_error",
        icon="mdi:bug-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
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
        icon="mdi:tune-variant",
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


# V4.4.0: Deep technical diagnostics now live in bounded JSON packages instead
# of permanent Recorder-facing entities. Keep only the five sparse recording
# status sensors from the diagnostic category.
DEBUG_STATUS_SENSOR_KEYS = frozenset(
    {
        "debug_recording_active",
        "debug_recording_ends_at",
        "debug_sample_count",
        "debug_last_package",
        "debug_last_error",
    }
)

RETIRED_DIAGNOSTIC_SENSOR_KEYS = frozenset(
    description.key
    for description in _SENSOR_DESCRIPTIONS
    if description.entity_category == EntityCategory.DIAGNOSTIC
    and description.key not in DEBUG_STATUS_SENSOR_KEYS
)

SENSORS: tuple[ZendureSensorEntityDescription, ...] = tuple(
    description
    for description in _SENSOR_DESCRIPTIONS
    if description.key not in RETIRED_DIAGNOSTIC_SENSOR_KEYS
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    add_entities: AddEntitiesCallback,
) -> None:
    registry = er.async_get(hass)
    for key in RETIRED_DIAGNOSTIC_SENSOR_KEYS:
        unique_id = f"{DOMAIN}_{entry.entry_id}_{key}"
        entity_id = registry.async_get_entity_id("sensor", DOMAIN, unique_id)
        if entity_id is not None:
            registry.async_remove(entity_id)

    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [ZendureSmartFlowSensor(entry, coordinator, d) for d in SENSORS]
    add_entities(entities)


class ZendureSmartFlowSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, entry, coordinator, description):
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry

        if description.runtime_key in PRICE_SENSOR_KEYS:
            self._attr_native_unit_of_measurement = (
                coordinator.price_currency.price_unit
            )
            self._attr_suggested_display_precision = price_input_profile(
                coordinator.price_currency
            ).display_precision
        elif description.runtime_key in MONETARY_SENSOR_KEYS:
            self._attr_native_unit_of_measurement = (
                coordinator.price_currency.monetary_unit
            )

        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{description.key}"

        if description.economics_device:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, f"{entry.entry_id}_economics")},
                translation_key="economics_and_prices",
                manufacturer=INTEGRATION_MANUFACTURER,
                model=virtual_device_model(coordinator.hass.config.language),
                sw_version=INTEGRATION_VERSION,
                via_device=(DOMAIN, entry.entry_id),
            )
        else:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, entry.entry_id)},
                translation_key="control_and_planning",
                manufacturer=INTEGRATION_MANUFACTURER,
                model=INTEGRATION_MODEL,
                sw_version=INTEGRATION_VERSION,
            )

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

            if val is None:
                return None

            if options == BOOLEAN_STATE_ENUMS and isinstance(val, bool):
                return "yes" if val else "no"

            # Empty inactive reasons are represented by the stable enum state
            # "none" so the frontend can translate them as well.
            if val == "" and "none" in options:
                return "none"

            if val in options:
                return val

            # Unknown future enum values must never be mislabeled as the first
            # valid state. Keep the raw value visible for diagnostics.
            return str(val)

        val = details.get(key, data.get(key))

        if val is None:
            return None

        if key in {"debug_last_package", "debug_last_error"}:
            return safe_diagnostic_sensor_value(key, val)

        if key == "learned_planning_data_coverage":
            try:
                return round(float(val) * 100.0, 1)
            except Exception:
                return None

        if self.native_unit_of_measurement:
            try:
                return float(val)
            except Exception:
                return None

        return val
        
    def _handle_coordinator_update(self) -> None:
        """Keep recorder-facing entities attribute-free in normal operation."""

        self._attr_extra_state_attributes = None
        super()._handle_coordinator_update()
