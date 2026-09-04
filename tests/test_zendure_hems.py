"""Contracts for the per-device Zendure HEMS hard blocker."""

from datetime import datetime, timezone
import unittest

from support import bootstrap

bootstrap()

from custom_components.battery_smartflow_ai.core.models import (  # noqa: E402
    MeasuredValue,
    HemsStatus,
    ValueValidity,
    ZendureTransport,
)
from custom_components.battery_smartflow_ai.zendure_device_matrix import (  # noqa: E402
    VerificationLevel,
)
from custom_components.battery_smartflow_ai.zendure_hems import (  # noqa: E402
    HemsCommandResult,
    ZendureHemsCommandGate,
)


NOW = datetime(2026, 9, 4, tzinfo=timezone.utc)


class ZendureHemsCommandGateTests(unittest.IsolatedAsyncioTestCase):
    async def test_active_hems_blocks_every_transport_and_command_type(self):
        gate = ZendureHemsCommandGate()
        gate.update(
            "device-a",
            MeasuredValue.available(True, observed_at=NOW),
            capability=VerificationLevel.VERIFIED,
        )
        writes = []

        async def send():
            writes.append("sent")

        for transport in (
            ZendureTransport.CLOUD_MQTT,
            ZendureTransport.LOCAL_MQTT,
            ZendureTransport.ZENSDK,
        ):
            for command_type in (
                "mode",
                "input_limit",
                "output_limit",
                "soc_limits",
                "manual",
            ):
                result = await gate.execute(
                    device_id="device-a",
                    transport=transport,
                    command_type=command_type,
                    send=send,
                )
                self.assertIsInstance(result, HemsCommandResult)
                self.assertEqual(result.decision.reason, "zendure_hems_active")
        self.assertEqual(writes, [])
        self.assertEqual(
            gate.diagnostics("device-a")["last_rejected_command"], "manual"
        )

    async def test_unknown_stale_and_invalid_capable_status_fail_closed(self):
        for validity, expected in (
            (ValueValidity.NEVER_RECEIVED, HemsStatus.UNKNOWN),
            (ValueValidity.STALE, HemsStatus.STALE),
            (ValueValidity.INVALID, HemsStatus.INVALID),
        ):
            gate = ZendureHemsCommandGate()
            decision = gate.update(
                "device-a",
                MeasuredValue.absent(validity, observed_at=NOW),
                capability=VerificationLevel.REFERENCE_ONLY,
            )
            self.assertEqual(decision.status, expected)
            self.assertFalse(decision.command_allowed)

    async def test_inactive_hems_does_not_bypass_other_future_gates(self):
        gate = ZendureHemsCommandGate()
        decision = gate.update(
            "device-a",
            MeasuredValue.available(False, observed_at=NOW),
            capability=VerificationLevel.VERIFIED,
        )
        self.assertTrue(decision.command_allowed)
        self.assertIsNone(decision.reason)

        async def send():
            return "next-gate-result"

        result = await gate.execute(
            device_id="device-a",
            transport=ZendureTransport.ZENSDK,
            command_type="mode",
            send=send,
        )
        self.assertEqual(result, "next-gate-result")

    async def test_unsupported_is_not_treated_as_unknown(self):
        gate = ZendureHemsCommandGate()
        decision = gate.update(
            "legacy-device",
            MeasuredValue.absent(ValueValidity.UNSUPPORTED),
            capability=VerificationLevel.UNSUPPORTED,
        )
        self.assertEqual(decision.status, HemsStatus.UNSUPPORTED)
        self.assertTrue(decision.command_allowed)

    async def test_devices_are_isolated_and_deactivation_needs_readback(self):
        gate = ZendureHemsCommandGate()
        gate.update(
            "blocked",
            MeasuredValue.available(True, observed_at=NOW),
            capability=VerificationLevel.VERIFIED,
        )
        gate.update(
            "free",
            MeasuredValue.available(False, observed_at=NOW),
            capability=VerificationLevel.VERIFIED,
        )
        calls = []

        async def send():
            calls.append("sent")
            return "sent"

        blocked = await gate.execute(
            device_id="blocked",
            transport=ZendureTransport.CLOUD_MQTT,
            command_type="mode",
            send=send,
        )
        allowed = await gate.execute(
            device_id="free",
            transport=ZendureTransport.CLOUD_MQTT,
            command_type="mode",
            send=send,
        )
        self.assertIsInstance(blocked, HemsCommandResult)
        self.assertEqual(allowed, "sent")
        self.assertEqual(calls, ["sent"])

        # A UI action cannot clear the blocker. Only fresh telemetry can update it.
        self.assertFalse(gate.decision("blocked").command_allowed)
        gate.update(
            "blocked",
            MeasuredValue.available(False, observed_at=NOW),
            capability=VerificationLevel.VERIFIED,
        )
        self.assertTrue(gate.decision("blocked").command_allowed)

    async def test_missing_device_state_fails_closed(self):
        gate = ZendureHemsCommandGate()
        decision = gate.decision("never-observed")
        self.assertEqual(decision.status, HemsStatus.UNKNOWN)
        self.assertFalse(decision.command_allowed)

    async def test_bsfai_can_never_disable_hems(self):
        gate = ZendureHemsCommandGate()
        gate.update(
            "device-a",
            MeasuredValue.available(False, observed_at=NOW),
            capability=VerificationLevel.VERIFIED,
        )
        calls = []

        async def send():
            calls.append("sent")

        result = await gate.execute(
            device_id="device-a",
            transport=ZendureTransport.ZENSDK,
            command_type="hems_disable",
            send=send,
        )
        self.assertIsInstance(result, HemsCommandResult)
        self.assertEqual(result.decision.reason, "zendure_hems_write_forbidden")
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
