"""Regression tests for SoC-driven automatic peak-reserve chatter."""

from __future__ import annotations

import unittest

from support import bootstrap

bootstrap()

from custom_components.battery_smartflow_ai.automatic_strategy import AutomaticStrategy


class AutomaticPeakReserveHysteresisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.strategy = AutomaticStrategy()

    def _weak_pv_permission(self, reserve_weight: float) -> tuple[bool, str]:
        return self.strategy._automatic_peak_reserve_permission(
            pv_weight=0.0,
            pv_reason="no_current_pv",
            reserve_weight=reserve_weight,
            reserve_reason="reserve_normal",
            forecast_weight=0.65,
            forecast_reason="mixed_pv_outlook",
        )

    def _mixed_forecast_permission(
        self, reserve_weight: float,
    ) -> tuple[bool, str]:
        return self.strategy._automatic_peak_reserve_permission(
            pv_weight=0.50,
            pv_reason="pv_covers_house_load",
            reserve_weight=reserve_weight,
            reserve_reason="reserve_normal",
            forecast_weight=0.65,
            forecast_reason="mixed_pv_outlook",
        )

    def test_one_point_soc_fluctuation_does_not_reenable_peak_reserve(self):
        # The supplied logs oscillated across the old 0.35 cutoff (.356/.344).
        self.assertEqual(
            self._weak_pv_permission(0.356),
            (False, "peak_reserve_context_not_required"),
        )
        self.assertEqual(
            self._weak_pv_permission(0.344),
            (False, "peak_reserve_context_not_required"),
        )
        self.assertEqual(
            self._weak_pv_permission(0.356),
            (False, "peak_reserve_context_not_required"),
        )

    def test_weak_pv_permission_uses_separate_entry_and_exit_thresholds(self):
        self.assertTrue(self._weak_pv_permission(0.37)[0])
        # Once enabled, it tolerates small SoC changes until the old 0.35 exit.
        self.assertTrue(self._weak_pv_permission(0.356)[0])
        self.assertFalse(self._weak_pv_permission(0.344)[0])
        # After exit, the old 0.356 reading cannot immediately re-arm it.
        self.assertFalse(self._weak_pv_permission(0.356)[0])
        self.assertTrue(self._weak_pv_permission(0.37)[0])

    def test_mixed_forecast_permission_also_has_hysteresis(self):
        # Exclude the weak-PV branch and exercise its mixed-forecast fallback.
        self.assertFalse(self._mixed_forecast_permission(0.46)[0])
        self.assertTrue(self._mixed_forecast_permission(0.47)[0])
        self.assertTrue(self._mixed_forecast_permission(0.451)[0])
        self.assertFalse(self._mixed_forecast_permission(0.449)[0])
        self.assertFalse(self._mixed_forecast_permission(0.46)[0])

    def test_inactive_automatic_mode_resets_hysteresis(self):
        self.assertTrue(self._weak_pv_permission(0.37)[0])
        self.strategy.evaluate(automatic_mode_active=False)
        self.assertFalse(self._weak_pv_permission(0.356)[0])


if __name__ == "__main__":
    unittest.main()
