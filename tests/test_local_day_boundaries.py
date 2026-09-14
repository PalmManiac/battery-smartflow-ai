"""Regression tests for Home Assistant local calendar-day accounting."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
import unittest

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.economics import (  # noqa: E402
    EconomicPowerFlows,
    EnergyAccumulator,
)


class LocalDayBoundaryTests(unittest.TestCase):
    def test_daily_bucket_uses_configured_local_midnight(self) -> None:
        accumulator = EnergyAccumulator(
            day_timezone=timezone(timedelta(hours=2), name="Europe/Berlin summer")
        )
        power = EconomicPowerFlows(battery_to_home_w=3600.0)
        before_midnight = datetime(2026, 9, 14, 21, 59, 50, tzinfo=UTC)
        accumulator.add_sample(sampled_at=before_midnight, power=power)

        accumulator.add_sample(
            sampled_at=before_midnight + timedelta(seconds=20), power=power
        )

        snapshot = accumulator.snapshot()
        self.assertEqual(snapshot.day.isoformat(), "2026-09-15")
        self.assertAlmostEqual(snapshot.daily.battery_to_home_kwh, 0.01)
        self.assertAlmostEqual(snapshot.total.battery_to_home_kwh, 0.02)

    def test_daily_bucket_does_not_reset_at_utc_midnight(self) -> None:
        accumulator = EnergyAccumulator(
            day_timezone=timezone(timedelta(hours=2), name="Europe/Berlin summer")
        )
        power = EconomicPowerFlows(grid_export_w=3600.0)
        before_utc_midnight = datetime(2026, 9, 14, 23, 59, 50, tzinfo=UTC)
        accumulator.add_sample(sampled_at=before_utc_midnight, power=power)

        accumulator.add_sample(
            sampled_at=before_utc_midnight + timedelta(seconds=20), power=power
        )

        snapshot = accumulator.snapshot()
        self.assertEqual(snapshot.day.isoformat(), "2026-09-15")
        self.assertAlmostEqual(snapshot.daily.grid_export_kwh, 0.02)

    def test_winter_day_starts_at_one_utc(self) -> None:
        accumulator = EnergyAccumulator(
            day_timezone=timezone(timedelta(hours=1), name="Europe/Berlin winter")
        )
        power = EconomicPowerFlows(grid_to_battery_w=3600.0)
        before_midnight = datetime(2026, 12, 14, 22, 59, 50, tzinfo=UTC)
        accumulator.add_sample(sampled_at=before_midnight, power=power)

        accumulator.add_sample(
            sampled_at=before_midnight + timedelta(seconds=20), power=power
        )

        snapshot = accumulator.snapshot()
        self.assertEqual(snapshot.day.isoformat(), "2026-12-15")
        self.assertAlmostEqual(snapshot.daily.grid_to_battery_kwh, 0.01)


if __name__ == "__main__":
    unittest.main()
