"""Typed, fail-closed Cloud MQTT command mapping for Zendure devices."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Protocol

from ...core.models import ZendureTransport
from ...native_command_verification import (
    NativeCommandVerificationManager,
    ReadbackPolicy,
)
from ...native_device_command_gate import AuthorizedNativeCommand
from .cloud import ZendureCloudBootstrap
from .device_matrix import (
    CloudCommandProtocol,
    VerificationLevel,
    resolve_zendure_device,
)


class CloudCommandStatus(StrEnum):
    SENT = "sent"
    REJECTED = "rejected"
    TRANSPORT_ERROR = "transport_error"


@dataclass(frozen=True, slots=True)
class CloudPropertyWrite:
    """One allow-listed low-level write and its readback contract."""

    property_name: str
    value: int
    message_id: int
    timestamp: int
    readback_tolerance: float = 0.0


@dataclass(frozen=True, slots=True)
class CloudCommandResult:
    """Safe result: a broker acceptance is deliberately not device success."""

    status: CloudCommandStatus
    reason: str
    verification_ids: tuple[str, ...] = ()
    writes_sent: int = 0


@dataclass(frozen=True, slots=True)
class CloudFunctionInvocation:
    """One allow-listed model command routed through function/invoke."""

    function: str
    arguments: Mapping[str, Any] | tuple[Mapping[str, Any], ...]
    expected_properties: Mapping[str, float]
    include_device_key: bool = False


@dataclass(frozen=True, slots=True)
class CloudCommandPlan:
    """Validated wire plan for one native setpoint command."""

    product_id: str
    device_id: str
    property_writes: tuple[CloudPropertyWrite, ...]
    invocation: CloudFunctionInvocation | None
    protocol: CloudCommandProtocol


class CloudPropertyPublisher(Protocol):
    def write_properties(
        self,
        product_id: str,
        device_id: str,
        writes: tuple[CloudPropertyWrite, ...],
    ) -> bool: ...

    def invoke_function(
        self,
        product_id: str,
        device_id: str,
        invocation: CloudFunctionInvocation,
        message_id: int,
        timestamp: int,
    ) -> bool: ...


_MODE_VALUES = {"input": 1, "output": 2}


def map_cloud_command(
    authorized: AuthorizedNativeCommand,
    bootstrap: ZendureCloudBootstrap,
    *,
    first_message_id: int,
    timestamp: int,
) -> tuple[str, str, tuple[CloudPropertyWrite, ...]]:
    """Map a property-protocol command, preserving its historical return shape."""

    plan = plan_cloud_command(
        authorized, bootstrap,
        first_message_id=first_message_id,
        timestamp=timestamp,
    )
    if plan.invocation is not None:
        raise ValueError("function_invoke_required")
    return plan.product_id, plan.device_id, plan.property_writes


def plan_cloud_command(
    authorized: AuthorizedNativeCommand,
    bootstrap: ZendureCloudBootstrap,
    *,
    first_message_id: int,
    timestamp: int,
) -> CloudCommandPlan:
    """Map only known model/protocol combinations to typed Cloud commands."""

    if not isinstance(authorized, AuthorizedNativeCommand):
        raise TypeError("gate_authorization_required")
    if authorized.transport is not ZendureTransport.CLOUD_MQTT:
        raise ValueError("wrong_transport")
    device = next((item for item in bootstrap.devices if item.candidate.candidate_id == authorized.device_id), None)
    if device is None:
        raise ValueError("device_not_found")
    identity = device.candidate.identity
    if not identity.device_id or not identity.product_id:
        raise ValueError("device_not_routable")
    matrix = resolve_zendure_device(identity)
    if matrix is None or not matrix.native_control_approved:
        raise ValueError("model_not_approved")
    if matrix.transport(ZendureTransport.CLOUD_MQTT).write is not VerificationLevel.VERIFIED:
        raise ValueError("transport_not_approved")
    command = authorized.command
    requested: list[tuple[str, int]] = []
    directional_write = any((
        command.should_write_mode,
        command.should_write_input,
        command.should_write_output,
    ))
    if directional_write:
        if command.ac_mode not in _MODE_VALUES:
            raise ValueError("unsupported_mode")
        input_limit = (
            _whole_watts(command.input_limit_w)
            if command.ac_mode == "input"
            else 0
        )
        output_limit = (
            _whole_watts(command.output_limit_w)
            if command.ac_mode == "output"
            else 0
        )
        active_limit = input_limit if command.ac_mode == "input" else output_limit
        if matrix.cloud_command_protocol is CloudCommandProtocol.DEVICE_AUTOMATION_OBJECT:
            if input_limit > 0 and matrix.profile_key != "Hyper 2000":
                raise ValueError("legacy_charge_not_supported")
            if input_limit > 0:
                program = 1
                auto_value: Any = {
                    "chargingType": 1,
                    "price": 2,
                    "chargingPower": input_limit,
                    "prices": [1] * 24,
                    "outPower": 0,
                    "freq": 0,
                }
            elif output_limit > 0:
                program = 2
                auto_value = {
                    "chargingType": 0,
                    "chargingPower": 0,
                    "freq": 0,
                    "outPower": output_limit,
                }
            else:
                program = 0
                auto_value = {
                    "chargingType": 0,
                    "chargingPower": 0,
                    "freq": 0,
                    "outPower": 0,
                }
            requested.extend(_soc_property_writes(command))
            expected = {
                "inputLimit": float(input_limit),
                "outputLimit": float(output_limit),
            }
            return CloudCommandPlan(
                identity.product_id,
                identity.device_id,
                _property_writes(
                    requested, matrix, first_message_id, timestamp
                ),
                CloudFunctionInvocation(
                    "deviceAutomation",
                    ({
                        "autoModelProgram": program,
                        "autoModelValue": auto_value,
                        "msgType": 1,
                        "autoModel": 8 if program else 0,
                    },),
                    expected,
                    include_device_key=True,
                ),
                matrix.cloud_command_protocol,
            )
        if matrix.cloud_command_protocol is CloudCommandProtocol.DEVICE_AUTOMATION_VALUE:
            if input_limit > 0:
                raise ValueError("legacy_charge_not_supported")
            requested.extend(_soc_property_writes(command))
            output_value = float(output_limit)
            arguments = (
                {
                    "autoModelProgram": 2 if output_limit > 0 else 0,
                    "autoModelValue": int(output_limit),
                    "msgType": 1,
                    "autoModel": 8 if output_limit > 0 else 0,
                },
            )
            return CloudCommandPlan(
                identity.product_id,
                identity.device_id,
                _property_writes(
                    requested, matrix, first_message_id, timestamp
                ),
                CloudFunctionInvocation(
                    "deviceAutomation",
                    arguments,
                    {"outputLimit": output_value, "inputLimit": 0.0},
                    include_device_key=True,
                ),
                matrix.cloud_command_protocol,
            )
        # Zendure directional control is one complete command. A bare limit
        # write can update the stored setpoint without starting Smart Mode.
        requested.extend((
            ("smartMode", 1 if active_limit > 0 else 0),
            ("acMode", _MODE_VALUES[command.ac_mode]),
            ("outputLimit", output_limit),
            ("inputLimit", input_limit),
        ))
    requested.extend(_soc_property_writes(command))
    if not requested:
        raise ValueError("empty_command")

    return CloudCommandPlan(
        identity.product_id,
        identity.device_id,
        _property_writes(requested, matrix, first_message_id, timestamp),
        None,
        matrix.cloud_command_protocol,
    )


def _soc_property_writes(command) -> list[tuple[str, int]]:
    requested: list[tuple[str, int]] = []
    if command.should_write_min_soc:
        requested.append(("minSoc", _soc_tenths(command.min_soc_pct)))
    if command.should_write_max_soc:
        requested.append(("socSet", _soc_tenths(command.max_soc_pct)))
    return requested


def _property_writes(
    requested: list[tuple[str, int]], matrix, first_message_id: int,
    timestamp: int,
) -> tuple[CloudPropertyWrite, ...]:
    writes = []
    for offset, (property_name, value) in enumerate(requested):
        if matrix.property_write_level(ZendureTransport.CLOUD_MQTT, property_name) is not VerificationLevel.VERIFIED:
            raise ValueError(f"property_not_approved:{property_name}")
        writes.append(CloudPropertyWrite(property_name, value, first_message_id + offset, timestamp))
    return tuple(writes)


class ZendureCloudCommandAdapter:
    """Execute only typed gate envelopes and correlate every property readback."""

    def __init__(self, bootstrap: ZendureCloudBootstrap, publisher: CloudPropertyPublisher,
                 verification: NativeCommandVerificationManager, *,
                 clock: Callable[[], datetime] | None = None) -> None:
        self._bootstrap = bootstrap
        self._publisher = publisher
        self._verification = verification
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._message_id = 0

    def execute(self, authorized: AuthorizedNativeCommand) -> CloudCommandResult:
        """Publish once per property; never retry or switch device/transport."""

        now = self._clock()
        try:
            plan = plan_cloud_command(
                authorized, self._bootstrap, first_message_id=self._message_id + 1,
                timestamp=int(now.timestamp()),
            )
        except ValueError as error:
            return CloudCommandResult(CloudCommandStatus.REJECTED, str(error))
        property_writes = list(plan.property_writes)
        self._message_id += len(property_writes) + (1 if plan.invocation else 0)
        verification_ids: list[str] = []
        prepared: list[tuple[CloudPropertyWrite, str]] = []
        for write in property_writes:
            verification = self._verification.prepare(
                device_id=authorized.device_id, command_type=write.property_name,
                target_key=write.property_name, transport=ZendureTransport.CLOUD_MQTT,
                requested_value=write.value, final_value=write.value,
                readback=ReadbackPolicy(write.property_name, write.value, write.readback_tolerance),
                prepared_at=now, max_attempts=1,
            )
            verification_ids.append(verification.command_id)
            self._verification.gate(verification.command_id, accepted=True, at=now)
            self._verification.sent(verification.command_id, at=now)
            prepared.append((write, verification.command_id))
        try:
            ok = (
                self._publisher.write_properties(
                    plan.product_id, plan.device_id, tuple(property_writes)
                )
                if property_writes
                else True
            )
        except Exception:  # noqa: BLE001 - isolate publisher/backend failures
            ok = False
        for _write, command_id in prepared:
            self._verification.transport_result(
                command_id, ok=ok,
                status="mqtt_publish_accepted" if ok else "mqtt_publish_failed",
                at=self._clock(),
            )
        if not ok:
            return CloudCommandResult(
                CloudCommandStatus.TRANSPORT_ERROR,
                "publish_failed",
                tuple(verification_ids),
                0,
            )
        sent = len(property_writes)
        if plan.invocation is not None:
            invocation_verifications: list[tuple[str, str]] = []
            for property_name, value in plan.invocation.expected_properties.items():
                verification = self._verification.prepare(
                    device_id=authorized.device_id,
                    command_type=plan.invocation.function,
                    target_key=property_name,
                    transport=ZendureTransport.CLOUD_MQTT,
                    requested_value=value,
                    final_value=value,
                    readback=ReadbackPolicy(property_name, value, 1.0),
                    prepared_at=now,
                    max_attempts=1,
                )
                self._verification.gate(verification.command_id, accepted=True, at=now)
                self._verification.sent(verification.command_id, at=now)
                invocation_verifications.append((property_name, verification.command_id))
            try:
                invoked = self._publisher.invoke_function(
                    plan.product_id,
                    plan.device_id,
                    plan.invocation,
                    self._message_id,
                    int(now.timestamp()),
                )
            except Exception:  # noqa: BLE001 - isolate publisher/backend failures
                invoked = False
            for _property_name, command_id in invocation_verifications:
                self._verification.transport_result(
                    command_id,
                    ok=invoked,
                    status="mqtt_invoke_accepted" if invoked else "mqtt_invoke_failed",
                    at=self._clock(),
                )
            if not invoked:
                return CloudCommandResult(
                    CloudCommandStatus.TRANSPORT_ERROR,
                    "invoke_failed",
                    tuple(verification_ids + [item[1] for item in invocation_verifications]),
                    sent,
                )
            sent += 1
            verification_ids.extend(item[1] for item in invocation_verifications)
        return CloudCommandResult(
            CloudCommandStatus.SENT,
            "awaiting_readback",
            tuple(verification_ids),
            sent,
        )

    def observe_properties(
        self,
        *,
        device_id: str,
        properties: Mapping[str, object],
        observed_at: datetime,
        retained: bool = False,
    ) -> int:
        """Attach fresh reports only to the currently active matching target."""

        confirmed = 0
        for property_name, raw_value in properties.items():
            active = self._verification.active_for(device_id, property_name)
            if active is None or isinstance(raw_value, bool):
                continue
            try:
                value = float(raw_value)
            except (TypeError, ValueError):
                continue
            if self._verification.observe_readback(
                active.command_id, device_id=device_id, property_name=property_name,
                value=value, observed_at=observed_at,
                source_transport=ZendureTransport.CLOUD_MQTT,
                retained=retained,
            ):
                confirmed += 1
        return confirmed


def _whole_watts(value: float) -> int:
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError("invalid_power_value")
    return round(number)


def _soc_tenths(value: float | None) -> int:
    if value is None:
        raise ValueError("missing_soc_value")
    number = float(value)
    if number < 0 or number > 100:
        raise ValueError("invalid_soc_value")
    return round(number * 10)
