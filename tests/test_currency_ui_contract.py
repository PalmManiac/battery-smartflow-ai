"""Static contract tests for currency-neutral Home Assistant entities."""

from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "battery_smartflow_ai"


class CurrencyUiContractTests(unittest.TestCase):
    def test_entity_platforms_have_no_hard_coded_eur_units_or_icons(self) -> None:
        for filename in ("number.py", "sensor.py"):
            with self.subTest(filename=filename):
                source = (COMPONENT / filename).read_text(encoding="utf-8")
                self.assertNotIn("€/kWh", source)
                self.assertNotIn('native_unit_of_measurement="€"', source)
                self.assertNotIn("mdi:currency-eur", source)

    def test_price_numbers_use_central_currency_profile_and_unit(self) -> None:
        source = (COMPONENT / "number.py").read_text(encoding="utf-8")

        self.assertIn("price_input_profile(coordinator.price_currency)", source)
        self.assertIn("coordinator.price_currency.price_unit", source)

    def test_price_sensors_use_central_dynamic_units(self) -> None:
        source = (COMPONENT / "sensor.py").read_text(encoding="utf-8")

        self.assertIn("coordinator.price_currency.price_unit", source)
        self.assertIn("coordinator.price_currency.monetary_unit", source)
        self.assertIn("price_input_profile(", source)
        self.assertIn("if self.native_unit_of_measurement:", source)


if __name__ == "__main__":
    unittest.main()
