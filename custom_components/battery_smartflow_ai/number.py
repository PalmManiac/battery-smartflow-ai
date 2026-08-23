from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
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
    SETTING_VALLEY_FACTOR,
    DEFAULT_VALLEY_FACTOR,
    SETTING_VERY_CHEAP_PRICE,
    DEFAULT_VERY_CHEAP_PRICE,
    SETTING_PV_CHARGE_START_EXPORT_W,
    DEFAULT_PV_CHARGE_START_EXPORT_W,
    SETTING_FORECAST_BASE_LOAD,
    DEFAULT_FORECAST_BASE_LOAD,
)
from .price_currency import price_input_profile
from .factor_display import (
    discount_pct_to_valley_factor,
    markup_pct_to_peak_factor,
    peak_factor_to_markup_pct,
    valley_factor_to_discount_pct,
)


PRICE_NUMBER_KEYS = frozenset(
    {
        SETTING_VERY_CHEAP_PRICE,
        SETTING_VERY_EXPENSIVE_THRESHOLD,
    }
)


@dataclass(frozen=True, kw_only=True)
class ZendureNumberEntityDescription(NumberEntityDescription):
    runtime_key: str
    factor_percentage_kind: str | None = None


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
        factor_percentage_kind="peak_markup",
        native_min_value=0,
        native_max_value=150,
        native_step=1,
        native_unit_of_measurement="%",
        mode="box",
        icon="mdi:chart-bell-curve",
    ),
    ZendureNumberEntityDescription(
        key=SETTING_VALLEY_FACTOR,
        translation_key="valley_factor",
        runtime_key=SETTING_VALLEY_FACTOR,
        factor_percentage_kind="valley_discount",
        native_min_value=0,
        native_max_value=50,
        native_step=1,
        native_unit_of_measurement="%",
        mode="box",
        icon="mdi:chart-bell-curve",
    ),
    ZendureNumberEntityDescription(
        key=SETTING_VERY_CHEAP_PRICE,
        translation_key="very_cheap_price",
        runtime_key=SETTING_VERY_CHEAP_PRICE,
        native_min_value=-1.0,
        native_max_value=1.0,
        native_step=0.01,
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
        key=SETTING_FORECAST_BASE_LOAD,
        translation_key="forecast_base_load",
        runtime_key=SETTING_FORECAST_BASE_LOAD,
        native_min_value=0,
        native_max_value=3000,
        native_step=10,
        native_unit_of_measurement="W",
        icon="mdi:home-lightning-bolt",
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
        native_max_value=4000,
        native_step=50,
        native_unit_of_measurement="W",
        icon="mdi:battery-arrow-up",
    ),
    ZendureNumberEntityDescription(
        key=SETTING_MAX_DISCHARGE,
        translation_key="max_discharge",
        runtime_key=SETTING_MAX_DISCHARGE,
        native_min_value=0,
        native_max_value=4000,
        native_step=50,
        native_unit_of_measurement="W",
        icon="mdi:battery-arrow-down",
    ),
    ZendureNumberEntityDescription(
        key=SETTING_EMERGENCY_CHARGE,
        translation_key="emergency_charge",
        runtime_key=SETTING_EMERGENCY_CHARGE,
        native_min_value=0,
        native_max_value=4000,
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
        icon="mdi:cash",
    ),
)


def _default_for_key(key: str, price_currency=None) -> float:
    if key == SETTING_VERY_EXPENSIVE_THRESHOLD and price_currency is not None:
        return price_input_profile(
            price_currency
        ).default_very_expensive_threshold

    defaults: dict[str, float] = {
        SETTING_BATTERY_PACKS: DEFAULT_BATTERY_PACKS,
        SETTING_PEAK_FACTOR: DEFAULT_PEAK_FACTOR,
        SETTING_VALLEY_FACTOR: DEFAULT_VALLEY_FACTOR,
        SETTING_VERY_CHEAP_PRICE: DEFAULT_VERY_CHEAP_PRICE,
        SETTING_PV_CHARGE_START_EXPORT_W: DEFAULT_PV_CHARGE_START_EXPORT_W,
        SETTING_FORECAST_BASE_LOAD: DEFAULT_FORECAST_BASE_LOAD,
        SETTING_SOC_MIN: DEFAULT_SOC_MIN,
        SETTING_SOC_MAX: DEFAULT_SOC_MAX,
        SETTING_MAX_CHARGE: DEFAULT_MAX_CHARGE,
        SETTING_MAX_DISCHARGE: DEFAULT_MAX_DISCHARGE,
        SETTING_EMERGENCY_CHARGE: DEFAULT_EMERGENCY_CHARGE,
        SETTING_EMERGENCY_SOC: DEFAULT_EMERGENCY_SOC,
        SETTING_PROFIT_MARGIN_PCT: DEFAULT_PROFIT_MARGIN_PCT,
        SETTING_VERY_EXPENSIVE_THRESHOLD: price_input_profile(
            "EUR"
        ).default_very_expensive_threshold,
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
                _default_for_key(key, coordinator.price_currency),
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

        if description.runtime_key in PRICE_NUMBER_KEYS:
            profile = price_input_profile(coordinator.price_currency)
            self._attr_native_min_value = profile.minimum
            self._attr_native_max_value = profile.maximum
            self._attr_native_step = profile.step
            self._attr_suggested_display_precision = profile.display_precision
            self._attr_native_unit_of_measurement = (
                coordinator.price_currency.price_unit
            )

        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "translation_key": "control_and_planning",
            "manufacturer": INTEGRATION_MANUFACTURER,
            "model": INTEGRATION_MODEL,
            "sw_version": INTEGRATION_VERSION,
        }

        if description.runtime_key not in coordinator.runtime_settings:
            coordinator.runtime_settings[description.runtime_key] = entry.options.get(
                description.runtime_key,
                _default_for_key(
                    description.runtime_key,
                    coordinator.price_currency,
                ),
            )

    @property
    def native_value(self) -> float:
        value = float(
            self.coordinator.runtime_settings.get(
                self.entity_description.runtime_key,
                _default_for_key(
                    self.entity_description.runtime_key,
                    self.coordinator.price_currency,
                ),
            )
        )

        if self.entity_description.factor_percentage_kind == "peak_markup":
            return peak_factor_to_markup_pct(value)
        if self.entity_description.factor_percentage_kind == "valley_discount":
            return valley_factor_to_discount_pct(value)
        return value

    async def async_set_native_value(self, value: float) -> None:
        value = float(value)

        if self.entity_description.factor_percentage_kind == "peak_markup":
            value = markup_pct_to_peak_factor(value)
        elif self.entity_description.factor_percentage_kind == "valley_discount":
            value = discount_pct_to_valley_factor(value)

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
