"""Pure helpers for event-driven regulation refresh decisions."""

from __future__ import annotations

import math
from typing import Any


def grid_value_changed(old_raw: Any, new_raw: Any, *, tolerance_w: float = 0.5) -> bool:
    """Return whether grid validity or a usable numeric reading changed."""

    old_value = _to_float(old_raw)
    new_value = _to_float(new_raw)
    if old_value is None or new_value is None:
        return old_value is not new_value
    return not math.isclose(
        old_value, new_value, rel_tol=0.0, abs_tol=max(0.0, tolerance_w)
    )


def grid_refresh_delay(
    *, now_monotonic: float, last_refresh_monotonic: float | None, min_interval_s: float
) -> float:
    """Return the remaining delay before the next coalesced regulation refresh."""

    if last_refresh_monotonic is None:
        return 0.0
    return max(
        0.0,
        max(0.0, float(min_interval_s))
        - (float(now_monotonic) - float(last_refresh_monotonic)),
    )


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None
