"""Safe V5-to-V6 configuration migration helpers."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from .const import (
    CONF_BATTERY_GROUPS,
    CONF_DYNAMIC_FEED_IN_PRICE_ENTITY,
    CONF_ENERGY_SCOPES,
    CONF_GRID_EXPORT_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_GRID_MODE,
    CONF_GRID_POWER_ENTITY,
    CONF_NATIVE_PV_ENTITY,
    CONF_PRICE_EXPORT_ENTITY,
    CONF_PRICE_NOW_ENTITY,
    CONF_PV_ENTITY,
    CONF_PV_FORECAST_CONFIG_ENTRIES,
    CONF_INSTALLED_PV_WP,
    GRID_MODE_NONE,
    GRID_MODE_SINGLE,
    GRID_MODE_SPLIT,
)
from .energy_scopes import (
    GRID_MODE_NONE as SCOPE_GRID_NONE,
    GRID_MODE_SIGNED as SCOPE_GRID_SIGNED,
    GRID_MODE_SPLIT as SCOPE_GRID_SPLIT,
    normalize_energy_scope_config,
)


def migrate_legacy_energy_scope(
    *, options: Mapping[str, Any], data: Mapping[str, Any]
) -> dict[str, Any]:
    """Copy legacy per-entry energy sources into the selected device's group scope.

    Old entry values remain intact for rollback and for settings not represented
    by the EnergyScope schema (for example direct forecast entities and the
    optional additional-battery sensors).
    """

    current = normalize_energy_scope_config(options.get(CONF_ENERGY_SCOPES))
    groups_config = options.get(CONF_BATTERY_GROUPS)
    groups = (
        groups_config.get("groups", {})
        if isinstance(groups_config, Mapping)
        else {}
    )
    selected_id = (
        options.get("native_zendure_selected_device")
        or data.get("native_zendure_selected_device")
    )
    if not isinstance(selected_id, str) or not isinstance(groups, Mapping):
        return current

    group_id = None
    group_name = None
    for candidate_id, group in groups.items():
        if not isinstance(group, Mapping):
            continue
        if selected_id in group.get("members", ()):
            group_id = str(candidate_id)
            group_name = str(group.get("name") or "System")
            break
    if group_id is None:
        return current

    scopes = dict(current["scopes"])
    if any(group_id in scope.get("group_ids", ()) for scope in scopes.values()):
        return current

    grid_mode_value = str(data.get(CONF_GRID_MODE, GRID_MODE_NONE))
    if grid_mode_value not in {GRID_MODE_NONE, GRID_MODE_SINGLE, GRID_MODE_SPLIT}:
        # Shelly-backed legacy grid inputs are entry-level connections and
        # cannot be represented as ordinary EnergyScope entity assignments.
        return current
    if grid_mode_value == GRID_MODE_SINGLE:
        grid_mode = SCOPE_GRID_SIGNED
        grid_power = _entity_list(data.get(CONF_GRID_POWER_ENTITY))
        grid_import: list[str] = []
        grid_export: list[str] = []
        if not grid_power:
            grid_mode = SCOPE_GRID_NONE
    elif grid_mode_value == GRID_MODE_SPLIT:
        grid_mode = SCOPE_GRID_SPLIT
        grid_power = []
        grid_import = _entity_list(data.get(CONF_GRID_IMPORT_ENTITY))
        grid_export = _entity_list(data.get(CONF_GRID_EXPORT_ENTITY))
        if not grid_import or not grid_export:
            grid_mode = SCOPE_GRID_NONE
            grid_import = []
            grid_export = []
    else:
        grid_mode = SCOPE_GRID_NONE
        grid_power = []
        grid_import = []
        grid_export = []

    pv_entity = data.get(CONF_PV_ENTITY) or data.get(CONF_NATIVE_PV_ENTITY)
    pv_entities = _entity_list(pv_entity)
    forecasts = _entity_list(data.get(CONF_PV_FORECAST_CONFIG_ENTRIES))
    source_has_data = bool(pv_entities or forecasts)
    pv_sources = (
        [
            {
                "id": "legacy-pv",
                "name": "PV",
                "mode": "aggregate",
                "power_entities": pv_entities,
                "forecast_entry_ids": forecasts,
                "installed_power_wp": _nonnegative(
                    options.get(CONF_INSTALLED_PV_WP, data.get(CONF_INSTALLED_PV_WP))
                ),
            }
        ]
        if source_has_data
        else []
    )

    has_energy_settings = any(
        (
            grid_mode != SCOPE_GRID_NONE,
            bool(data.get(CONF_PRICE_NOW_ENTITY)),
            bool(
                data.get(CONF_PRICE_EXPORT_ENTITY)
                or data.get(CONF_DYNAMIC_FEED_IN_PRICE_ENTITY)
            ),
            source_has_data,
        )
    )
    if not has_energy_settings:
        return current

    scopes["legacy-default"] = {
        "name": group_name,
        "group_ids": [group_id],
        "grid_mode": grid_mode,
        "grid_power_entities": grid_power,
        "grid_phase_power_entities": [],
        "grid_import_entities": grid_import,
        "grid_export_entities": grid_export,
        "pv_sources": pv_sources,
        "price_entity": data.get(CONF_PRICE_NOW_ENTITY),
        "export_price_entity": data.get(CONF_PRICE_EXPORT_ENTITY)
        or data.get(CONF_DYNAMIC_FEED_IN_PRICE_ENTITY),
    }
    try:
        return normalize_energy_scope_config({"version": 1, "scopes": scopes})
    except (TypeError, ValueError):
        # Preserve the prior configuration rather than creating an invalid scope.
        return current


def _entity_list(value: Any) -> list[str]:
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if isinstance(value, (list, tuple)):
        return list(
            dict.fromkeys(
                item.strip()
                for item in value
                if isinstance(item, str) and item.strip()
            )
        )
    return []


def _nonnegative(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) and number >= 0 else None
