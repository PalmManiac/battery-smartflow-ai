from __future__ import annotations

import logging

try:
    import homeassistant.helpers.config_validation as cv
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant, ServiceCall
except ModuleNotFoundError as err:
    if err.name is None or not err.name.startswith("homeassistant"):
        raise

    # Importing a neutral submodule first executes this package module.  Keep
    # that import path usable for standalone core tests without pretending
    # that Home Assistant is installed.
    CONFIG_SCHEMA = None
else:
    import voluptuous as vol

    from .const import DOMAIN, PLATFORMS
    from .coordinator import ZendureSmartFlowCoordinator

    CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)

SERVICE_START_DEBUG_RECORDING = "start_debug_recording"
SERVICE_STOP_DEBUG_RECORDING = "stop_debug_recording"


def _coordinator_for_call(hass: HomeAssistant, call: ServiceCall) -> ZendureSmartFlowCoordinator:
    """Resolve one config entry, defaulting only when it is unambiguous."""

    coordinators = hass.data.get(DOMAIN, {})
    entry_id = call.data.get("entry_id")
    if entry_id is None:
        if len(coordinators) == 1:
            return next(iter(coordinators.values()))
        raise ValueError(
            "entry_id is required when more than one Battery SmartFlow AI "
            "config entry is loaded"
        )
    coordinator = coordinators.get(str(entry_id))
    if coordinator is None:
        raise ValueError(f"Battery SmartFlow AI config entry not found: {entry_id}")
    return coordinator


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the integration (YAML not supported)."""
    if not hass.services.has_service(DOMAIN, SERVICE_START_DEBUG_RECORDING):
        async def async_start_debug_recording(call: ServiceCall) -> None:
            coordinator = _coordinator_for_call(hass, call)
            await coordinator.async_start_debug_recording(
                duration_minutes=int(call.data["duration_minutes"])
            )

        hass.services.async_register(
            DOMAIN,
            SERVICE_START_DEBUG_RECORDING,
            async_start_debug_recording,
            schema=vol.Schema(
                {
                    vol.Optional("entry_id"): str,
                    vol.Required("duration_minutes"): vol.All(
                        vol.Coerce(int),
                        vol.In({10, 30, 60, 120}),
                    ),
                }
            ),
        )

    if not hass.services.has_service(DOMAIN, SERVICE_STOP_DEBUG_RECORDING):
        async def async_stop_debug_recording(call: ServiceCall) -> None:
            coordinator = _coordinator_for_call(hass, call)
            await coordinator.async_stop_debug_recording()

        hass.services.async_register(
            DOMAIN,
            SERVICE_STOP_DEBUG_RECORDING,
            async_stop_debug_recording,
            schema=vol.Schema({vol.Optional("entry_id"): str}),
        )
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
