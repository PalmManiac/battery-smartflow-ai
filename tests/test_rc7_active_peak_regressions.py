"""RC7 regressions from Beat's RC6 active-peak trace in Discussion #123."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.learned_planning import (  # noqa: E402
    DEADLINE_REASON_BEFORE_PEAK_WINDOW,
    choose_deadline,
)
from custom_components.battery_smartflow_ai.market_price import (  # noqa: E402
    MarketPricePoint,
)


class Rc7ActivePeakRegressionTests(unittest.TestCase):
    def test_active_peak_is_not_reintroduced_as_next_slot_deadline(self) -> None:
        """10:55 inside one high-price block must not target 11:00 again."""

        now = datetime(2026, 8, 26, 10, 55, tzinfo=timezone.utc)
        start = datetime(2026, 8, 26, 10, 45, tzinfo=timezone.utc)
        prices = [
            MarketPricePoint(
                start=start + timedelta(minutes=15 * index),
                end=start + timedelta(minutes=15 * (index + 1)),
                price=price,
            )
            for index, price in enumerate(
                (0.388,) * 4
                + (0.238,) * 20
                + (0.500,) * 2
            )
        ]

        deadline, reason = choose_deadline(
            now=now,
            price_points=prices,
            forecast=None,
        )

        self.assertEqual(reason, DEADLINE_REASON_BEFORE_PEAK_WINDOW)
        self.assertEqual(
            deadline,
            datetime(2026, 8, 26, 16, 45, tzinfo=timezone.utc),
        )

    def test_future_peak_remains_a_valid_deadline(self) -> None:
        """The fix must preserve normal preparation for an upcoming peak."""

        now = datetime(2026, 8, 26, 10, 55, tzinfo=timezone.utc)
        start = datetime(2026, 8, 26, 10, 45, tzinfo=timezone.utc)
        prices = [
            MarketPricePoint(
                start=start + timedelta(minutes=15 * index),
                end=start + timedelta(minutes=15 * (index + 1)),
                price=price,
            )
            for index, price in enumerate(
                (0.238, 0.238, 0.238, 0.238, 0.450, 0.450)
            )
        ]

        deadline, reason = choose_deadline(
            now=now,
            price_points=prices,
            forecast=None,
        )

        self.assertEqual(reason, DEADLINE_REASON_BEFORE_PEAK_WINDOW)
        self.assertEqual(
            deadline,
            datetime(2026, 8, 26, 11, 45, tzinfo=timezone.utc),
        )


if __name__ == "__main__":
    unittest.main()
