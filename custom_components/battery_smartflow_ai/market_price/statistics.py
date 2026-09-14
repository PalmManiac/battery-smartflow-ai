"""Calendar-day statistics for normalized market-price intervals."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from math import isfinite
from typing import Iterable

from .models import MarketPricePoint


@dataclass(frozen=True, slots=True)
class DailyPriceStatistics:
    """Duration-weighted statistics for one local calendar day."""

    average: float
    minimum: float
    maximum: float


def daily_price_statistics(
    points: Iterable[MarketPricePoint],
    *,
    now_local: datetime,
) -> DailyPriceStatistics | None:
    """Calculate statistics only from intervals overlapping the local day."""

    if now_local.tzinfo is None or now_local.utcoffset() is None:
        raise ValueError("now_local must be timezone-aware")

    day_start = datetime.combine(now_local.date(), time.min, tzinfo=now_local.tzinfo)
    day_end = day_start + timedelta(days=1)
    weighted_total = 0.0
    total_seconds = 0.0
    prices: list[float] = []

    for point in points:
        if point.start.tzinfo is None or point.end.tzinfo is None:
            continue
        overlap_start = max(point.start, day_start)
        overlap_end = min(point.end, day_end)
        seconds = (overlap_end - overlap_start).total_seconds()
        price = float(point.price)
        if seconds <= 0.0 or not isfinite(price):
            continue
        weighted_total += price * seconds
        total_seconds += seconds
        prices.append(price)

    if total_seconds <= 0.0:
        return None
    return DailyPriceStatistics(
        average=weighted_total / total_seconds,
        minimum=min(prices),
        maximum=max(prices),
    )
