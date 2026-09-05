"""Strictly read-only local ZenSDK report collection for V5 field tests."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import ipaddress
import json
import re
from typing import Any, Awaitable, Callable, Mapping, Protocol
from urllib.parse import urlsplit

from .core.models import ZendureTransport
from .zendure_cloud import ZendureCloudBootstrap
from .zendure_cloud_mqtt import CloudMqttMessage
from .zendure_device_matrix import VerificationLevel, resolve_zendure_device


ZENSDK_REPORT_PATH = "/properties/report"
ZENSDK_WRITE_PATH = "/properties/write"
DEFAULT_ZENSDK_TIMEOUT = 4.0


class ZenSdkResponse(Protocol):
    status: int

    async def json(self) -> Any: ...


GetJson = Callable[..., Awaitable[ZenSdkResponse]]


@dataclass(frozen=True, slots=True)
class ZenSdkReadAttempt:
    """Privacy-safe outcome; the LAN endpoint is deliberately not retained."""

    device_candidate_id: str
    address_source: str
    result: str
    http_status: int | None = None


@dataclass(frozen=True, slots=True)
class ZenSdkReadResult:
    messages: tuple[CloudMqttMessage, ...]
    attempts: tuple[ZenSdkReadAttempt, ...]


@dataclass(frozen=True, slots=True)
class ZenSdkWriteResult:
    """HTTP acceptance only; this is deliberately not device confirmation."""

    accepted: bool
    http_status: int | None
    result: str


async def async_write_zensdk_property(
    bootstrap: ZendureCloudBootstrap,
    device_candidate_id: str,
    property_name: str,
    value: int,
    request_id: int,
    post_json: GetJson,
    *,
    timeout: float = DEFAULT_ZENSDK_TIMEOUT,
) -> ZenSdkWriteResult:
    """Write one allow-listed property to one exact local main device."""

    if property_name != "outputLimit":
        return ZenSdkWriteResult(False, None, "property_not_allowed")
    device = next(
        (item for item in bootstrap.devices
         if item.candidate.candidate_id == device_candidate_id), None
    )
    if device is None:
        return ZenSdkWriteResult(False, None, "device_not_found")
    identity = device.candidate.identity
    if identity.product_model != "SolarFlow 2400 AC" or not identity.serial_number:
        return ZenSdkWriteResult(False, None, "model_not_allowed")
    raw = next(
        (item for item in bootstrap.raw_device_list
         if str(item.get("deviceKey")) == str(identity.device_id)), {}
    )
    addresses = _candidate_addresses(raw, identity.product_model, identity.serial_number)
    if not addresses:
        return ZenSdkWriteResult(False, None, "no_local_address")
    # A read may try another address, but a write is sent exactly once.  A
    # timeout is ambiguous and must never cause an automatic duplicate POST.
    _source, host = addresses[0]
    try:
        response = await asyncio.wait_for(
            post_json(
                f"http://{host}{ZENSDK_WRITE_PATH}",
                json={
                    "sn": identity.serial_number,
                    "properties": {property_name: int(value)},
                    "id": int(request_id),
                },
            ),
            timeout=timeout,
        )
        status = int(response.status)
        return ZenSdkWriteResult(
            200 <= status < 300, status,
            "transport_ok" if 200 <= status < 300 else "http_error",
        )
    except Exception:
        return ZenSdkWriteResult(False, None, "transport_error")


async def async_read_zensdk_reports(
    bootstrap: ZendureCloudBootstrap,
    get_json: GetJson,
    *,
    timeout: float = DEFAULT_ZENSDK_TIMEOUT,
    clock: Callable[[], datetime] | None = None,
    candidate_ids: frozenset[str] | None = None,
) -> ZenSdkReadResult:
    """Read one local report per supported device without exposing a write API."""

    if timeout <= 0:
        raise ValueError("timeout must be positive")
    now = clock or (lambda: datetime.now(timezone.utc))
    raw_by_device = {
        str(item.get("deviceKey")): item
        for item in bootstrap.raw_device_list
        if isinstance(item, Mapping) and item.get("deviceKey") is not None
    }
    tasks = []
    for device in bootstrap.devices:
        candidate_id = device.candidate.candidate_id
        if candidate_ids is not None and candidate_id not in candidate_ids:
            continue
        identity = device.candidate.identity
        matrix = resolve_zendure_device(identity)
        if (
            matrix is None
            or matrix.transport(ZendureTransport.ZENSDK).read
            is VerificationLevel.UNSUPPORTED
            or identity.device_id is None
        ):
            continue
        raw = raw_by_device.get(identity.device_id, {})
        addresses = _candidate_addresses(
            raw, identity.product_model, identity.serial_number
        )
        tasks.append(
            _read_device(
                candidate_id,
                addresses,
                get_json,
                timeout,
                now,
                identity.serial_number,
            )
        )
    if not tasks:
        return ZenSdkReadResult((), ())
    results = await asyncio.gather(*tasks)
    return ZenSdkReadResult(
        tuple(message for messages, _attempts in results for message in messages),
        tuple(attempt for _messages, attempts in results for attempt in attempts),
    )


async def _read_device(
    candidate_id: str,
    addresses: tuple[tuple[str, str], ...],
    get_json: GetJson,
    timeout: float,
    clock: Callable[[], datetime],
    expected_serial: str | None,
) -> tuple[tuple[CloudMqttMessage, ...], tuple[ZenSdkReadAttempt, ...]]:
    attempts: list[ZenSdkReadAttempt] = []
    if not expected_serial:
        return (), (ZenSdkReadAttempt(candidate_id, "none", "identity_missing"),)
    if not addresses:
        return (), (ZenSdkReadAttempt(candidate_id, "none", "no_local_address"),)
    for source, host in addresses:
        try:
            response = await asyncio.wait_for(
                get_json(f"http://{host}{ZENSDK_REPORT_PATH}", allow_redirects=False),
                timeout=timeout,
            )
            status = int(response.status)
            if status != 200:
                attempts.append(
                    ZenSdkReadAttempt(candidate_id, source, "http_error", status)
                )
                continue
            payload = await asyncio.wait_for(response.json(), timeout=timeout)
            if (
                not isinstance(payload, Mapping)
                or not isinstance(payload.get("properties"), Mapping)
                or ("packData" in payload and (
                    not isinstance(payload["packData"], list)
                    or any(not isinstance(pack, Mapping) for pack in payload["packData"])
                ))
            ):
                attempts.append(
                    ZenSdkReadAttempt(candidate_id, source, "invalid_response", status)
                )
                continue
            # An IP may have been reassigned to another main system. Only the
            # main report serial establishes identity; pack serials cannot do so.
            report_serial = payload.get("sn")
            if not isinstance(report_serial, str) or report_serial != expected_serial:
                attempts.append(ZenSdkReadAttempt(
                    candidate_id, source,
                    "identity_missing" if not report_serial else "identity_mismatch",
                    status,
                ))
                continue
            encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            attempts.append(ZenSdkReadAttempt(candidate_id, source, "success", status))
            return (
                (
                    CloudMqttMessage(
                        received_at=clock(),
                        topic="zensdk/properties/report",
                        payload=encoded,
                        parsed_payload=dict(payload),
                        payload_format="json",
                        device_candidate_id=candidate_id,
                        pack_id=None,
                        known_topic=True,
                        session_number=0,
                        transport="zensdk",
                    ),
                ),
                tuple(attempts),
            )
        except TimeoutError:
            attempts.append(ZenSdkReadAttempt(candidate_id, source, "timeout"))
        except Exception:
            attempts.append(ZenSdkReadAttempt(candidate_id, source, "cannot_connect"))
    return (), tuple(attempts)


def _candidate_addresses(
    raw: Mapping[str, Any], model: str | None, serial: str | None
) -> tuple[tuple[str, str], ...]:
    result: list[tuple[str, str]] = []
    raw_ip = raw.get("ip")
    if isinstance(raw_ip, str) and _safe_lan_ip(raw_ip.strip()):
        result.append(("device_list_ip", raw_ip.strip()))
    hostname = _derived_hostname(model, serial)
    if hostname and all(host != hostname for _source, host in result):
        result.append(("derived_local_hostname", hostname))
    return tuple(result)


def _safe_lan_ip(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    return bool(
        (address.is_private or address.is_link_local)
        and not address.is_loopback
        and not address.is_multicast
        and not address.is_unspecified
        and not address.is_reserved
    )


def _derived_hostname(model: str | None, serial: str | None) -> str | None:
    if not model or not serial:
        return None
    compact_model = re.sub(r"\s+", "", model)
    if not re.fullmatch(r"[A-Za-z0-9+_-]+", compact_model):
        return None
    if not re.fullmatch(r"[A-Za-z0-9_-]+", serial):
        return None
    hostname = f"zendure-{compact_model}-{serial}.local"
    parsed = urlsplit(f"http://{hostname}")
    return hostname if parsed.hostname == hostname.casefold() else None
