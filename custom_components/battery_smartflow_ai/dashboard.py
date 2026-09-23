"""Registration helpers for the optional Battery SmartFlow AI panel."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import (
    CONF_BATTERY_AC_POWER_ENTITY,
    CONF_GRID_EXPORT_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_GRID_POWER_ENTITY,
    CONF_HEMS_DASHBOARD_ENABLED,
    CONF_NATIVE_PV_ENTITY,
    CONF_OFFGRID_POWER_ENTITY,
    CONF_PV_ENTITY,
    CONF_SOC_ENTITY,
    DOMAIN,
)

_PANEL_PATH = "battery-smartflow-ai"
_PANEL_URL = "/battery_smartflow_ai/hems-dashboard.js"
_PANEL_NAME = "battery-smartflow-ai-hems-dashboard"
_STATIC_PATH_KEY = f"{DOMAIN}_dashboard_static_registered"


async def async_update_dashboard_panel(hass: HomeAssistant) -> None:
    """Register the panel whenever at least one config entry opts in."""

    loaded_entry_ids = hass.data.get(DOMAIN, {})
    entries = [
        hass.config_entries.async_get_entry(entry_id)
        for entry_id in loaded_entry_ids
    ]
    enabled = any(
        entry is not None
        and bool(entry.options.get(CONF_HEMS_DASHBOARD_ENABLED, False))
        for entry in entries
    )

    frontend.async_remove_panel(hass, _PANEL_PATH, warn_if_unknown=False)
    if not enabled:
        return

    power_sources = []
    for entry in entries:
        if entry is None:
            continue
        data = entry.data
        sources = {
            "name": entry.title,
            "soc": data.get(CONF_SOC_ENTITY),
            "pv": data.get(CONF_PV_ENTITY),
            "native_pv": data.get(CONF_NATIVE_PV_ENTITY),
            "battery_power": (
                entry.options.get(CONF_BATTERY_AC_POWER_ENTITY)
                or data.get(CONF_BATTERY_AC_POWER_ENTITY)
            ),
            "grid_power": data.get(CONF_GRID_POWER_ENTITY),
            "grid_import": data.get(CONF_GRID_IMPORT_ENTITY),
            "grid_export": data.get(CONF_GRID_EXPORT_ENTITY),
            "offgrid_power": data.get(CONF_OFFGRID_POWER_ENTITY),
        }
        if any(value for key, value in sources.items() if key != "name"):
            power_sources.append(sources)

    if not hass.data.get(_STATIC_PATH_KEY):
        panel_file = Path(__file__).parent / "frontend" / "hems-dashboard.js"
        await hass.http.async_register_static_paths(
            [StaticPathConfig(_PANEL_URL, str(panel_file), cache_headers=True)]
        )
        hass.data[_STATIC_PATH_KEY] = True

    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=_PANEL_PATH,
        webcomponent_name=_PANEL_NAME,
        sidebar_title="SmartFlow",
        sidebar_icon="mdi:solar-power-variant",
        module_url=f"{_PANEL_URL}?v=11",
        config={"title": "Battery SmartFlow AI", "power_sources": power_sources},
        require_admin=False,
        handle_safe_area=True,
    )
