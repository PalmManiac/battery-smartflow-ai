"""User-facing percentage conversion for internal market price factors."""

from __future__ import annotations


def peak_factor_to_markup_pct(factor: float) -> float:
    """Convert an internal peak multiplier to a user-facing markup percent."""
    return round((float(factor) - 1.0) * 100.0, 6)


def markup_pct_to_peak_factor(percent: float) -> float:
    """Convert a user-facing peak markup percent to an internal multiplier."""
    return round(1.0 + (float(percent) / 100.0), 6)


def valley_factor_to_discount_pct(factor: float) -> float:
    """Convert an internal valley multiplier to a user-facing discount percent."""
    return round((1.0 - float(factor)) * 100.0, 6)


def discount_pct_to_valley_factor(percent: float) -> float:
    """Convert a user-facing valley discount percent to an internal multiplier."""
    return round(1.0 - (float(percent) / 100.0), 6)
