"""Central unit, currency, numeric and freshness normalization contracts."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.market_price import (  # noqa: E402
    MarketPriceValidity,
    NumericPriceNormalizer,
    PriceSourceReading,
    PriceSourceStatus,
    normalize_price_value,
)


NOW = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)


def normalize(value, *, unit=None, currency=None, active_currency="EUR"):
    return normalize_price_value(
        value,
        unit=unit,
        currency=currency,
        active_currency=active_currency,
    )


class MarketPriceValueNormalizationTests(unittest.TestCase):
    def test_currency_per_kwh_is_canonical_without_scaling(self) -> None:
        for currency in ("EUR", "DKK", "CHF"):
            with self.subTest(currency=currency):
                result = normalize(
                    -0.125,
                    unit=f"{currency}/kWh",
                    currency=currency.lower(),
                    active_currency=currency,
                )

                self.assertEqual(result.validity, MarketPriceValidity.VALID)
                self.assertEqual(result.value, -0.125)
                self.assertEqual(result.currency, currency)
                self.assertEqual(result.unit, f"{currency}/kWh")

    def test_cents_per_kwh_are_scaled_in_active_currency(self) -> None:
        for unit in ("ct/kWh", "cent/kWh", "c/kWh"):
            with self.subTest(unit=unit):
                result = normalize(-3.0, unit=unit)
                self.assertEqual(result.value, -0.03)
                self.assertEqual(result.unit, "EUR/kWh")

    def test_currency_per_mwh_is_divided_by_one_thousand(self) -> None:
        result = normalize(122.0, unit="EUR/MWh", currency="EUR")

        self.assertEqual(result.value, 0.122)
        self.assertEqual(result.unit, "EUR/kWh")

    def test_epex_euro_symbol_units_are_supported_for_eur(self) -> None:
        per_kwh = normalize(-0.125, unit="€/kWh")
        per_mwh = normalize(122.0, unit="€/MWh")

        self.assertEqual(per_kwh.validity, MarketPriceValidity.VALID)
        self.assertEqual(per_kwh.value, -0.125)
        self.assertEqual(per_kwh.currency, "EUR")
        self.assertEqual(per_kwh.unit, "EUR/kWh")
        self.assertEqual(per_mwh.validity, MarketPriceValidity.VALID)
        self.assertEqual(per_mwh.value, 0.122)

    def test_euro_symbol_unit_is_rejected_for_non_eur_system_currency(self) -> None:
        result = normalize(0.25, unit="€/kWh", active_currency="CHF")

        self.assertEqual(result.validity, MarketPriceValidity.INVALID)
        self.assertIsNone(result.value)

    def test_zero_remains_valid_for_every_supported_scale(self) -> None:
        for unit in ("EUR/kWh", "ct/kWh", "EUR/MWh", "€/kWh", "€/MWh"):
            with self.subTest(unit=unit):
                result = normalize(0.0, unit=unit)
                self.assertEqual(result.validity, MarketPriceValidity.VALID)
                self.assertEqual(result.value, 0.0)

    def test_missing_unit_keeps_v45_per_kwh_compatibility(self) -> None:
        result = normalize(0.25)

        self.assertEqual(result.value, 0.25)
        self.assertEqual(result.unit, "EUR/kWh")

    def test_currency_mismatch_is_invalid_and_never_converted(self) -> None:
        for unit, currency in (
            ("DKK/kWh", None),
            ("DKK/MWh", "DKK"),
            ("EUR/kWh", "DKK"),
        ):
            with self.subTest(unit=unit, currency=currency):
                result = normalize(100.0, unit=unit, currency=currency)
                self.assertEqual(result.validity, MarketPriceValidity.INVALID)
                self.assertIsNone(result.value)

    def test_unknown_units_and_invalid_currency_metadata_are_rejected(self) -> None:
        for unit, currency in (
            ("EUR/Wh", "EUR"),
            ("$/kWh", None),
            ("W", "EUR"),
            ("EUR/kWh", "EURO"),
        ):
            with self.subTest(unit=unit, currency=currency):
                result = normalize(1.0, unit=unit, currency=currency)
                self.assertEqual(result.validity, MarketPriceValidity.INVALID)

    def test_non_numeric_and_non_finite_values_are_invalid(self) -> None:
        for value in (None, "unknown", "nan", "inf", float("-inf")):
            with self.subTest(value=value):
                result = normalize(value, unit="EUR/kWh")
                self.assertEqual(result.validity, MarketPriceValidity.INVALID)
                self.assertIsNone(result.value)


class MarketPriceFreshnessTests(unittest.TestCase):
    def _reading(self, timestamp: datetime | None) -> PriceSourceReading:
        return PriceSourceReading(
            value=0.2,
            unit="EUR/kWh",
            currency="EUR",
            timestamp=timestamp,
            source="sensor.price",
            status=PriceSourceStatus.AVAILABLE,
            is_dynamic=True,
        )

    def test_recent_dynamic_state_is_valid(self) -> None:
        result = NumericPriceNormalizer(now=NOW).normalize(
            self._reading(NOW - timedelta(hours=1)),
            active_currency="EUR",
        )

        self.assertEqual(result.validity, MarketPriceValidity.VALID)

    def test_old_dynamic_state_is_stale(self) -> None:
        result = NumericPriceNormalizer(now=NOW).normalize(
            self._reading(NOW - timedelta(hours=7)),
            active_currency="EUR",
        )

        self.assertEqual(result.validity, MarketPriceValidity.STALE)
        self.assertIsNone(result.value)

    def test_missing_or_naive_dynamic_timestamp_is_invalid(self) -> None:
        for timestamp in (None, datetime(2026, 8, 22, 11, 0)):
            with self.subTest(timestamp=timestamp):
                result = NumericPriceNormalizer(now=NOW).normalize(
                    self._reading(timestamp),
                    active_currency="EUR",
                )
                self.assertEqual(result.validity, MarketPriceValidity.INVALID)

    def test_far_future_dynamic_timestamp_is_invalid(self) -> None:
        result = NumericPriceNormalizer(now=NOW).normalize(
            self._reading(NOW + timedelta(minutes=6)),
            active_currency="EUR",
        )

        self.assertEqual(result.validity, MarketPriceValidity.INVALID)

    def test_static_source_does_not_require_timestamp(self) -> None:
        reading = self._reading(None)
        reading = PriceSourceReading(
            value=reading.value,
            unit=reading.unit,
            currency=reading.currency,
            timestamp=None,
            source="config.feed_in_tariff",
            status=reading.status,
            is_dynamic=False,
        )
        result = NumericPriceNormalizer(now=NOW).normalize(
            reading,
            active_currency="EUR",
        )

        self.assertEqual(result.validity, MarketPriceValidity.VALID)


if __name__ == "__main__":
    unittest.main()
