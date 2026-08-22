"""End-to-end price scaling scenarios for V4.5.0."""

from __future__ import annotations

from dataclasses import replace
import unittest

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.charge_economics import (  # noqa: E402
    classify_charge_pricing,
)
from custom_components.battery_smartflow_ai.decision_engine import (  # noqa: E402
    DecisionContext,
    DecisionEngine,
    PricePoint,
)
from custom_components.battery_smartflow_ai.learned_planning import (  # noqa: E402
    LearnedSlotModel,
    LearningReadiness,
    build_learned_charge_plan,
)
from test_dev9_scenarios import (  # noqa: E402
    NOW,
    PROFILE,
    context,
    export_market_price,
    import_market_price,
    price_points,
)


def _scaled_optional(value: float | None, factor: float) -> float | None:
    return None if value is None else float(value) * factor


def scale_price_context(ctx: DecisionContext, factor: float) -> DecisionContext:
    """Scale every monetary price input while preserving physical inputs."""

    source_points = list(ctx.import_market_price.forecast.points)
    scaled_points = [
        PricePoint(point.start, point.end, float(point.price) * factor)
        for point in source_points
    ]
    import_price_now = ctx.import_market_price.current_price
    export_price_now = ctx.export_market_price.current_price
    return replace(
        ctx,
        avg_charge_price=_scaled_optional(ctx.avg_charge_price, factor),
        expensive_threshold=float(ctx.expensive_threshold) * factor,
        very_expensive_threshold=float(ctx.very_expensive_threshold) * factor,
        very_cheap_price=_scaled_optional(ctx.very_cheap_price, factor),
        import_market_price=import_market_price(
            _scaled_optional(import_price_now, factor),
            scaled_points,
        ),
        export_market_price=export_market_price(
            _scaled_optional(export_price_now, factor)
        ),
    )


def assert_scaled_result(
    case: unittest.TestCase,
    eur_result,
    scaled_result,
    factor: float,
) -> None:
    """Assert identical decisions and proportionally scaled diagnostics."""

    case.assertEqual(eur_result.action, scaled_result.action)
    case.assertEqual(eur_result.ac_mode, scaled_result.ac_mode)
    case.assertEqual(eur_result.reason, scaled_result.reason)
    case.assertEqual(eur_result.charge_w, scaled_result.charge_w)
    case.assertEqual(eur_result.discharge_w, scaled_result.discharge_w)
    case.assertEqual(eur_result.target_soc, scaled_result.target_soc)

    for field in (
        "current_peak_threshold",
        "current_valley_threshold",
        "economic_discharge_threshold",
        "effective_discharge_threshold",
    ):
        eur_value = getattr(eur_result, field)
        scaled_value = getattr(scaled_result, field)
        if eur_value is None:
            case.assertIsNone(scaled_value)
        else:
            case.assertAlmostEqual(scaled_value, eur_value * factor)


class CurrencyScaledDecisionScenarios(unittest.TestCase):
    def assert_engine_scale_invariant(
        self,
        base_context: DecisionContext,
        factor: float,
    ) -> None:
        eur_result = DecisionEngine().evaluate(base_context)
        scaled_result = DecisionEngine().evaluate(
            scale_price_context(base_context, factor)
        )
        assert_scaled_result(self, eur_result, scaled_result, factor)

    def test_peak_and_economic_discharge_scale_to_dkk(self) -> None:
        self.assert_engine_scale_invariant(
            context(
                price_now=0.45,
                avg_charge_price=0.10,
                automatic_planning_allowed=False,
            ),
            10.0,
        )

    def test_valley_charge_scale_to_dkk(self) -> None:
        self.assert_engine_scale_invariant(
            context(
                price_now=0.10,
                grid_import_w=0.0,
                automatic_valley_charge_allowed=True,
                automatic_planning_allowed=False,
            ),
            10.0,
        )

    def test_very_cheap_negative_price_scale_to_czk(self) -> None:
        negative_points = [
            replace(point, price=point.price - 0.20)
            for point in price_points()
        ]
        self.assert_engine_scale_invariant(
            context(
                price_now=-0.10,
                price_points=negative_points,
                very_cheap_price=-0.05,
                avg_charge_price=0.10,
                automatic_planning_allowed=False,
            ),
            25.0,
        )

    def test_neutral_price_state_scale_to_pln(self) -> None:
        self.assert_engine_scale_invariant(
            context(
                price_now=0.25,
                automatic_planning_allowed=False,
                automatic_valley_charge_allowed=False,
            ),
            4.5,
        )

    def test_all_required_currencies_keep_the_same_strategy_decision(self) -> None:
        base_context = context(
            price_now=0.45,
            avg_charge_price=0.10,
            automatic_planning_allowed=False,
        )
        nominal_factors = {
            "EUR": 1.0,
            "DKK": 10.0,
            "CHF": 1.1,
            "SEK": 11.0,
            "NOK": 12.0,
            "GBP": 0.85,
            "CZK": 25.0,
            "PLN": 4.5,
        }

        for currency, factor in nominal_factors.items():
            with self.subTest(currency=currency):
                self.assert_engine_scale_invariant(base_context, factor)


class CurrencyScaledEconomicsScenarios(unittest.TestCase):
    def test_mixed_grid_pv_price_scales_without_changing_source(self) -> None:
        eur = classify_charge_pricing(
            grid_import_w=400.0,
            grid_export_w=0.0,
            decision_charge_w=1000.0,
            decision_ac_mode="input",
            price_now=0.30,
            feed_in_tariff=0.12,
            battery_charge_w=1000.0,
            decision_reason="valley_opportunity_charge",
        )
        dkk = classify_charge_pricing(
            grid_import_w=400.0,
            grid_export_w=0.0,
            decision_charge_w=1000.0,
            decision_ac_mode="input",
            price_now=3.0,
            feed_in_tariff=1.2,
            battery_charge_w=1000.0,
            decision_reason="valley_opportunity_charge",
        )

        self.assertEqual(eur.source, dkk.source)
        self.assertEqual(eur.is_grid_charge, dkk.is_grid_charge)
        self.assertEqual(eur.grid_part_w, dkk.grid_part_w)
        self.assertEqual(eur.pv_part_w, dkk.pv_part_w)
        self.assertAlmostEqual(dkk.price_per_kwh, eur.price_per_kwh * 10.0)


class CurrencyScaledLearnedPlanningScenarios(unittest.TestCase):
    def test_learned_plan_selection_is_scale_invariant(self) -> None:
        model = LearnedSlotModel(
            slot_kwh=[0.05] * 96,
            slot_sample_count=[7] * 96,
            data_coverage=1.0,
            history_days=7,
            usable_days=7,
            night_window_days=7,
            morning_window_days=7,
            evening_window_days=7,
        )
        readiness = LearningReadiness(
            status="ready",
            history_days=7,
            usable_days=7,
            night_window_days=7,
            morning_window_days=7,
            evening_window_days=7,
            data_coverage=1.0,
        )

        def build(points: list[PricePoint]):
            return build_learned_charge_plan(
                model=model,
                readiness=readiness,
                now=NOW,
                market_price=import_market_price(points[0].price, points),
                forecast=None,
                total_battery_capacity_kwh=5.76,
                current_soc=5.0,
                soc_min=5.0,
                soc_max=100.0,
                profile_charge_limit_w=2400.0,
                current_effective_charge_cap_w=2400.0,
                learned_typical_charge_power_w=1161.0,
            )

        eur = build(price_points())
        scaled = build(
            [replace(point, price=point.price * 10.0) for point in price_points()]
        )

        self.assertEqual(eur.mode, scaled.mode)
        self.assertEqual(eur.decision_reason, scaled.decision_reason)
        self.assertEqual(eur.optimal_charge_start, scaled.optimal_charge_start)
        self.assertEqual(eur.optimal_charge_end, scaled.optimal_charge_end)
        self.assertEqual(eur.requested_charge_power_w, scaled.requested_charge_power_w)
        self.assertEqual(
            scaled.selected_prices,
            [round(value * 10.0, 6) for value in eur.selected_prices],
        )
        self.assertAlmostEqual(
            scaled.acceptable_charge_price_per_kwh,
            eur.acceptable_charge_price_per_kwh * 10.0,
        )


if __name__ == "__main__":
    unittest.main()
