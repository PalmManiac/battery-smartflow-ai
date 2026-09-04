"""Transport-neutral lifecycle and correlation for native device commands."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from hashlib import sha256
import math
from typing import Any
from uuid import uuid4

from .core.models import ZendureTransport


class CommandVerificationStatus(StrEnum):
    PREPARED = "prepared"
    GATE_ACCEPTED = "gate_accepted"
    BLOCKED = "blocked"
    SENT = "sent"
    TRANSPORT_OK = "transport_ok"
    TRANSPORT_ERROR = "transport_error"
    READBACK_CONFIRMED = "readback_confirmed"
    READBACK_TIMEOUT = "readback_timeout"
    READBACK_MISMATCH = "readback_mismatch"
    CONTRADICTORY_RESPONSE = "contradictory_response"
    EFFECT_CONFIRMED = "effect_confirmed"
    EFFECT_TIMEOUT = "effect_timeout"
    EFFECT_MISMATCH = "effect_mismatch"
    SUPERSEDED = "superseded"
    CANCELLED = "cancelled"


class EffectStatus(StrEnum):
    PENDING = "pending"
    NOT_APPLICABLE = "not_applicable"
    NOT_OBSERVABLE = "not_observable"
    CONFIRMED = "confirmed"
    TIMEOUT = "timeout"
    MISMATCH = "mismatch"


@dataclass(frozen=True, slots=True)
class ReadbackPolicy:
    property_name: str
    expected_value: float
    tolerance: float = 0.0

    def matches(self, value: float) -> bool:
        return math.isclose(
            float(value), float(self.expected_value), rel_tol=0.0,
            abs_tol=max(0.0, float(self.tolerance)),
        )


@dataclass(slots=True)
class CommandVerification:
    command_id: str
    device_id: str
    command_type: str
    target_key: str
    transport: ZendureTransport
    requested_value: float
    final_value: float
    readback: ReadbackPolicy
    prepared_at: datetime
    status: CommandVerificationStatus = CommandVerificationStatus.PREPARED
    gate_at: datetime | None = None
    sent_at: datetime | None = None
    transport_at: datetime | None = None
    readback_at: datetime | None = None
    readback_value: float | None = None
    effect_at: datetime | None = None
    effect_status: EffectStatus = EffectStatus.PENDING
    reason: str | None = None
    superseded_by: str | None = None
    transport_status: str | None = None
    attempts: int = 0
    max_attempts: int = 1
    readback_values: list[float] = field(default_factory=list)
    failure_counted: bool = False

    @property
    def active(self) -> bool:
        if self.status is CommandVerificationStatus.READBACK_CONFIRMED:
            return self.effect_status is EffectStatus.PENDING
        return self.status not in {
            CommandVerificationStatus.BLOCKED,
            CommandVerificationStatus.TRANSPORT_ERROR,
            CommandVerificationStatus.READBACK_TIMEOUT,
            CommandVerificationStatus.READBACK_MISMATCH,
            CommandVerificationStatus.CONTRADICTORY_RESPONSE,
            CommandVerificationStatus.EFFECT_CONFIRMED,
            CommandVerificationStatus.EFFECT_TIMEOUT,
            CommandVerificationStatus.EFFECT_MISMATCH,
            CommandVerificationStatus.SUPERSEDED,
            CommandVerificationStatus.CANCELLED,
        }

    def diagnostics(self) -> dict[str, Any]:
        """Expose no metadata, credentials, serial number or payload content."""
        return {
            "command_id": self.command_id,
            "device_id": _public_device_id(self.device_id),
            "command_type": self.command_type,
            "target": self.target_key,
            "transport": self.transport.value,
            "requested_value": self.requested_value,
            "final_value": self.final_value,
            "expected_property": self.readback.property_name,
            "readback_tolerance": self.readback.tolerance,
            "status": self.status.value,
            "effect_status": self.effect_status.value,
            "reason": self.reason,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "transport_status": self.transport_status,
            "readback_value": self.readback_value,
            "prepared_at": self.prepared_at,
            "gate_at": self.gate_at,
            "sent_at": self.sent_at,
            "transport_at": self.transport_at,
            "readback_at": self.readback_at,
            "effect_at": self.effect_at,
            "gate_to_send_seconds": _latency(self.gate_at, self.sent_at),
            "send_to_transport_seconds": _latency(self.sent_at, self.transport_at),
            "send_to_readback_seconds": _latency(self.sent_at, self.readback_at),
            "send_to_effect_seconds": _latency(self.sent_at, self.effect_at),
            "superseded_by": self.superseded_by,
        }


class NativeCommandVerificationManager:
    """Correlate writes above transports and below neutral regulation."""

    def __init__(self, *, history_limit: int = 50) -> None:
        if history_limit < 1:
            raise ValueError("history_limit must be positive")
        self._history_limit = history_limit
        self._commands: dict[str, CommandVerification] = {}
        self._active: dict[tuple[str, str], str] = {}
        self._failures: dict[str, int] = {}

    def prepare(
        self, *, device_id: str, command_type: str, target_key: str,
        transport: ZendureTransport, requested_value: float, final_value: float,
        readback: ReadbackPolicy, prepared_at: datetime | None = None,
        max_attempts: int = 1,
    ) -> CommandVerification:
        if not device_id or not command_type or not target_key:
            raise ValueError("command identity must not be empty")
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        key = (device_id, target_key)
        command_id = uuid4().hex
        previous_id = self._active.get(key)
        if previous_id is not None:
            previous = self._commands[previous_id]
            if previous.active:
                previous.status = CommandVerificationStatus.SUPERSEDED
                previous.superseded_by = command_id
                previous.reason = "newer_command"
        command = CommandVerification(
            command_id=command_id, device_id=device_id,
            command_type=command_type, target_key=target_key,
            transport=transport, requested_value=float(requested_value),
            final_value=float(final_value), readback=readback,
            prepared_at=_aware(prepared_at), max_attempts=max_attempts,
        )
        self._commands[command_id] = command
        self._active[key] = command_id
        self._trim()
        return command

    def gate(self, command_id: str, *, accepted: bool,
             reasons: tuple[str, ...] = (), at: datetime | None = None) -> None:
        command = self._mutable(command_id)
        command.gate_at = _aware(at)
        command.status = (
            CommandVerificationStatus.GATE_ACCEPTED
            if accepted else CommandVerificationStatus.BLOCKED
        )
        command.reason = None if accepted else ",".join(reasons) or "blocked"
        if not accepted:
            self._finish(command)

    def sent(self, command_id: str, *, at: datetime | None = None) -> None:
        command = self._mutable(command_id)
        if command.status is not CommandVerificationStatus.GATE_ACCEPTED:
            raise ValueError("command was not gate accepted")
        if command.attempts >= command.max_attempts:
            raise ValueError("retry_limit_reached")
        command.attempts += 1
        command.sent_at = _aware(at)
        command.status = CommandVerificationStatus.SENT

    def transport_result(self, command_id: str, *, ok: bool,
                         status: str | None = None,
                         at: datetime | None = None) -> None:
        command = self._mutable(command_id)
        if command.sent_at is None:
            raise ValueError("command was not sent")
        command.transport_at = _aware(at)
        command.transport_status = status
        command.status = (
            CommandVerificationStatus.TRANSPORT_OK
            if ok else CommandVerificationStatus.TRANSPORT_ERROR
        )
        command.reason = None if ok else "transport_error"
        if not ok:
            self._fail(command)

    def observe_readback(self, command_id: str, *, device_id: str,
                         property_name: str, value: float,
                         observed_at: datetime) -> bool:
        command = self._commands[command_id]
        if command.status is CommandVerificationStatus.SUPERSEDED:
            return False
        if device_id != command.device_id or property_name != command.readback.property_name:
            return False
        observed = _aware(observed_at)
        if command.sent_at is None or observed <= command.sent_at:
            return False
        numeric = float(value)
        command.readback_values.append(numeric)
        previously_confirmed = command.readback_at is not None
        if command.readback.matches(numeric):
            command.readback_at = observed
            command.readback_value = numeric
            if command.status is CommandVerificationStatus.TRANSPORT_ERROR:
                command.status = CommandVerificationStatus.CONTRADICTORY_RESPONSE
                command.reason = "transport_error_but_readback_confirmed"
                self._fail(command)
                return False
            command.status = CommandVerificationStatus.READBACK_CONFIRMED
            command.reason = None
            return True
        command.readback_value = numeric
        command.readback_at = observed
        command.status = (
            CommandVerificationStatus.CONTRADICTORY_RESPONSE
            if previously_confirmed or len(set(command.readback_values)) > 1
            else CommandVerificationStatus.READBACK_MISMATCH
        )
        command.reason = "readback_value_mismatch"
        self._fail(command)
        return False

    def readback_timeout(self, command_id: str) -> None:
        command = self._mutable(command_id)
        command.status = CommandVerificationStatus.READBACK_TIMEOUT
        command.reason = "readback_timeout"
        self._fail(command)

    def effect(self, command_id: str, *, status: EffectStatus,
               at: datetime | None = None, reason: str | None = None) -> None:
        command = self._mutable(command_id)
        if command.readback_at is None:
            raise ValueError("effect cannot precede readback")
        command.effect_status = status
        command.effect_at = _aware(at)
        command.reason = reason
        if status is EffectStatus.CONFIRMED:
            command.status = CommandVerificationStatus.EFFECT_CONFIRMED
            self._finish(command)
        elif status is EffectStatus.TIMEOUT:
            command.status = CommandVerificationStatus.EFFECT_TIMEOUT
            self._fail(command)
        elif status is EffectStatus.MISMATCH:
            command.status = CommandVerificationStatus.EFFECT_MISMATCH
            self._fail(command)
        elif status in {EffectStatus.NOT_APPLICABLE, EffectStatus.NOT_OBSERVABLE}:
            command.status = CommandVerificationStatus.READBACK_CONFIRMED
            self._finish(command)

    def cancel(self, command_id: str) -> None:
        command = self._commands[command_id]
        if command.sent_at is not None:
            raise ValueError("sent command cannot be cancelled")
        command.status = CommandVerificationStatus.CANCELLED
        command.reason = "cancelled_before_send"
        self._finish(command)

    def get(self, command_id: str) -> CommandVerification:
        return self._commands[command_id]

    def active_for(self, device_id: str, target_key: str) -> CommandVerification | None:
        command_id = self._active.get((device_id, target_key))
        return self._commands.get(command_id) if command_id else None

    def diagnostics(self) -> dict[str, Any]:
        return {
            "commands": [item.diagnostics() for item in self._commands.values()],
            "failures_by_device": {
                _public_device_id(key): value for key, value in self._failures.items()
            },
        }

    def _mutable(self, command_id: str) -> CommandVerification:
        command = self._commands[command_id]
        if command.status in {
            CommandVerificationStatus.SUPERSEDED,
            CommandVerificationStatus.CANCELLED,
        }:
            raise ValueError("command is no longer active")
        return command

    def _fail(self, command: CommandVerification) -> None:
        if not command.failure_counted:
            self._failures[command.device_id] = (
                self._failures.get(command.device_id, 0) + 1
            )
            command.failure_counted = True
        self._finish(command)

    def _finish(self, command: CommandVerification) -> None:
        key = (command.device_id, command.target_key)
        if self._active.get(key) == command.command_id:
            self._active.pop(key, None)

    def _trim(self) -> None:
        while len(self._commands) > self._history_limit:
            removable = next(
                (command_id for command_id, command in self._commands.items()
                 if not command.active),
                None,
            )
            if removable is None:
                break
            self._commands.pop(removable)


def _aware(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware")
    return result


def _latency(start: datetime | None, end: datetime | None) -> float | None:
    if start is None or end is None:
        return None
    return round(max(0.0, (end - start).total_seconds()), 3)


def _public_device_id(value: str) -> str:
    return f"device_{sha256(value.encode('utf-8')).hexdigest()[:12]}"
