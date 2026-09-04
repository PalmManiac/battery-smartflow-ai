"""Fail-closed Cloud MQTT command mapping and verification contracts."""

from __future__ import annotations

import asyncio
from base64 import b64encode
from datetime import datetime, timedelta, timezone
import unittest

from custom_components.battery_smartflow_ai.core.models import DeviceCommand, ZendureTransport
from custom_components.battery_smartflow_ai.native_command_verification import (
    CommandVerificationStatus,
    NativeCommandVerificationManager,
)
from custom_components.battery_smartflow_ai.native_device_command_gate import AuthorizedNativeCommand
from custom_components.battery_smartflow_ai.zendure_cloud import ZendureCloudClient
from custom_components.battery_smartflow_ai.zendure_cloud_mqtt_commands import (
    CloudCommandStatus,
    ZendureCloudCommandAdapter,
    map_cloud_command,
)


class Response:
    def __init__(self, data): self.data = data
    async def json(self): return self.data


async def bootstrap(model="SolarFlow 2400 AC"):
    token = b64encode(b"https://api.example.com.app-key").decode()
    async def post(*_args, **_kwargs):
        return Response({"code": 200, "success": True, "data": {
            "deviceList": [{"deviceKey": "main-1", "productKey": "product-a", "productModel": model, "snNumber": "serial-1", "online": True}],
            "mqtt": {"clientId": "client-secret", "url": "broker:1883", "username": "user-secret", "password": "pass-secret"},
        }})
    return await ZendureCloudClient(post).async_discover(token)


def envelope(command, *, device_id="cloud_mqtt:main-1", transport=ZendureTransport.CLOUD_MQTT):
    return AuthorizedNativeCommand("correlation-1", device_id, transport, command)


class Publisher:
    def __init__(self, result=True):
        self.result = result
        self.calls = []
    def write_property(self, product_id, device_id, write):
        self.calls.append((product_id, device_id, write))
        return self.result


class CloudCommandMappingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = asyncio.run(bootstrap())

    def test_maps_mode_limits_and_soc_in_explicit_order(self):
        command = DeviceCommand(
            "input", input_limit_w=123, output_limit_w=0,
            min_soc_pct=10.5, max_soc_pct=93,
            should_write_mode=True, should_write_input=True,
            should_write_output=True, should_write_min_soc=True,
            should_write_max_soc=True,
        )
        product, device, writes = map_cloud_command(
            envelope(command), self.data, first_message_id=4, timestamp=100
        )
        self.assertEqual((product, device), ("product-a", "main-1"))
        self.assertEqual(
            [(item.property_name, item.value, item.message_id) for item in writes],
            [("acMode", 1, 4), ("inputLimit", 123, 5), ("outputLimit", 0, 6), ("minSoc", 105, 7), ("socSet", 930, 8)],
        )

    def test_output_mode_and_valid_zero_are_preserved(self):
        command = DeviceCommand(
            "output", output_limit_w=0, should_write_mode=True,
            should_write_input=False, should_write_output=True,
        )
        *_, writes = map_cloud_command(envelope(command), self.data, first_message_id=1, timestamp=1)
        self.assertEqual([(item.property_name, item.value) for item in writes], [("acMode", 2), ("outputLimit", 0)])

    def test_wrong_transport_device_pack_or_model_never_maps(self):
        command = DeviceCommand("output", should_write_mode=False, should_write_input=False, should_write_output=True)
        cases = (
            envelope(command, transport=ZendureTransport.ZENSDK),
            envelope(command, device_id="cloud_mqtt:pack-1"),
        )
        for item in cases:
            with self.subTest(item=item), self.assertRaises(ValueError):
                map_cloud_command(item, self.data, first_message_id=1, timestamp=1)
        unknown = asyncio.run(bootstrap("Unknown Future"))
        with self.assertRaisesRegex(ValueError, "model_not_approved"):
            map_cloud_command(envelope(command), unknown, first_message_id=1, timestamp=1)

    def test_invalid_scaling_is_rejected(self):
        fractional_power = DeviceCommand("output", output_limit_w=1.5, should_write_mode=False, should_write_input=False, should_write_output=True)
        with self.assertRaisesRegex(ValueError, "invalid_power_value"):
            map_cloud_command(envelope(fractional_power), self.data, first_message_id=1, timestamp=1)

    def test_execute_records_publish_then_fresh_readback(self):
        publisher = Publisher()
        verification = NativeCommandVerificationManager()
        now = datetime(2026, 9, 4, 16, 0, tzinfo=timezone.utc)
        adapter = ZendureCloudCommandAdapter(self.data, publisher, verification, clock=lambda: now)
        command = DeviceCommand("output", output_limit_w=77, should_write_mode=False, should_write_input=False, should_write_output=True)
        result = adapter.execute(envelope(command))
        self.assertEqual(result.status, CloudCommandStatus.SENT)
        self.assertEqual(result.writes_sent, 1)
        tracked = verification.get(result.verification_ids[0])
        self.assertEqual(tracked.status, CommandVerificationStatus.TRANSPORT_OK)
        self.assertEqual(adapter.observe_properties(device_id="cloud_mqtt:main-1", properties={"outputLimit": 77}, observed_at=now + timedelta(seconds=1)), 1)
        self.assertEqual(tracked.status, CommandVerificationStatus.READBACK_CONFIRMED)

    def test_newer_same_target_supersedes_old_and_publish_failure_stops(self):
        publisher = Publisher(result=True)
        verification = NativeCommandVerificationManager()
        adapter = ZendureCloudCommandAdapter(self.data, publisher, verification)
        def command(value):
            return envelope(DeviceCommand("output", output_limit_w=value, should_write_mode=False, should_write_input=False, should_write_output=True))
        first = adapter.execute(command(10))
        second = adapter.execute(command(20))
        self.assertEqual(verification.get(first.verification_ids[0]).status, CommandVerificationStatus.SUPERSEDED)
        self.assertEqual(verification.get(second.verification_ids[0]).status, CommandVerificationStatus.TRANSPORT_OK)
        failed_adapter = ZendureCloudCommandAdapter(self.data, Publisher(False), NativeCommandVerificationManager())
        failed = failed_adapter.execute(command(30))
        self.assertEqual(failed.status, CloudCommandStatus.TRANSPORT_ERROR)
        self.assertEqual(failed.writes_sent, 0)

    def test_diagnostics_contain_no_route_or_credentials(self):
        verification = NativeCommandVerificationManager()
        adapter = ZendureCloudCommandAdapter(self.data, Publisher(), verification)
        result = adapter.execute(envelope(DeviceCommand("output", output_limit_w=1, should_write_mode=False, should_write_input=False, should_write_output=True)))
        text = repr(verification.diagnostics()) + repr(result)
        for secret in ("main-1", "serial-1", "product-a", "client-secret", "user-secret", "pass-secret"):
            self.assertNotIn(secret, text)


if __name__ == "__main__":
    unittest.main()
