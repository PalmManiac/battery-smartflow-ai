"""Tests for the central provider-independent EconomicsEngine."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.economics import (
    EconomicEnergyFlows,
    EconomicsEngine,
)
from custom_components.battery_smartflow_ai.market_price.models import (
    MarketPrice,
    MarketPriceDirection,
    MarketPriceValidity,
)


def _price(direction: MarketPriceDirection, value: float) -> MarketPrice:
    return MarketPrice(
        direction=direction,
        current_price=value,
        currency="EUR",
        unit="EUR/kWh",
        timestamp=datetime(2026, 8, 22, 12, tzinfo=UTC),
        source="normalized_test_source",
        validity=MarketPriceValidity.VALID,
        is_dynamic=True,
        is_fallback=False,
    )


def test_engine_calculates_central_values_and_weighted_averages() -> None:
    engine = EconomicsEngine(currency="EUR")

    engine.record(
        flows=EconomicEnergyFlows(
            grid_to_battery_kwh=2.0,
            pv_to_battery_kwh=1.0,
            grid_export_kwh=3.0,
            battery_to_home_kwh=1.5,
            battery_to_grid_kwh=0.5,
        ),
        import_price=_price(MarketPriceDirection.IMPORT, 0.30),
        export_price=_price(MarketPriceDirection.EXPORT, 0.10),
    )
    engine.record(
        flows=EconomicEnergyFlows(
            grid_to_battery_kwh=1.0,
            pv_to_battery_kwh=2.0,
            grid_export_kwh=1.0,
            battery_to_home_kwh=0.5,
        ),
        import_price=_price(MarketPriceDirection.IMPORT, 0.60),
        export_price=_price(MarketPriceDirection.EXPORT, 0.20),
    )

    result = engine.daily_snapshot()
    assert result.grid_charge_cost == pytest.approx(1.20)
    assert result.pv_opportunity_cost == pytest.approx(0.50)
    assert result.export_revenue == pytest.approx(0.50)
    assert result.avoided_grid_import_cost == pytest.approx(0.75)
    assert result.battery_benefit == pytest.approx(-0.90)
    assert result.average_grid_charge_price == pytest.approx(0.40)
    assert result.average_pv_opportunity_value == pytest.approx(1 / 6)
    assert result.average_export_price == pytest.approx(0.125)
    assert result.average_battery_discharge_value == pytest.approx(0.32)
    assert result.as_dict()["currency"] == "EUR"
    assert engine.total_snapshot() == result


def test_daily_reset_preserves_total_values() -> None:
    engine = EconomicsEngine(currency="EUR")
    engine.record(
        flows=EconomicEnergyFlows(grid_to_battery_kwh=1.0),
        import_price=_price(MarketPriceDirection.IMPORT, 0.25),
        export_price=_price(MarketPriceDirection.EXPORT, 0.08),
    )

    engine.reset_daily()

    assert engine.daily_snapshot().grid_charge_cost == 0.0
    assert engine.daily_snapshot().average_grid_charge_price is None
    assert engine.total_snapshot().grid_charge_cost == pytest.approx(0.25)


def test_negative_prices_remain_valid_economic_values() -> None:
    engine = EconomicsEngine(currency="EUR")
    engine.record(
        flows=EconomicEnergyFlows(
            grid_to_battery_kwh=1.0,
            pv_to_battery_kwh=1.0,
        ),
        import_price=_price(MarketPriceDirection.IMPORT, -0.05),
        export_price=_price(MarketPriceDirection.EXPORT, -0.02),
    )

    result = engine.daily_snapshot()
    assert result.grid_charge_cost == pytest.approx(-0.05)
    assert result.pv_opportunity_cost == pytest.approx(-0.02)
    assert result.battery_benefit == pytest.approx(0.07)


@pytest.mark.parametrize("value", [-1.0, float("inf"), float("nan")])
def test_energy_flows_reject_invalid_values(value: float) -> None:
    with pytest.raises(ValueError):
        EconomicEnergyFlows(grid_to_battery_kwh=value)


def test_engine_rejects_non_normalized_or_invalid_prices() -> None:
    engine = EconomicsEngine(currency="EUR")
    invalid_export = replace(
        _price(MarketPriceDirection.EXPORT, 0.10),
        validity=MarketPriceValidity.MISSING,
        current_price=None,
    )

    with pytest.raises(ValueError, match="export market price is not valid"):
        engine.record(
            flows=EconomicEnergyFlows(pv_to_battery_kwh=1.0),
            import_price=_price(MarketPriceDirection.IMPORT, 0.30),
            export_price=invalid_export,
        )


def test_unused_missing_price_does_not_block_independent_accounting() -> None:
    engine = EconomicsEngine(currency="EUR")
    missing_export = replace(
        _price(MarketPriceDirection.EXPORT, 0.10),
        validity=MarketPriceValidity.MISSING,
        current_price=None,
    )

    engine.record(
        flows=EconomicEnergyFlows(grid_to_battery_kwh=1.0),
        import_price=_price(MarketPriceDirection.IMPORT, 0.30),
        export_price=missing_export,
    )

    assert engine.daily_snapshot().grid_charge_cost == pytest.approx(0.30)


def test_grid_flows_use_each_intervals_historic_prices() -> None:
    engine = EconomicsEngine(currency="EUR")
    engine.record_grid_flows(
        flows=EconomicEnergyFlows(
            grid_to_battery_kwh=1.0,
            pv_to_battery_kwh=2.0,
            grid_export_kwh=1.0,
            battery_to_home_kwh=0.5,
        ),
        import_price=_price(MarketPriceDirection.IMPORT, 0.20),
        export_price=_price(MarketPriceDirection.EXPORT, 0.10),
    )
    engine.record_grid_flows(
        flows=EconomicEnergyFlows(
            grid_to_battery_kwh=2.0,
            pv_to_battery_kwh=1.0,
            grid_export_kwh=2.0,
            battery_to_home_kwh=1.0,
        ),
        import_price=_price(MarketPriceDirection.IMPORT, 0.50),
        export_price=_price(MarketPriceDirection.EXPORT, -0.05),
    )

    result = engine.total_snapshot()
    assert result.grid_charge_cost == pytest.approx(1.20)
    assert result.export_revenue == pytest.approx(0.0)
    assert result.avoided_grid_import_cost == pytest.approx(0.60)
    assert result.average_grid_charge_price == pytest.approx(0.40)
    assert result.average_export_price == pytest.approx(0.0)
    assert result.average_battery_discharge_value == pytest.approx(0.40)
    # PV charge belongs to #249 and must not leak into the #248 booking path.
    assert result.pv_opportunity_cost == 0.0
    assert result.battery_benefit == 0.0


def test_grid_flows_can_split_daily_and_total_midnight_energy() -> None:
    engine = EconomicsEngine(currency="EUR")
    engine.record_grid_flows(
        flows=EconomicEnergyFlows(grid_export_kwh=0.02),
        daily_flows=EconomicEnergyFlows(grid_export_kwh=0.01),
        import_price=_price(MarketPriceDirection.IMPORT, 0.30),
        export_price=_price(MarketPriceDirection.EXPORT, 0.10),
    )

    assert engine.daily_snapshot().export_revenue == pytest.approx(0.001)
    assert engine.total_snapshot().export_revenue == pytest.approx(0.002)


def test_grid_economics_state_survives_restart() -> None:
    engine = EconomicsEngine(currency="EUR")
    engine.record_grid_flows(
        flows=EconomicEnergyFlows(grid_to_battery_kwh=2.0),
        import_price=_price(MarketPriceDirection.IMPORT, 0.25),
        export_price=_price(MarketPriceDirection.EXPORT, 0.10),
    )

    restored = EconomicsEngine.from_state(engine.to_state(), currency="EUR")

    assert restored.daily_snapshot().grid_charge_cost == pytest.approx(0.50)
    assert restored.total_snapshot().grid_charge_cost == pytest.approx(0.50)


def test_economics_state_is_not_restored_for_another_currency() -> None:
    engine = EconomicsEngine(currency="EUR")
    engine.record_grid_flows(
        flows=EconomicEnergyFlows(grid_to_battery_kwh=2.0),
        import_price=_price(MarketPriceDirection.IMPORT, 0.25),
        export_price=_price(MarketPriceDirection.EXPORT, 0.10),
    )

    restored = EconomicsEngine.from_state(engine.to_state(), currency="USD")

    assert restored.total_snapshot().grid_charge_cost == 0.0
