"""Tests for the bounded V4.4.0 debug recorder lifecycle."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.debug_package import DebugSample  # noqa: E402
from custom_components.battery_smartflow_ai.debug_recorder import (  # noqa: E402
    DebugRecorder,
)


class DebugRecorderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.start = datetime(2026, 8, 12, 10, 0, tzinfo=timezone.utc)
        self.recorder = DebugRecorder(
            integration_version="4.4.0-dev1",
            max_samples=3,
        )

    def sample(self, offset_seconds: int) -> DebugSample:
        return DebugSample(
            timestamp=self.start + timedelta(seconds=offset_seconds),
            raw_values={"sequence": offset_seconds},
        )

    def test_start_exposes_sparse_status_and_rejects_parallel_recording(self) -> None:
        status = self.recorder.start(
            duration_minutes=10,
            now=self.start,
            device_profile="SF2400AC",
        )

        self.assertTrue(status.active)
        self.assertEqual(status.recording_start, self.start)
        self.assertEqual(status.recording_end, self.start + timedelta(minutes=10))
        self.assertEqual(status.sample_count, 0)
        with self.assertRaisesRegex(RuntimeError, "already active"):
            self.recorder.start(duration_minutes=10, now=self.start)

    def test_only_supported_durations_are_accepted(self) -> None:
        with self.assertRaisesRegex(ValueError, "10, 30, 60, 120"):
            self.recorder.start(duration_minutes=15, now=self.start)

    def test_inactive_fast_path_does_nothing(self) -> None:
        self.assertFalse(self.recorder.is_active)
        self.assertIsNone(self.recorder.tick(now=datetime(2000, 1, 1)))
        self.assertIsNone(
            self.recorder.record(self.sample(0), now=datetime(2000, 1, 1))
        )
        self.assertIsNone(self.recorder.stop(now=datetime(2000, 1, 1)))

    def test_manual_stop_builds_package_and_resets_active_state(self) -> None:
        config = {"token": "must-not-leak", "soc_min": 12}
        self.recorder.start(
            duration_minutes=30,
            now=self.start,
            config=config,
        )
        config["soc_min"] = 99
        self.recorder.record(self.sample(10), now=self.start + timedelta(seconds=10))

        package = self.recorder.stop(now=self.start + timedelta(minutes=2))

        assert package is not None
        result = package.as_dict()
        self.assertFalse(self.recorder.is_active)
        self.assertIsNone(self.recorder.status.recording_start)
        self.assertIsNone(self.recorder.status.recording_end)
        self.assertEqual(result["summary"]["stop_reason"], "manual")
        self.assertEqual(result["summary"]["captured_sample_count"], 1)
        self.assertEqual(result["config"]["token"], "[REDACTED]")
        self.assertEqual(result["config"]["soc_min"], 12)
        self.assertEqual(len(result["samples"]), 1)

    def test_sample_is_detached_and_redacted_when_recorded(self) -> None:
        raw_values = {"soc": 42, "api_key": "must-not-leak"}
        sample = DebugSample(timestamp=self.start, raw_values=raw_values)
        self.recorder.start(duration_minutes=10, now=self.start)

        self.recorder.record(sample, now=self.start)
        raw_values["soc"] = 99
        package = self.recorder.stop(now=self.start + timedelta(minutes=1))

        assert package is not None
        retained = package.as_dict()["samples"][0]["raw_values"]
        self.assertEqual(retained["soc"], 42)
        self.assertEqual(retained["api_key"], "[REDACTED]")

    def test_tick_auto_stops_at_planned_end_time(self) -> None:
        self.recorder.start(duration_minutes=10, now=self.start)
        self.recorder.record(self.sample(0), now=self.start)

        package = self.recorder.tick(now=self.start + timedelta(minutes=11))

        assert package is not None
        result = package.as_dict()
        self.assertEqual(result["summary"]["stop_reason"], "duration_elapsed")
        self.assertEqual(
            result["meta"]["recording_end"],
            "2026-08-12T10:10:00Z",
        )
        self.assertFalse(self.recorder.is_active)

    def test_sample_arriving_at_end_is_not_recorded(self) -> None:
        self.recorder.start(duration_minutes=10, now=self.start)

        package = self.recorder.record(
            self.sample(600),
            now=self.start + timedelta(minutes=10),
        )

        assert package is not None
        self.assertEqual(package.as_dict()["summary"]["captured_sample_count"], 0)

    def test_ring_buffer_discards_oldest_samples_and_reports_warning(self) -> None:
        self.recorder.start(duration_minutes=10, now=self.start)
        for offset in range(5):
            self.recorder.record(
                self.sample(offset),
                now=self.start + timedelta(seconds=offset),
            )

        package = self.recorder.stop(now=self.start + timedelta(minutes=1))

        assert package is not None
        result = package.as_dict()
        self.assertEqual(result["summary"]["captured_sample_count"], 5)
        self.assertEqual(result["summary"]["retained_sample_count"], 3)
        self.assertEqual(result["summary"]["dropped_sample_count"], 2)
        self.assertEqual(
            [sample["raw_values"]["sequence"] for sample in result["samples"]],
            [2, 3, 4],
        )
        self.assertEqual(result["warnings"][0]["code"], "sample_limit_reached")

    def test_completed_recorder_can_be_started_again_without_old_samples(self) -> None:
        self.recorder.start(duration_minutes=10, now=self.start)
        self.recorder.record(self.sample(1), now=self.start + timedelta(seconds=1))
        self.recorder.stop(now=self.start + timedelta(minutes=1))

        second_start = self.start + timedelta(hours=1)
        status = self.recorder.start(duration_minutes=30, now=second_start)

        self.assertTrue(status.active)
        self.assertEqual(status.sample_count, 0)
        self.assertEqual(status.dropped_sample_count, 0)


if __name__ == "__main__":
    unittest.main()
