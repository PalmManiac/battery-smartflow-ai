"""Contracts for the installable native Zendure development test."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "battery_smartflow_ai"


class NativeZendureHomeAssistantIntegrationTests(unittest.TestCase):
    def test_beta1_version_and_mqtt_dependency_are_packaged(self) -> None:
        manifest = json.loads(
            (COMPONENT / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["version"], "5.0.0.beta1")
        self.assertIn("paho-mqtt==2.1.0", manifest["requirements"])

    def test_options_flow_uses_a_password_field_and_never_suggests_token(self) -> None:
        source = (COMPONENT / "config_flow.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        method = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "_native_token_schema"
        )
        text = ast.unparse(method)
        self.assertIn("TextSelectorType.PASSWORD", text)
        self.assertNotIn("add_suggested_values_to_schema", text)
        self.assertIn("STORED_APP_TOKEN_MASK", text)
        self.assertIn("disable_native_zendure_test", text)

    def test_options_flow_does_not_ask_for_a_transport(self) -> None:
        source = (COMPONENT / "config_flow.py").read_text(encoding="utf-8")
        schema = source[
            source.index("def _native_device_schema"):
            source.index("def _native_device_summary")
        ]
        self.assertNotIn("CONF_NATIVE_ZENDURE_CONTROL_TRANSPORT", schema)
        self.assertIn("CONF_NATIVE_ZENDURE_CONTROL_ENABLED", schema)

    def test_runtime_keeps_native_control_explicit_and_transport_typed(self) -> None:
        setup = (COMPONENT / "__init__.py").read_text(encoding="utf-8")
        runtime = (COMPONENT / "native_zendure_runtime.py").read_text(
            encoding="utf-8"
        )
        mqtt = (COMPONENT / "zendure_cloud_mqtt.py").read_text(encoding="utf-8")
        self.assertIn("coordinator.native_zendure.start()", setup)
        self.assertNotIn("await coordinator.native_zendure.start()", setup)
        self.assertNotIn("publish(", runtime)
        self.assertIn("SERVICE_VERIFY_NATIVE_WRITE", setup)
        self.assertIn("async_run_first_write_test", runtime)
        self.assertIn("NativeDeviceCommandGate", runtime)
        self.assertIn("async_execute_device_command", runtime)
        self.assertIn("native_runtime.control_enabled", (
            COMPONENT / "coordinator.py"
        ).read_text(encoding="utf-8"))
        self.assertNotIn("def publish", mqtt)
        self.assertIn("self._consume_captured_messages(capture.messages)", runtime)
        self.assertIn(
            "await self._async_poll_zensdk(now_monotonic=loop.time())", runtime
        )
        self.assertIn("ZENSDK_POLL_INTERVAL = 5.0", runtime)
        self.assertIn("ZENSDK_MAX_RETRY_INTERVAL = 60.0", runtime)

    def test_secret_is_not_exposed_by_sensor_or_diagnostic_surfaces(self) -> None:
        runtime = (COMPONENT / "native_zendure_runtime.py").read_text(
            encoding="utf-8"
        )
        sensor_method = runtime[runtime.index("def sensor_data"):runtime.index("def overview_attributes")]
        diagnostic_method = runtime[runtime.index("def diagnostic_data"):runtime.index("async def _async_run")]
        self.assertNotIn("_app_token", sensor_method)
        self.assertNotIn("_app_token", diagnostic_method)
        self.assertIn("ZendureDiagnosticSanitizer", diagnostic_method)

    def test_native_failure_cannot_block_legacy_first_refresh(self) -> None:
        source = (COMPONENT / "__init__.py").read_text(encoding="utf-8")
        self.assertLess(
            source.index("await coordinator.async_config_entry_first_refresh()"),
            source.index("coordinator.native_zendure.start()"),
        )

    def test_native_hardware_is_exposed_as_child_devices_not_config_inputs(self) -> None:
        sensor = (COMPONENT / "sensor.py").read_text(encoding="utf-8")
        config = (COMPONENT / "config_flow.py").read_text(encoding="utf-8")
        self.assertIn("class NativeZendureHardwareSensor", sensor)
        self.assertIn('via_device=(DOMAIN, f"native_zendure_{parent_public_id}")', sensor)
        self.assertIn("coordinator.native_zendure.hardware_overview()", sensor)
        self.assertIn("coordinator.async_add_listener", sensor)
        self.assertNotIn("native_hardware_soc_pct", config)
        self.assertNotIn("native_hardware_charge_power_w", config)

    def test_serial_is_device_metadata_but_not_part_of_entity_identity(self) -> None:
        sensor = (COMPONENT / "sensor.py").read_text(encoding="utf-8")
        entity = sensor[sensor.index("class NativeZendureHardwareSensor"):]
        self.assertIn("public_id", entity)
        self.assertIn("serial_number=item.serial_number", entity)
        self.assertNotIn("device_id", entity)
        self.assertNotIn("pack_id", entity)

    def test_pack_device_name_uses_parent_name_and_stable_position(self) -> None:
        sensor = (COMPONENT / "sensor.py").read_text(encoding="utf-8")
        self.assertIn("parent.display_name", sensor)
        self.assertIn("enumerate(parent.packs, start=1)", sensor)
        self.assertIn('"de": "Batterie-Pack"', sensor)
        self.assertNotIn("public_id[-6:]", sensor)

    def test_native_voltage_and_current_sensors_show_two_decimal_places(self) -> None:
        source = (COMPONENT / "sensor.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        descriptions = {
            next(
                keyword.value.value
                for keyword in node.keywords
                if keyword.arg == "key"
            ): node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and getattr(node.func, "id", None) == "NativeHardwareSensorDescription"
            and any(keyword.arg == "key" for keyword in node.keywords)
        }
        for key in (
            "battery_voltage_v",
            "voltage_v",
            "current_a",
            "cell_min_v",
            "cell_max_v",
        ):
            precision = next(
                keyword.value.value
                for keyword in descriptions[key].keywords
                if keyword.arg == "suggested_display_precision"
            )
            self.assertEqual(precision, 2)


if __name__ == "__main__":
    unittest.main()
