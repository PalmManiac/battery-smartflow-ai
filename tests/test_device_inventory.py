"""V5 multi-device identity and V4 migration contracts."""

from __future__ import annotations

import unittest

from support import bootstrap

bootstrap()

from custom_components.battery_smartflow_ai.core.models import (  # noqa: E402
    BatteryPackIdentity,
    BindingState,
    DeviceControlState,
    DeviceInventory,
    DiscoveryCandidate,
    MainDevice,
    NativeDeviceIdentity,
    ZendureTransport,
)


def identity(
    device_id: str,
    *,
    model: str = "SF2400AC",
    serial: str | None = None,
    transport: ZendureTransport = ZendureTransport.CLOUD_MQTT,
) -> NativeDeviceIdentity:
    return NativeDeviceIdentity(
        transport=transport,
        device_id=device_id,
        serial_number=serial,
        product_id="product-family",
        product_model=model,
    )


class DeviceInventoryTests(unittest.TestCase):
    def test_v4_entry_becomes_stable_logical_system(self) -> None:
        device = MainDevice.from_v4_config_entry(
            "existing-entry-id", model="SF2400AC", profile_key="SF2400AC"
        )
        self.assertEqual(device.system_id, "config_entry:existing-entry-id")
        self.assertEqual(device.control_state, DeviceControlState.ACTIVE)
        self.assertEqual(device.selected_transport, ZendureTransport.HOME_ASSISTANT)
        self.assertEqual(device.native_identities, ())

    def test_discovery_does_not_create_or_activate_a_duplicate_system(self) -> None:
        legacy = MainDevice.from_v4_config_entry("existing-entry-id", model="SF2400AC")
        inventory = DeviceInventory(devices=(legacy,))
        candidate = DiscoveryCandidate(identity("device-1"), "My SF2400AC", True)
        inventory.discover(candidate)
        self.assertEqual(tuple(inventory.devices), (legacy.system_id,))
        self.assertIn(candidate.candidate_id, inventory.candidates)
        self.assertEqual(inventory.devices[legacy.system_id], legacy)

    def test_model_name_alone_never_suggests_an_identity_match(self) -> None:
        legacy = MainDevice.from_v4_config_entry("existing-entry-id", model="SF2400AC")
        inventory = DeviceInventory(devices=(legacy,))
        inventory.discover(
            DiscoveryCandidate(identity("unrelated-device"), "Same name", True)
        )
        proposal = inventory.suggest_bindings(legacy.system_id)[0]
        self.assertEqual(proposal.state, BindingState.UNMATCHED)
        self.assertEqual(proposal.reasons, ("model",))

    def test_exact_identity_is_only_suggested_and_not_bound(self) -> None:
        known = identity("cloud-device", serial="serial-123")
        legacy = MainDevice.from_v4_config_entry("existing-entry-id").bind(known)
        inventory = DeviceInventory(devices=(legacy,))
        local = DiscoveryCandidate(
            identity(
                "local-device",
                serial="serial-123",
                transport=ZendureTransport.ZENSDK,
            ),
            "SF2400AC local",
            True,
        )
        inventory.discover(local)
        proposal = inventory.suggest_bindings(legacy.system_id)[0]
        self.assertEqual(proposal.state, BindingState.SUGGESTED)
        self.assertIn("serial", proposal.reasons)
        self.assertEqual(len(inventory.devices[legacy.system_id].native_identities), 1)

    def test_confirmed_binding_enriches_same_logical_system(self) -> None:
        legacy = MainDevice.from_v4_config_entry("existing-entry-id", model="SF2400AC")
        inventory = DeviceInventory(devices=(legacy,))
        candidate = DiscoveryCandidate(identity("device-1"), "My SF2400AC", True)
        inventory.discover(candidate)
        bound = inventory.confirm_binding(legacy.system_id, candidate.candidate_id)
        self.assertEqual(bound.system_id, legacy.system_id)
        self.assertEqual(bound.control_state, DeviceControlState.ACTIVE)
        self.assertEqual(bound.selected_transport, ZendureTransport.HOME_ASSISTANT)
        self.assertIn(ZendureTransport.CLOUD_MQTT, bound.available_transports)
        self.assertNotIn(candidate.candidate_id, inventory.candidates)

    def test_fresh_install_starts_in_observation_mode(self) -> None:
        inventory = DeviceInventory()
        candidate = DiscoveryCandidate(identity("device-1"), "New system", True)
        inventory.discover(candidate)
        device = inventory.add_observed_system(
            candidate.candidate_id, system_id="bsfai-system-1"
        )
        self.assertEqual(device.control_state, DeviceControlState.OBSERVATION)

    def test_unknown_model_stays_unsupported_and_read_only(self) -> None:
        inventory = DeviceInventory()
        candidate = DiscoveryCandidate(
            identity("unknown-1", model="FutureProduct"), "Unknown", False
        )
        inventory.discover(candidate)
        device = inventory.add_observed_system(
            candidate.candidate_id, system_id="unknown-system"
        )
        self.assertEqual(device.control_state, DeviceControlState.UNSUPPORTED)
        self.assertFalse(device.supported)

    def test_packs_are_hierarchical_and_not_main_devices(self) -> None:
        main = MainDevice(system_id="main-1", display_name="Main")
        inventory = DeviceInventory(devices=(main,))
        inventory.add_pack(
            BatteryPackIdentity("pack-1", "main-1", serial_number="pack-serial")
        )
        self.assertEqual(len(inventory.devices), 1)
        self.assertEqual(inventory.packs["pack-1"].parent_system_id, "main-1")

    def test_pack_without_known_parent_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "parent"):
            DeviceInventory().add_pack(
                BatteryPackIdentity("pack-1", "missing")
            )

    def test_pack_membership_can_disappear_and_reappear(self) -> None:
        main = MainDevice(system_id="main-1", display_name="Main")
        inventory = DeviceInventory(
            devices=(main,),
            packs=(BatteryPackIdentity("pack-1", "main-1"),),
        )
        inventory.reconcile_packs("main-1", ())
        self.assertEqual(dict(inventory.packs), {})

        inventory.reconcile_packs(
            "main-1",
            (
                BatteryPackIdentity("pack-1", "main-1"),
                BatteryPackIdentity("pack-2", "main-1"),
            ),
        )
        self.assertEqual(set(inventory.packs), {"pack-1", "pack-2"})

    def test_inventory_has_no_artificial_device_limit(self) -> None:
        inventory = DeviceInventory(
            devices=(
                MainDevice(system_id=f"main-{number}", display_name=f"Main {number}")
                for number in range(25)
            )
        )
        self.assertEqual(len(inventory.devices), 25)

    def test_mixed_models_and_duplicate_display_names_remain_distinct(self) -> None:
        inventory = DeviceInventory(
            devices=(
                MainDevice(
                    system_id="main-1", display_name="Battery", model="SF2400AC"
                ),
                MainDevice(
                    system_id="main-2", display_name="Battery", model="SF800Pro"
                ),
            )
        )
        self.assertEqual(len(inventory.devices), 2)
        self.assertNotEqual(
            inventory.devices["main-1"].model,
            inventory.devices["main-2"].model,
        )

    def test_duplicate_logical_system_ids_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "system IDs"):
            DeviceInventory(
                devices=(
                    MainDevice(system_id="main-1", display_name="One"),
                    MainDevice(system_id="main-1", display_name="Two"),
                )
            )

    def test_v5_rejects_more_than_one_active_main_system(self) -> None:
        with self.assertRaisesRegex(ValueError, "one active"):
            DeviceInventory(
                devices=(
                    MainDevice.from_v4_config_entry("entry-1"),
                    MainDevice.from_v4_config_entry("entry-2"),
                )
            )

    def test_hems_blocks_control_without_removing_observation(self) -> None:
        main = MainDevice(system_id="main-1", display_name="Main")
        inventory = DeviceInventory(devices=(main,))
        blocked = inventory.set_hems_active("main-1", True)
        self.assertTrue(blocked.hems_active)
        self.assertEqual(blocked.control_state, DeviceControlState.HEMS_BLOCKED)

        with self.assertRaisesRegex(ValueError, "HEMS"):
            inventory.set_control_state("main-1", DeviceControlState.ACTIVE)

        unblocked = inventory.set_hems_active("main-1", False)
        self.assertFalse(unblocked.hems_active)
        self.assertEqual(unblocked.control_state, DeviceControlState.OBSERVATION)

    def test_second_system_cannot_be_activated_in_v5(self) -> None:
        active = MainDevice.from_v4_config_entry("entry-1")
        other = MainDevice(system_id="main-2", display_name="Other")
        inventory = DeviceInventory(devices=(active, other))

        with self.assertRaisesRegex(ValueError, "one active"):
            inventory.set_control_state("main-2", DeviceControlState.ACTIVE)

    def test_missing_active_system_does_not_select_another(self) -> None:
        active = MainDevice.from_v4_config_entry("entry-1")
        observed = MainDevice(system_id="main-2", display_name="Other")
        inventory = DeviceInventory(devices=(active, observed))
        inventory.mark_unavailable(active.system_id)
        self.assertEqual(
            inventory.devices[active.system_id].control_state,
            DeviceControlState.OFFLINE,
        )
        self.assertEqual(
            inventory.devices[observed.system_id].control_state,
            DeviceControlState.OBSERVATION,
        )

    def test_native_identity_cannot_belong_to_two_systems(self) -> None:
        native = identity("device-1")
        first = MainDevice(system_id="main-1", display_name="One").bind(native)
        second = MainDevice(system_id="main-2", display_name="Two").bind(native)
        with self.assertRaisesRegex(ValueError, "multiple systems"):
            DeviceInventory(devices=(first, second))

    def test_inventory_round_trip_preserves_identity_and_packs(self) -> None:
        main = MainDevice.from_v4_config_entry("entry-1", model="SF2400AC").bind(
            identity("device-1", serial="serial-1")
        )
        inventory = DeviceInventory(
            devices=(main,),
            packs=(BatteryPackIdentity("pack-1", main.system_id, "pack-serial"),),
        )
        restored = DeviceInventory.from_dict(inventory.as_dict())
        self.assertEqual(dict(restored.devices), dict(inventory.devices))
        self.assertEqual(dict(restored.packs), dict(inventory.packs))


if __name__ == "__main__":
    unittest.main()
