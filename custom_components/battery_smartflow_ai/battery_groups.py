"""Persistent configuration contract for V6 battery groups.

Groups describe ownership.  Productive group control requires a separate
explicit opt-in and a valid energy scope and electrical topology.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

GROUPS_SCHEMA_VERSION = 1
BALANCING_POLICY_ENERGY_WEIGHTED = "energy_weighted"
BALANCING_POLICY_SOC_DELTA = "soc_delta"
BALANCING_POLICIES = frozenset(
    {BALANCING_POLICY_ENERGY_WEIGHTED, BALANCING_POLICY_SOC_DELTA}
)
DEFAULT_BALANCING_POLICY = BALANCING_POLICY_ENERGY_WEIGHTED
GROUP_OBJECTIVE_NEAR_ZERO = "near_zero"
GROUP_OBJECTIVE_PEAK_SHAVING = "peak_shaving"
GROUP_OBJECTIVE_PV_STORAGE = "pv_storage"
GROUP_OBJECTIVE_UPS_PRICE_ARBITRAGE = "ups_price_arbitrage"
GROUP_OBJECTIVES = frozenset(
    {
        GROUP_OBJECTIVE_NEAR_ZERO,
        GROUP_OBJECTIVE_PEAK_SHAVING,
        GROUP_OBJECTIVE_PV_STORAGE,
        GROUP_OBJECTIVE_UPS_PRICE_ARBITRAGE,
    }
)
DEFAULT_GROUP_OBJECTIVE = GROUP_OBJECTIVE_NEAR_ZERO
DEFAULT_PEAK_IMPORT_LIMIT_W = 3000
DEFAULT_UPS_CHARGE_TARGET_SOC_PCT = 80
DEFAULT_UPS_RESERVE_SOC_PCT = 20
DEFAULT_SOC_DELTA_PCT = 10
MIN_SOC_DELTA_PCT = 1
MAX_SOC_DELTA_PCT = 50


def empty_group_config() -> dict[str, Any]:
    """Return an empty, versioned group configuration."""

    return {"version": GROUPS_SCHEMA_VERSION, "groups": {}}


def _normalize_balancing_policy(value: Any) -> str:
    return (
        value
        if isinstance(value, str) and value in BALANCING_POLICIES
        else DEFAULT_BALANCING_POLICY
    )


def _normalize_soc_delta_pct(value: Any) -> int:
    if isinstance(value, bool):
        return DEFAULT_SOC_DELTA_PCT
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return DEFAULT_SOC_DELTA_PCT
    if not math.isfinite(numeric):
        return DEFAULT_SOC_DELTA_PCT
    return max(MIN_SOC_DELTA_PCT, min(MAX_SOC_DELTA_PCT, round(numeric)))


def _normalize_bounded_number(value: Any, default: int, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(numeric):
        return default
    return max(minimum, min(maximum, round(numeric)))


def _normalize_group_objective(value: Any) -> str:
    return (
        value
        if isinstance(value, str) and value in GROUP_OBJECTIVES
        else DEFAULT_GROUP_OBJECTIVE
    )


def resolve_group_objective_target(
    objective: Any,
    strategy_target_w: float,
    *,
    grid_import_w: float | None,
    grid_export_w: float | None,
    peak_import_limit_w: float = DEFAULT_PEAK_IMPORT_LIMIT_W,
) -> float | None:
    """Resolve the group's signed target before per-device allocation.

    Positive values charge and negative values discharge. ``None`` signals
    that the required grid measurement is missing or invalid, so the caller
    must pause the group rather than assume a zero reading.
    """

    target = float(strategy_target_w)
    if not math.isfinite(target):
        return None
    if objective == GROUP_OBJECTIVE_PEAK_SHAVING:
        if grid_import_w is None or not math.isfinite(float(grid_import_w)):
            return None
        limit = _normalize_bounded_number(
            peak_import_limit_w, DEFAULT_PEAK_IMPORT_LIMIT_W, 0, 100000
        )
        measured_import = float(grid_import_w)
        if measured_import > limit:
            return -(measured_import - limit)
        return 0.0 if target < 0 else target
    if objective == GROUP_OBJECTIVE_PV_STORAGE:
        if (
            grid_import_w is None
            or grid_export_w is None
            or not math.isfinite(float(grid_import_w))
            or not math.isfinite(float(grid_export_w))
        ):
            return None
        exported = float(grid_export_w)
        if exported > 0 and target > 0:
            return min(target, exported)
        return 0.0 if target < 0 else target
    return target


def resolve_ups_price_target(
    current_price: float,
    cheap_price: float,
    expensive_price: float,
    *,
    max_charge_w: float,
    offgrid_loads_w: Sequence[float] | None,
) -> float | None:
    """Resolve the AC-charging / off-grid-load UPS price-arbitrage target."""

    values = (current_price, cheap_price, expensive_price, max_charge_w)
    if any(not math.isfinite(float(value)) for value in values):
        return None
    if cheap_price >= expensive_price or max_charge_w < 0:
        return None
    if current_price <= cheap_price:
        return max(0.0, float(max_charge_w))
    if current_price < expensive_price:
        return 0.0
    if offgrid_loads_w is None:
        return None
    loads: list[float] = []
    for value in offgrid_loads_w:
        if not math.isfinite(float(value)):
            return None
        loads.append(max(0.0, float(value)))
    return -sum(loads)


def migrate_single_device_group(
    value: Any,
    *,
    setup_map: Any,
    selected_device_id: Any,
) -> dict[str, Any]:
    """Map the pre-groups selected system to one group, once, without discovery.

    This migration is intentionally limited to the already selected and fully
    configured legacy system. Other discovered devices remain ungrouped.
    """

    result = reconcile_group_config(value)
    if (
        result["groups"]
        or (isinstance(value, Mapping) and value.get("version") is not None)
        or not isinstance(selected_device_id, str)
    ):
        return result
    records = setup_map.get("devices") if isinstance(setup_map, Mapping) else None
    record = records.get(selected_device_id) if isinstance(records, Mapping) else None
    if not isinstance(record, Mapping) or record.get("setup_status") != "configured":
        return result
    name = str(record.get("display_name") or record.get("model") or "System").strip()
    result["groups"]["default"] = {"name": name, "members": [selected_device_id]}
    return result


def reconcile_group_config(value: Any = None) -> dict[str, Any]:
    """Normalize stored groups while retaining offline and not-yet-seen IDs.

    Device discovery is allowed to be incomplete.  Membership is therefore
    never pruned merely because a device is missing from the latest scan.
    Invalid group records are ignored, but duplicate ownership is rejected so
    ambiguous configuration cannot silently become active later.
    """

    if isinstance(value, Mapping):
        stored_version = value.get("version")
        if stored_version is not None and stored_version != GROUPS_SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported battery group schema version: {stored_version}"
            )
    raw_groups = value.get("groups") if isinstance(value, Mapping) else None
    if not isinstance(raw_groups, Mapping):
        return empty_group_config()

    groups: dict[str, dict[str, Any]] = {}
    claimed_devices: set[str] = set()
    for raw_group_id, raw_group in raw_groups.items():
        if not isinstance(raw_group_id, str) or not raw_group_id.strip():
            continue
        if not isinstance(raw_group, Mapping):
            continue
        name = str(raw_group.get("name", "")).strip()
        raw_members = raw_group.get("members", ())
        if not name or not isinstance(raw_members, Sequence) or isinstance(
            raw_members, (str, bytes)
        ):
            continue
        members = sorted(
            {
                member.strip()
                for member in raw_members
                if isinstance(member, str) and member.strip()
            }
        )
        duplicates = claimed_devices.intersection(members)
        if duplicates:
            raise ValueError("A device may belong to only one battery group")
        claimed_devices.update(members)
        groups[raw_group_id.strip()] = {
            "name": name,
            "members": members,
            "control_enabled": raw_group.get("control_enabled") is True,
            "balancing_policy": _normalize_balancing_policy(
                raw_group.get("balancing_policy")
            ),
            "soc_delta_pct": _normalize_soc_delta_pct(
                raw_group.get("soc_delta_pct")
            ),
            "objective": _normalize_group_objective(raw_group.get("objective")),
            "peak_import_limit_w": _normalize_bounded_number(
                raw_group.get("peak_import_limit_w"),
                DEFAULT_PEAK_IMPORT_LIMIT_W,
                0,
                100000,
            ),
            "ups_charge_target_soc_pct": _normalize_bounded_number(
                raw_group.get("ups_charge_target_soc_pct"),
                DEFAULT_UPS_CHARGE_TARGET_SOC_PCT,
                5,
                100,
            ),
            "ups_reserve_soc_pct": _normalize_bounded_number(
                raw_group.get("ups_reserve_soc_pct"),
                DEFAULT_UPS_RESERVE_SOC_PCT,
                0,
                95,
            ),
        }

    return {"version": GROUPS_SCHEMA_VERSION, "groups": groups}


def save_group(
    config: Mapping[str, Any],
    *,
    group_id: str,
    name: str,
    members: Sequence[str],
    control_enabled: bool | None = None,
    balancing_policy: str | None = None,
    soc_delta_pct: int | float | None = None,
    objective: str | None = None,
    peak_import_limit_w: int | float | None = None,
    ups_charge_target_soc_pct: int | float | None = None,
    ups_reserve_soc_pct: int | float | None = None,
    move_members: bool = False,
) -> dict[str, Any]:
    """Add or update one group without changing any other membership."""

    normalized_id = str(group_id).strip()
    normalized_name = str(name).strip()
    if not normalized_id or not normalized_name:
        raise ValueError("Battery group ID and name are required")
    if isinstance(members, (str, bytes)):
        raise TypeError("Battery group members must be a sequence of device IDs")
    if any(not isinstance(member, str) for member in members):
        raise TypeError("Battery group members must be device IDs")
    normalized_members = sorted({member.strip() for member in members if member.strip()})

    result = reconcile_group_config(config)
    groups = result["groups"]
    for existing_id, existing in tuple(groups.items()):
        if existing_id == normalized_id:
            continue
        moved = set(existing["members"]).intersection(normalized_members)
        if moved and not move_members:
            raise ValueError("A device may belong to only one battery group")
        if moved:
            groups[existing_id] = {
                **existing,
                "members": sorted(set(existing["members"]) - moved),
            }
    existing = groups.get(normalized_id, {})
    enabled = (
        control_enabled
        if control_enabled is not None
        else existing.get("control_enabled") is True
    )
    policy = _normalize_balancing_policy(
        balancing_policy
        if balancing_policy is not None
        else existing.get("balancing_policy")
    )
    delta_pct = _normalize_soc_delta_pct(
        soc_delta_pct
        if soc_delta_pct is not None
        else existing.get("soc_delta_pct")
    )
    group_objective = _normalize_group_objective(
        objective if objective is not None else existing.get("objective")
    )
    peak_limit = _normalize_bounded_number(
        peak_import_limit_w
        if peak_import_limit_w is not None
        else existing.get("peak_import_limit_w"),
        DEFAULT_PEAK_IMPORT_LIMIT_W,
        0,
        100000,
    )
    ups_target_soc = _normalize_bounded_number(
        ups_charge_target_soc_pct
        if ups_charge_target_soc_pct is not None
        else existing.get("ups_charge_target_soc_pct"),
        DEFAULT_UPS_CHARGE_TARGET_SOC_PCT,
        5,
        100,
    )
    ups_reserve_soc = _normalize_bounded_number(
        ups_reserve_soc_pct
        if ups_reserve_soc_pct is not None
        else existing.get("ups_reserve_soc_pct"),
        DEFAULT_UPS_RESERVE_SOC_PCT,
        0,
        95,
    )
    if (
        group_objective == GROUP_OBJECTIVE_UPS_PRICE_ARBITRAGE
        and ups_reserve_soc >= ups_target_soc
    ):
        raise ValueError("UPS reserve SoC must remain below the charge target")
    groups[normalized_id] = {
        "name": normalized_name,
        "members": normalized_members,
        "control_enabled": enabled is True,
        "balancing_policy": policy,
        "soc_delta_pct": delta_pct,
        "objective": group_objective,
        "peak_import_limit_w": peak_limit,
        "ups_charge_target_soc_pct": ups_target_soc,
        "ups_reserve_soc_pct": ups_reserve_soc,
    }
    return result


def remove_group(config: Mapping[str, Any], group_id: str) -> dict[str, Any]:
    """Remove a group while leaving its devices known and ungrouped."""

    result = reconcile_group_config(config)
    result["groups"].pop(str(group_id), None)
    return result
