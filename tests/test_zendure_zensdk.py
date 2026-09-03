"""Read-only local ZenSDK report tests."""

from __future__ import annotations

from base64 import b64encode
from datetime import datetime, timezone
import sys
from types import SimpleNamespace
from types import ModuleType
import unittest

from support import bootstrap as bootstrap_test_environment


bootstrap_test_environment()

helpers_module = ModuleType("homeassistant.helpers")
aiohttp_module = ModuleType("homeassistant.helpers.aiohttp_client")
aiohttp_module.async_get_clientsession = lambda _hass: None
sys.modules.setdefault("homeassistant.helpers", helpers_module)
sys.modules.setdefault("homeassistant.helpers.aiohttp_client", aiohttp_module)

from custom_components.battery_smartflow_ai.zendure_cloud import (  # noqa: E402
    ZendureCloudClient,
)
from custom_components.battery_smartflow_ai.zendure_zensdk import (  # noqa: E402
    ZenSdkReadAttempt,
    ZenSdkReadResult,
    _candidate_addresses,
    async_read_zensdk_reports,
)
from custom_components.battery_smartflow_ai.zendure_normalizer import (  # noqa: E402
    ZendureCloudNormalizer,
)
from custom_components.battery_smartflow_ai.core.models import (  # noqa: E402
    DeviceControlState,
    ZendureTransport,
)
from custom_components.battery_smartflow_ai.native_zendure_runtime import (  # noqa: E402
    NativeZendureRuntime,
)


class Response:
    def __init__(self, data, status=200):
        self.data = data
        self.status = status

    async def json(self):
        return self.data


async def make_bootstrap(*, ip="192.168.1.44"):
    token = b64encode(b"https://api.example.com.app-key").decode()

    async def post(*_args, **_kwargs):
        return Response(
            {
                "code": 200,
                "success": True,
                "data": {
                    "deviceList": [
                        {
                            "deviceKey": "device-real-1",
                            "snNumber": "serial-real-1",
                            "productKey": "BC8B7F",
                            "productModel": "SolarFlow 2400 AC",
                            "deviceName": "Garage",
                            "online": True,
                            "ip": ip,
                        }
                    ],
                    "mqtt": {
                        "clientId": "client-secret",
                        "url": "mqtt://broker.example:1883",
                        "username": "user-secret",
                        "password": "password-secret",
                    },
                },
            }
        )

    return await ZendureCloudClient(post).async_discover(token)


class ZenSdkReadTests(unittest.IsolatedAsyncioTestCase):
    async def test_reads_private_ip_and_returns_transport_tagged_report(self):
        data = await make_bootstrap()
        requested = []
        payload = {
            "properties": {"electricLevel": 73},
            "packData": [{"sn": "pack-real-1", "socLevel": 72}],
        }

        async def get(url, **_kwargs):
            requested.append(url)
            return Response(payload)

        result = await async_read_zensdk_reports(
            data,
            get,
            clock=lambda: datetime(2026, 9, 3, 16, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(requested, ["http://192.168.1.44/properties/report"])
        self.assertEqual(result.attempts[0].result, "success")
        self.assertEqual(result.attempts[0].address_source, "device_list_ip")
        self.assertEqual(result.messages[0].transport, "zensdk")
        self.assertEqual(result.messages[0].parsed_payload, payload)
        normalized = ZendureCloudNormalizer(data).apply(result.messages[0])
        self.assertIsNotNone(normalized)
        self.assertEqual(
            normalized.state.observed_transport,
            ZendureTransport.ZENSDK,
        )
        self.assertEqual(len(normalized.state.packs), 1)

    async def test_falls_back_to_derived_local_hostname(self):
        data = await make_bootstrap()
        requested = []

        async def get(url, **_kwargs):
            requested.append(url)
            if "192.168.1.44" in url:
                raise OSError("unreachable")
            return Response({"properties": {"electricLevel": 50}})

        result = await async_read_zensdk_reports(data, get)

        self.assertEqual(len(requested), 2)
        self.assertEqual(
            requested[1],
            "http://zendure-SolarFlow2400AC-serial-real-1.local/properties/report",
        )
        self.assertEqual(
            [attempt.result for attempt in result.attempts],
            ["cannot_connect", "success"],
        )

    async def test_rejects_public_or_malformed_device_list_address(self):
        data = await make_bootstrap(ip="8.8.8.8")
        requested = []

        async def get(url, **_kwargs):
            requested.append(url)
            return Response({"properties": {}})

        await async_read_zensdk_reports(data, get)

        self.assertEqual(len(requested), 1)
        self.assertIn(".local/properties/report", requested[0])
        self.assertNotIn("8.8.8.8", requested[0])

    def test_address_candidates_reject_untrusted_hostname_components(self):
        self.assertEqual(
            _candidate_addresses(
                {"ip": "https://example.com"},
                "Bad/model",
                "serial?query=1",
            ),
            (),
        )

    async def test_runtime_marks_offline_after_three_failures_and_recovers_read_only(self):
        data = await make_bootstrap()
        candidate_id = data.devices[0].candidate.candidate_id
        runtime = NativeZendureRuntime(
            SimpleNamespace(),
            app_token="configured",
            selected_device=None,
            notify=lambda: None,
        )
        data.register_candidates(runtime._inventory)
        runtime._inventory.add_observed_system(
            candidate_id,
            system_id=candidate_id,
        )
        runtime._normalizer = ZendureCloudNormalizer(data)
        failure = ZenSdkReadResult(
            (),
            (
                ZenSdkReadAttempt(
                    candidate_id,
                    "device_list_ip",
                    "timeout",
                ),
            ),
        )

        runtime._record_zensdk_cycle(failure)
        runtime._record_zensdk_cycle(failure)
        self.assertTrue(runtime._inventory.devices[candidate_id].online)
        runtime._record_zensdk_cycle(failure)
        self.assertFalse(runtime._inventory.devices[candidate_id].online)
        self.assertEqual(
            runtime._inventory.devices[candidate_id].control_state,
            DeviceControlState.OFFLINE,
        )

        async def get(_url, **_kwargs):
            return Response({"properties": {"electricLevel": 81}})

        success = await async_read_zensdk_reports(data, get)
        runtime._record_zensdk_cycle(success)
        runtime._apply_messages(success.messages)

        self.assertTrue(runtime._inventory.devices[candidate_id].online)
        self.assertEqual(
            runtime._inventory.devices[candidate_id].control_state,
            DeviceControlState.OBSERVATION,
        )
        self.assertEqual(runtime._zensdk_failures[candidate_id], 0)
        self.assertEqual(runtime._processed_messages, 1)
        self.assertEqual(
            runtime._states[candidate_id].observed_transport,
            ZendureTransport.ZENSDK,
        )


if __name__ == "__main__":
    unittest.main()
