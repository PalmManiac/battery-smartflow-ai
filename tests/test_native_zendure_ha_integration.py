"""Contracts for the installable native Zendure development test."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "battery_smartflow_ai"


class NativeZendureHomeAssistantIntegrationTests(unittest.TestCase):
    def test_dev24_version_and_mqtt_dependency_are_packaged(self) -> None:
        manifest = json.loads(
            (COMPONENT / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["version"], "5.0.0.dev24")
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


if __name__ == "__main__":
    unittest.main()
