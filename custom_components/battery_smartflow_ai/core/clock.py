"""Platform-independent production and deterministic Clock implementations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, tzinfo
import time


def as_utc(value: datetime) -> datetime:
    """Normalize an aware domain timestamp without a platform dependency."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("value must be timezone-aware")
    return value.astimezone(UTC)


class SystemClock:
    """Read calendar and monotonic time from the host system."""

    def __init__(self, *, local_timezone: tzinfo = UTC) -> None:
        self._local_timezone = local_timezone

    def utc_now(self) -> datetime:
        return datetime.now(UTC)

    def local_now(self) -> datetime:
        return datetime.now(self._local_timezone)

    def monotonic(self) -> float:
        return time.monotonic()


class TestClock:
    """Controllable Clock for deterministic domain tests without waiting."""

    __test__ = False

    def __init__(
        self,
        now: datetime,
        *,
        local_timezone: tzinfo | None = None,
        monotonic_seconds: float = 0.0,
    ) -> None:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        self._utc_now = now.astimezone(UTC)
        self._local_timezone = local_timezone or now.tzinfo
        self._monotonic = float(monotonic_seconds)

    def utc_now(self) -> datetime:
        return self._utc_now

    def local_now(self) -> datetime:
        return self._utc_now.astimezone(self._local_timezone)

    def monotonic(self) -> float:
        return self._monotonic

    def set(self, now: datetime) -> None:
        """Set calendar time without changing the monotonic reading."""

        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        self._utc_now = now.astimezone(UTC)

    def advance(self, delta: timedelta) -> None:
        """Advance calendar and monotonic time together."""

        seconds = delta.total_seconds()
        if seconds < 0:
            raise ValueError("TestClock cannot advance by a negative duration")
        self._utc_now += delta
        self._monotonic += seconds
