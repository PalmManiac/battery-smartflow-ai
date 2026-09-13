"""Dedicated Local MQTT transport for verified ZendureLegacy devices."""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
from dataclasses import dataclass, field, replace
from urllib.parse import urlparse

from .core.models import ZendureTransport
from .native_device_command_gate import AuthorizedNativeCommand
from .zendure_cloud import (
    CloudMqttCredentials,
    ZendureCloudBootstrap,
)
from .zendure_cloud_mqtt import (
    ConnectionState,
    PahoReadOnlyMqttSession,
    ZendureCloudMqttTransport,
)
from .zendure_device_matrix import preferred_local_transport
from .zendure_local_mqtt_commands import (
    LocalMqttCommandResult,
    LocalMqttCommandStatus,
    LocalMqttInvocation,
    ZendureLocalMqttCommandAdapter,
)
from .zendure_legacy import ZendureLegacyCloudBridge

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True, repr=False)
class LocalMqttCredentials:
    """Opaque user-configured broker values kept inside the transport layer."""

    server: str = field(repr=False)
    port: int = field(default=1883, repr=False)
    username: str = field(default="", repr=False)
    password: str = field(default="", repr=False)

    def __post_init__(self) -> None:
        if not self.server.strip() or not 1 <= int(self.port) <= 65535:
            raise ValueError("invalid_local_mqtt_endpoint")

    def __repr__(self) -> str:
        return "LocalMqttCredentials([REDACTED])"


class PahoLocalMqttSession(PahoReadOnlyMqttSession):
    """Paho session with exactly one additional typed legacy invocation."""

    @property
    def connection_diagnostics(self):
        value = dict(super().connection_diagnostics)
        value["credential_source"] = "local_mqtt_options"
        return value

    def invoke_function(
        self,
        product_id: str,
        device_id: str,
        invocation: LocalMqttInvocation,
        message_id: int,
        timestamp: int,
    ) -> bool:
        if not product_id or not device_id or invocation.function != "deviceAutomation":
            return False
        topic = f"iot/{product_id}/{device_id}/function/invoke"
        payload = json.dumps(
            {
                "arguments": list(invocation.arguments),
                "function": invocation.function,
                "messageId": message_id,
                "deviceKey": device_id,
                "deviceId": device_id,
                "timestamp": timestamp,
            },
            separators=(",", ":"),
        )
        result = self._client.publish(topic, payload, qos=0, retain=False)
        result_code = getattr(result, "rc", None)
        if result_code is None:
            try:
                result_code = result[0]
            except (IndexError, TypeError):
                return False
        return result_code == 0

    def relay_cloud_message(self, topic: str, payload: bytes | str) -> bool:
        """Relay one validated device Cloud message to the local broker."""

        if not topic.startswith("iot/") or "#" in topic or "+" in topic:
            return False
        result = self._client.publish(topic, payload, qos=0, retain=False)
        return getattr(result, "rc", result[0] if isinstance(result, tuple) else None) == 0


class ZendureLocalMqttTransport(ZendureCloudMqttTransport):
    """Reuse hardened MQTT lifecycle while retaining a distinct local adapter."""

    def __init__(
        self,
        bootstrap: ZendureCloudBootstrap,
        credentials: LocalMqttCredentials,
        *,
        session_factory=None,
        clock=None,
        reconnect_delays=(1.0, 2.0, 5.0, 15.0, 30.0),
        max_messages=10_000,
        bridge_factory=None,
    ) -> None:
        devices = tuple(
            item
            for item in bootstrap.devices
            if preferred_local_transport(item.candidate.identity)
            is ZendureTransport.LOCAL_MQTT
        )
        local_bootstrap = ZendureCloudBootstrap(
            devices=devices,
            mqtt=CloudMqttCredentials(
                # A reload may briefly overlap the previous runtime. A unique
                # local client identity prevents MQTT "session taken over"
                # disconnects during that handover.
                client_id=(
                    f"local:{credentials.username or 'anonymous'}:"
                    f"{secrets.token_hex(8)}"
                ),
                url=f"mqtt://{credentials.server}:{int(credentials.port)}",
                username=credentials.username,
                password=credentials.password,
            ),
            raw_device_list=bootstrap.raw_device_list,
        )
        super().__init__(
            local_bootstrap,
            session_factory=session_factory or PahoLocalMqttSession,
            clock=clock,
            reconnect_delays=reconnect_delays,
            max_messages=max_messages,
        )
        # Keep the original Cloud bootstrap separate. ``super()`` stores the
        # Local bootstrap for subscriptions and commands; passing that object
        # to the bridge would connect a device-shaped Cloud session to the
        # Local broker and evict the real Legacy device with the same client ID.
        self._cloud_bootstrap = bootstrap
        self._local_adapter: ZendureLocalMqttCommandAdapter | None = None
        self._bridge_factory = bridge_factory or ZendureLegacyCloudBridge
        self._legacy_bridge: ZendureLegacyCloudBridge | None = None
        self._bridge_disabled_reason: str | None = None

    @property
    def bridge_connected_devices(self) -> int:
        return (
            len(self._legacy_bridge.connected_devices)
            if self._legacy_bridge is not None
            else 0
        )

    @property
    def bridge_status(self) -> str:
        if self._bridge_disabled_reason is not None:
            return self._bridge_disabled_reason
        return (
            self._legacy_bridge.status
            if self._legacy_bridge is not None
            else "not_started"
        )

    def _publish_bridged_local(self, topic: str, payload: bytes | str) -> bool:
        session = self._session
        publish = getattr(session, "relay_cloud_message", None)
        return bool(publish and publish(topic, payload))

    async def async_start(self, *, timeout: float = 15.0) -> None:
        await super().async_start(timeout=timeout)
        if _same_mqtt_endpoint(
            self._cloud_bootstrap.mqtt.url,
            self._bootstrap.mqtt.url,
        ):
            # Never let a device-ID Cloud session compete with the physical
            # Legacy device on its Local broker. Local telemetry/control stays
            # available; only the optional app-compatibility bridge is omitted.
            self._bridge_disabled_reason = "disabled_same_endpoint"
            _LOGGER.warning(
                "Zendure Legacy Cloud bridge disabled because Cloud and Local "
                "MQTT endpoints are identical"
            )
            return
        bridge = self._bridge_factory(
            self._cloud_bootstrap,
            self._publish_bridged_local,
        )
        try:
            await bridge.async_start(timeout=timeout)
        except Exception as error:
            # Local control remains useful during a Zendure Cloud outage. The
            # bridge is compatibility support for the app, not write authority.
            _LOGGER.warning("Zendure Legacy Cloud bridge unavailable: %s", type(error).__name__)
            await bridge.async_stop()
        else:
            self._legacy_bridge = bridge

    async def async_stop(self) -> None:
        bridge, self._legacy_bridge = self._legacy_bridge, None
        if bridge is not None:
            await bridge.async_stop()
        await super().async_stop()

    @property
    def connection_variant(self) -> str:
        return "local_mqtt31_persistent"

    async def async_execute_authorized(
        self, authorized: AuthorizedNativeCommand
    ) -> LocalMqttCommandResult:
        async with self._command_lock:
            if self._state is not ConnectionState.CONNECTED or self._session is None:
                return LocalMqttCommandResult(
                    LocalMqttCommandStatus.REJECTED,
                    "transport_not_connected",
                )
            if self._local_adapter is None:
                self._local_adapter = ZendureLocalMqttCommandAdapter(
                    self._bootstrap,
                    self._session,
                    self._verification,
                    clock=self._clock,
                )
            result = await asyncio.to_thread(self._local_adapter.execute, authorized)
            for command_id in result.verification_ids:
                self._schedule_command_timeout(command_id)
            return result

    def _handle_message(
        self,
        topic: str,
        payload: bytes,
        retained: bool = False,
    ) -> None:
        super()._handle_message(topic, payload, retained)
        if self._legacy_bridge is not None:
            self._legacy_bridge.forward_local(topic, payload)
        if not self._messages:
            return
        message = self._messages[-1]
        local_message = replace(message, transport="local_mqtt")
        self._messages[-1] = local_message
        if (
            local_message.device_candidate_id is not None
            and isinstance(local_message.parsed_payload, dict)
            and self._local_adapter is not None
        ):
            properties = local_message.parsed_payload.get("properties")
            if isinstance(properties, dict):
                self._local_adapter.observe_properties(
                    device_id=local_message.device_candidate_id,
                    properties=properties,
                    observed_at=local_message.received_at,
                    retained=local_message.retained,
                )


def _same_mqtt_endpoint(left: str, right: str) -> bool:
    """Compare MQTT endpoints without resolving or exposing their hostnames."""

    def normalized(value: str) -> tuple[str, int] | None:
        raw = str(value or "").strip()
        if not raw:
            return None
        parsed = urlparse(raw if "://" in raw else f"mqtt://{raw}")
        host = (parsed.hostname or "").rstrip(".").casefold()
        if not host:
            return None
        try:
            port = parsed.port or (8883 if parsed.scheme == "mqtts" else 1883)
        except ValueError:
            return None
        return host, port

    first, second = normalized(left), normalized(right)
    return first is not None and first == second
