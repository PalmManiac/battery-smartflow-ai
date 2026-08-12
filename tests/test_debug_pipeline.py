"""End-to-end tests for the pure V4.4.0 debug recording pipeline."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.debug_exporter import (  # noqa: E402
    export_debug_package,
)
from custom_components.battery_smartflow_ai.debug_recorder import (  # noqa: E402
    DebugRecorder,
)
from custom_components.battery_smartflow_ai.debug_sample_builder import (  # noqa: E402
    build_debug_sample,
)


class DebugPipelineTests(unittest.TestCase):
    def test_record_build_stop_export_and_redaction_pipeline(self) -> None:
        start = datetime(2026, 8, 12, 15, 0, tzinfo=timezone.utc)
        recorder = DebugRecorder(integration_version="4.4.0-dev1", max_samples=10)
        recorder.start(
            duration_minutes=10,
            now=start,
            device_profile="SF2400AC",
            config={
                "access_token": "structured-secret",
                "note": "Authorization: Bearer inline-secret",
            },
            profile={"TARGET_IMPORT_W": 10.0},
        )

        for index in range(3):
            timestamp = start + timedelta(seconds=index * 10)
            sample = build_debug_sample(
                timestamp=timestamp,
                details={
                    "soc": 50.0 + index,
                    "decision_action": "charge",
                    "decision_reason": "pv_surplus",
                    "regulation_final_power_w": 200.0 + index,
                    "regulation_command_ac_mode": "input",
                    "input_write_requested_w": 200.0 + index,
                },
                configured_entities={"soc": "sensor.battery_soc", "offgrid": None},
                entity_availability={"soc": True},
            )
            self.assertIsNone(recorder.record(sample, now=timestamp))

        package = recorder.stop(now=start + timedelta(minutes=1))
        self.assertIsNotNone(package)
        assert package is not None

        with tempfile.TemporaryDirectory() as config_directory:
            exported = export_debug_package(
                package,
                config_directory=config_directory,
            )
            data = json.loads(exported.path.read_text(encoding="utf-8"))

        self.assertFalse(recorder.status.active)
        self.assertIsNone(recorder.status.recording_end)
        self.assertEqual(data["summary"]["captured_sample_count"], 3)
        self.assertEqual(len(data["samples"]), 3)
        self.assertEqual(data["samples"][2]["raw_values"]["soc"], 52.0)
        self.assertEqual(data["config"]["access_token"], "[REDACTED]")
        self.assertNotIn("inline-secret", json.dumps(data))
        self.assertEqual(
            data["samples"][0]["raw_values"]["entities"]["offgrid"]["status"],
            "not_configured",
        )

    def test_elapsed_recording_exports_planned_end_not_late_tick_time(self) -> None:
        start = datetime(2026, 8, 12, 16, 0, tzinfo=timezone.utc)
        recorder = DebugRecorder(integration_version="4.4.0-dev1")
        recorder.start(duration_minutes=10, now=start)

        package = recorder.tick(now=start + timedelta(minutes=15))

        self.assertIsNotNone(package)
        assert package is not None
        self.assertEqual(
            package.as_dict()["meta"]["recording_end"],
            "2026-08-12T16:10:00Z",
        )


if __name__ == "__main__":
    unittest.main()
