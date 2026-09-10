"""Tests for Home Assistant AC-mode select compatibility."""

from __future__ import annotations

import unittest

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.ac_mode_options import (  # noqa: E402
    canonical_ac_mode,
    resolve_ac_mode_option,
)


class AcModeOptionTests(unittest.TestCase):
    def test_official_zha_options_are_preserved(self):
        self.assertEqual(
            resolve_ac_mode_option("input", ("input", "output")),
            "input",
        )

    def test_descriptive_options_are_resolved_to_exact_service_value(self):
        self.assertEqual(
            resolve_ac_mode_option("input", ("Input mode", "Output mode")),
            "Input mode",
        )
        self.assertEqual(canonical_ac_mode("AC Output Mode"), "output")

    def test_unknown_and_ambiguous_options_fail_closed(self):
        self.assertIsNone(resolve_ac_mode_option("input", ("charge", "discharge")))
        self.assertIsNone(resolve_ac_mode_option("input", ("input", "Input mode")))
        self.assertIsNone(resolve_ac_mode_option("idle", ("input", "output")))


if __name__ == "__main__":
    unittest.main()
