"""Canonical market price models shared by import and export prices.

The models in this module deliberately contain no Home Assistant or provider
knowledge. Price sources and adapters are responsible for normalizing their
input before constructing these immutable values.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class MarketPriceDirection(StrEnum):
    """Direction in which energy crosses the grid connection."""

    IMPORT = "import"
    EXPORT = "export"


class MarketPriceValidity(StrEnum):
    """Normalized reason why a market price is or is not usable."""

    VALID = "valid"
    MISSING = "missing"
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"
    STALE = "stale"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class MarketPricePoint:
    """One normalized market price interval in active currency per kWh."""

    start: datetime
    end: datetime
    price: float


@dataclass(frozen=True, slots=True)
class MarketPriceForecast:
    """Optional normalized price intervals supplied by one market source."""

    points: tuple[MarketPricePoint, ...]
    timestamp: datetime | None = None

    @classmethod
    def empty(cls, *, timestamp: datetime | None = None) -> MarketPriceForecast:
        """Return an explicit empty forecast without inventing price data."""

        return cls(points=(), timestamp=timestamp)


@dataclass(frozen=True, slots=True)
class MarketPrice:
    """Current import or export price and its optional normalized forecast.

    ``current_price`` is expressed in ``unit`` and may legitimately be zero or
    negative. Missing and unavailable values remain ``None`` and are described
    by ``validity``; they are never replaced with a synthetic zero price.
    """

    direction: MarketPriceDirection
    current_price: float | None
    currency: str
    unit: str
    timestamp: datetime | None
    source: str
    validity: MarketPriceValidity
    is_dynamic: bool
    is_fallback: bool
    forecast: MarketPriceForecast | None = None

    @property
    def valid(self) -> bool:
        """Return whether a real current price is available for calculations."""

        return (
            self.validity is MarketPriceValidity.VALID
            and self.current_price is not None
        )
