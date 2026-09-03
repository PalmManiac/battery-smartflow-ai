"""Strict read-only Zendure Cloud MQTT transport tests."""

from __future__ import annotations

import asyncio
from base64 import b64encode
from datetime import datetime, timezone
import inspect
import json
from pathlib import Path
import socket
import unittest

from custom_components.battery_smartflow_ai.zendure_cloud import ZendureCloudClient
from custom_components.battery_smartflow_ai.zendure_cloud_mqtt import (
    ConnectionState,
    ZendureCloudMqttTransport,
    _bsfai_client_id,
    _parse_broker_url,
    _reason_code_success,
    _safe_peer_scope,
    _safe_socket_family,
)


class Response:
    def __init__(self, data): self.data = data
    async def json(self): return self.data


async def bootstrap(devices):
    token = b64encode(b"https://api.example.com.app-key").decode()
    async def post(*_args, **_kwargs):
        return Response({"code": 200, "success": True, "data": {
            "deviceList": devices,
            "mqtt": {"clientId": "secret-client", "url": "mqtts://broker.example:8883", "username": "secret-user", "password": "secret-pass"},
        }})
    return await ZendureCloudClient(post).async_discover(token)


class FakeSession:
    def __init__(self, _credentials, *, connect_ok=True):
        self.connect_ok = connect_ok
        self.subscriptions = ()
        self.disconnected = False

    def set_callbacks(self, on_connect, on_disconnect, on_message):
        self.on_connect, self.on_disconnect, self.on_message = on_connect, on_disconnect, on_message

    def connect(self): self.on_connect(self.connect_ok, None if self.connect_ok else "not authorized")
    def subscribe(self, topics): self.subscriptions = topics
    def disconnect(self): self.disconnected = True
    def emit(self, topic, payload): self.on_message(topic, payload)
    def drop(self): self.on_disconnect("network lost")


class HangingSession(FakeSession):
    def connect(self):
        return None

    def disconnect(self):
        self.disconnected = True
        raise RuntimeError("not connected")


class CloudMqttTransportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.sessions = []
        self.now = datetime(2026, 9, 2, 10, 0, tzinfo=timezone.utc)
        self.data = await bootstrap([
            {"deviceKey": "main-1", "productKey": "product-a", "productModel": "SolarFlow2400AC", "deviceName": "One", "online": True, "packNum": 2},
            {"deviceKey": "main-2", "productKey": "product-b", "productModel": "Unknown Future", "deviceName": "Two"},
        ])

    def factory(self, credentials):
        session = FakeSession(credentials)
        self.sessions.append(session)
        return session

    async def test_connects_and_subscribes_all_devices(self):
        transport = ZendureCloudMqttTransport(self.data, session_factory=self.factory)
        await transport.async_start()
        self.assertEqual(transport.state, ConnectionState.CONNECTED)
        self.assertEqual(
            self.sessions[0].subscriptions,
            (
                "/product-a/main-1/#",
                "/product-b/main-2/#",
                "iot/product-a/main-1/#",
                "iot/product-b/main-2/#",
            ),
        )
        await transport.async_stop()
        self.assertTrue(self.sessions[0].disconnected)

    async def test_initial_incremental_unknown_and_invalid_payloads_are_retained(self):
        transport = ZendureCloudMqttTransport(self.data, session_factory=self.factory, clock=lambda: self.now)
        await transport.async_start()
        session = self.sessions[0]
        session.emit("/product-a/main-1/properties/report", json.dumps({"properties": {"socLevel": 55, "solarInputPower": 800}}).encode())
        session.emit("/product-a/main-1/new/future/topic", b'{broken')
        session.emit("/product-b/main-2/state", b"\xff\x00")
        await asyncio.sleep(0)
        messages = transport.messages
        self.assertEqual([item.payload_format for item in messages], ["json", "text", "binary"])
        self.assertTrue(messages[0].known_topic)
        self.assertFalse(messages[1].known_topic)
        self.assertEqual(messages[0].device_candidate_id, "cloud_mqtt:main-1")
        state = transport.device_states["cloud_mqtt:main-1"]
        self.assertEqual(state.last_message_at, self.now)
        self.assertEqual(set(state.property_updated_at), {"socLevel", "solarInputPower"})

    async def test_routes_pack_and_payload_device_identity(self):
        transport = ZendureCloudMqttTransport(self.data, session_factory=self.factory)
        await transport.async_start()
        self.sessions[0].emit("/account/events", json.dumps({"deviceKey": "main-1", "packId": "pack-77", "properties": {"socLevel": 44}}).encode())
        await asyncio.sleep(0)
        message = transport.messages[0]
        self.assertEqual(message.device_candidate_id, "cloud_mqtt:main-1")
        self.assertEqual(message.pack_id, "pack-77")

    async def test_disconnect_reconnects_without_commands(self):
        transport = ZendureCloudMqttTransport(self.data, session_factory=self.factory, reconnect_delays=(0.0,))
        await transport.async_start()
        self.sessions[0].drop()
        for _attempt in range(20):
            if len(self.sessions) >= 2:
                break
            await asyncio.sleep(0.01)
        self.assertGreaterEqual(len(self.sessions), 2)
        self.assertEqual(transport.state, ConnectionState.CONNECTED)
        self.assertFalse(hasattr(transport, "publish"))
        self.assertFalse(hasattr(transport, "command"))
        public = {name for name, _ in inspect.getmembers(type(transport), inspect.isfunction) if not name.startswith("_")}
        self.assertEqual(public, {"async_start", "async_stop"})

    async def test_credentials_do_not_appear_in_logs_or_representations(self):
        transport = ZendureCloudMqttTransport(self.data, session_factory=self.factory)
        with self.assertLogs("custom_components.battery_smartflow_ai.zendure_cloud_mqtt", level="INFO") as logs:
            await transport.async_start()
        text = " ".join(logs.output) + repr(transport) + repr(self.data)
        for secret in ("secret-client", "secret-user", "secret-pass", "broker.example"):
            self.assertNotIn(secret, text)

    async def test_disconnect_reason_is_sanitized(self):
        transport = ZendureCloudMqttTransport(self.data, session_factory=self.factory, reconnect_delays=(10.0,))
        await transport.async_start()
        with self.assertLogs("custom_components.battery_smartflow_ai.zendure_cloud_mqtt", level="WARNING") as logs:
            self.sessions[0].on_disconnect("username=secret-user password=secret-pass mqtts://broker.example:8883")
            await asyncio.sleep(0)
        text = " ".join(logs.output)
        for secret in ("secret-user", "secret-pass", "broker.example"):
            self.assertNotIn(secret, text)
        await transport.async_stop()

    async def test_no_routable_device_is_rejected(self):
        data = await bootstrap([{"snNumber": "serial-only", "productModel": "SolarFlow2400AC"}])
        transport = ZendureCloudMqttTransport(data, session_factory=self.factory)
        with self.assertRaisesRegex(Exception, "no_routable_devices"):
            await transport.async_start()

    async def test_cleanup_failure_does_not_mask_connection_timeout(self):
        session = HangingSession(None)
        transport = ZendureCloudMqttTransport(
            self.data,
            session_factory=lambda _credentials: session,
        )
        with self.assertRaisesRegex(Exception, "connection_timeout"):
            await transport.async_start(timeout=0.01)
        self.assertEqual(transport.state, ConnectionState.STOPPED)
        self.assertTrue(session.disconnected)
        self.assertEqual(transport.connection_variant, "mqtt31_persistent")

    async def test_connection_phase_is_retained_after_timeout_cleanup(self):
        class PhasedHangingSession(HangingSession):
            connection_phase = "tcp_connected_waiting_for_mqtt_connack"

        transport = ZendureCloudMqttTransport(
            self.data,
            session_factory=lambda _credentials: PhasedHangingSession(None),
        )
        with self.assertRaisesRegex(Exception, "connection_timeout"):
            await transport.async_start(timeout=0.01)
        self.assertEqual(
            transport.connection_phase,
            "tcp_connected_waiting_for_mqtt_connack",
        )

    def test_schema_free_port_1883_is_plain_mqtt(self):
        self.assertEqual(
            _parse_broker_url("broker.example:1883"),
            ("broker.example", 1883, False),
        )

    def test_tls_requires_an_explicit_secure_scheme(self):
        self.assertEqual(
            _parse_broker_url("mqtts://broker.example:8883"),
            ("broker.example", 8883, True),
        )
        self.assertEqual(
            _parse_broker_url("mqtt://broker.example:1883"),
            ("broker.example", 1883, False),
        )

    def test_paho_uses_zendure_ha_mqtt_31_persistent_session(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "custom_components"
            / "battery_smartflow_ai"
            / "zendure_cloud_mqtt.py"
        ).read_text(encoding="utf-8")
        self.assertIn("protocol=mqtt.MQTTv31", source)
        self.assertIn("clean_session=False", source)
        self.assertIn("connect_async", source)

    def test_socket_metadata_is_classified_without_retaining_addresses(self):
        class FakeSocket:
            family = socket.AF_INET

            def getpeername(self):
                return ("192.168.10.20", 1883)

        mqtt_socket = FakeSocket()
        self.assertEqual(_safe_socket_family(mqtt_socket), "ipv4")
        self.assertEqual(_safe_peer_scope(mqtt_socket), "private")
        self.assertNotIn("192.168.10.20", repr(_safe_peer_scope(mqtt_socket)))

    def test_public_and_loopback_peers_are_distinguished(self):
        class FakeSocket:
            family = socket.AF_INET6

            def __init__(self, address):
                self.address = address

            def getpeername(self):
                return (self.address, 1883, 0, 0)

        self.assertEqual(_safe_peer_scope(FakeSocket("2606:4700:4700::1111")), "public")
        self.assertEqual(_safe_peer_scope(FakeSocket("::1")), "loopback")

    def test_paho_reason_code_objects_do_not_require_integer_conversion(self):
        class ReasonCode:
            def __init__(self, *, is_failure, value):
                self.is_failure = is_failure
                self.value = value

            def __int__(self):
                raise TypeError("ReasonCode is not directly integer-convertible")

            def __str__(self):
                return "Success" if not self.is_failure else "Not authorized"

        self.assertTrue(_reason_code_success(ReasonCode(is_failure=False, value=0)))
        self.assertFalse(_reason_code_success(ReasonCode(is_failure=True, value=135)))
        self.assertTrue(_reason_code_success(0))
        self.assertFalse(_reason_code_success(5))

    def test_bsfai_uses_a_stable_private_mqtt31_client_identity(self):
        first = _bsfai_client_id("zendure-cloud-client-secret")
        second = _bsfai_client_id("zendure-cloud-client-secret")

        self.assertEqual(first, second)
        self.assertTrue(first.startswith("bsfai-"))
        self.assertLessEqual(len(first), 23)
        self.assertNotIn("zendure-cloud-client-secret", first)
        self.assertNotEqual(first, "zendure-cloud-client-secret")
        self.assertNotEqual(
            first,
            _bsfai_client_id("another-zendure-cloud-client"),
        )


if __name__ == "__main__":
    unittest.main()
