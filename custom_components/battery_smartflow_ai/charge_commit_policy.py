"""Pure policy helpers for strategic AC charge bindings."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .strategy_state import ChargeCommitState


LEARNED_FORCED_REASONS = {
    "learned_charge_window_latest_start_reached",
    "learned_charge_window_deadline_too_close_start_now",
}

ECONOMIC_DISCHARGE_REASONS = {
    "adaptive_peak_discharge",
    "very_expensive_force_discharge",
    "price_based_discharge",
}


def learned_plan_charge_need_satisfied(
    *,
    commit_type: str,
    learned_charge_plan: Any | None,
) -> bool:
    """Return whether a valid learned plan no longer requests grid energy."""

    if str(commit_type or "") != "learned" or learned_charge_plan is None:
        return False

    status = str(
        getattr(learned_charge_plan, "status", "") or ""
    )
    if status not in {"ready", "active"}:
        return False

    decision_reason = str(
        getattr(learned_charge_plan, "decision_reason", "") or ""
    )
    if decision_reason == "learned_charge_window_no_charge_needed":
        return True

    required_energy = getattr(
        learned_charge_plan,
        "required_charge_energy_kwh",
        None,
    )
    if required_energy is None:
        return False

    try:
        return float(required_energy) <= 0.0
    except (TypeError, ValueError):
        return False


def learned_commit_is_forced(
    *,
    commit: ChargeCommitState,
    now: datetime,
) -> bool:
    """Return whether a learned binding must charge to meet its deadline."""

    if str(commit.commit_type or "") != "learned":
        return False

    if str(commit.phase or "") == "forced":
        return True

    if str(commit.source_reason or "") in LEARNED_FORCED_REASONS:
        return True

    return bool(
        commit.latest_start is not None
        and now >= commit.latest_start
    )


def learned_commit_should_yield_to_discharge(
    *,
    commit: ChargeCommitState,
    now: datetime,
    selected_reason: str,
) -> bool:
    """Return whether a non-forced learned binding must pause for discharge."""

    return bool(
        str(commit.commit_type or "") == "learned"
        and not learned_commit_is_forced(commit=commit, now=now)
        and str(selected_reason or "") in ECONOMIC_DISCHARGE_REASONS
    )
