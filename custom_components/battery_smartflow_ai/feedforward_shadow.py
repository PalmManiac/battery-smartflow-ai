"""Read-only feedforward candidate evaluation for V5.2 diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math


FEEDFORWARD_SHADOW_MAX_AGE_SECONDS = 5.0
_OUTPUT_INTENTS = frozenset(
    {
        "cover_deficit",
        "peak_discharge",
        "arbitrage_discharge",
        "manual_discharge",
    }
)


@dataclass(frozen=True, slots=True)
class FeedforwardShadowResult:
    available: bool
    reason: str
    measured_battery_power_w: float | None = None
    measurement_age_seconds: float | None = None
    candidate_power_w: float | None = None

    def diagnostics(self) -> dict[str, float | str | bool | None]:
        return {
            "available": self.available,
            "reason": self.reason,
            "measured_battery_power_w": self.measured_battery_power_w,
            "measurement_age_seconds": self.measurement_age_seconds,
            "candidate_power_w": self.candidate_power_w,
        }


def evaluate_feedforward_shadow(
    *,
    intent: str,
    error_w: float | None,
    measured_battery_power_w: float | None,
    observed_at: datetime | None,
    now: datetime,
    max_input_w: float,
    max_output_w: float,
) -> FeedforwardShadowResult:
    """Estimate a feedforward setpoint without affecting the active controller.

    Battery power uses the coordinator convention: discharge is positive and
    charge is negative. A sample is only considered when both native power
    sensors have supplied a recent observation timestamp.
    """

    if intent not in _OUTPUT_INTENTS and intent != "pv_charge":
        return FeedforwardShadowResult(False, "intent_not_regulated")
    try:
        error = float(error_w)
        measured = float(measured_battery_power_w)
    except (TypeError, ValueError, OverflowError):
        return FeedforwardShadowResult(False, "regulation_error_unavailable")
    if not math.isfinite(error):
        return FeedforwardShadowResult(False, "regulation_error_unavailable")
    if not math.isfinite(measured):
        return FeedforwardShadowResult(False, "native_battery_power_unavailable")
    if observed_at is None:
        return FeedforwardShadowResult(False, "native_battery_power_timestamp_missing")
    if now.utcoffset() is None or observed_at.utcoffset() is None:
        return FeedforwardShadowResult(False, "timestamp_timezone_missing")

    age_seconds = (now - observed_at).total_seconds()
    if age_seconds < 0.0:
        return FeedforwardShadowResult(False, "native_battery_power_from_future")
    if age_seconds > FEEDFORWARD_SHADOW_MAX_AGE_SECONDS:
        return FeedforwardShadowResult(
            False,
            "native_battery_power_stale",
            measurement_age_seconds=round(age_seconds, 3),
        )

    if intent == "pv_charge":
        current_charge_w = max(0.0, -measured)
        candidate = current_charge_w + error
        candidate = min(max(0.0, candidate), max(0.0, float(max_input_w)))
    else:
        current_discharge_w = max(0.0, measured)
        candidate = current_discharge_w + error
        candidate = min(max(0.0, candidate), max(0.0, float(max_output_w)))

    return FeedforwardShadowResult(
        available=True,
        reason="candidate_only_no_control_change",
        measured_battery_power_w=round(measured, 2),
        measurement_age_seconds=round(age_seconds, 3),
        candidate_power_w=round(candidate, 2),
    )
