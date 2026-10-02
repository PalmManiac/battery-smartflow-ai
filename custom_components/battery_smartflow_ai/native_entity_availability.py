"""Availability policy for optional native Zendure telemetry entities."""

from __future__ import annotations

OPTIONAL_NATIVE_MAIN_SENSOR_KEYS = frozenset({"firmware", "wifi_status"})


def optional_native_main_sensor_available(system: object, key: str) -> bool:
    """Return whether an optional main-device field has been observed."""

    if key == "firmware":
        measured = getattr(system, "firmware", None)
    elif key == "wifi_status":
        measurements = getattr(system, "measurements", {})
        measured = measurements.get("wifiState")
    else:
        return True
    return measured is not None and measured.valid


def optional_native_sensor_registry_action(
    *,
    available: bool,
    disabled_by_integration: bool,
    enabled: bool,
    initializing: bool,
) -> str | None:
    """Return an integration-owned registry transition, if one is needed."""

    if available and disabled_by_integration:
        return "enable"
    if not available and initializing and enabled:
        return "disable"
    return None
