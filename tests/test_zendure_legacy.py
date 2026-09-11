"""Regression tests for the complete ZendureLegacy communication path."""

from __future__ import annotations

import asyncio
from base64 import b64encode
import json
import unittest

from support import bootstrap

bootstrap()

from custom_components.battery_smartflow_ai.zendure_cloud import (  # noqa: E402
    ZendureCloudClient,
)
from custom_components.battery_smartflow_ai.zendure_legacy import (  # noqa: E402
    ZendureLegacyCloudBridge,
    legacy_ble_commands,
    legacy_device_password,
)


class Response:
    def __init__(self, payload):
        self.payload = payload

    async def json(self):
        return self.payload


async def legacy_bootstrap():
    token = b64encode(b"https://api.example.com.app-key").decode()

    async def post(*_args, **_kwargs):
        return Response({
            "code": 200,
            "success": True,
            "data": {
                "deviceList": [{
                    "deviceKey": "legacy-1",
                    "productKey": "legacy-product",
                    "productModel": "Hyper 2000",
                    "deviceName": "Hyper",
                    "snNumber": "legacy-serial",
                    "online": True,
                }],
                "mqtt": {
                    "clientId": "account",
                    "url": "cloud.example:1883",
                    "username": "account-user",
                    "password": "account-password",
                },
            },
        })

    return await ZendureCloudClient(post).async_discover(token)


class FakeCloudSession:
    instances = []

    def __init__(self, credentials):
        self.credentials = credentials
        self.published = []
        self.subscriptions = ()
        self.__class__.instances.append(self)

    def set_callbacks(self, connect, disconnect, message):
        self.on_connect = connect
        self.on_disconnect = disconnect
        self.on_message = message

    def connect(self):
        self.on_connect(True, None)

    def subscribe(self, topics):
        self.subscriptions = topics

    def relay_local_message(self, topic, payload):
        self.published.append((topic, json.loads(payload)))
        return True

    def disconnect(self):
        return None


class ZendureLegacyTests(unittest.IsolatedAsyncioTestCase):
    def test_device_password_matches_zendure_protocol(self):
        self.assertEqual(
            legacy_device_password("legacy-1"),
            "185B2D7594FBE336",
        )

    def test_ble_commands_match_zendure_legacy_provisioning_contract(self):
        self.assertEqual(
            legacy_ble_commands("192.0.2.10", "Home WiFi", "secret"),
            (
                {
                    "iotUrl": "192.0.2.10",
                    "messageId": 1002,
                    "method": "token",
                    "password": "secret",
                    "ssid": "Home WiFi",
                    "timeZone": "GMT+01:00",
                    "token": "abcdefgh",
                },
                {"messageId": 1003, "method": "station"},
            ),
        )

    async def test_bridge_is_lazy_marks_local_and_relays_cloud(self):
        data = await legacy_bootstrap()
        local = []
        bridge = ZendureLegacyCloudBridge(
            data,
            lambda topic, payload: local.append((topic, payload)) or True,
            session_factory=FakeCloudSession,
        )
        await bridge.async_start()
        topic = "iot/legacy-product/legacy-1/properties/report"
        payload = json.dumps({"properties": {"electricLevel": 50}}).encode()

        self.assertFalse(bridge.forward_local(topic, payload))
        await asyncio.sleep(0)
        session = FakeCloudSession.instances[-1]
        self.assertEqual(
            session.subscriptions,
            ("iot/legacy-product/legacy-1/#",),
        )
        self.assertTrue(bridge.forward_local(topic, payload))
        self.assertTrue(session.published[-1][1]["isHA"])

        session.on_message(topic, payload, False)
        self.assertEqual(local[-1], (topic, payload))
        self.assertFalse(bridge.forward_local(topic, payload))
        await bridge.async_stop()

    async def test_bridge_does_not_loop_is_ha_messages(self):
        data = await legacy_bootstrap()
        bridge = ZendureLegacyCloudBridge(
            data,
            lambda *_args: True,
            session_factory=FakeCloudSession,
        )
        await bridge.async_start()
        topic = "iot/legacy-product/legacy-1/properties/report"
        bridge.forward_local(topic, b"{}")
        await asyncio.sleep(0)
        self.assertFalse(bridge.forward_local(topic, b'{"isHA":true}'))
        await bridge.async_stop()


if __name__ == "__main__":
    unittest.main()
