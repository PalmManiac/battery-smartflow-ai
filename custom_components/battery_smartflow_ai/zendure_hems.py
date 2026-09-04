"""Fail-closed, per-device Zendure HEMS command protection."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import TypeVar

from .core.models import HemsStatus, MeasuredValue, ValueValidity, ZendureTransport
from .zendure_device_matrix import VerificationLevel


@dataclass(frozen=True, slots=True)
class HemsControlDecision:
    """One explicit HEMS decision; absence never means permission."""

    device_id: str
    status: HemsStatus
    command_allowed: bool
    reason: str | None
    observed_at: datetime | None


@dataclass(frozen=True, slots=True)
class HemsCommandResult:
    """Result of the last safety gate immediately before a transport."""

    sent: bool
    decision: HemsControlDecision
    command_type: str
    transport: ZendureTransport


def evaluate_hems_status(
    value: MeasuredValue[bool],
    *,
    capability: VerificationLevel,
) -> HemsStatus:
    """Interpret HEMS without conflating unsupported and unavailable."""

    if capability is VerificationLevel.UNSUPPORTED:
        return HemsStatus.UNSUPPORTED
    if value.valid:
        return HemsStatus.ACTIVE if value.value else HemsStatus.INACTIVE
    if value.validity is ValueValidity.STALE:
        return HemsStatus.STALE
    if value.validity is ValueValidity.INVALID:
        return HemsStatus.INVALID
    return HemsStatus.UNKNOWN


ResultT = TypeVar("ResultT")
TransportSender = Callable[[], Awaitable[ResultT]]


class ZendureHemsCommandGate:
    """Per-device guard which every future native transport can share."""

    def __init__(self) -> None:
        self._decisions: dict[str, HemsControlDecision] = {}
        self._last_rejected: dict[str, HemsCommandResult] = {}

    def update(
        self,
        device_id: str,
        value: MeasuredValue[bool],
        *,
        capability: VerificationLevel,
    ) -> HemsControlDecision:
        status = evaluate_hems_status(value, capability=capability)
        allowed = status in {HemsStatus.INACTIVE, HemsStatus.UNSUPPORTED}
        reason = None if allowed else f"zendure_hems_{status.value}"
        decision = HemsControlDecision(
            device_id=device_id,
            status=status,
            command_allowed=allowed,
            reason=reason,
            observed_at=value.observed_at,
        )
        self._decisions[device_id] = decision
        return decision

    def decision(self, device_id: str) -> HemsControlDecision:
        """Fail closed until this exact device has a usable observation."""

        return self._decisions.get(
            device_id,
            HemsControlDecision(
                device_id=device_id,
                status=HemsStatus.UNKNOWN,
                command_allowed=False,
                reason="zendure_hems_unknown",
                observed_at=None,
            ),
        )

    async def execute(
        self,
        *,
        device_id: str,
        transport: ZendureTransport,
        command_type: str,
        send: TransportSender[ResultT],
    ) -> ResultT | HemsCommandResult:
        """Recheck HEMS at the last boundary before a real device write."""

        decision = self.decision(device_id)
        if command_type in {"hems", "hems_enable", "hems_disable"}:
            decision = HemsControlDecision(
                device_id=device_id,
                status=decision.status,
                command_allowed=False,
                reason="zendure_hems_write_forbidden",
                observed_at=decision.observed_at,
            )
        if decision.command_allowed:
            return await send()
        result = HemsCommandResult(
            sent=False,
            decision=decision,
            command_type=command_type,
            transport=transport,
        )
        self._last_rejected[device_id] = result
        return result

    def diagnostics(self, device_id: str) -> dict[str, object]:
        decision = self.decision(device_id)
        rejected = self._last_rejected.get(device_id)
        return {
            "status": decision.status.value,
            "blocks_control": not decision.command_allowed,
            "reason": decision.reason,
            "last_updated": decision.observed_at,
            "last_rejected_command": rejected.command_type if rejected else None,
            "last_rejected_transport": (
                rejected.transport.value if rejected else None
            ),
        }
