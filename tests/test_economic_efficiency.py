"""Tests for the BSFAI economic efficiency sensor calculation."""

from __future__ import annotations

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.economic_efficiency import (  # noqa: E402
    economic_efficiency_pct,
)


def _efficiency(**overrides: float) -> float | None:
    values = {
        "grid_charge_cost": 1.0,
        "pv_opportunity_cost": 0.0,
        "battery_benefit": 0.0,
        "charged_energy_kwh": 1.0,
        "discharged_energy_kwh": 1.0,
    }
    values.update(overrides)
    return economic_efficiency_pct(**values)


def test_one_hundred_percent_means_cost_recovery() -> None:
    assert _efficiency(battery_benefit=0.0) == 100.0


def test_positive_battery_benefit_exceeds_one_hundred_percent() -> None:
    assert _efficiency(battery_benefit=0.3) == 130.0


def test_negative_battery_benefit_is_below_cost_recovery() -> None:
    assert _efficiency(battery_benefit=-0.1) == 90.0


def test_grid_and_pv_input_values_are_both_included() -> None:
    assert _efficiency(
        grid_charge_cost=0.6,
        pv_opportunity_cost=0.4,
        battery_benefit=0.25,
    ) == 125.0


def test_result_waits_for_meaningful_charge_and_discharge_energy() -> None:
    assert _efficiency(charged_energy_kwh=0.09) is None
    assert _efficiency(discharged_energy_kwh=0.09) is None


def test_free_or_negative_input_value_has_no_finite_recovery_ratio() -> None:
    assert _efficiency(grid_charge_cost=0.0, pv_opportunity_cost=0.0) is None
    assert _efficiency(grid_charge_cost=-0.1, pv_opportunity_cost=0.0) is None
