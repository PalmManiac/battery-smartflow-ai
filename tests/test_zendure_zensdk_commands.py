"""Typed ZenSDK command adapter tests."""

from __future__ import annotations

import math
import unittest
from base64 import b64encode
from datetime import datetime, timedelta, timezone

from support import bootstrap as bootstrap_test_environment

bootstrap_test_environment()

from custom_components.battery_smartflow_ai.core.models import (
    DeviceCommand,
    ZendureTransport,
)
from custom_components.battery_smartflow_ai.hardware.zendure.cloud import (
    ZendureCloudClient,
)
from custom_components.battery_smartflow_ai.hardware.zendure.device_matrix import (
    SMART_MODE_ALWAYS_ONE_METADATA_KEY,
    SMART_MODE_STANDBY_CONFIRMED_METADATA_KEY,
)
from custom_components.battery_smartflow_ai.hardware.zendure.zensdk_commands import (
    ZendureZenSdkCommandAdapter,
    ZenSdkCommandStatus,
    map_zensdk_command,
)
from custom_components.battery_smartflow_ai.native_command_verification import (
    CommandVerificationStatus,
    NativeCommandVerificationManager,
)
from custom_components.battery_smartflow_ai.native_device_command_gate import (
    AuthorizedNativeCommand,
)

NOW = datetime(2026, 9, 5, 10, 0, tzinfo=timezone.utc)
DEVICE = "cloud_mqtt:device-real-1"


class Response:
    def __init__(self, data, status=200):
        self.data = data
        self.status = status

    async def json(self):
        return self.data


async def make_bootstrap(model="SolarFlow 2400 AC", product_id="BC8B7F"):
    token = b64encode(b"https://api.example.com.app-key").decode()

    async def post(*_args, **_kwargs):
        return Response({
            "code": 200,
            "success": True,
            "data": {
                "deviceList": [{
                    "deviceKey": "device-real-1",
                    "snNumber": "serial-real-1",
                    "productKey": product_id,
                    "productModel": model,
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
    async def test_adapter_uses_the_selected_devices_configured_address(self):
        data = await make_bootstrap()
        calls = []
        manager = NativeCommandVerificationManager()

        async def post(url, **kwargs):
            calls.append((url, kwargs))
            return Response({"success": True}, 200)

        adapter = ZendureZenSdkCommandAdapter(
            data,
            post,
            manager,
            clock=lambda: NOW,
            address_overrides={DEVICE: "192.168.1.99"},
        )
        result = await adapter.execute(authorized(output_command()))

        self.assertEqual(result.status, ZenSdkCommandStatus.SENT)
        self.assertEqual(
            calls[0][0], "http://192.168.1.99/properties/write"
        )
        self.assertEqual(
            adapter.diagnostics()["address_source"], "configured_ip"
        )
        self.assertNotIn("192.168.1.99", repr(adapter.diagnostics()))

    async def test_offgrid_mode_is_a_single_verified_property_write(self):
        data = await make_bootstrap()
        calls = []
        manager = NativeCommandVerificationManager()

        async def post(url, **kwargs):
            calls.append((url, kwargs))
            return Response({"success": True}, 200)

        command = DeviceCommand(
            "output",
            should_write_mode=False,
            should_write_input=False,
            should_write_output=False,
            should_write_offgrid_mode=True,
            offgrid_mode="eco",
        )
        result = await ZendureZenSdkCommandAdapter(
            data, post, manager, clock=lambda: NOW
        ).execute(authorized(command))

        self.assertEqual(result.status, ZenSdkCommandStatus.SENT)
        self.assertEqual(calls[0][1]["json"]["properties"], {"gridOffMode": 1})
        self.assertIsNotNone(manager.active_for(DEVICE, "gridOffMode"))
    async def test_running_output_adjustment_reasserts_temporary_smart_mode(self):
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
        self.assertEqual(result.writes_sent, 2)
        self.assertEqual(result.requests_sent, 1)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], "http://192.168.1.44/properties/write")
        self.assertEqual(calls[0][1]["json"], {
            "sn": "serial-real-1",
            "properties": {"smartMode": 1, "outputLimit": 301},
            "id": 1,
        })
        mode = manager.active_for(DEVICE, "smartMode")
        self.assertIsNotNone(mode)
        self.assertEqual(mode.status, CommandVerificationStatus.TRANSPORT_OK)
        tracked = manager.active_for(DEVICE, "outputLimit")
        self.assertIsNotNone(tracked)
        self.assertEqual(tracked.status, CommandVerificationStatus.TRANSPORT_OK)

    async def test_output_start_remains_one_complete_directional_post(self):
        data = await make_bootstrap()
        command = output_command()
        command.should_write_mode = True

        mapped = map_zensdk_command(
            authorized(command), data, first_request_id=1
        )

        self.assertEqual(mapped.properties, {
            "smartMode": 1,
            "acMode": 2,
            "outputLimit": 301,
            "inputLimit": 0,
        })

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
        for offgrid, expected in ((0, 1), (12, 1), (None, 1)):
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

    async def test_confirmed_stable_stop_uses_persistent_standby_smart_mode(self):
        data = await make_bootstrap()
        command = output_command(0)
        command.metadata.update({
            "native_offgrid_power_w": 20,
            SMART_MODE_STANDBY_CONFIRMED_METADATA_KEY: True,
        })

        mapped = map_zensdk_command(
            authorized(command), data, first_request_id=7
        )

        self.assertEqual(mapped.properties["smartMode"], 0)

    async def test_explicit_always_smart_mode_one_overrides_model_standby(self):
        data = await make_bootstrap()
        command = output_command(0)
        command.metadata.update({
            "native_offgrid_power_w": 0,
            SMART_MODE_STANDBY_CONFIRMED_METADATA_KEY: True,
            SMART_MODE_ALWAYS_ONE_METADATA_KEY: True,
        })

        mapped = map_zensdk_command(
            authorized(command), data, first_request_id=7
        )

        self.assertEqual(mapped.properties["smartMode"], 1)

    async def test_zero_command_uses_model_standby_smart_mode(self):
        data = await make_bootstrap(
            model="SolarFlow 2400 Pro", product_id="UNKNOWN_PRODUCT"
        )
        command = output_command(0)
        command.metadata["native_offgrid_power_w"] = 0

        mapped = map_zensdk_command(
            authorized(command), data, first_request_id=7
        )

        self.assertEqual(mapped.properties["smartMode"], 1)

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

    async def test_wrong_transport_is_rejected_and_fractional_power_is_rounded(self):
        data = await make_bootstrap()
        with self.assertRaisesRegex(ValueError, "wrong_transport"):
            map_zensdk_command(
                authorized(output_command(), transport=ZendureTransport.CLOUD_MQTT),
                data,
                first_request_id=1,
            )
        mapped = map_zensdk_command(
            authorized(output_command(300.5)), data, first_request_id=1
        )
        self.assertEqual(mapped.properties["outputLimit"], 300)
        for invalid_value in (-1, math.nan, math.inf):
            with self.subTest(invalid_value=invalid_value):
                with self.assertRaisesRegex(ValueError, "invalid_power_value"):
                    map_zensdk_command(
                        authorized(output_command(invalid_value)),
                        data,
                        first_request_id=1,
                    )

    async def test_http_failure_is_transport_error_and_never_retried(self):
        data = await make_bootstrap()
        calls = []
        manager = NativeCommandVerificationManager()

        async def post(url, **_kwargs):
            calls.append(url)
            return Response({"success": False}, 503)

        adapter = ZendureZenSdkCommandAdapter(
            data, post, manager, clock=lambda: NOW
        )
        result = await adapter.execute(authorized(output_command()))

        self.assertEqual(result.status, ZenSdkCommandStatus.TRANSPORT_ERROR)
        self.assertEqual(result.http_status, 503)
        self.assertEqual(result.requests_sent, 1)
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(result.verification_ids), 2)
        diagnostics = adapter.diagnostics()
        self.assertEqual(diagnostics["result"], "http_error")
        self.assertEqual(diagnostics["http_status"], 503)
        self.assertEqual(diagnostics["address_source"], "device_list_ip")
        self.assertEqual(diagnostics["properties"], ["outputLimit", "smartMode"])
        self.assertNotIn("url", diagnostics)
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
