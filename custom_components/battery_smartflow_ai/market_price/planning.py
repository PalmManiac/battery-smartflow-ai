"""Provider-independent market-price views for fixed-slot planning."""

from __future__ import annotations

from datetime import timedelta

from .models import MarketPrice, MarketPriceDirection, MarketPricePoint


PLANNING_SLOT_DURATION = timedelta(minutes=15)


def planning_price_points(market_price: MarketPrice | None) -> list[MarketPricePoint]:
    """Return canonical import prices as complete 15-minute planning slots.

    Native 15-minute points remain unchanged. Longer intervals are split while
    retaining their normalized price. Gaps are not filled, and incomplete
    trailing fragments are excluded because the existing planners account for
    every returned point as exactly one quarter hour of energy.
    """

    if (
        market_price is None
        or market_price.direction is not MarketPriceDirection.IMPORT
        or market_price.forecast is None
    ):
        return []

    slots: list[MarketPricePoint] = []
    seen: set[tuple] = set()
    for point in sorted(market_price.forecast.points, key=lambda item: item.start):
        cursor = point.start
        while cursor + PLANNING_SLOT_DURATION <= point.end:
            slot_end = cursor + PLANNING_SLOT_DURATION
            interval = (cursor, slot_end)
            if interval not in seen:
                slots.append(
                    MarketPricePoint(
                        start=cursor,
                        end=slot_end,
                        price=float(point.price),
                    )
                )
                seen.add(interval)
            cursor = slot_end
    return slots
