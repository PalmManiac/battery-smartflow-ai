"""Neutral measured states shared by BSFAI core areas.

These models deliberately keep measurement validity separate from the numeric
value.  Adapters translate platform-specific states such as ``unknown`` and
``unavailable`` before constructing them.  Issue #268 will compose these
parts into the single runtime input; this module does not introduce a second
aggregate context.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Generic, TypeVar


ValueT = TypeVar("ValueT")


class ValueValidity(StrEnum):
    """Platform-neutral availability and data-quality classification."""

    VALID = "valid"
    MISSING = "missing"
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"
    STALE = "stale"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class MeasuredValue(Generic[ValueT]):
    """A normalized value with explicit validity and optional observation time."""

    value: ValueT | None
    validity: ValueValidity
    observed_at: datetime | None = None

    @property
    def valid(self) -> bool:
        """Return whether the value is usable by core calculations."""

        return self.validity is ValueValidity.VALID and self.value is not None

    @classmethod
    def available(
        cls,
        value: ValueT,
        *,
        observed_at: datetime | None = None,
    ) -> MeasuredValue[ValueT]:
        """Construct a valid normalized measurement."""

        return cls(value=value, validity=ValueValidity.VALID, observed_at=observed_at)

    @classmethod
    def absent(
        cls,
        validity: ValueValidity,
        *,
        observed_at: datetime | None = None,
    ) -> MeasuredValue[ValueT]:
        """Construct a measurement without inventing a fallback value."""

        if validity is ValueValidity.VALID:
            raise ValueError("an absent measurement cannot be valid")
        return cls(value=None, validity=validity, observed_at=observed_at)


@dataclass(frozen=True, slots=True)
class BatteryState:
    """Normalized battery measurements; limits remain configuration."""

    soc_pct: MeasuredValue[float]
    charge_power_w: MeasuredValue[float]
    discharge_power_w: MeasuredValue[float]


@dataclass(frozen=True, slots=True)
class GridState:
    """Normalized grid flow using positive import and positive export values."""

    import_power_w: MeasuredValue[float]
    export_power_w: MeasuredValue[float]


@dataclass(frozen=True, slots=True)
class PVState:
    """Normalized PV production and house-load measurements."""

    production_power_w: MeasuredValue[float]
    house_load_power_w: MeasuredValue[float]


@dataclass(frozen=True, slots=True)
class OffGridState:
    """Optional off-grid socket measurements without HA entity information."""

    active: MeasuredValue[bool]
    output_power_w: MeasuredValue[float]


@dataclass(frozen=True, slots=True)
class AdditionalBatteryState:
    """Optional external battery flows normalized to positive magnitudes."""

    charge_power_w: MeasuredValue[float]
    discharge_power_w: MeasuredValue[float]
