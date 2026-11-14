"""Native Home Assistant diagnostics download for the latest BSFAI package."""

from __future__ import annotations

import json
from functools import partial
from pathlib import Path
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_BATTERY_GROUPS,
    CONF_ELECTRICAL_TOPOLOGY,
    CONF_ENERGY_SCOPES,
    DOMAIN,
)
from .debug_exporter import DEBUG_DIRECTORY, _anonymize_entity_ids
from .debug_package import redact_secrets


def _multi_system_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    """Return a bounded, identity-scrubbed snapshot across active entries."""

    coordinators = hass.data.get(DOMAIN, {})
    entries = (
        [
            coordinator
            for coordinator in coordinators.values()
            if getattr(coordinator, "entry", None) is not None
        ]
        if isinstance(coordinators, dict)
        else []
    )
    identity_aliases: dict[str, str] = {}
    for coordinator in entries:
        runtime = getattr(coordinator, "native_zendure", None)
        selected = getattr(runtime, "selected_device_id", None)
        if isinstance(selected, str) and selected and selected not in identity_aliases:
            identity_aliases[selected] = f"system_{len(identity_aliases) + 1:02d}"
        setups = getattr(runtime, "_device_setups", {})
        if isinstance(setups, dict):
            for device_id in sorted(setups):
                if isinstance(device_id, str) and device_id not in identity_aliases:
                    identity_aliases[device_id] = (
                        f"system_{len(identity_aliases) + 1:02d}"
                    )
        options = dict(getattr(coordinator.entry, "options", {}))
        raw_groups = options.get(CONF_BATTERY_GROUPS, {})
        group_records = (
            raw_groups.get("groups", {}) if isinstance(raw_groups, dict) else {}
        )
        if isinstance(group_records, dict):
            for group_id in group_records:
                if isinstance(group_id, str) and group_id not in identity_aliases:
                    identity_aliases[group_id] = (
                        f"group_{len(identity_aliases) + 1:02d}"
                    )
        raw_scopes = options.get(CONF_ENERGY_SCOPES, {})
        scope_records = (
            raw_scopes.get("scopes", {}) if isinstance(raw_scopes, dict) else {}
        )
        if isinstance(scope_records, dict):
            for scope_id in scope_records:
                if isinstance(scope_id, str) and scope_id not in identity_aliases:
                    identity_aliases[scope_id] = (
                        f"scope_{len(identity_aliases) + 1:02d}"
                    )

    def anonymize(value: Any, *, key: str | None = None) -> Any:
        if isinstance(value, dict):
            return {
                str(anonymize(child_key)): anonymize(item, key=str(child_key))
                for child_key, item in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [anonymize(item, key=key) for item in value]
        if isinstance(value, str):
            if key in {"name", "display_name", "friendly_name"}:
                return "redacted_name"
            if value in identity_aliases:
                return identity_aliases[value]
            if ":" in value:
                transport, separator, identifier = value.partition(":")
                if separator and identifier in identity_aliases:
                    return f"{transport}:{identity_aliases[identifier]}"
        return value

    systems: list[dict[str, Any]] = []
    for index, coordinator in enumerate(entries, start=1):
        entry = coordinator.entry
        runtime = getattr(coordinator, "native_zendure", None)
        native_diagnostics = getattr(runtime, "diagnostic_data", None)
        try:
            native = native_diagnostics() if callable(native_diagnostics) else None
        except Exception:  # pragma: no cover - diagnostics must remain available
            native = {"status": "diagnostics_unavailable"}
        allocation_reader = getattr(runtime, "shadow_allocation_snapshots", None)
        try:
            allocation = (
                allocation_reader(reserve_soc_pct=10.0, maximum_soc_pct=100.0)
                if callable(allocation_reader)
                else []
            )
        except Exception:  # pragma: no cover - defensive diagnostic boundary
            allocation = {"status": "allocation_unavailable"}
        options = dict(getattr(entry, "options", {}))
        groups = options.get(CONF_BATTERY_GROUPS)
        scopes = options.get(CONF_ENERGY_SCOPES)
        topology = options.get(CONF_ELECTRICAL_TOPOLOGY)
        profile_reader = getattr(coordinator, "_get_active_profile", None)
        try:
            profile = profile_reader() if callable(profile_reader) else None
        except Exception:  # pragma: no cover - keep diagnostics resilient
            profile = {"status": "profile_unavailable"}
        persisted = getattr(coordinator, "_persist", {})
        group_runtime = {
            key: persisted[key]
            for key in (
                "group_control_status",
                "group_control_members",
                "group_control_last_targets",
                "group_control_handover_pending",
                "group_control_lead_state",
            )
            if isinstance(persisted, dict) and key in persisted
        }
        systems.append(
            {
                "system": f"entry_{index:02d}",
                "transport_and_device": native,
                "groups": groups,
                "energy_scopes": scopes,
                "electrical_topology": topology,
                "allocation_snapshot": allocation,
                "regulation_profile": profile,
                "group_runtime": group_runtime,
            }
        )
    snapshot = {"active_system_count": len(systems), "systems": systems}
    return _anonymize_entity_ids(redact_secrets(anonymize(snapshot)))


def _load_latest_package(path: str, *, config_directory: str) -> dict[str, Any]:
    """Load only a JSON package inside BSFAI's dedicated debug directory."""

    allowed_directory = (Path(config_directory).resolve() / DEBUG_DIRECTORY).resolve()
    package_path = Path(path).resolve()
    if package_path.parent != allowed_directory or not package_path.is_file():
        return {
            "status": "debug_package_unavailable",
            "message": "No downloadable Battery SmartFlow AI debug package is available.",
        }

    with package_path.open("r", encoding="utf-8") as handle:
        package = json.load(handle)
    return redact_secrets(package)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return the latest completed recording through HA's diagnostics download."""

    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    native = getattr(coordinator, "native_zendure", None)
    maintenance = getattr(coordinator, "_full_charge_maintenance", None)
    maintenance_data = (
        redact_secrets(maintenance.sensor_data())
        if maintenance is not None
        else None
    )
    native_path = native.capture_path if native is not None else None
    debug_path = (
        coordinator.debug_last_package_path if coordinator is not None else None
    )
    path = native_path or debug_path
    if not path:
        return {
            "status": "debug_package_unavailable",
            "message": "Create a debug recording or configure the native Zendure test first.",
            "native_zendure": (
                native.diagnostic_data() if native is not None else None
            ),
            "full_charge_maintenance": maintenance_data,
            "multi_system": _multi_system_snapshot(hass),
        }
    package = await hass.async_add_executor_job(
        partial(
            _load_latest_package,
            path,
            config_directory=hass.config.config_dir,
        )
    )
    if native_path:
        return {
            "native_zendure": native.diagnostic_data(),
            "full_charge_maintenance": maintenance_data,
            "package": package,
            "multi_system": _multi_system_snapshot(hass),
        }
    return {
        "package": package,
        "multi_system": _multi_system_snapshot(hass),
    }
