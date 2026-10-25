"""Persistent EnergyScope configuration and source validation for V6."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

ENERGY_SCOPES_SCHEMA_VERSION = 1

GRID_MODE_NONE = "none"
GRID_MODE_SIGNED = "signed"
GRID_MODE_SPLIT = "split"
GRID_MODES = {GRID_MODE_NONE, GRID_MODE_SIGNED, GRID_MODE_SPLIT}

PV_SOURCE_AGGREGATE = "aggregate"
PV_SOURCE_COMPONENTS = "components"
PV_SOURCE_MODES = {PV_SOURCE_AGGREGATE, PV_SOURCE_COMPONENTS}


def empty_energy_scope_config() -> dict[str, Any]:
    """Return an empty, versioned EnergyScope configuration."""

    return {"version": ENERGY_SCOPES_SCHEMA_VERSION, "scopes": {}}


def _string_list(value: Any, *, label: str) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise TypeError(f"{label} must be a list of identifiers")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            continue
        normalized = item.strip()
        if normalized not in result:
            result.append(normalized)
    return result


def normalize_energy_scope_config(value: Any = None) -> dict[str, Any]:
    """Validate and normalize saved scopes without pruning offline IDs.

    PV source records explicitly identify whether their selected sensors are
    one aggregate or separate components. Exact duplicate entities and
    duplicate forecast mappings are rejected to avoid accidental double
    accounting.
    """

    if isinstance(value, Mapping):
        stored_version = value.get("version")
        if (
            stored_version is not None
            and stored_version != ENERGY_SCOPES_SCHEMA_VERSION
        ):
            raise ValueError(
                f"Unsupported EnergyScope schema version: {stored_version}"
            )
    raw_scopes = value.get("scopes") if isinstance(value, Mapping) else None
    if not isinstance(raw_scopes, Mapping):
        return empty_energy_scope_config()

    scopes: dict[str, dict[str, Any]] = {}
    claimed_groups: set[str] = set()
    for raw_scope_id, raw_scope in raw_scopes.items():
        if not isinstance(raw_scope_id, str) or not raw_scope_id.strip():
            continue
        if not isinstance(raw_scope, Mapping):
            continue
        scope_id = raw_scope_id.strip()
        name = str(raw_scope.get("name") or "").strip()
        if not name:
            raise ValueError("EnergyScope name is required")

        group_ids = _string_list(raw_scope.get("group_ids", ()), label="group_ids")
        duplicates = claimed_groups.intersection(group_ids)
        if duplicates:
            raise ValueError("A battery group may use only one EnergyScope")
        claimed_groups.update(group_ids)

        grid_mode = str(raw_scope.get("grid_mode", GRID_MODE_NONE)).strip().lower()
        if grid_mode not in GRID_MODES:
            raise ValueError(f"Unsupported EnergyScope grid mode: {grid_mode}")
        grid_power_entities = _string_list(
            raw_scope.get("grid_power_entities", ()), label="grid_power_entities"
        )
        grid_phase_power_entities = _string_list(
            raw_scope.get("grid_phase_power_entities", ()),
            label="grid_phase_power_entities",
        )
        grid_import_entities = _string_list(
            raw_scope.get("grid_import_entities", ()), label="grid_import_entities"
        )
        grid_export_entities = _string_list(
            raw_scope.get("grid_export_entities", ()), label="grid_export_entities"
        )
        if grid_mode == GRID_MODE_SIGNED:
            if (
                (not grid_power_entities and not grid_phase_power_entities)
                or grid_import_entities
                or grid_export_entities
            ):
                raise ValueError(
                    "Signed grid mode requires signed grid or per-phase sensors"
                )
        elif grid_mode == GRID_MODE_SPLIT:
            if (
                not grid_import_entities
                or not grid_export_entities
                or grid_power_entities
                or grid_phase_power_entities
            ):
                raise ValueError("Split grid mode requires import and export sensors")
        elif (
            grid_power_entities
            or grid_phase_power_entities
            or grid_import_entities
            or grid_export_entities
        ):
            raise ValueError("Grid sensors are not allowed when grid mode is none")

        all_grid_entities = (
            grid_power_entities
            + grid_phase_power_entities
            + grid_import_entities
            + grid_export_entities
        )
        if len(set(all_grid_entities)) != len(all_grid_entities):
            raise ValueError("A grid sensor may be assigned only once per EnergyScope")

        raw_pv_sources = raw_scope.get("pv_sources", ())
        if not isinstance(raw_pv_sources, Sequence) or isinstance(
            raw_pv_sources, (str, bytes)
        ):
            raise TypeError("pv_sources must be a list")
        pv_sources: list[dict[str, Any]] = []
        pv_ids: set[str] = set()
        pv_names: set[str] = set()
        pv_entities: set[str] = set()
        forecast_ids: set[str] = set()
        for raw_source in raw_pv_sources:
            if not isinstance(raw_source, Mapping):
                continue
            source_id = str(raw_source.get("id") or "").strip()
            source_name = str(raw_source.get("name") or "").strip()
            mode = str(raw_source.get("mode") or PV_SOURCE_AGGREGATE).strip().lower()
            normalized_source_name = source_name.casefold()
            if (
                not source_id
                or source_id in pv_ids
                or not source_name
                or normalized_source_name in pv_names
            ):
                raise ValueError("Each PV source needs a unique ID and a name")
            if mode not in PV_SOURCE_MODES:
                raise ValueError(f"Unsupported PV source mode: {mode}")
            power_entities = _string_list(
                raw_source.get("power_entities", ()), label="power_entities"
            )
            if mode == PV_SOURCE_AGGREGATE and len(power_entities) > 1:
                raise ValueError(
                    "An aggregate PV source may have only one power sensor"
                )
            if pv_entities.intersection(power_entities):
                raise ValueError(
                    "A PV power sensor may be counted only once per EnergyScope"
                )
            pv_entities.update(power_entities)
            source_forecasts = _string_list(
                raw_source.get("forecast_entry_ids", ()), label="forecast_entry_ids"
            )
            if forecast_ids.intersection(source_forecasts):
                raise ValueError(
                    "A forecast source may map to only one PV source per EnergyScope"
                )
            forecast_ids.update(source_forecasts)
            pv_ids.add(source_id)
            pv_names.add(normalized_source_name)
            pv_sources.append(
                {
                    "id": source_id,
                    "name": source_name,
                    "mode": mode,
                    "power_entities": power_entities,
                    "forecast_entry_ids": source_forecasts,
                    "installed_power_wp": _optional_nonnegative_number(
                        raw_source.get("installed_power_wp"),
                        label="installed_power_wp",
                    ),
                }
            )
        if set(all_grid_entities).intersection(pv_entities):
            raise ValueError("A sensor may not be assigned as both grid and PV power")

        scopes[scope_id] = {
            "name": name,
            "group_ids": group_ids,
            "grid_mode": grid_mode,
            "grid_power_entities": grid_power_entities,
            "grid_phase_power_entities": grid_phase_power_entities,
            "grid_import_entities": grid_import_entities,
            "grid_export_entities": grid_export_entities,
            "pv_sources": pv_sources,
            "price_entity": str(raw_scope.get("price_entity") or "").strip() or None,
            "export_price_entity": str(
                raw_scope.get("export_price_entity") or ""
            ).strip()
            or None,
        }

    return {"version": ENERGY_SCOPES_SCHEMA_VERSION, "scopes": scopes}


def _optional_nonnegative_number(value: Any, *, label: str) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        raise TypeError(f"{label} must be a nonnegative number")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise TypeError(f"{label} must be a nonnegative number") from error
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{label} must be a nonnegative number")
    return number


def save_energy_scope(
    config: Mapping[str, Any], *, scope_id: str, scope: Mapping[str, Any]
) -> dict[str, Any]:
    """Add or replace one scope and revalidate unique group ownership."""

    normalized_id = str(scope_id).strip()
    if not normalized_id:
        raise ValueError("EnergyScope ID is required")
    current = normalize_energy_scope_config(config)
    scopes = dict(current["scopes"])
    scopes[normalized_id] = dict(scope)
    return normalize_energy_scope_config(
        {"version": ENERGY_SCOPES_SCHEMA_VERSION, "scopes": scopes}
    )


def remove_energy_scope(config: Mapping[str, Any], scope_id: str) -> dict[str, Any]:
    """Remove one scope without changing any battery groups."""

    current = normalize_energy_scope_config(config)
    current["scopes"].pop(str(scope_id), None)
    return current
