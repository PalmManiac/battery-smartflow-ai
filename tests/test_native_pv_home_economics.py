"""Regression tests for direct native PV self-consumption accounting."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import unittest

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.economics import (  # noqa: E402
    EconomicEnergyFlows,
    EconomicPowerFlows,
    EconomicsEngine,
    EnergyAccumulator,
    direct_native_pv_to_home_power,
    priceable_energy_flows,
)
from custom_components.battery_smartflow_ai.market_price import (  # noqa: E402
    MarketPrice,
    MarketPriceDirection,
    MarketPriceValidity,
)


NOW = datetime(2026, 9, 14, 12, tzinfo=UTC)


def _price(
    value: float | None,
    *,
    direction: MarketPriceDirection,
) -> MarketPrice:
    return MarketPrice(
        direction=direction,
        current_price=value,
        currency="EUR",
        unit="EUR/kWh",
        timestamp=NOW,
        source="test.price",
        validity=(
            MarketPriceValidity.VALID
            if value is not None
            else MarketPriceValidity.MISSING
        ),
        is_dynamic=True,
        is_fallback=False,
    )


class NativePvHomeEconomicsTests(unittest.TestCase):
    def test_direct_pv_excludes_battery_charge_and_discharge(self) -> None:
        result = direct_native_pv_to_home_power(
            native_pv_w=1200.0,
            native_pv_to_battery_w=300.0,
            ac_output_w=1100.0,
            battery_discharge_w=200.0,
        )

        self.assertEqual(result, 900.0)

    def test_direct_pv_is_bounded_by_each_physical_side(self) -> None:
        self.assertEqual(
            direct_native_pv_to_home_power(
                native_pv_w=500.0,
                native_pv_to_battery_w=400.0,
                ac_output_w=900.0,
                battery_discharge_w=0.0,
            ),
            100.0,
        )
        self.assertEqual(
            direct_native_pv_to_home_power(
                native_pv_w=900.0,
                native_pv_to_battery_w=0.0,
                ac_output_w=500.0,
                battery_discharge_w=200.0,
            ),
            300.0,
        )

    def test_energy_accumulator_integrates_direct_pv_once(self) -> None:
        accumulator = EnergyAccumulator()
        power = EconomicPowerFlows(native_pv_to_home_w=1800.0)
        accumulator.add_sample(sampled_at=NOW, power=power)

        result = accumulator.add_sample(
            sampled_at=NOW + timedelta(seconds=20), power=power
        )

        self.assertAlmostEqual(result.energy.native_pv_to_home_kwh, 0.01)
        self.assertAlmostEqual(
            accumulator.snapshot().total.native_pv_to_home_kwh, 0.01
        )

    def test_interval_uses_current_import_price_without_battery_double_count(self) -> None:
        engine = EconomicsEngine(currency="EUR")
        flow = EconomicEnergyFlows(native_pv_to_home_kwh=0.5)
        engine.record_grid_flows(
            flows=flow,
            import_price=_price(0.40, direction=MarketPriceDirection.IMPORT),
            export_price=_price(0.08, direction=MarketPriceDirection.EXPORT),
        )

        snapshot = engine.total_snapshot()
        self.assertAlmostEqual(snapshot.native_pv_self_consumption_value, 0.20)
        self.assertEqual(snapshot.avoided_grid_import_cost, 0.0)
        self.assertEqual(snapshot.battery_benefit, 0.0)
        self.assertEqual(snapshot.export_revenue, 0.0)

    def test_missing_import_price_skips_value_but_keeps_physical_energy(self) -> None:
        physical = EconomicEnergyFlows(native_pv_to_home_kwh=0.25)
        priceable = priceable_energy_flows(
            physical,
            import_price=_price(None, direction=MarketPriceDirection.IMPORT),
            export_price=_price(0.08, direction=MarketPriceDirection.EXPORT),
        )

        self.assertEqual(priceable.flows.native_pv_to_home_kwh, 0.0)
        self.assertEqual(physical.native_pv_to_home_kwh, 0.25)


if __name__ == "__main__":
    unittest.main()
