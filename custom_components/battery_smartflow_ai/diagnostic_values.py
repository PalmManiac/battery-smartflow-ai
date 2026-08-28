"""Privacy-safe presentation values for permanent HA diagnostics."""

from __future__ import annotations

from pathlib import Path

from .debug_package import redact_secrets


def safe_diagnostic_sensor_value(key: str, value: object) -> object:
    """Minimize permanent diagnostic values without changing entity identity."""

    if key == "debug_last_package":
        # The full owned path remains internal for diagnostics download. A
        # Recorder-facing entity only needs the non-sensitive package name.
        return Path(str(value)).name
    if key == "debug_last_error":
        # Free error text may contain credentials from an upstream exception.
        return redact_secrets(str(value))
    return value
