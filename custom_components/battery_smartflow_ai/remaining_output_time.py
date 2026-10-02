"""Helpers for Zendure's estimated remaining discharge time."""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from numbers import Real


def remaining_output_minutes(
    estimate: object,
    discharge_power_w: object,
    *,
    estimate_available: bool,
    discharge_available: bool,
) -> int | None:
    """Return usable remaining minutes only for a valid active discharge."""

    if not estimate_available or not discharge_available:
        return None
    if (
        not isinstance(estimate, Real)
        or isinstance(estimate, bool)
        or not math.isfinite(float(estimate))
    ):
        return None
    if (
        not isinstance(discharge_power_w, Real)
        or isinstance(discharge_power_w, bool)
        or not math.isfinite(float(discharge_power_w))
        or discharge_power_w <= 0
    ):
        return None

    minutes = int(estimate)
    return minutes if minutes > 0 else None


class RemainingOutputTime:
    """Keep the absolute timestamp stable until the device estimate changes."""

    def __init__(self) -> None:
        self._minutes: int | None = None
        self._timestamp: datetime | None = None

    def invalidate(self) -> None:
        """Forget the prior estimate when the sensor is no longer available."""

        self._minutes = None
        self._timestamp = None

    def remaining_minutes(
        self,
        estimate: object,
        discharge_power_w: object,
        *,
        estimate_available: bool,
        discharge_available: bool,
    ) -> int | None:
        """Validate the estimate and clear the cache as soon as it is unusable."""

        minutes = remaining_output_minutes(
            estimate,
            discharge_power_w,
            estimate_available=estimate_available,
            discharge_available=discharge_available,
        )
        if minutes is None:
            self.invalidate()
        return minutes

    def timestamp(
        self,
        minutes: int | None,
        *,
        now: datetime,
    ) -> datetime | None:
        if minutes is None or minutes <= 0:
            self.invalidate()
            return None
        if self._minutes != minutes or self._timestamp is None:
            self._minutes = minutes
            self._timestamp = now + timedelta(minutes=minutes)
        return self._timestamp
