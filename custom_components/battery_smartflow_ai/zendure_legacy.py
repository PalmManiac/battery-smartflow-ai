"""ZendureLegacy provisioning, broker identity and Cloud bridge support."""

from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from typing import Any, Callable, Mapping

from .zendure_cloud import CloudMqttCredentials, ZendureCloudBootstrap
from .zendure_cloud_mqtt import PahoReadOnlyMqttSession

LEGACY_BLE_COMMAND_CHARACTERISTIC = "0000c304-0000-1000-8000-00805f9b34fb"


def legacy_ble_commands(
    mqtt_server: str,
    wifi_ssid: str,
    wifi_password: str,
) -> tuple[dict[str, object], ...]:
    """Build the two provisioning messages expected by Legacy firmware."""

    return (
        {
            "iotUrl": mqtt_server,
            "messageId": 1002,
            "method": "token",
            "password": wifi_password,
            "ssid": wifi_ssid,
            "timeZone": "GMT+01:00",
            "token": "abcdefgh",
        },
        {"messageId": 1003, "method": "station"},
    )


def legacy_device_password(device_id: str) -> str:
    """Return the credential required by the Zendure Legacy MQTT protocol."""

    if not str(device_id).strip():
        raise ValueError("legacy_device_id_missing")
    return hashlib.md5(str(device_id).encode()).hexdigest().upper()[8:24]  # noqa: S324


async def async_ensure_legacy_mqtt_users(hass: Any, device_ids: tuple[str, ...]) -> None:
    """Create the local-only HA users consumed by the Mosquitto add-on."""

    from homeassistant.auth.const import GROUP_ID_USER
    from homeassistant.auth.providers import homeassistant as auth_ha

    provider: auth_ha.HassAuthProvider = auth_ha.async_get_provider(hass)
    for device_id in device_ids:
        username = device_id.lower()
        password = legacy_device_password(device_id)
        credentials = await provider.async_get_or_create_credentials(
            {"username": username}
        )
        user = await hass.auth.async_get_user_by_credentials(credentials)
        if user is None:
            user = await hass.auth.async_create_user(
                device_id,
                group_ids=[GROUP_ID_USER],
                local_only=True,
            )
            await provider.async_add_auth(username, password)
            await hass.auth.async_link_user(user, credentials)
        else:
            await provider.async_change_password(username, password)


def _legacy_routes(bootstrap: ZendureCloudBootstrap) -> tuple[tuple[str, str], ...]:
    from .core.models import ZendureTransport
    from .zendure_device_matrix import preferred_local_transport

    routes = []
    for item in bootstrap.devices:
        identity = item.candidate.identity
        if (
            preferred_local_transport(identity) is ZendureTransport.LOCAL_MQTT
            and identity.device_id
            and identity.product_id
        ):
            routes.append((identity.device_id, identity.product_id))
    return tuple(routes)


class _LegacyDeviceCloudSession(PahoReadOnlyMqttSession):
    """Cloud session whose MQTT client identity must equal the device ID."""

    def __init__(self, credentials: CloudMqttCredentials) -> None:
        try:
            import paho.mqtt.client as mqtt
        except ImportError as error:
            raise RuntimeError("mqtt_dependency_missing") from error

        # Build the hardened base once, then replace only the Paho client. The
        # normal BSFAI session hashes client IDs deliberately; Zendure's legacy
        # bridge protocol requires the original device ID here.
        super().__init__(credentials)
        old_client = self._client
        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=credentials.client_id,
            clean_session=False,
            protocol=mqtt.MQTTv31,
        )
        self._client.username_pw_set(credentials.username, credentials.password)
        if self._tls:
            import ssl

            self._client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
        del old_client

    def relay_local_message(self, topic: str, payload: str) -> bool:
        """Relay one validated local device message to Zendure Cloud."""

        if not topic or "#" in topic or "+" in topic:
            return False
        result = self._client.publish(topic, payload, qos=0, retain=False)
        return getattr(result, "rc", result[0] if isinstance(result, tuple) else None) == 0


@dataclass(slots=True)
class _BridgeConnection:
    device_id: str
    product_id: str
    session: PahoReadOnlyMqttSession
    connected: bool = False


class ZendureLegacyCloudBridge:
    """Relay Legacy traffic between the local broker and Zendure Cloud."""

    def __init__(
        self,
        bootstrap: ZendureCloudBootstrap,
        publish_local: Callable[[str, bytes | str], bool],
        *,
        session_factory: Callable[[CloudMqttCredentials], PahoReadOnlyMqttSession]
        | None = None,
    ) -> None:
        self._bootstrap = bootstrap
        self._publish_local = publish_local
        self._session_factory = session_factory or _LegacyDeviceCloudSession
        self._connections: dict[str, _BridgeConnection] = {}
        self._routes = dict(_legacy_routes(bootstrap))
        self._loop: asyncio.AbstractEventLoop | None = None
        self._tasks: set[asyncio.Task[None]] = set()
        self._cloud_to_local: Counter[tuple[str, bytes]] = Counter()

    @property
    def connected_devices(self) -> tuple[str, ...]:
        return tuple(sorted(
            item.device_id for item in self._connections.values() if item.connected
        ))

    @property
    def status(self) -> str:
        if self.connected_devices:
            return "connected"
        if self._connections or self._tasks:
            return "cloud_connecting"
        return "waiting_for_local_device"

    async def async_start(self, *, timeout: float = 15.0) -> None:
        """Arm the bridge; device Cloud sessions start after local traffic."""

        del timeout
        self._loop = asyncio.get_running_loop()

    async def _async_connect_device(self, device_id: str, product_id: str) -> None:
        credentials = CloudMqttCredentials(
            client_id=device_id,
            url=self._bootstrap.mqtt.url,
            username=device_id,
            password=legacy_device_password(device_id),
        )
        session = self._session_factory(credentials)
        connection = _BridgeConnection(device_id, product_id, session)
        self._connections[device_id] = connection

        def on_connect(success: bool, _reason: str | None) -> None:
            connection.connected = success
            if success:
                connection.session.subscribe(
                    (f"iot/{product_id}/{device_id}/#",)
                )

        def on_disconnect(_reason: str | None) -> None:
            connection.connected = False

        def on_message(topic: str, payload: bytes, _retained: bool) -> None:
            if topic.startswith("iot/"):
                marker = (topic, payload)
                self._cloud_to_local[marker] += 1
                if not self._publish_local(topic, payload):
                    self._cloud_to_local[marker] -= 1
                    if self._cloud_to_local[marker] <= 0:
                        del self._cloud_to_local[marker]

        session.set_callbacks(on_connect, on_disconnect, on_message)
        await asyncio.to_thread(session.connect)

    async def async_stop(self) -> None:
        connections = tuple(self._connections.values())
        self._connections.clear()
        tasks = tuple(self._tasks)
        self._tasks.clear()
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await asyncio.gather(
            *(asyncio.to_thread(item.session.disconnect) for item in connections),
            return_exceptions=True,
        )

    def forward_local(self, topic: str, payload: bytes) -> bool:
        """Forward one known local device message, marking it against loops."""

        parts = tuple(part for part in topic.split("/") if part)
        if len(parts) < 3:
            return False
        marker = (topic, payload)
        if self._cloud_to_local[marker] > 0:
            self._cloud_to_local[marker] -= 1
            if self._cloud_to_local[marker] <= 0:
                del self._cloud_to_local[marker]
            return False
        connection = next(
            (item for item in self._connections.values() if item.device_id in parts),
            None,
        )
        if connection is None:
            device_id = next((item for item in self._routes if item in parts), None)
            if device_id is not None and self._loop is not None:
                task = self._loop.create_task(
                    self._async_connect_device(device_id, self._routes[device_id])
                )
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)
            return False
        if not connection.connected:
            return False
        try:
            parsed = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return False
        if not isinstance(parsed, Mapping) or parsed.get("isHA") is True:
            return False
        bridged = dict(parsed)
        bridged["isHA"] = True
        relay = getattr(connection.session, "relay_local_message", None)
        return bool(relay and relay(
            topic, json.dumps(bridged, separators=(",", ":"))
        ))


async def async_provision_legacy_device(
    hass: Any,
    *,
    serial_number: str,
    display_name: str,
    mqtt_server: str,
    wifi_ssid: str,
    wifi_password: str,
) -> None:
    """Point one discoverable ZendureLegacy device at the local broker."""

    from bleak import BleakClient
    from bleak_retry_connector import establish_connection
    from homeassistant.components import bluetooth

    ble_device = None
    serial = serial_number.strip()
    for info in bluetooth.async_discovered_service_info(hass, True):
        matched = False
        for raw in getattr(info, "manufacturer_data", {}).values():
            try:
                decoded = bytes(raw).decode("utf-8")
                # Zendure advertisements terminate this manufacturer field
                # with one non-serial byte; mirror Z-HA's matching rule.
                suffix = decoded[:-1]
            except (UnicodeDecodeError, TypeError, ValueError):
                continue
            if suffix and serial.endswith(suffix):
                matched = True
                break
        if matched:
            ble_device = bluetooth.async_ble_device_from_address(
                hass, str(info.address), True
            )
            break
    if ble_device is None:
        raise RuntimeError("legacy_ble_device_not_found")

    client = await establish_connection(BleakClient, ble_device, display_name)
    try:
        for command in legacy_ble_commands(mqtt_server, wifi_ssid, wifi_password):
            await client.write_gatt_char(
                LEGACY_BLE_COMMAND_CHARACTERISTIC,
                json.dumps(command, separators=(",", ":")).encode(),
                response=False,
            )
    finally:
        if client.is_connected:
            await client.disconnect()
