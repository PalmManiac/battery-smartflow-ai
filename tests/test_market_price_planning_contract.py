"""Contracts proving planning consumes only canonical market price data."""

from __future__ import annotations

from dataclasses import fields, replace
from datetime import timedelta
from pathlib import Path
import unittest

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.decision_engine import (  # noqa: E402
    DecisionContext,
    DecisionEngine,
)
from custom_components.battery_smartflow_ai.market_price import (  # noqa: E402
    MarketPrice,
    MarketPriceDirection,
    MarketPriceForecast,
    MarketPriceValidity,
    planning_price_points,
)
from test_dev9_scenarios import (  # noqa: E402
    NOW,
    context,
    import_market_price,
    price_points,
    export_market_price,
)


class MarketPricePlanningContractTests(unittest.TestCase):
    def test_decision_context_has_only_canonical_market_price_inputs(self) -> None:
        field_names = {field.name for field in fields(DecisionContext)}

        self.assertIn("import_market_price", field_names)
        self.assertIn("export_market_price", field_names)
        self.assertNotIn("price_now", field_names)
        self.assertNotIn("price_points", field_names)
        self.assertNotIn("feed_in_tariff", field_names)

    def test_import_and_export_prices_remain_directionally_separate(self) -> None:
        ctx = context(
            import_market_price=import_market_price(0.22, price_points()),
            export_market_price=export_market_price(-0.04),
        )
        engine = DecisionEngine()

        self.assertEqual(engine._current_import_price(ctx), 0.22)
        self.assertEqual(engine._current_export_price(ctx), -0.04)

    def test_classic_planning_ignores_conflicting_legacy_price_fields(self) -> None:
        canonical = import_market_price(0.10, price_points())
        ctx = context(
            battery_capacity_kwh=10.0,
            soc=20.0,
            price_now=99.0,
            price_points=[],
            import_market_price=canonical,
        )

        result = DecisionEngine()._evaluate_adaptive_planning(ctx)

        self.assertIsNotNone(result)
        self.assertEqual(result.reason, "planning_latest_start")

    def test_classic_planning_does_not_fall_back_to_legacy_price_fields(self) -> None:
        missing = MarketPrice(
            direction=MarketPriceDirection.IMPORT,
            current_price=None,
            currency="EUR",
            unit="EUR/kWh",
            timestamp=NOW,
            source="test.missing",
            validity=MarketPriceValidity.MISSING,
            is_dynamic=True,
            is_fallback=False,
            forecast=MarketPriceForecast.empty(timestamp=NOW),
        )
        ctx = context(
            battery_capacity_kwh=10.0,
            soc=20.0,
            price_now=0.10,
            price_points=price_points(),
            import_market_price=missing,
        )

        result = DecisionEngine()._evaluate_adaptive_planning(ctx)

        self.assertIsNone(result)

    def test_export_market_context_is_not_accepted_for_import_planning(self) -> None:
        export_price = replace(
            import_market_price(0.10, price_points()),
            direction=MarketPriceDirection.EXPORT,
        )
        ctx = context(
            battery_capacity_kwh=10.0,
            soc=20.0,
            import_market_price=export_price,
        )

        self.assertIsNone(DecisionEngine()._evaluate_adaptive_planning(ctx))

    def test_hourly_market_intervals_become_quarter_hour_planning_slots(self) -> None:
        hourly_point = replace(
            price_points()[0],
            end=NOW + timedelta(hours=1),
            price=-0.02,
        )
        market_price = import_market_price(0.10, [hourly_point])

        slots = planning_price_points(market_price)

        self.assertEqual(len(slots), 4)
        self.assertTrue(
            all(slot.end - slot.start == timedelta(minutes=15) for slot in slots)
        )
        self.assertTrue(all(slot.price == -0.02 for slot in slots))

    def test_planning_slot_view_preserves_gaps_and_drops_partial_fragments(self) -> None:
        points = [
            replace(
                price_points()[0],
                start=NOW,
                end=NOW + timedelta(minutes=30),
            ),
            replace(
                price_points()[0],
                start=NOW + timedelta(hours=1),
                end=NOW + timedelta(hours=1, minutes=20),
            ),
        ]

        slots = planning_price_points(import_market_price(0.10, points))

        self.assertEqual(len(slots), 3)
        self.assertEqual(slots[1].end, NOW + timedelta(minutes=30))
        self.assertEqual(slots[2].start, NOW + timedelta(hours=1))
        self.assertEqual(slots[2].end, NOW + timedelta(hours=1, minutes=15))

    def test_learned_planner_public_boundary_is_market_price(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "custom_components"
            / "battery_smartflow_ai"
            / "learned_planning.py"
        ).read_text(encoding="utf-8")

        signature = source.split("def build_learned_charge_plan(", 1)[1].split(
            ") -> LearnedChargePlan:",
            1,
        )[0]
        self.assertIn("market_price: MarketPrice", signature)
        self.assertNotIn("price_points:", signature)
        self.assertNotIn("from .decision_engine import PricePoint", source)


if __name__ == "__main__":
    unittest.main()
