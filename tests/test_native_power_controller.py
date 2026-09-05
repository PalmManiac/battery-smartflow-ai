"""Productive neutral DeviceCommand to native Cloud backend contracts."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sys
from types import ModuleType
from types import SimpleNamespace
import unittest

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
from custom_components.battery_smartflow_ai.native_zendure_runtime import (  # noqa: E402
    NativeZendureRuntime,
    STATUS_OBSERVING,
)
from custom_components.battery_smartflow_ai.zendure_cloud_mqtt import ConnectionState  # noqa: E402
from custom_components.battery_smartflow_ai.zendure_cloud_mqtt_commands import (  # noqa: E402
    CloudCommandResult,
    CloudCommandStatus,
)
from custom_components.battery_smartflow_ai.zendure_device_matrix import VerificationLevel  # noqa: E402
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
            ZenSdkCommandStatus.SENT, "awaiting_readback", ("zen-id",), 1, 200
        )


def runtime(*, enabled=True, current_state=None, control_transport="cloud_mqtt"):
    result = NativeZendureRuntime(
        SimpleNamespace(), app_token="configured", selected_device=DEVICE,
        notify=lambda: None, control_enabled=enabled,
        control_transport=control_transport,
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
    if control_transport == "zensdk":
        result._bootstrap = SimpleNamespace()
        result._zensdk_command_adapter = FakeZenSdkAdapter()
        result._zensdk_last_success[DEVICE] = NOW
        result._zensdk_failures[DEVICE] = 0
    return result


class NativePowerControllerTests(unittest.IsolatedAsyncioTestCase):
    async def test_output_uses_only_explicitly_selected_zensdk_transport(self):
        target = runtime(control_transport="zensdk")

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

    async def test_unverified_zensdk_sequence_is_blocked_without_any_write(self):
        target = runtime(control_transport="zensdk")

        result = await target.async_execute_device_command(DeviceCommand(
            "input", input_limit_w=300, output_limit_w=0,
            should_write_mode=True, should_write_input=True,
            should_write_output=True,
        ))

        self.assertEqual(result.status, CommandExecutionStatus.SKIPPED)
        self.assertIn("command_capability_unsupported:acMode", result.reason)
        self.assertEqual(target._zensdk_command_adapter.commands, [])
        self.assertEqual(target._transport.commands, [])

    async def test_unavailable_zensdk_never_falls_back_to_cloud(self):
        target = runtime(control_transport="zensdk")
        target._zensdk_last_success[DEVICE] = NOW - timedelta(minutes=5)

        result = await target.async_execute_device_command(DeviceCommand(
            "output", output_limit_w=250, should_write_mode=False,
            should_write_input=False, should_write_output=True,
        ))

        self.assertEqual(result.status, CommandExecutionStatus.SKIPPED)
        self.assertEqual(result.reason, "native_zensdk_not_ready")
        self.assertEqual(target._zensdk_command_adapter.commands, [])
        self.assertEqual(target._transport.commands, [])

    async def test_output_command_reaches_exact_cloud_device(self):
        target = runtime()
        result = await target.async_execute_device_command(DeviceCommand(
            "output", output_limit_w=250, should_write_mode=False,
            should_write_input=False, should_write_output=True,
        ))
        self.assertEqual(result.status, CommandExecutionStatus.APPLIED)
        self.assertTrue(result.output_written)
        self.assertEqual(len(target._transport.commands), 1)
        self.assertEqual(target._transport.commands[0].device_id, DEVICE)
        self.assertEqual(target._transport.commands[0].transport, ZendureTransport.CLOUD_MQTT)

    async def test_input_and_idle_zero_keep_neutral_semantics(self):
        target = runtime(current_state=state(input_w=0, output_w=100))
        charge = await target.async_execute_device_command(DeviceCommand(
            "input", input_limit_w=300, output_limit_w=0,
            should_write_mode=True, should_write_input=True,
            should_write_output=True,
        ))
        self.assertEqual(charge.status, CommandExecutionStatus.APPLIED)
        command = target._transport.commands[-1].command
        self.assertEqual(command.input_limit_w, 300)
        self.assertEqual(command.output_limit_w, 0)
        stop_target = runtime(current_state=state(output_w=100))
        stopped = await stop_target.async_execute_device_command(DeviceCommand(
            "output", output_limit_w=0, should_write_mode=False,
            should_write_input=False, should_write_output=True,
        ))
        self.assertEqual(stopped.status, CommandExecutionStatus.APPLIED)
        self.assertEqual(stop_target._transport.commands[-1].command.output_limit_w, 0)

    async def test_no_change_never_writes(self):
        target = runtime(current_state=state(output_w=250, discharge_w=250))
        result = await target.async_execute_device_command(DeviceCommand(
            "output", output_limit_w=250, should_write_mode=True,
            should_write_input=False, should_write_output=True,
        ))
        self.assertEqual(result.status, CommandExecutionStatus.SKIPPED)
        self.assertEqual(result.reason, "native_setpoints_unchanged")
        self.assertEqual(target._transport.commands, [])

    async def test_matching_stored_limit_restarts_inactive_direction(self):
        target = runtime(current_state=state(output_w=250, discharge_w=0))
        result = await target.async_execute_device_command(DeviceCommand(
            "output", output_limit_w=250, should_write_mode=False,
            should_write_input=False, should_write_output=False,
            skipped=True, skip_reason="unchanged_within_tolerance",
        ))
        self.assertEqual(result.status, CommandExecutionStatus.APPLIED)
        command = target._transport.commands[-1].command
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
        self.assertEqual(len(target._transport.commands), 1)

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
                self.assertEqual(target._transport.commands, [])

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
            target._transport.commands[-1].command.output_limit_w,
            2400,
        )

    async def test_disabled_hems_disconnect_and_restart_state_fail_closed(self):
        disabled = runtime(enabled=False)
        result = await disabled.async_execute_device_command(DeviceCommand("output"))
        self.assertEqual(result.reason, "native_control_disabled")
        self.assertEqual(disabled._transport.commands, [])

        blocked = runtime(current_state=state(hems=True))
        result = await blocked.async_execute_device_command(DeviceCommand(
            "output", output_limit_w=10, should_write_mode=False,
            should_write_input=False, should_write_output=True,
        ))
        self.assertIn("zendure_hems_active", result.reason)
        self.assertEqual(blocked._transport.commands, [])

        disconnected = runtime()
        disconnected._transport.state = ConnectionState.DISCONNECTED
        result = await disconnected.async_execute_device_command(DeviceCommand("output"))
        self.assertEqual(result.reason, "native_transport_not_ready")

        restarting = runtime()
        restarting._status = "connecting"
        result = await restarting.async_execute_device_command(DeviceCommand("output"))
        self.assertEqual(result.reason, "native_transport_not_ready")


if __name__ == "__main__":
    unittest.main()
