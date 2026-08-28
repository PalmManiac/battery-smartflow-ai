"""Issue #277 proof for removed runtime fallbacks and preserved migration."""

from __future__ import annotations

import ast
import unittest

from support import PACKAGE_ROOT, bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.device_profiles import (  # noqa: E402
    DEVICE_PROFILES,
    PROFILE_MIGRATION_OVERRIDE_FIELDS,
)


LEGACY_REGULATION_KEYS = {
    "DEADBAND_W",
    "KP_UP",
    "KP_DOWN",
    "MAX_STEP_UP",
    "MAX_STEP_DOWN",
}

DIRECTIONAL_REGULATION_KEYS = {
    "CHARGE_DEADBAND_W",
    "CHARGE_KP_UP",
    "CHARGE_KP_DOWN",
    "CHARGE_MAX_STEP_UP",
    "CHARGE_MAX_STEP_DOWN",
    "DISCHARGE_DEADBAND_W",
    "DISCHARGE_KP_UP",
    "DISCHARGE_KP_DOWN",
    "DISCHARGE_MAX_STEP_UP",
    "DISCHARGE_MAX_STEP_DOWN",
}


class LegacyCleanupV470Tests(unittest.TestCase):
    def test_every_profile_has_complete_directional_regulation(self) -> None:
        for name, profile in DEVICE_PROFILES.items():
            with self.subTest(profile=name):
                self.assertTrue(DIRECTIONAL_REGULATION_KEYS.issubset(profile))

    def test_legacy_regulation_keys_are_migration_only(self) -> None:
        self.assertEqual(PROFILE_MIGRATION_OVERRIDE_FIELDS, LEGACY_REGULATION_KEYS)
        for module_name in (
            "decision_engine.py",
            "power_controller.py",
            "regulation_power_controller.py",
            "grid_history.py",
        ):
            source = (PACKAGE_ROOT / module_name).read_text(encoding="utf-8")
            if module_name == "decision_engine.py":
                self.assertNotIn('profile.get("DEADBAND_W"', source)
            else:
                for key in LEGACY_REGULATION_KEYS:
                    self.assertNotIn(f'"{key}"', source, module_name)

    def test_removed_dead_helpers_do_not_return(self) -> None:
        expectations = {
            "decision_engine.py": {
                "_low_soc_discharge_requires_cell_resume",
                "_pv_surplus_should_prefer_pv_charge",
                "_profile_for_discharge",
                "_profile_for_charge",
            },
            "device_profiles.py": {"get_profile_defaults"},
        }
        for module_name, removed in expectations.items():
            tree = ast.parse(
                (PACKAGE_ROOT / module_name).read_text(encoding="utf-8")
            )
            definitions = {
                node.name
                for node in ast.walk(tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
            self.assertTrue(removed.isdisjoint(definitions), module_name)


if __name__ == "__main__":
    unittest.main()
