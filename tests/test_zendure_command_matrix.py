"""Exercise approved Zendure command routes and readbacks across the model matrix."""

from __future__ import annotations

import unittest
from base64 import b64encode
from datetime import datetime, timedelta, timezone

from support import bootstrap

bootstrap()

from custom_components.battery_smartflow_ai.core.models import (
    DeviceCommand,
    ZendureTransport,
)
from custom_components.battery_smartflow_ai.hardware.zendure.cloud import (
    ZendureCloudClient,
)
from custom_components.battery_smartflow_ai.hardware.zendure.cloud_mqtt_commands import (
    CloudCommandStatus,
    ZendureCloudCommandAdapter,
)
from custom_components.battery_smartflow_ai.hardware.zendure.device_matrix import (
    ZENDURE_DEVICE_MATRIX,
    VerificationLevel,
)
from custom_components.battery_smartflow_ai.hardware.zendure.local_mqtt_commands import (
    LocalMqttCommandStatus,
    ZendureLocalMqttCommandAdapter,
)
from custom_components.battery_smartflow_ai.hardware.zendure.zensdk_commands import (
    ZendureZenSdkCommandAdapter,
    ZenSdkCommandStatus,
)
from custom_components.battery_smartflow_ai.native_command_verification import (
    CommandVerificationStatus,
    NativeCommandVerificationManager,
)
from custom_components.battery_smartflow_ai.native_device_command_gate import (
    AuthorizedNativeCommand,
)

NOW = datetime(2026, 10, 8, 10, 0, tzinfo=timezone.utc)
DEVICE_ID = "cloud_mqtt:matrix-device"

# Keep these expectations explicit: changing a capability in the production
# matrix must force an intentional update to the command-contract tests.
ALL_SUPPORTED_MODELS = frozenset(
    {
        "SF2400AC",
        "SF2400Pro",
        "SF2400AC+",
        "SF1600AC",
        "SF800",
        "SF800Plus",
        "SF800Pro",
        "SF800Pro2",
        "Hyper 2000",
        "HUB 2000",
    }
)
ZENSDK_SUPPORTED_MODELS = frozenset(
    {
        "SF2400AC",
        "SF2400Pro",
        "SF2400AC+",
        "SF1600AC",
        "SF800",
        "SF800Plus",
        "SF800Pro",
        "SF800Pro2",
    }
)
LOCAL_MQTT_SUPPORTED_MODELS = frozenset({"Hyper 2000", "HUB 2000"})


class Response:
    def __init__(self, data, status=200):
        self.data = data
        self.status = status

    async def json(self):
        return self.data


async def bootstrap_model(model: str):
    token = b64encode(b"https://api.example.com.app-key").decode()

    async def post(*_args, **_kwargs):
        return Response(
            {
                "code": 200,
                "success": True,
                "data": {
                    "deviceList": [
                        {
                            "deviceKey": "matrix-device",
                            "productKey": "matrix-product",
                            "productModel": model,
                            "snNumber": "matrix-serial",
                            "online": True,
                            "ip": "192.0.2.10",
                        }
                    ],
                    "mqtt": {
                        "clientId": "unused-client",
                        "url": "broker.example:1883",
                        "username": "unused-user",
                        "password": "unused-password",
                    },
                },
            }
        )

    return await ZendureCloudClient(post).async_discover(token)


def command(transport: ZendureTransport) -> AuthorizedNativeCommand:
    return AuthorizedNativeCommand(
        "matrix-correlation",
        DEVICE_ID,
        transport,
        DeviceCommand(
            "output",
            output_limit_w=123,
            should_write_mode=False,
            should_write_input=False,
            should_write_output=True,
        ),
    )


class CloudPublisher:
    def __init__(self):
        self.calls = []

    def write_properties(self, product_id, device_id, writes):
        self.calls.append((product_id, device_id, writes))
        return True

    def invoke_function(
        self, product_id, device_id, invocation, message_id, timestamp
    ):
        if not hasattr(self, "invocations"):
            self.invocations = []
        self.invocations.append(
            (product_id, device_id, invocation, message_id, timestamp)
        )
        return True


class LocalPublisher:
    def __init__(self):
        self.calls = []

    def invoke_function(
        self, product_id, device_id, invocation, message_id, timestamp
    ):
        self.calls.append(
            (product_id, device_id, invocation, message_id, timestamp)
        )
        return True


class ZendureCommandMatrixTests(unittest.IsolatedAsyncioTestCase):
    async def test_every_approved_model_transport_sends_and_confirms_readback(self):
        self.assertEqual(ALL_SUPPORTED_MODELS, frozenset(ZENDURE_DEVICE_MATRIX))

        for model_key, entry in ZENDURE_DEVICE_MATRIX.items():
            data = await bootstrap_model(entry.canonical_model)

            with self.subTest(model=model_key, transport="cloud_mqtt"):
                self.assertIs(
                    entry.transport(ZendureTransport.CLOUD_MQTT).write,
                    VerificationLevel.VERIFIED,
                )
                publisher = CloudPublisher()
                verification = NativeCommandVerificationManager()
                adapter = ZendureCloudCommandAdapter(
                    data, publisher, verification, clock=lambda: NOW
                )
                result = adapter.execute(command(ZendureTransport.CLOUD_MQTT))
                self.assertEqual(result.status, CloudCommandStatus.SENT)
                if model_key == "Hyper 2000":
                    self.assertEqual(publisher.calls, [])
                    self.assertEqual(
                        publisher.invocations[0][2].function, "deviceAutomation"
                    )
                    self.assertEqual(
                        publisher.invocations[0][2].arguments[0]["autoModelValue"]["outPower"],
                        123,
                    )
                elif model_key == "HUB 2000":
                    self.assertEqual(publisher.calls, [])
                    self.assertEqual(
                        publisher.invocations[0][2].function, "deviceAutomation"
                    )
                    self.assertEqual(
                        publisher.invocations[0][2].arguments[0]["autoModelValue"],
                        123,
                    )
                else:
                    self.assertEqual(len(publisher.calls), 1)
                    self.assertFalse(getattr(publisher, "invocations", []))
                self.assertEqual(
                    adapter.observe_properties(
                        device_id=DEVICE_ID,
                        properties={"outputLimit": 123},
                        observed_at=NOW + timedelta(seconds=1),
                    ),
                    1,
                )
                tracked = next(
                    verification.get(command_id)
                    for command_id in result.verification_ids
                    if verification.get(command_id).target_key == "outputLimit"
                )
                self.assertEqual(
                    tracked.status, CommandVerificationStatus.READBACK_CONFIRMED
                )

            with self.subTest(model=model_key, transport="zensdk"):
                capability = entry.transport(ZendureTransport.ZENSDK).write
                post_calls = []

                async def post(url, _post_calls=post_calls, **kwargs):
                    _post_calls.append((url, kwargs))
                    return Response({"success": True})

                verification = NativeCommandVerificationManager()
                adapter = ZendureZenSdkCommandAdapter(
                    data, post, verification, clock=lambda: NOW
                )
                result = await adapter.execute(command(ZendureTransport.ZENSDK))
                if model_key in ZENSDK_SUPPORTED_MODELS:
                    self.assertIs(capability, VerificationLevel.VERIFIED)
                    self.assertEqual(result.status, ZenSdkCommandStatus.SENT)
                    self.assertEqual(len(post_calls), 1)
                    self.assertEqual(
                        adapter.observe_properties(
                            device_id=DEVICE_ID,
                            properties={"outputLimit": 123},
                            observed_at=NOW + timedelta(seconds=1),
                        ),
                        1,
                    )
                    self.assertEqual(
                        verification.get(result.verification_ids[0]).status,
                        CommandVerificationStatus.READBACK_CONFIRMED,
                    )
                else:
                    self.assertNotEqual(capability, VerificationLevel.VERIFIED)
                    self.assertEqual(result.status, ZenSdkCommandStatus.REJECTED)
                    self.assertEqual(post_calls, [])

            with self.subTest(model=model_key, transport="local_mqtt"):
                capability = entry.transport(ZendureTransport.LOCAL_MQTT).write
                publisher = LocalPublisher()
                verification = NativeCommandVerificationManager()
                adapter = ZendureLocalMqttCommandAdapter(
                    data, publisher, verification, clock=lambda: NOW
                )
                result = adapter.execute(command(ZendureTransport.LOCAL_MQTT))
                if model_key in LOCAL_MQTT_SUPPORTED_MODELS:
                    self.assertIs(capability, VerificationLevel.VERIFIED)
                    self.assertEqual(result.status, LocalMqttCommandStatus.SENT)
                    self.assertEqual(len(publisher.calls), 1)
                    self.assertEqual(
                        adapter.observe_properties(
                            device_id=DEVICE_ID,
                            properties={"outputLimit": 123},
                            observed_at=NOW + timedelta(seconds=1),
                        ),
                        1,
                    )
                    self.assertEqual(
                        verification.get(result.verification_ids[0]).status,
                        CommandVerificationStatus.READBACK_CONFIRMED,
                    )
                    invocation = publisher.calls[0][2]
                    if model_key == "Hyper 2000":
                        self.assertEqual(
                            invocation.arguments[0]["autoModelValue"]["outPower"],
                            123,
                        )
                    else:
                        self.assertEqual(invocation.arguments[0]["autoModelValue"], 123)
                else:
                    self.assertNotEqual(capability, VerificationLevel.VERIFIED)
                    self.assertEqual(result.status, LocalMqttCommandStatus.REJECTED)
                    self.assertEqual(publisher.calls, [])

    async def test_expected_support_sets_match_the_production_matrix(self):
        self.assertEqual(
            {
                key
                for key, entry in ZENDURE_DEVICE_MATRIX.items()
                if entry.transport(ZendureTransport.CLOUD_MQTT).write
                is VerificationLevel.VERIFIED
            },
            ALL_SUPPORTED_MODELS,
        )
        self.assertEqual(
            {
                key
                for key, entry in ZENDURE_DEVICE_MATRIX.items()
                if entry.transport(ZendureTransport.ZENSDK).write
                is VerificationLevel.VERIFIED
            },
            ZENSDK_SUPPORTED_MODELS,
        )
        self.assertEqual(
            {
                key
                for key, entry in ZENDURE_DEVICE_MATRIX.items()
                if entry.transport(ZendureTransport.LOCAL_MQTT).write
                is VerificationLevel.VERIFIED
            },
            LOCAL_MQTT_SUPPORTED_MODELS,
        )


if __name__ == "__main__":
    unittest.main()
