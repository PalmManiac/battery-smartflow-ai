"""Interpret Zendure Cloud HEMS activity without guessing device properties."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .core.models import MeasuredValue, ValueValidity


HEMS_ACTIVITY_TIMEOUT_SECONDS = 60.0
HEMS_ACTIVITY_SOURCE = "cloud_mqtt_properties_energy"


@dataclass(frozen=True, slots=True)
class HemsActivityDiagnostic:
    monitoring: bool
    source: str
    monitoring_started_at: datetime | None
    last_activity_at: datetime | None
    quiet_seconds: float | None
    confirmation_window_seconds: float


class HemsActivityTracker:
    """Per-device heartbeat tracker matching the observed Zendure event path."""

    def __init__(self, *, timeout_seconds: float = HEMS_ACTIVITY_TIMEOUT_SECONDS) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._timeout = float(timeout_seconds)
        self._monitoring = False
        self._monitoring_started_at: datetime | None = None
        self._last_activity_at: datetime | None = None

    def set_monitoring(self, available: bool, *, observed_at: datetime) -> None:
        """Start a fresh quiet window only for a healthy subscribed transport."""

        if available and not self._monitoring:
            self._monitoring_started_at = observed_at
        self._monitoring = available

    def observe_energy(self, *, observed_at: datetime) -> None:
        """Treat properties/energy solely as positive HEMS activity evidence."""

        self._last_activity_at = observed_at

    def measurement(self, *, now: datetime) -> MeasuredValue[bool]:
        if self._last_activity_at is not None:
            age = max(0.0, (now - self._last_activity_at).total_seconds())
            if not self._monitoring:
                return MeasuredValue.absent(
                    ValueValidity.STALE,
                    observed_at=self._last_activity_at,
                )
            if age <= self._timeout:
                return MeasuredValue.available(
                    True,
                    observed_at=self._last_activity_at,
                )
            return MeasuredValue.available(
                False,
                observed_at=self._last_activity_at,
            )

        if not self._monitoring or self._monitoring_started_at is None:
            return MeasuredValue.absent(ValueValidity.NEVER_RECEIVED)
        quiet = max(0.0, (now - self._monitoring_started_at).total_seconds())
        if quiet <= self._timeout:
            return MeasuredValue.absent(
                ValueValidity.NEVER_RECEIVED,
                observed_at=self._monitoring_started_at,
            )
        return MeasuredValue.available(False, observed_at=self._monitoring_started_at)

    def diagnostics(self, *, now: datetime) -> HemsActivityDiagnostic:
        anchor = self._last_activity_at or self._monitoring_started_at
        return HemsActivityDiagnostic(
            monitoring=self._monitoring,
            source=HEMS_ACTIVITY_SOURCE,
            monitoring_started_at=self._monitoring_started_at,
            last_activity_at=self._last_activity_at,
            quiet_seconds=(
                max(0.0, (now - anchor).total_seconds()) if anchor else None
            ),
            confirmation_window_seconds=self._timeout,
        )
