"""Strategy-boundary tests for full-charge maintenance."""

from __future__ import annotations

from pathlib import Path
import unittest

from support import bootstrap

ROOT = Path(__file__).resolve().parents[1]
bootstrap()

from custom_components.battery_smartflow_ai.core.full_charge_maintenance import (  # noqa: E402
    FullChargeMaintenanceDecision,
    FullChargeMaintenanceRecord,
    MaintenanceState,
    MaintenanceWindow,
)
from custom_components.battery_smartflow_ai.decision_engine import DecisionResult  # noqa: E402
from custom_components.battery_smartflow_ai.full_charge_maintenance_control import (  # noqa: E402
    apply_maintenance_charge_request,
)


def request(window: MaintenanceWindow) -> FullChargeMaintenanceDecision:
    return FullChargeMaintenanceDecision(
        record=FullChargeMaintenanceRecord("device", active=True),
        state=MaintenanceState.CHARGING_TO_FULL,
        selected_window=window,
        request_full_charge=True,
        target_soc_pct=100.0,
        temporary_user_limit_override=True,
    )


class FullChargeMaintenanceControlTests(unittest.TestCase):
    def test_price_window_temporarily_targets_full_without_mutating_input(self):
        normal = DecisionResult("idle", "output", 0.0, 0.0, "soc_limit_upper")
        result = apply_maintenance_charge_request(
            normal,
            request(MaintenanceWindow.LOW_PRICE),
            configured_soc_max=80.0,
            max_charge_w=1200.0,
            grid_export_w=0.0,
            automation_allowed=True,
        )
        self.assertTrue(result.applied)
        self.assertEqual(result.effective_soc_max, 100.0)
        self.assertEqual(result.decision.target_soc, 100.0)
        self.assertEqual(result.decision.charge_w, 1200.0)
        self.assertEqual(normal.action, "idle")

    def test_pv_window_starts_only_with_available_surplus(self):
        result = apply_maintenance_charge_request(
            DecisionResult("idle", "output", 0.0, 0.0, "idle"),
            request(MaintenanceWindow.PV_SURPLUS),
            configured_soc_max=80.0,
            max_charge_w=1200.0,
            grid_export_w=340.0,
            automation_allowed=True,
        )
        self.assertEqual(result.decision.charge_w, 340.0)
        self.assertEqual(result.decision.reason, "pv_surplus_charge")

    def test_manual_and_emergency_paths_are_never_overridden(self):
        emergency = DecisionResult(
            "emergency", "input", 300.0, 0.0, "emergency_latched_charge"
        )
        for allowed in (False, True):
            result = apply_maintenance_charge_request(
                emergency,
                request(MaintenanceWindow.OVERDUE_DEADLINE),
                configured_soc_max=80.0,
                max_charge_w=1200.0,
                grid_export_w=0.0,
                automation_allowed=allowed,
            )
            self.assertFalse(result.applied)
            self.assertIs(result.decision, emergency)
            self.assertEqual(result.effective_soc_max, 80.0)

    def test_inactive_request_leaves_normal_strategy_untouched(self):
        normal = DecisionResult("discharge", "output", 0.0, 500.0, "idle")
        result = apply_maintenance_charge_request(
            normal,
            None,
            configured_soc_max=75.0,
            max_charge_w=1200.0,
            grid_export_w=0.0,
            automation_allowed=True,
        )
        self.assertFalse(result.applied)
        self.assertIs(result.decision, normal)
        self.assertEqual(result.effective_soc_max, 75.0)


if __name__ == "__main__":
    unittest.main()
