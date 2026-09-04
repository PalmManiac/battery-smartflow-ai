"""One-shot, reversible verification for the first native Zendure write."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Awaitable, Callable

from .native_device_command_gate import NativeCommandContext, NativeCommandRequest, NativeDeviceCommandGate
from .native_command_verification import (
    EffectStatus,
    NativeCommandVerificationManager,
    ReadbackPolicy,
)


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
    verification_manager: NativeCommandVerificationManager | None = None,
) -> NativeWriteVerification:
    """Perform exactly one test write and one verified restoration."""
    gate_result = gate.evaluate(request, context)
    correlation_id = gate_result.correlation_id
    final_value = (
        float(gate_result.command.output_limit_w)
        if gate_result.command is not None else None
    )
    tracked = None
    if verification_manager is not None:
        tracked = verification_manager.prepare(
            device_id=request.device_id,
            command_type="set_output_limit",
            target_key="output_limit",
            transport=request.transport,
            requested_value=requested_value,
            final_value=final_value if final_value is not None else requested_value,
            readback=ReadbackPolicy(
                property_name,
                final_value if final_value is not None else requested_value,
            ),
        )
        verification_manager.gate(
            tracked.command_id, accepted=gate_result.accepted,
            reasons=gate_result.reasons,
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
    if tracked is not None:
        verification_manager.sent(tracked.command_id, at=sent_at)
    try:
        transport = await send_property(property_name, final_value, correlation_id)
    except Exception:
        if tracked is not None:
            verification_manager.transport_result(
                tracked.command_id, ok=False, status="exception"
            )
        return result(NativeWriteStatus.TRANSPORT_ERROR)
    if tracked is not None:
        verification_manager.transport_result(
            tracked.command_id, ok=transport.accepted,
            status=(str(transport.status) if transport.status is not None else None),
        )
    if not transport.accepted:
        return result(NativeWriteStatus.TRANSPORT_ERROR, transport_status=transport.status)
    readback, mismatch = await _await_readback(
        read_property, final_value, sent_at, timeout, poll_interval
    )
    write_status = (
        NativeWriteStatus.READBACK_MISMATCH if mismatch
        else NativeWriteStatus.TIMEOUT
    ) if readback is None else NativeWriteStatus.RESTORED
    if tracked is not None:
        if readback is not None:
            verification_manager.observe_readback(
                tracked.command_id, device_id=request.device_id,
                property_name=property_name, value=readback.value,
                observed_at=readback.observed_at,
            )
            verification_manager.effect(
                tracked.command_id, status=EffectStatus.NOT_APPLICABLE,
                reason="setpoint_only_test",
            )
        elif mismatch is not None:
            verification_manager.observe_readback(
                tracked.command_id, device_id=request.device_id,
                property_name=property_name, value=mismatch.value,
                observed_at=mismatch.observed_at,
            )
        else:
            verification_manager.readback_timeout(tracked.command_id)
    latency = (
        max(0.0, (readback.observed_at - sent_at).total_seconds())
        if readback is not None else None
    )
    restore_command = replace(
        request.command, output_limit_w=original_value,
        reason="native_first_write_restore",
    )
    restore_gate = gate.evaluate(replace(request, command=restore_command), context)
    restore_tracked = None
    if verification_manager is not None:
        restore_tracked = verification_manager.prepare(
            device_id=request.device_id,
            command_type="restore_output_limit",
            target_key="output_limit",
            transport=request.transport,
            requested_value=original_value,
            final_value=original_value,
            readback=ReadbackPolicy(property_name, original_value),
        )
        verification_manager.gate(
            restore_tracked.command_id, accepted=restore_gate.accepted,
            reasons=restore_gate.reasons,
        )
    restore_sent_at = datetime.now(timezone.utc)
    restore_transport = TransportWriteResult(False)
    try:
        restore_transport = (
            await _send_tracked_restore(
                send_property, property_name, original_value,
                f"{correlation_id}-restore", verification_manager,
                restore_tracked,
            )
            if restore_gate.accepted else TransportWriteResult(False)
        )
        restored, _ = await _await_readback(
            read_property, original_value, restore_sent_at, timeout, poll_interval
        ) if restore_transport.accepted else (None, None)
    except Exception:
        if restore_tracked is not None:
            verification_manager.transport_result(
                restore_tracked.command_id, ok=False, status="exception"
            )
        restored = None
    if restore_tracked is not None and restore_transport.accepted:
        if restored is not None:
            verification_manager.observe_readback(
                restore_tracked.command_id, device_id=request.device_id,
                property_name=property_name, value=restored.value,
                observed_at=restored.observed_at,
            )
            verification_manager.effect(
                restore_tracked.command_id,
                status=EffectStatus.NOT_APPLICABLE,
                reason="setpoint_only_test",
            )
        else:
            verification_manager.readback_timeout(restore_tracked.command_id)
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


async def _send_tracked_restore(
    send_property: SendProperty, property_name: str, value: float,
    correlation_id: str,
    manager: NativeCommandVerificationManager | None,
    tracked: object | None,
) -> TransportWriteResult:
    if manager is not None and tracked is not None:
        manager.sent(tracked.command_id)
    outcome = await send_property(property_name, value, correlation_id)
    if manager is not None and tracked is not None:
        manager.transport_result(
            tracked.command_id, ok=outcome.accepted,
            status=(str(outcome.status) if outcome.status is not None else None),
        )
    return outcome
