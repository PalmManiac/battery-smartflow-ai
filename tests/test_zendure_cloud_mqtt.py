"""Strict read-only Zendure Cloud MQTT transport tests."""

from __future__ import annotations

import asyncio
from base64 import b64encode
from datetime import datetime, timezone
import inspect
import json
from pathlib import Path
import unittest

from custom_components.battery_smartflow_ai.zendure_cloud import ZendureCloudClient
from custom_components.battery_smartflow_ai.zendure_cloud_mqtt import (
    ConnectionState,
    ZendureCloudMqttTransport,
    _parse_broker_url,
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

    def test_paho_uses_zendure_cloud_mqtt_31_protocol(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "custom_components"
            / "battery_smartflow_ai"
            / "zendure_cloud_mqtt.py"
        ).read_text(encoding="utf-8")
        self.assertIn("protocol=mqtt.MQTTv31", source)


if __name__ == "__main__":
    unittest.main()
