from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone

from custom_components.battery_smartflow_ai.core.models import ZendureTransport
from custom_components.battery_smartflow_ai.regulation_training import (
    RegulationDirectionMetrics,
    RegulationDirectionParameters,
    RegulationProfile,
    RegulationProfileKey,
    RegulationProfileState,
)


class RegulationTrainingModelTests(unittest.TestCase):
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
                fast_gain=1.1,
                max_step_fast_w=500.0,
            ),
        )

        serialized = profile.as_dict()

        self.assertEqual(serialized["state"], "shadow")
        self.assertEqual(serialized["charge"]["metrics"]["sample_count"], 20)
        self.assertEqual(serialized["discharge"]["parameters"]["fast_gain"], 1.1)
        self.assertIsNone(serialized["charge"]["parameters"]["fast_gain"])
        json.dumps(serialized)

    def test_profile_requires_timezone_aware_training_timestamp(self) -> None:
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            RegulationProfile(
                key=RegulationProfileKey(
                    device_id="internal-device-id",
                    transport=ZendureTransport.ZENSDK,
                    device_model="SolarFlow 2400 AC",
                ),
                trained_at=datetime(2026, 10, 5, 12, 0),
            )

    def test_metrics_and_candidate_parameters_reject_unsafe_numbers(self) -> None:
        with self.assertRaisesRegex(ValueError, "finite non-negative"):
            RegulationDirectionMetrics(command_to_effect_p95_seconds=float("nan"))
        with self.assertRaisesRegex(ValueError, "between 0 and 1"):
            RegulationDirectionMetrics(overshoot_rate=1.1)
        with self.assertRaisesRegex(ValueError, "finite non-negative"):
            RegulationDirectionParameters(fast_gain=-0.1)

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


if __name__ == "__main__":
    unittest.main()
