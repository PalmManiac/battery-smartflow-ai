"""Visible full-charge maintenance configuration and entity contracts."""

from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "battery_smartflow_ai"
LANGUAGES = ("de", "en", "fr", "nl")


class FullChargeMaintenanceUiTests(unittest.TestCase):
    def test_options_are_explicit_and_safe_by_default(self):
        constants = (COMPONENT / "const.py").read_text(encoding="utf-8")
        config = (COMPONENT / "config_flow.py").read_text(encoding="utf-8")
        self.assertIn("DEFAULT_FULL_CHARGE_MAINTENANCE_ENABLED = False", constants)
        self.assertIn("SETTING_FULL_CHARGE_MAINTENANCE_ENABLED", config)
        self.assertIn("SETTING_FULL_CHARGE_MAINTENANCE_INTERVAL_DAYS", config)
        self.assertIn("min=7", config)
        self.assertIn("max=90", config)

    def test_all_status_entities_are_declared(self):
        sensor = (COMPONENT / "sensor.py").read_text(encoding="utf-8")
        for key in (
            "full_charge_maintenance_state",
            "full_charge_maintenance_active",
            "full_charge_maintenance_next_recommended",
            "full_charge_maintenance_last_confirmed",
            "full_charge_maintenance_window",
            "full_charge_maintenance_block_reason",
        ):
            self.assertIn(f'key="{key}"', sensor)

    def test_translations_cover_options_and_entities(self):
        paths = [COMPONENT / "strings.json"] + [
            COMPONENT / "translations" / f"{language}.json"
            for language in LANGUAGES
        ]
        for path in paths:
            with self.subTest(path=path.name):
                data = json.loads(path.read_text(encoding="utf-8"))
                expert = data["options"]["step"]["expert"]
                self.assertIn("full_charge_maintenance_enabled", expert["data"])
                self.assertIn(
                    "full_charge_maintenance_interval_days", expert["data"]
                )
                sensors = data["entity"]["sensor"]
                for key in (
                    "full_charge_maintenance_state",
                    "full_charge_maintenance_active",
                    "full_charge_maintenance_next_recommended",
                    "full_charge_maintenance_last_confirmed",
                    "full_charge_maintenance_window",
                    "full_charge_maintenance_block_reason",
                ):
                    self.assertIn(key, sensors)


if __name__ == "__main__":
    unittest.main()
