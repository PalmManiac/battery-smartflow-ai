"""Read-only staged allocation proposals for grouped batteries (V6 Dev5)."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

NOMINAL_PHASE_VOLTAGE = 230.0
PREFERRED_LIMIT_FRACTION = 0.75


@dataclass(frozen=True, slots=True)
class ShadowDevice:
    """One device snapshot supplied to the pure allocation planner."""

    device_id: str
    name: str
    available: bool
    configured: bool
    supported: bool
    hems_blocked: bool
    protected: bool
    soc_pct: float | None
    reserve_soc_pct: float
    maximum_soc_pct: float
    capacity_kwh: float | None
    max_charge_w: float
    max_discharge_w: float
    circuit_ids: tuple[str, ...] = ()
    block_reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ShadowAllocation:
    """Serializable explanation of a proposed, non-command allocation."""

    status: str
    direction: str
    requested_power_w: float
    proposed_power_w: float
    unallocated_power_w: float
    lead_device_id: str | None
    devices: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "direction": self.direction,
            "requested_power_w": self.requested_power_w,
            "proposed_power_w": self.proposed_power_w,
            "unallocated_power_w": self.unallocated_power_w,
            "lead_device_id": self.lead_device_id,
            "devices": [dict(item) for item in self.devices],
            "writes_enabled": False,
        }


def allocate_staged_efficiency(
    target_power_w: float,
    devices: Sequence[ShadowDevice],
    topology: Mapping[str, Any] | None = None,
) -> ShadowAllocation:
    """Allocate one signed group target in stages without issuing commands.

    Positive power means charge, negative power means discharge. The first
    pass fills each device only to a preferred 75% of its effective limit; a
    second pass uses remaining device capacity if the group target needs it.
    Circuit and upstream circuit limits are enforced in both passes.
    """

    target = _finite_nonnegative(abs(float(target_power_w)))
    direction = (
        "charge"
        if target_power_w > 0
        else "discharge"
        if target_power_w < 0
        else "idle"
    )
    normalized_topology = topology if isinstance(topology, Mapping) else {}
    circuits = normalized_topology.get("circuits", {})
    if not isinstance(circuits, Mapping):
        circuits = {}

    candidates: list[tuple[ShadowDevice, float, float, list[str]]] = []
    rejected: list[dict[str, Any]] = []
    for device in devices:
        reasons = list(device.block_reasons)
        if not device.configured:
            reasons.append("setup_incomplete")
        if not device.supported:
            reasons.append("device_unsupported")
        if not device.available:
            reasons.append("device_offline")
        if device.hems_blocked:
            reasons.append("hems_blocks_control")
        if device.protected:
            reasons.append("device_protection_active")

        soc = _optional_finite(device.soc_pct)
        if direction == "discharge":
            if soc is None:
                reasons.append("soc_unavailable")
            elif soc <= device.reserve_soc_pct:
                reasons.append("soc_reserve")
        if reasons:
            rejected.append(
                {
                    "device_id": device.device_id,
                    "name": device.name,
                    "proposed_power_w": 0.0,
                    "effective_limit_w": 0.0,
                    "reasons": sorted(set(reasons)),
                }
            )
            continue

        maximum = _finite_nonnegative(
            device.max_charge_w if direction == "charge" else device.max_discharge_w
        )
        if direction == "charge" and soc is not None and soc >= device.maximum_soc_pct:
            maximum = 0.0
            reasons.append("soc_maximum")
        if maximum <= 0:
            rejected.append(
                {
                    "device_id": device.device_id,
                    "name": device.name,
                    "proposed_power_w": 0.0,
                    "effective_limit_w": 0.0,
                    "reasons": reasons or ["no_effective_power_limit"],
                }
            )
            continue
        candidates.append(
            (device, maximum, maximum * PREFERRED_LIMIT_FRACTION, reasons)
        )

    if direction == "discharge":
        candidates.sort(key=lambda item: _discharge_priority(item[0]))
    elif direction == "charge":
        candidates.sort(key=lambda item: _charge_priority(item[0]))
    else:
        candidates = []

    allocations = {item.device_id: 0.0 for item, *_ in candidates}
    explanations = {item.device_id: [] for item, *_ in candidates}
    lead_device_id = candidates[0][0].device_id if candidates else None
    if lead_device_id:
        explanations[lead_device_id].append("lead_selected")

    remaining = target
    for limit_index in (2, 1):
        for device, maximum, preferred, _ in candidates:
            if remaining <= 0.5:
                break
            stage_limit = preferred if limit_index == 2 else maximum
            device_remaining = max(0.0, stage_limit - allocations[device.device_id])
            circuit_remaining = _circuit_remaining(
                device,
                circuits,
                candidates,
                allocations,
            )
            allowed = min(device_remaining, circuit_remaining)
            amount = min(remaining, allowed)
            if amount > 0.5:
                allocations[device.device_id] += amount
                remaining -= amount
                explanations[device.device_id].append(
                    "preferred_allocation"
                    if limit_index == 2
                    else "second_stage_capacity"
                )
                if (
                    circuit_remaining < device_remaining
                    and amount >= circuit_remaining - 0.5
                ):
                    explanations[device.device_id].append("circuit_limit")
            elif circuit_remaining <= 0.5 and device_remaining > 0.5:
                explanations[device.device_id].append("circuit_limit")

    planned = []
    for device, maximum, preferred, _ in candidates:
        amount = allocations[device.device_id]
        reasons = list(explanations[device.device_id])
        if amount <= 0.5:
            reasons.append(
                "target_already_covered" if target > 0 else "no_group_target"
            )
        elif amount >= preferred - 0.5 and maximum > preferred + 0.5:
            reasons.append("preferred_limit_reached")
        planned.append(
            {
                "device_id": device.device_id,
                "name": device.name,
                "proposed_power_w": round(amount, 1),
                "effective_limit_w": round(maximum, 1),
                "preferred_limit_w": round(preferred, 1),
                "soc_pct": _round_or_none(device.soc_pct),
                "capacity_kwh": _round_or_none(device.capacity_kwh),
                "reasons": list(dict.fromkeys(reasons)),
            }
        )
    proposed = sum(allocations.values())
    status = (
        "idle"
        if target <= 0.5
        else "unavailable"
        if not candidates
        else "complete"
        if remaining <= 0.5
        else "partial"
    )
    return ShadowAllocation(
        status=status,
        direction=direction,
        requested_power_w=round(target, 1),
        proposed_power_w=round(proposed, 1),
        unallocated_power_w=round(max(0.0, remaining), 1),
        lead_device_id=lead_device_id,
        devices=tuple(rejected + planned),
    )


def _discharge_priority(device: ShadowDevice) -> tuple[float, float, str]:
    soc = _optional_finite(device.soc_pct) or 0.0
    capacity = _optional_finite(device.capacity_kwh) or 0.0
    return (-(capacity * soc), -soc, device.device_id)


def _charge_priority(device: ShadowDevice) -> tuple[float, float, str]:
    soc = _optional_finite(device.soc_pct)
    capacity = _optional_finite(device.capacity_kwh) or 0.0
    if soc is None:
        return (0.0, -capacity, device.device_id)
    return (-(capacity * max(0.0, 100.0 - soc)), soc, device.device_id)


def _circuit_remaining(device, circuits, candidates, allocations) -> float:
    """Return the smallest remaining applicable direct/upstream circuit cap."""

    if not device.circuit_ids:
        return math.inf
    limits = []
    for circuit_id in device.circuit_ids:
        ancestor_id = circuit_id
        seen = set()
        while ancestor_id and ancestor_id not in seen:
            seen.add(ancestor_id)
            circuit = circuits.get(ancestor_id)
            if not isinstance(circuit, Mapping):
                break
            cap = _circuit_limit(circuit)
            if cap is not None:
                used = sum(
                    allocations.get(other.device_id, 0.0)
                    for other, *_ in candidates
                    if ancestor_id in _circuit_ancestry(other.circuit_ids, circuits)
                )
                limits.append(max(0.0, cap - used))
            ancestor_id = circuit.get("parent_circuit_id")
    return min(limits) if limits else math.inf


def _circuit_ancestry(circuit_ids, circuits):
    ancestors = set()
    for circuit_id in circuit_ids:
        current = circuit_id
        while current and current not in ancestors:
            ancestors.add(current)
            circuit = circuits.get(current)
            current = (
                circuit.get("parent_circuit_id")
                if isinstance(circuit, Mapping)
                else None
            )
    return ancestors


def _circuit_limit(circuit):
    limits = []
    power = _optional_finite(circuit.get("max_power_w"))
    if power is not None and power > 0:
        limits.append(power)
    current = _optional_finite(circuit.get("max_current_a"))
    if current is not None and current > 0:
        limits.append(current * NOMINAL_PHASE_VOLTAGE)
    return min(limits) if limits else None


def _finite_nonnegative(value):
    number = _optional_finite(value)
    return max(0.0, number) if number is not None else 0.0


def _optional_finite(value):
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _round_or_none(value):
    number = _optional_finite(value)
    return round(number, 2) if number is not None else None
