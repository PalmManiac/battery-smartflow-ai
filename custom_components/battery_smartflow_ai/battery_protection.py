"""Pure battery-protection helpers."""

from __future__ import annotations

from math import isfinite


MIN_CELL_VOLTAGE_HYSTERESIS_V = 0.01


def next_cell_voltage_emergency_state(
    *,
    previously_active: bool,
    protection_enabled: bool,
    lowest_cell_voltage: float | None,
    warning_voltage: float,
    resume_voltage: float,
) -> bool:
    """Return the latched cell-voltage emergency-charge state.

    Charging starts at the warning threshold and remains active until the
    configured resume voltage is reached. This prevents the charging current
    from lifting the measured cell voltage just above the start threshold and
    immediately stopping the emergency charge again.
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
    if cell_v >= effective_resume_v:
        return False
    return bool(previously_active)
