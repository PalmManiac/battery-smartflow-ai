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


def smart_mode_state(value: object) -> str:
    """Translate Zendure's flash-write flag without guessing future values."""

    if isinstance(value, bool):
        return "unknown"
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "unknown"
    if numeric == 0:
        return "persistent_storage"
    if numeric == 1:
        return "temporary_control"
    return "unknown"


_ZENDURE_DOCUMENTED_STATUS_STATES = {
    "dataReady": {0: "not_ready", 1: "ready"},
    "gridState": {0: "disconnected", 1: "connected"},
    "pvStatus": {0: "inactive", 1: "active"},
    "socStatus": {0: "normal", 1: "calibrating"},
    "pass": {0: "inactive", 1: "active"},
    "reverseState": {0: "inactive", 1: "active"},
    "gridOffMode": {0: "standard", 1: "economic", 2: "disabled"},
    "is_error": {0: "no_error", 1: "error"},
}


def zendure_documented_status_state(key: str, value: object) -> str:
    """Translate only vendor status values with documented meanings.

    Unknown values intentionally remain visible as ``unknown`` rather than
    being guessed from neighboring firmware or device models.
    """

    if isinstance(value, bool):
        return "unknown"
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return "unknown"
    if numeric != value:
        return "unknown"
    return _ZENDURE_DOCUMENTED_STATUS_STATES.get(key, {}).get(numeric, "unknown")
