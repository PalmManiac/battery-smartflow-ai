from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from custom_components.battery_smartflow_ai.regulation_shadow_evaluator import (
    evaluate_training_session,
)


class RegulationShadowEvaluatorTests(unittest.TestCase):
    @staticmethod
    def _reversal_samples(
        *, override_at_reversal: bool = False, unchanged_commands: bool = False
    ) -> list[dict]:
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
                "command_skipped": unchanged_commands,
                "requested_charge_w": 100.0 if direction == "charge" else 0.0,
                "requested_discharge_w": 100.0 if direction == "discharge" else 0.0,
            }
            if unchanged_commands:
                sample["command_skip_reason"] = "unchanged_within_tolerance"
            if override_at_reversal and index == 5:
                sample["manual_action"] = "discharge"
            samples.append(sample)
        return samples

    @staticmethod
    def _samples(
        *,
        kp_up: float = 0.5,
        kp_down: float = 0.5,
        skipped: bool = False,
        skip_reason: str | None = "unchanged_within_tolerance",
    ) -> list[dict]:
        samples = []
        for index in range(60):
            requested = 500.0 if (index // 6) % 2 == 0 else 600.0
            samples.append(
                {
                    "direction": "charge",
                    "grid_valid": True,
                    "command_skipped": skipped,
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
            if skip_reason is not None:
                samples[-1]["command_skip_reason"] = (
                    skip_reason if skipped else "none"
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

    def test_unchanged_active_commands_remain_valid_observations(self) -> None:
        result = evaluate_training_session(
            {"samples": self._samples(skipped=True)}
        )["charge"]

        self.assertEqual(result["decision"], "proposed")
        self.assertEqual(result["sample_count"], 60)
        self.assertEqual(result["direction_sample_count"], 60)
        self.assertEqual(result["unchanged_command_sample_count"], 60)
        self.assertEqual(result["valid_sample_ratio"], 1.0)

    def test_legacy_active_skipped_commands_are_inferred_as_unchanged(self) -> None:
        result = evaluate_training_session(
            {"samples": self._samples(skipped=True, skip_reason=None)}
        )["charge"]

        self.assertEqual(result["decision"], "proposed")
        self.assertEqual(result["sample_count"], 60)
        self.assertEqual(result["unchanged_command_sample_count"], 60)

    def test_unrecognized_skipped_commands_stay_excluded_and_explain_why(self) -> None:
        result = evaluate_training_session(
            {"samples": self._samples(skipped=True, skip_reason="device_blocked")}
        )["charge"]

        self.assertEqual(result["decision"], "insufficient_data")
        self.assertEqual(result["sample_count"], 0)
        self.assertEqual(result["rejected_command_skip_count"], 60)
        self.assertIn("confidence_below_threshold", result["insufficient_reasons"])

    def test_direction_quality_reports_each_exclusion_class(self) -> None:
        samples = self._samples()
        samples[0]["grid_valid"] = False
        samples[1]["grid_error_w"] = None
        samples[2]["command_skipped"] = True
        samples[2]["command_skip_reason"] = "device_blocked"

        result = evaluate_training_session({"samples": samples})["charge"]

        self.assertEqual(result["direction_sample_count"], 60)
        self.assertEqual(result["sample_count"], 57)
        self.assertEqual(result["valid_sample_ratio"], 0.95)
        self.assertEqual(result["rejected_invalid_grid_count"], 1)
        self.assertEqual(result["rejected_missing_error_count"], 1)
        self.assertEqual(result["rejected_command_skip_count"], 1)

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
        self.assertEqual(result["eligibility_exclusion_counts"]["manual_action"], 1)

    def test_reversal_shadow_accepts_unchanged_active_commands(self) -> None:
        result = evaluate_training_session(
            {"samples": self._reversal_samples(unchanged_commands=True)}
        )["reversal_hysteresis"]

        self.assertEqual(result["status"], "simulated")
        self.assertEqual(result["direction_sample_count"], 45)
        self.assertEqual(result["eligible_sample_count"], 45)
        self.assertEqual(result["unchanged_command_sample_count"], 45)
        self.assertEqual(result["eligible_reversal_count"], 1)


if __name__ == "__main__":
    unittest.main()
