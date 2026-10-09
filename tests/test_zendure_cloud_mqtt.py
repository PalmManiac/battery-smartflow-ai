"""Strict read-only Zendure Cloud MQTT transport tests."""

from __future__ import annotations

import asyncio
import inspect
import json
import socket
import threading
import unittest
from base64 import b64encode
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from custom_components.battery_smartflow_ai.hardware.zendure.cloud import (
    ZendureCloudClient,
)
from custom_components.battery_smartflow_ai.hardware.zendure.cloud_mqtt import (
    CloudMqttError,
    ConnectionState,
    PahoReadOnlyMqttSession,
    PahoZendureCloudMqttSession,
    ZendureCloudMqttTransport,
    _bsfai_client_id,
    _disconnect_packet_from_server,
    _function_invoke_request,
    _get_all_request,
    _parse_broker_url,
    _property_write_request,
    _reason_code_number,
    _reason_code_success,
    _safe_peer_scope,
    _safe_socket_family,
)
from custom_components.battery_smartflow_ai.hardware.zendure.cloud_mqtt_commands import (
    CloudFunctionInvocation,
    CloudPropertyWrite,
)


class Response:
    def __init__(self, data): self.data = data
    async def json(self): return self.data


async def bootstrap(devices):
    token = b64encode(b"https://api.example.com.app-key").decode()
    async def post(*_args, **_kwargs):
        return Response({"code": 200, "success": True, "data": {
            "deviceList": devices,
            "mqtt": {"clientId": "secret-client", "url": "mqtts://broker.example:8883", "username": "secret-user", "password": "secret-pass"},
        }})
    return await ZendureCloudClient(post).async_discover(token)


class FakeSession:
    def __init__(self, _credentials, *, connect_ok=True):
        self.connect_ok = connect_ok
        self.subscriptions = ()
        self.state_requests = []
        self.property_writes = []
        self.disconnected = False

    def set_callbacks(self, on_connect, on_disconnect, on_message):
        self.on_connect, self.on_disconnect, self.on_message = on_connect, on_disconnect, on_message

    def connect(self): self.on_connect(self.connect_ok, None if self.connect_ok else "not authorized")
    def subscribe(self, topics): self.subscriptions = topics
    def request_all(self, product_id, device_id, message_id, timestamp):
        self.state_requests.append((product_id, device_id, message_id, timestamp))
    def write_properties(self, product_id, device_id, writes):
        self.property_writes.append((product_id, device_id, writes))
        return True
    def disconnect(self): self.disconnected = True
    def emit(self, topic, payload, retained=False):
        self.on_message(topic, payload, retained)
    def drop(self): self.on_disconnect("network lost")


class HangingSession(FakeSession):
    def connect(self):
        return None

    def disconnect(self):
        self.disconnected = True
        raise RuntimeError("not connected")


class FailedStateRequestSession(FakeSession):
    def request_all(self, product_id, device_id, message_id, timestamp):
        raise CloudMqttError("state_request_failed")


class WildcardRejectedSession(FakeSession):
    def subscribe(self, topics):
        if topics == ("#",):
            raise CloudMqttError("subscribe_failed")
        self.subscriptions = topics


class BrokerWildcardRejectedSession(FakeSession):
    def subscribe(self, topics):
        if topics == ("#",):
            raise CloudMqttError("subscribe_rejected")
        self.subscriptions = topics


class CloudMqttTransportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.sessions = []
        self.now = datetime(2026, 9, 2, 10, 0, tzinfo=timezone.utc)
        self.data = await bootstrap([
            {"deviceKey": "main-1", "productKey": "product-a", "productModel": "SolarFlow2400AC", "deviceName": "One", "online": True, "packNum": 2},
            {"deviceKey": "main-2", "productKey": "product-b", "productModel": "Unknown Future", "deviceName": "Two"},
        ])

    def factory(self, credentials):
        session = FakeSession(credentials)
        self.sessions.append(session)
        return session

    async def test_assigned_identity_is_limited_to_selected_cloud_mode(self):
        cloud = ZendureCloudMqttTransport(self.data)
        observer = ZendureCloudMqttTransport(
            self.data,
            use_assigned_client_id=False,
        )

        self.assertIs(cloud._session_factory, PahoZendureCloudMqttSession)
        self.assertIs(observer._session_factory, PahoReadOnlyMqttSession)

    async def test_connects_and_subscribes_all_devices(self):
        transport = ZendureCloudMqttTransport(
            self.data,
            session_factory=self.factory,
            clock=lambda: self.now,
        )
        await transport.async_start()
        self.assertEqual(transport.state, ConnectionState.CONNECTED)
        self.assertEqual(
            self.sessions[0].subscriptions,
            ("#",),
        )
        self.assertEqual(
            [(product, device) for product, device, _message, _timestamp in self.sessions[0].state_requests],
            [("product-a", "main-1"), ("product-b", "main-2")],
        )
        self.assertEqual(
            [message for _product, _device, message, _timestamp in self.sessions[0].state_requests],
            [1, 2],
        )
        self.assertTrue(
            all(
                timestamp == int(self.now.timestamp())
                for _product, _device, _message, timestamp
                in self.sessions[0].state_requests
            )
        )
        await transport.async_stop()
        self.assertTrue(self.sessions[0].disconnected)

    async def test_wildcard_rejection_falls_back_to_device_topics(self):
        sessions = []
        transport = ZendureCloudMqttTransport(
            self.data,
            session_factory=lambda credentials: (
                sessions.append(WildcardRejectedSession(credentials)) or sessions[-1]
            ),
            clock=lambda: self.now,
        )
        await transport.async_start()
        self.assertEqual(transport.state, ConnectionState.CONNECTED)
        self.assertEqual(
            sessions[0].subscriptions,
            (
                "/product-a/main-1/#",
                "/product-b/main-2/#",
                "iot/product-a/main-1/#",
                "iot/product-b/main-2/#",
            ),
        )
        await transport.async_stop()

    async def test_broker_suback_rejection_falls_back_to_device_topics(self):
        sessions = []
        transport = ZendureCloudMqttTransport(
            self.data,
            session_factory=lambda credentials: (
                sessions.append(BrokerWildcardRejectedSession(credentials))
                or sessions[-1]
            ),
            clock=lambda: self.now,
        )
        await transport.async_start()
        self.assertEqual(transport.state, ConnectionState.CONNECTED)
        self.assertEqual(
            sessions[0].subscriptions,
            (
                "/product-a/main-1/#",
                "/product-b/main-2/#",
                "iot/product-a/main-1/#",
                "iot/product-b/main-2/#",
            ),
        )
        await transport.async_stop()

    def test_paho_suback_acceptance_and_rejection(self):
        session = object.__new__(PahoReadOnlyMqttSession)
        session._subscription_condition = threading.Condition()
        session._subscription_results = {}
        session._subscription_ack_count = 0
        session._subscription_rejected_count = 0
        session._subscription_status = "not_requested"
        session._connection_phase = "mqtt_connack_accepted"
        session._tls = False
        session._endpoint_scope = "unknown"
        session._socket_family = "unknown"
        session._connect_packet_sent = False
        session._last_disconnect_packet_from_server = None
        session._last_disconnect_reason_code = None
        session._client = SimpleNamespace(subscribe=lambda _topic, qos: (0, 17))

        def granted(_topic, qos):
            session._paho_subscribe(None, None, 17, [0], None)
            return (0, 17)

        session._client.subscribe = granted
        session.subscribe(("#",))
        self.assertEqual(session.connection_diagnostics["subscription_status"], "accepted")

        def rejected(_topic, qos):
            session._paho_subscribe(None, None, 18, [128], None)
            return (0, 18)

        session._client.subscribe = rejected
        with self.assertRaisesRegex(CloudMqttError, "subscribe_rejected"):
            session.subscribe(("#",))
        self.assertEqual(session.connection_diagnostics["subscription_rejected_count"], 1)

    def test_paho_suback_timeout_is_classified(self):
        session = object.__new__(PahoReadOnlyMqttSession)
        session._subscription_condition = threading.Condition()
        session._subscription_results = {}
        session._subscription_ack_count = 0
        session._subscription_rejected_count = 0
        session._subscription_status = "not_requested"
        session._connection_phase = "mqtt_connack_accepted"
        session._tls = False
        session._endpoint_scope = "unknown"
        session._socket_family = "unknown"
        session._connect_packet_sent = False
        session._last_disconnect_packet_from_server = None
        session._last_disconnect_reason_code = None
        session._client = SimpleNamespace(subscribe=lambda _topic, qos: (0, 17))
        with (
            patch(
                "custom_components.battery_smartflow_ai.hardware.zendure.cloud_mqtt._SUBSCRIPTION_ACK_TIMEOUT_SECONDS",
                0.01,
            ),
            self.assertRaisesRegex(CloudMqttError, "subscribe_timeout"),
        ):
            session.subscribe(("#",))
        self.assertEqual(session.connection_diagnostics["subscription_status"], "ack_timeout")

    async def test_initial_incremental_unknown_and_invalid_payloads_are_retained(self):
        transport = ZendureCloudMqttTransport(self.data, session_factory=self.factory, clock=lambda: self.now)
        await transport.async_start()
        session = self.sessions[0]
        session.emit("/product-a/main-1/properties/report", json.dumps({"properties": {"socLevel": 55, "solarInputPower": 800}}).encode())
        session.emit(
            "/product-a/main-1/state",
            json.dumps({"hyperTmp": 311, "sn": "main-1"}).encode(),
        )
        session.emit("/product-a/main-1/new/future/topic", b'{broken')
        session.emit("/product-b/main-2/state", b"\xff\x00")
        await asyncio.sleep(0)
        messages = transport.messages
        self.assertEqual(
            [item.payload_format for item in messages],
            ["json", "json", "text", "binary"],
        )
        self.assertTrue(messages[0].known_topic)
        self.assertTrue(messages[1].known_topic)
        self.assertFalse(messages[2].known_topic)
        self.assertEqual(messages[0].device_candidate_id, "cloud_mqtt:main-1")
        state = transport.device_states["cloud_mqtt:main-1"]
        self.assertEqual(state.last_message_at, self.now)
        self.assertEqual(
            set(state.property_updated_at),
            {"socLevel", "solarInputPower", "hyperTmp"},
        )

    async def test_legacy_bridge_copy_is_not_counted_as_cloud_observation(self):
        transport = ZendureCloudMqttTransport(
            self.data, session_factory=self.factory, clock=lambda: self.now
        )
        await transport.async_start()
        self.sessions[0].emit(
            "/product-a/main-1/properties/report",
            json.dumps({"properties": {"socLevel": 55}, "isHA": True}).encode(),
        )
        await asyncio.sleep(0)
        self.assertEqual(transport.messages, ())
        self.assertIsNone(
            transport.device_states["cloud_mqtt:main-1"].last_message_at
        )

    async def test_command_echo_is_retained_but_never_refreshes_device_state(self):
        transport = ZendureCloudMqttTransport(
            self.data, session_factory=self.factory, clock=lambda: self.now
        )
        await transport.async_start()
        self.sessions[0].emit(
            "iot/product-a/main-1/properties/write",
            json.dumps({"properties": {"minSoc": 100, "socSet": 1000}}).encode(),
        )
        await asyncio.sleep(0)
        self.assertEqual(len(transport.messages), 1)
        self.assertFalse(transport.messages[0].known_topic)
        self.assertIsNone(transport.last_message_at)
        state = transport.device_states["cloud_mqtt:main-1"]
        self.assertIsNone(state.last_message_at)
        self.assertEqual(state.property_updated_at, {})
        await transport.async_stop()

    async def test_routes_pack_and_payload_device_identity(self):
        transport = ZendureCloudMqttTransport(self.data, session_factory=self.factory)
        await transport.async_start()
        self.sessions[0].emit("/account/events", json.dumps({"deviceKey": "main-1", "packId": "pack-77", "properties": {"socLevel": 44}}).encode())
        await asyncio.sleep(0)
        message = transport.messages[0]
        self.assertEqual(message.device_candidate_id, "cloud_mqtt:main-1")
        self.assertEqual(message.pack_id, "pack-77")

    async def test_mqtt_retained_flag_is_preserved_on_message(self):
        transport = ZendureCloudMqttTransport(
            self.data,
            session_factory=self.factory,
            clock=lambda: self.now,
        )
        await transport.async_start()
        self.sessions[0].emit(
            "/product-a/main-1/properties/report",
            json.dumps({"properties": {"socLevel": 55}}).encode(),
            retained=True,
        )
        await asyncio.sleep(0)
        self.assertTrue(transport.messages[0].retained)

    async def test_properties_energy_is_known_and_routed_per_device(self):
        transport = ZendureCloudMqttTransport(
            self.data,
            session_factory=self.factory,
            clock=lambda: self.now,
        )
        await transport.async_start()
        self.sessions[0].emit(
            "/product-a/main-1/properties/energy",
            json.dumps({"properties": {"gridPower": 120}}).encode(),
        )
        await asyncio.sleep(0)
        message = transport.messages[0]
        self.assertTrue(message.known_topic)
        self.assertEqual(message.device_candidate_id, "cloud_mqtt:main-1")
        self.assertTrue(message.topic.endswith("/properties/energy"))

    async def test_disconnect_reconnects_without_commands(self):
        transport = ZendureCloudMqttTransport(self.data, session_factory=self.factory, reconnect_delays=(0.0,))
        await transport.async_start()
        self.sessions[0].drop()
        for _attempt in range(20):
            if (
                len(self.sessions) >= 2
                and transport.state is ConnectionState.CONNECTED
            ):
                break
            await asyncio.sleep(0.01)
        self.assertGreaterEqual(len(self.sessions), 2)
        self.assertEqual(transport.state, ConnectionState.CONNECTED)
        self.assertFalse(hasattr(transport, "publish"))
        self.assertFalse(hasattr(transport, "command"))
        public = {name for name, _ in inspect.getmembers(type(transport), inspect.isfunction) if not name.startswith("_")}
        self.assertEqual(
            public,
            {
                "async_execute_authorized",
                "async_start",
                "async_stop",
            },
        )
        self.assertEqual(len(self.sessions[0].state_requests), 2)
        self.assertEqual(len(self.sessions[1].state_requests), 2)
        diagnostics = transport.connection_diagnostics
        self.assertEqual(diagnostics["disconnect_count"], 1)


        self.assertEqual(diagnostics["reconnect_count"], 1)
        self.assertEqual(
            diagnostics["last_disconnect_category"],
            "network_or_transport_error",
        )

    async def test_paho_managed_reconnect_does_not_create_competing_session(self):
        transport = ZendureCloudMqttTransport(
            self.data,
            session_factory=self.factory,
            reconnect_delays=(0.0,),
        )
        await transport.async_start()
        session = self.sessions[0]
        session.manages_reconnect = True

        with self.assertLogs(
            "custom_components.battery_smartflow_ai.hardware.zendure.cloud_mqtt",
            level="WARNING",
        ) as logs:
            session.drop()
            session.on_disconnect("network lost")
            await asyncio.sleep(0)

        self.assertEqual(len(self.sessions), 1)
        self.assertEqual(transport.state, ConnectionState.RECONNECTING)
        self.assertEqual(len(logs.output), 1)
        session.on_connect(True, None)
        for _attempt in range(20):
            if transport.state is ConnectionState.CONNECTED:
                break
            await asyncio.sleep(0.01)
        self.assertEqual(transport.state, ConnectionState.CONNECTED)
        diagnostics = transport.connection_diagnostics
        self.assertEqual(diagnostics["disconnect_count"], 1)
        self.assertEqual(diagnostics["reconnect_count"], 1)
        await transport.async_stop()

    async def test_credentials_do_not_appear_in_logs_or_representations(self):
        transport = ZendureCloudMqttTransport(self.data, session_factory=self.factory)
        with self.assertLogs("custom_components.battery_smartflow_ai.hardware.zendure.cloud_mqtt", level="INFO") as logs:
            await transport.async_start()
        text = " ".join(logs.output) + repr(transport) + repr(self.data)
        for secret in ("secret-client", "secret-user", "secret-pass", "broker.example"):
            self.assertNotIn(secret, text)

    async def test_disconnect_reason_is_sanitized(self):
        transport = ZendureCloudMqttTransport(self.data, session_factory=self.factory, reconnect_delays=(10.0,))
        await transport.async_start()
        with self.assertLogs("custom_components.battery_smartflow_ai.hardware.zendure.cloud_mqtt", level="WARNING") as logs:
            self.sessions[0].on_disconnect("username=secret-user password=secret-pass mqtts://broker.example:8883")
            await asyncio.sleep(0)
        text = " ".join(logs.output)
        for secret in ("secret-user", "secret-pass", "broker.example"):
            self.assertNotIn(secret, text)
        diagnostics = transport.connection_diagnostics
        self.assertEqual(diagnostics["disconnect_count"], 1)
        self.assertEqual(
            diagnostics["last_disconnect_category"],
            "unclassified",
        )
        self.assertNotIn("secret-user", repr(diagnostics))
        await transport.async_stop()

    def test_paho_disconnect_captures_only_safe_reason_facts(self):
        session = object.__new__(PahoReadOnlyMqttSession)
        session._tls = False
        session._endpoint_scope = "public"
        session._socket_family = "ipv4"
        session._connect_packet_sent = True
        session._last_disconnect_packet_from_server = None
        session._last_disconnect_reason_code = None
        disconnect_reasons = []
        session._on_disconnect = disconnect_reasons.append

        session._paho_disconnect(
            None,
            None,
            SimpleNamespace(is_disconnect_packet_from_server=True),
            SimpleNamespace(value=128),
            None,
        )

        diagnostics = session.connection_diagnostics
        self.assertIs(diagnostics["last_disconnect_packet_from_server"], True)
        self.assertEqual(diagnostics["last_disconnect_reason_code"], 128)
        self.assertIn("reason_code=128", disconnect_reasons[0])
        self.assertIn("disconnect_packet_from_server=True", disconnect_reasons[0])
        self.assertIsNone(_disconnect_packet_from_server(SimpleNamespace()))
        self.assertIsNone(_reason_code_number("Unspecified error"))

    async def test_no_routable_device_is_rejected(self):
        data = await bootstrap([{"snNumber": "serial-only", "productModel": "SolarFlow2400AC"}])
        transport = ZendureCloudMqttTransport(data, session_factory=self.factory)
        with self.assertRaisesRegex(Exception, "no_routable_devices"):
            await transport.async_start()

    async def test_state_request_failure_is_classified(self):
        transport = ZendureCloudMqttTransport(
            self.data,
            session_factory=lambda credentials: FailedStateRequestSession(
                credentials
            ),
        )

        with self.assertRaisesRegex(CloudMqttError, "state_request_failed"):
            await transport.async_start()

        self.assertEqual(transport.state, ConnectionState.STOPPED)

    async def test_cleanup_failure_does_not_mask_connection_timeout(self):
        session = HangingSession(None)
        transport = ZendureCloudMqttTransport(
            self.data,
            session_factory=lambda _credentials: session,
        )
        with self.assertRaisesRegex(Exception, "connection_timeout"):
            await transport.async_start(timeout=0.01)
        self.assertEqual(transport.state, ConnectionState.STOPPED)
        self.assertTrue(session.disconnected)
        self.assertEqual(transport.connection_variant, "mqtt31_persistent")

    async def test_connection_phase_is_retained_after_timeout_cleanup(self):
        class PhasedHangingSession(HangingSession):
            connection_phase = "tcp_connected_waiting_for_mqtt_connack"

        transport = ZendureCloudMqttTransport(
            self.data,
            session_factory=lambda _credentials: PhasedHangingSession(None),
        )
        with self.assertRaisesRegex(Exception, "connection_timeout"):
            await transport.async_start(timeout=0.01)
        self.assertEqual(
            transport.connection_phase,
            "tcp_connected_waiting_for_mqtt_connack",
        )

    def test_schema_free_port_1883_is_plain_mqtt(self):
        self.assertEqual(
            _parse_broker_url("broker.example:1883"),
            ("broker.example", 1883, False),
        )

    def test_tls_requires_an_explicit_secure_scheme(self):
        self.assertEqual(
            _parse_broker_url("mqtts://broker.example:8883"),
            ("broker.example", 8883, True),
        )
        self.assertEqual(
            _parse_broker_url("mqtt://broker.example:1883"),
            ("broker.example", 1883, False),
        )

    def test_paho_uses_zendure_ha_mqtt_31_persistent_session(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "custom_components"
            / "battery_smartflow_ai"
            / "hardware" / "zendure" / "cloud_mqtt.py"
        ).read_text(encoding="utf-8")
        self.assertIn("protocol=mqtt.MQTTv31", source)
        self.assertIn("clean_session=False", source)
        self.assertIn("connect_async", source)

    def test_socket_metadata_is_classified_without_retaining_addresses(self):
        class FakeSocket:
            family = socket.AF_INET

            def getpeername(self):
                return ("192.168.10.20", 1883)

        mqtt_socket = FakeSocket()
        self.assertEqual(_safe_socket_family(mqtt_socket), "ipv4")
        self.assertEqual(_safe_peer_scope(mqtt_socket), "private")
        self.assertNotIn("192.168.10.20", repr(_safe_peer_scope(mqtt_socket)))

    def test_public_and_loopback_peers_are_distinguished(self):
        class FakeSocket:
            family = socket.AF_INET6

            def __init__(self, address):
                self.address = address

            def getpeername(self):
                return (self.address, 1883, 0, 0)

        self.assertEqual(_safe_peer_scope(FakeSocket("2606:4700:4700::1111")), "public")
        self.assertEqual(_safe_peer_scope(FakeSocket("::1")), "loopback")

    def test_paho_reason_code_objects_do_not_require_integer_conversion(self):
        class ReasonCode:
            def __init__(self, *, is_failure, value):
                self.is_failure = is_failure
                self.value = value

            def __int__(self):
                raise TypeError("ReasonCode is not directly integer-convertible")

            def __str__(self):
                return "Success" if not self.is_failure else "Not authorized"

        self.assertTrue(_reason_code_success(ReasonCode(is_failure=False, value=0)))
        self.assertFalse(_reason_code_success(ReasonCode(is_failure=True, value=135)))
        self.assertTrue(_reason_code_success(0))
        self.assertFalse(_reason_code_success(5))

    def test_bsfai_uses_a_stable_private_mqtt31_client_identity(self):
        first = _bsfai_client_id("zendure-cloud-client-secret")
        second = _bsfai_client_id("zendure-cloud-client-secret")

        self.assertEqual(first, second)
        self.assertTrue(first.startswith("bsfai-"))
        self.assertLessEqual(len(first), 23)
        self.assertNotIn("zendure-cloud-client-secret", first)
        self.assertNotEqual(first, "zendure-cloud-client-secret")
        self.assertNotEqual(
            first,
            _bsfai_client_id("another-zendure-cloud-client"),
        )

    def test_zendure_cloud_uses_the_assigned_client_identity(self):
        credentials = type(
            "Credentials", (), {"client_id": "zendure-assigned-client"}
        )()

        self.assertEqual(
            PahoZendureCloudMqttSession._client_id(credentials),
            "zendure-assigned-client",
        )
        self.assertNotEqual(
            PahoReadOnlyMqttSession._client_id(credentials),
            "zendure-assigned-client",
        )

    def test_get_all_request_has_no_arbitrary_write_surface(self):
        topic, payload = _get_all_request(
            "product-a", "main-1", 7, 1788444000
        )

        self.assertEqual(topic, "iot/product-a/main-1/properties/read")
        self.assertEqual(
            json.loads(payload),
            {
                "properties": ["getAll"],
                "messageId": 7,
                "deviceId": "main-1",
                "timestamp": 1788444000,
            },
        )
        self.assertNotIn("properties/write", topic)
        self.assertNotIn("function/invoke", topic)

    def test_typed_property_write_has_confirmed_topic_and_envelope(self):
        topic, payload = _property_write_request(
            "product-a",
            "main-1",
            (
                CloudPropertyWrite("smartMode", 1, 8, 1788444001),
                CloudPropertyWrite("acMode", 2, 9, 1788444001),
                CloudPropertyWrite("outputLimit", 500, 10, 1788444001),
                CloudPropertyWrite("inputLimit", 0, 11, 1788444001),
            ),
        )
        self.assertEqual(topic, "iot/product-a/main-1/properties/write")
        self.assertEqual(json.loads(payload), {
            "properties": {
                "smartMode": 1,
                "acMode": 2,
                "outputLimit": 500,
                "inputLimit": 0,
            }, "messageId": 8,
            "deviceId": "main-1", "timestamp": 1788444001,
        })


class CloudMqttFunctionInvokeTests(unittest.TestCase):
    def test_serializes_hyper_device_automation_object_invoke(self):
        topic, payload = _function_invoke_request(
            "product-a",
            "device-a",
            CloudFunctionInvocation(
                "deviceAutomation",
                ({
                    "autoModelProgram": 2,
                    "autoModelValue": {
                        "chargingType": 0,
                        "chargingPower": 0,
                        "freq": 0,
                        "outPower": 250,
                    },
                    "msgType": 1,
                    "autoModel": 8,
                },),
                {"outputLimit": 250.0},
                include_device_key=True,
            ),
            17,
            100,
        )
        self.assertEqual(topic, "iot/product-a/device-a/function/invoke")
        self.assertEqual(
            json.loads(payload),
            {
                "function": "deviceAutomation",
                "arguments": [{
                    "autoModelProgram": 2,
                    "autoModelValue": {
                        "chargingType": 0,
                        "chargingPower": 0,
                        "freq": 0,
                        "outPower": 250,
                    },
                    "msgType": 1,
                    "autoModel": 8,
                }],
                "messageId": 17,
                "deviceId": "device-a",
                "deviceKey": "device-a",
                "timestamp": 100,
            },
        )

    def test_rejects_unapproved_function_and_argument_shape(self):
        with self.assertRaisesRegex(CloudMqttError, "unsupported_function"):
            _function_invoke_request(
                "product-a",
                "device-a",
                CloudFunctionInvocation("arbitrary", {}, {}),
                1,
                100,
            )
        with self.assertRaisesRegex(CloudMqttError, "invalid_legacy_arguments"):
            _function_invoke_request(
                "product-a",
                "device-a",
                CloudFunctionInvocation(
                    "deviceAutomation",
                    ({"anything": 1},),
                    {},
                ),
                1,
                100,
            )


if __name__ == "__main__":
    unittest.main()
