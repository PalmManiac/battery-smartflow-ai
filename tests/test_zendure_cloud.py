"""Read-only Zendure Cloud bootstrap tests."""

from __future__ import annotations

import asyncio
from base64 import b64encode
import unittest

from support import bootstrap

bootstrap()

from custom_components.battery_smartflow_ai.core.models import DeviceInventory  # noqa: E402
from custom_components.battery_smartflow_ai.zendure_cloud import (  # noqa: E402
    ZendureCloudClient,
    ZendureCloudError,
    parse_app_token,
)


def token(value: str = "https://api-eu.example.com.secret-app-key") -> str:
    return b64encode(value.encode()).decode()


class Response:
    def __init__(self, payload):
        self.payload = payload

    async def json(self):
        return self.payload


def payload(devices=None):
    return {
        "code": 200,
        "success": True,
        "data": {
            "deviceList": devices or [{
                "deviceKey": "device-1",
                "productKey": "product-1",
                "productModel": "solarflow2400ac",
                "snNumber": "serial-1",
                "deviceName": "Basement",
                "online": True,
                "packData": [{"sn": "pack-1"}],
                "newFirmwareField": 42,
            }],
            "mqtt": {
                "clientId": "client-secret",
                "url": "broker.example.com:1883",
                "username": "mqtt-user",
                "password": "mqtt-password",
            },
        },
    }


class ZendureCloudTests(unittest.IsolatedAsyncioTestCase):
    def test_token_is_validated_and_never_represented(self):
        parsed = parse_app_token(token())
        self.assertEqual(parsed.region_host, "api-eu.example.com")
        self.assertNotIn("secret-app-key", repr(parsed))
        for invalid in (
            "",
            "not-base64",
            token("http://api.example.com.key"),
            token("https://localhost"),
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ZendureCloudError):
                parse_app_token(invalid)

    async def test_signed_post_maps_all_devices_to_passive_candidates(self):
        calls = []

        async def post(url, **kwargs):
            calls.append((url, kwargs))
            return Response(payload())

        result = await ZendureCloudClient(
            post, clock=lambda: 1234567890, nonce_factory=lambda: "12345"
        ).async_discover(token())
        self.assertEqual(
            calls[0][0], "https://api-eu.example.com/api/ha/deviceList"
        )
        self.assertEqual(calls[0][1]["json"], {"appKey": "secret-app-key"})
        self.assertEqual(calls[0][1]["headers"]["clientid"], "zenHa")
        self.assertEqual(calls[0][1]["headers"]["timestamp"], "1234567890")
        self.assertEqual(calls[0][1]["headers"]["nonce"], "12345")
        self.assertEqual(len(calls[0][1]["headers"]["sign"]), 40)
        device = result.devices[0]
        self.assertEqual(device.candidate.display_name, "Basement")
        self.assertEqual(device.candidate.pack_count, 1)
        self.assertEqual(device.extra_field_names, ("newFirmwareField",))
        inventory = DeviceInventory()
        result.register_candidates(inventory)
        self.assertEqual(inventory.devices, {})
        self.assertIn("cloud_mqtt:device-1", inventory.candidates)

    async def test_mqtt_credentials_are_opaque(self):
        async def post(*args, **kwargs):
            return Response(payload())

        result = await ZendureCloudClient(post).async_discover(token())
        text = repr(result) + repr(result.mqtt)
        self.assertNotIn("mqtt-password", text)
        self.assertNotIn("mqtt-user", text)
        self.assertNotIn("broker.example.com", text)

    async def test_duplicate_names_are_allowed_but_ids_are_not(self):
        same_name = [
            {"deviceKey": "a", "deviceName": "Battery", "productModel": "A"},
            {"deviceKey": "b", "deviceName": "Battery", "productModel": "B"},
        ]

        async def good(*args, **kwargs):
            return Response(payload(same_name))

        self.assertEqual(
            len((await ZendureCloudClient(good).async_discover(token())).devices),
            2,
        )
        same_name[1]["deviceKey"] = "a"
        with self.assertRaisesRegex(ZendureCloudError, "duplicate_device_id"):
            await ZendureCloudClient(good).async_discover(token())

    async def test_unknown_model_remains_visible_and_unsupported(self):
        async def post(*args, **kwargs):
            return Response(payload([{"deviceKey": "new-device", "deviceName": "Future"}]))

        result = await ZendureCloudClient(post).async_discover(token())
        self.assertFalse(result.devices[0].candidate.supported)
        self.assertEqual(result.devices[0].candidate.display_name, "Future")

    async def test_errors_are_classified_without_response_details(self):
        cases = [
            ({"code": 401, "success": False, "msg": "token secret"}, "invalid_or_expired_token"),
            ({"code": 200, "success": True, "data": {"deviceList": [], "mqtt": {}}}, "no_devices"),
            ({"code": 200, "success": True, "data": {"deviceList": [{}], "mqtt": {}}}, "incomplete_device"),
        ]
        for raw, reason in cases:
            async def post(*args, _raw=raw, **kwargs):
                return Response(_raw)

            with self.subTest(reason=reason), self.assertRaisesRegex(
                ZendureCloudError, reason
            ):
                await ZendureCloudClient(post).async_discover(token())

    async def test_timeout_is_bounded(self):
        async def post(*args, **kwargs):
            await asyncio.sleep(0.05)
            return Response(payload())

        with self.assertRaisesRegex(ZendureCloudError, "timeout"):
            await ZendureCloudClient(post, timeout=0.001).async_discover(token())

    async def test_nested_network_exception_cannot_expose_credentials(self):
        async def post(*args, **kwargs):
            raise RuntimeError("secret-app-key at broker.example.com")

        try:
            await ZendureCloudClient(post).async_discover(token())
        except ZendureCloudError as error:
            self.assertEqual(str(error), "cannot_connect")
            self.assertIsNone(error.__cause__)
            self.assertNotIn("secret-app-key", repr(error))
        else:  # pragma: no cover - assertion guard
            self.fail("Expected a classified cloud error")
