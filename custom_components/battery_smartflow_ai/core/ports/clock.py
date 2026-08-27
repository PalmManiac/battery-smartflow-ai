"""Neutral time source for calendar and process-runtime semantics."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    """Provide explicit calendar time and monotonic process time."""

    def utc_now(self) -> datetime:
        """Return an aware UTC timestamp for restart-safe domain time."""

    def local_now(self) -> datetime:
        """Return an aware local timestamp for calendar-based planning."""

    def monotonic(self) -> float:
        """Return process-local seconds for non-persisted intervals."""
