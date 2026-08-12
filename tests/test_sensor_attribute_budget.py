"""Guard the V4.4.0 Home Assistant Recorder attribute budget."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SENSOR = ROOT / "custom_components" / "battery_smartflow_ai" / "sensor.py"


class SensorAttributeBudgetTests(unittest.TestCase):
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
