"""Typed V5.2 passive-training models and bounded recording lifecycle.

Training is opt-in and observational. Nothing in this module can alter live
controller parameters.
"""

from __future__ import annotations

import math
from collections import deque
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

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


ALLOWED_TRAINING_MINUTES = frozenset({10, 30, 60, 120, 1440})
# The recent observed capture rate was about 326 samples per 30 minutes.
# 20,000 samples leave headroom for a complete 24-hour run at that rate.
MAX_TRAINING_SAMPLES = 20_000
MAX_STORED_TRAINING_SESSIONS = 5
MAX_STORED_TRAINING_SAMPLES = 22_000
TRAINING_CHECKPOINT_INTERVAL = timedelta(minutes=15)


def candidate_gain_parameters(evaluation: Mapping[str, Any]) -> dict[str, float]:
    """Validate and extract only proposed bounded Kp gains from an evaluation."""

    if evaluation.get("status") != "candidate_proposed":
        raise ValueError("No regulation training candidate is available")
    parameters: dict[str, float] = {}
    for direction, prefix in (("charge", "CHARGE"), ("discharge", "DISCHARGE")):
        outcome = evaluation.get(direction)
        if not isinstance(outcome, Mapping) or outcome.get("decision") != "proposed":
            continue
        proposed = outcome.get("parameters")
        if not isinstance(proposed, Mapping):
            continue
        for key, option_key in (
            ("kp_up", f"{prefix}_KP_UP"),
            ("kp_down", f"{prefix}_KP_DOWN"),
        ):
            value = proposed.get(key)
            if value is None:
                continue
            numeric = _finite_number(value)
            if numeric is None or not 0.1 <= numeric <= 2.0:
                raise ValueError("Training candidate gain is outside safe bounds")
            parameters[option_key] = round(numeric, 4)
    if not parameters:
        raise ValueError("Training candidate contains no applicable gains")
    return parameters


def training_session_candidate_parameters(
    session: Mapping[str, Any],
) -> dict[str, float]:
    """Extract an applicable candidate, rejecting partial interrupted runs."""

    if session.get("interrupted") is True:
        raise ValueError("Interrupted training data cannot be applied")
    evaluation = session.get("shadow_evaluation")
    if not isinstance(evaluation, Mapping):
        raise TypeError("No regulation training evaluation is available")
    return candidate_gain_parameters(evaluation)


def training_candidate_scope_matches(
    stored_key: Any, current_key: Mapping[str, Any]
) -> bool:
    """Match stable device/transport identity; tolerate unknown firmware."""

    if not isinstance(stored_key, Mapping):
        return False
    for field in ("device_id", "transport", "device_model"):
        if stored_key.get(field) != current_key.get(field):
            return False
    stored_firmware = stored_key.get("firmware_context")
    current_firmware = current_key.get("firmware_context")
    return (
        stored_firmware is None
        or current_firmware is None
        or stored_firmware == current_firmware
    )


def retain_training_sessions(
    sessions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Keep recent sessions within count and aggregate sample budgets."""

    retained = sessions[-MAX_STORED_TRAINING_SESSIONS:]

    def sample_count(session: Mapping[str, Any]) -> int:
        try:
            return max(0, int(session.get("sample_count", 0)))
        except (TypeError, ValueError):
            samples = session.get("samples")
            return len(samples) if isinstance(samples, list) else 0

    while (
        len(retained) > 1
        and sum(sample_count(session) for session in retained)
        > MAX_STORED_TRAINING_SAMPLES
    ):
        retained = retained[1:]
    return retained


def recover_interrupted_training_session(
    checkpoint: Mapping[str, Any], *, interrupted_at: datetime
) -> dict[str, Any] | None:
    """Convert a persisted active snapshot to an analyzable partial session."""

    _aware(interrupted_at)
    samples = checkpoint.get("samples")
    key = checkpoint.get("key")
    if not isinstance(samples, list) or not isinstance(key, dict):
        return None
    recovered = dict(checkpoint)
    recovered["samples"] = [item for item in samples if isinstance(item, dict)]
    recovered["sample_count"] = len(recovered["samples"])
    recovered["interrupted"] = True
    recovered["interrupted_at"] = interrupted_at.isoformat()
    recovered["intended_ends_at"] = recovered.get("ends_at")
    timestamps = [
        item.get("timestamp")
        for item in recovered["samples"]
        if isinstance(item.get("timestamp"), str)
    ]
    recovered["completed_at"] = (
        timestamps[-1]
        if timestamps
        else recovered.get("checkpointed_at")
        or recovered.get("started_at")
    )
    profile = recovered.get("profile")
    if isinstance(profile, dict):
        recovered["profile"] = {**profile, "trained_at": recovered["completed_at"]}
    return recovered


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
    grid_error_w: float | None = None
    target_import_w: float | None = None
    baseline_kp_up: float | None = None
    baseline_kp_down: float | None = None
    baseline_max_step_up_w: float | None = None
    baseline_max_step_down_w: float | None = None
    baseline_deadband_w: float | None = None
    ai_mode: str | None = None
    manual_action: str | None = None
    strategy_intent: str | None = None
    strategy_force: bool | None = None
    strategy_priority: int | None = None
    mode_allowed: bool | None = None
    discharge_allowed: bool | None = None
    mode_arbiter_reason: str | None = None

    def __post_init__(self) -> None:
        _aware(self.timestamp)
        if self.direction not in {"charge", "discharge", "idle"}:
            raise ValueError("direction must be charge, discharge, or idle")
        for name, value in asdict(self).items():
            if (
                name
                in {
                    "timestamp",
                    "direction",
                    "ai_mode",
                    "manual_action",
                    "strategy_intent",
                    "strategy_force",
                    "strategy_priority",
                    "mode_allowed",
                    "discharge_allowed",
                    "mode_arbiter_reason",
                }
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

    def snapshot(self, *, now: datetime) -> TrainingSession | None:
        """Return a serializable point-in-time copy without ending the run."""

        if not self.active:
            return None
        _aware(now)
        assert self._key is not None
        assert self._started_at is not None
        if now < self._started_at:
            raise ValueError("Snapshot time must not be before training start")
        return TrainingSession(
            key=self._key,
            started_at=self._started_at,
            completed_at=min(now, self._ends_at or now),
            direction_scope=self._direction_scope,
            samples=tuple(self._samples),
            dropped_sample_count=self._dropped_sample_count,
        )

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
            grid_error_w=_finite_number(details.get("regulation_error_w")),
            target_import_w=_finite_number(
                details.get("regulation_target_import_w")
            ),
            baseline_kp_up=_finite_number(
                details.get(f"effective_{direction}_kp_up")
            ),
            baseline_kp_down=_finite_number(
                details.get(f"effective_{direction}_kp_down")
            ),
            baseline_max_step_up_w=_finite_number(
                details.get(f"effective_{direction}_max_step_up")
            ),
            baseline_max_step_down_w=_finite_number(
                details.get(f"effective_{direction}_max_step_down")
            ),
            baseline_deadband_w=_finite_number(
                details.get(f"effective_{direction}_deadband_w")
            ),
            ai_mode=(str(details["ai_mode"]) if details.get("ai_mode") else None),
            manual_action=(
                str(details["manual_action"]) if details.get("manual_action") else None
            ),
            strategy_intent=(
                str(details["regulation_strategy_intent"])
                if details.get("regulation_strategy_intent")
                else None
            ),
            strategy_force=(
                bool(details["regulation_strategy_force"])
                if "regulation_strategy_force" in details
                else None
            ),
            strategy_priority=(
                int(details["regulation_strategy_priority"])
                if _finite_number(details.get("regulation_strategy_priority"))
                is not None
                else None
            ),
            mode_allowed=(
                bool(details["regulation_mode_allowed"])
                if "regulation_mode_allowed" in details
                else None
            ),
            discharge_allowed=(
                bool(details["regulation_discharge_allowed"])
                if "regulation_discharge_allowed" in details
                else None
            ),
            mode_arbiter_reason=(
                str(details["regulation_mode_arbiter_reason"])
                if details.get("regulation_mode_arbiter_reason")
                else None
            ),
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

    kp_up: float | None = None
    kp_down: float | None = None
    max_step_up_w: float | None = None
    max_step_down_w: float | None = None
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
    schema_version: int = 2

    def __post_init__(self) -> None:
        if self.trained_at.tzinfo is None or self.trained_at.utcoffset() is None:
            raise ValueError("trained_at must be timezone-aware")
        if self.schema_version != 2:
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
