"""Typed V5.2 passive-training models and bounded recording lifecycle.

Training is opt-in and observational. Nothing in this module can alter live
controller parameters.
"""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import StrEnum
import math
from typing import Any, Mapping

from .core.models import ZendureTransport


class RegulationProfileState(StrEnum):
    """Lifecycle state; V5.2 candidates remain non-active until approved."""

    SHADOW = "shadow"
    PROPOSED = "proposed"
    ACTIVE = "active"


class TrainingDirection(StrEnum):
    """Requested passive-training direction scope."""

    BOTH = "both"
    CHARGE = "charge"
    DISCHARGE = "discharge"


ALLOWED_TRAINING_MINUTES = frozenset({10, 30, 60, 120})
MAX_TRAINING_SAMPLES = 7200


def _aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Training timestamps must be timezone-aware")


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


@dataclass(frozen=True, slots=True)
class TrainingSample:
    """Allowlisted regulation observation; contains no entity IDs or secrets."""

    timestamp: datetime
    direction: str
    grid_import_w: float | None
    grid_export_w: float | None
    soc_pct: float | None
    pv_w: float | None
    requested_charge_w: float | None
    requested_discharge_w: float | None
    observed_charge_w: float | None
    observed_discharge_w: float | None
    grid_valid: bool
    pv_valid: bool
    command_skipped: bool

    def __post_init__(self) -> None:
        _aware(self.timestamp)
        if self.direction not in {"charge", "discharge", "idle"}:
            raise ValueError("direction must be charge, discharge, or idle")
        for name, value in asdict(self).items():
            if (
                name in {"timestamp", "direction"}
                or isinstance(value, bool)
                or value is None
            ):
                continue
            if not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite")

    def as_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["timestamp"] = self.timestamp.isoformat()
        return result


@dataclass(frozen=True, slots=True)
class TrainingSession:
    """Completed, bounded training capture scoped to one device and transport."""

    key: RegulationProfileKey
    started_at: datetime
    completed_at: datetime
    direction_scope: TrainingDirection
    samples: tuple[TrainingSample, ...]
    dropped_sample_count: int = 0

    def profile(self) -> RegulationProfile:
        """Create a conservative shadow profile from observed coverage only."""

        def direction_metrics(direction: str) -> RegulationDirectionMetrics:
            samples = [item for item in self.samples if item.direction == direction]
            if not samples:
                return RegulationDirectionMetrics()
            valid_count = sum(item.grid_valid for item in samples)
            # Coverage confidence is deliberately capped until dev04 can score
            # event diversity, latency spread, and measured physical response.
            confidence = min(0.5, len(samples) / 60.0) * (
                valid_count / len(samples)
            )
            return RegulationDirectionMetrics(
                sample_count=len(samples), confidence=round(confidence, 3)
            )

        return RegulationProfile(
            key=self.key,
            trained_at=self.completed_at,
            charge_metrics=direction_metrics("charge"),
            discharge_metrics=direction_metrics("discharge"),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key.as_dict(),
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "direction_scope": self.direction_scope.value,
            "sample_count": len(self.samples),
            "dropped_sample_count": self.dropped_sample_count,
            "profile": self.profile().as_dict(),
            "samples": [sample.as_dict() for sample in self.samples],
        }


class PassiveTrainingRecorder:
    """Manual, bounded recorder that observes normal coordinator cycles only."""

    def __init__(self, *, max_samples: int = MAX_TRAINING_SAMPLES) -> None:
        if max_samples < 1:
            raise ValueError("max_samples must be at least 1")
        self._max_samples = max_samples
        self._samples: deque[TrainingSample] = deque(maxlen=max_samples)
        self._key: RegulationProfileKey | None = None
        self._started_at: datetime | None = None
        self._ends_at: datetime | None = None
        self._direction_scope = TrainingDirection.BOTH
        self._dropped_sample_count = 0

    @property
    def active(self) -> bool:
        return self._started_at is not None

    @property
    def status(self) -> dict[str, Any]:
        return {
            "active": self.active,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "ends_at": self._ends_at.isoformat() if self._ends_at else None,
            "direction_scope": self._direction_scope.value,
            "sample_count": len(self._samples),
            "dropped_sample_count": self._dropped_sample_count,
        }

    def start(
        self,
        *,
        key: RegulationProfileKey,
        now: datetime,
        duration_minutes: int,
        direction_scope: TrainingDirection,
    ) -> None:
        _aware(now)
        if self.active:
            raise RuntimeError("A regulation training session is already active")
        if duration_minutes not in ALLOWED_TRAINING_MINUTES:
            raise ValueError("Unsupported training duration")
        self._key = key
        self._started_at = now
        self._ends_at = now + timedelta(minutes=duration_minutes)
        self._direction_scope = TrainingDirection(direction_scope)
        self._samples.clear()
        self._dropped_sample_count = 0

    def record(self, sample: TrainingSample) -> None:
        if not self.active:
            return
        if (
            self._direction_scope is not TrainingDirection.BOTH
            and sample.direction not in {self._direction_scope.value, "idle"}
        ):
            return
        if len(self._samples) == self._max_samples:
            self._dropped_sample_count += 1
        self._samples.append(sample)

    def stop(self, *, now: datetime) -> TrainingSession | None:
        if not self.active:
            return None
        _aware(now)
        assert self._key is not None
        assert self._started_at is not None
        if now < self._started_at:
            raise ValueError("Stop time must not be before training start")
        session = TrainingSession(
            key=self._key,
            started_at=self._started_at,
            completed_at=min(now, self._ends_at or now),
            direction_scope=self._direction_scope,
            samples=tuple(self._samples),
            dropped_sample_count=self._dropped_sample_count,
        )
        self._key = None
        self._started_at = None
        self._ends_at = None
        self._samples.clear()
        self._dropped_sample_count = 0
        return session

    def tick(self, *, now: datetime) -> TrainingSession | None:
        if not self.active:
            return None
        _aware(now)
        if self._ends_at is not None and now >= self._ends_at:
            return self.stop(now=self._ends_at)
        return None

    @staticmethod
    def sample_from_details(
        *, timestamp: datetime, details: Mapping[str, Any]
    ) -> TrainingSample:
        """Build a minimal sample from a single coordinator snapshot."""

        charge = max(0.0, _finite_number(details.get("battery_charge_w")) or 0.0)
        discharge = max(
            0.0, _finite_number(details.get("battery_discharge_w")) or 0.0
        )
        requested_charge = max(
            0.0, _finite_number(details.get("regulation_command_input_limit_w")) or 0.0
        )
        requested_discharge = max(
            0.0, _finite_number(details.get("regulation_command_output_limit_w")) or 0.0
        )
        mode = str(details.get("regulation_command_ac_mode") or "").lower()
        direction = (
            "charge"
            if mode in {"input", "charge"} and requested_charge > 0
            else "discharge"
            if mode in {"output", "discharge"} and requested_discharge > 0
            else "idle"
        )
        return TrainingSample(
            timestamp=timestamp,
            direction=direction,
            grid_import_w=_finite_number(details.get("deficit")),
            grid_export_w=_finite_number(details.get("surplus")),
            soc_pct=_finite_number(details.get("soc")),
            pv_w=_finite_number(details.get("pv_w")),
            requested_charge_w=requested_charge,
            requested_discharge_w=requested_discharge,
            observed_charge_w=charge,
            observed_discharge_w=discharge,
            grid_valid=bool(details.get("grid_sensor_valid")),
            pv_valid=bool(details.get("pv_sensor_valid")),
            command_skipped=bool(details.get("regulation_command_skipped")),
        )


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
