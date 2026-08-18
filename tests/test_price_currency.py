"""Tests for the central Home Assistant price currency context."""

from __future__ import annotations

import unittest

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.price_currency import (  # noqa: E402
    DEFAULT_CURRENCY,
    GENERIC_PRICE_PROFILE,
    LARGE_NOMINAL_PRICE_PROFILE,
    MEDIUM_NOMINAL_PRICE_PROFILE,
    PriceCurrency,
    SMALL_NOMINAL_PRICE_PROFILE,
    migrate_legacy_price_fields,
    normalize_currency_code,
    price_input_profile,
    resolve_price_currency,
)


class PriceCurrencyTests(unittest.TestCase):
    def test_eur_remains_unchanged(self) -> None:
        currency = resolve_price_currency("EUR")

        self.assertEqual(currency, PriceCurrency("EUR"))
        self.assertEqual(currency.price_unit, "EUR/kWh")
        self.assertEqual(currency.monetary_unit, "EUR")
        self.assertFalse(currency.used_fallback)

    def test_dkk_is_used_without_conversion(self) -> None:
        currency = resolve_price_currency("DKK")

        self.assertEqual(currency.code, "DKK")
        self.assertEqual(currency.price_unit, "DKK/kWh")
        self.assertFalse(currency.used_fallback)

    def test_currency_code_is_normalized(self) -> None:
        self.assertEqual(normalize_currency_code(" chf "), "CHF")
        self.assertEqual(resolve_price_currency("gbp").code, "GBP")

    def test_missing_currency_uses_safe_eur_fallback(self) -> None:
        currency = resolve_price_currency(None)

        self.assertEqual(currency.code, DEFAULT_CURRENCY)
        self.assertEqual(currency.price_unit, "EUR/kWh")
        self.assertTrue(currency.used_fallback)

    def test_invalid_currency_uses_safe_eur_fallback(self) -> None:
        for value in ("", "EU", "EURO", "€€€", "12A", object()):
            with self.subTest(value=value):
                currency = resolve_price_currency(value)
                self.assertEqual(currency.code, DEFAULT_CURRENCY)
                self.assertTrue(currency.used_fallback)

    def test_iso_style_codes_are_not_limited_to_a_hard_coded_list(self) -> None:
        currency = resolve_price_currency("xyz")

        self.assertEqual(currency.code, "XYZ")
        self.assertFalse(currency.used_fallback)

    def test_legacy_persisted_prices_are_copied_without_conversion(self) -> None:
        values = {
            "charge_commit_acceptable_price_eur_kwh": 2.2,
            "charge_commit_price_eur_kwh": 1.75,
            "profit_eur": 8.4,
        }

        migrate_legacy_price_fields(values)

        self.assertEqual(values["charge_commit_acceptable_price_per_kwh"], 2.2)
        self.assertEqual(values["charge_commit_price_per_kwh"], 1.75)
        self.assertEqual(values["profit"], 8.4)
        self.assertEqual(values["charge_commit_acceptable_price_eur_kwh"], 2.2)
        self.assertEqual(values["charge_commit_price_eur_kwh"], 1.75)
        self.assertEqual(values["profit_eur"], 8.4)

    def test_neutral_persisted_prices_win_over_legacy_values(self) -> None:
        values = {
            "charge_commit_price_per_kwh": 3.0,
            "charge_commit_price_eur_kwh": 0.3,
        }

        migrate_legacy_price_fields(values)

        self.assertEqual(values["charge_commit_price_per_kwh"], 3.0)

    def test_zero_legacy_prices_are_preserved_exactly(self) -> None:
        values = {
            "charge_commit_acceptable_price_eur_kwh": 0.0,
            "charge_commit_price_eur_kwh": 0.0,
            "profit_eur": 0.0,
        }

        migrate_legacy_price_fields(values)

        self.assertEqual(values["charge_commit_acceptable_price_per_kwh"], 0.0)
        self.assertEqual(values["charge_commit_price_per_kwh"], 0.0)
        self.assertEqual(values["profit"], 0.0)

    def test_legacy_price_migration_is_idempotent_and_keeps_source_fields(self) -> None:
        values = {
            "charge_commit_acceptable_price_eur_kwh": 0.35,
            "charge_commit_price_eur_kwh": 0.49,
            "profit_eur": -1.25,
        }

        migrate_legacy_price_fields(values)
        first_result = dict(values)
        migrate_legacy_price_fields(values)

        self.assertEqual(values, first_result)
        self.assertEqual(values["charge_commit_acceptable_price_eur_kwh"], 0.35)
        self.assertEqual(values["charge_commit_price_eur_kwh"], 0.49)
        self.assertEqual(values["profit_eur"], -1.25)

    def test_currency_resolution_never_converts_existing_values(self) -> None:
        configured = {
            "price_threshold": 0.35,
            "very_expensive_threshold": 0.49,
            "feed_in_tariff": 0.081,
        }
        original = dict(configured)

        for code in ("EUR", "DKK", "CHF", "SEK", "NOK", "GBP", "CZK", "PLN"):
            resolve_price_currency(code)
            price_input_profile(code)

        self.assertEqual(configured, original)

    def test_small_nominal_currency_profiles(self) -> None:
        for code in ("EUR", "CHF", "GBP"):
            with self.subTest(code=code):
                self.assertEqual(
                    price_input_profile(code),
                    SMALL_NOMINAL_PRICE_PROFILE,
                )

    def test_medium_nominal_currency_profiles(self) -> None:
        for code in ("DKK", "SEK", "NOK"):
            with self.subTest(code=code):
                self.assertEqual(
                    price_input_profile(code),
                    MEDIUM_NOMINAL_PRICE_PROFILE,
                )

    def test_large_nominal_currency_profiles(self) -> None:
        for code in ("CZK", "PLN"):
            with self.subTest(code=code):
                self.assertEqual(
                    price_input_profile(code),
                    LARGE_NOMINAL_PRICE_PROFILE,
                )

    def test_unknown_valid_currency_gets_safe_generic_profile(self) -> None:
        self.assertEqual(price_input_profile("XYZ"), GENERIC_PRICE_PROFILE)

    def test_profiles_allow_negative_and_high_price_scenarios(self) -> None:
        self.assertLess(SMALL_NOMINAL_PRICE_PROFILE.minimum, 0.0)
        self.assertGreaterEqual(MEDIUM_NOMINAL_PRICE_PROFILE.maximum, 50.0)
        self.assertGreaterEqual(LARGE_NOMINAL_PRICE_PROFILE.maximum, 250.0)

    def test_eur_defaults_remain_backward_compatible(self) -> None:
        profile = price_input_profile("EUR")
        self.assertEqual(profile.default_expensive_threshold, 0.35)
        self.assertEqual(profile.default_very_expensive_threshold, 0.49)

    def test_nominal_groups_receive_suitable_unconfigured_defaults(self) -> None:
        self.assertEqual(
            price_input_profile("DKK").default_expensive_threshold,
            3.5,
        )
        self.assertEqual(
            price_input_profile("DKK").default_very_expensive_threshold,
            4.9,
        )
        self.assertEqual(
            price_input_profile("CZK").default_expensive_threshold,
            17.5,
        )
        self.assertEqual(
            price_input_profile("CZK").default_very_expensive_threshold,
            24.5,
        )


if __name__ == "__main__":
    unittest.main()
