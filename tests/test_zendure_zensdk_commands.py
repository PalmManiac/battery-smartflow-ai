"""Typed ZenSDK command adapter tests."""

from __future__ import annotations

from base64 import b64encode
from datetime import datetime, timedelta, timezone
import unittest

from support import bootstrap as bootstrap_test_environment


bootstrap_test_environment()

from custom_components.battery_smartflow_ai.core.models import (  # noqa: E402
    DeviceCommand,
    ZendureTransport,
)
from custom_components.battery_smartflow_ai.native_command_verification import (  # noqa: E402
    CommandVerificationStatus,
    NativeCommandVerificationManager,
)
from custom_components.battery_smartflow_ai.native_device_command_gate import (  # noqa: E402
    AuthorizedNativeCommand,
)
from custom_components.battery_smartflow_ai.zendure_cloud import (  # noqa: E402
    ZendureCloudClient,
)
from custom_components.battery_smartflow_ai.zendure_zensdk_commands import (  # noqa: E402
    ZenSdkCommandStatus,
    ZendureZenSdkCommandAdapter,
    map_zensdk_command,
)


NOW = datetime(2026, 9, 5, 10, 0, tzinfo=timezone.utc)
DEVICE = "cloud_mqtt:device-real-1"


class Response:
    def __init__(self, data, status=200):
        self.data = data
        self.status = status

    async def json(self):
        return self.data


async def make_bootstrap():
    token = b64encode(b"https://api.example.com.app-key").decode()

    async def post(*_args, **_kwargs):
        return Response({
            "code": 200,
            "success": True,
            "data": {
                "deviceList": [{
                    "deviceKey": "device-real-1",
                    "snNumber": "serial-real-1",
                    "productKey": "BC8B7F",
                    "productModel": "SolarFlow 2400 AC",
                    "online": True,
                    "ip": "192.168.1.44",
                }],
                "mqtt": {
                    "clientId": "client-secret",
                    "url": "mqtt://broker.example:1883",
                    "username": "user-secret",
                    "password": "password-secret",
                },
            },
        })

    return await ZendureCloudClient(post).async_discover(token)


def authorized(command: DeviceCommand, *, transport=ZendureTransport.ZENSDK):
    return AuthorizedNativeCommand("gate-correlation", DEVICE, transport, command)


def output_command(value=301):
    return DeviceCommand(
        "output",
        output_limit_w=value,
        should_write_mode=False,
        should_write_input=False,
        should_write_output=True,
        metadata={"native_offgrid_power_w": 0},
    )


class ZenSdkCommandAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_output_is_one_complete_directional_post(self):
        data = await make_bootstrap()
        calls = []
        manager = NativeCommandVerificationManager()

        async def post(url, **kwargs):
            calls.append((url, kwargs))
            return Response({"success": True}, 200)

        adapter = ZendureZenSdkCommandAdapter(
            data, post, manager, clock=lambda: NOW
        )
        result = await adapter.execute(authorized(output_command()))

        self.assertEqual(result.status, ZenSdkCommandStatus.SENT)
        self.assertEqual(result.writes_sent, 4)
        self.assertEqual(result.requests_sent, 1)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], "http://192.168.1.44/properties/write")
        self.assertEqual(calls[0][1]["json"], {
            "sn": "serial-real-1",
            "properties": {
                "smartMode": 1,
                "acMode": 2,
                "outputLimit": 301,
                "inputLimit": 0,
            },
            "id": 1,
        })
        tracked = manager.active_for(DEVICE, "outputLimit")
        self.assertIsNotNone(tracked)
        self.assertEqual(tracked.status, CommandVerificationStatus.TRANSPORT_OK)

    async def test_input_is_one_complete_directional_post(self):
        data = await make_bootstrap()
        calls = []

        async def post(*args, **kwargs):
            calls.append((args, kwargs))
            return Response({})

        command = DeviceCommand(
            "input",
            input_limit_w=200,
            should_write_mode=False,
            should_write_input=True,
            should_write_output=False,
            metadata={"native_offgrid_power_w": 0},
        )
        adapter = ZendureZenSdkCommandAdapter(
            data, post, NativeCommandVerificationManager()
        )
        result = await adapter.execute(authorized(command))

        self.assertEqual(result.status, ZenSdkCommandStatus.SENT)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1]["json"]["properties"], {
            "smartMode": 1,
            "acMode": 1,
            "outputLimit": 0,
            "inputLimit": 200,
        })

    async def test_zero_command_respects_offgrid_load_and_unknown_state(self):
        data = await make_bootstrap()
        for offgrid, expected in ((0, 0), (12, 1), (None, 1)):
            with self.subTest(offgrid=offgrid):
                command = output_command(0)
                command.metadata["native_offgrid_power_w"] = offgrid
                mapped = map_zensdk_command(
                    authorized(command), data, first_request_id=7
                )
                self.assertEqual(mapped.properties, {
                    "smartMode": expected,
                    "acMode": 2,
                    "outputLimit": 0,
                    "inputLimit": 0,
                })

    async def test_soc_property_remains_rejected_without_network(self):
        data = await make_bootstrap()
        calls = []

        async def post(*args, **kwargs):
            calls.append((args, kwargs))
            return Response({})

        command = DeviceCommand(
            "output",
            min_soc_pct=10,
            should_write_mode=False,
            should_write_input=False,
            should_write_output=False,
            should_write_min_soc=True,
        )
        result = await ZendureZenSdkCommandAdapter(
            data, post, NativeCommandVerificationManager()
        ).execute(authorized(command))
        self.assertEqual(result.status, ZenSdkCommandStatus.REJECTED)
        self.assertEqual(result.reason, "property_not_approved:minSoc")
        self.assertEqual(calls, [])

    async def test_wrong_transport_and_non_integral_power_are_rejected(self):
        data = await make_bootstrap()
        with self.assertRaisesRegex(ValueError, "wrong_transport"):
            map_zensdk_command(
                authorized(output_command(), transport=ZendureTransport.CLOUD_MQTT),
                data,
                first_request_id=1,
            )
        with self.assertRaisesRegex(ValueError, "invalid_power_value"):
            map_zensdk_command(
                authorized(output_command(300.5)), data, first_request_id=1
            )

    async def test_http_failure_is_transport_error_and_never_retried(self):
        data = await make_bootstrap()
        calls = []
        manager = NativeCommandVerificationManager()

        async def post(url, **_kwargs):
            calls.append(url)
            return Response({"success": False}, 503)

        result = await ZendureZenSdkCommandAdapter(
            data, post, manager, clock=lambda: NOW
        ).execute(authorized(output_command()))

        self.assertEqual(result.status, ZenSdkCommandStatus.TRANSPORT_ERROR)
        self.assertEqual(result.http_status, 503)
        self.assertEqual(result.requests_sent, 1)
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(result.verification_ids), 4)
        for command_id in result.verification_ids:
            tracked = manager.get(command_id)
            self.assertEqual(
                tracked.status, CommandVerificationStatus.TRANSPORT_ERROR
            )

    async def test_only_fresh_matching_report_confirms_readback(self):
        data = await make_bootstrap()
        manager = NativeCommandVerificationManager()

        async def post(*_args, **_kwargs):
            return Response({"success": True}, 200)

        adapter = ZendureZenSdkCommandAdapter(
            data, post, manager, clock=lambda: NOW
        )
        await adapter.execute(authorized(output_command()))

        self.assertEqual(adapter.observe_properties(
            device_id=DEVICE,
            properties={"outputLimit": 301},
            observed_at=NOW,
        ), 0)
        self.assertEqual(adapter.observe_properties(
            device_id="cloud_mqtt:different-device",
            properties={"outputLimit": 301},
            observed_at=NOW + timedelta(seconds=1),
        ), 0)
        self.assertEqual(adapter.observe_properties(
            device_id=DEVICE,
            properties={"outputLimit": 301},
            observed_at=NOW + timedelta(seconds=1),
        ), 1)
        tracked = manager.active_for(DEVICE, "outputLimit")
        self.assertEqual(
            tracked.status, CommandVerificationStatus.READBACK_CONFIRMED
        )


if __name__ == "__main__":
    unittest.main()
