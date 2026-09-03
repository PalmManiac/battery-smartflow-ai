"""Contracts for the first installable native Zendure read-only test."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "battery_smartflow_ai"


class NativeZendureHomeAssistantIntegrationTests(unittest.TestCase):
    def test_dev1_version_and_mqtt_dependency_are_packaged(self) -> None:
        manifest = json.loads(
            (COMPONENT / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["version"], "5.0.0-dev4")
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
        self.assertIn("disable_native_zendure_test", text)

    def test_runtime_is_background_only_and_has_no_native_write_surface(self) -> None:
        setup = (COMPONENT / "__init__.py").read_text(encoding="utf-8")
        runtime = (COMPONENT / "native_zendure_runtime.py").read_text(
            encoding="utf-8"
        )
        mqtt = (COMPONENT / "zendure_cloud_mqtt.py").read_text(encoding="utf-8")
        self.assertIn("coordinator.native_zendure.start()", setup)
        self.assertNotIn("await coordinator.native_zendure.start()", setup)
        self.assertNotIn("publish(", runtime)
        self.assertNotIn("properties/write", runtime)
        self.assertNotIn("DeviceCommand", runtime)
        self.assertNotIn("def publish", mqtt)

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
