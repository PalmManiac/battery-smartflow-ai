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
            "strategic_charge_active=bool(charge_commit_active)", self.source
        )

    def test_observation_mode_cannot_request_maintenance_charge(self):
        call = self.source[
            self.source.index("native_runtime.full_charge_maintenance_input("):
        ]
        call = call[:call.index(")\n                if maintenance_input")]
        self.assertIn("enabled=False", call)

    def test_status_is_exposed_without_changing_strategy_decision(self):
        self.assertIn("**maintenance_status", self.source)
        maintenance_section = self.source[
            self.source.index("maintenance_status ="):
            self.source.index('self._persist["debug"] = "OK"')
        ]
        self.assertNotIn("DeviceCommand(", maintenance_section)
        self.assertNotIn("charge_commit_target_soc =", maintenance_section)


if __name__ == "__main__":
    unittest.main()
