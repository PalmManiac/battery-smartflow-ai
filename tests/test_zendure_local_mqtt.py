"""Read, identity and command tests for ZendureLegacy Local MQTT."""

from __future__ import annotations

import asyncio
import json
import unittest
from base64 import b64encode
from datetime import datetime, timezone

from support import bootstrap

bootstrap()

from custom_components.battery_smartflow_ai.core.models import (  # noqa: E402
    DeviceCommand,
    ZendureTransport,
)
from custom_components.battery_smartflow_ai.native_command_verification import (  # noqa: E402
    NativeCommandVerificationManager,
)
from custom_components.battery_smartflow_ai.native_device_command_gate import (  # noqa: E402
    AuthorizedNativeCommand,
)
from custom_components.battery_smartflow_ai.hardware.zendure.cloud import (  # noqa: E402
    ZendureCloudClient,
)
from custom_components.battery_smartflow_ai.hardware.zendure.local_mqtt import (  # noqa: E402
    LocalMqttCredentials,
    ZendureLocalMqttTransport,
    _LEGACY_PERIODIC_REFRESH_SECONDS,
)
from custom_components.battery_smartflow_ai.hardware.zendure.local_mqtt_commands import (  # noqa: E402
    LocalMqttCommandStatus,
    ZendureLocalMqttCommandAdapter,
    map_local_mqtt_command,
)

NOW = datetime(2026, 9, 6, 8, 0, tzinfo=timezone.utc)


class Response:
    def __init__(self, data):
        self.data = data

    async def json(self):
        return self.data


async def discovered(model="Hyper 2000"):
    token = b64encode(b"https://api.example.com.app-key").decode()

    async def post(*_args, **_kwargs):
        return Response(
            {
                "code": 200,
                "success": True,
                "data": {
                    "deviceList": [
                        {
                            "deviceKey": "legacy-1",
                            "productKey": "legacy-product",
                            "productModel": model,
                            "deviceName": "Legacy",
                            "snNumber": "legacy-serial",
                            "online": True,
                        },
                        {
                            "deviceKey": "zen-1",
                            "productKey": "zen-product",
                            "productModel": "SolarFlow 2400 AC",
                            "deviceName": "Zen",
                            "snNumber": "zen-serial",
                            "online": True,
                        },
                    ],
                    "mqtt": {
                        "clientId": "cloud",
                        "url": "cloud:1883",
                        "username": "cloud-user",
                        "password": "cloud-pass",
                    },
                },
            }
        )

    return await ZendureCloudClient(post).async_discover(token)


def authorized(data, command):
    item = data.devices[0]
    return AuthorizedNativeCommand(
        "correlation",
        item.candidate.candidate_id,
        ZendureTransport.LOCAL_MQTT,
        command,
    )


class FakeSession:
    connection_phase = "created"
    connection_diagnostics = {}

    def __init__(self, _credentials):
        self.subscriptions = ()
        self.requests = []
        self.invocations = []

    def set_callbacks(self, connect, disconnect, message):
        self.on_connect, self.on_disconnect, self.on_message = (
            connect,
            disconnect,
            message,
        )

    def connect(self):
        self.on_connect(True, None)

    def disconnect(self):
        return None

    def subscribe(self, topics):
        self.subscriptions = topics

    def request_all(self, product, device, message, timestamp):
        self.requests.append((product, device, message, timestamp))

    def write_properties(self, *_args):
        raise AssertionError("cloud write used")

    def invoke_function(self, product, device, invocation, message, timestamp):
        self.invocations.append((product, device, invocation, message, timestamp))
        return True


class FakeBridge:
    instances = []

    def __init__(self, bootstrap, publish_local):
        self.bootstrap = bootstrap
        self.publish_local = publish_local
        self.connected_devices = ()
        self.status = "waiting_for_local_device"
        self.started = False
        self.__class__.instances.append(self)

    async def async_start(self, *, timeout=15.0):
        del timeout
        self.started = True

    async def async_stop(self):
        return None

    def forward_local(self, _topic, _payload):
        return False


class LocalMqttTests(unittest.IsolatedAsyncioTestCase):
    def test_periodic_legacy_refresh_stays_inside_native_safety_window(self):
        """A quiet legacy device must refresh before native state expires."""
        self.assertEqual(_LEGACY_PERIODIC_REFRESH_SECONDS, 15.0)
        self.assertLess(_LEGACY_PERIODIC_REFRESH_SECONDS, 30.0)

    async def test_bridge_uses_cloud_bootstrap_not_local_broker(self):
        data = await discovered()
        transport = ZendureLocalMqttTransport(
            data,
            LocalMqttCredentials("192.168.1.2", 1883, "user", "secret"),
            session_factory=FakeSession,
            bridge_factory=FakeBridge,
        )
        await transport.async_start()
        bridge = FakeBridge.instances[-1]
        self.assertTrue(bridge.started)
        self.assertEqual(bridge.bootstrap.mqtt.url, "cloud:1883")
        self.assertNotEqual(bridge.bootstrap.mqtt.url, transport._bootstrap.mqtt.url)
        await transport.async_stop()

    async def test_same_cloud_and_local_endpoint_disables_device_id_bridge(self):
        data = await discovered()
        same_endpoint = type(data)(
            devices=data.devices,
            mqtt=type(data.mqtt)(
                client_id=data.mqtt.client_id,
                url="mqtt://192.168.1.2:1883",
                username=data.mqtt.username,
                password=data.mqtt.password,
            ),
            raw_device_list=data.raw_device_list,
        )
        before = len(FakeBridge.instances)
        transport = ZendureLocalMqttTransport(
            same_endpoint,
            LocalMqttCredentials("192.168.1.2", 1883, "user", "secret"),
            session_factory=FakeSession,
            bridge_factory=FakeBridge,
        )
        await transport.async_start()
        self.assertEqual(len(FakeBridge.instances), before)
        self.assertEqual(transport.bridge_status, "disabled_same_endpoint")
        await transport.async_stop()

    async def test_local_sessions_use_distinct_client_id_seeds(self):
        data = await discovered()
        credentials = LocalMqttCredentials(
            "192.168.1.2", 1883, "shared-user", "secret"
        )
        first = ZendureLocalMqttTransport(
            data, credentials, session_factory=FakeSession
        )
        second = ZendureLocalMqttTransport(
            data, credentials, session_factory=FakeSession
        )
        self.assertNotEqual(
            first._bootstrap.mqtt.client_id,
            second._bootstrap.mqtt.client_id,
        )

    async def test_transport_subscribes_only_verified_legacy_device(self):
        data = await discovered()
        sessions = []
        transport = ZendureLocalMqttTransport(
            data,
            LocalMqttCredentials("192.168.1.2", 1883, "user", "secret"),
            session_factory=lambda credentials: (
                sessions.append(FakeSession(credentials)) or sessions[-1]
            ),
            bridge_factory=FakeBridge,
            clock=lambda: NOW,
        )
        await transport.async_start()
        self.assertEqual(transport.connection_variant, "local_mqtt31_persistent")
        self.assertEqual(
            sessions[0].subscriptions,
            (
                "/legacy-product/legacy-1/#",
                "iot/legacy-product/legacy-1/#",
            ),
        )
        sessions[0].on_message(
            "iot/legacy-product/legacy-1/properties/report",
            json.dumps({"properties": {"electricLevel": 54}}).encode(),
        )
        await __import__("asyncio").sleep(0)
        self.assertEqual(transport.messages[-1].transport, "local_mqtt")
        self.assertEqual(
            transport.messages[-1].device_candidate_id,
            "cloud_mqtt:legacy-1",
        )
        await transport.async_stop()

    async def test_retries_get_all_until_legacy_properties_arrive(self):
        data = await discovered()
        sessions = []
        transport = ZendureLocalMqttTransport(
            data,
            LocalMqttCredentials("192.168.1.2", 1883, "user", "secret"),
            session_factory=lambda credentials: (
                sessions.append(FakeSession(credentials)) or sessions[-1]
            ),
            bridge_factory=FakeBridge,
            clock=lambda: NOW,
            initial_refresh_seconds=0.01,
            periodic_refresh_seconds=0.2,
        )
        await transport.async_start()
        self.assertEqual(len(sessions[0].requests), 1)

        await asyncio.sleep(0.025)
        self.assertGreaterEqual(len(sessions[0].requests), 2)
        self.assertGreaterEqual(
            transport.refresh_diagnostics["request_count"], 1
        )
        self.assertEqual(
            transport.refresh_diagnostics["devices_waiting_for_properties"], 1
        )

        sessions[0].on_message(
            "iot/legacy-product/legacy-1/properties/report",
            json.dumps({"properties": {"electricLevel": 54}}).encode(),
        )
        await asyncio.sleep(0.025)
        requests_after_telemetry = len(sessions[0].requests)
        await asyncio.sleep(0.025)
        self.assertEqual(len(sessions[0].requests), requests_after_telemetry)
        self.assertEqual(
            transport.refresh_diagnostics["devices_waiting_for_properties"], 0
        )
        await transport.async_stop()

    async def test_hyper_input_output_and_stop_are_allow_listed(self):
        data = await discovered()
        input_call = map_local_mqtt_command(
            authorized(
                data,
                DeviceCommand(
                    "input",
                    input_limit_w=500,
                    output_limit_w=0,
                    should_write_mode=True,
                    should_write_input=True,
                ),
            ),
            data,
        )
        self.assertEqual(input_call.function, "deviceAutomation")
        self.assertEqual(
            input_call.arguments[0]["autoModelValue"]["chargingPower"], 500
        )

        output_call = map_local_mqtt_command(
            authorized(
                data,
                DeviceCommand(
                    "output",
                    input_limit_w=0,
                    output_limit_w=700,
                    should_write_output=True,
                ),
            ),
            data,
        )
        self.assertEqual(output_call.arguments[0]["autoModelValue"]["outPower"], 700)

        stop_call = map_local_mqtt_command(
            authorized(
                data,
                DeviceCommand(
                    "output",
                    output_limit_w=0,
                    should_write_output=True,
                ),
            ),
            data,
        )
        self.assertEqual(stop_call.arguments[0]["autoModelProgram"], 0)

    async def test_adapter_uses_function_invoke_once(self):
        data = await discovered()
        session = FakeSession(None)
        adapter = ZendureLocalMqttCommandAdapter(
            data, session, NativeCommandVerificationManager(), clock=lambda: NOW
        )
        result = adapter.execute(
            authorized(
                data,
                DeviceCommand(
                    "output",
                    output_limit_w=600,
                    should_write_output=True,
                ),
            )
        )
        self.assertEqual(result.status, LocalMqttCommandStatus.SENT)
        self.assertEqual(len(session.invocations), 1)
        self.assertEqual(session.invocations[0][0:2], ("legacy-product", "legacy-1"))

    async def test_hub_input_fails_closed(self):
        data = await discovered("SolarFlow Hub 2000")
        with self.assertRaisesRegex(ValueError, "input_not_supported"):
            map_local_mqtt_command(
                authorized(
                    data,
                    DeviceCommand(
                        "input",
                        input_limit_w=300,
                        should_write_input=True,
                    ),
                ),
                data,
            )

    def test_credentials_hide_all_values(self):
        credentials = LocalMqttCredentials(
            "broker.internal", 1883, "mqtt-user", "mqtt-password"
        )
        text = repr(credentials)
        for secret in ("broker.internal", "mqtt-user", "mqtt-password"):
            self.assertNotIn(secret, text)


if __name__ == "__main__":
    unittest.main()
