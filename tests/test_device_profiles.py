"""Regression tests for the SolarFlow Mix profiles added in Beta2."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.device_profiles import (  # noqa: E402
    DEVICE_PROFILES,
    SF2400AC_PROFILE,
)


ROOT = Path(__file__).resolve().parents[1]
NUMBER_SOURCE = (
    ROOT / "custom_components" / "battery_smartflow_ai" / "number.py"
)


EXPECTED_MIX_LIMITS = {
    "SF3000MixAC+": 3000.0,
    "SF4000MixAC+": 4000.0,
    "SF4000MixPro": 4000.0,
}


class MixDeviceProfileTests(unittest.TestCase):
    def test_confirmed_ac_and_offgrid_limits(self) -> None:
        for profile_key, ac_limit_w in EXPECTED_MIX_LIMITS.items():
            with self.subTest(profile=profile_key):
                profile = DEVICE_PROFILES[profile_key]
                self.assertEqual(profile["MAX_INPUT_W"], ac_limit_w)
                self.assertEqual(profile["MAX_OUTPUT_W"], ac_limit_w)
                self.assertEqual(profile["OFFGRID_MAX_INTERNAL_SUPPLY_W"], 3680.0)
                self.assertTrue(profile["SUPPORTS_OFFGRID_SOCKET"])
                self.assertTrue(profile["SUPPORTS_OFFGRID_INPUT"])

    def test_mix_models_use_neutral_ac_coupled_behavior(self) -> None:
        inherited_fields = (
            "TARGET_IMPORT_W",
            "DISCHARGE_TARGET_IMPORT_W",
            "LOW_SOC_PROTECTION_STRICT",
            "LOW_SOC_PV_CHARGE_REQUIRES_EXPORT",
            "LOW_SOC_DISCHARGE_REQUIRES_CELL_RESUME",
            "PV_HOUSELOAD_PASSTHROUGH",
            "REQUIRES_STABLE_EXPORT_FOR_INPUT",
            "SUPPORTS_FAST_MODE_SWITCH",
        )

        for profile_key in EXPECTED_MIX_LIMITS:
            with self.subTest(profile=profile_key):
                profile = DEVICE_PROFILES[profile_key]
                for field in inherited_fields:
                    self.assertEqual(profile[field], SF2400AC_PROFILE[field])

    def test_power_setting_entities_allow_4000_w(self) -> None:
        tree = ast.parse(NUMBER_SOURCE.read_text(encoding="utf-8"))
        maximum_by_key: dict[str, float] = {}

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            keywords = {keyword.arg: keyword.value for keyword in node.keywords}
            key_node = keywords.get("key")
            max_node = keywords.get("native_max_value")
            if not isinstance(key_node, ast.Name) or not isinstance(
                max_node, ast.Constant
            ):
                continue
            maximum_by_key[key_node.id] = float(max_node.value)

        for setting in (
            "SETTING_MAX_CHARGE",
            "SETTING_MAX_DISCHARGE",
            "SETTING_EMERGENCY_CHARGE",
        ):
            with self.subTest(setting=setting):
                self.assertEqual(maximum_by_key[setting], 4000.0)


if __name__ == "__main__":
    unittest.main()
