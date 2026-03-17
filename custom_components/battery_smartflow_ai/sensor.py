from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .device_profiles import DEVICE_PROFILES
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
)

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
    # --- Numeric sensors ---
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

    # --------------------------------------------------
    # NACHTLADUNG TRANSPARENZ (v3.2)
    # --------------------------------------------------
    ZendureSensorEntityDescription(
        key="night_charge_status",
        translation_key="night_charge_status",
        runtime_key="night_charge_status",
        device_class=SensorDeviceClass.ENUM,
        options=["charging", "goal_reached", "no_need", "discharge_paused", "inactive"],
        icon="mdi:weather-night",
    ),
    ZendureSensorEntityDescription(
        key="night_charge_pv_kwh",
        translation_key="night_charge_pv_kwh",
        runtime_key="night_charge_pv_kwh",
        native_unit_of_measurement="kWh",
        icon="mdi:solar-power",
    ),
    ZendureSensorEntityDescription(
        key="night_charge_byd_target_soc",
        translation_key="night_charge_byd_target_soc",
        runtime_key="night_charge_byd_target_soc",
        native_unit_of_measurement="%",
        icon="mdi:battery-arrow-up-outline",
    ),
    ZendureSensorEntityDescription(
        key="night_charge_byd_kwh",
        translation_key="night_charge_byd_kwh",
        runtime_key="night_charge_byd_kwh",
        native_unit_of_measurement="kWh",
        icon="mdi:battery-arrow-up-outline",
    ),
    ZendureSensorEntityDescription(
        key="night_charge_zendure_target_soc",
        translation_key="night_charge_zendure_target_soc",
        runtime_key="night_charge_zendure_target_soc",
        native_unit_of_measurement="%",
        icon="mdi:lightning-bolt",
    ),
    ZendureSensorEntityDescription(
        key="night_charge_zendure_kwh",
        translation_key="night_charge_zendure_kwh",
        runtime_key="night_charge_zendure_kwh",
        native_unit_of_measurement="kWh",
        icon="mdi:lightning-bolt",
    ),
    ZendureSensorEntityDescription(
        key="total_available_kwh",
        translation_key="total_available_kwh",
        runtime_key="total_available_kwh",
        native_unit_of_measurement="kWh",
        icon="mdi:battery-high",
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

        # -------------------------
        # TIMESTAMP
        # -------------------------
        if self.device_class == SensorDeviceClass.TIMESTAMP:
            val = data.get(key)
            if val is None:
                return None
            if hasattr(val, "tzinfo"):
                return dt_util.as_utc(val)
            if isinstance(val, str):
                dt = dt_util.parse_datetime(val)
                return dt_util.as_utc(dt) if dt else None
            return None

        # -------------------------
        # ENUM
        # -------------------------
        if self.device_class == SensorDeviceClass.ENUM:
            val = details.get(key, data.get(key))
            options = self.entity_description.options or []
            if val in options:
                return val
            return options[0] if options else None

        # -------------------------
        # NUMERIC
        # -------------------------
        val = details.get(key, data.get(key))

        if val is None:
            return None

        # Numeric detection via unit
        if self.entity_description.native_unit_of_measurement:
            try:
                return float(val)
            except Exception:
                return None

        return val

    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data or {}
        self._attr_extra_state_attributes = data.get("details") or {}
        super()._handle_coordinator_update()
