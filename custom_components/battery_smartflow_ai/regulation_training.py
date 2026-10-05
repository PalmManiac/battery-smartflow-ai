"""Typed V5.2 passive-training profile model.

This module only describes per-device/per-transport training results. It does
not persist, activate, or apply candidate parameters to the live controller.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum
import math
from typing import Any

from .core.models import ZendureTransport


class RegulationProfileState(StrEnum):
    """Lifecycle state; V5.2 candidates remain non-active until approved."""

    SHADOW = "shadow"
    PROPOSED = "proposed"
    ACTIVE = "active"


@dataclass(frozen=True, slots=True)
class RegulationProfileKey:
    """Identity boundary for learned dynamics, never shared across transports."""

    device_id: str
    transport: ZendureTransport
    device_model: str
    firmware_context: str | None = None

    def __post_init__(self) -> None:
        if not self.device_id.strip():
            raise ValueError("device_id must not be empty")
        if not self.device_model.strip():
            raise ValueError("device_model must not be empty")
        if not isinstance(self.transport, ZendureTransport):
            raise TypeError("transport must be a ZendureTransport")

    def as_dict(self) -> dict[str, str | None]:
        return {
            "device_id": self.device_id,
            "transport": self.transport.value,
            "device_model": self.device_model,
            "firmware_context": self.firmware_context,
        }


@dataclass(frozen=True, slots=True)
class RegulationDirectionMetrics:
    """Observed response metrics kept separate for charge and discharge."""

    sample_count: int = 0
    command_to_readback_p50_seconds: float | None = None
    command_to_readback_p95_seconds: float | None = None
    command_to_effect_p50_seconds: float | None = None
    command_to_effect_p95_seconds: float | None = None
    effective_ramp_w_per_second: float | None = None
    minimum_effective_step_w: float | None = None
    overshoot_rate: float | None = None
    settling_time_p50_seconds: float | None = None
    confidence: float = 0.0

    def __post_init__(self) -> None:
        if self.sample_count < 0:
            raise ValueError("sample_count must not be negative")
        for name, value in asdict(self).items():
            if name == "sample_count" or value is None:
                continue
            numeric = float(value)
            if not math.isfinite(numeric) or numeric < 0.0:
                raise ValueError(f"{name} must be a finite non-negative number")
        if self.overshoot_rate is not None and self.overshoot_rate > 1.0:
            raise ValueError("overshoot_rate must be between 0 and 1")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class RegulationDirectionParameters:
    """Optional optimizer proposal; missing values retain standard control."""

    fast_gain: float | None = None
    slow_gain: float | None = None
    max_step_fast_w: float | None = None
    max_step_slow_w: float | None = None
    soft_landing_threshold_w: float | None = None
    min_command_interval_seconds: float | None = None

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            if value is None:
                continue
            numeric = float(value)
            if not math.isfinite(numeric) or numeric < 0.0:
                raise ValueError(f"{name} must be a finite non-negative number")


@dataclass(frozen=True, slots=True)
class RegulationProfile:
    """Shadow/proposed profile with explicit safety and context boundaries."""

    key: RegulationProfileKey
    trained_at: datetime
    charge_metrics: RegulationDirectionMetrics = RegulationDirectionMetrics()
    discharge_metrics: RegulationDirectionMetrics = RegulationDirectionMetrics()
    charge_parameters: RegulationDirectionParameters = (
        RegulationDirectionParameters()
    )
    discharge_parameters: RegulationDirectionParameters = (
        RegulationDirectionParameters()
    )
    state: RegulationProfileState = RegulationProfileState.SHADOW
    schema_version: int = 1

    def __post_init__(self) -> None:
        if self.trained_at.tzinfo is None or self.trained_at.utcoffset() is None:
            raise ValueError("trained_at must be timezone-aware")
        if self.schema_version != 1:
            raise ValueError("unsupported regulation profile schema version")

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation for future persistence."""

        return {
            "schema_version": self.schema_version,
            "key": self.key.as_dict(),
            "trained_at": self.trained_at.isoformat(),
            "state": self.state.value,
            "charge": {
                "metrics": asdict(self.charge_metrics),
                "parameters": asdict(self.charge_parameters),
            },
            "discharge": {
                "metrics": asdict(self.discharge_metrics),
                "parameters": asdict(self.discharge_parameters),
            },
        }
