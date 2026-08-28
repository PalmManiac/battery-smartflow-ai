"""Regression tests for the SolarFlow Mix profiles added in Beta2."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.device_profiles import (  # noqa: E402
    DEVICE_PROFILE_MODELS,
    DEVICE_PROFILES,
    SF2400AC_PROFILE,
    get_device_profile,
    merge_profile_with_overrides,
)
from custom_components.battery_smartflow_ai.core.models import (  # noqa: E402
    DeviceCapabilities,
)
from custom_components.battery_smartflow_ai.mode_arbiter import (  # noqa: E402
    build_mode_arbiter_config,
)
from custom_components.battery_smartflow_ai.regulation_power_controller import (  # noqa: E402
    build_regulation_power_config,
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


class TypedDeviceProfileTests(unittest.TestCase):
    def test_every_typed_profile_rebuilds_the_legacy_mapping_exactly(self) -> None:
        self.assertEqual(set(DEVICE_PROFILE_MODELS), set(DEVICE_PROFILES))

        for key, legacy in DEVICE_PROFILES.items():
            with self.subTest(profile=key):
                self.assertEqual(
                    DEVICE_PROFILE_MODELS[key].as_legacy_mapping(),
                    legacy,
                )

    def test_capabilities_and_tuning_have_distinct_owners(self) -> None:
        profile = DEVICE_PROFILE_MODELS["SF800Pro"]

        self.assertEqual(profile.capabilities.max_input_w, 1000.0)
        self.assertEqual(profile.capabilities.max_output_w, 800.0)
        self.assertTrue(profile.capabilities.supports_passthrough)
        self.assertTrue(
            profile.capabilities.supports_pv_house_load_passthrough
        )
        self.assertTrue(profile.capabilities.mppt_clips_without_output)
        self.assertFalse(profile.capabilities.input_keepalive_safe)
        self.assertNotIn("MAX_INPUT_W", profile.settings)
        self.assertNotIn("SUPPORTS_PASSTHROUGH", profile.settings)
        self.assertNotIn("PV_HOUSELOAD_PASSTHROUGH", profile.settings)
        self.assertEqual(profile.settings["CHARGE_DEADBAND_W"], 35.0)
        self.assertEqual(profile.settings["DISCHARGE_KP_DOWN"], 0.75)

        with self.assertRaises(TypeError):
            profile.settings["CHARGE_DEADBAND_W"] = 999.0  # type: ignore[index]

    def test_unknown_profile_keeps_the_existing_sf2400ac_fallback(self) -> None:
        self.assertIs(
            get_device_profile("future-unknown-device"),
            DEVICE_PROFILE_MODELS["SF2400AC"],
        )

    def test_legacy_override_fields_remain_compatibility_only(self) -> None:
        merged = merge_profile_with_overrides(
            "SF2400AC",
            {
                "DEADBAND_W": 77.0,
                "CHARGE_DEADBAND_W": 44.0,
                "MAX_INPUT_W": 9999.0,
                "SUPPORTS_PASSTHROUGH": True,
            },
        )

        self.assertEqual(merged["DEADBAND_W"], 77.0)
        self.assertEqual(merged["CHARGE_DEADBAND_W"], 44.0)
        self.assertEqual(merged["MAX_INPUT_W"], 2400.0)
        self.assertFalse(merged["SUPPORTS_PASSTHROUGH"])

    def test_core_configs_prefer_typed_capabilities_over_mapping_flags(self) -> None:
        legacy = dict(DEVICE_PROFILES["SF2400AC"])
        capabilities = DeviceCapabilities(
            max_input_w=1111.0,
            max_output_w=777.0,
            supports_passthrough=True,
            supports_fast_mode_switch=False,
            supports_offgrid_socket=False,
            supports_offgrid_input=False,
            output_zero_is_neutral=False,
            input_keepalive_safe=False,
            requires_stable_export_for_input=True,
        )

        arbiter = build_mode_arbiter_config(legacy, capabilities)
        power = build_regulation_power_config(
            legacy,
            capabilities=capabilities,
        )

        self.assertTrue(arbiter.supports_passthrough)
        self.assertFalse(arbiter.supports_fast_mode_switch)
        self.assertFalse(arbiter.input_keepalive_safe)
        self.assertTrue(arbiter.requires_stable_export_for_input)
        self.assertEqual(power.max_input_w, 1111.0)
        self.assertEqual(power.max_output_w, 777.0)

    def test_partial_mapping_builder_defaults_remain_unchanged(self) -> None:
        arbiter = build_mode_arbiter_config({})
        power = build_regulation_power_config({})

        self.assertTrue(arbiter.supports_fast_mode_switch)
        self.assertTrue(arbiter.input_keepalive_safe)
        self.assertFalse(arbiter.supports_passthrough)
        self.assertEqual(power.max_input_w, 2400.0)
        self.assertEqual(power.max_output_w, 2400.0)


if __name__ == "__main__":
    unittest.main()
