"""Hierarchical, privacy-safe native device overview tests."""

from datetime import datetime, timezone
from types import SimpleNamespace
import unittest

from support import bootstrap

bootstrap()

from custom_components.battery_smartflow_ai.core.models import (  # noqa: E402
    BatteryPackIdentity, DeviceControlState, DeviceInventory, HemsStatus, MainDevice,
    MeasuredValue, NativeDeviceIdentity, ZendureTransport,
)
from custom_components.battery_smartflow_ai.native_device_overview import (  # noqa: E402
    build_native_device_overview,
)


def measured(value):
    return MeasuredValue.available(value)


def observed_pack(pack_id, parent):
    values = dict(
        pack_id=pack_id, parent_system_id=parent, firmware=measured("1.2.3"),
        soc_pct=measured(55.0), charge_power_w=measured(100.0),
        discharge_power_w=measured(0.0), voltage_v=measured(49.5),
        current_a=measured(2.0), cell_min_v=measured(3.29),
        cell_max_v=measured(3.31), temperature_c=measured(25.0),
        state_code=measured(1), fault_code=measured(0),
        protection_active=measured(False),
        last_message_at=datetime(2026, 9, 2, tzinfo=timezone.utc),
    )
    return SimpleNamespace(**values)


class NativeDeviceOverviewTests(unittest.TestCase):
    def test_multiple_systems_and_duplicate_names_remain_separate(self):
        inventory = DeviceInventory(devices=(
            MainDevice("main-secret-a", "Battery", model="SF2400AC"),
            MainDevice("main-secret-b", "Battery", model="SF800Pro"),
        ))
        overview = build_native_device_overview(inventory, {})
        self.assertEqual(len(overview), 2)
        self.assertNotEqual(overview[0].public_id, overview[1].public_id)
        self.assertEqual({item.display_name for item in overview}, {"Battery"})

    def test_unknown_pack_model_keeps_verified_measurements(self):
        main = MainDevice("main-secret", "Main")
        inventory = DeviceInventory(
            devices=(main,),
            packs=(BatteryPackIdentity("pack-secret", main.system_id),),
        )
        state = SimpleNamespace(
            packs=(observed_pack("pack-secret", main.system_id),),
            firmware=measured("2.0.0"), soc_pct=measured(55.0),
            charge_power_w=measured(100.0), discharge_power_w=measured(0.0),
            ac_input_power_w=measured(0.0), ac_output_power_w=measured(100.0),
            pv_power_w=measured(250.0), mode=measured("charge"),
            fault_code=measured(0), protection_active=measured(False),
            temperature_c=measured(25.0), battery_voltage_v=measured(49.5),
            last_message_at=datetime(2026, 9, 2, tzinfo=timezone.utc),
        )
        item = build_native_device_overview(inventory, {main.system_id: state})[0]
        self.assertEqual(len(item.packs), 1)
        self.assertIsNone(item.packs[0].pack_model)
        self.assertEqual(item.packs[0].measurements["soc_pct"].value, 55.0)
        self.assertFalse(hasattr(item.packs[0], "capacity"))
        self.assertFalse(hasattr(item.packs[0], "cell_count"))
        self.assertEqual(item.packs[0].parent_public_id, item.public_id)

    def test_numeric_pack_type_is_not_exposed_as_a_model_name(self):
        main = MainDevice("main-secret", "SolarFlow 2400 AC")
        inventory = DeviceInventory(
            devices=(main,),
            packs=(BatteryPackIdentity("pack-secret", main.system_id, pack_type="5"),),
        )
        state = SimpleNamespace(
            packs=(observed_pack("pack-secret", main.system_id),),
            last_message_at=None,
        )
        pack = build_native_device_overview(
            inventory, {main.system_id: state}
        )[0].packs[0]
        self.assertIsNone(pack.pack_model)

    def test_sensitive_full_identifiers_never_enter_projection(self):
        identity = NativeDeviceIdentity(
            ZendureTransport.CLOUD_MQTT,
            device_id="full-device-secret",
            serial_number="full-serial-secret",
            product_id="BC8B7F",
            product_model="SolarFlow2400AC",
        )
        main = MainDevice(
            "logical-system-secret", "Allowed display name",
            native_identities=(identity,),
            selected_transport=ZendureTransport.CLOUD_MQTT,
            available_transports=frozenset({ZendureTransport.CLOUD_MQTT}),
        )
        text = repr(build_native_device_overview(DeviceInventory(devices=(main,)), {}))
        self.assertNotIn("full-device-secret", text)
        self.assertNotIn("full-serial-secret", text)
        self.assertNotIn("logical-system-secret", text)
        self.assertIn("BC8B7F", text)

    def test_management_states_are_visible_and_control_defaults_off(self):
        devices = tuple(
            MainDevice(
                f"main-{state.value}", state.value,
                supported=state is not DeviceControlState.UNSUPPORTED,
                online=state is not DeviceControlState.OFFLINE,
                hems_active=state is DeviceControlState.HEMS_BLOCKED,
                control_state=state,
            )
            for state in (
                DeviceControlState.OBSERVATION,
                DeviceControlState.HEMS_BLOCKED,
                DeviceControlState.UNSUPPORTED,
                DeviceControlState.OFFLINE,
            )
        )
        overview = build_native_device_overview(DeviceInventory(devices=devices), {})
        self.assertTrue(all(not item.control_enabled for item in overview))
        self.assertTrue(any("HEMS active" in item.status_text for item in overview))
        self.assertTrue(any("not supported" in item.status_text for item in overview))

    def test_disappeared_pack_and_device_do_not_trigger_failover(self):
        active = MainDevice.from_v4_config_entry("entry")
        other = MainDevice("other", "Other")
        inventory = DeviceInventory(devices=(active, other))
        inventory.mark_unavailable(active.system_id)
        overview = build_native_device_overview(inventory, {})
        by_name = {item.display_name: item for item in overview}
        self.assertFalse(by_name["Battery SmartFlow AI"].actively_controlled)
        self.assertFalse(by_name["Other"].actively_controlled)

    def test_hems_quality_and_block_reason_are_visible_per_device(self):
        main = MainDevice("main", "Main")
        inventory = DeviceInventory(devices=(main,))
        observed_at = datetime(2026, 9, 4, tzinfo=timezone.utc)
        inventory.set_hems_status(
            main.system_id,
            HemsStatus.STALE,
            observed_at=observed_at,
        )
        item = build_native_device_overview(inventory, {})[0]
        self.assertEqual(item.hems_status, HemsStatus.STALE)
        self.assertEqual(item.hems_observed_at, observed_at)
        self.assertEqual(item.control_block_reason, "zendure_hems_stale")
        self.assertIn("status stale", item.status_text)

    def test_fresh_data_preserves_online_state_but_offline_recovery_is_passive(self):
        active = MainDevice.from_v4_config_entry("entry")
        inventory = DeviceInventory(devices=(active,))

        inventory.mark_available(active.system_id)
        self.assertEqual(
            inventory.devices[active.system_id].control_state,
            DeviceControlState.ACTIVE,
        )

        inventory.mark_unavailable(active.system_id)
        inventory.mark_available(active.system_id)
        recovered = inventory.devices[active.system_id]
        self.assertTrue(recovered.online)
        self.assertEqual(recovered.control_state, DeviceControlState.OBSERVATION)


if __name__ == "__main__":
    unittest.main()
