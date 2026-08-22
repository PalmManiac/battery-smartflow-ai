"""Tests for generic, static and adaptable market price sources."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import unittest

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.market_price import (  # noqa: E402
    GenericStatePriceSource,
    MarketPriceDirection,
    MarketPriceSourceAdapter,
    MarketPriceValidity,
    NumericPriceNormalizer,
    PriceSourceStatus,
    StaticPriceSource,
)


NOW = datetime(2026, 8, 21, 13, 0, tzinfo=timezone.utc)


@dataclass
class FakeState:
    state: object
    attributes: dict[str, object]
    last_updated: datetime = NOW


class MarketPriceSourceTests(unittest.TestCase):
    def test_generic_numeric_state_sensor_builds_dynamic_market_price(self) -> None:
        states = {
            "sensor.import_price": FakeState(
                state="0.142",
                attributes={"unit_of_measurement": "EUR/kWh"},
            )
        }
        source = GenericStatePriceSource(
            "sensor.import_price",
            states.get,
        )
        adapter = MarketPriceSourceAdapter(
            source=source,
            normalizer=NumericPriceNormalizer(),
            direction=MarketPriceDirection.IMPORT,
            active_currency="EUR",
        )

        price = adapter.read()

        self.assertTrue(price.valid)
        self.assertEqual(price.current_price, 0.142)
        self.assertEqual(price.currency, "EUR")
        self.assertEqual(price.unit, "EUR/kWh")
        self.assertEqual(price.timestamp, NOW)
        self.assertEqual(price.source, "sensor.import_price")
        self.assertTrue(price.is_dynamic)
        self.assertFalse(price.is_fallback)

    def test_generic_state_preserves_explicit_currency_metadata(self) -> None:
        states = {
            "sensor.danish_price": FakeState(
                state=1.35,
                attributes={
                    "unit_of_measurement": "DKK/kWh",
                    "currency": "dkk",
                },
            )
        }
        source = GenericStatePriceSource("sensor.danish_price", states.get)
        price = MarketPriceSourceAdapter(
            source=source,
            normalizer=NumericPriceNormalizer(),
            direction=MarketPriceDirection.IMPORT,
            active_currency="DKK",
        ).read()

        self.assertEqual(price.currency, "DKK")
        self.assertEqual(price.unit, "DKK/kWh")
        self.assertEqual(price.current_price, 1.35)

    def test_different_source_currency_is_rejected_without_conversion(self) -> None:
        source = GenericStatePriceSource(
            "sensor.danish_price",
            lambda _: FakeState(
                1.35,
                {
                    "unit_of_measurement": "DKK/kWh",
                    "currency": "DKK",
                },
            ),
        )
        price = MarketPriceSourceAdapter(
            source=source,
            normalizer=NumericPriceNormalizer(),
            direction=MarketPriceDirection.IMPORT,
            active_currency="EUR",
        ).read()

        self.assertFalse(price.valid)
        self.assertIsNone(price.current_price)
        self.assertEqual(price.validity, MarketPriceValidity.INVALID)

    def test_zero_and_negative_state_prices_remain_valid(self) -> None:
        for raw_value in ("0", "-0.05"):
            with self.subTest(raw_value=raw_value):
                source = GenericStatePriceSource(
                    "sensor.export_price",
                    lambda _: FakeState(raw_value, {}),
                )
                price = MarketPriceSourceAdapter(
                    source=source,
                    normalizer=NumericPriceNormalizer(),
                    direction=MarketPriceDirection.EXPORT,
                    active_currency="EUR",
                ).read()

                self.assertTrue(price.valid)
                self.assertEqual(price.current_price, float(raw_value))

    def test_missing_entity_propagates_missing_status(self) -> None:
        source = GenericStatePriceSource("sensor.missing", lambda _: None)
        reading = source.read()
        price = MarketPriceSourceAdapter(
            source=source,
            normalizer=NumericPriceNormalizer(),
            direction=MarketPriceDirection.IMPORT,
            active_currency="EUR",
        ).read()

        self.assertEqual(reading.status, PriceSourceStatus.MISSING)
        self.assertEqual(price.validity, MarketPriceValidity.MISSING)
        self.assertIsNone(price.current_price)
        self.assertFalse(price.valid)

    def test_unknown_and_unavailable_states_remain_distinct(self) -> None:
        expected = {
            "unknown": MarketPriceValidity.UNKNOWN,
            "unavailable": MarketPriceValidity.UNAVAILABLE,
        }
        for raw_state, validity in expected.items():
            with self.subTest(raw_state=raw_state):
                source = GenericStatePriceSource(
                    "sensor.price",
                    lambda _: FakeState(raw_state, {}),
                )
                price = MarketPriceSourceAdapter(
                    source=source,
                    normalizer=NumericPriceNormalizer(),
                    direction=MarketPriceDirection.IMPORT,
                    active_currency="EUR",
                ).read()

                self.assertEqual(price.validity, validity)
                self.assertIsNone(price.current_price)

    def test_invalid_and_non_finite_state_values_are_rejected(self) -> None:
        for raw_value in ("not-a-number", "nan", "inf", None):
            with self.subTest(raw_value=raw_value):
                source = GenericStatePriceSource(
                    "sensor.price",
                    lambda _: FakeState(raw_value, {}),
                )
                price = MarketPriceSourceAdapter(
                    source=source,
                    normalizer=NumericPriceNormalizer(),
                    direction=MarketPriceDirection.IMPORT,
                    active_currency="EUR",
                ).read()

                self.assertEqual(price.validity, MarketPriceValidity.INVALID)
                self.assertIsNone(price.current_price)

    def test_static_source_uses_same_adapter_and_marks_fallback(self) -> None:
        source = StaticPriceSource(
            value=0.122,
            currency="EUR",
            unit="EUR/kWh",
            source="config.feed_in_tariff",
            is_fallback=True,
        )
        price = MarketPriceSourceAdapter(
            source=source,
            normalizer=NumericPriceNormalizer(),
            direction=MarketPriceDirection.EXPORT,
            active_currency="EUR",
        ).read()

        self.assertTrue(price.valid)
        self.assertEqual(price.current_price, 0.122)
        self.assertFalse(price.is_dynamic)
        self.assertTrue(price.is_fallback)
        self.assertEqual(price.source, "config.feed_in_tariff")

    def test_source_acquisition_does_not_convert_units(self) -> None:
        source = GenericStatePriceSource(
            "sensor.megawatt_hour_price",
            lambda _: FakeState(
                122.0,
                {"unit_of_measurement": "EUR/MWh"},
            ),
        )

        reading = source.read()

        self.assertEqual(reading.value, 122.0)
        self.assertEqual(reading.unit, "EUR/MWh")


if __name__ == "__main__":
    unittest.main()
