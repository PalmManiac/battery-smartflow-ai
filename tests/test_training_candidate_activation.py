from __future__ import annotations

import unittest

from custom_components.battery_smartflow_ai.regulation_training import (
    candidate_gain_parameters,
    training_candidate_scope_matches,
    training_session_candidate_parameters,
)


class TrainingCandidateActivationTests(unittest.TestCase):
    def _parameters(self, session: dict) -> dict[str, float]:
        return candidate_gain_parameters(session)

    def test_extracts_only_the_proposed_direction_gains(self) -> None:
        session = {
            "shadow_evaluation": {
                "status": "candidate_proposed",
                "charge": {
                    "decision": "proposed",
                    "parameters": {
                        "kp_up": 0.715,
                        "kp_down": None,
                        "max_step_up_w": 5000,
                    },
                },
                "discharge": {
                    "decision": "rejected",
                    "parameters": {"kp_up": 1.5, "kp_down": 1.2},
                },
            }
        }

        self.assertEqual(
            self._parameters(session["shadow_evaluation"]),
            {"CHARGE_KP_UP": 0.715},
        )

    def test_rejects_a_non_proposed_result(self) -> None:
        with self.assertRaisesRegex(ValueError, "No regulation training candidate"):
            self._parameters({"status": "no_improvement"})

    def test_interrupted_session_candidate_is_not_applicable(self) -> None:
        with self.assertRaisesRegex(ValueError, "Interrupted training data"):
            training_session_candidate_parameters(
                {
                    "interrupted": True,
                    "shadow_evaluation": {
                        "status": "candidate_proposed",
                        "charge": {
                            "decision": "proposed",
                            "parameters": {"kp_up": 0.8},
                        },
                    },
                }
            )

    def test_rejects_non_finite_or_out_of_range_gains(self) -> None:
        for value in (float("nan"), 0.09, 2.01):
            with self.subTest(value=value):
                session = {
                    "shadow_evaluation": {
                        "status": "candidate_proposed",
                        "charge": {
                            "decision": "proposed",
                            "parameters": {"kp_up": value},
                        },
                    }
                }
                with self.assertRaisesRegex(ValueError, "outside safe bounds"):
                    self._parameters(session["shadow_evaluation"])

    def test_candidate_scope_requires_same_device_and_transport(self) -> None:
        stored = {
            "device_id": "device-a",
            "transport": "zensdk",
            "device_model": "SolarFlow 2400 AC",
            "firmware_context": "2.0.1",
        }

        self.assertTrue(
            training_candidate_scope_matches(
                stored, {**stored, "firmware_context": None}
            )
        )
        self.assertFalse(
            training_candidate_scope_matches(
                stored, {**stored, "device_id": "device-b"}
            )
        )
        self.assertFalse(
            training_candidate_scope_matches(
                stored, {**stored, "transport": "cloud_mqtt"}
            )
        )
        self.assertFalse(
            training_candidate_scope_matches(
                stored, {**stored, "firmware_context": "3.0.0"}
            )
        )


if __name__ == "__main__":
    unittest.main()
