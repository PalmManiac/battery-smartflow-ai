"""Offline one-step counterfactual evaluator for opt-in training sessions.

The evaluator only creates shadow proposals. Its simplified one-step replay
is intentionally conservative and never feeds the live PowerController.
It is a screening estimate, not a full chronological plant simulation or a
promise of real-world improvement.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from statistics import median
from typing import Any

from .regulation_training import RegulationProfileState

MIN_DIRECTION_SAMPLES = 60
MIN_RESPONSE_EVENTS = 3
MIN_RELATIVE_IMPROVEMENT = 0.03
MAX_REPLAY_OVERSHOOT_RATE = 0.10
_GAIN_FACTORS = (0.8, 0.9, 1.0, 1.1, 1.2)


@dataclass(frozen=True, slots=True)
class ShadowDirectionResult:
    """Measured telemetry and candidate comparison for one direction."""

    sample_count: int
    response_event_count: int
    confidence: float
    baseline_score: float | None
    candidate_score: float | None
    overshoot_rate: float | None
    relative_improvement: float | None
    selected_gain_factor: float | None
    parameters: dict[str, float | None]
    decision: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "sample_count": self.sample_count,
            "response_event_count": self.response_event_count,
            "confidence": self.confidence,
            "baseline_score": self.baseline_score,
            "candidate_score": self.candidate_score,
            "overshoot_rate": self.overshoot_rate,
            "relative_improvement": self.relative_improvement,
            "selected_gain_factor": self.selected_gain_factor,
            "parameters": dict(self.parameters),
            "decision": self.decision,
        }


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _active_samples(
    samples: list[Mapping[str, Any]], direction: str
) -> list[Mapping[str, Any]]:
    return [
        sample
        for sample in samples
        if sample.get("direction") == direction
        and sample.get("grid_valid") is True
        and sample.get("command_skipped") is False
        and _number(sample.get("grid_error_w")) is not None
    ]


def _response_events(samples: list[Mapping[str, Any]]) -> int:
    events = 0
    last_command: float | None = None
    for sample in samples:
        requested = max(
            _number(sample.get("requested_charge_w")) or 0.0,
            _number(sample.get("requested_discharge_w")) or 0.0,
        )
        if last_command is not None and abs(requested - last_command) >= 20.0:
            events += 1
        last_command = requested
    return events


def _direction_score(
    samples: list[Mapping[str, Any]], *, gain_factor: float
) -> tuple[float, float] | None:
    residuals: list[float] = []
    overshoots = 0
    for sample in samples:
        error = _number(sample.get("grid_error_w"))
        kp_up = _number(sample.get("baseline_kp_up"))
        kp_down = _number(sample.get("baseline_kp_down"))
        max_step_up = _number(sample.get("baseline_max_step_up_w"))
        max_step_down = _number(sample.get("baseline_max_step_down_w"))
        requested = max(
            _number(sample.get("requested_charge_w")) or 0.0,
            _number(sample.get("requested_discharge_w")) or 0.0,
        )
        observed = max(
            _number(sample.get("observed_charge_w")) or 0.0,
            _number(sample.get("observed_discharge_w")) or 0.0,
        )
        if (
            error is None
            or kp_up is None
            or kp_down is None
            or requested <= 0.0
        ):
            continue

        increase_target = error >= 0.0
        gain = kp_up if increase_target else kp_down
        step = max_step_up if increase_target else max_step_down
        if step is None:
            step = max(abs(error), 0.0)
        effect_ratio = min(1.0, max(0.0, observed / requested))
        correction = min(abs(error) * gain * gain_factor, step) * effect_ratio
        if correction > abs(error) + 25.0:
            overshoots += 1
        residuals.append(abs(error - math.copysign(correction, error)))

    if not residuals:
        return None
    overshoot_rate = overshoots / len(residuals)
    # Penalize predicted overshoot more than an equal-sized residual.
    return (sum(residuals) / len(residuals)) * (1.0 + 2.0 * overshoot_rate), overshoot_rate


def _evaluate_direction(
    samples: list[Mapping[str, Any]], direction: str
) -> ShadowDirectionResult:
    usable = _active_samples(samples, direction)
    events = _response_events(usable)
    valid_ratio = len(usable) / max(
        1,
        sum(1 for item in samples if item.get("direction") == direction),
    )
    confidence = min(1.0, len(usable) / 120.0) * min(1.0, events / 8.0) * valid_ratio
    parameters: dict[str, float | None] = {
        "kp_up": None,
        "kp_down": None,
        "max_step_up_w": None,
        "max_step_down_w": None,
    }
    baseline = _direction_score(usable, gain_factor=1.0)
    if (
        len(usable) < MIN_DIRECTION_SAMPLES
        or events < MIN_RESPONSE_EVENTS
        or confidence < 0.35
        or baseline is None
    ):
        return ShadowDirectionResult(
            sample_count=len(usable),
            response_event_count=events,
            confidence=round(confidence, 3),
            baseline_score=round(baseline[0], 2) if baseline else None,
            candidate_score=None,
            overshoot_rate=round(baseline[1], 3) if baseline else None,
            relative_improvement=None,
            selected_gain_factor=None,
            parameters=parameters,
            decision="insufficient_data",
        )

    candidates = [
        (factor, _direction_score(usable, gain_factor=factor))
        for factor in _GAIN_FACTORS
    ]
    candidates = [(factor, score) for factor, score in candidates if score]
    factor, candidate = min(candidates, key=lambda item: item[1][0])
    relative_improvement = (
        (baseline[0] - candidate[0]) / baseline[0]
        if baseline[0] > 0.0
        else 0.0
    )
    decision = "rejected"
    if (
        factor != 1.0
        and relative_improvement >= MIN_RELATIVE_IMPROVEMENT
        and candidate[1] <= baseline[1] + MAX_REPLAY_OVERSHOOT_RATE
    ):
        decision = "proposed"
        kp_up_values = [
            _number(item.get("baseline_kp_up"))
            for item in usable
            if (
                (_number(item.get("grid_error_w")) or 0.0) > 0.0
                and _number(item.get("baseline_kp_up")) is not None
            )
        ]
        kp_down_values = [
            _number(item.get("baseline_kp_down"))
            for item in usable
            if (
                (_number(item.get("grid_error_w")) or 0.0) < 0.0
                and _number(item.get("baseline_kp_down")) is not None
            )
        ]
        up_steps = [
            _number(item.get("baseline_max_step_up_w"))
            for item in usable
            if _number(item.get("baseline_max_step_up_w")) is not None
        ]
        down_steps = [
            _number(item.get("baseline_max_step_down_w"))
            for item in usable
            if _number(item.get("baseline_max_step_down_w")) is not None
        ]
        parameters = {
            "kp_up": round(median(kp_up_values) * factor, 4) if kp_up_values else None,
            "kp_down": round(median(kp_down_values) * factor, 4) if kp_down_values else None,
            "max_step_up_w": median(up_steps) if up_steps else None,
            "max_step_down_w": median(down_steps) if down_steps else None,
        }
    return ShadowDirectionResult(
        sample_count=len(usable),
        response_event_count=events,
        confidence=round(confidence, 3),
        baseline_score=round(baseline[0], 2),
        candidate_score=round(candidate[0], 2),
        overshoot_rate=round(candidate[1], 3),
        relative_improvement=round(relative_improvement, 4),
        selected_gain_factor=factor,
        parameters=parameters,
        decision=decision,
    )


def evaluate_training_session(session: Mapping[str, Any]) -> dict[str, Any]:
    """Replay a finished session and return non-active charge/discharge proposals."""

    raw_samples = session.get("samples")
    samples = [item for item in raw_samples if isinstance(item, Mapping)] if isinstance(raw_samples, list) else []
    charge = _evaluate_direction(samples, "charge")
    discharge = _evaluate_direction(samples, "discharge")
    proposed = charge.decision == "proposed" or discharge.decision == "proposed"
    status = (
        "candidate_proposed"
        if proposed
        else "no_improvement"
        if "rejected" in {charge.decision, discharge.decision}
        else "insufficient_data"
    )
    return {
        "status": status,
        "state": (
            RegulationProfileState.PROPOSED.value
            if proposed
            else RegulationProfileState.SHADOW.value
        ),
        "method": "bounded_one_step_proportional_counterfactual_v1",
        "score_unit": "mean_absolute_predicted_grid_error_w",
        "interpretation": (
            "Screening estimate from recorded errors, commands, readbacks, and "
            "baseline gains; it does not simulate full device or grid dynamics."
        ),
        "live_parameters_changed": False,
        "charge": charge.as_dict(),
        "discharge": discharge.as_dict(),
    }
