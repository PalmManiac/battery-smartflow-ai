from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    INTEGRATION_NAME,
    INTEGRATION_MANUFACTURER,
    INTEGRATION_MODEL,
    INTEGRATION_VERSION,
    SETTING_BATTERY_PACKS,
    DEFAULT_BATTERY_PACKS,
    SETTING_PEAK_FACTOR,
    DEFAULT_PEAK_FACTOR,
    SETTING_SOC_MIN,
    SETTING_SOC_MAX,
    SETTING_MAX_CHARGE,
    SETTING_MAX_DISCHARGE,
    SETTING_EMERGENCY_CHARGE,
    SETTING_EMERGENCY_SOC,
    SETTING_PROFIT_MARGIN_PCT,
    SETTING_VERY_EXPENSIVE_THRESHOLD,
    DEFAULT_SOC_MIN,
    DEFAULT_SOC_MAX,
    DEFAULT_MAX_CHARGE,
    DEFAULT_MAX_DISCHARGE,
    DEFAULT_EMERGENCY_CHARGE,
    DEFAULT_EMERGENCY_SOC,
    DEFAULT_PROFIT_MARGIN_PCT,
    DEFAULT_VERY_EXPENSIVE_THRESHOLD,
    SETTING_VALLEY_FACTOR,
    DEFAULT_VALLEY_FACTOR,
    SETTING_VERY_CHEAP_PRICE,
    DEFAULT_VERY_CHEAP_PRICE,
    SETTING_PV_CHARGE_START_EXPORT_W,
    DEFAULT_PV_CHARGE_START_EXPORT_W,
)


@dataclass(frozen=True, kw_only=True)
class ZendureNumberEntityDescription(NumberEntityDescription):
    runtime_key: str


NUMBERS: tuple[ZendureNumberEntityDescription, ...] = (
    ZendureNumberEntityDescription(
        key=SETTING_BATTERY_PACKS,
        translation_key="battery_packs",
        runtime_key=SETTING_BATTERY_PACKS,
        native_min_value=1,
        native_max_value=10,
        native_step=1,
        mode="box",
    ),
    ZendureNumberEntityDescription(
        key=SETTING_PEAK_FACTOR,
        translation_key="peak_factor",
        runtime_key=SETTING_PEAK_FACTOR,
        native_min_value=1.0,
        native_max_value=2.5,
        native_step=0.01,
        mode="box",
        icon="mdi:chart-bell-curve",
    ),
    ZendureNumberEntityDescription(
        key=SETTING_VALLEY_FACTOR,
        translation_key="valley_factor",
        runtime_key=SETTING_VALLEY_FACTOR,
        native_min_value=0.5,
        native_max_value=1.0,
        native_step=0.01,
        mode="box",
        icon="mdi:chart-bell-curve",
    ),
    ZendureNumberEntityDescription(
        key=SETTING_VERY_CHEAP_PRICE,
        translation_key="very_cheap_price",
        runtime_key=SETTING_VERY_CHEAP_PRICE,
        native_min_value=0.0,
        native_max_value=1.0,
        native_step=0.01,
        native_unit_of_measurement="€/kWh",
        icon="mdi:cash",
    ),
    ZendureNumberEntityDescription(
        key=SETTING_PV_CHARGE_START_EXPORT_W,
        translation_key="pv_charge_start_export_w",
        runtime_key=SETTING_PV_CHARGE_START_EXPORT_W,
        native_min_value=0,
        native_max_value=1000,
        native_step=10,
        native_unit_of_measurement="W",
        icon="mdi:solar-power-variant",
    ),
    ZendureNumberEntityDescription(
        key=SETTING_SOC_MIN,
        translation_key="soc_min",
        runtime_key=SETTING_SOC_MIN,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement="%",
        icon="mdi:battery-alert",
    ),
    ZendureNumberEntityDescription(
        key=SETTING_SOC_MAX,
        translation_key="soc_max",
        runtime_key=SETTING_SOC_MAX,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement="%",
        icon="mdi:battery-check",
    ),
    ZendureNumberEntityDescription(
        key=SETTING_MAX_CHARGE,
        translation_key="max_charge",
        runtime_key=SETTING_MAX_CHARGE,
        native_min_value=0,
        native_max_value=2400,
        native_step=50,
        native_unit_of_measurement="W",
        icon="mdi:battery-arrow-up",
    ),
    ZendureNumberEntityDescription(
        key=SETTING_MAX_DISCHARGE,
        translation_key="max_discharge",
        runtime_key=SETTING_MAX_DISCHARGE,
        native_min_value=0,
        native_max_value=2400,
        native_step=50,
        native_unit_of_measurement="W",
        icon="mdi:battery-arrow-down",
    ),
    ZendureNumberEntityDescription(
        key=SETTING_EMERGENCY_CHARGE,
        translation_key="emergency_charge",
        runtime_key=SETTING_EMERGENCY_CHARGE,
        native_min_value=0,
        native_max_value=2400,
        native_step=50,
        native_unit_of_measurement="W",
        icon="mdi:flash-alert",
    ),
    ZendureNumberEntityDescription(
        key=SETTING_EMERGENCY_SOC,
        translation_key="emergency_soc",
        runtime_key=SETTING_EMERGENCY_SOC,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement="%",
        icon="mdi:alert-circle",
    ),
    ZendureNumberEntityDescription(
        key=SETTING_PROFIT_MARGIN_PCT,
        translation_key="profit_margin_pct",
        runtime_key=SETTING_PROFIT_MARGIN_PCT,
        native_min_value=0,
        native_max_value=1000,
        native_step=1,
        native_unit_of_measurement="%",
        icon="mdi:chart-line",
    ),
    ZendureNumberEntityDescription(
        key=SETTING_VERY_EXPENSIVE_THRESHOLD,
        translation_key="very_expensive_threshold",
        runtime_key=SETTING_VERY_EXPENSIVE_THRESHOLD,
        native_min_value=0,
        native_max_value=2,
        native_step=0.01,
        native_unit_of_measurement="€/kWh",
        icon="mdi:currency-eur",
    ),
)


def _default_for_key(key: str) -> float:
    defaults: dict[str, float] = {
        SETTING_BATTERY_PACKS: DEFAULT_BATTERY_PACKS,
        SETTING_PEAK_FACTOR: DEFAULT_PEAK_FACTOR,
        SETTING_VALLEY_FACTOR: DEFAULT_VALLEY_FACTOR,
        SETTING_VERY_CHEAP_PRICE: DEFAULT_VERY_CHEAP_PRICE,
        SETTING_PV_CHARGE_START_EXPORT_W: DEFAULT_PV_CHARGE_START_EXPORT_W,
        SETTING_SOC_MIN: DEFAULT_SOC_MIN,
        SETTING_SOC_MAX: DEFAULT_SOC_MAX,
        SETTING_MAX_CHARGE: DEFAULT_MAX_CHARGE,
        SETTING_MAX_DISCHARGE: DEFAULT_MAX_DISCHARGE,
        SETTING_EMERGENCY_CHARGE: DEFAULT_EMERGENCY_CHARGE,
        SETTING_EMERGENCY_SOC: DEFAULT_EMERGENCY_SOC,
        SETTING_PROFIT_MARGIN_PCT: DEFAULT_PROFIT_MARGIN_PCT,
        SETTING_VERY_EXPENSIVE_THRESHOLD: DEFAULT_VERY_EXPENSIVE_THRESHOLD,
    }
    return float(defaults.get(key, 0.0))


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        ZendureSmartFlowNumber(entry, coordinator, description)
        for description in NUMBERS
    ]

    add_entities(entities)

    for ent in entities:
        key = ent.entity_description.runtime_key

        if key not in coordinator.runtime_settings:
            coordinator.runtime_settings[key] = entry.options.get(
                key,
                _default_for_key(key),
            )


class ZendureSmartFlowNumber(NumberEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator,
        description: ZendureNumberEntityDescription,
    ) -> None:
        self.entity_description = description
        self.coordinator = coordinator
        self._entry = entry

        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": INTEGRATION_NAME,
            "manufacturer": INTEGRATION_MANUFACTURER,
            "model": INTEGRATION_MODEL,
            "sw_version": INTEGRATION_VERSION,
        }

        if description.runtime_key not in coordinator.runtime_settings:
            coordinator.runtime_settings[description.runtime_key] = entry.options.get(
                description.runtime_key,
                _default_for_key(description.runtime_key),
            )

    @property
    def native_value(self) -> float:
        return float(
            self.coordinator.runtime_settings.get(
                self.entity_description.runtime_key,
                _default_for_key(self.entity_description.runtime_key),
            )
        )

    async def async_set_native_value(self, value: float) -> None:
        value = float(value)

        self.coordinator.runtime_settings[self.entity_description.runtime_key] = value

        self.hass.config_entries.async_update_entry(
            self._entry,
            options={
                **self._entry.options,
                self.entity_description.runtime_key: value,
            },
        )

        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )
