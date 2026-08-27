"""Bounded recording lifecycle for V4.4.0 JSON debug packages."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Mapping

from .debug_package import DebugPackage, DebugSample, redact_secrets


ALLOWED_RECORDING_MINUTES = frozenset({10, 30, 60, 120})
DEFAULT_MAX_SAMPLES = 720


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Debug timestamps must be timezone-aware")


@dataclass(frozen=True, slots=True)
class DebugRecorderStatus:
    """Small immutable status snapshot suitable for sparse HA entities."""

    active: bool
    recording_start: datetime | None
    recording_end: datetime | None
    sample_count: int
    dropped_sample_count: int


class DebugRecorder:
    """Manage one bounded in-memory debug recording at a time.

    The recorder has no scheduler and performs no I/O.  The integration calls
    ``tick`` or ``record`` with its normal coordinator cadence.  This keeps the
    inactive path allocation-free and avoids an additional polling loop.
    """

    def __init__(self, *, integration_version: str, max_samples: int = DEFAULT_MAX_SAMPLES) -> None:
        if max_samples < 1:
            raise ValueError("max_samples must be at least 1")
        self._integration_version = integration_version
        self._max_samples = max_samples
        self._active = False
        self._recording_start: datetime | None = None
        self._recording_end: datetime | None = None
        self._samples: deque[DebugSample] = deque(maxlen=max_samples)
        self._captured_sample_count = 0
        self._dropped_sample_count = 0
        self._device_profile: str | None = None
        self._ai_mode: str | None = None
        self._season_mode: str | None = None
        self._config: Mapping[str, Any] = {}
        self._profile: Mapping[str, Any] = {}

    @property
    def is_active(self) -> bool:
        """Return whether callers should construct and submit samples."""

        return self._active

    @property
    def status(self) -> DebugRecorderStatus:
        """Return the current lightweight recorder state."""

        return DebugRecorderStatus(
            active=self._active,
            recording_start=self._recording_start,
            recording_end=self._recording_end,
            sample_count=len(self._samples),
            dropped_sample_count=self._dropped_sample_count,
        )

    def start(
        self,
        *,
        duration_minutes: int,
        now: datetime,
        device_profile: str | None = None,
        ai_mode: str | None = None,
        season_mode: str | None = None,
        config: Mapping[str, Any] | None = None,
        profile: Mapping[str, Any] | None = None,
    ) -> DebugRecorderStatus:
        """Start a fresh recording with one of the supported durations."""

        _require_aware(now)
        if self._active:
            raise RuntimeError("A debug recording is already active")
        if duration_minutes not in ALLOWED_RECORDING_MINUTES:
            choices = ", ".join(str(value) for value in sorted(ALLOWED_RECORDING_MINUTES))
            raise ValueError(f"duration_minutes must be one of: {choices}")

        self._active = True
        self._recording_start = now
        self._recording_end = now + timedelta(minutes=duration_minutes)
        self._samples.clear()
        self._captured_sample_count = 0
        self._dropped_sample_count = 0
        self._device_profile = device_profile
        self._ai_mode = ai_mode
        self._season_mode = season_mode
        self._config = redact_secrets(config or {})
        self._profile = redact_secrets(profile or {})
        return self.status

    def record(self, sample: DebugSample, *, now: datetime) -> DebugPackage | None:
        """Capture a sample or auto-stop when the configured end is reached."""

        if not self._active:
            return None
        completed = self.tick(now=now)
        if completed is not None:
            return completed

        if len(self._samples) == self._max_samples:
            self._dropped_sample_count += 1
        self._samples.append(sample.redacted_copy())
        self._captured_sample_count += 1
        return None

    def tick(self, *, now: datetime) -> DebugPackage | None:
        """Auto-stop an elapsed recording without requiring a new sample."""

        if not self._active:
            return None
        _require_aware(now)
        assert self._recording_end is not None
        if now < self._recording_end:
            return None
        return self._finish(now=self._recording_end, stop_reason="duration_elapsed")

    def stop(self, *, now: datetime) -> DebugPackage | None:
        """Stop an active recording manually; return ``None`` when inactive."""

        if not self._active:
            return None
        _require_aware(now)
        assert self._recording_start is not None
        if now < self._recording_start:
            raise ValueError("Stop time must not be before recording start")
        return self._finish(now=now, stop_reason="manual")

    def _finish(self, *, now: datetime, stop_reason: str) -> DebugPackage:
        assert self._recording_start is not None
        warnings: list[dict[str, Any]] = []
        if self._dropped_sample_count:
            warnings.append(
                {
                    "code": "sample_limit_reached",
                    "message": "Oldest samples were discarded to keep memory bounded.",
                    "dropped_sample_count": self._dropped_sample_count,
                }
            )
        package = DebugPackage(
            integration_version=self._integration_version,
            recording_start=self._recording_start,
            recording_end=now,
            created_at=now,
            device_profile=self._device_profile,
            ai_mode=self._ai_mode,
            season_mode=self._season_mode,
            config=self._config,
            profile=self._profile,
            samples=list(self._samples),
            summary={
                "stop_reason": stop_reason,
                "captured_sample_count": self._captured_sample_count,
                "retained_sample_count": len(self._samples),
                "dropped_sample_count": self._dropped_sample_count,
            },
            warnings=warnings,
        )
        self._active = False
        self._recording_start = None
        self._recording_end = None
        self._samples.clear()
        self._captured_sample_count = 0
        self._dropped_sample_count = 0
        return package
