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
from datetime import datetime
from statistics import median
from typing import Any

from .regulation_training import RegulationProfileState

MIN_DIRECTION_SAMPLES = 60
MIN_RESPONSE_EVENTS = 3
MIN_RELATIVE_IMPROVEMENT = 0.03
MAX_REPLAY_OVERSHOOT_RATE = 0.10
_GAIN_FACTORS = (0.8, 0.9, 1.0, 1.1, 1.2)
REVERSAL_THRESHOLD_WATT_SECONDS = 3_000.0
MAX_REVERSAL_SAMPLE_GAP_SECONDS = 30.0
MAX_AUTOMATIC_STRATEGY_PRIORITY = 400


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


def _sample_direction(sample: Mapping[str, Any]) -> tuple[str, float] | None:
    """Return a commanded direction and magnitude, or None for idle samples."""

    charge = max(0.0, _number(sample.get("requested_charge_w")) or 0.0)
    discharge = max(0.0, _number(sample.get("requested_discharge_w")) or 0.0)
    if charge > 0.0 and discharge <= 0.0:
        return "charge", charge
    if discharge > 0.0 and charge <= 0.0:
        return "discharge", discharge
    return None


def _reversal_hysteresis_shadow(
    samples: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Estimate a 3 kWs reversal hold on ordinary automatic regulation only.

    This deliberately reports withheld command energy and hold time, not a
    claimed grid-error improvement: the passive sample stream cannot reproduce
    the counterfactual physical response of the battery or home load.
    """

    timed: list[tuple[datetime, Mapping[str, Any]]] = []
    for sample in samples:
        raw_timestamp = sample.get("timestamp")
        if not isinstance(raw_timestamp, str):
            continue
        try:
            timestamp = datetime.fromisoformat(raw_timestamp)
        except ValueError:
            continue
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            continue
        timed.append((timestamp, sample))
    timed.sort(key=lambda item: item[0])

    def eligible(sample: Mapping[str, Any]) -> bool:
        return (
            sample.get("ai_mode") == "automatic"
            and sample.get("manual_action") == "standby"
            and sample.get("strategy_intent") in {"pv_charge", "cover_deficit"}
            and sample.get("strategy_force") is False
            and _number(sample.get("strategy_priority")) is not None
            and _number(sample.get("strategy_priority"))
            <= MAX_AUTOMATIC_STRATEGY_PRIORITY
            and sample.get("mode_allowed") is True
            and sample.get("discharge_allowed") is True
            and sample.get("grid_valid") is True
            and sample.get("command_skipped") is False
        )

    eligible_samples = 0
    observed_reversals = 0
    eligible_reversals = 0
    override_reversals = 0
    held_reversals = 0
    released_reversals = 0
    held_seconds = 0.0
    held_energy_ws = 0.0
    max_hold_seconds = 0.0
    previous: tuple[datetime, str, float, Mapping[str, Any]] | None = None
    locked_direction: str | None = None
    pending_direction: str | None = None
    pending_ws = 0.0
    pending_seconds = 0.0

    for timestamp, sample in timed:
        command = _sample_direction(sample)
        if command is None:
            previous = None
            locked_direction = None
            pending_direction = None
            pending_ws = 0.0
            pending_seconds = 0.0
            continue
        direction, watts = command
        is_eligible = eligible(sample)
        if is_eligible:
            eligible_samples += 1
        if previous is None:
            if is_eligible:
                locked_direction = direction
            previous = (timestamp, direction, watts, sample)
            continue

        previous_time, previous_direction, previous_watts, previous_sample = previous
        elapsed = (timestamp - previous_time).total_seconds()
        if elapsed <= 0.0 or elapsed > MAX_REVERSAL_SAMPLE_GAP_SECONDS:
            previous = (timestamp, direction, watts, sample)
            locked_direction = direction if is_eligible else None
            pending_direction = None
            pending_ws = 0.0
            pending_seconds = 0.0
            continue

        direction_changed = direction != previous_direction
        if direction_changed:
            observed_reversals += 1
            if not (is_eligible and eligible(previous_sample)):
                override_reversals += 1
                previous = (timestamp, direction, watts, sample)
                locked_direction = direction if is_eligible else None
                pending_direction = None
                pending_ws = 0.0
                pending_seconds = 0.0
                continue
            eligible_reversals += 1

        if not is_eligible or not eligible(previous_sample):
            previous = (timestamp, direction, watts, sample)
            locked_direction = direction if is_eligible else None
            pending_direction = None
            pending_ws = 0.0
            pending_seconds = 0.0
            continue

        if locked_direction is None:
            locked_direction = direction
        if direction == locked_direction:
            # A rapid return to the original direction cancels an uncompleted
            # hold, matching the intent of a reversal dead-time.
            if pending_direction is not None:
                interval_ws = previous_watts * elapsed
                held_energy_ws += interval_ws
                held_seconds += elapsed
                max_hold_seconds = max(
                    max_hold_seconds, pending_seconds + elapsed
                )
            pending_direction = None
            pending_ws = 0.0
            pending_seconds = 0.0
        elif direction != pending_direction:
            pending_direction = direction
            pending_ws = 0.0
            pending_seconds = 0.0
            held_reversals += 1
        else:
            interval_ws = ((previous_watts + watts) / 2.0) * elapsed
            pending_ws += interval_ws
            pending_seconds += elapsed
            held_energy_ws += interval_ws
            held_seconds += elapsed
            max_hold_seconds = max(max_hold_seconds, pending_seconds)
            if pending_ws >= REVERSAL_THRESHOLD_WATT_SECONDS:
                locked_direction = pending_direction
                pending_direction = None
                pending_ws = 0.0
                pending_seconds = 0.0
                released_reversals += 1
        previous = (timestamp, direction, watts, sample)

    status = "simulated" if eligible_samples >= 2 else "insufficient_data"
    return {
        "status": status,
        "method": "automatic_reversal_watt_seconds_shadow_v1",
        "threshold_watt_seconds": REVERSAL_THRESHOLD_WATT_SECONDS,
        "sample_count": len(timed),
        "eligible_sample_count": eligible_samples,
        "observed_reversal_count": observed_reversals,
        "eligible_reversal_count": eligible_reversals,
        "override_reversal_count": override_reversals,
        "held_reversal_count": held_reversals,
        "released_reversal_count": released_reversals,
        "estimated_hold_seconds": round(held_seconds, 2),
        "estimated_withheld_energy_wh": round(held_energy_ws / 3600.0, 3),
        "maximum_hold_seconds": round(max_hold_seconds, 2),
        "live_parameters_changed": False,
        "interpretation": (
            "Shadow-only estimate for ordinary automatic PV/load regulation. "
            "Manual actions, forced or higher-priority strategies, denied mode "
            "changes, and discharge-protection states are excluded. Withheld "
            "energy and hold time are not a prediction of grid-error improvement."
        ),
    }


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
        "reversal_hysteresis": _reversal_hysteresis_shadow(samples),
        "charge": charge.as_dict(),
        "discharge": discharge.as_dict(),
    }
