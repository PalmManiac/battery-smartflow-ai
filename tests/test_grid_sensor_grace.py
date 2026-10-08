from __future__ import annotations

import unittest

from custom_components.battery_smartflow_ai.grid_sensor_grace import (
    GridSensorGapGrace,
)


class GridSensorGapGraceTests(unittest.TestCase):
    def test_holds_only_active_automatic_discharge_within_grace(self) -> None:
        guard = GridSensorGapGrace(grace_seconds=12.5)
        elapsed = guard.observe(now=100.0, valid=False)

        self.assertTrue(
            guard.may_hold_discharge(
                elapsed_seconds=elapsed,
                automatic_mode=True,
                active_discharge=True,
            )
        )
        self.assertTrue(
            guard.may_hold_discharge(
                elapsed_seconds=10.0,
                automatic_mode=True,
                active_discharge=True,
            )
        )

    def test_does_not_hold_after_grace_expires(self) -> None:
        guard = GridSensorGapGrace(grace_seconds=12.5)
        guard.observe(now=100.0, valid=False)

        self.assertFalse(
            guard.may_hold_discharge(
                elapsed_seconds=13.0,
                automatic_mode=True,
                active_discharge=True,
            )
        )

    def test_never_holds_manual_or_idle_operation(self) -> None:
        guard = GridSensorGapGrace(grace_seconds=12.5)
        elapsed = guard.observe(now=100.0, valid=False)

        self.assertFalse(
            guard.may_hold_discharge(
                elapsed_seconds=elapsed,
                automatic_mode=False,
                active_discharge=True,
            )
        )
        self.assertFalse(
            guard.may_hold_discharge(
                elapsed_seconds=elapsed,
                automatic_mode=True,
                active_discharge=False,
            )
        )

    def test_valid_reading_resets_gap_timer(self) -> None:
        guard = GridSensorGapGrace(grace_seconds=12.5)
        self.assertEqual(guard.observe(now=100.0, valid=False), 0.0)
        self.assertEqual(guard.observe(now=105.0, valid=False), 5.0)
        self.assertEqual(guard.observe(now=106.0, valid=True), 0.0)
        self.assertEqual(guard.observe(now=200.0, valid=False), 0.0)


if __name__ == "__main__":
    unittest.main()
