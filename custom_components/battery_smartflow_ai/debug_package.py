"""Pure data model for V4.4.0 JSON debug packages.

This module deliberately has no Home Assistant imports.  Building a package must
not create entities, touch the recorder, or write files.  Recording lifecycle
and persistence are added by the later V4.4.0 work items.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import re
from typing import Any, Mapping

from .core.clock import SystemClock


DEBUG_SCHEMA_NAME = "battery_smartflow_ai.debug"
DEBUG_SCHEMA_VERSION = 1

_SECRET_KEY_PARTS = (
    "access_token",
    "api_key",
    "apikey",
    "auth",
    "bearer",
    "client_secret",
    "credential",
    "password",
    "private_key",
    "refresh_token",
    "secret",
    "token",
)
_REDACTED = "[REDACTED]"
_AUTHORIZATION_PATTERN = re.compile(
    r"(?i)\bauthorization(\s*[:=]\s*)(?:(bearer|basic)\s+)?[^\s,;&]+"
)
_BEARER_PATTERN = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")
_SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b("
    r"access[_ -]?token|refresh[_ -]?token|api[_ -]?key|client[_ -]?secret|"
    r"password|secret|token"
    r")\b(\s*[:=]\s*)([^\s,;&]+)"
)


def _redact_text(value: str) -> str:
    """Remove common inline credential forms from free diagnostic text."""

    value = _AUTHORIZATION_PATTERN.sub(
        lambda match: (
            f"Authorization{match.group(1)}"
            f"{match.group(2).title() + ' ' if match.group(2) else ''}{_REDACTED}"
        ),
        value,
    )
    value = _BEARER_PATTERN.sub(f"Bearer {_REDACTED}", value)
    return _SECRET_ASSIGNMENT_PATTERN.sub(
        lambda match: f"{match.group(1)}{match.group(2)}{_REDACTED}",
        value,
    )


def _iso_utc(value: datetime) -> str:
    """Return a stable ISO-8601 UTC timestamp."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Debug timestamps must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _json_safe(value: Any) -> Any:
    """Convert common runtime values into deterministic JSON-safe values."""

    if isinstance(value, str):
        return _redact_text(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, datetime):
        return _iso_utc(value)
    if isinstance(value, Enum):
        return _json_safe(value.value)
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_safe(item) for item in value]
    return str(value)


def redact_secrets(value: Any) -> Any:
    """Return a JSON-safe deep copy with secret-looking mapping values removed.

    Redaction happens while the package dictionary is built, so callers cannot
    accidentally persist an unfiltered package through the supported API.
    """

    safe = _json_safe(deepcopy(value))
    return _redact_json_safe(safe)


def _redact_json_safe(value: Any) -> Any:
    """Redact an already copied and normalized JSON-compatible value."""

    safe = value
    if isinstance(safe, dict):
        redacted: dict[str, Any] = {}
        for key, item in safe.items():
            normalized = key.casefold().replace("-", "_").replace(" ", "_")
            if any(part in normalized for part in _SECRET_KEY_PARTS):
                redacted[key] = _REDACTED
            else:
                redacted[key] = _redact_json_safe(item)
        return redacted
    if isinstance(safe, list):
        return [_redact_json_safe(item) for item in safe]
    return safe


@dataclass(slots=True)
class DebugSample:
    """One diagnostic snapshot captured during an active recording."""

    timestamp: datetime
    strategy: Mapping[str, Any] = field(default_factory=dict)
    regulation: Mapping[str, Any] = field(default_factory=dict)
    raw_values: Mapping[str, Any] = field(default_factory=dict)
    prices: Mapping[str, Any] = field(default_factory=dict)
    planning: Mapping[str, Any] = field(default_factory=dict)
    command: Mapping[str, Any] = field(default_factory=dict)

    def redacted_copy(self) -> DebugSample:
        """Return a detached sample safe to retain in the recorder buffer."""

        _iso_utc(self.timestamp)
        return DebugSample(
            timestamp=self.timestamp,
            strategy=redact_secrets(self.strategy),
            regulation=redact_secrets(self.regulation),
            raw_values=redact_secrets(self.raw_values),
            prices=redact_secrets(self.prices),
            planning=redact_secrets(self.planning),
            command=redact_secrets(self.command),
        )

    def as_dict(self) -> dict[str, Any]:
        """Build the public sample shape used by schema version 1."""

        return redact_secrets(
            {
                "ts": _iso_utc(self.timestamp),
                "strategy": self.strategy,
                "regulation": self.regulation,
                "raw_values": self.raw_values,
                "prices": self.prices,
                "planning": self.planning,
                "command": self.command,
            }
        )


@dataclass(slots=True)
class DebugPackage:
    """In-memory representation of one complete debug recording."""

    integration_version: str
    recording_start: datetime
    recording_end: datetime | None = None
    created_at: datetime | None = None
    device_profile: str | None = None
    ai_mode: str | None = None
    season_mode: str | None = None
    config: Mapping[str, Any] = field(default_factory=dict)
    profile: Mapping[str, Any] = field(default_factory=dict)
    samples: list[DebugSample] = field(default_factory=list)
    summary: Mapping[str, Any] = field(default_factory=dict)
    warnings: list[Any] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        """Build a complete, JSON-safe and secret-filtered package."""

        created_at = self.created_at or SystemClock().utc_now()
        if self.recording_end is not None and self.recording_end < self.recording_start:
            raise ValueError("recording_end must not be before recording_start")

        package = {
            "meta": {
                "schema": DEBUG_SCHEMA_NAME,
                "schema_version": DEBUG_SCHEMA_VERSION,
                "integration_version": self.integration_version,
                "created_at": _iso_utc(created_at),
                "recording_start": _iso_utc(self.recording_start),
                "recording_end": (
                    _iso_utc(self.recording_end)
                    if self.recording_end is not None
                    else None
                ),
                "device_profile": self.device_profile,
                "ai_mode": self.ai_mode,
                "season_mode": self.season_mode,
            },
            "config": self.config,
            "profile": self.profile,
            "samples": [sample.as_dict() for sample in self.samples],
            "summary": self.summary,
            "warnings": self.warnings,
        }
        return redact_secrets(package)
