"""Tests for currency-neutral price calculations."""

from __future__ import annotations

import unittest

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.price_math import (  # noqa: E402
    comparison_tolerance,
    peak_threshold,
)


class PriceMathTests(unittest.TestCase):
    def test_peak_threshold_scales_with_all_input_prices(self) -> None:
        eur_prices = [0.15, 0.30, 0.45]
        scaled_prices = [value * 10.0 for value in eur_prices]
        self.assertAlmostEqual(
            peak_threshold(scaled_prices, 1.35),
            peak_threshold(eur_prices, 1.35) * 10.0,
        )

    def test_peak_threshold_supports_negative_prices(self) -> None:
        threshold = peak_threshold([-0.20, -0.05, 0.10], 1.35)
        self.assertGreater(threshold, -0.05)
        self.assertLessEqual(threshold, 0.10)

    def test_market_spread_provides_separation_around_zero(self) -> None:
        self.assertGreater(peak_threshold([-1.0, 0.0, 1.0], 1.35), 0.0)

    def test_empty_price_series_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            peak_threshold([], 1.35)

    def test_comparison_tolerance_follows_price_step(self) -> None:
        self.assertEqual(comparison_tolerance(0.01), 0.005)
        self.assertEqual(comparison_tolerance(0.05), 0.025)
        self.assertEqual(comparison_tolerance(0.1), 0.05)


if __name__ == "__main__":
    unittest.main()
