"""Read-only Zendure Cloud bootstrap for native V5 discovery.

Secrets in this module are transport-layer values.  Callers must only pass the
neutral discovery candidates to the core and must never serialize credentials.
"""

from __future__ import annotations

import asyncio
from base64 import b64decode
import binascii
from copy import deepcopy
from dataclasses import dataclass, field
import hashlib
import logging
import re
import secrets
import time
from typing import Any, Awaitable, Callable, Mapping, Protocol
from urllib.parse import urlsplit

from ...core.models import (
    DeviceInventory,
    DiscoveryCandidate,
    NativeDeviceIdentity,
    ZendureTransport,
)
from .device_matrix import resolve_zendure_device


DEVICE_LIST_PATH = "/api/ha/deviceList"
CLIENT_ID = "zenHa"
# Required by Zendure's HA endpoint.  Keep this protocol signing material in
# the transport adapter; it is not user/account data and must not leave it.
_SIGNING_KEY = "C*dafwArEOXK"
_LOGGER = logging.getLogger(__name__)
_DIAGNOSTIC_FIELD_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
_REDACTED_FIELD_NAME = "[redacted]"


class ZendureCloudError(Exception):
    """Safe, classified Cloud bootstrap failure."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True, slots=True, repr=False)
class ZendureAppToken:
    """Validated token components, deliberately hidden from representations."""

    encoded: str = field(repr=False)
    api_base: str = field(repr=False)
    app_key: str = field(repr=False)

    @property
    def region_host(self) -> str:
        """Return only the host for internal routing, never for diagnostics."""

        return urlsplit(self.api_base).hostname or ""

    def __repr__(self) -> str:
        return "ZendureAppToken([REDACTED])"


@dataclass(frozen=True, slots=True, repr=False)
class CloudMqttCredentials:
    """Opaque MQTT bootstrap values retained only by the transport layer."""

    client_id: str = field(repr=False)
    url: str = field(repr=False)
    username: str = field(repr=False)
    password: str = field(repr=False)

    def __repr__(self) -> str:
        return "CloudMqttCredentials([REDACTED])"


@dataclass(frozen=True, slots=True)
class ZendureCloudDevice:
    """Parsed main-device metadata without transport credentials."""

    candidate: DiscoveryCandidate
    online: bool | None
    pack_count: int | None
    extra_field_names: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True, repr=False)
class ZendureCloudBootstrap:
    """One account discovery result; credentials stay opaque."""

    devices: tuple[ZendureCloudDevice, ...]
    mqtt: CloudMqttCredentials = field(repr=False)
    raw_device_list: tuple[Mapping[str, Any], ...] = field(
        default=(), repr=False
    )

    def __repr__(self) -> str:
        return f"ZendureCloudBootstrap(devices={len(self.devices)}, mqtt=[REDACTED])"

    def register_candidates(self, inventory: DeviceInventory) -> None:
        """Register passive candidates without creating or activating systems."""

        for device in self.devices:
            inventory.discover(device.candidate)


class JsonResponse(Protocol):
    """Minimum response contract implemented by aiohttp responses."""

    async def json(self) -> Any: ...


PostJson = Callable[..., Awaitable[JsonResponse]]


def parse_app_token(value: str) -> ZendureAppToken:
    """Decode and strictly validate a Zendure App/Home Assistant token."""

    token = value.strip()
    if not token:
        raise ZendureCloudError("invalid_token")
    try:
        decoded = b64decode(token, validate=True).decode("utf-8")
        api_base, app_key = decoded.rsplit(".", 1)
    except (binascii.Error, UnicodeDecodeError, ValueError):
        raise ZendureCloudError("invalid_token") from None

    parsed = urlsplit(api_base)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or not app_key
    ):
        raise ZendureCloudError("invalid_token")
    normalized_base = api_base.rstrip("/")
    return ZendureAppToken(token, normalized_base, app_key)


class ZendureCloudClient:
    """Perform the sole read-only account bootstrap request."""

    def __init__(
        self,
        post_json: PostJson,
        *,
        timeout: float = 15.0,
        clock: Callable[[], float] = time.time,
        nonce_factory: Callable[[], str] | None = None,
    ) -> None:
        self._post_json = post_json
        self._timeout = timeout
        self._clock = clock
        self._nonce_factory = nonce_factory or (
            lambda: str(secrets.randbelow(90000) + 10000)
        )

    async def async_discover(self, encoded_token: str) -> ZendureCloudBootstrap:
        """Read and validate every device in the Zendure account."""

        token = parse_app_token(encoded_token)
        body = {"appKey": token.app_key}
        timestamp = int(self._clock())
        nonce = self._nonce_factory()
        headers = _signed_headers(body, timestamp, nonce)
        try:
            response = await asyncio.wait_for(
                self._post_json(
                    f"{token.api_base}{DEVICE_LIST_PATH}",
                    json=body,
                    headers=headers,
                ),
                timeout=self._timeout,
            )
            payload = await asyncio.wait_for(response.json(), timeout=self._timeout)
        except TimeoutError:
            raise ZendureCloudError("timeout") from None
        except ZendureCloudError:
            raise
        except Exception:
            raise ZendureCloudError("cannot_connect") from None
        return _parse_bootstrap(payload)


def _signed_headers(
    body: Mapping[str, Any], timestamp: int, nonce: str
) -> dict[str, str]:
    params = {**body, "timestamp": timestamp, "nonce": nonce}
    body_string = "".join(f"{key}{value}" for key, value in sorted(params.items()))
    signature = hashlib.sha1(  # noqa: S324 - required by Zendure protocol
        f"{_SIGNING_KEY}{body_string}{_SIGNING_KEY}".encode()
    ).hexdigest().upper()
    return {
        "Content-Type": "application/json",
        "timestamp": str(timestamp),
        "nonce": nonce,
        "clientid": CLIENT_ID,
        "sign": signature,
    }


def _parse_bootstrap(payload: Any) -> ZendureCloudBootstrap:
    if not isinstance(payload, Mapping):
        raise ZendureCloudError("invalid_response")
    if payload.get("code") != 200 or payload.get("success") is not True:
        raise ZendureCloudError("invalid_or_expired_token")
    data = payload.get("data")
    if not isinstance(data, Mapping):
        raise ZendureCloudError("invalid_response")
    raw_devices = data.get("deviceList")
    if not isinstance(raw_devices, list):
        raise ZendureCloudError("invalid_response")
    if not raw_devices:
        raise ZendureCloudError("no_devices")

    devices = tuple(_parse_device(item) for item in raw_devices)
    candidate_ids = [item.candidate.candidate_id for item in devices]
    if len(candidate_ids) != len(set(candidate_ids)):
        unique_devices: list[ZendureCloudDevice] = []
        unique_raw_devices: list[Mapping[str, Any]] = []
        first_by_candidate: dict[
            str, tuple[ZendureCloudDevice, Mapping[str, Any]]
        ] = {}
        redundant_records = True
        for device, raw in zip(devices, raw_devices, strict=True):
            candidate_id = device.candidate.candidate_id
            first = first_by_candidate.get(candidate_id)
            if first is None:
                first_by_candidate[candidate_id] = (device, raw)
                unique_devices.append(device)
                unique_raw_devices.append(raw)
                continue
            if not _same_supported_device_metadata(first[1], raw):
                redundant_records = False
        _log_duplicate_device_identities(
            devices, raw_devices, redundant_records_ignored=redundant_records
        )
        if not redundant_records:
            raise ZendureCloudError("duplicate_device_id")
        devices = tuple(unique_devices)
        raw_devices = unique_raw_devices
    mqtt = _parse_mqtt(data.get("mqtt"))
    raw_device_list = tuple(
        deepcopy(dict(item)) for item in raw_devices if isinstance(item, Mapping)
    )
    return ZendureCloudBootstrap(
        devices=devices,
        mqtt=mqtt,
        raw_device_list=raw_device_list,
    )


def _log_duplicate_device_identities(
    devices: tuple[ZendureCloudDevice, ...],
    raw_devices: list[Any],
    *,
    redundant_records_ignored: bool,
) -> None:
    """Log duplicate positions and a privacy-safe metadata comparison."""
    seen: dict[str, int] = {}
    duplicates: list[tuple[int, int, str, str, dict[str, Any]]] = []
    safe_fields = {
        "deviceKey": "device_key",
        "snNumber": "serial_number",
        "productKey": "product_key",
        "productModel": "product_model",
        "deviceName": "device_name",
        "online": "online",
        "isOnline": "is_online",
        "packNum": "pack_count",
        "packData": "pack_data",
        "ip": "ip_address",
    }
    for position, device in enumerate(devices, start=1):
        identity = device.candidate.identity
        key = device.candidate.candidate_id
        first_position = seen.get(key)
        if first_position is None:
            seen[key] = position
            continue
        identity_source = "deviceKey" if identity.device_id else "serialNumber"
        model = identity.product_model or "unknown"
        first_raw = raw_devices[first_position - 1]
        current_raw = raw_devices[position - 1]
        if not isinstance(first_raw, Mapping) or not isinstance(current_raw, Mapping):
            comparison = {"records_identical": False, "comparison_available": False}
        else:
            differing_fields = tuple(
                field
                for field in safe_fields
                if first_raw.get(field) != current_raw.get(field)
            )
            known_fields = set(safe_fields)
            first_other = {
                field: value for field, value in first_raw.items() if field not in known_fields
            }
            current_other = {
                field: value for field, value in current_raw.items() if field not in known_fields
            }
            missing = object()
            other_differing_fields = tuple(
                sorted(
                    {
                        _safe_diagnostic_field_name(field)
                        for field in set(first_other) | set(current_other)
                        if first_other.get(field, missing)
                        != current_other.get(field, missing)
                    }
                )
            )
            comparison = {
                "records_identical": dict(first_raw) == dict(current_raw),
                "differing_fields": differing_fields,
                "other_fields_differ": first_other != current_other,
                "other_differing_fields": other_differing_fields,
            }
        duplicates.append(
            (first_position, position, identity_source, model, comparison)
        )

    action = (
        "redundant records with matching supported metadata were ignored"
        if redundant_records_ignored
        else "conflicting duplicate identities were rejected"
    )
    _LOGGER.warning(
        "Zendure device discovery returned duplicate identities; %s; "
        "duplicate positions and sanitized metadata comparison "
        "(no identifier or field values): %s",
        action,
        duplicates,
    )


def _same_supported_device_metadata(
    first: Mapping[str, Any], current: Mapping[str, Any]
) -> bool:
    """Allow duplicate rows only when all behavior-relevant fields agree."""
    supported_fields = (
        "deviceKey",
        "snNumber",
        "productKey",
        "productModel",
        "deviceName",
        "online",
        "isOnline",
        "packNum",
        "packData",
        "ip",
    )
    return all(first.get(field) == current.get(field) for field in supported_fields)


def _safe_diagnostic_field_name(field: Any) -> str:
    """Return a field name without logging its associated value."""
    name = str(field)
    if not _DIAGNOSTIC_FIELD_NAME_PATTERN.fullmatch(name):
        return _REDACTED_FIELD_NAME
    return name


_KNOWN_DEVICE_FIELDS = {
    "deviceKey",
    "productKey",
    "productModel",
    "snNumber",
    "deviceName",
    "online",
    "isOnline",
    "packData",
    "packNum",
    "ip",
}


def _parse_device(value: Any) -> ZendureCloudDevice:
    if not isinstance(value, Mapping):
        raise ZendureCloudError("invalid_response")
    device_id = _text(value.get("deviceKey"))
    serial = _text(value.get("snNumber"))
    if device_id is None and serial is None:
        raise ZendureCloudError("incomplete_device")
    model = _text(value.get("productModel"))
    product_id = _text(value.get("productKey"))
    name = _text(value.get("deviceName")) or model or "Zendure device"
    pack_data = value.get("packData")
    if isinstance(pack_data, list):
        pack_count = len(pack_data)
    else:
        raw_count = value.get("packNum")
        pack_count = (
            raw_count
            if isinstance(raw_count, int)
            and not isinstance(raw_count, bool)
            and raw_count >= 0
            else None
        )
    online_raw = value.get("online", value.get("isOnline"))
    online = online_raw if isinstance(online_raw, bool) else None
    identity = NativeDeviceIdentity(
        transport=ZendureTransport.CLOUD_MQTT,
        device_id=device_id,
        serial_number=serial,
        product_id=product_id,
        product_model=model,
    )
    candidate = DiscoveryCandidate(
        identity=identity,
        display_name=name,
        supported=resolve_zendure_device(identity) is not None,
        pack_count=pack_count,
    )
    return ZendureCloudDevice(
        candidate=candidate,
        online=online,
        pack_count=pack_count,
        extra_field_names=tuple(
            sorted(str(key) for key in value if key not in _KNOWN_DEVICE_FIELDS)
        ),
    )


def _parse_mqtt(value: Any) -> CloudMqttCredentials:
    if not isinstance(value, Mapping):
        raise ZendureCloudError("no_mqtt_credentials")
    fields = tuple(
        _text(value.get(key))
        for key in ("clientId", "url", "username", "password")
    )
    if any(item is None for item in fields):
        raise ZendureCloudError("no_mqtt_credentials")
    client_id, url, username, password = fields
    return CloudMqttCredentials(client_id, url, username, password)  # type: ignore[arg-type]


def _text(value: Any) -> str | None:
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        return None
    text = str(value).strip()
    return text or None
