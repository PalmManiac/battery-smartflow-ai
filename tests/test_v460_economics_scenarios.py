"""End-to-end V4.6 market-price, energy and economics scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.economics import (  # noqa: E402
    EconomicPowerFlows,
    EconomicsEngine,
    EnergyAccumulator,
)
from custom_components.battery_smartflow_ai.market_price import (  # noqa: E402
    ExportMarketPriceResolver,
    MarketPrice,
    MarketPriceDirection,
    MarketPriceValidity,
    normalize_price_value,
)


NOW = datetime(2026, 8, 22, 12, tzinfo=UTC)


def _price(direction: MarketPriceDirection, value: float) -> MarketPrice:
    return MarketPrice(
        direction=direction,
        current_price=value,
        currency="EUR",
        unit="EUR/kWh",
        timestamp=NOW,
        source="scenario",
        validity=MarketPriceValidity.VALID,
        is_dynamic=True,
        is_fallback=False,
    )


def _book(
    engine: EconomicsEngine,
    energy,
    *,
    import_value: float,
    export_value: float,
    daily_energy=None,
) -> None:
    import_price = _price(MarketPriceDirection.IMPORT, import_value)
    export_price = _price(MarketPriceDirection.EXPORT, export_value)
    engine.record_grid_flows(
        flows=energy,
        daily_flows=daily_energy,
        import_price=import_price,
        export_price=export_price,
    )
    engine.record_battery_value_flows(
        flows=energy,
        daily_flows=daily_energy,
        import_price=import_price,
        export_price=export_price,
    )


def _one_hour(power: EconomicPowerFlows):
    accumulator = EnergyAccumulator(max_interval_seconds=3600)
    accumulator.add_sample(sampled_at=NOW, power=power)
    return accumulator.add_sample(
        sampled_at=NOW + timedelta(hours=1), power=power
    ).energy


def test_pure_grid_charge_uses_interval_import_price() -> None:
    energy = _one_hour(EconomicPowerFlows(grid_to_battery_w=1000))
    engine = EconomicsEngine(currency="EUR")
    _book(engine, energy, import_value=0.25, export_value=0.08)

    result = engine.total_snapshot()
    assert result.grid_charge_cost == pytest.approx(0.25)
    assert result.pv_opportunity_cost == 0.0
    assert result.battery_benefit == pytest.approx(-0.25)


def test_pure_pv_charge_uses_negative_export_opportunity_price() -> None:
    energy = _one_hour(EconomicPowerFlows(pv_to_battery_w=1000))
    engine = EconomicsEngine(currency="EUR")
    _book(engine, energy, import_value=0.30, export_value=-0.04)

    result = engine.total_snapshot()
    assert result.pv_opportunity_cost == pytest.approx(-0.04)
    assert result.battery_benefit == pytest.approx(0.04)


def test_mixed_charge_keeps_grid_and_pv_costs_separate() -> None:
    energy = _one_hour(
        EconomicPowerFlows(grid_to_battery_w=600, pv_to_battery_w=400)
    )
    engine = EconomicsEngine(currency="EUR")
    _book(engine, energy, import_value=0.30, export_value=0.10)

    result = engine.total_snapshot()
    assert result.grid_charge_cost == pytest.approx(0.18)
    assert result.pv_opportunity_cost == pytest.approx(0.04)
    assert result.battery_benefit == pytest.approx(-0.22)
    assert result.average_grid_charge_price == pytest.approx(0.30)
    assert result.average_pv_opportunity_value == pytest.approx(0.10)


def test_battery_house_supply_and_export_are_attributed_once() -> None:
    energy = _one_hour(
        EconomicPowerFlows(
            grid_export_w=800,
            battery_to_home_w=500,
            battery_to_grid_w=200,
        )
    )
    engine = EconomicsEngine(currency="EUR")
    _book(engine, energy, import_value=0.40, export_value=0.10)

    result = engine.total_snapshot()
    assert result.avoided_grid_import_cost == pytest.approx(0.20)
    assert result.export_revenue == pytest.approx(0.08)
    # Only 0.2 kWh of battery export, not all 0.8 kWh export, adds benefit.
    assert result.battery_benefit == pytest.approx(0.22)


@dataclass
class _State:
    state: object
    attributes: dict[str, object]
    last_updated: datetime = NOW


def test_dynamic_export_zero_and_static_fallback_reach_economics() -> None:
    states = {
        "sensor.export": _State("0", {"unit_of_measurement": "EUR/kWh"})
    }
    dynamic_zero = ExportMarketPriceResolver(
        state_getter=states.get,
        active_currency="EUR",
        dynamic_entity_id="sensor.export",
        static_value=0.08,
        static_configured=True,
        now=NOW,
    ).resolve()
    states["sensor.export"] = _State("unavailable", {})
    fallback = ExportMarketPriceResolver(
        state_getter=states.get,
        active_currency="EUR",
        dynamic_entity_id="sensor.export",
        static_value=0.08,
        static_configured=True,
        now=NOW,
    ).resolve()

    assert dynamic_zero.current_price == 0.0
    assert dynamic_zero.is_dynamic
    assert fallback.current_price == pytest.approx(0.08)
    assert fallback.is_fallback


@pytest.mark.parametrize(
    ("raw", "unit", "expected"),
    [
        (0.25, "EUR/kWh", 0.25),
        (25.0, "ct/kWh", 0.25),
        (250.0, "EUR/MWh", 0.25),
        (-5.0, "ct/kWh", -0.05),
        (0.0, "EUR/MWh", 0.0),
    ],
)
def test_supported_price_units_feed_the_same_canonical_economics(
    raw: float, unit: str, expected: float
) -> None:
    normalized = normalize_price_value(
        raw, unit=unit, currency="EUR", active_currency="EUR"
    )
    assert normalized.validity is MarketPriceValidity.VALID
    assert normalized.value == pytest.approx(expected)


def test_restart_preserves_totals_without_booking_offline_gap_twice() -> None:
    power = EconomicPowerFlows(grid_to_battery_w=1800)
    accumulator = EnergyAccumulator(max_interval_seconds=300)
    engine = EconomicsEngine(currency="EUR")
    accumulator.add_sample(sampled_at=NOW, power=power)
    first = accumulator.add_sample(
        sampled_at=NOW + timedelta(seconds=20), power=power
    )
    _book(engine, first.energy, import_value=0.30, export_value=0.10)

    restored_accumulator = EnergyAccumulator.from_state(accumulator.to_state())
    restored_engine = EconomicsEngine.from_state(engine.to_state(), currency="EUR")
    baseline = restored_accumulator.add_sample(
        sampled_at=NOW + timedelta(hours=4), power=power
    )
    _book(restored_engine, baseline.energy, import_value=0.50, export_value=0.10)

    assert baseline.status == "baseline"
    assert restored_accumulator.snapshot().total.grid_to_battery_kwh == pytest.approx(
        0.01
    )
    assert restored_engine.total_snapshot().grid_charge_cost == pytest.approx(0.003)


def test_midnight_keeps_total_and_books_only_new_day_share_as_daily() -> None:
    accumulator = EnergyAccumulator(max_interval_seconds=300)
    engine = EconomicsEngine(currency="EUR")
    start = datetime(2026, 8, 22, 23, 59, 50, tzinfo=UTC)
    power = EconomicPowerFlows(grid_export_w=3600)
    accumulator.add_sample(sampled_at=start, power=power)
    interval = accumulator.add_sample(
        sampled_at=start + timedelta(seconds=20), power=power
    )
    engine.reset_daily()
    _book(
        engine,
        interval.energy,
        daily_energy=interval.daily_energy,
        import_value=0.30,
        export_value=0.10,
    )

    assert engine.daily_snapshot().export_revenue == pytest.approx(0.001)
    assert engine.total_snapshot().export_revenue == pytest.approx(0.002)
