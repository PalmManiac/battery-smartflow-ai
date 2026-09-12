"""Configuration contract for Energy dashboard compatible forecasts."""

import ast
from pathlib import Path
from typing import Any
import unittest

from support import bootstrap

bootstrap()

from custom_components.battery_smartflow_ai import const  # noqa: E402


ROOT = Path(__file__).parents[1]
COMPONENT = ROOT / "custom_components" / "battery_smartflow_ai"


class EnergyForecastConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = COMPONENT / "config_flow.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        wanted = {
            "_normalize_forecast_entries",
            "_apply_forecast_selection",
        }
        nodes = [
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name in wanted
        ]
        namespace = {**vars(const), "Any": Any}
        exec(compile(ast.Module(nodes, type_ignores=[]), str(path), "exec"), namespace)
        cls.apply_selection = staticmethod(namespace["_apply_forecast_selection"])

    def test_config_uses_energy_provider_multiselect_not_daily_entities(self):
        source = (COMPONENT / "config_flow.py").read_text(encoding="utf-8")
        self.assertIn("async_energy_forecast_sources", source)
        self.assertIn("CONF_PV_FORECAST_CONFIG_ENTRIES", source)
        self.assertIn("multiple=True", source)
        self.assertNotIn("vol.Optional(CONF_PV_FORECAST_TODAY_ENTITY)", source)
        self.assertNotIn("vol.Optional(CONF_PV_FORECAST_TOMORROW_ENTITY)", source)

    def test_runtime_prefers_energy_api_and_keeps_legacy_fallback(self):
        source = (COMPONENT / "forecast.py").read_text(encoding="utf-8")
        self.assertIn("async_get_energy_platforms", source)
        self.assertIn('forecast.get("wh_hours")', source)
        self.assertIn("return build_forecast_summary(", source)

    def test_rc_version_is_consistent(self):
        const = (COMPONENT / "const.py").read_text(encoding="utf-8")
        manifest = (COMPONENT / "manifest.json").read_text(encoding="utf-8")
        self.assertIn('INTEGRATION_VERSION = "5.0.0-rc09"', const)
        self.assertIn('"version": "5.0.0-rc09"', manifest)
        self.assertIn('"after_dependencies": ["energy"]', manifest)
        self.assertLess(
            manifest.index('"after_dependencies"'), manifest.index('"codeowners"')
        )

    def test_untouched_legacy_forecast_sensors_remain_compatible(self):
        data = {
            const.CONF_PV_FORECAST_TODAY_ENTITY: "sensor.today",
            const.CONF_PV_FORECAST_TOMORROW_ENTITY: "sensor.tomorrow",
        }
        self.apply_selection(data)
        self.assertEqual(data[const.CONF_PV_FORECAST_TODAY_ENTITY], "sensor.today")
        self.assertEqual(
            data[const.CONF_PV_FORECAST_TOMORROW_ENTITY], "sensor.tomorrow"
        )

    def test_energy_selection_replaces_legacy_sensors_and_deduplicates(self):
        data = {
            const.CONF_PV_FORECAST_TODAY_ENTITY: "sensor.today",
            const.CONF_PV_FORECAST_TOMORROW_ENTITY: "sensor.tomorrow",
            const.CONF_PV_FORECAST_CONFIG_ENTRIES: ["east", "west", "east"],
        }
        self.apply_selection(data)
        self.assertEqual(
            data[const.CONF_PV_FORECAST_CONFIG_ENTRIES], ["east", "west"]
        )
        self.assertNotIn(const.CONF_PV_FORECAST_TODAY_ENTITY, data)
        self.assertNotIn(const.CONF_PV_FORECAST_TOMORROW_ENTITY, data)


if __name__ == "__main__":
    unittest.main()
