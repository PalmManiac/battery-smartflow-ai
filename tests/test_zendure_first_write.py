"""Verification-state contracts for the first native write."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
import unittest

from support import bootstrap

bootstrap()

from custom_components.battery_smartflow_ai.zendure_first_write import (  # noqa: E402
    NativeWriteStatus,
    PropertyReadback,
    TransportWriteResult,
    async_verify_reversible_write,
)
from custom_components.battery_smartflow_ai.core.models import DeviceCommand, ZendureTransport  # noqa: E402
from custom_components.battery_smartflow_ai.native_device_command_gate import NativeCommandRequest  # noqa: E402


def request(value: float) -> NativeCommandRequest:
    return NativeCommandRequest(
        "device", ZendureTransport.ZENSDK,
        DeviceCommand(
            "output", output_limit_w=value, should_write_mode=False,
            should_write_input=False, should_write_output=True,
        ),
    )


class Gate:
    def __init__(self, *, accepted=True):
        self.accepted = accepted

    def evaluate(self, request, _context):
        return SimpleNamespace(
            correlation_id="safe-correlation",
            accepted=self.accepted,
            command=request.command if self.accepted else None,
            status=SimpleNamespace(value="accepted" if self.accepted else "blocked"),
            reasons=() if self.accepted else ("hems_active",),
        )


class FirstWriteTests(unittest.IsolatedAsyncioTestCase):
    async def test_write_and_restore_both_require_fresh_readback(self):
        writes = []

        async def send(prop, value, correlation):
            writes.append((prop, value, correlation))
            return TransportWriteResult(True, 200)

        async def read():
            value = 101.0 if len(writes) == 1 else 100.0
            return PropertyReadback(value, datetime.now(timezone.utc))

        result = await async_verify_reversible_write(
            gate=Gate(), request=request(101.0), context=None,
            property_name="outputLimit", original_value=100.0,
            requested_value=101.0, send_property=send, read_property=read,
            timeout=0.1, poll_interval=0,
        )
        self.assertEqual(result.status, NativeWriteStatus.RESTORED)
        self.assertEqual([item[1] for item in writes], [101.0, 100.0])
        self.assertEqual(writes[1][2], "safe-correlation-restore")

    async def test_transport_ok_without_readback_is_timeout_and_not_retried(self):
        writes = []

        async def send(prop, value, correlation):
            writes.append((prop, value, correlation))
            return TransportWriteResult(True, 200)

        async def read():
            return None

        result = await async_verify_reversible_write(
            gate=Gate(), request=request(1),
            context=None, property_name="outputLimit", original_value=0,
            requested_value=1, send_property=send, read_property=read,
            timeout=0.01, poll_interval=0,
        )
        self.assertEqual(result.status, NativeWriteStatus.TIMEOUT)
        self.assertEqual(result.restore_status, "failed")
        self.assertEqual(len(writes), 2)

    async def test_blocked_gate_never_calls_transport(self):
        called = False

        async def send(*_args):
            nonlocal called
            called = True

        result = await async_verify_reversible_write(
            gate=Gate(accepted=False), request=request(1),
            context=None, property_name="outputLimit", original_value=0,
            requested_value=1, send_property=send, read_property=lambda: None,
        )
        self.assertEqual(result.status, NativeWriteStatus.BLOCKED)
        self.assertFalse(called)


if __name__ == "__main__":
    unittest.main()
