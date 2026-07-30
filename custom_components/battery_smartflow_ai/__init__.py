from __future__ import annotations

import logging

import homeassistant.helpers.config_validation as cv
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .coordinator import ZendureSmartFlowCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the integration (YAML not supported)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})

    coordinator = ZendureSmartFlowCoordinator(hass, entry)
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
        if coordinator:
            await coordinator.async_shutdown()
    return unload_ok

async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old config entries to new version."""
    new_version = int(entry.version)
    new_data = dict(entry.data)
    new_options = dict(entry.options)

    if new_version == 1:
        # Falls pack_capacity_kwh noch nicht existiert → Default setzen
        if "pack_capacity_kwh" not in new_data:
            new_data["pack_capacity_kwh"] = 2.88
        new_version = 2

    if new_version == 2:
        # V4.3.0-dev8.1:
        # The improved power regulation is now the only active command path.
        # Remove the obsolete user switch, including stored False values from
        # existing installations.
        new_options.pop("regulation_v42_enabled", None)
        new_version = 3

    if (
        new_version != entry.version
        or new_data != dict(entry.data)
        or new_options != dict(entry.options)
    ):
        hass.config_entries.async_update_entry(
            entry,
            data=new_data,
            options=new_options,
            version=new_version,
        )

    return True
