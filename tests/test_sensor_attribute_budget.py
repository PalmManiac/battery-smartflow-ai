"""Guard the V4.4.0 Home Assistant Recorder attribute budget."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SENSOR = ROOT / "custom_components" / "battery_smartflow_ai" / "sensor.py"


class SensorAttributeBudgetTests(unittest.TestCase):
    def test_only_sparse_debug_status_diagnostics_remain_recorder_facing(self) -> None:
        source = SENSOR.read_text(encoding="utf-8")

        self.assertIn("RETIRED_DIAGNOSTIC_SENSOR_KEYS", source)
        self.assertIn("description.entity_category == EntityCategory.DIAGNOSTIC", source)
        self.assertIn("description.key not in DEBUG_STATUS_SENSOR_KEYS", source)
        self.assertIn("registry.async_remove(entity_id)", source)

        tree = ast.parse(source)
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

        descriptions = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "ZendureSensorEntityDescription"
        ]
        diagnostic_keys = {
            ast.literal_eval(key_node)
            for node in descriptions
            if any(
                keyword.arg == "entity_category"
                and ast.unparse(keyword.value) == "EntityCategory.DIAGNOSTIC"
                for keyword in node.keywords
            )
            for key_node in [
                next(keyword.value for keyword in node.keywords if keyword.arg == "key")
            ]
        }
        # V4.6 promotes charge_price_applied from a retired diagnostic to the
        # economics device while preserving its existing entity identity.
        self.assertEqual(len(diagnostic_keys), 50)
        self.assertEqual(len(diagnostic_keys - debug_keys), 45)

    def test_sensor_platform_has_no_dynamic_attribute_builders(self) -> None:
        tree = ast.parse(SENSOR.read_text(encoding="utf-8"))
        method_names = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

        self.assertFalse(
            {name for name in method_names if name.startswith("_build_") and name.endswith("_attributes")}
        )

    def test_every_coordinator_update_clears_extra_state_attributes(self) -> None:
        source = SENSOR.read_text(encoding="utf-8")

        self.assertIn("self._attr_extra_state_attributes = None", source)
        self.assertNotIn("profile_overrides\"] =", source)


if __name__ == "__main__":
    unittest.main()
