"""Selection of dynamic and static export market price sources."""

from __future__ import annotations

from dataclasses import dataclass

from .adapters import MarketPriceSourceAdapter, NumericPriceNormalizer
from .models import MarketPrice, MarketPriceDirection, MarketPriceValidity
from .sources import (
    GenericStatePriceSource,
    PriceSource,
    StateGetter,
    StaticPriceSource,
)


@dataclass(frozen=True, slots=True)
class ExportMarketPriceResolver:
    """Resolve the current export price using the documented fallback order."""

    state_getter: StateGetter
    active_currency: str
    dynamic_entity_id: str | None = None
    static_value: object | None = None
    static_configured: bool = False

    def resolve(self) -> MarketPrice:
        """Prefer a valid dynamic sensor, then the configured static tariff."""

        if self.dynamic_entity_id:
            dynamic_price = self._adapt(
                GenericStatePriceSource(
                    entity_id=self.dynamic_entity_id,
                    state_getter=self.state_getter,
                )
            )
            if dynamic_price.valid:
                return dynamic_price

        if self.static_configured:
            static_price = self._adapt(
                StaticPriceSource(
                    value=self.static_value,
                    currency=self.active_currency,
                    unit=f"{self.active_currency}/kWh",
                    source="config.feed_in_tariff",
                    is_fallback=bool(self.dynamic_entity_id),
                )
            )
            if static_price.valid:
                return static_price

        return MarketPrice(
            direction=MarketPriceDirection.EXPORT,
            current_price=None,
            currency=self.active_currency,
            unit=f"{self.active_currency}/kWh",
            timestamp=None,
            source="not_configured",
            validity=MarketPriceValidity.MISSING,
            is_dynamic=False,
            is_fallback=False,
        )

    def _adapt(self, source: PriceSource) -> MarketPrice:
        return MarketPriceSourceAdapter(
            source=source,
            normalizer=NumericPriceNormalizer(),
            direction=MarketPriceDirection.EXPORT,
            active_currency=self.active_currency,
        ).read()
