"""Derived native hardware statistics with explicit data-quality semantics."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class NativeStatistics:
    available_energy_kwh: float | None
    roundtrip_efficiency_pct: float | None
    switch_count: int | None
    switch_count_is_estimate: bool

def roundtrip_efficiency_pct(charged_kwh: Any, discharged_kwh: Any) -> float | None:
    try:
        charged, discharged = float(charged_kwh), float(discharged_kwh)
    except (TypeError, ValueError):
        return None
    if charged <= 0 or discharged < 0:
        return None
    return round(min(100.0, discharged / charged * 100.0), 1)

def derived_statistics(*, soc_pct: Any, capacity_kwh: Any,
                       charged_kwh: Any = None, discharged_kwh: Any = None,
                       switch_count: Any = None) -> NativeStatistics:
    try:
        soc, capacity = float(soc_pct), float(capacity_kwh)
        available = round(capacity * soc / 100.0, 3) if 0 <= soc <= 100 and capacity > 0 else None
    except (TypeError, ValueError):
        available = None
    try:
        count = int(switch_count) if switch_count is not None and int(switch_count) >= 0 else None
    except (TypeError, ValueError):
        count = None
    return NativeStatistics(available, roundtrip_efficiency_pct(charged_kwh, discharged_kwh),
                            count, count is not None)
