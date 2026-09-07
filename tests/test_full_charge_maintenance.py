"""Contracts for the native per-device full-charge maintenance planner."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from support import bootstrap

bootstrap()

from custom_components.battery_smartflow_ai.core.full_charge_maintenance import (  # noqa: E402
    CalibrationInformationSource,
    FullChargeMaintenanceInput,
    FullChargeMaintenancePlanner,
    FullChargeMaintenanceRecord,
    MaintenanceBlockReason,
    MaintenanceState,
    MaintenanceWindow,
    NativeCalibrationInformation,
)


NOW = datetime(2026, 9, 7, 12, tzinfo=timezone.utc)


def observation(**changes):
    values = {
        "now": NOW,
        "enabled": True,
        "soc_pct": 80.0,
        "soc_fresh": True,
        "charge_power_w": 500.0,
    }
    values.update(changes)
    return FullChargeMaintenanceInput(**values)


class FullChargeMaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.planner = FullChargeMaintenancePlanner()

    def record(self, device="device-a", *, days_ago=31, **changes):
        values = {
            "device_id": device,
            "last_confirmed_full_at": NOW - timedelta(days=days_ago),
        }
        values.update(changes)
        return FullChargeMaintenanceRecord(**values)

    def test_not_due_due_soon_and_due_are_distinct(self):
        self.assertEqual(
            self.planner.evaluate(self.record(days_ago=1), observation()).state,
            MaintenanceState.NOT_DUE,
        )
        self.assertEqual(
            self.planner.evaluate(self.record(days_ago=28), observation()).state,
            MaintenanceState.DUE_SOON,
        )
        self.assertEqual(
            self.planner.evaluate(self.record(days_ago=31), observation()).state,
            MaintenanceState.WAITING_FOR_FAVORABLE_WINDOW,
        )

    def test_pv_then_price_then_existing_charge_window_priority(self):
        record = self.record()
        both = self.planner.evaluate(
            record, observation(pv_window_favorable=True, price_window_favorable=True)
        )
        self.assertEqual(both.selected_window, MaintenanceWindow.PV_SURPLUS)
        price = self.planner.evaluate(
            record, observation(price_window_favorable=True)
        )
        self.assertEqual(price.selected_window, MaintenanceWindow.LOW_PRICE)
        existing = self.planner.evaluate(
            record, observation(strategic_charge_active=True)
        )
        self.assertEqual(
            existing.selected_window, MaintenanceWindow.EXISTING_STRATEGIC_CHARGE
        )

    def test_manual_mode_blocks_new_and_running_maintenance(self):
        for record in (self.record(), self.record(active=True)):
            decision = self.planner.evaluate(
                record,
                observation(
                    automation_allowed=False,
                    pv_window_favorable=True,
                ),
            )
            self.assertEqual(decision.state, MaintenanceState.BLOCKED)
            self.assertEqual(
                decision.block_reason, MaintenanceBlockReason.MANUAL_MODE
            )
            self.assertFalse(decision.request_full_charge)

    def test_overdue_deadline_prevents_unbounded_postponement(self):
        result = self.planner.evaluate(self.record(days_ago=38), observation())
        self.assertEqual(result.selected_window, MaintenanceWindow.OVERDUE_DEADLINE)
        self.assertTrue(result.request_full_charge)

    def test_user_authorization_is_required_and_limit_override_is_temporary(self):
        blocked = self.planner.evaluate(
            self.record(), observation(enabled=False, price_window_favorable=True)
        )
        self.assertEqual(blocked.block_reason, MaintenanceBlockReason.NOT_ENABLED)
        active = self.planner.evaluate(
            self.record(), observation(price_window_favorable=True)
        )
        self.assertEqual(active.target_soc_pct, 100.0)
        self.assertTrue(active.temporary_user_limit_override)
        self.assertTrue(active.record.active)
        disabled_again = self.planner.evaluate(
            active.record,
            observation(enabled=False, price_window_favorable=True),
        )
        self.assertEqual(
            disabled_again.block_reason, MaintenanceBlockReason.NOT_ENABLED
        )
        self.assertFalse(disabled_again.request_full_charge)

    def test_hems_protection_stale_soc_and_pack_conflict_block(self):
        cases = (
            ({"hems_active": True}, MaintenanceBlockReason.HEMS_ACTIVE),
            ({"protection_active": True}, MaintenanceBlockReason.PROTECTION_ACTIVE),
            ({"soc_fresh": False}, MaintenanceBlockReason.SOC_INVALID_OR_STALE),
            ({"pack_data_conflict": True}, MaintenanceBlockReason.PACK_DATA_CONFLICT),
            ({"transport_available": False}, MaintenanceBlockReason.TRANSPORT_UNAVAILABLE),
        )
        for changes, reason in cases:
            with self.subTest(reason=reason):
                result = self.planner.evaluate(self.record(), observation(**changes))
                self.assertEqual(result.state, MaintenanceState.BLOCKED)
                self.assertEqual(result.block_reason, reason)
                self.assertFalse(result.request_full_charge)

    def test_short_or_unconvincing_100_percent_does_not_complete(self):
        active = self.record(active=True)
        first = self.planner.evaluate(active, observation(soc_pct=100.0))
        self.assertEqual(first.state, MaintenanceState.CONFIRMING_FULL)
        early = self.planner.evaluate(
            first.record,
            observation(now=NOW + timedelta(minutes=4), soc_pct=100.0),
        )
        self.assertEqual(early.state, MaintenanceState.CONFIRMING_FULL)
        high_power = self.planner.evaluate(
            first.record,
            observation(now=NOW + timedelta(minutes=6), soc_pct=100.0),
        )
        self.assertEqual(high_power.state, MaintenanceState.CONFIRMING_FULL)

    def test_confirmed_full_completes_and_restores_normal_limit_semantics(self):
        active = self.record(active=True)
        first = self.planner.evaluate(active, observation(soc_pct=100.0))
        completed = self.planner.evaluate(
            first.record,
            observation(
                now=NOW + timedelta(minutes=5),
                soc_pct=100.0,
                charge_power_w=25.0,
            ),
        )
        self.assertEqual(completed.state, MaintenanceState.COMPLETED)
        self.assertFalse(completed.record.active)
        self.assertFalse(completed.temporary_user_limit_override)
        self.assertEqual(
            completed.record.last_confirmed_full_at, NOW + timedelta(minutes=5)
        )

    def test_restart_preserves_per_device_commit_without_commands(self):
        first = self.planner.evaluate(
            self.record("device-a"), observation(price_window_favorable=True)
        )
        restored = FullChargeMaintenanceRecord.from_dict(first.record.as_dict())
        self.assertEqual(restored, first.record)
        self.assertEqual(set(restored.as_dict()), {
            "device_id", "interval_days", "last_confirmed_full_at",
            "last_completed_maintenance_at", "active", "full_candidate_since",
        })
        resumed = self.planner.evaluate(
            restored, observation(now=NOW + timedelta(minutes=1))
        )
        self.assertEqual(resumed.state, MaintenanceState.CHARGING_TO_FULL)
        self.assertTrue(resumed.request_full_charge)

    def test_multiple_devices_are_independent(self):
        first = self.planner.evaluate(
            self.record("device-a"), observation(pv_window_favorable=True)
        )
        second = self.planner.evaluate(self.record("device-b", days_ago=1), observation())
        self.assertTrue(first.record.active)
        self.assertFalse(second.record.active)
        self.assertNotEqual(first.record.device_id, second.record.device_id)

    def test_unverified_fields_cannot_masquerade_as_native_calibration(self):
        with self.assertRaisesRegex(ValueError, "unverified"):
            NativeCalibrationInformation(
                source=CalibrationInformationSource.BSFAI_DERIVED,
                next_calibration_at=NOW,
            )
        verified = NativeCalibrationInformation(
            source=CalibrationInformationSource.VERIFIED_NATIVE,
            status="required",
            next_calibration_at=NOW,
        )
        self.assertEqual(verified.status, "required")

    def test_planner_has_no_discharge_or_transport_command_surface(self):
        decision = self.planner.evaluate(
            self.record(), observation(pv_window_favorable=True)
        )
        self.assertFalse(hasattr(decision, "request_discharge"))
        self.assertFalse(hasattr(decision, "transport"))


if __name__ == "__main__":
    unittest.main()
