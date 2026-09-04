"""Central fail-closed gate for every future native Zendure command."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import StrEnum
import math
from typing import Any, TypeVar
from uuid import uuid4

from .core.models import (
    DeviceCommand,
    DeviceControlState,
    DeviceInventory,
    MeasuredValue,
    NeutralDeviceState,
    ValueValidity,
    ZendureTransport,
)
from .zendure_device_matrix import (
    VerificationLevel,
    ZendureDeviceMatrixEntry,
    resolve_zendure_device,
)
from .zendure_hems import ZendureHemsCommandGate


class NativeGateStatus(StrEnum):
    ACCEPTED = "accepted"
    ACCEPTED_CLAMPED = "accepted_clamped"
    BLOCKED = "blocked"
    UNSUPPORTED = "unsupported"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class NativeLimitInputs:
    """Optional lower runtime ceilings; absent values never become zero."""

    input_limit_w: MeasuredValue[float] = field(
        default_factory=lambda: MeasuredValue.absent(ValueValidity.UNSUPPORTED)
    )
    output_limit_w: MeasuredValue[float] = field(
        default_factory=lambda: MeasuredValue.absent(ValueValidity.UNSUPPORTED)
    )
    dynamic_input_limit_w: MeasuredValue[float] = field(
        default_factory=lambda: MeasuredValue.absent(ValueValidity.UNSUPPORTED)
    )
    dynamic_output_limit_w: MeasuredValue[float] = field(
        default_factory=lambda: MeasuredValue.absent(ValueValidity.UNSUPPORTED)
    )
    required_validity: bool = False


@dataclass(frozen=True, slots=True)
class NativeCommandContext:
    """Current per-device authority and safety state supplied to the gate."""

    inventory: DeviceInventory
    states: Mapping[str, NeutralDeviceState]
    selected_device_id: str | None
    native_control_enabled: bool
    available_transports: frozenset[ZendureTransport]
    migration_blocked: bool = False
    writer_conflict: bool = False
    required_state_valid: bool = True
    limits: NativeLimitInputs = field(default_factory=NativeLimitInputs)


@dataclass(frozen=True, slots=True)
class NativeCommandRequest:
    """An explicitly addressed command; names and list order are never targets."""

    device_id: str
    transport: ZendureTransport
    command: DeviceCommand


@dataclass(frozen=True, slots=True)
class NativeGateResult:
    """Diagnostic result retained before any transport execution."""

    correlation_id: str
    device_id: str
    transport: ZendureTransport
    status: NativeGateStatus
    reasons: tuple[str, ...]
    requested: Mapping[str, Any]
    final: Mapping[str, Any] | None
    command: DeviceCommand | None
    evaluated_at: datetime

    @property
    def accepted(self) -> bool:
        return self.status in {
            NativeGateStatus.ACCEPTED,
            NativeGateStatus.ACCEPTED_CLAMPED,
        }

    def diagnostics(self) -> dict[str, Any]:
        """Return bounded correlation data with no identity or credential payloads."""

        return {
            "correlation_id": self.correlation_id,
            "device_id": self.device_id,
            "transport": self.transport.value,
            "status": self.status.value,
            "reasons": list(self.reasons),
            "requested": dict(self.requested),
            "final": dict(self.final) if self.final is not None else None,
            "evaluated_at": self.evaluated_at,
        }


ResultT = TypeVar("ResultT")


@dataclass(frozen=True, slots=True)
class AuthorizedNativeCommand:
    """Gate-issued envelope accepted by future native transport adapters."""

    correlation_id: str
    device_id: str
    transport: ZendureTransport
    command: DeviceCommand


NativeSender = Callable[[AuthorizedNativeCommand], Awaitable[ResultT]]
MatrixResolver = Callable[[Any], ZendureDeviceMatrixEntry | None]


class NativeDeviceCommandGate:
    """The only supported boundary between neutral commands and native adapters."""

    def __init__(
        self,
        hems_gate: ZendureHemsCommandGate,
        *,
        matrix_resolver: MatrixResolver = resolve_zendure_device,
    ) -> None:
        self._hems_gate = hems_gate
        self._matrix_resolver = matrix_resolver
        self._last_result: dict[str, NativeGateResult] = {}

    def evaluate(
        self,
        request: NativeCommandRequest,
        context: NativeCommandContext,
    ) -> NativeGateResult:
        correlation_id = uuid4().hex
        evaluated_at = datetime.now(timezone.utc)
        requested = _command_values(request.command)
        reasons: list[str] = []
        status = NativeGateStatus.BLOCKED

        device = context.inventory.devices.get(request.device_id)
        if device is None:
            reason = (
                "pack_not_command_target"
                if request.device_id in context.inventory.packs
                else "unknown_device"
            )
            return self._remember(_blocked(
                correlation_id, request, evaluated_at, requested, reason
            ))

        matching_identities = tuple(
            item
            for item in device.native_identities
            if item.transport is request.transport
        )
        identity = matching_identities[0] if len(matching_identities) == 1 else None
        if identity is None:
            reasons.append("ambiguous_or_missing_device_identity")
            matrix = None
        else:
            matrix = self._matrix_resolver(identity)
        if matrix is None:
            reasons.append("unknown_device_profile")
        elif not matrix.native_control_approved:
            reasons.append("device_profile_not_approved")

        if not context.native_control_enabled:
            reasons.append("control_disabled")
        if context.selected_device_id != request.device_id:
            reasons.append("device_not_selected")
        if device.control_state is not DeviceControlState.ACTIVE:
            reasons.append("device_not_active")
        if context.migration_blocked:
            reasons.append("migration_blocked")
        if context.writer_conflict:
            reasons.append("writer_conflict")

        if request.transport is not device.selected_transport:
            reasons.append("transport_not_selected")
        if request.transport not in device.available_transports:
            reasons.append("transport_not_available_for_device")
        if request.transport not in context.available_transports:
            reasons.append("transport_unavailable")

        if matrix is not None:
            transport = matrix.transport(request.transport)
            if transport.write is not VerificationLevel.VERIFIED:
                reasons.append("transport_write_not_verified")

        state = context.states.get(request.device_id)
        if state is None:
            reasons.append("required_state_missing")
        else:
            if not state.online.valid:
                reasons.append(_validity_reason("device_online", state.online.validity))
            elif not state.online.value:
                reasons.append("device_offline")
            if not context.required_state_valid:
                reasons.append("required_state_stale")
            if not state.protection_active.valid:
                reasons.append(
                    _validity_reason("protection_state", state.protection_active.validity)
                )
            elif state.protection_active.value:
                reasons.append("protection_active")

        hems = self._hems_gate.decision(request.device_id)
        if not hems.command_allowed:
            reasons.append(hems.reason or "zendure_hems_unknown")

        command_reasons = _validate_command(request.command, matrix, request.transport)
        reasons.extend(command_reasons)
        if any(reason.startswith("command_") for reason in command_reasons):
            status = NativeGateStatus.UNSUPPORTED
        if any(reason.startswith("invalid_") for reason in command_reasons):
            status = NativeGateStatus.INVALID

        final_command, clamp_reasons, limit_errors = _clamp_command(
            request.command,
            matrix,
            context.limits,
        )
        reasons.extend(limit_errors)
        if limit_errors:
            status = NativeGateStatus.INVALID

        reasons = list(dict.fromkeys(reasons))
        if reasons:
            return self._remember(NativeGateResult(
                correlation_id=correlation_id,
                device_id=request.device_id,
                transport=request.transport,
                status=status,
                reasons=tuple(reasons),
                requested=requested,
                final=None,
                command=None,
                evaluated_at=evaluated_at,
            ))

        return self._remember(NativeGateResult(
            correlation_id=correlation_id,
            device_id=request.device_id,
            transport=request.transport,
            status=(
                NativeGateStatus.ACCEPTED_CLAMPED
                if clamp_reasons
                else NativeGateStatus.ACCEPTED
            ),
            reasons=tuple(clamp_reasons),
            requested=requested,
            final=_command_values(final_command),
            command=final_command,
            evaluated_at=evaluated_at,
        ))

    async def execute(
        self,
        request: NativeCommandRequest,
        context: NativeCommandContext,
        send: NativeSender[ResultT],
    ) -> tuple[NativeGateResult, ResultT | None]:
        """Evaluate immediately before transport and never send blocked commands."""

        result = self.evaluate(request, context)
        if not result.accepted or result.command is None:
            return result, None
        authorized = AuthorizedNativeCommand(
            correlation_id=result.correlation_id,
            device_id=result.device_id,
            transport=result.transport,
            command=result.command,
        )
        return result, await send(authorized)

    def last_result(self, device_id: str) -> NativeGateResult | None:
        return self._last_result.get(device_id)

    def _remember(self, result: NativeGateResult) -> NativeGateResult:
        self._last_result[result.device_id] = result
        return result


def _blocked(
    correlation_id: str,
    request: NativeCommandRequest,
    evaluated_at: datetime,
    requested: Mapping[str, Any],
    reason: str,
) -> NativeGateResult:
    return NativeGateResult(
        correlation_id=correlation_id,
        device_id=request.device_id,
        transport=request.transport,
        status=NativeGateStatus.BLOCKED,
        reasons=(reason,),
        requested=requested,
        final=None,
        command=None,
        evaluated_at=evaluated_at,
    )


def _validate_command(
    command: DeviceCommand,
    matrix: ZendureDeviceMatrixEntry | None,
    transport: ZendureTransport,
) -> tuple[str, ...]:
    reasons = []
    if command.skipped:
        reasons.append("invalid_skipped_command")
    if command.ac_mode not in {"input", "output"}:
        reasons.append("invalid_command_mode")
    for name, value in (
        ("input_limit_w", command.input_limit_w),
        ("output_limit_w", command.output_limit_w),
    ):
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)) or value < 0:
            reasons.append(f"invalid_{name}")
    for name, value, enabled in (
        ("min_soc_pct", command.min_soc_pct, command.should_write_min_soc),
        ("max_soc_pct", command.max_soc_pct, command.should_write_max_soc),
    ):
        if enabled and (
            not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or not 0 <= float(value) <= 100
        ):
            reasons.append(f"invalid_{name}")
    if (
        command.should_write_min_soc
        and command.should_write_max_soc
        and isinstance(command.min_soc_pct, (int, float))
        and isinstance(command.max_soc_pct, (int, float))
        and command.min_soc_pct > command.max_soc_pct
    ):
        reasons.append("invalid_soc_interval")
    if command.ac_mode == "input" and command.should_write_output and command.output_limit_w != 0:
        reasons.append("invalid_input_mode_output_target")
    if command.ac_mode == "output" and command.should_write_input and command.input_limit_w != 0:
        reasons.append("invalid_output_mode_input_target")
    if not any((
        command.should_write_mode,
        command.should_write_input,
        command.should_write_output,
        command.should_write_min_soc,
        command.should_write_max_soc,
    )):
        reasons.append("invalid_empty_command")
    if matrix is not None:
        properties = []
        if command.should_write_mode:
            properties.append("acMode")
        if command.should_write_input:
            properties.append("inputLimit")
        if command.should_write_output:
            properties.append("outputLimit")
        if command.should_write_min_soc:
            properties.append("minSoc")
        if command.should_write_max_soc:
            properties.append("socSet")
        for prop in properties:
            if matrix.writable_main_properties.get(prop) is not VerificationLevel.VERIFIED:
                reasons.append(f"command_capability_unsupported:{prop}")
        if matrix.transport(transport).write is not VerificationLevel.VERIFIED:
            reasons.append("command_transport_unsupported")
    return tuple(reasons)


def _clamp_command(
    command: DeviceCommand,
    matrix: ZendureDeviceMatrixEntry | None,
    limits: NativeLimitInputs,
) -> tuple[DeviceCommand, tuple[str, ...], tuple[str, ...]]:
    if matrix is None:
        return replace(command, metadata=dict(command.metadata)), (), ()
    errors = []
    clamp_reasons = []
    input_max = matrix.profile.capabilities.max_input_w
    output_max = matrix.profile.capabilities.max_output_w
    for name, measured in (
        ("runtime_input_limit", limits.input_limit_w),
        ("dynamic_input_limit", limits.dynamic_input_limit_w),
    ):
        value, error = _limit_value(name, measured, limits.required_validity)
        if error:
            errors.append(error)
        elif value is not None:
            input_max = min(input_max, value)
    for name, measured in (
        ("runtime_output_limit", limits.output_limit_w),
        ("dynamic_output_limit", limits.dynamic_output_limit_w),
    ):
        value, error = _limit_value(name, measured, limits.required_validity)
        if error:
            errors.append(error)
        elif value is not None:
            output_max = min(output_max, value)
    final_input = min(float(command.input_limit_w), input_max)
    final_output = min(float(command.output_limit_w), output_max)
    if final_input < command.input_limit_w:
        clamp_reasons.append("input_limit_clamped")
    if final_output < command.output_limit_w:
        clamp_reasons.append("output_limit_clamped")
    return (
        replace(
            command,
            input_limit_w=final_input,
            output_limit_w=final_output,
            metadata=dict(command.metadata),
        ),
        tuple(clamp_reasons),
        tuple(errors),
    )


def _limit_value(
    name: str,
    value: MeasuredValue[float],
    required: bool,
) -> tuple[float | None, str | None]:
    if not value.valid:
        if required and value.validity is not ValueValidity.UNSUPPORTED:
            return None, _validity_reason(name, value.validity)
        return None, None
    numeric = float(value.value)
    if not math.isfinite(numeric) or numeric < 0:
        return None, f"invalid_{name}"
    return numeric, None


def _validity_reason(name: str, validity: ValueValidity) -> str:
    return f"{name}_{validity.value}"


def _command_values(command: DeviceCommand) -> dict[str, Any]:
    return {
        "mode": command.ac_mode,
        "input_limit_w": command.input_limit_w,
        "output_limit_w": command.output_limit_w,
        "min_soc_pct": command.min_soc_pct,
        "max_soc_pct": command.max_soc_pct,
        "write_mode": command.should_write_mode,
        "write_input": command.should_write_input,
        "write_output": command.should_write_output,
        "write_min_soc": command.should_write_min_soc,
        "write_max_soc": command.should_write_max_soc,
    }
