"""Registration helpers for the optional Battery SmartFlow AI panel."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import CONF_HEMS_DASHBOARD_ENABLED, DOMAIN

_PANEL_PATH = "battery-smartflow-ai"
_PANEL_URL = "/battery_smartflow_ai/hems-dashboard.js"
_PANEL_NAME = "battery-smartflow-ai-hems-dashboard"
_STATIC_PATH_KEY = f"{DOMAIN}_dashboard_static_registered"


async def async_update_dashboard_panel(hass: HomeAssistant) -> None:
    """Register the panel whenever at least one config entry opts in."""

    loaded_entry_ids = hass.data.get(DOMAIN, {})
    entries = (
        hass.config_entries.async_get_entry(entry_id)
        for entry_id in loaded_entry_ids
    )
    enabled = any(
        entry is not None
        and bool(entry.options.get(CONF_HEMS_DASHBOARD_ENABLED, False))
        for entry in entries
    )

    frontend.async_remove_panel(hass, _PANEL_PATH, warn_if_unknown=False)
    if not enabled:
        return

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
        module_url=f"{_PANEL_URL}?v=1",
        config={"title": "Battery SmartFlow AI"},
        require_admin=False,
        handle_safe_area=True,
    )
