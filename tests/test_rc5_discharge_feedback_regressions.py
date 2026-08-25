"""RC5 regressions from the SF800Pro RC4 trace in Discussion #123."""

from __future__ import annotations

import unittest

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.automatic_strategy import (  # noqa: E402
    AutomaticStrategy,
    maintain_active_economic_discharge,
)


class Rc5DischargeFeedbackRegressionTests(unittest.TestCase):
    def test_active_discharge_survives_its_own_grid_import_reduction(self) -> None:
        strategy = AutomaticStrategy()

        started, _ = strategy._automatic_discharge_permission(
            price_weight=1.0,
            price_reason="very_expensive_price_range",
            reserve_weight=0.4,
            reserve_reason="reserve_normal",
            pv_weight=0.95,
            pv_reason="pv_covers_house_load",
            grid_import_w=620.0,
        )
        reduced_import_allowed, reduced_import_reason = (
            strategy._automatic_discharge_permission(
                price_weight=1.0,
                price_reason="very_expensive_price_range",
                reserve_weight=0.4,
                reserve_reason="reserve_normal",
                pv_weight=0.95,
                pv_reason="pv_covers_house_load",
                grid_import_w=88.0,
            )
        )

        self.assertTrue(started)
        self.assertFalse(reduced_import_allowed)
        self.assertEqual(
            reduced_import_reason,
            "pv_covers_load_blocks_discharge",
        )
        self.assertTrue(
            maintain_active_economic_discharge(
                automatic_mode_active=True,
                strategy_active=True,
                strategy_allows_discharge=reduced_import_allowed,
                effective_price_reached=True,
                previous_regulation_state="discharge_active",
                active_output_w=531.0,
            )
        )

    def test_dc_charge_measurement_does_not_hide_commanded_ac_output(self) -> None:
        measured_battery_discharge_w = 0.0
        last_commanded_output_w = 507.0

        active_output_w = max(
            measured_battery_discharge_w,
            last_commanded_output_w,
        )

        self.assertTrue(
            maintain_active_economic_discharge(
                automatic_mode_active=True,
                strategy_active=True,
                strategy_allows_discharge=False,
                effective_price_reached=True,
                previous_regulation_state="discharge_active",
                active_output_w=active_output_w,
            )
        )

    def test_passthrough_output_does_not_create_economic_discharge_hold(self) -> None:
        self.assertFalse(
            maintain_active_economic_discharge(
                automatic_mode_active=True,
                strategy_active=True,
                strategy_allows_discharge=False,
                effective_price_reached=True,
                previous_regulation_state="passthrough_active",
                active_output_w=789.0,
            )
        )

    def test_real_exit_conditions_disable_the_hold_context(self) -> None:
        common = {
            "automatic_mode_active": True,
            "strategy_active": True,
            "strategy_allows_discharge": False,
            "previous_regulation_state": "discharge_active",
            "active_output_w": 531.0,
        }

        self.assertFalse(
            maintain_active_economic_discharge(
                **common,
                effective_price_reached=False,
            )
        )
        self.assertFalse(
            maintain_active_economic_discharge(
                **{
                    **common,
                    "automatic_mode_active": False,
                    "effective_price_reached": True,
                }
            )
        )


if __name__ == "__main__":
    unittest.main()
