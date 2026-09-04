"""Safety contract for the initial native Zendure device matrix."""

from __future__ import annotations

from dataclasses import replace
import unittest

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.core.models import (  # noqa: E402
    NativeDeviceIdentity,
    ZendureTransport,
)
from custom_components.battery_smartflow_ai.device_profiles import (  # noqa: E402
    DEVICE_PROFILE_MODELS,
)
from custom_components.battery_smartflow_ai.zendure_device_matrix import (  # noqa: E402
    VerificationLevel,
    ZENDURE_DEVICE_MATRIX,
    resolve_zendure_device,
)


def identity(
    *,
    model: str | None = None,
    product_id: str | None = None,
    device_id: str = "device-1",
) -> NativeDeviceIdentity:
    return NativeDeviceIdentity(
        transport=ZendureTransport.CLOUD_MQTT,
        device_id=device_id,
        product_id=product_id,
        product_model=model,
    )


class ZendureDeviceMatrixTests(unittest.TestCase):
    def test_all_initial_profiles_have_exact_model_mapping(self):
        models = {
            "SF2400AC": "SolarFlow 2400 AC",
            "SF2400Pro": "SolarFlow 2400 Pro",
            "SF2400AC+": "SolarFlow 2400 AC+",
            "SF800Pro": "SolarFlow 800 Pro",
        }
        self.assertEqual(set(ZENDURE_DEVICE_MATRIX), set(models))
        for profile_key, model in models.items():
            with self.subTest(profile=profile_key):
                entry = resolve_zendure_device(identity(model=model))
                self.assertIsNotNone(entry)
                self.assertIs(entry.profile, DEVICE_PROFILE_MODELS[profile_key])

    def test_only_confirmed_product_ids_are_mapped(self):
        self.assertEqual(
            resolve_zendure_device(identity(product_id="BC8B7F")).profile_key,
            "SF2400AC",
        )
        self.assertEqual(
            resolve_zendure_device(identity(product_id="R3mn8U")).profile_key,
            "SF800Pro",
        )
        self.assertIsNone(resolve_zendure_device(identity(product_id="guessed")))

    def test_display_name_cannot_affect_resolution(self):
        self.assertIsNone(
            resolve_zendure_device(
                identity(model="My SF800Pro in the basement")
            )
        )
        self.assertIsNone(resolve_zendure_device(identity(model="SF800Pro2")))

    def test_conflicting_verified_identity_is_rejected(self):
        self.assertIsNone(
            resolve_zendure_device(
                identity(model="SF800Pro", product_id="BC8B7F")
            )
        )

    def test_profile_is_only_hardware_limit_authority(self):
        entry = ZENDURE_DEVICE_MATRIX["SF2400AC"]
        hardware_limit = entry.profile.capabilities.max_input_w
        runtime_report = {"inputLimit": 321, "chargeMaxLimit": 654}
        self.assertEqual(
            entry.profile.capabilities.max_input_w,
            hardware_limit,
        )
        self.assertNotEqual(runtime_report["inputLimit"], hardware_limit)

    def test_only_sf2400ac_zensdk_output_limit_is_approved(self):
        approved = ZENDURE_DEVICE_MATRIX["SF2400AC"]
        self.assertTrue(approved.native_control_approved)
        self.assertIs(
            approved.transport(ZendureTransport.ZENSDK).write,
            VerificationLevel.VERIFIED,
        )
        self.assertIs(
            approved.writable_main_properties["outputLimit"],
            VerificationLevel.VERIFIED,
        )
        self.assertIs(
            approved.transport(ZendureTransport.CLOUD_MQTT).write,
            VerificationLevel.REFERENCE_ONLY,
        )
        for key, entry in ZENDURE_DEVICE_MATRIX.items():
            if key == "SF2400AC":
                continue
            with self.subTest(profile=key):
                self.assertFalse(entry.native_control_approved)
                self.assertNotIn(
                    VerificationLevel.VERIFIED,
                    entry.writable_main_properties.values(),
                )

    def test_transports_remain_separate_evidence_domains(self):
        entry = ZENDURE_DEVICE_MATRIX["SF800Pro"]
        self.assertIs(
            entry.transport(ZendureTransport.CLOUD_MQTT).read,
            VerificationLevel.VERIFIED,
        )
        self.assertIs(
            entry.transport(ZendureTransport.ZENSDK).read,
            VerificationLevel.REFERENCE_ONLY,
        )
        self.assertIs(
            entry.transport(ZendureTransport.LOCAL_MQTT).read,
            VerificationLevel.UNKNOWN,
        )

    def test_pack_observation_does_not_enable_main_system_control(self):
        entry = ZENDURE_DEVICE_MATRIX["SF2400Pro"]
        self.assertIn("soc_pct", entry.neutral_pack_targets)
        self.assertFalse(entry.native_control_approved)

    def test_gate_can_model_future_approval_without_approving_production(self):
        approved = replace(
            ZENDURE_DEVICE_MATRIX["SF800Pro"],
            native_control_approved=True,
        )
        self.assertTrue(approved.native_control_approved)
        self.assertFalse(ZENDURE_DEVICE_MATRIX["SF800Pro"].native_control_approved)


if __name__ == "__main__":
    unittest.main()
