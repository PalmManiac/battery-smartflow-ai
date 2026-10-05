from __future__ import annotations

import unittest

from custom_components.battery_smartflow_ai.regulation_shadow_evaluator import (
    evaluate_training_session,
)


class RegulationShadowEvaluatorTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
