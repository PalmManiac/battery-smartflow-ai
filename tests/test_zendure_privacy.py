from __future__ import annotations

from datetime import datetime, timezone
import json
import unittest

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.zendure_privacy import (  # noqa: E402
    REDACTED,
    ZendureDiagnosticSanitizer,
    sanitize_zendure_diagnostics,
)


class ZendurePrivacyTests(unittest.TestCase):
    def test_cloud_bootstrap_secrets_are_removed_recursively(self) -> None:
        source = {
            "token": "complete-app-token",
            "data": {
                "appKey": "secret-app-key",
                "mqtt": {
                    "clientId": "secret-client",
                    "username": "secret-user",
                    "password": "secret-password",
                },
            },
        }

        result = sanitize_zendure_diagnostics(source)
        encoded = json.dumps(result)

        self.assertNotIn("complete-app-token", encoded)
        self.assertNotIn("secret-app-key", encoded)
        self.assertNotIn("secret-client", encoded)
        self.assertNotIn("secret-user", encoded)
        self.assertNotIn("secret-password", encoded)
        self.assertEqual(result["token"], REDACTED)

    def test_device_pack_and_serial_aliases_are_consistent_per_export(self) -> None:
        result = sanitize_zendure_diagnostics(
            {
                "deviceKey": "device-key-123",
                "device_id": "device-key-123",
                "snNumber": "serial-main-456",
                "packData": [
                    {"packId": "pack-789", "sn": "pack-serial-789"},
                    {"pack_id": "pack-789", "sn": "pack-serial-789"},
                ],
            }
        )

        self.assertEqual(result["deviceKey"], "ZD_DEVICE_A1")
        self.assertEqual(result["device_id"], "ZD_DEVICE_A1")
        self.assertEqual(result["snNumber"], "ZD_SERIAL_A1")
        self.assertEqual(result["packData"][0]["packId"], "ZD_PACK_A1")
        self.assertEqual(result["packData"][1]["pack_id"], "ZD_PACK_A1")
        self.assertEqual(result["packData"][0]["sn"], "ZD_SERIAL_A2")
        self.assertEqual(result["packData"][1]["sn"], "ZD_SERIAL_A2")

    def test_topic_is_cleaned_even_when_identity_appears_later(self) -> None:
        result = sanitize_zendure_diagnostics(
            {
                "topic": "iot/device-key-123/properties/report",
                "payload": {"deviceKey": "device-key-123", "power": 0},
            }
        )

        self.assertEqual(
            result["topic"],
            "iot/ZD_DEVICE_A1/properties/report",
        )
        self.assertEqual(result["payload"]["power"], 0)

    def test_device_ids_used_as_mapping_keys_are_pseudonymized(self) -> None:
        result = sanitize_zendure_diagnostics(
            {
                "devices": {
                    "device-key-123": {
                        "topic": "iot/device-key-123/properties/report",
                        "power": 500,
                    }
                }
            }
        )

        self.assertIn("ZD_DEVICE_A1", result["devices"])
        self.assertNotIn("device-key-123", json.dumps(result))
        self.assertEqual(
            result["devices"]["ZD_DEVICE_A1"]["topic"],
            "iot/ZD_DEVICE_A1/properties/report",
        )

    def test_unknown_nested_credential_fields_use_same_boundary(self) -> None:
        result = sanitize_zendure_diagnostics(
            {
                "unknown": [
                    {
                        "futureCredentialBlob": "future-secret",
                        "newProperty": {"api-signature": "signed-secret"},
                    }
                ]
            }
        )

        self.assertEqual(
            result["unknown"][0]["futureCredentialBlob"],
            REDACTED,
        )
        self.assertEqual(
            result["unknown"][0]["newProperty"]["api-signature"],
            REDACTED,
        )

    def test_network_identifiers_are_not_exported(self) -> None:
        result = sanitize_zendure_diagnostics(
            {
                "apiUrl": "https://example.invalid/api",
                "url": "mqtts://broker.invalid:8883",
                "mqttUrl": "mqtts://broker.invalid:8883",
                "ip": "192.0.2.10",
                "hostname": "zendure-device-serial.local",
                "transport": "cloud_mqtt",
            }
        )

        self.assertEqual(result["apiUrl"], REDACTED)
        self.assertEqual(result["url"], REDACTED)
        self.assertEqual(result["mqttUrl"], REDACTED)
        self.assertEqual(result["ip"], REDACTED)
        self.assertEqual(result["hostname"], REDACTED)
        self.assertEqual(result["transport"], "cloud_mqtt")

    def test_network_values_embedded_in_exception_text_are_removed(self) -> None:
        result = ZendureDiagnosticSanitizer().sanitize_exception(
            RuntimeError(
                "failed at https://api.example.invalid/path via 192.0.2.10 "
                "and zendure-device.local"
            )
        )

        self.assertNotIn("api.example.invalid", result)
        self.assertNotIn("192.0.2.10", result)
        self.assertNotIn("zendure-device.local", result)

    def test_exception_path_uses_discovered_secret_and_identity_values(self) -> None:
        sanitizer = ZendureDiagnosticSanitizer()
        sanitizer.sanitize(
            {
                "username": "mqtt-user-123",
                "password": "mqtt-password-456",
                "deviceKey": "device-key-789",
            }
        )

        result = sanitizer.sanitize_exception(
            RuntimeError(
                "login failed for mqtt-user-123 / mqtt-password-456 "
                "on device-key-789"
            )
        )

        self.assertNotIn("mqtt-user-123", result)
        self.assertNotIn("mqtt-password-456", result)
        self.assertNotIn("device-key-789", result)
        self.assertIn("ZD_DEVICE_A1", result)

    def test_inline_authorization_and_assignments_are_removed(self) -> None:
        result = sanitize_zendure_diagnostics(
            {
                "error": (
                    "Authorization: Bearer abc.def "
                    "username=mqtt-user password=mqtt-pass appKey=app-secret"
                )
            }
        )["error"]

        self.assertNotIn("abc.def", result)
        self.assertNotIn("mqtt-user", result)
        self.assertNotIn("mqtt-pass", result)
        self.assertNotIn("app-secret", result)

    def test_source_is_not_mutated_and_json_values_remain_distinct(self) -> None:
        timestamp = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
        source = {
            "deviceKey": "device-key-123",
            "values": {"zero": 0, "missing": None, "online": False},
            "timestamp": timestamp,
        }

        result = sanitize_zendure_diagnostics(source)

        self.assertEqual(source["deviceKey"], "device-key-123")
        self.assertIs(source["timestamp"], timestamp)
        self.assertEqual(result["values"]["zero"], 0)
        self.assertIsNone(result["values"]["missing"])
        self.assertIs(result["values"]["online"], False)
        self.assertEqual(result["timestamp"], "2026-09-01T12:00:00Z")

    def test_alias_namespace_is_package_local(self) -> None:
        first = sanitize_zendure_diagnostics({"deviceKey": "device-one"})
        second = sanitize_zendure_diagnostics({"deviceKey": "device-two"})

        self.assertEqual(first["deviceKey"], "ZD_DEVICE_A1")
        self.assertEqual(second["deviceKey"], "ZD_DEVICE_A1")

    def test_user_defined_device_name_is_not_exported(self) -> None:
        result = ZendureDiagnosticSanitizer().sanitize(
            {"deviceName": "Thomas Garage Battery", "productModel": "SF2400AC"}
        )

        self.assertEqual(result["deviceName"], REDACTED)
        self.assertEqual(result["productModel"], "SF2400AC")


if __name__ == "__main__":
    unittest.main()
