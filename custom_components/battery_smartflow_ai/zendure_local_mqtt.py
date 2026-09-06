"""Dedicated Local MQTT transport for verified ZendureLegacy devices."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field, replace

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
                client_id=f"local:{credentials.username or 'anonymous'}",
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
        self._local_adapter: ZendureLocalMqttCommandAdapter | None = None

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

    def _handle_message(self, topic: str, payload: bytes) -> None:
        super()._handle_message(topic, payload)
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
                )
