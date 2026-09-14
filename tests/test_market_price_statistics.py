"""Tests for local calendar-day market price statistics."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
import unittest

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.market_price import (  # noqa: E402
    MarketPricePoint,
    daily_price_statistics,
)


class MarketPriceStatisticsTests(unittest.TestCase):
    def test_statistics_use_local_day_and_weight_interval_duration(self) -> None:
        berlin = timezone(timedelta(hours=2), name="Europe/Berlin summer")
        now = datetime(2026, 9, 14, 12, tzinfo=berlin)
        points = [
        MarketPricePoint(
            start=datetime(2026, 9, 13, 22, tzinfo=UTC),
            end=datetime(2026, 9, 13, 23, tzinfo=UTC),
            price=0.10,
        ),
        MarketPricePoint(
            start=datetime(2026, 9, 13, 23, tzinfo=UTC),
            end=datetime(2026, 9, 14, 1, tzinfo=UTC),
            price=0.40,
        ),
        MarketPricePoint(
            start=datetime(2026, 9, 14, 22, tzinfo=UTC),
            end=datetime(2026, 9, 14, 23, tzinfo=UTC),
            price=9.99,
        ),
        ]

        result = daily_price_statistics(points, now_local=now)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertAlmostEqual(result.average, 0.30)
        self.assertEqual(result.minimum, 0.10)
        self.assertEqual(result.maximum, 0.40)

    def test_statistics_return_none_without_current_day_intervals(self) -> None:
        berlin = timezone(timedelta(hours=2), name="Europe/Berlin summer")
        now = datetime(2026, 9, 14, 12, tzinfo=berlin)
        tomorrow = MarketPricePoint(
            start=datetime(2026, 9, 14, 22, tzinfo=UTC),
            end=datetime(2026, 9, 14, 23, tzinfo=UTC),
            price=0.20,
        )

        self.assertIsNone(daily_price_statistics([tomorrow], now_local=now))


if __name__ == "__main__":
    unittest.main()
