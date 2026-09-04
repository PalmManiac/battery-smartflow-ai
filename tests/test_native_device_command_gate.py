"""Contracts for the central native DeviceCommand safety gate."""

from dataclasses import replace
from types import SimpleNamespace
import unittest

from support import bootstrap

bootstrap()

from custom_components.battery_smartflow_ai.core.models import (  # noqa: E402
    BatteryPackIdentity,
    DeviceCommand,
    DeviceControlState,
    DeviceInventory,
    MainDevice,
    MeasuredValue,
    NativeDeviceIdentity,
    ValueValidity,
    ZendureTransport,
)
from custom_components.battery_smartflow_ai.native_device_command_gate import (  # noqa: E402
    NativeCommandContext,
    NativeCommandRequest,
    NativeDeviceCommandGate,
    NativeGateStatus,
    NativeLimitInputs,
)
from custom_components.battery_smartflow_ai.zendure_device_matrix import (  # noqa: E402
    TransportCapability,
    VerificationLevel,
    ZENDURE_DEVICE_MATRIX,
)
from custom_components.battery_smartflow_ai.zendure_hems import (  # noqa: E402
    ZendureHemsCommandGate,
)


DEVICE_ID = "logical-main"
TRANSPORT = ZendureTransport.ZENSDK


def valid(value):
    return MeasuredValue.available(value)


def approved_matrix():
    source = ZENDURE_DEVICE_MATRIX["SF2400AC"]
    transports = dict(source.transports)
    transports[TRANSPORT] = TransportCapability(
        TRANSPORT,
        read=VerificationLevel.VERIFIED,
        write=VerificationLevel.VERIFIED,
        discovery=VerificationLevel.VERIFIED,
    )
    return replace(
        source,
        native_control_approved=True,
        transports=transports,
        writable_main_properties={
            "acMode": VerificationLevel.VERIFIED,
            "inputLimit": VerificationLevel.VERIFIED,
            "outputLimit": VerificationLevel.VERIFIED,
            "minSoc": VerificationLevel.REFERENCE_ONLY,
            "socSet": VerificationLevel.REFERENCE_ONLY,
        },
    )


def main_device(*, active=True, transport=TRANSPORT):
    identity = NativeDeviceIdentity(
        transport,
        device_id="native-secret",
        product_id="BC8B7F",
        product_model="SolarFlow 2400 AC",
    )
    return MainDevice(
        DEVICE_ID,
        "Main",
        model="SolarFlow 2400 AC",
        profile_key="SF2400AC",
        control_state=DeviceControlState.ACTIVE if active else DeviceControlState.OBSERVATION,
        selected_transport=transport,
        available_transports=frozenset({transport}),
        native_identities=(identity,),
    )


def state(*, online=valid(True), protection=valid(False)):
    return SimpleNamespace(online=online, protection_active=protection)


def command(mode="input", input_w=500, output_w=0):
    return DeviceCommand(
        mode,
        input_limit_w=input_w,
        output_limit_w=output_w,
        should_write_mode=True,
        should_write_input=True,
        should_write_output=True,
    )


def context(
    *,
    device=None,
    states=None,
    selected=DEVICE_ID,
    enabled=True,
    available=frozenset({TRANSPORT}),
    **kwargs,
):
    device = device or main_device()
    return NativeCommandContext(
        inventory=DeviceInventory(devices=(device,)),
        states={DEVICE_ID: state()} if states is None else states,
        selected_device_id=selected,
        native_control_enabled=enabled,
        available_transports=available,
        **kwargs,
    )


def ready_gate():
    hems = ZendureHemsCommandGate()
    hems.update(
        DEVICE_ID,
        valid(False),
        capability=VerificationLevel.VERIFIED,
    )
    return NativeDeviceCommandGate(hems, matrix_resolver=lambda _identity: approved_matrix())


class NativeDeviceCommandGateTests(unittest.IsolatedAsyncioTestCase):
    async def test_valid_command_reaches_adapter_with_correlation_id(self):
        gate = ready_gate()
        calls = []

        async def send(authorized):
            calls.append(authorized)
            return "adapter-result"

        result, adapter_result = await gate.execute(
            NativeCommandRequest(DEVICE_ID, TRANSPORT, command()),
            context(),
            send,
        )
        self.assertEqual(result.status, NativeGateStatus.ACCEPTED)
        self.assertEqual(adapter_result, "adapter-result")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].correlation_id, result.correlation_id)
        self.assertIs(calls[0].command, result.command)

    async def test_unknown_device_and_pack_target_never_reach_adapter(self):
        main = main_device()
        inventory = DeviceInventory(
            devices=(main,),
            packs=(BatteryPackIdentity("pack-1", DEVICE_ID),),
        )
        base = replace(context(), inventory=inventory)
        for target, reason in (
            ("missing", "unknown_device"),
            ("pack-1", "pack_not_command_target"),
        ):
            called = []

            async def send(_authorized):
                called.append(True)

            result, _ = await ready_gate().execute(
                NativeCommandRequest(target, TRANSPORT, command()), base, send
            )
            self.assertIn(reason, result.reasons)
            self.assertEqual(called, [])

    async def test_production_matrix_is_fail_closed(self):
        hems = ZendureHemsCommandGate()
        hems.update(DEVICE_ID, valid(False), capability=VerificationLevel.VERIFIED)
        gate = NativeDeviceCommandGate(hems)
        result = gate.evaluate(
            NativeCommandRequest(DEVICE_ID, TRANSPORT, command()), context()
        )
        self.assertFalse(result.accepted)
        self.assertIn("device_profile_not_approved", result.reasons)
        self.assertIn("transport_write_not_verified", result.reasons)

    async def test_control_selection_and_active_state_are_independent_blockers(self):
        result = ready_gate().evaluate(
            NativeCommandRequest(DEVICE_ID, TRANSPORT, command()),
            context(device=main_device(active=False), selected="other", enabled=False),
        )
        self.assertIn("control_disabled", result.reasons)
        self.assertIn("device_not_selected", result.reasons)
        self.assertIn("device_not_active", result.reasons)

    async def test_no_device_or_transport_fallback(self):
        wrong_transport = ZendureTransport.CLOUD_MQTT
        result = ready_gate().evaluate(
            NativeCommandRequest(DEVICE_ID, wrong_transport, command()),
            context(available=frozenset({wrong_transport})),
        )
        self.assertIn("transport_not_selected", result.reasons)
        self.assertIn("transport_not_available_for_device", result.reasons)
        self.assertIsNone(result.command)

    async def test_selected_transport_identity_is_resolved_not_first_identity(self):
        device = main_device()
        cloud_identity = NativeDeviceIdentity(
            ZendureTransport.CLOUD_MQTT,
            device_id="cloud-native-secret",
            product_model="Unknown device",
        )
        device = replace(
            device,
            native_identities=(cloud_identity, *device.native_identities),
            available_transports=frozenset(
                {ZendureTransport.CLOUD_MQTT, ZendureTransport.ZENSDK}
            ),
        )
        result = ready_gate().evaluate(
            NativeCommandRequest(DEVICE_ID, TRANSPORT, command()),
            context(device=device),
        )
        self.assertTrue(result.accepted)

    async def test_offline_invalid_and_protection_states_fail_closed(self):
        cases = (
            (state(online=valid(False)), "device_offline"),
            (state(online=MeasuredValue.absent(ValueValidity.STALE)), "device_online_stale"),
            (state(protection=valid(True)), "protection_active"),
            (
                state(protection=MeasuredValue.absent(ValueValidity.INVALID)),
                "protection_state_invalid",
            ),
        )
        for current, reason in cases:
            result = ready_gate().evaluate(
                NativeCommandRequest(DEVICE_ID, TRANSPORT, command()),
                context(states={DEVICE_ID: current}),
            )
            self.assertIn(reason, result.reasons)
            self.assertFalse(result.accepted)

    async def test_hems_active_unknown_and_stale_block_at_central_gate(self):
        for measured, reason in (
            (valid(True), "zendure_hems_active"),
            (MeasuredValue.absent(ValueValidity.NEVER_RECEIVED), "zendure_hems_unknown"),
            (MeasuredValue.absent(ValueValidity.STALE), "zendure_hems_stale"),
        ):
            hems = ZendureHemsCommandGate()
            hems.update(DEVICE_ID, measured, capability=VerificationLevel.VERIFIED)
            result = NativeDeviceCommandGate(
                hems, matrix_resolver=lambda _identity: approved_matrix()
            ).evaluate(NativeCommandRequest(DEVICE_ID, TRANSPORT, command()), context())
            self.assertIn(reason, result.reasons)
            self.assertFalse(result.accepted)

    async def test_profile_runtime_and_dynamic_limits_only_lower_target(self):
        result = ready_gate().evaluate(
            NativeCommandRequest(DEVICE_ID, TRANSPORT, command(input_w=3000)),
            context(
                limits=NativeLimitInputs(
                    input_limit_w=valid(1800),
                    dynamic_input_limit_w=valid(1200),
                )
            ),
        )
        self.assertEqual(result.status, NativeGateStatus.ACCEPTED_CLAMPED)
        self.assertEqual(result.command.input_limit_w, 1200)
        self.assertEqual(result.requested["input_limit_w"], 3000)
        self.assertEqual(result.final["input_limit_w"], 1200)

    async def test_valid_zero_is_not_treated_as_missing(self):
        result = ready_gate().evaluate(
            NativeCommandRequest(DEVICE_ID, TRANSPORT, command(input_w=0)), context()
        )
        self.assertTrue(result.accepted)
        self.assertEqual(result.command.input_limit_w, 0)

    async def test_invalid_direction_and_values_are_blocked_not_clamped(self):
        bad_direction = command(mode="input", output_w=50)
        bad_value = command(input_w=-1)
        for item in (bad_direction, bad_value):
            result = ready_gate().evaluate(
                NativeCommandRequest(DEVICE_ID, TRANSPORT, item), context()
            )
            self.assertEqual(result.status, NativeGateStatus.INVALID)
            self.assertIsNone(result.command)

    async def test_required_stale_limit_is_not_replaced_with_zero(self):
        result = ready_gate().evaluate(
            NativeCommandRequest(DEVICE_ID, TRANSPORT, command()),
            context(
                limits=NativeLimitInputs(
                    dynamic_input_limit_w=MeasuredValue.absent(ValueValidity.STALE),
                    required_validity=True,
                )
            ),
        )
        self.assertIn("dynamic_input_limit_stale", result.reasons)
        self.assertIsNone(result.final)

    async def test_soc_commands_require_explicit_capability_and_valid_interval(self):
        soc_command = command(input_w=0)
        soc_command.should_write_min_soc = True
        soc_command.should_write_max_soc = True
        soc_command.min_soc_pct = 10
        soc_command.max_soc_pct = 90
        blocked = ready_gate().evaluate(
            NativeCommandRequest(DEVICE_ID, TRANSPORT, soc_command), context()
        )
        self.assertIn("command_capability_unsupported:minSoc", blocked.reasons)
        self.assertIn("command_capability_unsupported:socSet", blocked.reasons)

        invalid = replace(soc_command, min_soc_pct=95, max_soc_pct=90)
        result = ready_gate().evaluate(
            NativeCommandRequest(DEVICE_ID, TRANSPORT, invalid), context()
        )
        self.assertEqual(result.status, NativeGateStatus.INVALID)
        self.assertIn("invalid_soc_interval", result.reasons)

    async def test_migration_writer_conflict_and_stale_runtime_are_named(self):
        result = ready_gate().evaluate(
            NativeCommandRequest(DEVICE_ID, TRANSPORT, command()),
            context(
                migration_blocked=True,
                writer_conflict=True,
                required_state_valid=False,
            ),
        )
        self.assertIn("migration_blocked", result.reasons)
        self.assertIn("writer_conflict", result.reasons)
        self.assertIn("required_state_stale", result.reasons)

    async def test_diagnostics_exclude_command_metadata_and_native_identity(self):
        item = command()
        item.metadata = {"password": "secret", "serial": "native-secret"}
        result = ready_gate().evaluate(
            NativeCommandRequest(DEVICE_ID, TRANSPORT, item), context()
        )
        text = repr(result.diagnostics())
        self.assertNotIn("password", text)
        self.assertNotIn("secret", text)
        self.assertNotIn("native-secret", text)
        self.assertIn(result.correlation_id, text)


if __name__ == "__main__":
    unittest.main()
