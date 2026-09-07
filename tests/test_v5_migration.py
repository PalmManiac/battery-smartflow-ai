"""V4.7-to-V5 configuration and persistence migration contracts."""

import unittest

from support import bootstrap

bootstrap()

from custom_components.battery_smartflow_ai.core.models import (  # noqa: E402
    DiscoveryCandidate, NativeDeviceIdentity, ZendureTransport,
)
from custom_components.battery_smartflow_ai.v5_migration import (  # noqa: E402
    confirm_native_binding, initial_v5_migration_state, match_v4_device,
    migrate_persisted_v47_state,
)


def candidate(device_id, model, supported=True, name="Same display name"):
    return DiscoveryCandidate(
        NativeDeviceIdentity(
            ZendureTransport.CLOUD_MQTT,
            device_id=device_id,
            product_model=model,
        ),
        name,
        supported,
    )


class V5MigrationTests(unittest.TestCase):
    def test_initial_state_retains_zha_and_never_enables_native_writes(self):
        state = initial_v5_migration_state("entry-1")
        self.assertTrue(state.legacy_zha_enabled)
        self.assertFalse(state.native_control_enabled)
        self.assertIsNone(state.native_candidate_id)

    def test_persistence_migration_preserves_all_v47_values_and_totals(self):
        old = {
            "learned_load_slots": {"12:00": 1.25},
            "economics_money_state": {"grid_charge_cost": 12.34},
            "economics_energy_state": {"pv_charge_kwh": 56.7},
            "charge_commit_active": True,
            "charge_commit_target_soc": 80,
            "custom_future_value": [1, 2, 3],
        }
        migrated = migrate_persisted_v47_state(
            old, legacy_system_id="config_entry:entry-1"
        )
        for key, value in old.items():
            self.assertEqual(migrated[key], value)
        self.assertEqual(
            migrated["v5_charge_commit_owner"], "config_entry:entry-1"
        )
        self.assertEqual(migrated["v5_economics_owner"], "config_entry:entry-1")
        self.assertFalse(migrated["v5_native_control_enabled"])
        self.assertTrue(migrated["v5_legacy_zha_enabled"])
        self.assertIsNot(migrated["learned_load_slots"], old["learned_load_slots"])

    def test_persistence_migration_is_idempotent_and_restart_safe(self):
        once = migrate_persisted_v47_state(
            {"charge_commit_active": False},
            legacy_system_id="config_entry:entry-1",
        )
        twice = migrate_persisted_v47_state(
            once, legacy_system_id="config_entry:entry-1"
        )
        self.assertEqual(once, twice)

    def test_confirmed_binding_keeps_zha_and_native_writes_separate(self):
        initial = initial_v5_migration_state("entry-1")
        confirmed = confirm_native_binding(
            initial.as_dict(),
            native_candidate_id="cloud_mqtt:device-1",
        )
        self.assertEqual(confirmed["binding_state"], "confirmed")
        self.assertEqual(confirmed["phase"], "shadow_ready")
        self.assertEqual(
            confirmed["native_candidate_id"],
            "cloud_mqtt:device-1",
        )
        self.assertFalse(confirmed["native_control_enabled"])
        self.assertTrue(confirmed["legacy_zha_enabled"])

    def test_confirmed_device_owns_persisted_economics_and_commitment(self):
        native_id = "cloud_mqtt:device-1"
        migrated = migrate_persisted_v47_state(
            {
                "charge_commit_active": True,
                "v5_economics_owner": "config_entry:entry-1",
                "v5_charge_commit_owner": "config_entry:entry-1",
            },
            legacy_system_id="config_entry:entry-1",
            native_candidate_id=native_id,
        )
        self.assertEqual(migrated["v5_binding_state"], "confirmed")
        self.assertEqual(migrated["v5_economics_owner"], native_id)
        self.assertEqual(migrated["v5_charge_commit_owner"], native_id)
        self.assertFalse(migrated["v5_native_control_enabled"])

    def test_confirmed_persistence_binding_is_idempotent(self):
        native_id = "cloud_mqtt:device-1"
        once = migrate_persisted_v47_state(
            {"charge_commit_active": True},
            legacy_system_id="config_entry:entry-1",
            native_candidate_id=native_id,
        )
        twice = migrate_persisted_v47_state(
            once,
            legacy_system_id="config_entry:entry-1",
            native_candidate_id=native_id,
        )
        self.assertEqual(once, twice)

    def test_matching_uses_supported_matrix_profile_not_name_or_order(self):
        candidates = (
            candidate("wrong", "SolarFlow800Pro"),
            candidate("right", "SolarFlow2400AC"),
            candidate("unknown", "SF2400AC lookalike", False),
        )
        matches = match_v4_device(
            legacy_profile="SF2400AC", candidates=candidates
        )
        self.assertEqual([item.identity.device_id for item in matches], ["right"])

    def test_ambiguous_matches_remain_for_explicit_user_choice(self):
        matches = match_v4_device(
            legacy_profile="SF2400AC",
            candidates=(
                candidate("first", "SolarFlow2400AC"),
                candidate("second", "SF2400AC"),
            ),
        )
        self.assertEqual(len(matches), 2)

    def test_missing_or_unknown_device_never_gets_fallback_match(self):
        self.assertEqual(
            match_v4_device(
                legacy_profile="SF2400AC",
                candidates=(candidate("future", "FutureModel"),),
            ),
            (),
        )


if __name__ == "__main__":
    unittest.main()
