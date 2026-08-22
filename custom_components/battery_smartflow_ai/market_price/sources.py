"""Provider-independent acquisition of raw market price source values."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Callable, Mapping, Protocol


class PriceSourceStatus(StrEnum):
    """Availability reported by a raw price source."""

    AVAILABLE = "available"
    MISSING = "missing"
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class PriceSourceReading:
    """Raw value and metadata read from one configured price source."""

    value: object | None
    unit: str | None
    currency: str | None
    timestamp: datetime | None
    source: str
    status: PriceSourceStatus
    is_dynamic: bool
    is_fallback: bool = False


class PriceSource(Protocol):
    """Common acquisition interface for static and dynamic price sources."""

    def read(self) -> PriceSourceReading:
        """Read one raw value without applying price normalization."""


class StateLike(Protocol):
    """Minimal Home Assistant state shape used by the generic source."""

    state: object
    attributes: Mapping[str, Any]
    last_updated: datetime


StateGetter = Callable[[str], StateLike | None]


@dataclass(frozen=True, slots=True)
class GenericStatePriceSource:
    """Read a price from the state of any configured Home Assistant sensor."""

    entity_id: str
    state_getter: StateGetter

    def read(self) -> PriceSourceReading:
        """Return the sensor state and metadata without interpreting its unit."""

        state = self.state_getter(self.entity_id)
        if state is None:
            return PriceSourceReading(
                value=None,
                unit=None,
                currency=None,
                timestamp=None,
                source=self.entity_id,
                status=PriceSourceStatus.MISSING,
                is_dynamic=True,
            )

        raw_value = state.state
        state_text = str(raw_value).strip().lower()
        if state_text == PriceSourceStatus.UNKNOWN:
            status = PriceSourceStatus.UNKNOWN
            raw_value = None
        elif state_text == PriceSourceStatus.UNAVAILABLE:
            status = PriceSourceStatus.UNAVAILABLE
            raw_value = None
        else:
            status = PriceSourceStatus.AVAILABLE

        attributes = state.attributes or {}
        raw_unit = attributes.get("unit_of_measurement")
        raw_currency = attributes.get("currency")

        return PriceSourceReading(
            value=raw_value,
            unit=str(raw_unit).strip() if raw_unit is not None else None,
            currency=(
                str(raw_currency).strip().upper()
                if raw_currency is not None
                else None
            ),
            timestamp=getattr(state, "last_updated", None),
            source=self.entity_id,
            status=status,
            is_dynamic=True,
        )


@dataclass(frozen=True, slots=True)
class StaticPriceSource:
    """Expose one configured static price through the common source contract."""

    value: object
    currency: str
    unit: str
    source: str
    is_fallback: bool = False

    def read(self) -> PriceSourceReading:
        """Return the configured value without converting or validating it."""

        return PriceSourceReading(
            value=self.value,
            unit=self.unit,
            currency=self.currency,
            timestamp=None,
            source=self.source,
            status=PriceSourceStatus.AVAILABLE,
            is_dynamic=False,
            is_fallback=self.is_fallback,
        )
