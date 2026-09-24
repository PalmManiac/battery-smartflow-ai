"""Registration helpers for the optional Battery SmartFlow AI panel."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_BATTERY_AC_POWER_ENTITY,
    CONF_GRID_EXPORT_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_GRID_POWER_ENTITY,
    CONF_HEMS_DASHBOARD_ENABLED,
    CONF_NATIVE_PV_ENTITY,
    CONF_PRICE_NOW_ENTITY,
    CONF_OFFGRID_POWER_ENTITY,
    CONF_PV_ENTITY,
    CONF_PV_FORECAST_CONFIG_ENTRIES,
    CONF_PV_FORECAST_TODAY_ENTITY,
    CONF_PV_FORECAST_TOMORROW_ENTITY,
    CONF_SOC_ENTITY,
    DOMAIN,
    INTEGRATION_VERSION,
)

_PANEL_PATH = "battery-smartflow-ai"
_PANEL_URL = "/battery_smartflow_ai/hems-dashboard.js"
_PANEL_NAME = "battery-smartflow-ai-hems-dashboard"
_STATIC_PATH_KEY = f"{DOMAIN}_dashboard_static_registered"
DASHBOARD_VERSION = "1.0.6"

_SYSTEM_SIGNAL_SENSOR_KEYS = (
    "native_zendure_status",
    "native_zendure_control",
    "native_zendure_device_count",
    "native_zendure_message_count",
    "native_zendure_last_capture",
    "native_zendure_error",
    "forecast_status",
)

_DASHBOARD_SENSOR_KEYS = (
    "forecast_status",
    "forecast_remaining_today_kwh",
    "forecast_tomorrow_kwh",
    "forecast_gross_remaining_today_kwh",
    "forecast_gross_tomorrow_kwh",
    "forecast_next_3h_kwh",
    "forecast_next_6h_kwh",
    "forecast_gross_next_3h_kwh",
    "forecast_gross_next_6h_kwh",
    "price_now",
    "price_daily_average",
    "current_peak_threshold",
    "current_valley_threshold",
    "learned_planning_required_charge_energy_kwh",
    "learned_planning_pv_forecast_credit_kwh",
    "learned_planning_coverage_end",
    "economics_daily_grid_to_battery_kwh",
    "economics_daily_pv_to_battery_kwh",
    "economics_daily_grid_export_kwh",
    "economics_daily_battery_to_home_kwh",
    "economics_daily_battery_to_grid_kwh",
    "economics_daily_native_pv_to_home_kwh",
    "economics_daily_battery_benefit",
    "economics_daily_avoided_grid_import_cost",
    "economics_daily_grid_charge_cost",
    "economics_daily_pv_opportunity_cost",
    "economics_daily_export_revenue",
    "economics_daily_native_pv_self_consumption_value",
    "economics_average_grid_charge_price",
    "economics_average_pv_opportunity_value",
    "economics_average_battery_charge_price",
    "economics_average_export_price",
    "economics_average_battery_discharge_value",
    "economics_average_native_pv_to_home_return",
    "economics_total_economic_efficiency_pct",
)


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
    forecast_sources = []
    sensor_entities: dict[str, list[str]] = {key: [] for key in _DASHBOARD_SENSOR_KEYS}
    forecast_source_keys = set()
    entity_registry = er.async_get(hass)
    for entry in entries:
        if entry is None:
            continue
        data = entry.data
        configured_forecasts = data.get(CONF_PV_FORECAST_CONFIG_ENTRIES, ()) or ()
        if isinstance(configured_forecasts, str):
            configured_forecasts = (configured_forecasts,)
        for forecast_entry_id in configured_forecasts:
            forecast_entry = hass.config_entries.async_get_entry(forecast_entry_id)
            if forecast_entry is None:
                continue
            label = str(forecast_entry.title or forecast_entry.domain or "").strip()
            if label and forecast_entry.domain:
                label = f"{label} ({forecast_entry.domain})"
            key = label.casefold()
            if label and key not in forecast_source_keys:
                forecast_source_keys.add(key)
                forecast_sources.append(label)
        if not configured_forecasts:
            for forecast_entity_id in (
                data.get(CONF_PV_FORECAST_TODAY_ENTITY),
                data.get(CONF_PV_FORECAST_TOMORROW_ENTITY),
            ):
                forecast_state = (
                    hass.states.get(forecast_entity_id)
                    if forecast_entity_id
                    else None
                )
                label = (
                    forecast_state.attributes.get("friendly_name")
                    if forecast_state is not None
                    else None
                ) or forecast_entity_id
                key = str(label).casefold()
                if label and key not in forecast_source_keys:
                    forecast_source_keys.add(key)
                    forecast_sources.append(str(label))

        sources = {
            "name": entry.title,
            "soc": data.get(CONF_SOC_ENTITY),
            "price_now": data.get(CONF_PRICE_NOW_ENTITY),
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
        configured_price = data.get(CONF_PRICE_NOW_ENTITY)
        if configured_price and configured_price not in sensor_entities["price_now"]:
            sensor_entities["price_now"].append(configured_price)

        unique_prefix = f"{DOMAIN}_{entry.entry_id}_"
        for registry_entry in entity_registry.entities.values():
            if (
                registry_entry.config_entry_id != entry.entry_id
                or registry_entry.domain != "sensor"
                or registry_entry.platform != DOMAIN
                or not registry_entry.unique_id.startswith(unique_prefix)
            ):
                continue
            key = registry_entry.unique_id.removeprefix(unique_prefix)
            if key in sensor_entities and registry_entry.entity_id not in sensor_entities[key]:
                sensor_entities[key].append(registry_entry.entity_id)

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
            module_url=f"{_PANEL_URL}?v=20",
        config={
            "title": "Battery SmartFlow AI",
            "integration_version": INTEGRATION_VERSION,
            "dashboard_version": DASHBOARD_VERSION,
            "power_sources": power_sources,
            "forecast_sources": forecast_sources,
            "sensor_entities": sensor_entities,
            "system_signal_entity_ids": [
                registry_entry.entity_id
                for registry_entry in entity_registry.entities.values()
                if registry_entry.platform == DOMAIN
                and registry_entry.domain == "sensor"
                and any(
                    registry_entry.unique_id.endswith(f"_{key}")
                    for key in _SYSTEM_SIGNAL_SENSOR_KEYS
                )
            ],
        },
        require_admin=False,
        handle_safe_area=True,
    )
