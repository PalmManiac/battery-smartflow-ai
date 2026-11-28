from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
import unittest

from support import bootstrap

bootstrap()

from custom_components.battery_smartflow_ai.cold_wakeup import (  # noqa: E402
    cold_wakeup_command,
    cold_wakeup_evidence,
    cold_wakeup_stop_command,
)
from custom_components.battery_smartflow_ai.core.models import (  # noqa: E402
    DeviceCommand,
    DeviceControlState,
    DeviceInventory,
    MainDevice,
    MeasuredValue,
    NativeDeviceIdentity,
    ZendureTransport,
)
from custom_components.battery_smartflow_ai.hardware.zendure.device_matrix import (  # noqa: E402
    VerificationLevel,
    ZENDURE_DEVICE_MATRIX,
)
from custom_components.battery_smartflow_ai.hardware.zendure.hems import (  # noqa: E402
    ZendureHemsCommandGate,
)
from custom_components.battery_smartflow_ai.native_device_command_gate import (  # noqa: E402
    NativeCommandContext,
    NativeCommandRequest,
    NativeDeviceCommandGate,
)


NOW = datetime.now(timezone.utc)


def measured(value):
    return MeasuredValue.available(value, observed_at=NOW)


def cold_state():
    return SimpleNamespace(
        online=measured(True),
        protection_active=measured(True),
        heating_active=measured(False),
        mode=measured("discharge"),
        pv_power_w=measured(0),
        diagnostics={"is_error": measured(1)},
        packs=(SimpleNamespace(temperature_c=measured(0.95)),),
    )


def wake_command():
    return DeviceCommand(
        "input", input_limit_w=0, output_limit_w=0,
        reason="cold_protection_wakeup", should_write_mode=True,
        should_write_input=False, should_write_output=False,
    )


class ColdWakeupTests(unittest.TestCase):
    def test_requires_fresh_cold_protection_evidence(self):
        state = cold_state()
        self.assertTrue(cold_wakeup_evidence(state, now=NOW))
        from datetime import timedelta
        self.assertFalse(cold_wakeup_evidence(state, now=NOW + timedelta(minutes=1)))
        state.packs = (SimpleNamespace(temperature_c=measured(4.0)),)
        self.assertFalse(cold_wakeup_evidence(state, now=NOW))

    def test_only_zero_power_mode_write_qualifies(self):
        self.assertTrue(cold_wakeup_command(wake_command()))
        active_charge = wake_command()
        active_charge.input_limit_w = 120
        self.assertFalse(cold_wakeup_command(active_charge))
        stop = DeviceCommand(
            "output", input_limit_w=0, output_limit_w=0,
            reason="cold_protection_wakeup_stop",
        )
        self.assertTrue(cold_wakeup_stop_command(stop))

    def test_gate_keeps_other_protected_commands_blocked(self):
        transport = ZendureTransport.ZENSDK
        device = MainDevice(
            "cold-device", "Cold device", model="SolarFlow 2400 Pro",
            profile_key="SF2400Pro", control_state=DeviceControlState.ACTIVE,
            selected_transport=transport,
            available_transports=frozenset({transport}),
            native_identities=(NativeDeviceIdentity(
                transport, device_id="test-device", product_model="SF2400Pro"
            ),),
        )
        hems = ZendureHemsCommandGate()
        hems.update(
            "cold-device", measured(False), capability=VerificationLevel.VERIFIED
        )
        gate = NativeDeviceCommandGate(
            hems, matrix_resolver=lambda _identity: ZENDURE_DEVICE_MATRIX["SF2400Pro"]
        )
        context = NativeCommandContext(
            inventory=DeviceInventory(devices=(device,)),
            states={"cold-device": cold_state()},
            selected_device_id="cold-device", native_control_enabled=True,
            available_transports=frozenset({transport}),
        )
        result = gate.evaluate(
            NativeCommandRequest("cold-device", transport, wake_command()), context
        )
        self.assertTrue(result.accepted, result.reasons)
        normal_charge = wake_command()
        normal_charge.input_limit_w = 120
        blocked = gate.evaluate(
            NativeCommandRequest("cold-device", transport, normal_charge), context
        )
        self.assertIn("protection_active", blocked.reasons)
        stop = DeviceCommand(
            "output", input_limit_w=0, output_limit_w=0,
            reason="cold_protection_wakeup_stop",
        )
        stopped = gate.evaluate(
            NativeCommandRequest("cold-device", transport, stop), context
        )
        self.assertTrue(stopped.accepted, stopped.reasons)
