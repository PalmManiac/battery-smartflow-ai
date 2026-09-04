"""Neutral Zendure HEMS safety states."""

from enum import StrEnum


class HemsStatus(StrEnum):
    """Safety-relevant interpretation of one device's HEMS telemetry."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    UNKNOWN = "unknown"
    STALE = "stale"
    INVALID = "invalid"
    UNSUPPORTED = "unsupported"
