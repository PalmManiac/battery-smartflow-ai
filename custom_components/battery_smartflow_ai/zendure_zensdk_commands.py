"""Typed, fail-closed ZenSDK command mapping for Zendure devices."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Callable, Mapping

from .core.models import ZendureTransport
from .native_command_verification import (
    NativeCommandVerificationManager,
    ReadbackPolicy,
)
from .native_device_command_gate import AuthorizedNativeCommand
from .zendure_cloud import ZendureCloudBootstrap
from .zendure_device_matrix import VerificationLevel, resolve_zendure_device
from .zendure_zensdk import GetJson, async_write_zensdk_property


class ZenSdkCommandStatus(StrEnum):
    """Result of the HTTP transport step, not device confirmation."""

    SENT = "sent"
    REJECTED = "rejected"
    TRANSPORT_ERROR = "transport_error"


@dataclass(frozen=True, slots=True)
class ZenSdkPropertyWrite:
    """One allow-listed low-level write plus its readback contract."""

    property_name: str
    value: int
    request_id: int
    readback_tolerance: float = 0.0


@dataclass(frozen=True, slots=True)
class ZenSdkCommandResult:
    """Privacy-safe command result retained while readback is pending."""

    status: ZenSdkCommandStatus
    reason: str
    verification_ids: tuple[str, ...] = ()
    writes_sent: int = 0
    http_status: int | None = None


def map_zensdk_command(
    authorized: AuthorizedNativeCommand,
    bootstrap: ZendureCloudBootstrap,
    *,
    first_request_id: int,
) -> tuple[ZenSdkPropertyWrite, ...]:
    """Map only gate-authorized and transport-verified properties."""

    if not isinstance(authorized, AuthorizedNativeCommand):
        raise ValueError("gate_authorization_required")
    if authorized.transport is not ZendureTransport.ZENSDK:
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
    if matrix is None or not matrix.native_control_approved:
        raise ValueError("model_not_approved")
    if (
        matrix.transport(ZendureTransport.ZENSDK).write
        is not VerificationLevel.VERIFIED
    ):
        raise ValueError("transport_not_approved")

    command = authorized.command
    requested: list[tuple[str, int]] = []
    if command.should_write_mode:
        requested.append(("acMode", 1 if command.ac_mode == "input" else 2))
    if command.should_write_input:
        requested.append(("inputLimit", _whole_watts(command.input_limit_w)))
    if command.should_write_output:
        requested.append(("outputLimit", _whole_watts(command.output_limit_w)))
    if command.should_write_min_soc:
        requested.append(("minSoc", _soc_tenths(command.min_soc_pct)))
    if command.should_write_max_soc:
        requested.append(("socSet", _soc_tenths(command.max_soc_pct)))
    if not requested:
        raise ValueError("empty_command")

    writes = []
    for offset, (property_name, value) in enumerate(requested):
        if (
            matrix.property_write_level(ZendureTransport.ZENSDK, property_name)
            is not VerificationLevel.VERIFIED
        ):
            raise ValueError(f"property_not_approved:{property_name}")
        writes.append(
            ZenSdkPropertyWrite(
                property_name=property_name,
                value=value,
                request_id=first_request_id + offset,
            )
        )
    return tuple(writes)


class ZendureZenSdkCommandAdapter:
    """Send typed ZenSDK writes once and correlate fresh readback reports."""

    def __init__(
        self,
        bootstrap: ZendureCloudBootstrap,
        post_json: GetJson,
        verification: NativeCommandVerificationManager,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._bootstrap = bootstrap
        self._post_json = post_json
        self._verification = verification
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._request_id = 0

    async def execute(
        self, authorized: AuthorizedNativeCommand
    ) -> ZenSdkCommandResult:
        """POST each approved property once; never retry or fall back."""

        now = self._clock()
        try:
            writes = map_zensdk_command(
                authorized,
                self._bootstrap,
                first_request_id=self._request_id + 1,
            )
        except ValueError as error:
            return ZenSdkCommandResult(ZenSdkCommandStatus.REJECTED, str(error))

        prepared: list[tuple[ZenSdkPropertyWrite, str]] = []
        for write in writes:
            verification = self._verification.prepare(
                device_id=authorized.device_id,
                command_type=write.property_name,
                target_key=write.property_name,
                transport=ZendureTransport.ZENSDK,
                requested_value=write.value,
                final_value=write.value,
                readback=ReadbackPolicy(
                    write.property_name,
                    write.value,
                    write.readback_tolerance,
                ),
                prepared_at=now,
                max_attempts=1,
            )
            self._verification.gate(
                verification.command_id, accepted=True, at=now
            )
            prepared.append((write, verification.command_id))

        sent_count = 0
        last_http_status: int | None = None
        for write, command_id in prepared:
            self._verification.sent(command_id, at=self._clock())
            # The id belongs to an attempted request, even when its response is
            # an error or ambiguous timeout. Never reuse it for a later POST.
            self._request_id = write.request_id
            outcome = await async_write_zensdk_property(
                self._bootstrap,
                authorized.device_id,
                write.property_name,
                write.value,
                write.request_id,
                self._post_json,
            )
            last_http_status = outcome.http_status
            self._verification.transport_result(
                command_id,
                ok=outcome.accepted,
                status=(
                    f"http_{outcome.http_status}"
                    if outcome.http_status is not None
                    else outcome.result
                ),
                at=self._clock(),
            )
            if not outcome.accepted:
                for _pending_write, pending_id in prepared[sent_count + 1:]:
                    self._verification.cancel(pending_id)
                return ZenSdkCommandResult(
                    ZenSdkCommandStatus.TRANSPORT_ERROR,
                    outcome.result,
                    tuple(item[1] for item in prepared),
                    sent_count,
                    outcome.http_status,
                )
            sent_count += 1

        return ZenSdkCommandResult(
            ZenSdkCommandStatus.SENT,
            "awaiting_readback",
            tuple(item[1] for item in prepared),
            sent_count,
            last_http_status,
        )

    def observe_properties(
        self,
        *,
        device_id: str,
        properties: Mapping[str, object],
        observed_at: datetime,
    ) -> int:
        """Confirm only a new report for the exact device and property."""

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
