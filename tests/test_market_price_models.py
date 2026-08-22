"""Contract tests for the provider-independent market price data model."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
import unittest

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.market_price import (  # noqa: E402
    MarketPrice,
    MarketPriceDirection,
    MarketPriceForecast,
    MarketPricePoint,
    MarketPriceValidity,
)


NOW = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)


def market_price(
    *,
    direction: MarketPriceDirection = MarketPriceDirection.IMPORT,
    current_price: float | None = 0.25,
    validity: MarketPriceValidity = MarketPriceValidity.VALID,
    forecast: MarketPriceForecast | None = None,
) -> MarketPrice:
    """Build one concise market price fixture."""

    return MarketPrice(
        direction=direction,
        current_price=current_price,
        currency="EUR",
        unit="EUR/kWh",
        timestamp=NOW,
        source="sensor.market_price",
        validity=validity,
        is_dynamic=True,
        is_fallback=False,
        forecast=forecast,
    )


class MarketPriceModelTests(unittest.TestCase):
    def test_import_and_export_use_the_same_model(self) -> None:
        import_price = market_price(direction=MarketPriceDirection.IMPORT)
        export_price = market_price(direction=MarketPriceDirection.EXPORT)

        self.assertIs(type(import_price), type(export_price))
        self.assertEqual(import_price.direction, MarketPriceDirection.IMPORT)
        self.assertEqual(export_price.direction, MarketPriceDirection.EXPORT)

    def test_zero_price_is_valid(self) -> None:
        price = market_price(current_price=0.0)

        self.assertTrue(price.valid)
        self.assertEqual(price.current_price, 0.0)

    def test_negative_price_is_valid(self) -> None:
        price = market_price(current_price=-0.05)

        self.assertTrue(price.valid)
        self.assertEqual(price.current_price, -0.05)

    def test_missing_price_is_not_replaced_with_zero(self) -> None:
        price = market_price(
            current_price=None,
            validity=MarketPriceValidity.MISSING,
        )

        self.assertFalse(price.valid)
        self.assertIsNone(price.current_price)
        self.assertEqual(price.validity, MarketPriceValidity.MISSING)

    def test_validity_distinguishes_unknown_and_unavailable(self) -> None:
        unknown = market_price(
            current_price=None,
            validity=MarketPriceValidity.UNKNOWN,
        )
        unavailable = market_price(
            current_price=None,
            validity=MarketPriceValidity.UNAVAILABLE,
        )

        self.assertNotEqual(unknown.validity, unavailable.validity)
        self.assertFalse(unknown.valid)
        self.assertFalse(unavailable.valid)

    def test_forecast_points_preserve_normalized_intervals_and_prices(self) -> None:
        first = MarketPricePoint(
            start=NOW,
            end=NOW + timedelta(minutes=15),
            price=-0.03,
        )
        second = MarketPricePoint(
            start=first.end,
            end=first.end + timedelta(hours=1),
            price=0.0,
        )
        forecast = MarketPriceForecast(points=(first, second), timestamp=NOW)
        price = market_price(forecast=forecast)

        self.assertEqual(price.forecast, forecast)
        self.assertEqual(price.forecast.points, (first, second))
        self.assertEqual(price.forecast.points[0].price, -0.03)
        self.assertEqual(price.forecast.points[1].price, 0.0)

    def test_empty_forecast_is_explicit_and_does_not_invent_points(self) -> None:
        forecast = MarketPriceForecast.empty(timestamp=NOW)

        self.assertEqual(forecast.points, ())
        self.assertEqual(forecast.timestamp, NOW)

    def test_market_models_are_immutable(self) -> None:
        price = market_price()

        with self.assertRaises(FrozenInstanceError):
            price.current_price = 0.5  # type: ignore[misc]

    def test_model_is_currency_neutral(self) -> None:
        price = MarketPrice(
            direction=MarketPriceDirection.IMPORT,
            current_price=1.35,
            currency="DKK",
            unit="DKK/kWh",
            timestamp=NOW,
            source="sensor.generic_danish_price",
            validity=MarketPriceValidity.VALID,
            is_dynamic=True,
            is_fallback=False,
        )

        self.assertTrue(price.valid)
        self.assertEqual(price.currency, "DKK")
        self.assertEqual(price.unit, "DKK/kWh")


if __name__ == "__main__":
    unittest.main()
