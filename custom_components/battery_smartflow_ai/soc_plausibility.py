"""Fail-safe accounting treatment for physically implausible SoC samples."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


SOC_OUTLIER_CONFIRM_CYCLES = 3
SOC_OUTLIER_MIN_TOLERANCE_PCT = 2.0
SOC_OUTLIER_CONFIRM_TOLERANCE_PCT = 1.0
SOC_OUTLIER_MAX_CONTINUOUS_SECONDS = 300.0


@dataclass(frozen=True, slots=True)
class SocAccountingDecision:
    """The SoC value that may safely affect persistent economics."""

    accounting_soc: float
    accepted: bool
    status: str
    pending_soc: float | None
    pending_count: int


def evaluate_soc_for_accounting(
    *,
    raw_soc: float,
    previous_soc: float | None,
    previous_at: datetime | None,
    now: datetime,
    capacity_kwh: float,
    max_charge_w: float,
    max_discharge_w: float,
    pending_soc: float | None,
    pending_count: int,
) -> SocAccountingDecision:
    """Accept plausible SoC changes, but never let one bad sample reset economics.

    The raw SoC remains available to the control and safety paths. This helper
    only protects the long-lived energy and price ledger from a discontinuity
    that the battery could not physically have made in the elapsed time.
    """

    raw_soc = float(raw_soc)
    if previous_soc is None:
        return SocAccountingDecision(raw_soc, True, "baseline", None, 0)
    if previous_at is None:
        # Existing installations have a legacy SoC but no timestamp. Preserve
        # that trusted value for one cycle while establishing the time base.
        return SocAccountingDecision(
            float(previous_soc), True, "timestamp_initialized", None, 0
        )

    elapsed_seconds = (now - previous_at).total_seconds()
    if elapsed_seconds <= 0:
        return SocAccountingDecision(raw_soc, True, "clock_reset", None, 0)
    if elapsed_seconds > SOC_OUTLIER_MAX_CONTINUOUS_SECONDS:
        return SocAccountingDecision(raw_soc, True, "gap_baseline", None, 0)
    if capacity_kwh <= 0:
        return SocAccountingDecision(raw_soc, True, "capacity_unknown", None, 0)

    previous_soc = float(previous_soc)
    power_w = max_charge_w if raw_soc >= previous_soc else max_discharge_w
    possible_change_pct = (
        max(0.0, float(power_w))
        * elapsed_seconds
        / 3_600_000.0
        / float(capacity_kwh)
        * 100.0
    )
    allowed_change_pct = SOC_OUTLIER_MIN_TOLERANCE_PCT + possible_change_pct
    if abs(raw_soc - previous_soc) <= allowed_change_pct:
        return SocAccountingDecision(raw_soc, True, "accepted", None, 0)

    pending_matches = (
        pending_soc is not None
        and abs(raw_soc - float(pending_soc)) <= SOC_OUTLIER_CONFIRM_TOLERANCE_PCT
    )
    next_count = min(
        SOC_OUTLIER_CONFIRM_CYCLES,
        (max(0, int(pending_count)) + 1) if pending_matches else 1,
    )
    if next_count >= SOC_OUTLIER_CONFIRM_CYCLES:
        return SocAccountingDecision(
            raw_soc, True, "confirmed_discontinuity", None, 0
        )

    return SocAccountingDecision(
        previous_soc,
        False,
        "rejected_physical_outlier",
        raw_soc,
        next_count,
    )
