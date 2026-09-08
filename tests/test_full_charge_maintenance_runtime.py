"""Restart and persistence contracts for full-charge maintenance runtime."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from support import bootstrap

bootstrap()

from custom_components.battery_smartflow_ai.core.full_charge_maintenance import (  # noqa: E402
    FullChargeMaintenanceInput,
    MaintenanceState,
)
from custom_components.battery_smartflow_ai.full_charge_maintenance_runtime import (  # noqa: E402
    FullChargeMaintenanceRuntime,
)


NOW = datetime(2026, 9, 7, 12, tzinfo=timezone.utc)


def input_data(**changes):
    values = {
        "now": NOW,
        "enabled": True,
        "soc_pct": 70.0,
        "soc_fresh": True,
        "charge_power_w": 0.0,
        "price_window_favorable": True,
    }
    values.update(changes)
    return FullChargeMaintenanceInput(**values)


class FullChargeMaintenanceRuntimeTests(unittest.TestCase):
    def test_active_semantic_commit_survives_restart_without_command(self):
        runtime = FullChargeMaintenanceRuntime()
        first = runtime.evaluate("device-a", input_data())
        self.assertEqual(first.state, MaintenanceState.CHARGING_TO_FULL)

        persisted = runtime.persisted_state()
        restored = FullChargeMaintenanceRuntime()
        self.assertEqual(restored.restore(persisted), ())
        resumed = restored.evaluate(
            "device-a",
            input_data(
                now=NOW + timedelta(minutes=1),
                price_window_favorable=False,
            ),
        )
        self.assertEqual(resumed.state, MaintenanceState.WAITING_FOR_FAVORABLE_WINDOW)
        self.assertTrue(resumed.record.active)
        self.assertFalse(resumed.request_full_charge)
        self.assertNotIn("command", str(persisted).lower())
        self.assertNotIn("transport", str(persisted).lower())

    def test_records_remain_separate_per_device(self):
        runtime = FullChargeMaintenanceRuntime()
        runtime.evaluate("device-a", input_data())
        runtime.evaluate(
            "device-b",
            input_data(
                enabled=False,
                price_window_favorable=False,
                soc_pct=60.0,
            ),
        )
        records = runtime.persisted_state()["records"]
        self.assertEqual(set(records), {"device-a", "device-b"})
        self.assertTrue(records["device-a"]["active"])
        self.assertFalse(records["device-b"]["active"])

    def test_one_corrupt_record_does_not_destroy_valid_device_history(self):
        runtime = FullChargeMaintenanceRuntime()
        invalid = runtime.restore({
            "records": {
                "valid": {
                    "device_id": "device-a",
                    "interval_days": 30,
                    "last_confirmed_full_at": NOW.isoformat(),
                    "active": False,
                },
                "broken": {"device_id": "", "interval_days": 0},
            }
        })
        self.assertEqual(invalid, ("broken",))
        self.assertIn("device-a", runtime.persisted_state()["records"])

    def test_interval_change_preserves_history_and_never_changes_active_commit(self):
        runtime = FullChargeMaintenanceRuntime()
        runtime.restore({
            "records": {
                "device-a": {
                    "device_id": "device-a",
                    "interval_days": 30,
                    "last_confirmed_full_at": NOW.isoformat(),
                    "active": False,
                }
            }
        })
        runtime.evaluate("device-a", input_data(enabled=False), interval_days=45)
        record = runtime.persisted_state()["records"]["device-a"]
        self.assertEqual(record["interval_days"], 45)
        self.assertEqual(record["last_confirmed_full_at"], NOW.isoformat())

    def test_sensor_surface_contains_no_device_identity(self):
        runtime = FullChargeMaintenanceRuntime()
        runtime.evaluate("secret-device-id", input_data())
        data = runtime.sensor_data()
        self.assertNotIn("secret-device-id", str(data))
        self.assertEqual(
            data["full_charge_maintenance_state"], "charging_to_full"
        )


if __name__ == "__main__":
    unittest.main()
