"""Privacy-safe Zendure initial-sync capture tests."""

from __future__ import annotations

from base64 import b64encode
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.zendure_cloud import (  # noqa: E402
    ZendureCloudClient,
)
from custom_components.battery_smartflow_ai.zendure_cloud_mqtt import (  # noqa: E402
    CloudMqttMessage,
    ConnectionState,
)
from custom_components.battery_smartflow_ai.zendure_initial_sync import (  # noqa: E402
    InitialSyncExportError,
    ZendureInitialSyncRecorder,
    async_capture_initial_sync,
    export_initial_sync_capture,
)
from custom_components.battery_smartflow_ai.zendure_zensdk import (  # noqa: E402
    ZenSdkReadAttempt,
)


class Response:
    def __init__(self, data):
        self.data = data

    async def json(self):
        return self.data


async def make_bootstrap():
    token = b64encode(b"https://api.example.com.app-key-secret").decode()

    async def post(*_args, **_kwargs):
        return Response(
            {
                "code": 200,
                "success": True,
                "data": {
                    "deviceList": [
                        {
                            "deviceKey": "real-device-1",
                            "snNumber": "real-serial-1",
                            "productKey": "product-a",
                            "productModel": "SolarFlow2400AC",
                            "deviceName": "Garage battery",
                            "firmwareVersion": "2.3.4",
                            "packData": [
                                {
                                    "packId": "real-pack-1",
                                    "snNumber": "real-pack-serial-1",
                                }
                            ],
                        },
                        {
                            "deviceKey": "real-device-2",
                            "productKey": "product-b",
                            "productModel": "FutureModel",
                            "deviceName": "Second battery",
                        },
                    ],
                    "mqtt": {
                        "clientId": "mqtt-client-secret",
                        "url": "mqtts://broker.secret:8883",
                        "username": "mqtt-user-secret",
                        "password": "mqtt-password-secret",
                    },
                },
            }
        )

    return await ZendureCloudClient(post).async_discover(token)


def message(
    at: datetime,
    device: str,
    topic_device: str,
    payload,
    *,
    pack: str | None = None,
    payload_format: str = "json",
    raw: bytes | None = None,
):
    return CloudMqttMessage(
        received_at=at,
        topic=f"/product-a/{topic_device}/properties/report",
        payload=raw if raw is not None else json.dumps(payload).encode(),
        parsed_payload=payload,
        payload_format=payload_format,
        device_candidate_id=device,
        pack_id=pack,
        known_topic=True,
        session_number=1,
    )


class MutableTime:
    def __init__(self):
        self.elapsed = 0.0
        self.wall = datetime(2026, 9, 2, 14, 0, tzinfo=timezone.utc)

    def monotonic(self):
        return self.elapsed

    def clock(self):
        return self.wall + timedelta(seconds=self.elapsed)

    def advance(self, seconds):
        self.elapsed += seconds


class InitialSyncCaptureTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bootstrap = await make_bootstrap()
        self.time = MutableTime()

    def recorder(self, **kwargs):
        return ZendureInitialSyncRecorder(
            self.bootstrap,
            quiet_period=2.0,
            hard_timeout=10.0,
            clock=self.time.clock,
            monotonic=self.time.monotonic,
            **kwargs,
        )

    async def test_discovery_raw_response_is_retained_inside_transport_boundary(self):
        self.assertEqual(len(self.bootstrap.raw_device_list), 2)
        self.assertEqual(
            self.bootstrap.raw_device_list[0]["firmwareVersion"], "2.3.4"
        )
        self.assertNotIn("mqtt-password-secret", repr(self.bootstrap))

    async def test_quiet_completion_requires_every_main_device(self):
        recorder = self.recorder()
        recorder.observe_message(
            message(
                self.time.clock(),
                "cloud_mqtt:real-device-1",
                "real-device-1",
                {"properties": {"socLevel": 60}},
            )
        )
        self.time.advance(3)
        self.assertIsNone(recorder.completion())
        recorder.observe_message(
            message(
                self.time.clock(),
                "cloud_mqtt:real-device-2",
                "real-device-2",
                {"properties": {"electricLevel": 44}},
            )
        )
        self.time.advance(2.1)
        self.assertEqual(recorder.completion(), (True, "initial_sync_quiet"))

    async def test_only_novel_topics_or_properties_extend_quiet_period(self):
        recorder = self.recorder()
        first = message(
            self.time.clock(),
            "cloud_mqtt:real-device-1",
            "real-device-1",
            {"properties": {"socLevel": 60}},
        )
        recorder.observe_message(first)
        self.time.advance(1.5)
        recorder.observe_message(
            message(
                self.time.clock(),
                "cloud_mqtt:real-device-1",
                "real-device-1",
                {"properties": {"socLevel": 61}},
            )
        )
        self.time.advance(0.6)
        recorder.observe_message(
            message(
                self.time.clock(),
                "cloud_mqtt:real-device-2",
                "real-device-2",
                {"properties": {"electricLevel": 40}},
            )
        )
        self.time.advance(2.1)
        self.assertEqual(recorder.completion(), (True, "initial_sync_quiet"))

    async def test_timeout_produces_useful_incomplete_capture(self):
        recorder = self.recorder()
        recorder.observe_connection(ConnectionState.CONNECTED)
        recorder.observe_message(
            message(
                self.time.clock(),
                "cloud_mqtt:real-device-1",
                "real-device-1",
                {"properties": {"socLevel": 60}},
            )
        )
        self.time.advance(10)
        complete, reason = recorder.completion()
        result = recorder.finish(complete=complete, reason=reason)
        self.assertFalse(result.complete)
        self.assertEqual(result.completion_reason, "hard_timeout")
        self.assertEqual(len(result.messages), 1)

    async def test_export_has_raw_and_summary_with_complete_nested_properties(self):
        recorder = self.recorder()
        recorder.observe_connection(ConnectionState.CONNECTED)
        recorder.observe_message(
            message(
                self.time.clock(),
                "cloud_mqtt:real-device-1",
                "real-device-1",
                {
                    "deviceKey": "real-device-1",
                    "properties": {
                        "socLevel": 60,
                        "packData": {
                            "packId": "real-pack-1",
                            "cell": {"voltage": 3.42},
                        },
                        "futureUnknown": [1, 2, 3],
                    },
                },
                pack="real-pack-1",
            )
        )
        result = recorder.finish(complete=True, reason="initial_sync_quiet")
        data = result.as_dict()
        self.assertIn("raw_communication", data)
        self.assertIn("bsfai_interpretation", data)
        properties = data["bsfai_interpretation"]["properties"]
        self.assertIn("socLevel", properties)
        self.assertIn("packData.cell.voltage", properties)
        self.assertIn("futureUnknown", properties)
        self.assertEqual(properties["futureUnknown"]["types"], ["array"])

    async def test_summary_collects_all_pack_ids_from_main_device_report(self):
        recorder = self.recorder()
        recorder.observe_message(
            message(
                self.time.clock(),
                "cloud_mqtt:real-device-1",
                "real-device-1",
                {
                    "properties": {"packNum": 2},
                    "packData": [
                        {"sn": "pack-b", "socLevel": 52},
                        {"sn": "pack-a", "socLevel": 48},
                    ],
                },
            )
        )

        summary = recorder.finish(complete=True, reason="test").as_dict()[
            "bsfai_interpretation"
        ]

        pack_ids = summary["pack_ids"]
        self.assertEqual(len(pack_ids), 2)
        self.assertEqual(len(set(pack_ids)), 2)
        self.assertTrue(all(item.startswith("ZD_SERIAL_A") for item in pack_ids))
        self.assertNotIn("pack-a", pack_ids)
        self.assertNotIn("pack-b", pack_ids)

    async def test_all_secrets_and_identities_are_consistently_sanitized(self):
        recorder = self.recorder()
        recorder.observe_message(
            message(
                self.time.clock(),
                "cloud_mqtt:real-device-1",
                "real-device-1",
                {
                    "deviceKey": "real-device-1",
                    "packId": "real-pack-1",
                    "properties": {
                        "password": "payload-secret",
                        "token": "payload-token",
                    },
                },
                pack="real-pack-1",
            )
        )
        text = json.dumps(
            recorder.finish(complete=True, reason="test").as_dict()
        )
        for secret in (
            "real-device-1",
            "real-device-2",
            "real-serial-1",
            "real-pack-1",
            "payload-secret",
            "payload-token",
            "mqtt-password-secret",
            "Garage battery",
            "Second battery",
        ):
            self.assertNotIn(secret, text)
        self.assertIn("ZD_DEVICE_A1", text)
        self.assertIn("ZD_PACK_A1", text)

    async def test_binary_and_invalid_json_are_preserved(self):
        recorder = self.recorder()
        recorder.observe_message(
            message(
                self.time.clock(),
                "cloud_mqtt:real-device-1",
                "real-device-1",
                b"\xff\x00",
                payload_format="binary",
                raw=b"\xff\x00",
            )
        )
        raw = recorder.finish(complete=False, reason="test").as_dict()[
            "raw_communication"
        ]["mqtt_messages"][0]
        self.assertEqual(raw["payload"], {"base64": "/wA="})

    async def test_atomic_export_creates_shareable_json(self):
        recorder = self.recorder()
        result = recorder.finish(complete=False, reason="hard_timeout")
        with tempfile.TemporaryDirectory() as directory:
            exported = export_initial_sync_capture(
                result, config_directory=directory
            )
            self.assertTrue(exported.path.is_file())
            self.assertEqual(exported.path.parent, Path(directory) / "bsfai" / "debug")
            data = json.loads(exported.path.read_text(encoding="utf-8"))
            self.assertEqual(
                data["meta"]["schema"],
                "battery_smartflow_ai.zendure_initial_sync",
            )
            self.assertFalse(data["meta"]["complete"])
            self.assertFalse(list(exported.path.parent.glob("*.tmp")))

    async def test_zensdk_report_and_attempt_are_exported_without_lan_identity(self):
        local_report = message(
            self.time.clock(),
            "cloud_mqtt:real-device-1",
            "real-device-1",
            {
                "properties": {"electricLevel": 75},
                "packData": [{"sn": "real-pack-1", "socLevel": 74}],
            },
        )
        local_report = CloudMqttMessage(
            received_at=local_report.received_at,
            topic="zensdk/properties/report",
            payload=local_report.payload,
            parsed_payload=local_report.parsed_payload,
            payload_format="json",
            device_candidate_id=local_report.device_candidate_id,
            pack_id=None,
            known_topic=True,
            session_number=0,
            transport="zensdk",
        )
        recorder = ZendureInitialSyncRecorder(
            self.bootstrap,
            clock=self.time.clock,
            monotonic=self.time.monotonic,
            initial_messages=(local_report,),
            zensdk_attempts=(
                ZenSdkReadAttempt(
                    "cloud_mqtt:real-device-1",
                    "device_list_ip",
                    "success",
                    200,
                ),
            ),
        )
        package = recorder.finish(complete=True, reason="initial_sync_quiet").as_dict()

        self.assertEqual(
            package["raw_communication"]["zensdk_responses"][0]["transport"],
            "zensdk",
        )
        self.assertEqual(package["raw_communication"]["mqtt_messages"], [])
        self.assertEqual(
            package["raw_communication"]["zensdk_requests"][0]["path"],
            "/properties/report",
        )
        self.assertEqual(len(package["bsfai_interpretation"]["pack_ids"]), 1)
        self.assertTrue(
            package["bsfai_interpretation"]["pack_ids"][0].startswith("ZD_SERIAL_A")
        )
        self.assertEqual(
            package["raw_communication"]["device_list"][0]["deviceKey"],
            package["raw_communication"]["zensdk_responses"][0]["device_id"],
        )
        self.assertEqual(
            package["bsfai_interpretation"]["devices_with_messages"],
            [package["raw_communication"]["device_list"][0]["deviceKey"]],
        )

    async def test_export_size_limit_is_enforced(self):
        result = self.recorder().finish(complete=False, reason="test")
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(
                InitialSyncExportError, "capture_size_limit_exceeded"
            ):
                export_initial_sync_capture(
                    result,
                    config_directory=directory,
                    max_export_bytes=1,
                )

    async def test_orchestrator_returns_partial_result_on_connection_failure(self):
        class FailedTransport:
            state = ConnectionState.DISCONNECTED
            messages = ()
            connection_variant = "mqtt31_persistent"
            connection_phase = "dns_or_tcp_connect"

            async def async_start(self, *, timeout):
                raise RuntimeError("mqtt-user-secret")

        result = await async_capture_initial_sync(
            self.bootstrap,
            FailedTransport(),
            quiet_period=0.01,
            hard_timeout=0.1,
        )
        self.assertFalse(result.complete)
        self.assertEqual(result.completion_reason, "mqtt_connect_failed")
        self.assertNotIn("mqtt-user-secret", json.dumps(result.as_dict()))
        self.assertEqual(
            result.connection_events[-1]["phase"],
            "dns_or_tcp_connect",
        )
        self.assertEqual(
            result.connection_events[-1]["variant"],
            "mqtt31_persistent",
        )

    async def test_orchestrator_completes_after_real_quiet_period(self):
        messages = (
            message(
                self.time.clock(),
                "cloud_mqtt:real-device-1",
                "real-device-1",
                {"properties": {"socLevel": 60}},
            ),
            message(
                self.time.clock(),
                "cloud_mqtt:real-device-2",
                "real-device-2",
                {"properties": {"socLevel": 50}},
            ),
        )

        class ConnectedTransport:
            state = ConnectionState.DISCONNECTED

            async def async_start(self, *, timeout):
                self.state = ConnectionState.CONNECTED

            @property
            def messages(self):
                return messages

        result = await async_capture_initial_sync(
            self.bootstrap,
            ConnectedTransport(),
            quiet_period=0.01,
            hard_timeout=0.2,
            poll_interval=0.002,
        )
        self.assertTrue(result.complete)
        self.assertEqual(result.completion_reason, "initial_sync_quiet")
        self.assertEqual(len(result.messages), 2)


if __name__ == "__main__":
    unittest.main()
