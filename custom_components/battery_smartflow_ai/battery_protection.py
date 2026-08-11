"""Pure battery-protection helpers."""

from __future__ import annotations

from datetime import datetime
from math import isfinite


MIN_CELL_VOLTAGE_HYSTERESIS_V = 0.01
CELL_VOLTAGE_EMERGENCY_MINIMUM_CHARGE_SECONDS = 20 * 60
NORMAL_CHARGE_CONFIRMATION_W = 50.0


def cell_voltage_emergency_minimum_elapsed(
    *,
    started_at: datetime | None,
    now: datetime,
) -> bool:
    """Return whether the emergency charge has built its minimum time buffer."""
    if started_at is None:
        return False
    try:
        elapsed_seconds = (now - started_at).total_seconds()
    except (TypeError, ValueError, OverflowError):
        return False
    return elapsed_seconds >= CELL_VOLTAGE_EMERGENCY_MINIMUM_CHARGE_SECONDS


def next_cell_voltage_emergency_state(
    *,
    previously_active: bool,
    protection_enabled: bool,
    lowest_cell_voltage: float | None,
    warning_voltage: float,
    resume_voltage: float,
    minimum_charge_elapsed: bool,
) -> bool:
    """Return the latched cell-voltage emergency-charge state.

    Charging starts at the warning threshold and remains active until both the
    configured minimum charging time and the resume voltage are reached. This
    prevents a voltage rise caused by the charging current from ending the
    emergency charge before the battery has gained a useful energy buffer.
    """
    if not protection_enabled or lowest_cell_voltage is None:
        return False

    try:
        cell_v = float(lowest_cell_voltage)
        warning_v = float(warning_voltage)
        resume_v = float(resume_voltage)
    except (TypeError, ValueError):
        return False

    if not all(isfinite(value) for value in (cell_v, warning_v, resume_v)):
        return False

    effective_resume_v = max(
        resume_v,
        warning_v + MIN_CELL_VOLTAGE_HYSTERESIS_V,
    )

    if cell_v <= warning_v:
        return True
    if previously_active and not minimum_charge_elapsed:
        return True
    if cell_v >= effective_resume_v:
        return False
    return bool(previously_active)


def next_cell_voltage_discharge_lock_state(
    *,
    previously_locked: bool,
    normal_charge_observed: bool,
    cell_voltage_emergency_active: bool,
    decision_action: str,
    decision_reason: str,
    measured_charge_w: float,
    soc: float,
    resume_soc: float,
    lowest_cell_voltage: float | None,
    resume_voltage: float,
) -> tuple[bool, bool]:
    """Return the persistent post-emergency discharge lock state."""
    locked = bool(previously_locked)
    observed = bool(normal_charge_observed) if locked else False
    observed_before_this_cycle = observed

    if cell_voltage_emergency_active:
        return True, False

    emergency_reasons = {
        "cell_voltage_emergency_charge",
        "emergency_latched_charge",
    }
    regular_charge_active = bool(
        locked
        and str(decision_action or "") == "charge"
        and str(decision_reason or "") not in emergency_reasons
        and float(measured_charge_w or 0.0) >= NORMAL_CHARGE_CONFIRMATION_W
    )
    if regular_charge_active:
        observed = True

    if (
        not locked
        or not observed_before_this_cycle
        or lowest_cell_voltage is None
    ):
        return locked, observed

    try:
        recovery_reached = bool(
            float(soc) >= float(resume_soc)
            and float(lowest_cell_voltage) >= float(resume_voltage)
        )
    except (TypeError, ValueError):
        recovery_reached = False

    if recovery_reached:
        return False, False
    return True, observed
