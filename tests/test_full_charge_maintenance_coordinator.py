"""Coordinator integration contracts for observed full-charge maintenance."""

from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "battery_smartflow_ai"


class FullChargeMaintenanceCoordinatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (COMPONENT / "coordinator.py").read_text(encoding="utf-8")

    def test_runtime_is_restored_and_saved_in_existing_state_document(self):
        self.assertIn("FullChargeMaintenanceRuntime()", self.source)
        self.assertIn(
            'self._full_charge_maintenance.restore(\n'
            '                self._persist.get("full_charge_maintenance")',
            self.source,
        )
        self.assertIn(
            'self._persist["full_charge_maintenance"] = (', self.source
        )
        self.assertIn(
            "self._full_charge_maintenance.persisted_state()", self.source
        )

    def test_coordinator_passes_real_planning_windows_to_native_observation(self):
        self.assertIn("native_runtime.full_charge_maintenance_input(", self.source)
        self.assertIn("pv_window_favorable=bool(", self.source)
        self.assertIn("price_window_favorable=bool(", self.source)
        self.assertIn(
            'self._persist.get("charge_commit_active", False)', self.source
        )

    def test_user_setting_is_passed_to_observation_planner(self):
        call = self.source[
            self.source.index("native_runtime.full_charge_maintenance_input("):
        ]
        call = call[:call.index(")\n                if maintenance_input")]
        self.assertIn("SETTING_FULL_CHARGE_MAINTENANCE_ENABLED", call)
        self.assertIn("DEFAULT_FULL_CHARGE_MAINTENANCE_ENABLED", call)
        self.assertIn("SETTING_FULL_CHARGE_MAINTENANCE_INTERVAL_DAYS", self.source)

    def test_request_crosses_only_the_strategy_adapter(self):
        self.assertIn("**maintenance_status", self.source)
        self.assertIn("apply_maintenance_charge_request(", self.source)
        adapter = (COMPONENT / "full_charge_maintenance_control.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("DeviceCommand(", adapter)
        self.assertNotIn("native_zendure", adapter)

    def test_maintenance_is_evaluated_before_strategy_and_charge_binding(self):
        maintenance = self.source.index(
            "maintenance_decision = self._full_charge_maintenance.evaluate("
        )
        strategy = self.source.index("decision = self._engine.evaluate(ctx)")
        binding = self.source.index("decision = self._apply_charge_commit(")
        self.assertLess(maintenance, strategy)
        self.assertLess(strategy, binding)
        self.assertIn("ctx.soc_max = 100.0", self.source[maintenance:strategy])
        self.assertIn(
            "soc_max = maintenance_application.effective_soc_max",
            self.source[strategy:binding],
        )


if __name__ == "__main__":
    unittest.main()
