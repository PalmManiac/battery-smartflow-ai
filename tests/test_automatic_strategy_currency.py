"""Currency scaling tests for automatic strategy price weighting."""

from __future__ import annotations

import unittest

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.automatic_strategy import (  # noqa: E402
    AutomaticStrategy,
)


class AutomaticStrategyCurrencyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.strategy = AutomaticStrategy()

    def test_price_range_weight_is_scale_invariant(self) -> None:
        eur = self.strategy._price_weight(
            price_now=0.45,
            price_min=0.15,
            price_max=0.50,
            price_average=0.30,
        )
        scaled = self.strategy._price_weight(
            price_now=4.5,
            price_min=1.5,
            price_max=5.0,
            price_average=3.0,
        )
        self.assertAlmostEqual(eur[0], scaled[0])
        self.assertEqual(eur[1], scaled[1])

    def test_missing_range_weight_is_scale_invariant(self) -> None:
        eur = self.strategy._price_weight(
            price_now=0.40,
            price_min=None,
            price_max=None,
            price_average=0.30,
        )
        scaled = self.strategy._price_weight(
            price_now=4.0,
            price_min=None,
            price_max=None,
            price_average=3.0,
        )
        self.assertAlmostEqual(eur[0], scaled[0])
        self.assertEqual(eur[1], scaled[1])

    def test_negative_prices_are_compared_relatively(self) -> None:
        weight, reason = self.strategy._price_weight(
            price_now=-0.05,
            price_min=None,
            price_max=None,
            price_average=-0.10,
        )
        self.assertGreater(weight, 0.30)
        self.assertEqual(reason, "price_deviation_from_average")


if __name__ == "__main__":
    unittest.main()
