"""Registration helpers for the optional Battery SmartFlow AI panel."""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_BATTERY_AC_POWER_ENTITY,
    CONF_BATTERY_GROUPS,
    CONF_ENERGY_SCOPES,
    CONF_GRID_EXPORT_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_GRID_POWER_ENTITY,
    CONF_HEMS_DASHBOARD_ENABLED,
    CONF_NATIVE_PV_ENTITY,
    CONF_NATIVE_ZENDURE_DEVICE_SETUPS,
    CONF_OFFGRID_POWER_ENTITY,
    CONF_PRICE_NOW_ENTITY,
    CONF_PV_ENTITY,
    CONF_PV_FORECAST_CONFIG_ENTRIES,
    CONF_PV_FORECAST_TODAY_ENTITY,
    CONF_PV_FORECAST_TOMORROW_ENTITY,
    CONF_SOC_ENTITY,
    DOMAIN,
    GRID_MODE_SHELLY_3EM,
    GRID_MODE_SHELLY_PRO_3EM,
    GRID_MODE_SHELLY_PRO_3EM_MODBUS,
    INTEGRATION_VERSION,
)
from .energy_scopes import normalize_energy_scope_config

_PANEL_PATH = "battery-smartflow-ai"
_PANEL_URL = "/battery_smartflow_ai/hems-dashboard.js"
_SF2400AC_IMAGE_URL = "/battery_smartflow_ai/images/sf2400ac.png"
_SF2400AC_PLUS_IMAGE_URL = "/battery_smartflow_ai/images/sf2400ac-plus.png"
_SF2400ACPRO_IMAGE_URL = "/battery_smartflow_ai/images/sf2400acpro.png"
_SF1600AC_PLUS_IMAGE_URL = "/battery_smartflow_ai/images/sf1600ac-plus.png"
_HYPER2000_IMAGE_URL = "/battery_smartflow_ai/images/hyper2000.png"
_HUB2000_IMAGE_URL = "/battery_smartflow_ai/images/hub2000.png"
_SF800_IMAGE_URL = "/battery_smartflow_ai/images/sf800.png"
_SF800PRO_IMAGE_URL = "/battery_smartflow_ai/images/sf800pro.png"
_SF800PRO2_IMAGE_URL = "/battery_smartflow_ai/images/sf800pro2.png"
_SF800PLUS_IMAGE_URL = "/battery_smartflow_ai/images/sf800plus.png"
_PANEL_NAME = "battery-smartflow-ai-hems-dashboard"
_STATIC_PATH_KEY = f"{DOMAIN}_dashboard_static_registered"
_STATIC_PATH_LOCK_KEY = f"{DOMAIN}_dashboard_static_registration_lock"
DASHBOARD_VERSION = "1.0.48"

_SYSTEM_SIGNAL_SENSOR_KEYS = (
    "native_zendure_status",
    "native_zendure_control",
    "native_zendure_device_count",
    "native_zendure_message_count",
    "native_zendure_last_capture",
    "native_zendure_error",
    "native_zendure_watchdog",
    "forecast_status",
    "grid_power",
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

    update_lock = hass.data.setdefault(
        f"{DOMAIN}_dashboard_update_lock", asyncio.Lock()
    )
    async with update_lock:
        await _async_update_dashboard_panel_locked(hass)


async def _async_update_dashboard_panel_locked(hass: HomeAssistant) -> None:
    """Build and register the panel while holding the update lock."""

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
    training_entries = []
    sensor_entities: dict[str, list[str]] = {key: [] for key in _DASHBOARD_SENSOR_KEYS}
    forecast_source_keys = set()
    battery_groups = []
    entity_registry = er.async_get(hass)
    for entry in entries:
        if entry is None:
            continue
        group_config = entry.options.get(CONF_BATTERY_GROUPS, {})
        groups = group_config.get("groups", {}) if isinstance(group_config, dict) else {}
        setup_config = entry.options.get(CONF_NATIVE_ZENDURE_DEVICE_SETUPS, {})
        setup_devices = (
            setup_config.get("devices", {}) if isinstance(setup_config, dict) else {}
        )

        def device_label(device_id, setup_devices=setup_devices):
            public_id = "ZD_DEVICE_" + hashlib.sha256(
                f"bsfai:DEVICE:{device_id}".encode()
            ).hexdigest()[:12]
            record = setup_devices.get(device_id, {}) if isinstance(setup_devices, dict) else {}
            if isinstance(record, dict):
                label = str(record.get("display_name") or record.get("model") or "Zendure")
                model = str(record.get("model") or "").strip()
                if model and model.casefold() not in label.casefold():
                    label = f"{label} – {model}"
                if record.get("serial_suffix"):
                    label = f"{label} · SN {record['serial_suffix']}"
                return {
                    "id": public_id,
                    "label": label,
                    "model": model or None,
                    "transport": record.get("transport"),
                    "pack_count": record.get("pack_count"),
                    "online": record.get("online"),
                    "setup_status": record.get("setup_status"),
                }
            return {
                "id": public_id,
                "label": f"Offline / nicht erkannt ({hashlib.sha256(device_id.encode()).hexdigest()[:6]})",
                "online": False,
                "setup_status": "unknown",
            }

        claimed = set()
        group_summaries = []
        if isinstance(groups, dict):
            for group_id, group in groups.items():
                if not isinstance(group_id, str) or not isinstance(group, dict):
                    continue
                members = group.get("members", [])
                if not isinstance(members, list):
                    continue
                claimed.update(member for member in members if isinstance(member, str))
                group_summaries.append(
                    {
                        "name": str(group.get("name") or "Gruppe"),
                        "members": [device_label(member) for member in members if isinstance(member, str)],
                    }
                )
        ungrouped = []
        if isinstance(setup_devices, dict):
            for device_id, record in setup_devices.items():
                if (
                    isinstance(device_id, str)
                    and isinstance(record, dict)
                    and record.get("setup_status") in {"configured", "setup_required"}
                    and device_id not in claimed
                ):
                    ungrouped.append(device_label(device_id))
        raw_scopes = entry.options.get(CONF_ENERGY_SCOPES)
        try:
            scope_config = normalize_energy_scope_config(raw_scopes)
        except (TypeError, ValueError):
            scope_config = {"scopes": {}}
        group_names = {
            group_id: str(group.get("name") or "Gruppe")
            for group_id, group in groups.items()
            if isinstance(group_id, str) and isinstance(group, dict)
        } if isinstance(groups, dict) else {}
        scope_summaries = []
        for scope_id, scope in scope_config["scopes"].items():
            grid_entities = (
                scope["grid_power_entities"]
                + scope["grid_import_entities"]
                + scope["grid_export_entities"]
            )
            scope_summaries.append(
                {
                    "id": scope_id,
                    "name": scope["name"],
                    "groups": [
                        group_names[group_id]
                        for group_id in scope["group_ids"]
                        if group_id in group_names
                    ],
                    "grid_mode": scope["grid_mode"],
                    "grid_entities": grid_entities,
                    "grid_phase_entities": scope["grid_phase_power_entities"],
                    "pv_sources": [
                        {
                            "name": source["name"],
                            "mode": source["mode"],
                            "power_entities": source["power_entities"],
                            "forecast_count": len(source["forecast_entry_ids"]),
                        }
                        for source in scope["pv_sources"]
                    ],
                }
            )
        battery_groups.append(
            {
                "entry_id": entry.entry_id,
                "system": entry.title,
                "groups": group_summaries,
                "ungrouped": ungrouped,
                "energy_scopes": scope_summaries,
            }
        )
        training_entries.append(
            {
                "entry_id": entry.entry_id,
                "title": entry.title,
                "active_entity": entity_registry.async_get_entity_id(
                    "sensor",
                    DOMAIN,
                    f"{DOMAIN}_{entry.entry_id}_regulation_training_active",
                ),
                "samples_entity": entity_registry.async_get_entity_id(
                    "sensor",
                    DOMAIN,
                    f"{DOMAIN}_{entry.entry_id}_regulation_training_sample_count",
                ),
                "result_entity": entity_registry.async_get_entity_id(
                    "sensor",
                    DOMAIN,
                    f"{DOMAIN}_{entry.entry_id}_regulation_training_result",
                ),
                "debug_active_entity": entity_registry.async_get_entity_id(
                    "sensor",
                    DOMAIN,
                    f"{DOMAIN}_{entry.entry_id}_debug_recording_active",
                ),
                "debug_samples_entity": entity_registry.async_get_entity_id(
                    "sensor",
                    DOMAIN,
                    f"{DOMAIN}_{entry.entry_id}_debug_sample_count",
                ),
                "debug_ends_entity": entity_registry.async_get_entity_id(
                    "sensor",
                    DOMAIN,
                    f"{DOMAIN}_{entry.entry_id}_debug_recording_ends_at",
                ),
            }
        )
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
            "entry_id": entry.entry_id,
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
            "house_load": entity_registry.async_get_entity_id(
                "sensor",
                DOMAIN,
                f"{DOMAIN}_{entry.entry_id}_house_load",
            ),
        }
        if data.get("grid_mode") in (
            GRID_MODE_SHELLY_PRO_3EM,
            GRID_MODE_SHELLY_PRO_3EM_MODBUS,
            GRID_MODE_SHELLY_3EM,
        ):
            sources["grid_power"] = entity_registry.async_get_entity_id(
                "sensor",
                DOMAIN,
                f"{DOMAIN}_{entry.entry_id}_grid_power",
            )
        configured_price = data.get(CONF_PRICE_NOW_ENTITY)
        if configured_price and configured_price not in sensor_entities["price_now"]:
            sensor_entities["price_now"].append(configured_price)

        unique_prefix = f"{DOMAIN}_{entry.entry_id}_"
        native_main_prefix = f"{unique_prefix}native_main_"
        native_battery_power: dict[str, dict[str, str]] = {}
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
            if registry_entry.unique_id.startswith(native_main_prefix):
                for suffix, field in (
                    ("_charge_power_w", "charge_entity"),
                    ("_discharge_power_w", "discharge_entity"),
                ):
                    if registry_entry.unique_id.endswith(suffix):
                        public_id = registry_entry.unique_id[
                            len(native_main_prefix) : -len(suffix)
                        ]
                        native_battery_power.setdefault(public_id, {})[field] = (
                            registry_entry.entity_id
                        )
        sources["native_battery_power"] = list(native_battery_power.values())
        if any(value for key, value in sources.items() if key not in {"name", "entry_id"}):
            power_sources.append(sources)

    # Multiple config entries can reach dashboard setup concurrently. Protect
    # the check-and-register sequence so each instance cannot register the
    # same GET route before the other one marks it as registered.
    frontend_dir = Path(__file__).parent / "frontend"
    panel_module_version = hashlib.sha256(
        (frontend_dir / "hems-dashboard.js").read_bytes()
    ).hexdigest()[:12]

    registration_lock = hass.data.setdefault(_STATIC_PATH_LOCK_KEY, asyncio.Lock())
    async with registration_lock:
        if not hass.data.get(_STATIC_PATH_KEY):
            await hass.http.async_register_static_paths(
                [
                    StaticPathConfig(
                        _PANEL_URL,
                        str(frontend_dir / "hems-dashboard.js"),
                        cache_headers=True,
                    ),
                    StaticPathConfig(
                        _SF2400AC_IMAGE_URL,
                        str(frontend_dir / "images" / "sf2400ac.png"),
                        cache_headers=True,
                    ),
                    StaticPathConfig(
                        _SF2400AC_PLUS_IMAGE_URL,
                        str(frontend_dir / "images" / "sf2400ac-plus.png"),
                        cache_headers=True,
                    ),
                    StaticPathConfig(
                        _SF2400ACPRO_IMAGE_URL,
                        str(frontend_dir / "images" / "sf2400acpro.png"),
                        cache_headers=True,
                    ),
                    StaticPathConfig(
                        _SF1600AC_PLUS_IMAGE_URL,
                        str(frontend_dir / "images" / "sf1600ac-plus.png"),
                        cache_headers=True,
                    ),
                    StaticPathConfig(
                        _HYPER2000_IMAGE_URL,
                        str(frontend_dir / "images" / "hyper2000.png"),
                        cache_headers=True,
                    ),
                    StaticPathConfig(
                        _HUB2000_IMAGE_URL,
                        str(frontend_dir / "images" / "hub2000.png"),
                        cache_headers=True,
                    ),
                    StaticPathConfig(
                        _SF800_IMAGE_URL,
                        str(frontend_dir / "images" / "sf800.png"),
                        cache_headers=True,
                    ),
                    StaticPathConfig(
                        _SF800PRO_IMAGE_URL,
                        str(frontend_dir / "images" / "sf800pro.png"),
                        cache_headers=True,
                    ),
                    StaticPathConfig(
                        _SF800PRO2_IMAGE_URL,
                        str(frontend_dir / "images" / "sf800pro2.png"),
                        cache_headers=True,
                    ),
                    StaticPathConfig(
                        _SF800PLUS_IMAGE_URL,
                        str(frontend_dir / "images" / "sf800plus.png"),
                        cache_headers=True,
                    ),
                ]
            )
            hass.data[_STATIC_PATH_KEY] = True

    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=_PANEL_PATH,
        webcomponent_name=_PANEL_NAME,
        sidebar_title="BSFAI Portal",
        sidebar_icon="mdi:solar-power-variant",
        module_url=f"{_PANEL_URL}?v={panel_module_version}",
        config={
            "title": "Battery SmartFlow AI",
            "integration_version": INTEGRATION_VERSION,
            "dashboard_version": DASHBOARD_VERSION,
            "power_sources": power_sources,
            "forecast_sources": forecast_sources,
            "sensor_entities": sensor_entities,
            "training_entries": training_entries,
            "battery_groups": battery_groups,
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
