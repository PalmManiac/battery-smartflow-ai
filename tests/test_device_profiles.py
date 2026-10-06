"""Regression tests for the SolarFlow Mix profiles added in Beta2."""

from __future__ import annotations

import ast
from dataclasses import dataclass
import importlib
from pathlib import Path
import sys
from types import SimpleNamespace
from types import ModuleType
import unittest

from support import bootstrap


bootstrap()

ha_components = ModuleType("homeassistant.components")
ha_components.__path__ = []
number_component = ModuleType("homeassistant.components.number")


@dataclass(frozen=True, kw_only=True)
class NumberEntityDescription:
    key: str
    translation_key: str
    native_min_value: float = 0.0
    native_max_value: float = 100.0
    native_step: float = 1.0
    native_unit_of_measurement: str | None = None
    suggested_display_precision: int | None = None
    mode: str | None = None
    icon: str | None = None


class NumberEntity:
    @property
    def native_max_value(self):
        return getattr(
            self,
            "_attr_native_max_value",
            self.entity_description.native_max_value,
        )


number_component.NumberEntity = NumberEntity
number_component.NumberEntityDescription = NumberEntityDescription
ha_components.number = number_component
sys.modules.setdefault("homeassistant.components", ha_components)
sys.modules.setdefault("homeassistant.components.number", number_component)

ha_helpers = ModuleType("homeassistant.helpers")
ha_helpers.__path__ = []
ha_entity_platform = ModuleType("homeassistant.helpers.entity_platform")
ha_entity_platform.AddEntitiesCallback = object
ha_entity_registry = ModuleType("homeassistant.helpers.entity_registry")
ha_entity_registry.async_get = lambda _hass: None
ha_helpers.entity_registry = ha_entity_registry
sys.modules.setdefault("homeassistant.helpers", ha_helpers)
sys.modules.setdefault("homeassistant.helpers.entity_platform", ha_entity_platform)
sys.modules.setdefault("homeassistant.helpers.entity_registry", ha_entity_registry)

from custom_components.battery_smartflow_ai.device_profiles import (  # noqa: E402
    DEVICE_PROFILE_MODELS,
    DEVICE_PROFILES,
    SF2400AC_PROFILE,
    get_device_profile,
    merge_profile_with_overrides,
    resolve_charge_limits,
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
number_module = importlib.import_module(
    "custom_components.battery_smartflow_ai.number"
)
NUMBERS = number_module.NUMBERS
ZendureSmartFlowNumber = number_module.ZendureSmartFlowNumber


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

    def test_power_setting_descriptions_cover_largest_supported_model(self) -> None:
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

    def test_charge_and_discharge_numbers_use_model_hardware_limits(self) -> None:
        descriptions = {
            description.runtime_key: description
            for description in NUMBERS
        }
        models = {
            "SF2400Pro": (2400.0, 2400.0),
            "SF800Pro": (1000.0, 800.0),
            "SF4000MixAC+": (4000.0, 4000.0),
        }

        for model, expected_limits in models.items():
            with self.subTest(model=model):
                coordinator = SimpleNamespace(
                    device_profile_key=model,
                    runtime_settings={
                        "max_charge": 4000.0,
                        "max_discharge": 4000.0,
                    },
                    price_currency=None,
                )
                entry = SimpleNamespace(entry_id="test-entry", options={})
                charge = ZendureSmartFlowNumber(
                    entry, coordinator, descriptions["max_charge"]
                )
                discharge = ZendureSmartFlowNumber(
                    entry, coordinator, descriptions["max_discharge"]
                )

                self.assertEqual(charge.native_max_value, expected_limits[0])
                self.assertEqual(discharge.native_max_value, expected_limits[1])
                self.assertEqual(charge.native_value, expected_limits[0])
                self.assertEqual(discharge.native_value, expected_limits[1])
                self.assertEqual(charge._attr_mode, "box")
                self.assertEqual(discharge._attr_mode, "box")


class PowerLimitNumberTests(unittest.IsolatedAsyncioTestCase):
    async def test_direct_value_submission_is_clamped_to_model_ceiling(self):
        coordinator = SimpleNamespace(
            device_profile_key="SF2400Pro",
            runtime_settings={"max_discharge": 1200.0},
            price_currency=None,
        )
        options_updates = []
        entry = SimpleNamespace(entry_id="test-entry", options={})
        entity = ZendureSmartFlowNumber(
            entry,
            coordinator,
            next(item for item in NUMBERS if item.runtime_key == "max_discharge"),
        )
        entity.hass = SimpleNamespace(
            config_entries=SimpleNamespace(
                async_update_entry=lambda _entry, *, options: options_updates.append(
                    options
                )
            )
        )
        entity.async_write_ha_state = lambda: None

        await entity.async_set_native_value(4000.0)

        self.assertEqual(coordinator.runtime_settings["max_discharge"], 2400.0)
        self.assertEqual(options_updates[0]["max_discharge"], 2400.0)


class TypedDeviceProfileTests(unittest.TestCase):
    def test_original_sf800_has_its_own_conservative_profile(self):
        profile = DEVICE_PROFILES["SF800"]
        pro = DEVICE_PROFILES["SF800Pro"]

        self.assertEqual(profile["label"], "Zendure SF800")
        self.assertEqual(profile["MAX_INPUT_W"], 1200.0)
        self.assertEqual(profile["MAX_OUTPUT_W"], 800.0)
        self.assertFalse(profile["LOW_SOC_PROTECTION_STRICT"])
        self.assertFalse(profile["SUPPORTS_PASSTHROUGH"])
        self.assertFalse(profile["MPPT_CLIPS_WITHOUT_OUTPUT"])
        self.assertNotEqual(
            profile["PV_HOUSELOAD_PASSTHROUGH"],
            pro["PV_HOUSELOAD_PASSTHROUGH"],
        )

    def test_sf800plus_uses_confirmed_limits_and_conservative_800w_tuning(self):
        plus = DEVICE_PROFILES["SF800Plus"]
        pro = DEVICE_PROFILES["SF800Pro"]

        self.assertEqual(plus["MAX_INPUT_W"], 1000.0)
        self.assertEqual(plus["MAX_OUTPUT_W"], 800.0)
        self.assertEqual(plus["CHARGE_KP_UP"], pro["CHARGE_KP_UP"])
        self.assertEqual(plus["DISCHARGE_KP_DOWN"], pro["DISCHARGE_KP_DOWN"])
        self.assertEqual(plus["label"], "Zendure SF800Plus")

    def test_800pro_profiles_separate_ac_inlet_and_battery_charge_limits(self):
        for key in ("SF800Pro", "SF800Pro2"):
            with self.subTest(profile=key):
                profile = DEVICE_PROFILES[key]

                self.assertEqual(profile["MAX_INPUT_W"], 1000.0)
                self.assertEqual(profile["MAX_BATTERY_CHARGE_W"], 1440.0)
                self.assertEqual(
                    profile["MAX_BATTERY_CHARGE_W_WITH_EXPANSION"],
                    2000.0,
                )
                self.assertEqual(
                    resolve_charge_limits(
                        profile,
                        configured_charge_w=2400.0,
                        battery_packs=1,
                        native_pv_w=0.0,
                        native_pv_valid=True,
                    ),
                    (1440.0, 1000.0, 1000.0),
                )
                self.assertEqual(
                    resolve_charge_limits(
                        profile,
                        configured_charge_w=800.0,
                        battery_packs=3,
                        native_pv_w=443.0,
                        native_pv_valid=True,
                    ),
                    (2000.0, 800.0, 1243.0),
                )
                self.assertEqual(
                    resolve_charge_limits(
                        profile,
                        configured_charge_w=2400.0,
                        battery_packs=3,
                        native_pv_w=1800.0,
                        native_pv_valid=True,
                    ),
                    (2000.0, 200.0, 2000.0),
                )
                self.assertEqual(
                    resolve_charge_limits(
                        profile,
                        configured_charge_w=800.0,
                        battery_packs=3,
                        native_pv_w=1800.0,
                        native_pv_valid=True,
                    ),
                    (2000.0, 200.0, 2000.0),
                )

    def test_2400_profiles_enforce_combined_battery_charge_limit(self):
        for key in ("SF2400AC+", "SF2400Pro"):
            with self.subTest(profile=key):
                profile = DEVICE_PROFILES[key]
                self.assertEqual(profile["MAX_INPUT_W"], 2400.0)
                self.assertEqual(profile["MAX_BATTERY_CHARGE_W"], 2400.0)

        self.assertEqual(
            resolve_charge_limits(
                DEVICE_PROFILES["SF2400AC+"],
                configured_charge_w=3000.0,
                battery_packs=2,
            ),
            (2400.0, 2400.0, 2400.0),
        )
        self.assertEqual(
            resolve_charge_limits(
                DEVICE_PROFILES["SF2400Pro"],
                configured_charge_w=3000.0,
                battery_packs=2,
                native_pv_w=1000.0,
                native_pv_valid=True,
            ),
            (2400.0, 1400.0, 2400.0),
        )
        self.assertEqual(
            resolve_charge_limits(
                DEVICE_PROFILES["SF2400Pro"],
                configured_charge_w=800.0,
                battery_packs=2,
                native_pv_w=1000.0,
                native_pv_valid=True,
            ),
            (2400.0, 800.0, 1800.0),
        )

    def test_other_profiles_keep_their_legacy_charge_limit_semantics(self):
        self.assertEqual(
            resolve_charge_limits(
                DEVICE_PROFILES["SF2400AC"],
                configured_charge_w=2400.0,
                battery_packs=1,
            ),
            (2400.0, 2400.0, 2400.0),
        )

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
