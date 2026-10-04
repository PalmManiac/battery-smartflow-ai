"""Tests for AC-mode observation used by command-effectiveness checks."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from support import bootstrap

bootstrap()

from custom_components.battery_smartflow_ai.command_effectiveness import (  # noqa: E402
    CommandEffectivenessState,
    evaluate_command_effectiveness,
    resolve_observed_ac_mode,
)


class ResolveObservedAcModeTests(unittest.TestCase):
    def test_valid_native_mode_takes_precedence_over_unavailable_ha_select(self):
        self.assertEqual(
            resolve_observed_ac_mode(
                native_mode="charge",
                native_mode_valid=True,
                entity_mode="unavailable",
            ),
            "input",
        )

    def test_valid_native_idle_does_not_fall_back_to_stale_ha_select(self):
        self.assertEqual(
            resolve_observed_ac_mode(
                native_mode="idle",
                native_mode_valid=True,
                entity_mode="input",
            ),
            "idle",
        )

    def test_missing_native_mode_uses_the_legacy_entity_state(self):
        self.assertEqual(
            resolve_observed_ac_mode(
                native_mode=None,
                native_mode_valid=False,
                entity_mode="output",
            ),
            "output",
        )

    def test_unknown_valid_native_mode_fails_closed(self):
        self.assertEqual(
            resolve_observed_ac_mode(
                native_mode="unknown",
                native_mode_valid=True,
                entity_mode="input",
            ),
            "",
        )

    def test_native_charge_mode_confirms_measured_effect_without_ha_select(self):
        observed_mode = resolve_observed_ac_mode(
            native_mode="charge",
            native_mode_valid=True,
            entity_mode="unavailable",
        )
        result = evaluate_command_effectiveness(
            now=datetime(2026, 10, 4, tzinfo=timezone.utc),
            requested_mode="input",
            input_target_w=2300,
            output_target_w=0,
            battery_charge_w=172,
            battery_discharge_w=0,
            battery_sensor_valid=True,
            grid_import_w=649,
            current_ac_mode=observed_mode,
            active_command_write_pending=False,
            previous=CommandEffectivenessState(direction="input"),
        )

        self.assertEqual(result.status, "effective")
        self.assertEqual(result.reason, "measured_power_active")


if __name__ == "__main__":
    unittest.main()
