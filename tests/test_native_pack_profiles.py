"""Verified native battery model and capacity resolution."""

import unittest

from support import bootstrap

bootstrap()

from custom_components.battery_smartflow_ai.native_capacity import (  # noqa: E402
    pack_capacity_kwh,
    resolve_pack_profile,
)


class NativePackProfileTests(unittest.TestCase):
    def test_serial_profiles_resolve_model_and_capacity_together(self):
        cases = {
            ("A003-test", None): ("AIO2400", 2.4),
            ("A000-test", None): ("AB1000", 0.96),
            ("B000-test", None): ("AB1000S", 0.96),
            ("B000-test", "70"): ("I8000", 8.0),
            ("C00F-test", None): ("AB2000S", 1.92),
            ("C00E-test", None): ("AB2000X", 1.92),
            ("C00A-test", None): ("AB2000", 1.92),
            ("F000-test", None): ("AB3000", 2.88),
            ("G000-test", None): ("AB3000L", 2.88),
            ("J02A-test", None): ("I2400", 2.4),
        }
        for (serial, pack_type), expected in cases.items():
            with self.subTest(serial=serial, pack_type=pack_type):
                profile = resolve_pack_profile(serial, pack_type)
                self.assertIsNotNone(profile)
                self.assertEqual((profile.model, profile.capacity_kwh), expected)
                self.assertEqual(
                    pack_capacity_kwh(serial, pack_type), expected[1]
                )

    def test_pack_type_fallback_handles_missing_or_short_serial(self):
        cases = {
            "70": ("I8000", 8.0),
            "250": ("AB1000", 0.96),
            "300": ("AB2000S / AB2000X", 1.92),
            "500": ("I2400", 2.4),
        }
        for pack_type, expected in cases.items():
            with self.subTest(pack_type=pack_type):
                profile = resolve_pack_profile("", pack_type)
                self.assertEqual((profile.model, profile.capacity_kwh), expected)

        sf2400ac = resolve_pack_profile("", "5", "SolarFlow 2400 AC")
        self.assertEqual(
            (sf2400ac.model, sf2400ac.capacity_kwh), ("AB3000X", 2.88)
        )

    def test_unknown_or_ambiguous_evidence_does_not_guess(self):
        self.assertIsNone(resolve_pack_profile(None, None))
        self.assertIsNone(resolve_pack_profile("short", "999"))
        self.assertIsNone(pack_capacity_kwh(None, "5"))


if __name__ == "__main__":
    unittest.main()
