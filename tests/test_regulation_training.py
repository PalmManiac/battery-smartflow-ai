from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone

from custom_components.battery_smartflow_ai.core.models import ZendureTransport
from custom_components.battery_smartflow_ai.regulation_training import (
    PassiveTrainingRecorder,
    RegulationDirectionMetrics,
    RegulationDirectionParameters,
    RegulationProfile,
    RegulationProfileKey,
    RegulationProfileState,
    TrainingDirection,
    TrainingSample,
    recover_interrupted_training_session,
    retain_training_sessions,
)


class RegulationTrainingModelTests(unittest.TestCase):
    def _key(self) -> RegulationProfileKey:
        return RegulationProfileKey(
            device_id="internal-device-id",
            transport=ZendureTransport.ZENSDK,
            device_model="SolarFlow 2400 AC",
            firmware_context="2.0.1",
        )

    def _sample(self, minute: int, direction: str) -> TrainingSample:
        return TrainingSample(
            timestamp=datetime(2026, 10, 5, 12, minute, tzinfo=timezone.utc),
            direction=direction,
            grid_import_w=300.0,
            grid_export_w=0.0,
            soc_pct=55.0,
            pv_w=1200.0,
            requested_charge_w=500.0 if direction == "charge" else 0.0,
            requested_discharge_w=400.0 if direction == "discharge" else 0.0,
            observed_charge_w=450.0 if direction == "charge" else 0.0,
            observed_discharge_w=350.0 if direction == "discharge" else 0.0,
            grid_valid=True,
            pv_valid=True,
            command_skipped=False,
        )

    def test_profile_is_scoped_to_device_transport_model_and_firmware(self) -> None:
        key = RegulationProfileKey(
            device_id="internal-device-id",
            transport=ZendureTransport.ZENSDK,
            device_model="SolarFlow 2400 AC",
            firmware_context="2.0.1",
        )

        serialized = key.as_dict()

        self.assertEqual(serialized["transport"], "zensdk")
        self.assertEqual(serialized["device_model"], "SolarFlow 2400 AC")
        self.assertEqual(serialized["firmware_context"], "2.0.1")

    def test_profile_serializes_separate_direction_metrics_and_parameters(self) -> None:
        profile = RegulationProfile(
            key=RegulationProfileKey(
                device_id="internal-device-id",
                transport=ZendureTransport.CLOUD_MQTT,
                device_model="SolarFlow 2400 AC",
            ),
            trained_at=datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc),
            charge_metrics=RegulationDirectionMetrics(
                sample_count=20,
                command_to_readback_p50_seconds=1.2,
                confidence=0.5,
            ),
            discharge_parameters=RegulationDirectionParameters(
                kp_up=1.1,
                max_step_up_w=500.0,
            ),
        )

        serialized = profile.as_dict()

        self.assertEqual(serialized["state"], "shadow")
        self.assertEqual(serialized["charge"]["metrics"]["sample_count"], 20)
        self.assertEqual(serialized["discharge"]["parameters"]["kp_up"], 1.1)
        self.assertIsNone(serialized["charge"]["parameters"]["kp_up"])
        json.dumps(serialized)

    def test_profile_requires_timezone_aware_training_timestamp(self) -> None:
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            RegulationProfile(
                key=RegulationProfileKey(
                    device_id="internal-device-id",
                    transport=ZendureTransport.ZENSDK,
                    device_model="SolarFlow 2400 AC",
                ),
                trained_at=datetime(2026, 10, 5, 12, 0),  # noqa: DTZ001
            )

    def test_metrics_and_candidate_parameters_reject_unsafe_numbers(self) -> None:
        with self.assertRaisesRegex(ValueError, "finite non-negative"):
            RegulationDirectionMetrics(command_to_effect_p95_seconds=float("nan"))
        with self.assertRaisesRegex(ValueError, "between 0 and 1"):
            RegulationDirectionMetrics(overshoot_rate=1.1)
        with self.assertRaisesRegex(ValueError, "finite non-negative"):
            RegulationDirectionParameters(kp_up=-0.1)

    def test_profile_state_is_not_implicitly_active(self) -> None:
        profile = RegulationProfile(
            key=RegulationProfileKey(
                device_id="internal-device-id",
                transport=ZendureTransport.LOCAL_MQTT,
                device_model="SolarFlow 2400 AC",
            ),
            trained_at=datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc),
        )

        self.assertIs(profile.state, RegulationProfileState.SHADOW)

    def test_recorder_is_manual_bounded_and_separates_directions(self) -> None:
        recorder = PassiveTrainingRecorder(max_samples=2)
        started = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
        recorder.start(
            key=self._key(),
            now=started,
            duration_minutes=10,
            direction_scope=TrainingDirection.CHARGE,
        )
        recorder.record(self._sample(1, "charge"))
        recorder.record(self._sample(2, "discharge"))
        recorder.record(self._sample(3, "charge"))
        recorder.record(self._sample(4, "charge"))

        session = recorder.stop(
            now=datetime(2026, 10, 5, 12, 5, tzinfo=timezone.utc)
        )

        self.assertFalse(recorder.active)
        self.assertEqual(len(session.samples), 2)
        self.assertEqual(session.dropped_sample_count, 1)
        self.assertTrue(all(item.direction == "charge" for item in session.samples))
        self.assertEqual(session.profile().state, RegulationProfileState.SHADOW)
        self.assertEqual(session.profile().discharge_metrics.sample_count, 0)
        self.assertLessEqual(session.profile().charge_metrics.confidence, 0.5)

    def test_auto_stop_and_serialization_keep_context_and_allowlisted_values(self) -> None:
        recorder = PassiveTrainingRecorder()
        started = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
        recorder.start(
            key=self._key(),
            now=started,
            duration_minutes=10,
            direction_scope=TrainingDirection.BOTH,
        )
        sample = recorder.sample_from_details(
            timestamp=started,
            details={
                "soc": 55,
                "pv_w": 1200,
                "deficit": 300,
                "surplus": 0,
                "grid_sensor_valid": True,
                "pv_sensor_valid": True,
                "regulation_command_ac_mode": "input",
                "regulation_command_input_limit_w": 500,
                "regulation_command_output_limit_w": 0,
                "battery_charge_w": 450,
                "battery_discharge_w": 0,
                "regulation_command_skipped": False,
                "regulation_error_w": 120,
                "regulation_target_import_w": 10,
                "ai_mode": "automatic",
                "manual_action": "standby",
                "regulation_strategy_intent": "pv_charge",
                "regulation_strategy_force": False,
                "regulation_strategy_priority": 400,
                "regulation_mode_allowed": True,
                "regulation_discharge_allowed": True,
                "regulation_mode_arbiter_reason": "stable_export",
                "effective_charge_kp_up": 0.65,
                "effective_charge_kp_down": 0.45,
                "effective_charge_max_step_up": 550,
                "effective_charge_max_step_down": 300,
                "effective_charge_deadband_w": 50,
                "password": "must-not-be-recorded",
            },
        )
        recorder.record(sample)
        session = recorder.tick(now=started.replace(minute=10))

        serialized = session.as_dict()
        self.assertEqual(serialized["key"]["transport"], "zensdk")
        self.assertEqual(serialized["profile"]["state"], "shadow")
        self.assertEqual(serialized["samples"][0]["direction"], "charge")
        self.assertEqual(serialized["samples"][0]["grid_error_w"], 120)
        self.assertEqual(serialized["samples"][0]["baseline_kp_up"], 0.65)
        self.assertEqual(serialized["samples"][0]["strategy_intent"], "pv_charge")
        self.assertEqual(serialized["samples"][0]["strategy_priority"], 400)
        self.assertFalse(serialized["samples"][0]["strategy_force"])
        self.assertTrue(serialized["samples"][0]["mode_allowed"])
        self.assertEqual(
            serialized["samples"][0]["baseline_max_step_down_w"], 300
        )
        self.assertNotIn("password", json.dumps(serialized))
        self.assertFalse(recorder.active)

    def test_snapshot_preserves_active_run_and_captured_samples(self) -> None:
        recorder = PassiveTrainingRecorder()
        started = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
        recorder.start(
            key=self._key(),
            now=started,
            duration_minutes=1440,
            direction_scope=TrainingDirection.BOTH,
        )
        recorder.record(self._sample(1, "charge"))

        checkpoint = recorder.snapshot(
            now=datetime(2026, 10, 5, 12, 15, tzinfo=timezone.utc)
        )

        self.assertIsNotNone(checkpoint)
        self.assertTrue(recorder.active)
        self.assertEqual(len(checkpoint.samples), 1)
        self.assertEqual(checkpoint.started_at, started)
        self.assertEqual(checkpoint.as_dict()["sample_count"], 1)

        recorder.record(self._sample(2, "discharge"))
        self.assertEqual(recorder.status["sample_count"], 2)

    def test_checkpoint_recovery_marks_partial_run_and_keeps_captured_samples(self) -> None:
        checkpoint = {
            "key": self._key().as_dict(),
            "started_at": "2026-10-05T12:00:00+00:00",
            "ends_at": "2026-10-06T12:00:00+00:00",
            "checkpointed_at": "2026-10-05T12:15:00+00:00",
            "sample_count": 1,
            "samples": [self._sample(1, "charge").as_dict()],
            "profile": {"state": "shadow", "trained_at": "old"},
        }

        recovered = recover_interrupted_training_session(
            checkpoint,
            interrupted_at=datetime(2026, 10, 5, 12, 16, tzinfo=timezone.utc),
        )

        self.assertTrue(recovered["interrupted"])
        self.assertEqual(recovered["sample_count"], 1)
        self.assertEqual(recovered["completed_at"], "2026-10-05T12:01:00+00:00")
        self.assertEqual(recovered["intended_ends_at"], checkpoint["ends_at"])
        self.assertEqual(recovered["profile"]["trained_at"], recovered["completed_at"])
        self.assertIsNone(
            recover_interrupted_training_session(
                {"samples": "malformed", "key": {}},
                interrupted_at=datetime(2026, 10, 5, 12, 16, tzinfo=timezone.utc),
            )
        )

    def test_recorder_rejects_unbounded_or_naive_session_configuration(self) -> None:
        recorder = PassiveTrainingRecorder()
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            recorder.start(
                key=self._key(),
                now=datetime(2026, 10, 5, 12, 0),  # noqa: DTZ001
                duration_minutes=10,
                direction_scope=TrainingDirection.BOTH,
            )
        with self.assertRaisesRegex(ValueError, "duration"):
            recorder.start(
                key=self._key(),
                now=datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc),
                duration_minutes=999,
                direction_scope=TrainingDirection.BOTH,
            )

    def test_recorder_supports_and_auto_stops_after_24_hours(self) -> None:
        recorder = PassiveTrainingRecorder()
        started = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
        recorder.start(
            key=self._key(),
            now=started,
            duration_minutes=1440,
            direction_scope=TrainingDirection.BOTH,
        )
        recorder.record(self._sample(1, "charge"))

        end = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)
        self.assertEqual(recorder.status["ends_at"], end.isoformat())
        self.assertIsNone(
            recorder.tick(now=datetime(2026, 10, 6, 11, 59, tzinfo=timezone.utc))
        )
        session = recorder.tick(now=end)

        self.assertIsNotNone(session)
        self.assertEqual(session.completed_at, end)
        self.assertEqual(len(session.samples), 1)
        self.assertFalse(recorder.active)

    def test_training_storage_keeps_recent_sessions_with_sample_budget(self) -> None:
        sessions = [
            {"sample_count": 12_000, "label": "old"},
            {"sample_count": 8_000, "label": "middle"},
            {"sample_count": 15_000, "label": "new"},
        ]

        retained = retain_training_sessions(sessions)

        self.assertEqual([item["label"] for item in retained], ["new"])


if __name__ == "__main__":
    unittest.main()
