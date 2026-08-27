"""Contracts for the platform-independent V4.7 Clock boundary."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
import unittest
from zoneinfo import ZoneInfo

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.core.clock import (  # noqa: E402
    SystemClock,
    TestClock,
)


BERLIN = ZoneInfo("Europe/Berlin")


class ClockTests(unittest.TestCase):
    def test_test_clock_exposes_utc_local_and_monotonic_time(self) -> None:
        clock = TestClock(
            datetime(2026, 8, 27, 12, 0, tzinfo=UTC),
            local_timezone=BERLIN,
            monotonic_seconds=40.0,
        )

        self.assertEqual(
            clock.utc_now(),
            datetime(2026, 8, 27, 12, 0, tzinfo=UTC),
        )
        self.assertEqual(clock.local_now().hour, 14)
        self.assertEqual(clock.local_now().utcoffset(), timedelta(hours=2))
        self.assertEqual(clock.monotonic(), 40.0)

    def test_advance_moves_deadlines_and_runtime_together(self) -> None:
        clock = TestClock(
            datetime(2026, 8, 27, 23, 45, tzinfo=BERLIN),
            local_timezone=BERLIN,
            monotonic_seconds=10.0,
        )

        clock.advance(timedelta(minutes=30))

        self.assertEqual(clock.local_now().date().isoformat(), "2026-08-28")
        self.assertEqual(clock.local_now().strftime("%H:%M"), "00:15")
        self.assertEqual(clock.monotonic(), 1810.0)

    def test_calendar_set_does_not_fake_process_elapsed_time(self) -> None:
        clock = TestClock(
            datetime(2026, 8, 27, 12, 0, tzinfo=UTC),
            monotonic_seconds=25.0,
        )

        clock.set(datetime(2026, 8, 28, 12, 0, tzinfo=UTC))

        self.assertEqual(clock.utc_now().day, 28)
        self.assertEqual(clock.monotonic(), 25.0)

    def test_naive_time_and_negative_advance_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            TestClock(datetime(2026, 8, 27, 12, 0))

        clock = TestClock(datetime(2026, 8, 27, 12, 0, tzinfo=UTC))
        with self.assertRaises(ValueError):
            clock.advance(timedelta(seconds=-1))

    def test_system_clock_returns_aware_values(self) -> None:
        clock = SystemClock(local_timezone=BERLIN)

        self.assertIsNotNone(clock.utc_now().utcoffset())
        self.assertIsNotNone(clock.local_now().utcoffset())
        self.assertGreater(clock.monotonic(), 0.0)

    def test_core_clock_has_no_home_assistant_dependency(self) -> None:
        root = Path(__file__).resolve().parents[1]
        port = (
            root
            / "custom_components"
            / "battery_smartflow_ai"
            / "core"
            / "ports"
            / "clock.py"
        ).read_text(encoding="utf-8")
        implementation = (
            root
            / "custom_components"
            / "battery_smartflow_ai"
            / "core"
            / "clock.py"
        ).read_text(encoding="utf-8")
        coordinator = (
            root
            / "custom_components"
            / "battery_smartflow_ai"
            / "coordinator.py"
        ).read_text(encoding="utf-8")
        forecast = (
            root
            / "custom_components"
            / "battery_smartflow_ai"
            / "forecast.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn("homeassistant", port)
        self.assertNotIn("homeassistant", implementation)
        self.assertNotIn("dt_util.utcnow()", coordinator)
        self.assertNotIn("dt_util.utcnow()", forecast)
        self.assertIn("clock: Clock | None = None", coordinator)
        self.assertIn("clock=self._clock", coordinator)


if __name__ == "__main__":
    unittest.main()
