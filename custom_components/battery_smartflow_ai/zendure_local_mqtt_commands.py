"""Allow-listed Local MQTT commands for verified ZendureLegacy models."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Callable, Mapping, Protocol

from .core.models import ZendureTransport
from .native_command_verification import (
    NativeCommandVerificationManager,
    ReadbackPolicy,
)
from .native_device_command_gate import AuthorizedNativeCommand
from .zendure_cloud import ZendureCloudBootstrap
from .zendure_device_matrix import VerificationLevel, resolve_zendure_device


class LocalMqttCommandStatus(StrEnum):
    SENT = "sent"
    REJECTED = "rejected"
    TRANSPORT_ERROR = "transport_error"


@dataclass(frozen=True, slots=True)
class LocalMqttInvocation:
    function: str
    arguments: tuple[Mapping[str, Any], ...]
    expected_properties: Mapping[str, float]


@dataclass(frozen=True, slots=True)
class LocalMqttCommandResult:
    status: LocalMqttCommandStatus
    reason: str
    verification_ids: tuple[str, ...] = ()
    publishes_sent: int = 0


class LocalMqttPublisher(Protocol):
    def invoke_function(
        self,
        product_id: str,
        device_id: str,
        invocation: LocalMqttInvocation,
        message_id: int,
        timestamp: int,
    ) -> bool: ...


def map_local_mqtt_command(
    authorized: AuthorizedNativeCommand,
    bootstrap: ZendureCloudBootstrap,
) -> LocalMqttInvocation:
    """Translate one neutral command to a verified legacy deviceAutomation call."""

    if not isinstance(authorized, AuthorizedNativeCommand):
        raise ValueError("gate_authorization_required")
    if authorized.transport is not ZendureTransport.LOCAL_MQTT:
        raise ValueError("wrong_transport")
    device = next(
        (
            item
            for item in bootstrap.devices
            if item.candidate.candidate_id == authorized.device_id
        ),
        None,
    )
    if device is None:
        raise ValueError("device_not_found")
    matrix = resolve_zendure_device(device.candidate.identity)
    if (
        matrix is None
        or not matrix.native_control_approved
        or matrix.transport(ZendureTransport.LOCAL_MQTT).write
        is not VerificationLevel.VERIFIED
    ):
        raise ValueError("model_not_approved")

    command = authorized.command
    if command.should_write_min_soc or command.should_write_max_soc:
        raise ValueError("soc_command_not_approved")
    input_w = _whole_watts(command.input_limit_w)
    output_w = _whole_watts(command.output_limit_w)
    model = matrix.profile_key

    if command.ac_mode == "input" and input_w > 0:
        if model != "Hyper 2000":
            raise ValueError("input_not_supported")
        return LocalMqttInvocation(
            "deviceAutomation",
            (
                {
                    "autoModelProgram": 1,
                    "autoModelValue": {
                        "chargingType": 1,
                        "price": 2,
                        "chargingPower": input_w,
                        "prices": [1] * 24,
                        "outPower": 0,
                        "freq": 0,
                    },
                    "msgType": 1,
                    "autoModel": 8,
                },
            ),
            {"inputLimit": float(input_w), "outputLimit": 0.0},
        )

    if command.ac_mode == "output" and output_w > 0:
        auto_value: Any = (
            {
                "chargingType": 0,
                "chargingPower": 0,
                "freq": 0,
                "outPower": output_w,
            }
            if model == "Hyper 2000"
            else output_w
        )
        return LocalMqttInvocation(
            "deviceAutomation",
            (
                {
                    "autoModelProgram": 2,
                    "autoModelValue": auto_value,
                    "msgType": 1,
                    "autoModel": 8,
                },
            ),
            {"outputLimit": float(output_w), "inputLimit": 0.0},
        )

    auto_value = (
        {
            "chargingType": 0,
            "chargingPower": 0,
            "freq": 0,
            "outPower": 0,
        }
        if model == "Hyper 2000"
        else 0
    )
    return LocalMqttInvocation(
        "deviceAutomation",
        (
            {
                "autoModelProgram": 0,
                "autoModelValue": auto_value,
                "msgType": 1,
                "autoModel": 0,
            },
        ),
        {"inputLimit": 0.0, "outputLimit": 0.0},
    )


class ZendureLocalMqttCommandAdapter:
    """Publish one allow-listed invocation and correlate later reports."""

    def __init__(
        self,
        bootstrap: ZendureCloudBootstrap,
        publisher: LocalMqttPublisher,
        verification: NativeCommandVerificationManager,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._bootstrap = bootstrap
        self._publisher = publisher
        self._verification = verification
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._message_id = 0

    def execute(self, authorized: AuthorizedNativeCommand) -> LocalMqttCommandResult:
        now = self._clock()
        try:
            invocation = map_local_mqtt_command(authorized, self._bootstrap)
        except ValueError as error:
            return LocalMqttCommandResult(LocalMqttCommandStatus.REJECTED, str(error))

        prepared: list[str] = []
        for property_name, value in invocation.expected_properties.items():
            verification = self._verification.prepare(
                device_id=authorized.device_id,
                command_type=property_name,
                target_key=property_name,
                transport=ZendureTransport.LOCAL_MQTT,
                requested_value=value,
                final_value=value,
                readback=ReadbackPolicy(property_name, value, 1.0),
                prepared_at=now,
                max_attempts=1,
            )
            self._verification.gate(verification.command_id, accepted=True, at=now)
            self._verification.sent(verification.command_id, at=now)
            prepared.append(verification.command_id)

        self._message_id += 1
        sent = self._publisher.invoke_function(
            _product_id(self._bootstrap, authorized.device_id),
            _device_id(self._bootstrap, authorized.device_id),
            invocation,
            self._message_id,
            int(now.timestamp()),
        )
        for command_id in prepared:
            self._verification.transport_result(
                command_id,
                ok=sent,
                status="published" if sent else "publish_failed",
                at=self._clock(),
            )
        return LocalMqttCommandResult(
            LocalMqttCommandStatus.SENT
            if sent
            else LocalMqttCommandStatus.TRANSPORT_ERROR,
            "awaiting_readback" if sent else "publish_failed",
            tuple(prepared),
            1 if sent else 0,
        )

    def observe_properties(
        self,
        *,
        device_id: str,
        properties: Mapping[str, object],
        observed_at: datetime,
    ) -> int:
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
                active.command_id,
                device_id=device_id,
                property_name=property_name,
                value=value,
                observed_at=observed_at,
            ):
                confirmed += 1
        return confirmed


def _whole_watts(value: float) -> int:
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError("invalid_power_value")
    return int(round(number))


def _device(bootstrap: ZendureCloudBootstrap, candidate_id: str):
    return next(
        (
            item
            for item in bootstrap.devices
            if item.candidate.candidate_id == candidate_id
        ),
        None,
    )


def _device_id(bootstrap: ZendureCloudBootstrap, candidate_id: str) -> str:
    item = _device(bootstrap, candidate_id)
    value = item.candidate.identity.device_id if item is not None else None
    if not value:
        raise ValueError("device_id_missing")
    return value


def _product_id(bootstrap: ZendureCloudBootstrap, candidate_id: str) -> str:
    item = _device(bootstrap, candidate_id)
    value = item.candidate.identity.product_id if item is not None else None
    if not value:
        raise ValueError("product_id_missing")
    return value
