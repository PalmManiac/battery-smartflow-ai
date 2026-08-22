"""Adapters from raw price sources to canonical market price values."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import math
import re
from typing import Mapping, Protocol

from .models import (
    MarketPrice,
    MarketPriceDirection,
    MarketPriceForecast,
    MarketPriceValidity,
)
from .sources import PriceSource, PriceSourceReading, PriceSourceStatus
from ..price_currency import normalize_currency_code


@dataclass(frozen=True, slots=True)
class NormalizedNumericPrice:
    """Validated value plus canonical active-currency unit metadata."""

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


_CURRENCY_ENERGY_UNIT = re.compile(r"^([A-Za-z]{3})/(kWh|MWh)$", re.IGNORECASE)
_EURO_SYMBOL_ENERGY_UNIT = re.compile(r"^€/(kWh|MWh)$", re.IGNORECASE)
_CENT_PER_KWH_UNITS = frozenset({"ct/kwh", "cent/kwh", "c/kwh"})
DEFAULT_CURRENT_PRICE_MAX_AGE = timedelta(hours=6)
MAX_FUTURE_TIMESTAMP_SKEW = timedelta(minutes=5)


def normalize_price_value(
    value: object,
    *,
    unit: object | None,
    currency: object | None,
    active_currency: str,
) -> NormalizedNumericPrice:
    """Normalize one finite price to active currency per kWh.

    Only energy-unit scaling is performed. A different currency is rejected;
    this function never applies an exchange rate.
    """

    active_code = normalize_currency_code(active_currency)
    source_code = (
        normalize_currency_code(currency) if currency is not None else None
    )
    canonical_unit = f"{active_code or str(active_currency).upper()}/kWh"

    if active_code is None or (currency is not None and source_code is None):
        return NormalizedNumericPrice(
            value=None,
            currency=active_code or str(active_currency).upper(),
            unit=canonical_unit,
            validity=MarketPriceValidity.INVALID,
        )
    if source_code is not None and source_code != active_code:
        return NormalizedNumericPrice(
            value=None,
            currency=source_code,
            unit=canonical_unit,
            validity=MarketPriceValidity.INVALID,
        )

    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        numeric_value = None
    if numeric_value is None or not math.isfinite(numeric_value):
        return NormalizedNumericPrice(
            value=None,
            currency=source_code or active_code,
            unit=canonical_unit,
            validity=MarketPriceValidity.INVALID,
        )

    raw_unit = str(unit).strip() if unit is not None else ""
    compact_unit = raw_unit.replace(" ", "")
    divisor = 1.0
    unit_currency = None

    if not compact_unit:
        pass  # V4.5 compatibility: an unlabelled value is already per kWh.
    elif compact_unit.lower() in _CENT_PER_KWH_UNITS:
        divisor = 100.0
    else:
        euro_match = _EURO_SYMBOL_ENERGY_UNIT.fullmatch(compact_unit)
        currency_match = _CURRENCY_ENERGY_UNIT.fullmatch(compact_unit)
        if euro_match is not None:
            unit_currency = "EUR"
            energy_unit = euro_match.group(1)
        elif currency_match is not None:
            unit_currency = normalize_currency_code(currency_match.group(1))
            energy_unit = currency_match.group(2)
        else:
            return NormalizedNumericPrice(
                value=None,
                currency=source_code or active_code,
                unit=canonical_unit,
                validity=MarketPriceValidity.INVALID,
            )
        if unit_currency != active_code:
            return NormalizedNumericPrice(
                value=None,
                currency=unit_currency or active_code,
                unit=canonical_unit,
                validity=MarketPriceValidity.INVALID,
            )
        divisor = 1000.0 if energy_unit.lower() == "mwh" else 1.0

    if source_code is not None and unit_currency is not None:
        if source_code != unit_currency:
            return NormalizedNumericPrice(
                value=None,
                currency=source_code,
                unit=canonical_unit,
                validity=MarketPriceValidity.INVALID,
            )

    return NormalizedNumericPrice(
        value=numeric_value / divisor,
        currency=active_code,
        unit=canonical_unit,
        validity=MarketPriceValidity.VALID,
    )


@dataclass(frozen=True, slots=True)
class NumericPriceNormalizer:
    """Validate currency, unit, value and optional current-price freshness."""

    now: datetime | None = None
    max_age: timedelta = DEFAULT_CURRENT_PRICE_MAX_AGE

    def normalize(
        self,
        reading: PriceSourceReading,
        *,
        active_currency: str,
    ) -> NormalizedNumericPrice:
        """Parse a finite number and preserve zero and negative prices."""

        active_code = normalize_currency_code(active_currency) or str(
            active_currency
        ).strip().upper()
        canonical_unit = f"{active_code}/kWh"

        if reading.status is not PriceSourceStatus.AVAILABLE:
            return NormalizedNumericPrice(
                value=None,
                currency=active_code,
                unit=canonical_unit,
                validity=_SOURCE_VALIDITY.get(
                    reading.status,
                    MarketPriceValidity.INVALID,
                ),
            )

        if self.now is not None and reading.is_dynamic:
            timestamp = reading.timestamp
            if (
                timestamp is None
                or timestamp.tzinfo is None
                or self.now.tzinfo is None
            ):
                return NormalizedNumericPrice(
                    value=None,
                    currency=active_code,
                    unit=canonical_unit,
                    validity=MarketPriceValidity.INVALID,
                )
            if timestamp < self.now - self.max_age:
                return NormalizedNumericPrice(
                    value=None,
                    currency=active_code,
                    unit=canonical_unit,
                    validity=MarketPriceValidity.STALE,
                )
            if timestamp > self.now + MAX_FUTURE_TIMESTAMP_SKEW:
                return NormalizedNumericPrice(
                    value=None,
                    currency=active_code,
                    unit=canonical_unit,
                    validity=MarketPriceValidity.INVALID,
                )

        return normalize_price_value(
            reading.value,
            unit=reading.unit,
            currency=reading.currency,
            active_currency=active_code,
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
