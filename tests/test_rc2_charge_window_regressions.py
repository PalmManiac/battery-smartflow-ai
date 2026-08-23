"""RC2 regressions for learned AC charge planning and status display."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.const import (  # noqa: E402
    AI_MODE_AUTOMATIC,
    AI_STATUS_PRICE_CHARGE,
)
from custom_components.battery_smartflow_ai.ai_status import (  # noqa: E402
    map_ai_status,
)
from custom_components.battery_smartflow_ai.learned_planning import (  # noqa: E402
    optimize_charge_window,
)
from custom_components.battery_smartflow_ai.market_price import (  # noqa: E402
    MarketPricePoint,
)


class Rc2ChargeWindowRegressionTests(unittest.TestCase):
    def test_equal_price_overnight_window_keeps_end_reserve(self) -> None:
        start = datetime(2026, 8, 23, 23, 0, tzinfo=timezone.utc)
        deadline = start + timedelta(hours=7)
        points = [
            MarketPricePoint(
                start=start + timedelta(minutes=15 * index),
                end=start + timedelta(minutes=15 * (index + 1)),
                price=0.10,
            )
            for index in range(28)
        ]

        selected_start, selected_end, *_ = optimize_charge_window(
            now=start,
            deadline=deadline,
            price_points=points,
            window_slots=20,
        )

        self.assertEqual(selected_start, start + timedelta(hours=1))
        self.assertEqual(selected_end, deadline - timedelta(hours=1))

    def test_lower_price_still_beats_timing_reserve(self) -> None:
        start = datetime(2026, 8, 23, 23, 0, tzinfo=timezone.utc)
        points = [
            MarketPricePoint(
                start=start + timedelta(minutes=15 * index),
                end=start + timedelta(minutes=15 * (index + 1)),
                price=0.20 if index < 4 else 0.10,
            )
            for index in range(12)
        ]

        selected_start, selected_end, *_ = optimize_charge_window(
            now=start,
            deadline=start + timedelta(hours=3),
            price_points=points,
            window_slots=8,
        )

        self.assertEqual(selected_start, start + timedelta(hours=1))
        self.assertEqual(selected_end, start + timedelta(hours=3))

    def test_learned_ac_charge_is_shown_as_price_charge(self) -> None:
        status = map_ai_status(
            AI_MODE_AUTOMATIC,
            "charge",
            "learned_charge_window_active",
        )

        self.assertEqual(status, AI_STATUS_PRICE_CHARGE)


if __name__ == "__main__":
    unittest.main()
