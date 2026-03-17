"""Switch entities for Battery SmartFlow AI."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    INTEGRATION_NAME,
    INTEGRATION_MANUFACTURER,
    INTEGRATION_MODEL,
    INTEGRATION_VERSION,
    SETTING_PV_FORECAST_ENABLED,
    DEFAULT_PV_FORECAST_ENABLED,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Battery SmartFlow AI switch entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    # Initialise runtime setting from stored options (persisted across restarts)
    coordinator.runtime_settings[SETTING_PV_FORECAST_ENABLED] = float(
        entry.options.get(SETTING_PV_FORECAST_ENABLED, DEFAULT_PV_FORECAST_ENABLED)
    )

    async_add_entities([PvNightChargeSwitch(coordinator, entry)])


class PvNightChargeSwitch(SwitchEntity):
    """Switch to enable/disable PV-forecast-based BYD night charging."""

    _attr_has_entity_name = True
    _attr_translation_key = "pv_forecast_enabled"
    _attr_icon = "mdi:weather-night"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        self.coordinator = coordinator
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_pv_forecast_enabled"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": INTEGRATION_NAME,
            "manufacturer": INTEGRATION_MANUFACTURER,
            "model": INTEGRATION_MODEL,
            "sw_version": INTEGRATION_VERSION,
        }

    @property
    def is_on(self) -> bool:
        return (
            float(
                self.coordinator.runtime_settings.get(
                    SETTING_PV_FORECAST_ENABLED, DEFAULT_PV_FORECAST_ENABLED
                )
            )
            >= 1.0
        )

    async def async_turn_on(self, **kwargs) -> None:
        self.coordinator.runtime_settings[SETTING_PV_FORECAST_ENABLED] = 1.0
        self.hass.config_entries.async_update_entry(
            self._entry,
            options={**self._entry.options, SETTING_PV_FORECAST_ENABLED: 1.0},
        )
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        self.coordinator.runtime_settings[SETTING_PV_FORECAST_ENABLED] = 0.0
        self.hass.config_entries.async_update_entry(
            self._entry,
            options={**self._entry.options, SETTING_PV_FORECAST_ENABLED: 0.0},
        )
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )
