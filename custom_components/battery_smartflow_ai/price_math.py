"""Currency-neutral calculations for values expressed as price per kWh."""

from __future__ import annotations

from collections.abc import Sequence


def peak_threshold(prices: Sequence[float], peak_factor: float) -> float:
    """Return a scale-invariant peak threshold for one price series."""

    values = [float(value) for value in prices]
    if not values:
        raise ValueError("prices must not be empty")

    average = sum(values) / len(values)
    factor_delta = max(0.0, float(peak_factor) - 1.0)
    price_span = max(values) - min(values)
    relative_separation = abs(average) * factor_delta
    observed_separation = max(0.0, price_span) * 0.10

    return average + max(relative_separation, observed_separation)


def comparison_tolerance(price_step: float) -> float:
    """Return a small price hysteresis derived from UI precision."""

    return max(0.0, float(price_step)) * 0.5
