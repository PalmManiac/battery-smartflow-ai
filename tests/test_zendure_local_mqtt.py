"""Read, identity and command tests for ZendureLegacy Local MQTT."""

from __future__ import annotations

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
from custom_components.battery_smartflow_ai.zendure_cloud import (  # noqa: E402
    ZendureCloudClient,
)
from custom_components.battery_smartflow_ai.zendure_local_mqtt import (  # noqa: E402
    LocalMqttCredentials,
    ZendureLocalMqttTransport,
)
from custom_components.battery_smartflow_ai.zendure_local_mqtt_commands import (  # noqa: E402
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


class LocalMqttTests(unittest.IsolatedAsyncioTestCase):
    async def test_transport_subscribes_only_verified_legacy_device(self):
        data = await discovered()
        sessions = []
        transport = ZendureLocalMqttTransport(
            data,
            LocalMqttCredentials("192.168.1.2", 1883, "user", "secret"),
            session_factory=lambda credentials: (
                sessions.append(FakeSession(credentials)) or sessions[-1]
            ),
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
