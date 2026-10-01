from __future__ import annotations

import unittest

from custom_components.battery_smartflow_ai.offgrid_select import (
    matching_offgrid_options,
    normalize_offgrid_option,
)


class TestOffgridModeSelectOptions(unittest.TestCase):
    def test_normalizes_common_localized_and_numeric_options(self) -> None:
        self.assertEqual(normalize_offgrid_option("Aus"), "off")
        self.assertEqual(normalize_offgrid_option("Standard"), "normal")
        self.assertEqual(normalize_offgrid_option("Economic"), "eco")
        self.assertEqual(normalize_offgrid_option("2"), "eco")
        self.assertIsNone(normalize_offgrid_option("unknown mode"))

    def test_maps_only_supported_modes_to_original_select_labels(self) -> None:
        self.assertEqual(
            matching_offgrid_options(["Disabled", "Normal", "Economic", "Auto"]),
            {"off": "Disabled", "normal": "Normal", "eco": "Economic"},
        )

    def test_missing_or_unrecognized_options_are_not_exposed(self) -> None:
        self.assertEqual(matching_offgrid_options(None), {})
        self.assertEqual(matching_offgrid_options(["Auto", "Standby"]), {})


if __name__ == "__main__":
    unittest.main()
