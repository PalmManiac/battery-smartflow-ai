"""Productive neutral DeviceCommand to native Cloud backend contracts."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from types import ModuleType, SimpleNamespace

from support import bootstrap

bootstrap()

helpers_module = ModuleType("homeassistant.helpers")
aiohttp_module = ModuleType("homeassistant.helpers.aiohttp_client")
aiohttp_module.async_get_clientsession = lambda _hass: None
sys.modules.setdefault("homeassistant.helpers", helpers_module)
sys.modules.setdefault("homeassistant.helpers.aiohttp_client", aiohttp_module)

from custom_components.battery_smartflow_ai.core.models import (  # noqa: E402
    CommandExecutionStatus,
    DeviceCommand,
    DeviceInventory,
    DeviceOperatingMode,
    MainDevice,
    MeasuredValue,
    NativeDeviceIdentity,
    ReportedDeviceSetpoints,
    ZendureTransport,
)
from custom_components.battery_smartflow_ai.native_command_verification import (  # noqa: E402
    CommandVerificationStatus,
    ReadbackPolicy,
)
from custom_components.battery_smartflow_ai.native_zendure_runtime import (  # noqa: E402
    STATUS_OBSERVING,
    NativeZendureRuntime,
)
from custom_components.battery_smartflow_ai.zendure_cloud_mqtt import (
    ConnectionState,  # noqa: E402
)
from custom_components.battery_smartflow_ai.zendure_cloud_mqtt_commands import (  # noqa: E402
    CloudCommandResult,
    CloudCommandStatus,
)
from custom_components.battery_smartflow_ai.zendure_device_matrix import (
    VerificationLevel,  # noqa: E402
)
from custom_components.battery_smartflow_ai.zendure_local_mqtt_commands import (  # noqa: E402
    LocalMqttCommandResult,
    LocalMqttCommandStatus,
)
from custom_components.battery_smartflow_ai.zendure_zensdk_commands import (  # noqa: E402
    ZenSdkCommandResult,
    ZenSdkCommandStatus,
)

DEVICE = "cloud_mqtt:main-1"
NOW = datetime.now(timezone.utc)


def measured(value):
    return MeasuredValue.available(value, observed_at=NOW)


def state(*, input_w=0, output_w=0, charge_w=0, discharge_w=0, hems=False):
    return SimpleNamespace(
        online=measured(True),
        protection_active=measured(False),
        hems_active=measured(hems),
        charge_power_w=measured(charge_w),
        discharge_power_w=measured(discharge_w),
        last_message_at=NOW,
        packs=(),
        observed_transport=ZendureTransport.ZENSDK,
        mode=measured(DeviceOperatingMode.DISCHARGE),
        setpoints=ReportedDeviceSetpoints(
            measured(input_w), measured(output_w), measured(2400),
            measured(2400), measured(10), measured(100),
        ),
        offgrid_power_w=measured(0),
    )


class FakeTransport:
    state = ConnectionState.CONNECTED
    command_diagnostics = {"commands": []}
    last_message_at = None

    def __init__(self):
        self.commands = []

    async def async_execute_authorized(self, authorized):
        self.commands.append(authorized)
        return CloudCommandResult(CloudCommandStatus.SENT, "awaiting_readback", ("id",), 1)


class FakeZenSdkAdapter:
    def __init__(self):
        self.commands = []

    async def execute(self, authorized):
        self.commands.append(authorized)
        return ZenSdkCommandResult(
            status=ZenSdkCommandStatus.SENT,
            reason="awaiting_readback",
            verification_ids=("zen-id",),
            writes_sent=4,
            requests_sent=1,
            http_status=200,
        )


class FakeLocalTransport:
    state = ConnectionState.CONNECTED
    command_diagnostics = {"commands": []}

    def __init__(self):
        self.commands = []
        self.device_states = {
            DEVICE: SimpleNamespace(last_message_at=NOW, online=True)
        }

    async def async_execute_authorized(self, authorized):
        self.commands.append(authorized)
        return LocalMqttCommandResult(
            LocalMqttCommandStatus.SENT,
            "awaiting_readback",
            ("local-id",),
            1,
        )


def runtime(*, enabled=True, current_state=None):
    result = NativeZendureRuntime(
        SimpleNamespace(), app_token="configured", selected_device=DEVICE,
        notify=lambda: None, control_enabled=enabled,
    )
    identity = NativeDeviceIdentity(
        ZendureTransport.CLOUD_MQTT, device_id="main-1",
        product_id="product-a", product_model="SolarFlow 2400 AC",
    )
    result._inventory = DeviceInventory(devices=(MainDevice(
        DEVICE, "Main", model="SolarFlow 2400 AC", profile_key="SF2400AC",
        selected_transport=ZendureTransport.CLOUD_MQTT,
        available_transports=frozenset({ZendureTransport.CLOUD_MQTT}),
        native_identities=(identity,),
    ),))
    result._states[DEVICE] = current_state or state()
    result._hems_gate.update(
        DEVICE, result._states[DEVICE].hems_active,
        capability=VerificationLevel.VERIFIED,
    )
    result._status = STATUS_OBSERVING
    result._transport = FakeTransport()
    result._bootstrap = SimpleNamespace()
    result._zensdk_command_adapter = FakeZenSdkAdapter()
    result._zensdk_last_success[DEVICE] = NOW
    result._zensdk_failures[DEVICE] = 0
    return result


def legacy_runtime(*, current_state=None):
    result = runtime(current_state=current_state)
    identity = NativeDeviceIdentity(
        ZendureTransport.CLOUD_MQTT,
        device_id="main-1",
        product_id="product-a",
        product_model="Hyper 2000",
    )
    result._inventory = DeviceInventory(devices=(MainDevice(
        DEVICE, "Legacy", model="Hyper 2000", profile_key="Hyper 2000",
        selected_transport=ZendureTransport.CLOUD_MQTT,
        available_transports=frozenset({ZendureTransport.CLOUD_MQTT}),
        native_identities=(identity,),
    ),))
    result._local_transport = FakeLocalTransport()
    return result


class NativePowerControllerTests(unittest.IsolatedAsyncioTestCase):
    async def test_native_effectiveness_confirms_physical_effect_separately(self):
        target = runtime()
        verification = target._command_verification.prepare(
            device_id=DEVICE,
            command_type="outputLimit",
            target_key="outputLimit",
            transport=ZendureTransport.ZENSDK,
            requested_value=450,
            final_value=450,
            readback=ReadbackPolicy("outputLimit", 450),
            prepared_at=NOW - timedelta(seconds=3),
        )
        target._command_verification.gate(
            verification.command_id,
            accepted=True,
            at=NOW - timedelta(seconds=2.9),
        )
        target._command_verification.sent(
            verification.command_id,
            at=NOW - timedelta(seconds=2.8),
        )
        target._command_verification.transport_result(
            verification.command_id,
            ok=True,
            at=NOW - timedelta(seconds=2.7),
        )
        target._command_verification.observe_readback(
            verification.command_id,
            device_id=DEVICE,
            property_name="outputLimit",
            value=450,
            observed_at=NOW - timedelta(seconds=2),
        )

        confirmed = target.observe_command_effectiveness(
            direction="output",
            status="effective",
            observed_at=NOW,
        )

        self.assertTrue(confirmed)
        self.assertEqual(
            verification.status,
            CommandVerificationStatus.EFFECT_CONFIRMED,
        )
        self.assertEqual(
            verification.diagnostics()["send_to_effect_seconds"],
            2.8,
        )

    async def test_legacy_device_routes_exactly_once_to_local_mqtt(self):
        target = legacy_runtime()

        result = await target.async_execute_device_command(DeviceCommand(
            "output", output_limit_w=450, should_write_output=True,
        ))

        self.assertEqual(result.status, CommandExecutionStatus.APPLIED)
        self.assertEqual(len(target._local_transport.commands), 1)
        self.assertEqual(target._zensdk_command_adapter.commands, [])
        self.assertEqual(target._transport.commands, [])
        self.assertEqual(
            target.sensor_data()["native_zendure_control"],
            "native_local_mqtt_active",
        )

    async def test_stale_local_mqtt_never_falls_back(self):
        target = legacy_runtime()
        target._local_transport.device_states[DEVICE].last_message_at = (
            NOW - timedelta(minutes=5)
        )

        result = await target.async_execute_device_command(DeviceCommand(
            "output", output_limit_w=450, should_write_output=True,
        ))

        self.assertEqual(result.status, CommandExecutionStatus.SKIPPED)
        self.assertEqual(result.reason, "native_local_mqtt_not_ready")
        self.assertEqual(target._local_transport.commands, [])
        self.assertEqual(target._zensdk_command_adapter.commands, [])
        self.assertEqual(target._transport.commands, [])

    async def test_conflicting_model_families_never_select_a_writer(self):
        target = runtime()
        current = target._inventory.devices[DEVICE]
        legacy = NativeDeviceIdentity(
            ZendureTransport.CLOUD_MQTT,
            device_id="legacy-alias",
            product_model="Hyper 2000",
        )
        target._inventory = DeviceInventory(devices=(MainDevice(
            current.system_id,
            current.display_name,
            model=current.model,
            profile_key=current.profile_key,
            selected_transport=current.selected_transport,
            available_transports=current.available_transports,
            native_identities=(*current.native_identities, legacy),
        ),))

        result = await target.async_execute_device_command(DeviceCommand(
            "output", output_limit_w=450, should_write_output=True,
        ))

        self.assertEqual(result.status, CommandExecutionStatus.SKIPPED)
        self.assertEqual(result.reason, "native_local_transport_ambiguous")
        self.assertEqual(target._zensdk_command_adapter.commands, [])
        self.assertEqual(target._transport.commands, [])

    async def test_disconnect_revokes_authority_without_cloud_or_zha_fallback(self):
        target = runtime()
        command = DeviceCommand(
            "output", output_limit_w=450, should_write_output=True,
        )
        applied = await target.async_execute_device_command(command)
        initial_generation = target._transport_router.snapshot.generation
        target._zensdk_last_success[DEVICE] = NOW - timedelta(minutes=5)

        blocked = await target.async_execute_device_command(command)

        self.assertEqual(applied.status, CommandExecutionStatus.APPLIED)
        self.assertEqual(blocked.reason, "native_zensdk_not_ready")
        self.assertGreater(
            target._transport_router.snapshot.generation,
            initial_generation,
        )
        self.assertEqual(len(target._zensdk_command_adapter.commands), 1)
        self.assertEqual(target._transport.commands, [])
    async def test_fresh_running_setpoint_is_consumed_once_as_handover_baseline(self):
        target = runtime(current_state=state(output_w=950, discharge_w=947))

        self.assertEqual(
            target.consume_control_baseline(),
            ("output", 0, 950),
        )
        self.assertIsNone(target.consume_control_baseline())

    async def test_disabled_control_never_exposes_handover_baseline(self):
        target = runtime(
            enabled=False,
            current_state=state(output_w=950, discharge_w=947),
        )

        self.assertIsNone(target.consume_control_baseline())

    async def test_output_uses_only_explicitly_selected_zensdk_transport(self):
        target = runtime()

        result = await target.async_execute_device_command(DeviceCommand(
            "output", output_limit_w=250, should_write_mode=False,
            should_write_input=False, should_write_output=True,
        ))

        self.assertEqual(result.status, CommandExecutionStatus.APPLIED)
        self.assertEqual(len(target._zensdk_command_adapter.commands), 1)
        command = target._zensdk_command_adapter.commands[0]
        self.assertEqual(command.device_id, DEVICE)
        self.assertEqual(command.transport, ZendureTransport.ZENSDK)
        self.assertEqual(target._transport.commands, [])
        self.assertEqual(
            target.sensor_data()["native_zendure_control"],
            "native_zensdk_active",
        )

    async def test_verified_zensdk_directional_sequence_reaches_adapter(self):
        target = runtime()

        result = await target.async_execute_device_command(DeviceCommand(
            "input", input_limit_w=300, output_limit_w=0,
            should_write_mode=True, should_write_input=True,
            should_write_output=True,
        ))

        self.assertEqual(result.status, CommandExecutionStatus.APPLIED)
        self.assertEqual(len(target._zensdk_command_adapter.commands), 1)
        command = target._zensdk_command_adapter.commands[0].command
        self.assertEqual(command.ac_mode, "input")
        self.assertEqual(command.metadata["native_offgrid_power_w"], 0.0)
        self.assertEqual(target._transport.commands, [])

    async def test_unavailable_zensdk_never_falls_back_to_cloud(self):
        target = runtime()
        target._zensdk_last_success[DEVICE] = NOW - timedelta(minutes=5)

        result = await target.async_execute_device_command(DeviceCommand(
            "output", output_limit_w=250, should_write_mode=False,
            should_write_input=False, should_write_output=True,
        ))

        self.assertEqual(result.status, CommandExecutionStatus.SKIPPED)
        self.assertEqual(result.reason, "native_zensdk_not_ready")
        self.assertEqual(target._zensdk_command_adapter.commands, [])
        self.assertEqual(target._transport.commands, [])

    async def test_output_command_reaches_exact_local_device(self):
        target = runtime()
        result = await target.async_execute_device_command(DeviceCommand(
            "output", output_limit_w=250, should_write_mode=False,
            should_write_input=False, should_write_output=True,
        ))
        self.assertEqual(result.status, CommandExecutionStatus.APPLIED)
        self.assertTrue(result.output_written)
        self.assertEqual(len(target._zensdk_command_adapter.commands), 1)
        self.assertEqual(target._zensdk_command_adapter.commands[0].device_id, DEVICE)
        self.assertEqual(target._zensdk_command_adapter.commands[0].transport, ZendureTransport.ZENSDK)
        self.assertEqual(target._transport.commands, [])

    async def test_idle_zero_keeps_neutral_semantics(self):
        stop_target = runtime(current_state=state(output_w=100))
        stopped = await stop_target.async_execute_device_command(DeviceCommand(
            "output", output_limit_w=0, should_write_mode=False,
            should_write_input=False, should_write_output=True,
        ))
        self.assertEqual(stopped.status, CommandExecutionStatus.APPLIED)
        self.assertEqual(
            stop_target._zensdk_command_adapter.commands[-1].command.output_limit_w,
            0,
        )

    async def test_no_change_never_writes(self):
        target = runtime(current_state=state(output_w=250, discharge_w=250))
        result = await target.async_execute_device_command(DeviceCommand(
            "output", output_limit_w=250, should_write_mode=True,
            should_write_input=False, should_write_output=True,
        ))
        self.assertEqual(result.status, CommandExecutionStatus.SKIPPED)
        self.assertEqual(result.reason, "native_setpoints_unchanged")
        self.assertEqual(target._zensdk_command_adapter.commands, [])

    async def test_matching_stored_limit_restarts_inactive_direction(self):
        target = runtime(current_state=state(output_w=250, discharge_w=0))
        result = await target.async_execute_device_command(DeviceCommand(
            "output", output_limit_w=250, should_write_mode=False,
            should_write_input=False, should_write_output=False,
            skipped=True, skip_reason="unchanged_within_tolerance",
        ))
        self.assertEqual(result.status, CommandExecutionStatus.APPLIED)
        command = target._zensdk_command_adapter.commands[-1].command
        self.assertTrue(command.should_write_output)
        self.assertFalse(command.skipped)

    async def test_confirmed_inactive_hems_remains_usable_after_quiet_window(self):
        current = state(output_w=250, discharge_w=0)
        current.hems_active = MeasuredValue.available(
            False, observed_at=NOW - timedelta(minutes=5)
        )
        target = runtime(current_state=current)

        result = await target.async_execute_device_command(DeviceCommand(
            "output", output_limit_w=250, should_write_mode=False,
            should_write_input=False, should_write_output=False,
            skipped=True, skip_reason="unchanged_within_tolerance",
        ))

        self.assertEqual(result.status, CommandExecutionStatus.APPLIED)
        self.assertEqual(len(target._zensdk_command_adapter.commands), 1)

    async def test_stale_online_or_protection_state_still_blocks_commands(self):
        for field in ("online", "protection_active"):
            with self.subTest(field=field):
                current = state(output_w=250, discharge_w=0)
                setattr(
                    current,
                    field,
                    MeasuredValue.available(
                        field == "online",
                        observed_at=NOW - timedelta(minutes=5),
                    ),
                )
                target = runtime(current_state=current)

                result = await target.async_execute_device_command(DeviceCommand(
                    "output", output_limit_w=250, should_write_mode=False,
                    should_write_input=False, should_write_output=True,
                ))

                self.assertEqual(result.status, CommandExecutionStatus.SKIPPED)
                self.assertEqual(result.reason, "native_state_not_fresh")
                self.assertEqual(target._zensdk_command_adapter.commands, [])

    async def test_last_dispatch_reason_is_visible_without_identity(self):
        target = runtime(current_state=state(output_w=250, discharge_w=250))
        await target.async_execute_device_command(DeviceCommand(
            "output", output_limit_w=250, should_write_mode=False,
            should_write_input=False, should_write_output=False,
            skipped=True, skip_reason="unchanged_within_tolerance",
        ))
        diagnostic = target.diagnostic_data()["last_command_result"]
        self.assertEqual(diagnostic["status"], "skipped")
        self.assertEqual(diagnostic["reason"], "native_setpoints_unchanged")
        self.assertNotIn(DEVICE, repr(diagnostic))

    async def test_profile_limit_is_clamped_only_by_central_gate(self):
        target = runtime()
        result = await target.async_execute_device_command(DeviceCommand(
            "output", output_limit_w=3000, should_write_mode=False,
            should_write_input=False, should_write_output=True,
        ))
        self.assertEqual(result.status, CommandExecutionStatus.APPLIED)
        self.assertEqual(
            target._zensdk_command_adapter.commands[-1].command.output_limit_w,
            2400,
        )

    async def test_disabled_hems_disconnect_and_restart_state_fail_closed(self):
        disabled = runtime(enabled=False)
        result = await disabled.async_execute_device_command(DeviceCommand("output"))
        self.assertEqual(result.reason, "native_control_disabled")
        self.assertEqual(disabled._zensdk_command_adapter.commands, [])

        blocked = runtime(current_state=state(hems=True))
        result = await blocked.async_execute_device_command(DeviceCommand(
            "output", output_limit_w=10, should_write_mode=False,
            should_write_input=False, should_write_output=True,
        ))
        self.assertIn("zendure_hems_active", result.reason)
        self.assertEqual(blocked._zensdk_command_adapter.commands, [])

        disconnected = runtime()
        disconnected._zensdk_last_success[DEVICE] = NOW - timedelta(minutes=5)
        result = await disconnected.async_execute_device_command(DeviceCommand("output"))
        self.assertEqual(result.reason, "native_zensdk_not_ready")

        restarting = runtime()
        restarting._status = "connecting"
        result = await restarting.async_execute_device_command(DeviceCommand("output"))
        self.assertEqual(result.reason, "native_transport_not_ready")


if __name__ == "__main__":
    unittest.main()
