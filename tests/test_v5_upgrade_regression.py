"""End-to-end contracts for an existing V4.7 installation entering V5."""

from __future__ import annotations

from copy import deepcopy
import unittest

from support import bootstrap

bootstrap()

from custom_components.battery_smartflow_ai.native_registry_identity import (  # noqa: E402
    native_hardware_unique_id,
    native_main_device_identifier,
    native_pack_device_identifier,
)
from custom_components.battery_smartflow_ai.v5_migration import (  # noqa: E402
    confirm_native_binding,
    initial_v5_migration_state,
    migrate_persisted_v47_state,
)


class V5UpgradeRegressionTests(unittest.TestCase):
    def test_v47_binding_restart_preserves_data_and_registry_identity(self):
        entry_id = "existing-entry"
        native_id = "cloud_mqtt:physical-device"
        public_main = "ZD_DEVICE_123456789abc"
        public_pack = "ZD_PACK_abcdef123456"
        v47 = {
            "learned_load_slots": {"12:00": 1.25},
            "economics_money_state": {"grid_charge_cost": 12.34},
            "economics_energy_state": {"pv_charge_kwh": 56.7},
            "charge_commit_active": True,
            "charge_commit_target_soc": 80,
            "custom_future_value": [1, 2, 3],
        }
        migration = confirm_native_binding(
            initial_v5_migration_state(entry_id).as_dict(),
            native_candidate_id=native_id,
        )
        first_start = migrate_persisted_v47_state(
            v47,
            legacy_system_id=f"config_entry:{entry_id}",
            native_candidate_id=migration["native_candidate_id"],
        )

        second_start = migrate_persisted_v47_state(
            deepcopy(first_start),
            legacy_system_id=f"config_entry:{entry_id}",
            native_candidate_id=migration["native_candidate_id"],
        )

        self.assertEqual(first_start, second_start)
        for key, value in v47.items():
            self.assertEqual(second_start[key], value)
        self.assertEqual(second_start["v5_economics_owner"], native_id)
        self.assertEqual(second_start["v5_charge_commit_owner"], native_id)
        self.assertFalse(second_start["v5_native_control_enabled"])
        self.assertTrue(second_start["v5_legacy_zha_enabled"])

        before_restart = (
            native_hardware_unique_id(
                entry_id, "main", public_main, "soc_pct"
            ),
            native_hardware_unique_id(
                entry_id, "pack", public_pack, "soc_pct"
            ),
            native_main_device_identifier(public_main),
            native_pack_device_identifier(public_pack),
        )
        after_restart = (
            native_hardware_unique_id(
                entry_id, "main", public_main, "soc_pct"
            ),
            native_hardware_unique_id(
                entry_id, "pack", public_pack, "soc_pct"
            ),
            native_main_device_identifier(public_main),
            native_pack_device_identifier(public_pack),
        )
        self.assertEqual(before_restart, after_restart)
        self.assertEqual(len(set(before_restart)), len(before_restart))

    def test_existing_v4_entity_identity_is_not_reused_by_native_hardware(self):
        entry_id = "existing-entry"
        legacy_unique_id = f"battery_smartflow_ai_{entry_id}_soc"
        native_unique_id = native_hardware_unique_id(
            entry_id,
            "main",
            "ZD_DEVICE_123456789abc",
            "soc_pct",
        )
        self.assertNotEqual(legacy_unique_id, native_unique_id)
        self.assertEqual(
            legacy_unique_id,
            "battery_smartflow_ai_existing-entry_soc",
        )


if __name__ == "__main__":
    unittest.main()
