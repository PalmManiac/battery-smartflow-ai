"""Tests for mapping coordinator diagnostics into V4.4.0 samples."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.debug_sample_builder import (  # noqa: E402
    build_debug_sample,
    build_entity_diagnostics,
)


class DebugSampleBuilderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 8, 12, 12, 0, tzinfo=timezone.utc)

    def test_groups_existing_diagnostics_without_inventing_missing_values(self) -> None:
        details = {
            "soc": 56.5,
            "pv_w": 840.0,
            "deficit": 120.0,
            "price_now": 0.21,
            "season_mode": "summer",
            "decision_action": "charge",
            "decision_reason": "pv_surplus",
            "automatic_strategy_active": True,
            "automatic_strategy_reason": "balanced",
            "charge_source_allocation_active": True,
            "charge_source_allocation_reason": "mixed_pv_grid_charge",
            "charge_total_target_w": 900.0,
            "charge_pv_allocated_w": 400.0,
            "charge_grid_requested_w": 500.0,
            "regulation_strategy_intent": "charge",
            "regulation_strategy_priority": 40,
            "regulation_grid_avg_short_w": 110.0,
            "regulation_raw_target_w": 500.0,
            "regulation_command_ac_mode": "input",
            "regulation_command_should_write_input": True,
            "learned_planning_status": "ready",
            "learned_planning_required_charge_energy_kwh": 1.2,
            "forecast_status": "ready",
            "forecast_tomorrow_kwh": 8.4,
            "pv_outlook": "high",
            "charge_commit_active": True,
            "charge_commit_reason": "learned_window",
            "set_mode": "input",
            "set_input_w": 500,
            "mode_write_requested": "input",
            "mode_write_entity_state_before_write": "output",
            "mode_write_live_entity_state": "input",
            "mode_write_last_success": "input",
            "input_write_requested_w": 500,
            "input_write_effective_w": 500,
            "input_write_skipped": False,
            "command_effectiveness_status": "effective",
        }

        result = build_debug_sample(timestamp=self.now, details=details).as_dict()

        self.assertEqual(result["raw_values"]["soc"], 56.5)
        self.assertNotIn("battery_ac_power_raw", result["raw_values"])
        self.assertEqual(result["prices"]["price_now"], 0.21)
        self.assertEqual(result["strategy"]["decision_action"], "charge")
        self.assertEqual(result["strategy"]["season_mode"], "summer")
        self.assertTrue(result["strategy"]["automatic"]["strategy_active"])
        self.assertEqual(result["strategy"]["intent"]["intent"], "charge")
        allocation = result["strategy"]["charge_source_allocation"]
        self.assertTrue(allocation["active"])
        self.assertEqual(allocation["reason"], "mixed_pv_grid_charge")
        self.assertEqual(allocation["charge_total_target_w"], 900.0)
        self.assertEqual(allocation["charge_pv_allocated_w"], 400.0)
        self.assertEqual(allocation["charge_grid_requested_w"], 500.0)
        self.assertEqual(result["regulation"]["grid_avg_short_w"], 110.0)
        self.assertNotIn("command_ac_mode", result["regulation"])
        self.assertEqual(result["planning"]["learned"]["status"], "ready")
        self.assertEqual(result["planning"]["forecast"]["pv_outlook"], "high")
        self.assertTrue(result["planning"]["charge_commit"]["active"])
        self.assertEqual(result["command"]["requested"]["set_input_w"], 500)
        self.assertEqual(result["command"]["regulation"]["ac_mode"], "input")
        self.assertEqual(result["command"]["mode_write"]["requested"], "input")
        self.assertEqual(
            result["command"]["mode_write"]["entity_state_before_write"],
            "output",
        )
        self.assertEqual(
            result["command"]["mode_write"]["live_entity_state"],
            "input",
        )
        self.assertEqual(
            result["command"]["mode_write"]["last_success"],
            "input",
        )
        self.assertNotIn("entity_state", result["command"]["mode_write"])
        self.assertEqual(result["command"]["input_write"]["effective_w"], 500)
        self.assertEqual(result["command"]["effectiveness"]["status"], "effective")

    def test_sample_omits_repeated_profile_and_healthy_entity_details(self) -> None:
        result = build_debug_sample(
            timestamp=self.now,
            details={
                "soc": 50.0,
                "regulation_grid_now_w": 10.0,
                "regulation_profile_target_import_w": 10.0,
            },
            configured_entities={
                "soc": "sensor.private_battery_name",
                "pv": "sensor.private_pv_name",
            },
            entity_availability={"soc": True, "pv": False},
        ).as_dict()

        self.assertEqual(result["regulation"]["grid_now_w"], 10.0)
        self.assertNotIn("profile_target_import_w", result["regulation"])
        self.assertNotIn("soc", result["raw_values"]["entities"])
        self.assertNotIn("offgrid", result["raw_values"]["entities"])
        self.assertEqual(
            result["raw_values"]["entities"]["pv"]["status"],
            "unavailable",
        )
        self.assertNotIn(
            "entity_id",
            result["raw_values"]["entities"]["pv"],
        )

    def test_entity_diagnostics_distinguish_all_availability_states(self) -> None:
        result = build_entity_diagnostics(
            {
                "soc": "sensor.battery_soc",
                "pv": "sensor.pv_power",
                "offgrid": None,
                "optional_cell_voltage": "sensor.lowest_cell_voltage",
            },
            {
                "soc": True,
                "pv": False,
                "optional_cell_voltage": None,
            },
        )

        self.assertEqual(result["soc"]["status"], "available")
        self.assertEqual(result["pv"]["status"], "unavailable")
        self.assertEqual(result["offgrid"]["status"], "not_configured")
        self.assertEqual(result["optional_cell_voltage"]["status"], "unknown")

    def test_builder_filters_secrets_before_returning_sample(self) -> None:
        sample = build_debug_sample(
            timestamp=self.now,
            details={
                "decision_reason": "test",
                "regulation_command_reason": {"api_key": "must-not-leak"},
            },
            configured_entities={"token_sensor": "sensor.harmless"},
            entity_availability={"token_sensor": False},
        )

        result = sample.as_dict()

        self.assertEqual(
            result["command"]["regulation"]["reason"]["api_key"],
            "[REDACTED]",
        )
        self.assertEqual(
            result["raw_values"]["entities"]["token_sensor"],
            "[REDACTED]",
        )

    def test_source_mapping_changes_do_not_change_built_sample(self) -> None:
        details = {"soc": 40.0, "automatic_strategy_active": True}
        sample = build_debug_sample(timestamp=self.now, details=details)

        details["soc"] = 99.0
        details["automatic_strategy_active"] = False

        result = sample.as_dict()
        self.assertEqual(result["raw_values"]["soc"], 40.0)
        self.assertTrue(result["strategy"]["automatic"]["strategy_active"])


if __name__ == "__main__":
    unittest.main()
