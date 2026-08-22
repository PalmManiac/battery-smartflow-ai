"""Tests for time-based and persistent economic energy accumulation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.economics import (  # noqa: E402
    EconomicPowerFlows,
    EnergyAccumulator,
)


NOW = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)


def test_real_elapsed_time_converts_each_power_direction_to_energy() -> None:
    accumulator = EnergyAccumulator()
    power = EconomicPowerFlows(
        grid_to_battery_w=1800.0,
        pv_to_battery_w=900.0,
        grid_export_w=360.0,
        battery_to_home_w=720.0,
        battery_to_grid_w=180.0,
    )

    assert accumulator.add_sample(sampled_at=NOW, power=power).status == "baseline"
    result = accumulator.add_sample(
        sampled_at=NOW + timedelta(seconds=20), power=power
    )

    assert result.elapsed_seconds == 20.0
    assert result.accounted_seconds == 20.0
    assert result.energy.grid_to_battery_kwh == pytest.approx(0.01)
    assert result.energy.pv_to_battery_kwh == pytest.approx(0.005)
    assert result.energy.grid_export_kwh == pytest.approx(0.002)
    assert result.energy.battery_to_home_kwh == pytest.approx(0.004)
    assert result.energy.battery_to_grid_kwh == pytest.approx(0.001)
    assert accumulator.snapshot().daily == result.energy
    assert accumulator.snapshot().total == result.energy


def test_duplicate_and_out_of_order_samples_are_not_counted() -> None:
    accumulator = EnergyAccumulator()
    power = EconomicPowerFlows(grid_to_battery_w=1000.0)
    accumulator.add_sample(sampled_at=NOW, power=power)

    duplicate = accumulator.add_sample(sampled_at=NOW, power=power)
    older = accumulator.add_sample(
        sampled_at=NOW - timedelta(seconds=5), power=power
    )
    counted = accumulator.add_sample(
        sampled_at=NOW + timedelta(seconds=10), power=power
    )

    assert duplicate.status == "duplicate_or_out_of_order"
    assert older.status == "duplicate_or_out_of_order"
    assert counted.accounted_seconds == 10.0
    assert accumulator.snapshot().total.grid_to_battery_kwh == pytest.approx(
        10 / 3600
    )


def test_large_gap_is_limited_instead_of_backfilled() -> None:
    accumulator = EnergyAccumulator(max_interval_seconds=60.0)
    power = EconomicPowerFlows(grid_export_w=1000.0)
    accumulator.add_sample(sampled_at=NOW, power=power)

    result = accumulator.add_sample(
        sampled_at=NOW + timedelta(hours=2), power=power
    )

    assert result.status == "gap_limited"
    assert result.elapsed_seconds == 7200.0
    assert result.accounted_seconds == 60.0
    assert result.energy.grid_export_kwh == pytest.approx(1 / 60)


def test_midnight_interval_resets_daily_but_preserves_total() -> None:
    accumulator = EnergyAccumulator()
    before_midnight = datetime(2026, 8, 22, 23, 59, 50, tzinfo=UTC)
    power = EconomicPowerFlows(battery_to_home_w=3600.0)
    accumulator.add_sample(sampled_at=before_midnight, power=power)

    accumulator.add_sample(
        sampled_at=before_midnight + timedelta(seconds=20), power=power
    )

    snapshot = accumulator.snapshot()
    assert snapshot.day.isoformat() == "2026-08-23"
    assert snapshot.daily.battery_to_home_kwh == pytest.approx(0.01)
    assert snapshot.total.battery_to_home_kwh == pytest.approx(0.02)


def test_persisted_totals_survive_restart_without_counting_downtime() -> None:
    accumulator = EnergyAccumulator()
    power = EconomicPowerFlows(pv_to_battery_w=1800.0)
    accumulator.add_sample(sampled_at=NOW, power=power)
    accumulator.add_sample(
        sampled_at=NOW + timedelta(seconds=20), power=power
    )
    state = accumulator.to_state()

    restored = EnergyAccumulator.from_state(state)
    baseline = restored.add_sample(
        sampled_at=NOW + timedelta(hours=3), power=power
    )

    assert baseline.status == "baseline"
    assert restored.snapshot().total.pv_to_battery_kwh == pytest.approx(0.01)
    assert restored.snapshot().daily.pv_to_battery_kwh == pytest.approx(0.01)

    restored.add_sample(
        sampled_at=NOW + timedelta(hours=3, seconds=10), power=power
    )
    assert restored.snapshot().total.pv_to_battery_kwh == pytest.approx(0.015)


def test_first_sample_on_new_day_resets_restored_daily_values() -> None:
    accumulator = EnergyAccumulator()
    power = EconomicPowerFlows(grid_to_battery_w=3600.0)
    accumulator.add_sample(sampled_at=NOW, power=power)
    accumulator.add_sample(sampled_at=NOW + timedelta(seconds=10), power=power)

    restored = EnergyAccumulator.from_state(accumulator.to_state())
    restored.add_sample(sampled_at=NOW + timedelta(days=1), power=power)

    assert restored.snapshot().daily.grid_to_battery_kwh == 0.0
    assert restored.snapshot().total.grid_to_battery_kwh == pytest.approx(0.01)


def test_corrupt_state_falls_back_to_empty_accumulator() -> None:
    restored = EnergyAccumulator.from_state(
        {
            "version": 1,
            "day": "not-a-date",
            "daily": {},
            "total": {"grid_export_kwh": -1.0},
        }
    )

    result = restored.add_sample(sampled_at=NOW, power=EconomicPowerFlows())
    assert result.status == "baseline"
    assert restored.snapshot().total.grid_export_kwh == 0.0
