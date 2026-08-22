"""Fallback contracts for static and dynamic export prices."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import unittest

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.market_price import (  # noqa: E402
    ExportMarketPriceResolver,
    MarketPriceDirection,
    MarketPriceValidity,
)


NOW = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)


@dataclass
class FakeState:
    state: object
    attributes: dict[str, object]
    last_updated: datetime = NOW


def resolve(
    states: dict[str, FakeState],
    *,
    dynamic_entity_id: str | None = "sensor.dynamic_export_price",
    static_value: object | None = 0.08,
    static_configured: bool = True,
):
    return ExportMarketPriceResolver(
        state_getter=states.get,
        active_currency="EUR",
        dynamic_entity_id=dynamic_entity_id,
        static_value=static_value,
        static_configured=static_configured,
    ).resolve()


class ExportMarketPriceResolverTests(unittest.TestCase):
    def test_valid_dynamic_price_has_priority(self) -> None:
        price = resolve(
            {
                "sensor.dynamic_export_price": FakeState(
                    "0.14",
                    {"unit_of_measurement": "EUR/kWh"},
                )
            }
        )

        self.assertTrue(price.valid)
        self.assertEqual(price.direction, MarketPriceDirection.EXPORT)
        self.assertEqual(price.current_price, 0.14)
        self.assertEqual(price.source, "sensor.dynamic_export_price")
        self.assertTrue(price.is_dynamic)
        self.assertFalse(price.is_fallback)

    def test_dynamic_zero_and_negative_prices_are_valid(self) -> None:
        for raw_value in ("0", "-0.05"):
            with self.subTest(raw_value=raw_value):
                price = resolve(
                    {
                        "sensor.dynamic_export_price": FakeState(
                            raw_value,
                            {"unit_of_measurement": "EUR/kWh"},
                        )
                    }
                )

                self.assertTrue(price.valid)
                self.assertEqual(price.current_price, float(raw_value))
                self.assertEqual(price.source, "sensor.dynamic_export_price")

    def test_unusable_dynamic_states_fall_back_to_static_tariff(self) -> None:
        for raw_value in ("unknown", "unavailable", "invalid", "nan"):
            with self.subTest(raw_value=raw_value):
                price = resolve(
                    {"sensor.dynamic_export_price": FakeState(raw_value, {})}
                )

                self.assertTrue(price.valid)
                self.assertEqual(price.current_price, 0.08)
                self.assertEqual(price.source, "config.feed_in_tariff")
                self.assertFalse(price.is_dynamic)
                self.assertTrue(price.is_fallback)

    def test_missing_dynamic_entity_falls_back_to_static_zero(self) -> None:
        price = resolve({}, static_value=0.0)

        self.assertTrue(price.valid)
        self.assertEqual(price.current_price, 0.0)
        self.assertEqual(price.source, "config.feed_in_tariff")
        self.assertTrue(price.is_fallback)

    def test_static_source_is_primary_when_no_dynamic_sensor_is_configured(self) -> None:
        price = resolve({}, dynamic_entity_id=None)

        self.assertTrue(price.valid)
        self.assertEqual(price.current_price, 0.08)
        self.assertFalse(price.is_dynamic)
        self.assertFalse(price.is_fallback)

    def test_no_usable_source_returns_missing_without_synthetic_zero(self) -> None:
        price = resolve(
            {"sensor.dynamic_export_price": FakeState("unavailable", {})},
            static_configured=False,
        )

        self.assertFalse(price.valid)
        self.assertIsNone(price.current_price)
        self.assertEqual(price.validity, MarketPriceValidity.MISSING)
        self.assertEqual(price.source, "not_configured")

    def test_invalid_static_value_does_not_become_zero(self) -> None:
        price = resolve({}, dynamic_entity_id=None, static_value="invalid")

        self.assertFalse(price.valid)
        self.assertIsNone(price.current_price)


if __name__ == "__main__":
    unittest.main()
