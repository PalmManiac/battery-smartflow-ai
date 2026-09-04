"""Typed, fail-closed Cloud MQTT command mapping for Zendure devices."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Callable, Mapping, Protocol

from .core.models import ZendureTransport
from .native_command_verification import NativeCommandVerificationManager, ReadbackPolicy
from .native_device_command_gate import AuthorizedNativeCommand
from .zendure_cloud import ZendureCloudBootstrap
from .zendure_device_matrix import VerificationLevel, resolve_zendure_device


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


class CloudPropertyPublisher(Protocol):
    def write_properties(
        self,
        product_id: str,
        device_id: str,
        writes: tuple[CloudPropertyWrite, ...],
    ) -> bool: ...


_MODE_VALUES = {"input": 1, "output": 2}


def map_cloud_command(
    authorized: AuthorizedNativeCommand,
    bootstrap: ZendureCloudBootstrap,
    *,
    first_message_id: int,
    timestamp: int,
) -> tuple[str, str, tuple[CloudPropertyWrite, ...]]:
    """Map a gate-issued command to small ordered writes for one exact device."""

    if not isinstance(authorized, AuthorizedNativeCommand):
        raise ValueError("gate_authorization_required")
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
        # Zendure directional control is one complete command. A bare limit
        # write can update the stored setpoint without starting Smart Mode.
        requested.extend((
            ("smartMode", 1 if active_limit > 0 else 0),
            ("acMode", _MODE_VALUES[command.ac_mode]),
            ("outputLimit", output_limit),
            ("inputLimit", input_limit),
        ))
    if command.should_write_min_soc:
        requested.append(("minSoc", _soc_tenths(command.min_soc_pct)))
    if command.should_write_max_soc:
        requested.append(("socSet", _soc_tenths(command.max_soc_pct)))
    if not requested:
        raise ValueError("empty_command")

    writes = []
    for offset, (property_name, value) in enumerate(requested):
        if matrix.property_write_level(ZendureTransport.CLOUD_MQTT, property_name) is not VerificationLevel.VERIFIED:
            raise ValueError(f"property_not_approved:{property_name}")
        writes.append(CloudPropertyWrite(property_name, value, first_message_id + offset, timestamp))
    return identity.product_id, identity.device_id, tuple(writes)


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
            product_id, device_id, writes = map_cloud_command(
                authorized, self._bootstrap, first_message_id=self._message_id + 1,
                timestamp=int(now.timestamp()),
            )
        except ValueError as error:
            return CloudCommandResult(CloudCommandStatus.REJECTED, str(error))
        self._message_id += len(writes)
        verification_ids: list[str] = []
        prepared: list[tuple[CloudPropertyWrite, str]] = []
        for write in writes:
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
            ok = self._publisher.write_properties(product_id, device_id, writes)
        except Exception:
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
        sent = len(writes)
        return CloudCommandResult(CloudCommandStatus.SENT, "awaiting_readback", tuple(verification_ids), sent)

    def observe_properties(self, *, device_id: str, properties: Mapping[str, object], observed_at: datetime) -> int:
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
            ):
                confirmed += 1
        return confirmed


def _whole_watts(value: float) -> int:
    number = float(value)
    if not number.is_integer() or number < 0:
        raise ValueError("invalid_power_value")
    return int(number)


def _soc_tenths(value: float | None) -> int:
    if value is None:
        raise ValueError("missing_soc_value")
    number = float(value)
    if number < 0 or number > 100:
        raise ValueError("invalid_soc_value")
    return int(round(number * 10))
