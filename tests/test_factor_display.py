"""Tests for user-facing market factor percentages."""

from __future__ import annotations

from pathlib import Path

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.factor_display import (  # noqa: E402
    discount_pct_to_valley_factor,
    markup_pct_to_peak_factor,
    peak_factor_to_markup_pct,
    valley_factor_to_discount_pct,
)

def test_existing_peak_factor_is_shown_as_markup_percent() -> None:
    assert peak_factor_to_markup_pct(1.27) == 27.0


def test_existing_valley_factor_is_shown_as_discount_percent() -> None:
    assert valley_factor_to_discount_pct(0.85) == 15.0


def test_peak_markup_percent_round_trips_to_internal_factor() -> None:
    assert markup_pct_to_peak_factor(27.0) == 1.27
    assert peak_factor_to_markup_pct(markup_pct_to_peak_factor(27.0)) == 27.0


def test_valley_discount_percent_round_trips_to_internal_factor() -> None:
    assert discount_pct_to_valley_factor(15.0) == 0.85
    assert valley_factor_to_discount_pct(discount_pct_to_valley_factor(15.0)) == 15.0


def test_default_factors_have_clear_percentage_values() -> None:
    assert peak_factor_to_markup_pct(1.35) == 35.0
    assert valley_factor_to_discount_pct(0.85) == 15.0


def test_factor_number_entities_use_user_facing_percentages() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "custom_components"
        / "battery_smartflow_ai"
        / "number.py"
    ).read_text(encoding="utf-8")

    assert 'factor_percentage_kind="peak_markup"' in source
    assert 'factor_percentage_kind="valley_discount"' in source
    assert source.count('native_unit_of_measurement="%"') >= 6
    assert "peak_factor_to_markup_pct(value)" in source
    assert "valley_factor_to_discount_pct(value)" in source
    assert "markup_pct_to_peak_factor(value)" in source
    assert "discount_pct_to_valley_factor(value)" in source
