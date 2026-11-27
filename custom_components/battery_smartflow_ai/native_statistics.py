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
    pv_energy_kwh: float = 0.0
    last_charge_timestamp: float | None = None
    last_discharge_timestamp: float | None = None
    last_pv_timestamp: float | None = None

    @classmethod
    def from_dict(cls, data: Any) -> "NativeEnergyAccumulator":
        if not isinstance(data, dict):
            return cls()
        try:
            charge = max(0.0, float(data.get("charged_kwh", 0.0)))
            discharge = max(0.0, float(data.get("discharged_kwh", 0.0)))
            pv_energy = max(0.0, float(data.get("pv_energy_kwh", 0.0)))
            # The former shared timestamp cannot establish whether either
            # measurement stayed valid. Start both channels with a fresh sample.
            charge_stamp = data.get("last_charge_timestamp")
            charge_stamp = float(charge_stamp) if charge_stamp is not None else None
            discharge_stamp = data.get("last_discharge_timestamp")
            discharge_stamp = float(discharge_stamp) if discharge_stamp is not None else None
            pv_stamp = data.get("last_pv_timestamp")
            pv_stamp = float(pv_stamp) if pv_stamp is not None else None
        except (TypeError, ValueError):
            return cls()
        return cls(
            charged_kwh=charge,
            discharged_kwh=discharge,
            pv_energy_kwh=pv_energy,
            last_charge_timestamp=charge_stamp,
            last_discharge_timestamp=discharge_stamp,
            last_pv_timestamp=pv_stamp,
        )

    def as_dict(self) -> dict[str, float | None]:
        state = {
            "charged_kwh": self.charged_kwh,
            "discharged_kwh": self.discharged_kwh,
            "last_charge_timestamp": self.last_charge_timestamp,
            "last_discharge_timestamp": self.last_discharge_timestamp,
        }
        if self.last_pv_timestamp is not None:
            state.update({
                "pv_energy_kwh": self.pv_energy_kwh,
                "last_pv_timestamp": self.last_pv_timestamp,
            })
        return state

    def add(
        self,
        *,
        timestamp: Any,
        charge_power_w: Any,
        discharge_power_w: Any,
        pv_power_w: Any = None,
        max_interval_seconds: float = 300.0,
    ) -> bool:
        """Integrate one sample; reject invalid samples and large/offline gaps."""
        try:
            now = float(timestamp)
        except (TypeError, ValueError):
            return False

        charge_valid = False
        try:
            charge = max(0.0, float(charge_power_w))
            charge_valid = True
        except (TypeError, ValueError):
            self.last_charge_timestamp = None
        if charge_valid:
            if self.last_charge_timestamp is not None:
                delta = now - self.last_charge_timestamp
                if 0 < delta <= max_interval_seconds:
                    self.charged_kwh += charge * delta / 3_600_000
            self.last_charge_timestamp = now

        discharge_valid = False
        try:
            discharge = max(0.0, float(discharge_power_w))
            discharge_valid = True
        except (TypeError, ValueError):
            self.last_discharge_timestamp = None
        if discharge_valid:
            if self.last_discharge_timestamp is not None:
                delta = now - self.last_discharge_timestamp
                if 0 < delta <= max_interval_seconds:
                    self.discharged_kwh += discharge * delta / 3_600_000
            self.last_discharge_timestamp = now

        pv_valid = True
        try:
            pv_power = max(0.0, float(pv_power_w))
        except (TypeError, ValueError):
            pv_valid = False
        if pv_valid:
            if self.last_pv_timestamp is not None:
                delta = now - self.last_pv_timestamp
                if 0 < delta <= max_interval_seconds:
                    self.pv_energy_kwh += pv_power * delta / 3_600_000
            self.last_pv_timestamp = now

        return charge_valid or discharge_valid or pv_valid


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
