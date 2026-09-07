"""Economics invariants for parallel native telemetry sources."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from support import bootstrap

bootstrap()

from custom_components.battery_smartflow_ai.economics import (  # noqa: E402
    EconomicPowerFlows,
    EnergyAccumulator,
)


class NativeEconomicsDeduplicationTests(unittest.TestCase):
    def test_same_arbitrated_runtime_cycle_is_accounted_once(self) -> None:
        now = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)
        power = EconomicPowerFlows(grid_to_battery_w=1800)
        accumulator = EnergyAccumulator(max_interval_seconds=300)
        accumulator.add_sample(sampled_at=now, power=power)

        first = accumulator.add_sample(
            sampled_at=now + timedelta(seconds=20),
            power=power,
        )
        duplicate = accumulator.add_sample(
            sampled_at=now + timedelta(seconds=20),
            power=power,
        )

        self.assertEqual(first.status, "accounted")
        self.assertEqual(duplicate.status, "duplicate_or_out_of_order")
        self.assertEqual(duplicate.accounted_seconds, 0.0)
        self.assertAlmostEqual(
            accumulator.snapshot().total.grid_to_battery_kwh,
            0.01,
        )


if __name__ == "__main__":
    unittest.main()
