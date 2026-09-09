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


@dataclass
class NativeEnergyAccumulator:
    """Persistable, gap-safe integration of native power measurements."""
    charged_kwh: float = 0.0
    discharged_kwh: float = 0.0
    last_timestamp: float | None = None

    @classmethod
    def from_dict(cls, data: Any) -> "NativeEnergyAccumulator":
        if not isinstance(data, dict):
            return cls()
        try:
            charge = max(0.0, float(data.get("charged_kwh", 0.0)))
            discharge = max(0.0, float(data.get("discharged_kwh", 0.0)))
            stamp = data.get("last_timestamp")
            stamp = float(stamp) if stamp is not None else None
        except (TypeError, ValueError):
            return cls()
        return cls(charge, discharge, stamp)

    def as_dict(self) -> dict[str, float | None]:
        return {
            "charged_kwh": self.charged_kwh,
            "discharged_kwh": self.discharged_kwh,
            "last_timestamp": self.last_timestamp,
        }

    def add(
        self,
        *,
        timestamp: Any,
        charge_power_w: Any,
        discharge_power_w: Any,
        max_interval_seconds: float = 300.0,
    ) -> bool:
        """Integrate one sample; reject invalid samples and large/offline gaps."""
        try:
            now = float(timestamp)
            charge = max(0.0, float(charge_power_w))
            discharge = max(0.0, float(discharge_power_w))
        except (TypeError, ValueError):
            return False
        if self.last_timestamp is not None:
            delta = now - self.last_timestamp
            if 0 < delta <= max_interval_seconds:
                self.charged_kwh += charge * delta / 3_600_000
                self.discharged_kwh += discharge * delta / 3_600_000
        self.last_timestamp = now
        return True


def roundtrip_efficiency_pct(charged_kwh: Any, discharged_kwh: Any) -> float | None:
    try:
        charged, discharged = float(charged_kwh), float(discharged_kwh)
    except (TypeError, ValueError):
        return None
    if charged <= 0 or discharged < 0:
        return None
    return round(min(100.0, discharged / charged * 100.0), 1)


def derived_statistics(
    *,
    soc_pct: Any,
    capacity_kwh: Any,
    charged_kwh: Any = None,
    discharged_kwh: Any = None,
    switch_count: Any = None,
) -> NativeStatistics:
    try:
        soc, capacity = float(soc_pct), float(capacity_kwh)
        available = (
            round(capacity * soc / 100.0, 3)
            if 0 <= soc <= 100 and capacity > 0
            else None
        )
    except (TypeError, ValueError):
        available = None
    try:
        count = (
            int(switch_count)
            if switch_count is not None and int(switch_count) >= 0
            else None
        )
    except (TypeError, ValueError):
        count = None
    return NativeStatistics(
        available,
        roundtrip_efficiency_pct(charged_kwh, discharged_kwh),
        count,
        count is not None,
    )
