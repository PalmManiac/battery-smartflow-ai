"""Offline one-step counterfactual evaluator for opt-in training sessions.

The evaluator only creates shadow proposals. Its simplified one-step replay
is intentionally conservative and never feeds the live PowerController.
It is a screening estimate, not a full chronological plant simulation or a
promise of real-world improvement.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from statistics import median
from typing import Any

from .regulation_training import RegulationProfileState

MIN_DIRECTION_SAMPLES = 60
MIN_RESPONSE_EVENTS = 3
MIN_EVALUATION_CONFIDENCE = 0.35
MIN_RELATIVE_IMPROVEMENT = 0.03
MAX_REPLAY_OVERSHOOT_RATE = 0.10
_GAIN_FACTORS = (0.8, 0.9, 1.0, 1.1, 1.2)
REVERSAL_THRESHOLD_WATT_SECONDS = 3_000.0
MAX_REVERSAL_SAMPLE_GAP_SECONDS = 30.0
MAX_AUTOMATIC_STRATEGY_PRIORITY_BY_INTENT = {
    "pv_charge": 500,
    "cover_deficit": 400,
}


@dataclass(frozen=True, slots=True)
class ShadowDirectionResult:
    """Measured telemetry and candidate comparison for one direction."""

    sample_count: int
    direction_sample_count: int
    unchanged_command_sample_count: int
    rejected_invalid_grid_count: int
    rejected_missing_error_count: int
    rejected_command_skip_count: int
    rejected_context_count: int
    rejected_profile_mismatch_count: int
    valid_sample_ratio: float
    minimum_confidence: float
    response_event_count: int
    confidence: float
    baseline_score: float | None
    candidate_score: float | None
    overshoot_rate: float | None
    relative_improvement: float | None
    selected_gain_factor: float | None
    parameters: dict[str, float | None]
    decision: str
    insufficient_reasons: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "sample_count": self.sample_count,
            "direction_sample_count": self.direction_sample_count,
            "unchanged_command_sample_count": self.unchanged_command_sample_count,
            "rejected_invalid_grid_count": self.rejected_invalid_grid_count,
            "rejected_missing_error_count": self.rejected_missing_error_count,
            "rejected_command_skip_count": self.rejected_command_skip_count,
            "rejected_context_count": self.rejected_context_count,
            "rejected_profile_mismatch_count": self.rejected_profile_mismatch_count,
            "valid_sample_ratio": self.valid_sample_ratio,
            "minimum_confidence": self.minimum_confidence,
            "response_event_count": self.response_event_count,
            "confidence": self.confidence,
            "baseline_score": self.baseline_score,
            "candidate_score": self.candidate_score,
            "overshoot_rate": self.overshoot_rate,
            "relative_improvement": self.relative_improvement,
            "selected_gain_factor": self.selected_gain_factor,
            "parameters": dict(self.parameters),
            "decision": self.decision,
            "insufficient_reasons": list(self.insufficient_reasons),
        }


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _command_is_usable_observation(sample: Mapping[str, Any]) -> bool:
    """Keep observations when an active command was unchanged, not blocked.

    Older persisted training samples do not contain ``command_skip_reason``.
    An active directional command with a non-zero request could only be
    skipped by the input/output command builder because it was unchanged
    within tolerance, so infer that specific legacy case conservatively.
    """

    skipped = sample.get("command_skipped")
    if skipped is False:
        return True
    if skipped is not True:
        return False
    if sample.get("command_skip_reason") == "unchanged_within_tolerance":
        return _sample_direction(sample) is not None
    if "command_skip_reason" not in sample:
        return _sample_direction(sample) is not None
    return False


def _direction_sample_quality(
    samples: list[Mapping[str, Any]],
    direction: str,
    *,
    expected_profile_signature: str | None = None,
) -> tuple[list[Mapping[str, Any]], dict[str, int]]:
    direction_samples = [
        sample for sample in samples if sample.get("direction") == direction
    ]
    usable: list[Mapping[str, Any]] = []
    unchanged_command_count = 0
    invalid_grid_count = 0
    missing_error_count = 0
    skipped_command_count = 0
    rejected_context_count = 0
    rejected_profile_mismatch_count = 0
    observation_segment = 0
    previous_usable = False
    for sample in samples:
        if sample.get("direction") != direction:
            observation_segment += 1
            previous_usable = False
            continue
        if expected_profile_signature is not None and sample.get(
            "profile_signature"
        ) != expected_profile_signature:
            rejected_profile_mismatch_count += 1
            observation_segment += 1
            previous_usable = False
            continue
        # Price-window AC charging and other non-PV actions have different
        # dynamics from the PV proportional loop and break its event sequence.
        if direction == "charge" and (
            sample.get("strategy_intent") != "pv_charge"
            or sample.get("ai_mode") not in {"automatic", "summer"}
            or sample.get("manual_action") != "standby"
            or sample.get("strategy_force") is not False
        ):
            rejected_context_count += 1
            observation_segment += 1
            previous_usable = False
            continue
        if sample.get("grid_valid") is not True:
            invalid_grid_count += 1
            observation_segment += 1
            previous_usable = False
            continue
        if _number(sample.get("grid_error_w")) is None:
            missing_error_count += 1
            observation_segment += 1
            previous_usable = False
            continue
        if not _command_is_usable_observation(sample):
            skipped_command_count += 1
            observation_segment += 1
            previous_usable = False
            continue
        if not previous_usable:
            observation_segment += 1
        usable_sample = dict(sample)
        usable_sample["_training_observation_segment"] = observation_segment
        usable.append(usable_sample)
        previous_usable = True
        if sample.get("command_skipped") is True:
            unchanged_command_count += 1
    return usable, {
        "direction_sample_count": len(direction_samples),
        "unchanged_command_sample_count": unchanged_command_count,
        "rejected_invalid_grid_count": invalid_grid_count,
        "rejected_missing_error_count": missing_error_count,
        "rejected_command_skip_count": skipped_command_count,
        "rejected_context_count": rejected_context_count,
        "rejected_profile_mismatch_count": rejected_profile_mismatch_count,
    }


def _response_events(samples: list[Mapping[str, Any]]) -> int:
    events = 0
    last_command: float | None = None
    last_segment: Any = None
    for sample in samples:
        segment = (
            sample.get("_training_session_segment"),
            sample.get("_training_observation_segment"),
        )
        if last_command is not None and segment != last_segment:
            last_command = None
        requested = max(
            _number(sample.get("requested_charge_w")) or 0.0,
            _number(sample.get("requested_discharge_w")) or 0.0,
        )
        if last_command is not None and abs(requested - last_command) >= 20.0:
            events += 1
        last_command = requested
        last_segment = segment
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
    samples: list[Mapping[str, Any]],
    direction: str,
    *,
    expected_profile_signature: str | None = None,
) -> ShadowDirectionResult:
    usable, quality = _direction_sample_quality(
        samples,
        direction,
        expected_profile_signature=expected_profile_signature,
    )
    events = _response_events(usable)
    valid_ratio = len(usable) / max(1, quality["direction_sample_count"])
    confidence = min(1.0, len(usable) / 120.0) * min(1.0, events / 8.0) * valid_ratio
    parameters: dict[str, float | None] = {
        "kp_up": None,
        "kp_down": None,
        "max_step_up_w": None,
        "max_step_down_w": None,
    }
    baseline = _direction_score(usable, gain_factor=1.0)
    insufficient_reasons = []
    if len(usable) < MIN_DIRECTION_SAMPLES:
        insufficient_reasons.append("too_few_samples")
    if events < MIN_RESPONSE_EVENTS:
        insufficient_reasons.append("too_few_response_events")
    if confidence < MIN_EVALUATION_CONFIDENCE:
        insufficient_reasons.append("confidence_below_threshold")
    if baseline is None:
        insufficient_reasons.append("missing_baseline")
    if insufficient_reasons:
        return ShadowDirectionResult(
            sample_count=len(usable),
            direction_sample_count=quality["direction_sample_count"],
            unchanged_command_sample_count=quality[
                "unchanged_command_sample_count"
            ],
            rejected_invalid_grid_count=quality["rejected_invalid_grid_count"],
            rejected_missing_error_count=quality["rejected_missing_error_count"],
            rejected_command_skip_count=quality["rejected_command_skip_count"],
            rejected_context_count=quality["rejected_context_count"],
            rejected_profile_mismatch_count=quality[
                "rejected_profile_mismatch_count"
            ],
            valid_sample_ratio=round(valid_ratio, 3),
            minimum_confidence=MIN_EVALUATION_CONFIDENCE,
            response_event_count=events,
            confidence=round(confidence, 3),
            baseline_score=round(baseline[0], 2) if baseline else None,
            candidate_score=None,
            overshoot_rate=round(baseline[1], 3) if baseline else None,
            relative_improvement=None,
            selected_gain_factor=None,
            parameters=parameters,
            decision="insufficient_data",
            insufficient_reasons=tuple(insufficient_reasons),
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
        direction_sample_count=quality["direction_sample_count"],
        unchanged_command_sample_count=quality[
            "unchanged_command_sample_count"
        ],
        rejected_invalid_grid_count=quality["rejected_invalid_grid_count"],
        rejected_missing_error_count=quality["rejected_missing_error_count"],
        rejected_command_skip_count=quality["rejected_command_skip_count"],
        rejected_context_count=quality["rejected_context_count"],
        rejected_profile_mismatch_count=quality[
            "rejected_profile_mismatch_count"
        ],
        valid_sample_ratio=round(valid_ratio, 3),
        minimum_confidence=MIN_EVALUATION_CONFIDENCE,
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


def _reversal_ineligibility_reason(
    sample: Mapping[str, Any], *, expected_profile_signature: str | None = None
) -> str | None:
    """Return the first reason a command is unsafe to delay in the shadow."""

    if sample.get("ai_mode") != "automatic":
        return "not_automatic"
    if (
        expected_profile_signature is not None
        and sample.get("profile_signature") != expected_profile_signature
    ):
        return "profile_changed"
    if sample.get("manual_action") != "standby":
        return "manual_action"
    if sample.get("strategy_intent") not in {"pv_charge", "cover_deficit"}:
        return "strategy_not_pv_or_load"
    if sample.get("strategy_force") is not False:
        return "forced_or_unknown_strategy"
    allowed_priority = MAX_AUTOMATIC_STRATEGY_PRIORITY_BY_INTENT.get(
        str(sample.get("strategy_intent"))
    )
    priority = _number(sample.get("strategy_priority"))
    if (
        allowed_priority is None
        or priority is None
        or priority > allowed_priority
    ):
        return "priority_missing_or_high"
    if sample.get("mode_allowed") is not True:
        return "mode_change_denied"
    if sample.get("discharge_allowed") is not True:
        return "discharge_protection"
    if sample.get("grid_valid") is not True:
        return "invalid_grid"
    if not _command_is_usable_observation(sample):
        return "command_not_observable"
    return None


def _reversal_hysteresis_shadow(
    samples: list[Mapping[str, Any]],
    *,
    expected_profile_signature: str | None = None,
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
            _reversal_ineligibility_reason(
                sample,
                expected_profile_signature=expected_profile_signature,
            )
            is None
        )

    direction_samples = [
        sample for _, sample in timed if _sample_direction(sample) is not None
    ]
    exclusion_counts: Counter[str] = Counter()
    for sample in direction_samples:
        reason = _reversal_ineligibility_reason(
            sample,
            expected_profile_signature=expected_profile_signature,
        )
        if reason is not None:
            exclusion_counts[reason] += 1

    eligible_samples = 0
    observed_reversals = 0
    eligible_reversals = 0
    override_reversals = 0
    held_reversals = 0
    released_reversals = 0
    unchanged_command_samples = 0
    held_seconds = 0.0
    held_energy_ws = 0.0
    max_hold_seconds = 0.0
    previous: tuple[datetime, str, float, Mapping[str, Any]] | None = None
    locked_direction: str | None = None
    pending_direction: str | None = None
    pending_ws = 0.0
    pending_seconds = 0.0

    for timestamp, sample in timed:
        segment = sample.get("_training_session_segment")
        if previous is not None and previous[3].get(
            "_training_session_segment"
        ) != segment:
            previous = None
            locked_direction = None
            pending_direction = None
            pending_ws = 0.0
            pending_seconds = 0.0
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
            if sample.get("command_skipped") is True:
                unchanged_command_samples += 1
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
        "direction_sample_count": len(direction_samples),
        "eligible_sample_count": eligible_samples,
        "unchanged_command_sample_count": unchanged_command_samples,
        "eligibility_exclusion_counts": dict(sorted(exclusion_counts.items())),
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


def evaluate_training_sessions(sessions: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Replay compatible training runs as one bounded, passive data pool."""

    sessions = [session for session in sessions if isinstance(session, Mapping)]
    if not sessions:
        sessions = [{}]
    latest = sessions[-1]
    profile_signature = latest.get("profile_signature")
    latest_key = latest.get("key")
    same_device_sessions = (
        [session for session in sessions if session.get("key") == latest_key]
        if latest_key is not None
        else [latest]
    )
    compatible_sessions = [
        session
        for session in same_device_sessions
        if profile_signature is not None
        and session.get("profile_signature") == profile_signature
    ]
    # Legacy sessions have no profile fingerprint. They remain evaluable alone,
    # but are never mixed with another run whose baseline cannot be verified.
    if not compatible_sessions:
        compatible_sessions = [latest]

    samples: list[Mapping[str, Any]] = []
    for index, session in enumerate(compatible_sessions):
        raw_samples = session.get("samples")
        if not isinstance(raw_samples, list):
            continue
        segment = f"{index}:{session.get('started_at') or 'unknown'}"
        for item in raw_samples:
            if not isinstance(item, Mapping):
                continue
            sample = dict(item)
            sample["_training_session_segment"] = segment
            samples.append(sample)

    charge = _evaluate_direction(
        samples,
        "charge",
        expected_profile_signature=(
            str(profile_signature) if profile_signature is not None else None
        ),
    )
    discharge = _evaluate_direction(
        samples,
        "discharge",
        expected_profile_signature=(
            str(profile_signature) if profile_signature is not None else None
        ),
    )
    profile_samples = [
        item
        for item in samples
        if profile_signature is None
        or item.get("profile_signature") == profile_signature
    ]
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
        "sessions_aggregated": len(compatible_sessions),
        "sessions_available": len(same_device_sessions),
        "sessions_excluded_incompatible": max(
            0, len(same_device_sessions) - len(compatible_sessions)
        ),
        "profile_signature": profile_signature,
        "charge_context_counts": {
            "pv_regulation": sum(
                item.get("direction") == "charge"
                and item.get("strategy_intent") == "pv_charge"
                and item.get("ai_mode") in {"automatic", "summer"}
                and item.get("manual_action") == "standby"
                and item.get("strategy_force") is False
                for item in profile_samples
            ),
            "fixed_or_other": sum(
                item.get("direction") == "charge"
                and not (
                    item.get("strategy_intent") == "pv_charge"
                    and item.get("ai_mode") in {"automatic", "summer"}
                    and item.get("manual_action") == "standby"
                    and item.get("strategy_force") is False
                )
                for item in profile_samples
            ),
        },
        "score_unit": "mean_absolute_predicted_grid_error_w",
        "interpretation": (
            "Screening estimate from recorded errors, commands, readbacks, and "
            "baseline gains; it does not simulate full device or grid dynamics."
        ),
        "live_parameters_changed": False,
        "reversal_hysteresis": _reversal_hysteresis_shadow(
            samples,
            expected_profile_signature=(
                str(profile_signature) if profile_signature is not None else None
            ),
        ),
        "charge": charge.as_dict(),
        "discharge": discharge.as_dict(),
    }


def evaluate_training_session(session: Mapping[str, Any]) -> dict[str, Any]:
    """Backward-compatible single-run evaluator entrypoint."""

    return evaluate_training_sessions([session])
