"""State-reading Zendure Cloud MQTT transport with typed property writes.

The public transport surface deliberately contains no arbitrary publish API.
State requests and gate-authorized commands use separately typed methods while
credentials remain inside the transport boundary.
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
import hashlib
import ipaddress
import json
import logging
import random
import socket
import ssl
from typing import Any, Callable, Mapping, Protocol
from urllib.parse import urlsplit

from .zendure_cloud import CloudMqttCredentials, ZendureCloudBootstrap
from .zendure_privacy import ZendureDiagnosticSanitizer
from .native_command_verification import NativeCommandVerificationManager
from .native_device_command_gate import AuthorizedNativeCommand
from .zendure_cloud_mqtt_commands import (
    CloudCommandResult,
    CloudCommandStatus,
    CloudPropertyWrite,
    ZendureCloudCommandAdapter,
)


_LOGGER = logging.getLogger(__name__)
_MAX_RETAINED_MESSAGES = 10_000


class CloudMqttError(Exception):
    """Safe, classified Cloud MQTT failure."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class ConnectionState(StrEnum):
    """Observable state of the read-only Cloud transport."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    STOPPED = "stopped"


@dataclass(frozen=True, slots=True)
class CloudMqttMessage:
    """One lossless inbound MQTT message plus safe routing metadata."""

    received_at: datetime
    topic: str
    payload: bytes = field(repr=False)
    parsed_payload: Any = field(repr=False)
    payload_format: str
    device_candidate_id: str | None
    pack_id: str | None
    known_topic: bool
    session_number: int
    transport: str = "cloud_mqtt"


@dataclass(slots=True)
class CloudMqttDeviceState:
    """Freshness facts observed for one discovered main device."""

    last_message_at: datetime | None = None
    online: bool | None = None
    property_updated_at: dict[str, datetime] = field(default_factory=dict)


MessageCallback = Callable[[str, bytes], None]
ConnectCallback = Callable[[bool, str | None], None]
DisconnectCallback = Callable[[str | None], None]


class CloudMqttSession(Protocol):
    """Minimal typed session contract without an arbitrary publish surface."""

    def set_callbacks(
        self,
        on_connect: ConnectCallback,
        on_disconnect: DisconnectCallback,
        on_message: MessageCallback,
    ) -> None: ...

    def connect(self) -> None: ...

    def subscribe(self, topics: tuple[str, ...]) -> None: ...

    def request_all(
        self,
        product_id: str,
        device_id: str,
        message_id: int,
        timestamp: int,
    ) -> None: ...

    def write_property(
        self,
        product_id: str,
        device_id: str,
        write: CloudPropertyWrite,
    ) -> bool: ...

    def disconnect(self) -> None: ...

    @property
    def connection_phase(self) -> str: ...

    @property
    def connection_diagnostics(self) -> Mapping[str, str | bool]: ...


SessionFactory = Callable[[CloudMqttCredentials], CloudMqttSession]


class ZendureCloudMqttTransport:
    """Receive all Cloud MQTT traffic for every discovered Zendure system."""

    def __init__(
        self,
        bootstrap: ZendureCloudBootstrap,
        *,
        session_factory: SessionFactory | None = None,
        clock: Callable[[], datetime] | None = None,
        reconnect_delays: tuple[float, ...] = (1.0, 2.0, 5.0, 15.0, 30.0),
        max_messages: int = _MAX_RETAINED_MESSAGES,
    ) -> None:
        self._bootstrap = bootstrap
        self._session_factory = session_factory or PahoReadOnlyMqttSession
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._reconnect_delays = reconnect_delays
        self._messages: deque[CloudMqttMessage] = deque(maxlen=max_messages)
        self._state = ConnectionState.DISCONNECTED
        self._session: CloudMqttSession | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._connected = asyncio.Event()
        self._connect_failure: str | None = None
        self._stopping = False
        self._reconnect_task: asyncio.Task[None] | None = None
        self._session_number = 0
        self._request_message_id = 0
        self._last_message_at: datetime | None = None
        self._last_connection_phase = "not_started"
        self._last_connection_diagnostics: dict[str, str | bool] = {
            "credential_source": "cloud_mqtt_block",
            "transport_security": "unknown",
            "endpoint_scope": "unknown",
            "socket_family": "unknown",
            "connect_packet_sent": False,
        }
        self._verification = NativeCommandVerificationManager()
        self._command_adapter: ZendureCloudCommandAdapter | None = None
        self._command_lock = asyncio.Lock()
        self._devices = {
            item.candidate.candidate_id: CloudMqttDeviceState(
                online=item.online
            )
            for item in bootstrap.devices
        }
        self._routes: list[tuple[str, str, str | None]] = []
        for item in bootstrap.devices:
            identity = item.candidate.identity
            if identity.device_id:
                self._routes.append(
                    (identity.device_id, item.candidate.candidate_id, identity.product_id)
                )

    @property
    def state(self) -> ConnectionState:
        return self._state

    @property
    def messages(self) -> tuple[CloudMqttMessage, ...]:
        return tuple(self._messages)

    @property
    def last_message_at(self) -> datetime | None:
        return self._last_message_at

    @property
    def device_states(self) -> Mapping[str, CloudMqttDeviceState]:
        return dict(self._devices)

    @property
    def command_diagnostics(self) -> Mapping[str, Any]:
        """Return bounded verification facts without MQTT payloads or identities."""

        return self._verification.diagnostics()

    async def async_execute_authorized(
        self, authorized: AuthorizedNativeCommand
    ) -> CloudCommandResult:
        """Execute a gate-issued command; this is not an arbitrary publish API."""

        async with self._command_lock:
            if self._state is not ConnectionState.CONNECTED or self._session is None:
                return CloudCommandResult(
                    CloudCommandStatus.REJECTED, "transport_not_connected"
                )
            if self._command_adapter is None:
                self._command_adapter = ZendureCloudCommandAdapter(
                    self._bootstrap,
                    self._session,
                    self._verification,
                    clock=self._clock,
                )
            return await asyncio.to_thread(self._command_adapter.execute, authorized)

    @property
    def connection_variant(self) -> str:
        """Return a safe identifier for the currently tested Cloud dialect."""

        return "mqtt31_persistent"

    @property
    def connection_phase(self) -> str:
        """Return the furthest privacy-safe connection phase observed."""

        if self._session is not None:
            return str(
                getattr(self._session, "connection_phase", self._last_connection_phase)
            )
        return self._last_connection_phase

    @property
    def connection_diagnostics(self) -> Mapping[str, str | bool]:
        """Return only allow-listed, non-identifying connection facts."""

        if self._session is not None:
            value = getattr(self._session, "connection_diagnostics", None)
            if isinstance(value, Mapping):
                return dict(value)
        return dict(self._last_connection_diagnostics)

    @property
    def topics(self) -> tuple[str, ...]:
        """Return broad read-only subscriptions without guessing properties."""

        topics: set[str] = set()
        for device_id, _candidate_id, product_id in self._routes:
            if product_id:
                topics.add(f"/{product_id}/{device_id}/#")
                topics.add(f"iot/{product_id}/{device_id}/#")
            else:
                topics.add(f"/+/{device_id}/#")
                topics.add(f"iot/+/{device_id}/#")
        return tuple(sorted(topics))

    async def async_start(self, *, timeout: float = 15.0) -> None:
        """Start the subscriber and wait for the initial broker connection."""

        if self._state not in {ConnectionState.DISCONNECTED, ConnectionState.STOPPED}:
            return
        if not self.topics:
            raise CloudMqttError("no_routable_devices")
        self._loop = asyncio.get_running_loop()
        self._stopping = False
        self._connected.clear()
        self._connect_failure = None
        self._state = ConnectionState.CONNECTING
        await self._open_session()
        try:
            await asyncio.wait_for(self._connected.wait(), timeout=timeout)
        except TimeoutError:
            await self.async_stop()
            raise CloudMqttError("connection_timeout") from None
        if self._connect_failure is not None:
            reason = self._connect_failure
            await self.async_stop()
            raise CloudMqttError(reason)

    async def async_stop(self) -> None:
        """Stop reconnects and disconnect the read-only subscriber."""

        self._stopping = True
        task = self._reconnect_task
        self._reconnect_task = None
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        session, self._session = self._session, None
        if session is not None:
            self._last_connection_phase = str(
                getattr(session, "connection_phase", self._last_connection_phase)
            )
            value = getattr(session, "connection_diagnostics", None)
            if isinstance(value, Mapping):
                self._last_connection_diagnostics = dict(value)
            try:
                await asyncio.to_thread(session.disconnect)
            except Exception:
                _LOGGER.warning("Zendure Cloud MQTT cleanup failed")
        self._connected.clear()
        self._state = ConnectionState.STOPPED

    async def _open_session(self) -> None:
        self._session_number += 1
        session = self._session_factory(self._bootstrap.mqtt)
        session.set_callbacks(self._on_connect, self._on_disconnect, self._on_message)
        self._session = session
        self._command_adapter = None
        # The production backend starts Paho's non-blocking network loop here.
        # A custom backend may still perform blocking setup, so retain the
        # thread boundary to protect Home Assistant's event loop.
        await asyncio.to_thread(session.connect)

    def _threadsafe(self, callback: Callable[..., None], *args: Any) -> None:
        if self._loop is not None:
            self._loop.call_soon_threadsafe(callback, *args)

    def _on_connect(self, successful: bool, reason: str | None) -> None:
        self._threadsafe(self._handle_connect, successful, reason)

    def _handle_connect(self, successful: bool, reason: str | None) -> None:
        if self._stopping:
            return
        if not successful:
            safe = ZendureDiagnosticSanitizer().sanitize(reason or "unknown")
            _LOGGER.warning(
                "Zendure Cloud MQTT authentication/connect failed: %s", safe
            )
            self._schedule_reconnect()
            return
        if self._session is None:
            return
        try:
            self._session.subscribe(self.topics)
            for device_id, _candidate_id, product_id in self._routes:
                if product_id is None:
                    continue
                self._request_message_id += 1
                self._session.request_all(
                    product_id,
                    device_id,
                    self._request_message_id,
                    int(self._clock().timestamp()),
                )
        except CloudMqttError as error:
            _LOGGER.warning(
                "Zendure Cloud MQTT state request failed: %s", error.reason
            )
            self._connect_failure = error.reason
            self._connected.set()
            return
        self._state = ConnectionState.CONNECTED
        self._connected.set()
        _LOGGER.info(
            "Zendure Cloud MQTT connected; subscribed to %d state topics",
            len(self.topics),
        )

    def _on_disconnect(self, reason: str | None) -> None:
        self._threadsafe(self._handle_disconnect, reason)

    def _handle_disconnect(self, reason: str | None) -> None:
        self._connected.clear()
        if self._stopping:
            return
        safe = ZendureDiagnosticSanitizer().sanitize(reason or "unknown")
        _LOGGER.warning("Zendure Cloud MQTT disconnected: %s", safe)
        self._schedule_reconnect()

    def _schedule_reconnect(self) -> None:
        if self._reconnect_task is None or self._reconnect_task.done():
            self._state = ConnectionState.RECONNECTING
            self._reconnect_task = asyncio.create_task(self._reconnect())

    async def _reconnect(self) -> None:
        attempt = 0
        while not self._stopping:
            delay = self._reconnect_delays[
                min(attempt, len(self._reconnect_delays) - 1)
            ]
            if self._stopping:
                return
            await asyncio.sleep(delay + random.uniform(0, min(0.25, delay / 4)))
            self._connected.clear()
            self._connect_failure = None
            old, self._session = self._session, None
            if old is not None:
                try:
                    await asyncio.to_thread(old.disconnect)
                except Exception:
                    _LOGGER.warning("Zendure Cloud MQTT reconnect cleanup failed")
            try:
                await self._open_session()
                await asyncio.wait_for(self._connected.wait(), timeout=15.0)
                if self._connect_failure is not None:
                    raise CloudMqttError(self._connect_failure)
                return
            except Exception as error:  # backend errors are sanitized before logging
                safe = ZendureDiagnosticSanitizer().sanitize_exception(error)
                _LOGGER.warning("Zendure Cloud MQTT reconnect failed: %s", safe)
                attempt += 1

    def _on_message(self, topic: str, payload: bytes) -> None:
        self._threadsafe(self._handle_message, topic, bytes(payload))

    def _handle_message(self, topic: str, payload: bytes) -> None:
        received_at = self._clock()
        parsed, payload_format = _parse_payload(payload)
        candidate_id, pack_id = self._route_message(topic, parsed)
        known_topic = (
            topic.endswith("/properties/report")
            or topic.endswith("/properties/energy")
            or topic.endswith("/state")
        )
        message = CloudMqttMessage(
            received_at=received_at,
            topic=topic,
            payload=payload,
            parsed_payload=parsed,
            payload_format=payload_format,
            device_candidate_id=candidate_id,
            pack_id=pack_id,
            known_topic=known_topic,
            session_number=self._session_number,
        )
        self._messages.append(message)
        self._last_message_at = received_at
        if candidate_id is not None:
            state = self._devices[candidate_id]
            state.last_message_at = received_at
            for name in _property_names(parsed):
                state.property_updated_at[name] = received_at
            online = _online_value(parsed)
            if online is not None:
                state.online = online
            properties = parsed.get("properties") if isinstance(parsed, Mapping) else None
            if isinstance(properties, Mapping) and self._command_adapter is not None:
                self._command_adapter.observe_properties(
                    device_id=candidate_id,
                    properties=properties,
                    observed_at=received_at,
                )

    def _route_message(self, topic: str, parsed: Any) -> tuple[str | None, str | None]:
        segments = {part for part in topic.split("/") if part}
        payload_ids = _identity_values(parsed)
        for device_id, candidate_id, _product_id in self._routes:
            if device_id in segments or device_id in payload_ids:
                return candidate_id, _pack_identity(parsed, device_id)
        return None, _pack_identity(parsed, None)


def _parse_payload(payload: bytes) -> tuple[Any, str]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        return payload, "binary"
    try:
        return json.loads(text), "json"
    except (json.JSONDecodeError, ValueError):
        return text, "text"


def _property_write_request(
    product_id: str,
    device_id: str,
    write: CloudPropertyWrite,
) -> tuple[str, str]:
    """Build the one allow-listed Zendure Cloud property-write envelope."""

    if not product_id or not device_id or not write.property_name:
        raise CloudMqttError("invalid_write_address")
    return (
        f"iot/{product_id}/{device_id}/properties/write",
        json.dumps(
            {
                "properties": {write.property_name: write.value},
                "messageId": write.message_id,
                "deviceId": device_id,
                "timestamp": write.timestamp,
            },
            separators=(",", ":"),
        ),
    )


def _identity_values(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).casefold() in {"devicekey", "deviceid", "sn", "snnumber"} and isinstance(item, (str, int)):
                found.add(str(item))
            found.update(_identity_values(item))
    elif isinstance(value, list):
        for item in value:
            found.update(_identity_values(item))
    return found


def _pack_identity(value: Any, main_device_id: str | None) -> str | None:
    if not isinstance(value, Mapping):
        return None
    for key in ("packId", "packKey", "packSn", "packSN"):
        item = value.get(key)
        if isinstance(item, (str, int)) and str(item) != main_device_id:
            return str(item)
    return None


def _property_names(value: Any) -> set[str]:
    if not isinstance(value, Mapping):
        return set()
    properties = value.get("properties")
    if isinstance(properties, Mapping):
        return {str(name) for name in properties}
    return set()


def _online_value(value: Any) -> bool | None:
    if not isinstance(value, Mapping):
        return None
    raw = value.get("online")
    if isinstance(raw, bool):
        return raw
    if raw in (0, 1):
        return bool(raw)
    return None


class PahoReadOnlyMqttSession:
    """Paho session exposing only typed state and property operations."""

    def __init__(self, credentials: CloudMqttCredentials) -> None:
        try:
            import paho.mqtt.client as mqtt
        except ImportError as error:
            raise CloudMqttError("mqtt_dependency_missing") from error

        self._host, self._port, self._tls = _parse_broker_url(credentials.url)
        self._connection_phase = "created"
        self._endpoint_scope = "unknown"
        self._socket_family = "unknown"
        self._connect_packet_sent = False
        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=_bsfai_client_id(credentials.client_id),
            clean_session=False,
            protocol=mqtt.MQTTv31,
        )
        self._client.username_pw_set(credentials.username, credentials.password)
        if self._tls:
            self._client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
        self._on_connect: ConnectCallback | None = None
        self._on_disconnect: DisconnectCallback | None = None
        self._on_message: MessageCallback | None = None

    @property
    def connection_phase(self) -> str:
        return self._connection_phase

    @property
    def connection_diagnostics(self) -> Mapping[str, str | bool]:
        return {
            "credential_source": "cloud_mqtt_block",
            "transport_security": "tls" if self._tls else "plain",
            "endpoint_scope": self._endpoint_scope,
            "socket_family": self._socket_family,
            "connect_packet_sent": self._connect_packet_sent,
        }

    def set_callbacks(
        self,
        on_connect: ConnectCallback,
        on_disconnect: DisconnectCallback,
        on_message: MessageCallback,
    ) -> None:
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect
        self._on_message = on_message
        self._client.on_connect = self._paho_connect
        self._client.on_disconnect = self._paho_disconnect
        self._client.on_message = self._paho_message
        self._client.on_socket_open = self._paho_socket_open
        self._client.on_socket_register_write = self._paho_register_write
        self._client.on_socket_unregister_write = self._paho_unregister_write

    def connect(self) -> None:
        self._connection_phase = "dns_or_tcp_connect"
        self._client.connect_async(self._host, self._port, keepalive=60)
        self._client.loop_start()

    def subscribe(self, topics: tuple[str, ...]) -> None:
        for topic in topics:
            result, _mid = self._client.subscribe(topic, qos=0)
            if result != 0:
                raise CloudMqttError("subscribe_failed")

    def request_all(
        self,
        product_id: str,
        device_id: str,
        message_id: int,
        timestamp: int,
    ) -> None:
        topic, payload = _get_all_request(
            product_id, device_id, message_id, timestamp
        )
        result = self._client.publish(topic, payload)
        result_code = getattr(result, "rc", None)
        if result_code is None:
            try:
                result_code = result[0]
            except (IndexError, TypeError):
                result_code = None
        if result_code != 0:
            raise CloudMqttError("state_request_failed")

    def write_property(
        self,
        product_id: str,
        device_id: str,
        write: CloudPropertyWrite,
    ) -> bool:
        topic, payload = _property_write_request(product_id, device_id, write)
        result = self._client.publish(topic, payload, qos=0, retain=False)
        result_code = getattr(result, "rc", None)
        if result_code is None:
            try:
                result_code = result[0]
            except (IndexError, TypeError):
                return False
        return result_code == 0

    def disconnect(self) -> None:
        try:
            self._client.disconnect()
        finally:
            self._client.loop_stop()

    def _paho_connect(
        self,
        _client: Any,
        _userdata: Any,
        _flags: Any,
        reason_code: Any,
        _properties: Any,
    ) -> None:
        successful = _reason_code_success(reason_code)
        self._connection_phase = (
            "mqtt_connack_accepted" if successful else "mqtt_connack_rejected"
        )
        if self._on_connect is not None:
            self._on_connect(successful, None if successful else str(reason_code))

    def _paho_socket_open(self, _client: Any, _userdata: Any, mqtt_socket: Any) -> None:
        self._socket_family = _safe_socket_family(mqtt_socket)
        self._endpoint_scope = _safe_peer_scope(mqtt_socket)
        self._connection_phase = "tcp_connected_waiting_for_mqtt_connack"

    def _paho_register_write(self, _client: Any, _userdata: Any, _socket: Any) -> None:
        if self._connection_phase.startswith("tcp_connected"):
            self._connection_phase = "mqtt_connect_queued"

    def _paho_unregister_write(self, _client: Any, _userdata: Any, _socket: Any) -> None:
        if self._connection_phase in {
            "tcp_connected_waiting_for_mqtt_connack",
            "mqtt_connect_queued",
        }:
            self._connect_packet_sent = True
            self._connection_phase = "mqtt_connect_sent_waiting_for_connack"

    def _paho_disconnect(
        self,
        _client: Any,
        _userdata: Any,
        _flags: Any,
        reason_code: Any,
        _properties: Any,
    ) -> None:
        if self._on_disconnect is not None:
            self._on_disconnect(
                None if _reason_code_success(reason_code) else str(reason_code)
            )

    def _paho_message(self, _client: Any, _userdata: Any, message: Any) -> None:
        if self._on_message is not None:
            self._on_message(str(message.topic), bytes(message.payload))


def _safe_socket_family(mqtt_socket: Any) -> str:
    """Classify a socket family without exporting an address."""

    family = getattr(mqtt_socket, "family", None)
    if family == socket.AF_INET:
        return "ipv4"
    if family == socket.AF_INET6:
        return "ipv6"
    return "other"


def _reason_code_success(reason_code: Any) -> bool:
    """Handle Paho 2.x ReasonCode objects and legacy integer codes."""

    is_failure = getattr(reason_code, "is_failure", None)
    if isinstance(is_failure, bool):
        return not is_failure
    value = getattr(reason_code, "value", reason_code)
    try:
        return int(value) == 0
    except (TypeError, ValueError):
        return str(reason_code).strip().casefold() == "success"


def _bsfai_client_id(cloud_client_id: str) -> str:
    """Return a stable MQTT 3.1 ID distinct from Zendure-HA's identity.

    MQTT 3.1 brokers may restrict client IDs to 23 characters.  Hashing the
    account-provided ID keeps the BSFAI identity stable without exposing the
    original identifier in the broker session name.
    """

    digest = hashlib.sha256(cloud_client_id.encode("utf-8")).hexdigest()[:16]
    return f"bsfai-{digest}"


def _get_all_request(
    product_id: str,
    device_id: str,
    message_id: int,
    timestamp: int,
) -> tuple[str, str]:
    """Build the sole allow-listed outbound state request."""

    return (
        f"iot/{product_id}/{device_id}/properties/read",
        json.dumps(
            {
                "properties": ["getAll"],
                "messageId": message_id,
                "deviceId": device_id,
                "timestamp": timestamp,
            },
            separators=(",", ":"),
        ),
    )


def _safe_peer_scope(mqtt_socket: Any) -> str:
    """Classify the connected peer without retaining its address."""

    try:
        peer = mqtt_socket.getpeername()
        raw_address = peer[0] if isinstance(peer, tuple) and peer else peer
        address = ipaddress.ip_address(str(raw_address).split("%", 1)[0])
    except (OSError, TypeError, ValueError):
        return "unknown"
    if address.is_loopback:
        return "loopback"
    if address.is_private or address.is_link_local:
        return "private"
    if address.is_global:
        return "public"
    return "other"


def _parse_broker_url(value: str) -> tuple[str, int, bool]:
    """Parse Zendure's schema-free port-1883 broker as plain MQTT.

    TLS is enabled only when Zendure explicitly returns an MQTT TLS scheme.
    This mirrors the official Zendure-HA Cloud connection behavior while
    retaining support for an explicit secure endpoint.
    """

    parsed = urlsplit(value if "://" in value else f"mqtt://{value}")
    if not parsed.hostname or parsed.scheme not in {"mqtt", "mqtts", "ssl", "tcp"}:
        raise CloudMqttError("invalid_broker_url")
    tls = parsed.scheme in {"mqtts", "ssl"}
    try:
        port = parsed.port or (8883 if tls else 1883)
    except ValueError:
        raise CloudMqttError("invalid_broker_url") from None
    return parsed.hostname, port, tls
