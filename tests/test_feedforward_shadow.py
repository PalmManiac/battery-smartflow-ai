from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from custom_components.battery_smartflow_ai.feedforward_shadow import (
    evaluate_feedforward_shadow,
)


class FeedforwardShadowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)

    def test_output_candidate_uses_fresh_measured_discharge(self) -> None:
        result = evaluate_feedforward_shadow(
            intent="cover_deficit",
            error_w=250.0,
            measured_battery_power_w=600.0,
            observed_at=self.now - timedelta(seconds=2),
            now=self.now,
            max_input_w=2400.0,
            max_output_w=1200.0,
        )

        self.assertTrue(result.available)
        self.assertEqual(result.candidate_power_w, 850.0)
        self.assertEqual(result.measurement_age_seconds, 2.0)

    def test_pv_charge_candidate_uses_charge_sign_and_hardware_limit(self) -> None:
        result = evaluate_feedforward_shadow(
            intent="pv_charge",
            error_w=500.0,
            measured_battery_power_w=-700.0,
            observed_at=self.now,
            now=self.now,
            max_input_w=1000.0,
            max_output_w=2400.0,
        )

        self.assertTrue(result.available)
        self.assertEqual(result.candidate_power_w, 1000.0)

    def test_stale_measurement_is_not_used_for_candidate(self) -> None:
        result = evaluate_feedforward_shadow(
            intent="cover_deficit",
            error_w=100.0,
            measured_battery_power_w=300.0,
            observed_at=self.now - timedelta(seconds=5.001),
            now=self.now,
            max_input_w=2400.0,
            max_output_w=2400.0,
        )

        self.assertFalse(result.available)
        self.assertEqual(result.reason, "native_battery_power_stale")
        self.assertIsNone(result.candidate_power_w)

    def test_unrelated_strategy_has_no_feedforward_candidate(self) -> None:
        result = evaluate_feedforward_shadow(
            intent="manual_charge",
            error_w=100.0,
            measured_battery_power_w=300.0,
            observed_at=self.now,
            now=self.now,
            max_input_w=2400.0,
            max_output_w=2400.0,
        )

        self.assertFalse(result.available)
        self.assertEqual(result.reason, "intent_not_regulated")


if __name__ == "__main__":
    unittest.main()
