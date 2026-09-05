"""Read-only local ZenSDK report tests."""

from __future__ import annotations

from base64 import b64encode
from datetime import datetime, timezone
import sys
from types import SimpleNamespace
from types import ModuleType
import unittest
from dataclasses import replace

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
    async_write_zensdk_property,
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
    async def test_first_write_posts_one_allowlisted_property_to_exact_device(self):
        data = await make_bootstrap()
        calls = []

        async def post(url, **kwargs):
            calls.append((url, kwargs))
            return Response({"success": True}, 200)

        result = await async_write_zensdk_property(
            data, "cloud_mqtt:device-real-1", "outputLimit", 301, 7, post
        )

        self.assertTrue(result.accepted)
        self.assertEqual(calls[0][0], "http://192.168.1.44/properties/write")
        self.assertEqual(
            calls[0][1]["json"],
            {"sn": "serial-real-1", "properties": {"outputLimit": 301}, "id": 7},
        )

    async def test_first_write_rejects_every_other_property_without_network(self):
        data = await make_bootstrap()
        called = False

        async def post(*_args, **_kwargs):
            nonlocal called
            called = True
            return Response({})

        result = await async_write_zensdk_property(
            data, "cloud_mqtt:device-real-1", "inputLimit", 1, 1, post
        )
        self.assertFalse(result.accepted)
        self.assertEqual(result.result, "property_not_allowed")
        self.assertFalse(called)

    async def test_first_write_never_retries_an_ambiguous_timeout(self):
        data = await make_bootstrap()
        calls = []

        async def post(url, **_kwargs):
            calls.append(url)
            raise TimeoutError

        result = await async_write_zensdk_property(
            data, "cloud_mqtt:device-real-1", "outputLimit", 1, 1, post
        )
        self.assertFalse(result.accepted)
        self.assertEqual(calls, ["http://192.168.1.44/properties/write"])

    async def test_reads_private_ip_and_returns_transport_tagged_report(self):
        data = await make_bootstrap()
        requested = []
        payload = {
            "sn": "serial-real-1",
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
            return Response({"sn": "serial-real-1", "properties": {"electricLevel": 50}})

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
            return Response({"sn": "serial-real-1", "properties": {}})

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

    async def test_reassigned_ip_is_rejected_and_hostname_recovers_exact_device(self):
        data = await make_bootstrap()

        async def get(url, **kwargs):
            self.assertFalse(kwargs["allow_redirects"])
            serial = "other-main" if "192.168.1.44" in url else "serial-real-1"
            return Response({"sn": serial, "properties": {"electricLevel": 0}})

        result = await async_read_zensdk_reports(data, get)
        self.assertEqual([a.result for a in result.attempts], ["identity_mismatch", "success"])
        self.assertEqual(len(result.messages), 1)
        self.assertEqual(result.messages[0].device_candidate_id, "cloud_mqtt:device-real-1")
        state = ZendureCloudNormalizer(data).apply(result.messages[0]).state
        self.assertEqual(state.soc_pct.value, 0)
        self.assertTrue(state.soc_pct.valid)

    async def test_unidentified_and_malformed_reports_do_not_update_state(self):
        data = await make_bootstrap()
        cases = (
            ({"properties": {}, "packData": [{"sn": "serial-real-1"}]}, "identity_missing"),
            ({"sn": "wrong-device", "properties": {}}, "identity_mismatch"),
            ({"sn": "serial-real-1"}, "invalid_response"),
            ({"sn": "serial-real-1", "properties": []}, "invalid_response"),
            ({"sn": "serial-real-1", "properties": {}, "packData": [None]}, "invalid_response"),
            ({"sn": "serial-real-1", "properties": {}, "packData": {}}, "invalid_response"),
        )
        for payload, reason in cases:
            with self.subTest(reason=reason, payload=payload):
                async def get(_url, **_kwargs):
                    return Response(payload)

                result = await async_read_zensdk_reports(data, get)
                self.assertEqual(result.messages, ())
                self.assertEqual({a.result for a in result.attempts}, {reason})
                self.assertNotIn("serial-real-1", repr(result.attempts))
                self.assertNotIn("wrong-device", repr(result.attempts))

    async def test_missing_bootstrap_identity_makes_no_network_request(self):
        data = await make_bootstrap()
        device = data.devices[0]
        device = replace(device, candidate=replace(
            device.candidate, identity=replace(device.candidate.identity, serial_number=None)
        ))
        data = replace(data, devices=(device,))

        async def get(*_args, **_kwargs):
            self.fail("Missing identity must block the request")

        result = await async_read_zensdk_reports(data, get)
        self.assertEqual(result.messages, ())
        self.assertEqual(result.attempts[0].result, "identity_missing")

    async def test_multiple_identical_models_keep_states_and_packs_separate(self):
        data = await make_bootstrap()
        first = data.devices[0]
        second = replace(first, candidate=replace(
            first.candidate,
            identity=replace(first.candidate.identity, device_id="device-real-2", serial_number="serial-real-2"),
        ))
        data = replace(data, devices=(second, first), raw_device_list=(
            *data.raw_device_list,
            {**data.raw_device_list[0], "deviceKey": "device-real-2", "snNumber": "serial-real-2", "ip": "192.168.1.45"},
        ))

        async def get(url, **_kwargs):
            index = 2 if "192.168.1.45" in url else 1
            return Response({
                "sn": f"serial-real-{index}",
                "properties": {"electricLevel": index * 20},
                "packData": [{"sn": f"pack-{index}", "socLevel": index * 20}],
            })

        result = await async_read_zensdk_reports(data, get)
        normalizer = ZendureCloudNormalizer(data)
        states = {m.device_candidate_id: normalizer.apply(m).state for m in result.messages}
        self.assertEqual(len(states), 2)
        self.assertEqual(states["cloud_mqtt:device-real-1"].soc_pct.value, 20)
        self.assertEqual(states["cloud_mqtt:device-real-2"].soc_pct.value, 40)
        self.assertNotEqual(states["cloud_mqtt:device-real-1"].packs, states["cloud_mqtt:device-real-2"].packs)

    async def test_http_redirect_is_not_accepted_as_a_report(self):
        data = await make_bootstrap()

        async def get(_url, **kwargs):
            self.assertFalse(kwargs["allow_redirects"])
            return Response({}, status=302)

        result = await async_read_zensdk_reports(data, get)
        self.assertEqual(result.messages, ())
        self.assertEqual({a.result for a in result.attempts}, {"http_error"})

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
            return Response({"sn": "serial-real-1", "properties": {"electricLevel": 81}})

        success = await async_read_zensdk_reports(data, get)
        runtime._record_zensdk_cycle(success)
        runtime._apply_messages(success.messages)

        self.assertTrue(runtime._inventory.devices[candidate_id].online)
        self.assertEqual(
            runtime._inventory.devices[candidate_id].control_state,
            DeviceControlState.HEMS_BLOCKED,
        )
        self.assertEqual(
            runtime._inventory.devices[candidate_id].hems_status.value,
            "unknown",
        )
        self.assertEqual(runtime._zensdk_failures[candidate_id], 0)
        self.assertEqual(runtime._processed_messages, 1)
        self.assertEqual(
            runtime._states[candidate_id].observed_transport,
            ZendureTransport.ZENSDK,
        )


if __name__ == "__main__":
    unittest.main()
