from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from custom_components.battery_smartflow_ai.regulation_shadow_evaluator import (
    evaluate_training_session,
)


class RegulationShadowEvaluatorTests(unittest.TestCase):
    @staticmethod
    def _reversal_samples(*, override_at_reversal: bool = False) -> list[dict]:
        started = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
        samples = []
        for index in range(45):
            direction = "charge" if index < 5 else "discharge"
            sample = {
                "timestamp": (started + timedelta(seconds=index)).isoformat(),
                "direction": direction,
                "ai_mode": "automatic",
                "manual_action": "standby",
                "strategy_intent": "cover_deficit" if direction == "discharge" else "pv_charge",
                "strategy_force": False,
                "strategy_priority": 400,
                "mode_allowed": True,
                "discharge_allowed": True,
                "grid_valid": True,
                "command_skipped": False,
                "requested_charge_w": 100.0 if direction == "charge" else 0.0,
                "requested_discharge_w": 100.0 if direction == "discharge" else 0.0,
            }
            if override_at_reversal and index == 5:
                sample["manual_action"] = "discharge"
            samples.append(sample)
        return samples

    @staticmethod
    def _samples(*, kp_up: float = 0.5, kp_down: float = 0.5) -> list[dict]:
        samples = []
        for index in range(60):
            requested = 500.0 if (index // 6) % 2 == 0 else 600.0
            samples.append(
                {
                    "direction": "charge",
                    "grid_valid": True,
                    "command_skipped": False,
                    "grid_error_w": 500.0,
                    "requested_charge_w": requested,
                    "requested_discharge_w": 0.0,
                    "observed_charge_w": 250.0,
                    "observed_discharge_w": 0.0,
                    "baseline_kp_up": kp_up,
                    "baseline_kp_down": kp_down,
                    "baseline_max_step_up_w": 1000.0,
                    "baseline_max_step_down_w": 1000.0,
                }
            )
        return samples

    def test_proposes_a_shadow_only_candidate_when_replay_improves(self) -> None:
        result = evaluate_training_session({"samples": self._samples()})

        self.assertEqual(result["status"], "candidate_proposed")
        self.assertEqual(result["state"], "proposed")
        self.assertFalse(result["live_parameters_changed"])
        self.assertGreaterEqual(result["charge"]["relative_improvement"], 0.03)
        self.assertEqual(result["charge"]["parameters"]["kp_up"], 0.6)
        self.assertIsNone(result["charge"]["parameters"]["kp_down"])
        self.assertEqual(result["discharge"]["decision"], "insufficient_data")

    def test_rejects_a_candidate_without_measurable_improvement(self) -> None:
        result = evaluate_training_session(
            {"samples": self._samples(kp_up=0.0, kp_down=0.0)}
        )

        self.assertEqual(result["status"], "no_improvement")
        self.assertEqual(result["charge"]["decision"], "rejected")
        self.assertEqual(result["state"], "shadow")
        self.assertFalse(result["live_parameters_changed"])

    def test_requires_sample_and_response_event_coverage(self) -> None:
        result = evaluate_training_session({"samples": self._samples()[:20]})

        self.assertEqual(result["status"], "insufficient_data")
        self.assertEqual(result["charge"]["decision"], "insufficient_data")
        self.assertIsNone(result["charge"]["candidate_score"])

    def test_reversal_hold_is_simulated_without_changing_live_regulation(self) -> None:
        result = evaluate_training_session(
            {"samples": self._reversal_samples()}
        )["reversal_hysteresis"]

        self.assertEqual(result["status"], "simulated")
        self.assertEqual(result["threshold_watt_seconds"], 3000)
        self.assertEqual(result["eligible_reversal_count"], 1)
        self.assertEqual(result["held_reversal_count"], 1)
        self.assertEqual(result["released_reversal_count"], 1)
        self.assertAlmostEqual(result["estimated_hold_seconds"], 30)
        self.assertAlmostEqual(result["estimated_withheld_energy_wh"], 0.833)
        self.assertFalse(result["live_parameters_changed"])

    def test_manual_reversal_is_counted_as_override_not_delayed(self) -> None:
        result = evaluate_training_session(
            {"samples": self._reversal_samples(override_at_reversal=True)}
        )["reversal_hysteresis"]

        self.assertEqual(result["override_reversal_count"], 1)
        self.assertEqual(result["eligible_reversal_count"], 0)
        self.assertEqual(result["held_reversal_count"], 0)


if __name__ == "__main__":
    unittest.main()
