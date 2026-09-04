"""One-shot, reversible verification for the first native Zendure write."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Awaitable, Callable

from .native_device_command_gate import NativeCommandContext, NativeCommandRequest, NativeDeviceCommandGate


class NativeWriteStatus(StrEnum):
    BLOCKED = "blocked"
    TRANSPORT_ERROR = "transport_error"
    READBACK_MISMATCH = "readback_mismatch"
    TIMEOUT = "timeout"
    RESTORE_FAILED = "restore_failed"
    RESTORED = "restored"


@dataclass(frozen=True, slots=True)
class PropertyReadback:
    value: float
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class TransportWriteResult:
    accepted: bool
    status: int | None = None


@dataclass(frozen=True, slots=True)
class NativeWriteVerification:
    correlation_id: str
    status: NativeWriteStatus
    property_name: str
    original_value: float
    requested_value: float
    final_value: float | None
    readback_value: float | None
    readback_latency_seconds: float | None
    restore_status: str
    gate_status: str
    gate_reasons: tuple[str, ...]
    transport_status: int | None = None

    def diagnostics(self) -> dict[str, object]:
        return {
            "correlation_id": self.correlation_id, "status": self.status.value,
            "property": self.property_name, "original_value": self.original_value,
            "requested_value": self.requested_value, "final_value": self.final_value,
            "readback_value": self.readback_value,
            "readback_latency_seconds": self.readback_latency_seconds,
            "restore_status": self.restore_status, "gate_status": self.gate_status,
            "gate_reasons": list(self.gate_reasons),
            "transport_status": self.transport_status,
        }


SendProperty = Callable[[str, float, str], Awaitable[TransportWriteResult]]
ReadProperty = Callable[[], Awaitable[PropertyReadback | None]]


async def async_verify_reversible_write(
    *, gate: NativeDeviceCommandGate, request: NativeCommandRequest,
    context: NativeCommandContext, property_name: str, original_value: float,
    requested_value: float, send_property: SendProperty,
    read_property: ReadProperty, timeout: float = 10.0,
    poll_interval: float = 0.5,
) -> NativeWriteVerification:
    """Perform exactly one test write and one verified restoration."""
    gate_result = gate.evaluate(request, context)
    correlation_id = gate_result.correlation_id
    final_value = (
        float(gate_result.command.output_limit_w)
        if gate_result.command is not None else None
    )

    def result(status: NativeWriteStatus, *, readback=None, latency=None,
               restore="not_started", transport_status=None):
        return NativeWriteVerification(
            correlation_id, status, property_name, original_value,
            requested_value, final_value, readback, latency, restore,
            gate_result.status.value, gate_result.reasons, transport_status,
        )

    if not gate_result.accepted or final_value is None:
        return result(NativeWriteStatus.BLOCKED)
    sent_at = datetime.now(timezone.utc)
    try:
        transport = await send_property(property_name, final_value, correlation_id)
    except Exception:
        return result(NativeWriteStatus.TRANSPORT_ERROR)
    if not transport.accepted:
        return result(NativeWriteStatus.TRANSPORT_ERROR, transport_status=transport.status)
    readback, mismatch = await _await_readback(
        read_property, final_value, sent_at, timeout, poll_interval
    )
    write_status = (
        NativeWriteStatus.READBACK_MISMATCH if mismatch
        else NativeWriteStatus.TIMEOUT
    ) if readback is None else NativeWriteStatus.RESTORED
    latency = (
        max(0.0, (readback.observed_at - sent_at).total_seconds())
        if readback is not None else None
    )
    restore_command = replace(
        request.command, output_limit_w=original_value,
        reason="native_first_write_restore",
    )
    restore_gate = gate.evaluate(replace(request, command=restore_command), context)
    restore_sent_at = datetime.now(timezone.utc)
    try:
        restore_transport = (
            await send_property(
                property_name, original_value, f"{correlation_id}-restore"
            )
            if restore_gate.accepted else TransportWriteResult(False)
        )
        restored, _ = await _await_readback(
            read_property, original_value, restore_sent_at, timeout, poll_interval
        ) if restore_transport.accepted else (None, None)
    except Exception:
        restored = None
    return result(
        (
            NativeWriteStatus.RESTORE_FAILED
            if readback is not None and not restored
            else write_status
        ),
        readback=(readback.value if readback else mismatch.value if mismatch else None),
        latency=round(latency, 3) if latency is not None else None,
        restore="readback_confirmed" if restored else "failed",
        transport_status=transport.status,
    )


async def _await_readback(read_property: ReadProperty, expected: float,
                          sent_at: datetime, timeout: float, poll_interval: float):
    deadline = asyncio.get_running_loop().time() + timeout
    mismatch = None
    while asyncio.get_running_loop().time() < deadline:
        value = await read_property()
        if value is not None and value.observed_at > sent_at:
            if value.value == expected:
                return value, mismatch
            mismatch = value
        await asyncio.sleep(poll_interval)
    return None, mismatch
