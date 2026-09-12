"""Regression coverage for stable SF800Pro PV passthrough."""

from __future__ import annotations

import unittest

from support import bootstrap

bootstrap()

from custom_components.battery_smartflow_ai.automatic_strategy import (  # noqa: E402
    forecast_blocks_pv_passthrough_start,
)


class PassthroughForecastHysteresisTests(unittest.TestCase):
    def test_active_passthrough_survives_forecast_start_threshold(self):
        self.assertFalse(
            forecast_blocks_pv_passthrough_start(
                mppt_clips_without_output=True,
                already_active=True,
                battery_near_full=False,
                forecast_surplus_expected=False,
            )
        )

    def test_forecast_threshold_still_blocks_new_passthrough(self):
        self.assertTrue(
            forecast_blocks_pv_passthrough_start(
                mppt_clips_without_output=True,
                already_active=False,
                battery_near_full=False,
                forecast_surplus_expected=False,
            )
        )

    def test_near_full_passthrough_is_not_blocked_by_forecast(self):
        self.assertFalse(
            forecast_blocks_pv_passthrough_start(
                mppt_clips_without_output=True,
                already_active=False,
                battery_near_full=True,
                forecast_surplus_expected=False,
            )
        )


if __name__ == "__main__":
    unittest.main()
