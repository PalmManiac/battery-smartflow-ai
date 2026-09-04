"""Contracts for privacy-safe native Zendure configuration labels."""

from __future__ import annotations

import unittest

from support import bootstrap

bootstrap()

from custom_components.battery_smartflow_ai.native_config_ui import (  # noqa: E402
    STORED_APP_TOKEN_MASK,
    native_device_label,
    native_device_summary_line,
    resolve_app_token_input,
)


class NativeConfigUiTests(unittest.TestCase):
    def test_mask_and_blank_reuse_private_stored_token(self) -> None:
        stored = "private-real-token"
        self.assertEqual(resolve_app_token_input(STORED_APP_TOKEN_MASK, stored), stored)
        self.assertEqual(resolve_app_token_input("", stored), stored)
        self.assertNotIn(stored, STORED_APP_TOKEN_MASK)

    def test_new_token_replaces_stored_token(self) -> None:
        self.assertEqual(
            resolve_app_token_input(" replacement ", "old"), "replacement"
        )

    def test_identical_name_and_model_are_not_repeated(self) -> None:
        self.assertEqual(
            native_device_label("SolarFlow 2400 AC", "SolarFlow 2400 AC", None),
            "SolarFlow 2400 AC",
        )

    def test_model_is_kept_for_a_distinct_user_name(self) -> None:
        self.assertEqual(
            native_device_label("Hobbyraum", "SolarFlow 2400 AC", None),
            "Hobbyraum – SolarFlow 2400 AC",
        )

    def test_unknown_and_zero_pack_counts_are_omitted(self) -> None:
        for count in (None, 0):
            with self.subTest(count=count):
                label = native_device_label(
                    "SolarFlow 2400 AC", "SolarFlow 2400 AC", count
                )
                summary = native_device_summary_line(
                    "SolarFlow 2400 AC", "SolarFlow 2400 AC", count, True
                )
                self.assertEqual(label, "SolarFlow 2400 AC")
                self.assertEqual(summary, "• SolarFlow 2400 AC, online")
                self.assertNotIn("pack", label + summary)

    def test_positive_pack_count_is_shown_once(self) -> None:
        self.assertEqual(
            native_device_label("Hobbyraum", "SolarFlow 2400 AC", 2),
            "Hobbyraum – SolarFlow 2400 AC (2 packs)",
        )
        self.assertEqual(
            native_device_summary_line(
                "Hobbyraum", "SolarFlow 2400 AC", 1, False
            ),
            "• Hobbyraum – SolarFlow 2400 AC, 1 pack, offline",
        )


if __name__ == "__main__":
    unittest.main()
