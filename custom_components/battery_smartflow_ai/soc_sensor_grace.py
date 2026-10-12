"""Bounded reuse of a recent SoC sample during transient sensor gaps."""

from __future__ import annotations

import math

SOC_SENSOR_GAP_GRACE_SECONDS = 120.0


def may_reuse_cached_soc_during_gap(
    *,
    age_seconds: float,
    grace_seconds: float = SOC_SENSOR_GAP_GRACE_SECONDS,
    automatic_mode: bool,
    active_command: bool,
    source_allows_grace: bool,
    cached_soc_pct: float | None,
    capacity_kwh: float,
    soc_min_pct: float,
    soc_max_pct: float,
    max_charge_w: float,
    max_discharge_w: float,
) -> bool:
    """Return whether a cached SoC is safe to reuse for this control cycle.

    The worst-case charge and discharge energy over the grace interval must
    both fit inside the configured SoC window. Reuse is limited to automatic
    operation that was already actively charging or discharging; it cannot
    start a new action or keep manual control alive without fresh SoC data.
    """

    if not automatic_mode or not active_command or not source_allows_grace:
        return False

    values = (
        age_seconds,
        grace_seconds,
        cached_soc_pct,
        capacity_kwh,
        soc_min_pct,
        soc_max_pct,
        max_charge_w,
        max_discharge_w,
    )
    if any(value is None or not math.isfinite(float(value)) for value in values):
        return False

    age = float(age_seconds)
    grace = max(0.0, float(grace_seconds))
    soc = float(cached_soc_pct)
    capacity = float(capacity_kwh)
    soc_min = float(soc_min_pct)
    soc_max = float(soc_max_pct)
    max_charge = float(max_charge_w)
    max_discharge = float(max_discharge_w)

    if age < 0.0 or age > grace or capacity <= 0.0:
        return False
    if not 0.0 <= soc <= 100.0 or not 0.0 <= soc_min < soc_max <= 100.0:
        return False
    if max_charge < 0.0 or max_discharge <= 0.0:
        return False

    # Convert maximum possible energy movement during the gap to SoC points.
    # Use the full configured limits in both directions, rather than assuming
    # that the current strategy will keep the same direction throughout.
    charge_headroom_pct = max_charge * age / (36_000.0 * capacity)
    discharge_headroom_pct = max_discharge * age / (36_000.0 * capacity)
    return bool(
        soc - discharge_headroom_pct > soc_min
        and soc + charge_headroom_pct < soc_max
    )
