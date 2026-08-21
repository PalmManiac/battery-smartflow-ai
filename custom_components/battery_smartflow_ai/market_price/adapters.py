"""Adapters from raw price sources to canonical market price values."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Protocol

from .models import (
    MarketPrice,
    MarketPriceDirection,
    MarketPriceForecast,
    MarketPriceValidity,
)
from .sources import PriceSource, PriceSourceReading, PriceSourceStatus


@dataclass(frozen=True, slots=True)
class NormalizedNumericPrice:
    """Finite numeric value plus metadata, without unit conversion."""

    value: float | None
    currency: str
    unit: str
    validity: MarketPriceValidity


class PriceNormalizer(Protocol):
    """Boundary between raw acquisition and canonical price construction."""

    def normalize(
        self,
        reading: PriceSourceReading,
        *,
        active_currency: str,
    ) -> NormalizedNumericPrice:
        """Normalize one raw source reading."""


class ForecastAdapter(Protocol):
    """Extension point for provider-specific forecast attribute structures."""

    @property
    def name(self) -> str:
        """Return a stable adapter name for diagnostics."""

    def supports(self, attributes: Mapping[str, object]) -> bool:
        """Return whether this adapter recognizes the supplied attributes."""

    def normalize(
        self,
        attributes: Mapping[str, object],
        *,
        direction: MarketPriceDirection,
        active_currency: str,
    ) -> MarketPriceForecast:
        """Return provider-independent points for one market direction."""


_SOURCE_VALIDITY = {
    PriceSourceStatus.MISSING: MarketPriceValidity.MISSING,
    PriceSourceStatus.UNKNOWN: MarketPriceValidity.UNKNOWN,
    PriceSourceStatus.UNAVAILABLE: MarketPriceValidity.UNAVAILABLE,
    PriceSourceStatus.INVALID: MarketPriceValidity.INVALID,
}


class NumericPriceNormalizer:
    """Normalize an already per-kWh numeric value without unit conversion.

    Unit conversion and currency consistency checks belong to issue #243. This
    normalizer establishes the source/normalizer boundary while preserving the
    V4.5 behavior for an ordinary numeric state sensor.
    """

    def normalize(
        self,
        reading: PriceSourceReading,
        *,
        active_currency: str,
    ) -> NormalizedNumericPrice:
        """Parse a finite number and preserve zero and negative prices."""

        currency = str(reading.currency or active_currency).strip().upper()
        unit = str(reading.unit or f"{currency}/kWh").strip()

        if reading.status is not PriceSourceStatus.AVAILABLE:
            return NormalizedNumericPrice(
                value=None,
                currency=currency,
                unit=unit,
                validity=_SOURCE_VALIDITY.get(
                    reading.status,
                    MarketPriceValidity.INVALID,
                ),
            )

        try:
            value = float(reading.value)
        except (TypeError, ValueError):
            value = None

        if value is None or not math.isfinite(value):
            return NormalizedNumericPrice(
                value=None,
                currency=currency,
                unit=unit,
                validity=MarketPriceValidity.INVALID,
            )

        return NormalizedNumericPrice(
            value=value,
            currency=currency,
            unit=unit,
            validity=MarketPriceValidity.VALID,
        )


@dataclass(frozen=True, slots=True)
class MarketPriceSourceAdapter:
    """Compose acquisition and normalization into one canonical market price."""

    source: PriceSource
    normalizer: PriceNormalizer
    direction: MarketPriceDirection
    active_currency: str

    def read(self) -> MarketPrice:
        """Read and normalize the configured source."""

        reading = self.source.read()
        normalized = self.normalizer.normalize(
            reading,
            active_currency=self.active_currency,
        )
        return MarketPrice(
            direction=self.direction,
            current_price=normalized.value,
            currency=normalized.currency,
            unit=normalized.unit,
            timestamp=reading.timestamp,
            source=reading.source,
            validity=normalized.validity,
            is_dynamic=reading.is_dynamic,
            is_fallback=reading.is_fallback,
        )
