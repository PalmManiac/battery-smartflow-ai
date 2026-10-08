"""Bounded grace for transient grid-sensor gaps during active discharge."""

from __future__ import annotations


class GridSensorGapGrace:
    """Track invalid-grid duration and allow only a short output hold."""

    def __init__(self, grace_seconds: float) -> None:
        self.grace_seconds = max(0.0, float(grace_seconds))
        self._invalid_since: float | None = None

    def observe(self, *, now: float, valid: bool) -> float:
        """Return invalid duration, resetting the timer when data recovers."""

        if valid:
            self._invalid_since = None
            return 0.0

        if self._invalid_since is None:
            self._invalid_since = float(now)

        return max(0.0, float(now) - self._invalid_since)

    def may_hold_discharge(
        self,
        *,
        elapsed_seconds: float,
        automatic_mode: bool,
        active_discharge: bool,
    ) -> bool:
        """Permit holding the existing output only during a brief gap."""

        return bool(
            automatic_mode
            and active_discharge
            and self.grace_seconds > 0.0
            and float(elapsed_seconds) <= self.grace_seconds
        )
