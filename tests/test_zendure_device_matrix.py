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
    preferred_local_transport,
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
    def test_known_current_generation_models_prefer_zensdk_automatically(self):
        for entry in (
            ZENDURE_DEVICE_MATRIX[key]
            for key in ("SF2400AC", "SF2400Pro", "SF2400AC+", "SF800Pro")
        ):
            with self.subTest(profile=entry.profile_key):
                self.assertIs(
                    preferred_local_transport(
                        identity(model=entry.canonical_model)
                    ),
                    ZendureTransport.ZENSDK,
                )

    def test_unknown_model_has_no_guessed_local_transport(self):
        self.assertIsNone(
            preferred_local_transport(identity(model="SolarFlow future model"))
        )

    def test_all_initial_profiles_have_exact_model_mapping(self):
        models = {
            "SF2400AC": "SolarFlow 2400 AC",
            "SF2400Pro": "SolarFlow 2400 Pro",
            "SF2400AC+": "SolarFlow 2400 AC+",
            "SF800Pro": "SolarFlow 800 Pro",
        }
        self.assertTrue(set(models).issubset(ZENDURE_DEVICE_MATRIX))
        for profile_key, model in models.items():
            with self.subTest(profile=profile_key):
                entry = resolve_zendure_device(identity(model=model))
                self.assertIsNotNone(entry)
                self.assertIs(entry.profile, DEVICE_PROFILE_MODELS[profile_key])

    def test_verified_legacy_models_prefer_local_mqtt_automatically(self):
        for profile_key, model in (
            ("Hyper 2000", "Hyper 2000"),
            ("HUB 2000", "SolarFlow Hub 2000"),
        ):
            native_identity = NativeDeviceIdentity(
                ZendureTransport.CLOUD_MQTT,
                device_id=profile_key,
                product_model=model,
            )
            entry = resolve_zendure_device(native_identity)
            self.assertIsNotNone(entry)
            self.assertEqual(entry.profile_key, profile_key)
            self.assertEqual(
                preferred_local_transport(native_identity),
                ZendureTransport.LOCAL_MQTT,
            )

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

    def test_cloud_and_zensdk_write_evidence_remain_separate(self):
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
            VerificationLevel.VERIFIED,
        )
        for key, entry in ZENDURE_DEVICE_MATRIX.items():
            with self.subTest(profile=key):
                self.assertTrue(entry.native_control_approved)
                self.assertIs(
                    entry.property_write_level(
                        ZendureTransport.CLOUD_MQTT, "outputLimit"
                    ),
                    VerificationLevel.VERIFIED,
                )
                self.assertIs(
                    entry.property_write_level(
                        ZendureTransport.ZENSDK, "outputLimit"
                    ),
                    VerificationLevel.VERIFIED
                    if key == "SF2400AC"
                    else VerificationLevel.REFERENCE_ONLY,
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
        self.assertNotIn("socLevel", entry.writable_main_properties)

    def test_profile_approval_can_still_be_revoked_fail_closed(self):
        blocked = replace(
            ZENDURE_DEVICE_MATRIX["SF800Pro"],
            native_control_approved=False,
        )
        self.assertFalse(blocked.native_control_approved)
        self.assertTrue(ZENDURE_DEVICE_MATRIX["SF800Pro"].native_control_approved)


if __name__ == "__main__":
    unittest.main()
