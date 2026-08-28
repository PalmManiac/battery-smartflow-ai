"""Issue #278 contracts for safe, compatible HA diagnostics."""

from __future__ import annotations

import ast
import unittest

from support import PACKAGE_ROOT, bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.diagnostic_values import (  # noqa: E402
    safe_diagnostic_sensor_value,
)


class SensorDiagnosticsV470Tests(unittest.TestCase):
    def test_debug_status_surface_stays_bounded(self) -> None:
        tree = ast.parse(
            (PACKAGE_ROOT / "sensor.py").read_text(encoding="utf-8")
        )
        debug_keys = next(
            ast.literal_eval(node.value.args[0])
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name)
                and target.id == "DEBUG_STATUS_SENSOR_KEYS"
                for target in node.targets
            )
            and isinstance(node.value, ast.Call)
        )
        self.assertEqual(
            debug_keys,
            {
                "debug_recording_active",
                "debug_recording_ends_at",
                "debug_sample_count",
                "debug_last_package",
                "debug_last_error",
            },
        )
        source = ast.unparse(tree)
        self.assertIn("description.key not in DEBUG_STATUS_SENSOR_KEYS", source)

    def test_package_sensor_never_exposes_local_path(self) -> None:
        path = r"C:\private\home-assistant\battery_smartflow_ai_debug\report.json"
        self.assertEqual(
            safe_diagnostic_sensor_value("debug_last_package", path),
            "report.json",
        )

    def test_error_sensor_uses_debug_secret_redaction(self) -> None:
        result = safe_diagnostic_sensor_value(
            "debug_last_error",
            "request failed authorization=Bearer abc123 password=hunter2",
        )
        self.assertNotIn("abc123", str(result))
        self.assertNotIn("hunter2", str(result))
        self.assertIn("[REDACTED]", str(result))

    def test_sensor_unique_id_formula_is_unchanged(self) -> None:
        source = (PACKAGE_ROOT / "sensor.py").read_text(encoding="utf-8")
        self.assertIn(
            'f"{DOMAIN}_{entry.entry_id}_{description.key}"',
            source,
        )

    def test_core_models_have_no_ha_sensor_surface(self) -> None:
        forbidden = {
            "SensorEntityDescription",
            "SensorDeviceClass",
            "SensorStateClass",
            "EntityCategory",
            "translation_key",
            "entity_id",
        }
        for path in (PACKAGE_ROOT / "core").rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            self.assertTrue(forbidden.isdisjoint(source.split()), str(path))


if __name__ == "__main__":
    unittest.main()
