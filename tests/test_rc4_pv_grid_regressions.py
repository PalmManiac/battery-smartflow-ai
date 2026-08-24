"""RC4 regressions from the SF800Pro trace in Discussion #123."""

from __future__ import annotations

import unittest

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.automatic_strategy import (  # noqa: E402
    AutomaticStrategy,
    forecast_supports_early_pv_passthrough,
)


class Rc4PvGridRegressionTests(unittest.TestCase):
    def test_real_grid_import_overrides_dc_pv_cover_assumption(self) -> None:
        allowed, reason = AutomaticStrategy()._automatic_discharge_permission(
            price_weight=1.0,
            price_reason="very_expensive_price_range",
            reserve_weight=0.4,
            reserve_reason="reserve_normal",
            pv_weight=0.95,
            pv_reason="pv_covers_house_load",
            grid_import_w=842.0,
        )

        self.assertTrue(allowed)
        self.assertEqual(reason, "economic_discharge_context_allowed")

    def test_small_grid_import_still_allows_pv_discharge_block(self) -> None:
        allowed, reason = AutomaticStrategy()._automatic_discharge_permission(
            price_weight=1.0,
            price_reason="very_expensive_price_range",
            reserve_weight=0.4,
            reserve_reason="reserve_normal",
            pv_weight=0.95,
            pv_reason="pv_covers_house_load",
            grid_import_w=40.0,
        )

        self.assertFalse(allowed)
        self.assertEqual(reason, "pv_covers_load_blocks_discharge")

    def test_good_forecast_exceeding_headroom_enables_early_passthrough(self) -> None:
        self.assertTrue(
            forecast_supports_early_pv_passthrough(
                forecast_status="available",
                pv_outlook="good",
                remaining_today_kwh=2.433,
                battery_capacity_kwh=3.84,
                soc=63.0,
                soc_max=100.0,
            )
        )

    def test_forecast_inside_headroom_keeps_battery_priority(self) -> None:
        self.assertFalse(
            forecast_supports_early_pv_passthrough(
                forecast_status="available",
                pv_outlook="good",
                remaining_today_kwh=1.2,
                battery_capacity_kwh=3.84,
                soc=63.0,
                soc_max=100.0,
            )
        )


if __name__ == "__main__":
    unittest.main()
