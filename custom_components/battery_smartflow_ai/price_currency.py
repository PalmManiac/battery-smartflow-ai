"""Currency context for price values used by Battery SmartFlow AI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, MutableMapping


DEFAULT_CURRENCY = "EUR"

LEGACY_PRICE_FIELD_NAMES: dict[str, str] = {
    "charge_commit_acceptable_price_per_kwh": (
        "charge_commit_acceptable_price_eur_kwh"
    ),
    "charge_commit_price_per_kwh": "charge_commit_price_eur_kwh",
    "profit": "profit_eur",
}


def normalize_currency_code(value: object) -> str | None:
    """Return a normalized ISO-style currency code or ``None``.

    Home Assistant exposes its configured system currency as a three-letter
    code. Keeping validation structural lets BSFAI follow every currency Home
    Assistant supports without maintaining its own potentially stale list.
    """

    if not isinstance(value, str):
        return None

    code = value.strip().upper()
    if len(code) != 3 or not code.isascii() or not code.isalpha():
        return None
    return code


@dataclass(frozen=True, slots=True)
class PriceCurrency:
    """Active currency metadata; numeric price values are never converted."""

    code: str
    used_fallback: bool = False

    @property
    def price_unit(self) -> str:
        """Return the Home Assistant unit used for prices per kWh."""

        return f"{self.code}/kWh"

    @property
    def monetary_unit(self) -> str:
        """Return the unit used for monetary totals."""

        return self.code


@dataclass(frozen=True, slots=True)
class PriceInputProfile:
    """Safe input range and precision for one nominal currency group."""

    minimum: float
    maximum: float
    step: float
    display_precision: int
    default_expensive_threshold: float
    default_very_expensive_threshold: float


SMALL_NOMINAL_CURRENCIES = frozenset(
    {"EUR", "CHF", "GBP", "USD", "CAD", "AUD", "NZD"}
)
MEDIUM_NOMINAL_CURRENCIES = frozenset({"DKK", "SEK", "NOK"})
LARGE_NOMINAL_CURRENCIES = frozenset({"CZK", "PLN"})

SMALL_NOMINAL_PRICE_PROFILE = PriceInputProfile(
    -2.0, 5.0, 0.01, 2, 0.35, 0.49
)
MEDIUM_NOMINAL_PRICE_PROFILE = PriceInputProfile(
    -20.0, 50.0, 0.05, 2, 3.5, 4.9
)
LARGE_NOMINAL_PRICE_PROFILE = PriceInputProfile(
    -100.0, 250.0, 0.1, 1, 17.5, 24.5
)
GENERIC_PRICE_PROFILE = PriceInputProfile(
    -1000.0, 10000.0, 0.01, 2, 700.0, 980.0
)


def resolve_price_currency(value: object) -> PriceCurrency:
    """Resolve Home Assistant's currency with a safe EUR fallback."""

    code = normalize_currency_code(value)
    if code is None:
        return PriceCurrency(DEFAULT_CURRENCY, used_fallback=True)
    return PriceCurrency(code)


def price_input_profile(currency: PriceCurrency | str) -> PriceInputProfile:
    """Return ranges suitable for the currency's nominal price magnitude."""

    code = currency.code if isinstance(currency, PriceCurrency) else str(currency)
    code = normalize_currency_code(code) or DEFAULT_CURRENCY

    if code in SMALL_NOMINAL_CURRENCIES:
        return SMALL_NOMINAL_PRICE_PROFILE
    if code in MEDIUM_NOMINAL_CURRENCIES:
        return MEDIUM_NOMINAL_PRICE_PROFILE
    if code in LARGE_NOMINAL_CURRENCIES:
        return LARGE_NOMINAL_PRICE_PROFILE
    return GENERIC_PRICE_PROFILE


def migrate_legacy_price_fields(values: MutableMapping[str, Any]) -> None:
    """Copy legacy EUR-named persisted values to currency-neutral fields.

    Legacy fields are retained for downgrade safety. Existing numeric values
    are copied exactly and are never interpreted as a different currency or
    passed through an exchange-rate conversion.
    """

    for neutral_name, legacy_name in LEGACY_PRICE_FIELD_NAMES.items():
        if values.get(neutral_name) is None and values.get(legacy_name) is not None:
            values[neutral_name] = values[legacy_name]
