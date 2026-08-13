"""Dev9 regression scenarios for modes, fallbacks and optional data."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import unittest

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.const import (  # noqa: E402
    AI_MODE_AUTOMATIC,
    AI_MODE_MANUAL,
    AI_MODE_SUMMER,
    AI_MODES,
    normalize_ai_mode,
)
from custom_components.battery_smartflow_ai.decision_engine import (  # noqa: E402
    DecisionContext,
    DecisionEngine,
    LearnedPlanningRule,
    PricePoint,
)
from custom_components.battery_smartflow_ai.learned_planning import (  # noqa: E402
    LearnedSlotModel,
    LearningChargePowerSample,
    LearningReadiness,
    build_learned_charge_plan,
    learned_typical_charge_power_w,
    requested_charge_power_w,
)
from custom_components.battery_smartflow_ai.strategy_adapter import (  # noqa: E402
    decision_to_strategy_decision,
)
from custom_components.battery_smartflow_ai.strategy_state import (  # noqa: E402
    StrategicState,
    VisibleState,
)


NOW = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)

PROFILE = {
    "TARGET_IMPORT_W": 20.0,
    "TARGET_EXPORT_W": 10.0,
    "DEADBAND_W": 25.0,
    "EXPORT_GUARD_W": 80.0,
    "KP_UP": 0.5,
    "KP_DOWN": 0.7,
    "MAX_STEP_UP": 200.0,
    "MAX_STEP_DOWN": 250.0,
    "KEEPALIVE_MIN_DEFICIT_W": 40.0,
    "KEEPALIVE_MIN_OUTPUT_W": 60.0,
}


def price_points() -> list[PricePoint]:
    return [
        PricePoint(
            start=NOW,
            end=NOW + timedelta(minutes=15),
            price=0.10,
        ),
        PricePoint(
            start=NOW + timedelta(minutes=15),
            end=NOW + timedelta(minutes=30),
            price=0.12,
        ),
        PricePoint(
            start=NOW + timedelta(minutes=30),
            end=NOW + timedelta(minutes=45),
            price=0.45,
        ),
        PricePoint(
            start=NOW + timedelta(minutes=45),
            end=NOW + timedelta(minutes=60),
            price=0.40,
        ),
    ]


def context(**overrides) -> DecisionContext:
    values = {
        "now": NOW,
        "soc": 50.0,
        "soc_min": 5.0,
        "soc_max": 100.0,
        "emergency_soc": 3.0,
        "emergency_charge_w": 300.0,
        "max_charge_w": 1000.0,
        "max_discharge_w": 1000.0,
        "grid_import_w": 500.0,
        "grid_export_w": 0.0,
        "pv_w": 0.0,
        "house_load_w": 500.0,
        "price_now": 0.10,
        "avg_charge_price": 0.20,
        "expensive_threshold": 0.32,
        "very_expensive_threshold": 0.50,
        "profit_margin_pct": 15.0,
        "price_points": price_points(),
        "ai_mode": AI_MODE_AUTOMATIC,
        "manual_action": None,
        "season": "winter",
        "profile": PROFILE,
        "prev_discharge_w": 0.0,
        "prev_charge_w": 0.0,
        "battery_capacity_kwh": 2.0,
        "automatic_strategy_active": True,
        "automatic_discharge_allowed": True,
        "automatic_peak_reserve_allowed": False,
        "automatic_valley_charge_allowed": False,
        "automatic_planning_allowed": True,
    }
    values.update(overrides)
    return DecisionContext(**values)


class Dev9ModeScenarios(unittest.TestCase):
    def test_winter_is_migrated_and_no_longer_selectable(self) -> None:
        self.assertEqual(
            AI_MODES,
            [AI_MODE_AUTOMATIC, AI_MODE_SUMMER, AI_MODE_MANUAL],
        )
        self.assertEqual(normalize_ai_mode("winter"), AI_MODE_AUTOMATIC)
        self.assertEqual(normalize_ai_mode("invalid"), AI_MODE_AUTOMATIC)
        self.assertEqual(normalize_ai_mode(AI_MODE_SUMMER), AI_MODE_SUMMER)

    def test_automatic_decision_is_not_switched_by_season(self) -> None:
        engine = DecisionEngine()
        winter = engine.evaluate(context(season="winter"))
        summer = engine.evaluate(context(season="summer"))

        self.assertEqual(winter.reason, summer.reason)
        self.assertEqual(winter.action, summer.action)
        self.assertEqual(winter.charge_w, summer.charge_w)
        self.assertEqual(winter.discharge_w, summer.discharge_w)

    def test_autarky_covers_load_but_never_starts_price_planning(self) -> None:
        result = DecisionEngine().evaluate(
            context(
                ai_mode=AI_MODE_SUMMER,
                season="summer",
                automatic_planning_allowed=True,
            )
        )

        self.assertEqual(result.reason, "summer_cover_deficit")
        self.assertEqual(result.action, "discharge")
        self.assertGreater(result.discharge_w, 0.0)


class Dev9FallbackScenarios(unittest.TestCase):
    def test_invalid_grid_data_forces_safe_idle(self) -> None:
        result = DecisionEngine().evaluate(
            context(grid_sensor_valid=False)
        )
        strategy = decision_to_strategy_decision(result)

        self.assertEqual(result.reason, "grid_sensor_invalid")
        self.assertEqual(strategy.state, StrategicState.IDLE_SAFE)
        self.assertEqual(strategy.visible_state, VisibleState.SAFE_IDLE)
        self.assertEqual(strategy.requested_mode, "idle")

    def test_emergency_charge_overrides_grid_sensor_outage(self) -> None:
        result = DecisionEngine().evaluate(
            context(soc=2.0, grid_sensor_valid=False)
        )

        self.assertIn(
            result.reason,
            {"emergency_latched_charge", "cell_voltage_emergency_charge"},
        )
        self.assertEqual(result.action, "emergency")
        self.assertGreater(result.charge_w, 0.0)

    def test_invalid_soc_limits_force_safe_idle(self) -> None:
        result = DecisionEngine().evaluate(
            context(soc_limits_valid=False)
        )
        strategy = decision_to_strategy_decision(result)

        self.assertEqual(result.reason, "soc_limits_invalid")
        self.assertEqual(strategy.state, StrategicState.IDLE_SAFE)

    def test_invalid_power_limits_force_safe_idle(self) -> None:
        result = DecisionEngine().evaluate(
            context(power_limits_valid=False)
        )

        self.assertEqual(result.reason, "power_limits_invalid")
        self.assertEqual(result.action, "idle")

    def test_manual_action_remains_available_without_grid_sensor(self) -> None:
        result = DecisionEngine().evaluate(
            context(
                ai_mode=AI_MODE_MANUAL,
                manual_action="discharge",
                grid_sensor_configured=False,
                grid_sensor_valid=False,
            )
        )

        self.assertEqual(result.reason, "manual_discharge")
        self.assertEqual(result.action, "discharge")

    def test_automatic_requires_a_configured_grid_sensor(self) -> None:
        result = DecisionEngine().evaluate(
            context(
                grid_sensor_configured=False,
                grid_sensor_valid=False,
            )
        )

        self.assertEqual(result.reason, "grid_sensor_invalid")
        self.assertEqual(result.action, "idle")


class Dev9OptionalDataScenarios(unittest.TestCase):
    def test_active_learned_window_bypasses_coarse_pv_planning_gate(self) -> None:
        plan = SimpleNamespace(
            status="ready",
            mode="charge",
            decision_reason="learned_charge_window_active",
            required_charge_energy_kwh=1.5,
            requested_charge_power_w=1000.0,
        )

        result = DecisionEngine().evaluate(
            context(
                learned_planning_enabled=True,
                learned_charge_plan=plan,
                automatic_planning_allowed=False,
            )
        )

        self.assertEqual(result.reason, "learned_charge_window_active")
        self.assertEqual(result.action, "charge")
        self.assertEqual(result.charge_w, 1000.0)

    def test_missing_price_only_blocks_price_strategies(self) -> None:
        result = DecisionEngine().evaluate(
            context(
                ai_mode=AI_MODE_SUMMER,
                season="summer",
                price_now=None,
                price_points=[],
            )
        )

        self.assertEqual(result.reason, "summer_cover_deficit")
        self.assertEqual(result.action, "discharge")

    def test_missing_forecast_does_not_block_classic_planning(self) -> None:
        base = context(forecast=None)
        result = DecisionEngine().evaluate(
            replace(
                base,
                battery_capacity_kwh=10.0,
                soc=20.0,
            )
        )

        self.assertEqual(result.reason, "planning_latest_start")
        self.assertEqual(result.action, "charge")

    def test_invalid_pv_sensor_cannot_create_pv_charge(self) -> None:
        result = DecisionEngine().evaluate(
            context(
                pv_sensor_valid=False,
                pv_w=0.0,
                grid_import_w=0.0,
                grid_export_w=900.0,
                price_now=None,
                price_points=[],
                automatic_planning_allowed=False,
            )
        )

        self.assertNotEqual(result.reason, "pv_surplus_charge")

    def test_legacy_reasons_have_neutral_strategic_labels(self) -> None:
        autarky = DecisionEngine().evaluate(
            context(ai_mode=AI_MODE_SUMMER, season="summer")
        )
        strategy = decision_to_strategy_decision(autarky)

        self.assertEqual(strategy.source_reason, "summer_cover_deficit")
        self.assertEqual(strategy.strategic_reason, "load_coverage")


class Dev6ToDev8RegressionScenarios(unittest.TestCase):
    def test_dev7_directional_blocker_keeps_valid_pv_charge(self) -> None:
        result = DecisionEngine().evaluate(
            context(
                additional_battery_charge_w=400.0,
                grid_import_w=0.0,
                grid_export_w=500.0,
                pv_w=1200.0,
                house_load_w=300.0,
                pv_charge_start_counter=3,
                automatic_planning_allowed=False,
            )
        )

        self.assertEqual(result.reason, "pv_surplus_charge")
        self.assertEqual(result.action, "charge")

    def test_dev8_full_soc_passthrough_remains_selected(self) -> None:
        result = DecisionEngine().evaluate(
            context(
                soc=100.0,
                pv_w=900.0,
                house_load_w=600.0,
                profile={
                    **PROFILE,
                    "PV_HOUSELOAD_PASSTHROUGH": True,
                },
                pv_houseload_passthrough_active=True,
                pv_houseload_passthrough_target_w=600.0,
                automatic_planning_allowed=False,
            )
        )

        self.assertEqual(result.reason, "pv_house_load_passthrough")
        self.assertEqual(result.action, "passthrough")
        self.assertEqual(result.discharge_w, 600.0)

    def test_dev8_2_offgrid_load_does_not_block_planned_charge(self) -> None:
        result = DecisionEngine().evaluate(
            context(
                battery_capacity_kwh=10.0,
                soc=20.0,
                offgrid_load_active=True,
                offgrid_active=True,
            )
        )

        self.assertEqual(result.reason, "planning_latest_start")
        self.assertEqual(result.action, "charge")

    def test_dev8_3_has_no_hidden_reserve_discharge_floor(self) -> None:
        result = DecisionEngine().evaluate(
            context(
                soc=10.0,
                price_now=0.45,
                avg_charge_price=0.10,
                automatic_planning_allowed=False,
            )
        )

        self.assertIn(
            result.reason,
            {
                "adaptive_peak_discharge",
                "price_based_discharge",
            },
        )
        self.assertEqual(result.action, "discharge")


class Dev9Point1ChargePowerScenarios(unittest.TestCase):
    def test_remaining_cheap_window_raises_charge_power(self) -> None:
        requested = requested_charge_power_w(
            required_charge_energy_kwh=1.16,
            now=NOW,
            window_start=NOW,
            window_end=NOW + timedelta(minutes=30),
            available_charge_power_w_value=2400.0,
        )

        self.assertEqual(requested, 2320.0)

    def test_learned_rule_uses_request_instead_of_learned_estimate(self) -> None:
        plan = SimpleNamespace(
            status="active",
            mode="charge",
            decision_reason="learned_charge_window_active",
            required_charge_energy_kwh=1.16,
            effective_charge_power_w=1161.0,
            requested_charge_power_w=2320.0,
        )

        result = LearnedPlanningRule().evaluate(
            DecisionEngine(),
            context(
                max_charge_w=2400.0,
                battery_capacity_kwh=5.76,
                learned_planning_enabled=True,
                learned_charge_plan=plan,
            ),
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.charge_w, 2320.0)

    def test_complete_plan_separates_estimate_from_power_request(self) -> None:
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

        plan = build_learned_charge_plan(
            model=model,
            readiness=readiness,
            now=NOW,
            price_points=price_points(),
            forecast=None,
            total_battery_capacity_kwh=5.76,
            current_soc=5.0,
            soc_min=5.0,
            soc_max=100.0,
            profile_charge_limit_w=2400.0,
            current_effective_charge_cap_w=2400.0,
            learned_typical_charge_power_w=1161.0,
        )

        self.assertEqual(plan.mode, "charge")
        self.assertEqual(plan.effective_charge_power_w, 1161.0)
        self.assertGreater(plan.requested_charge_power_w, 1161.0)
        self.assertLessEqual(plan.requested_charge_power_w, 2400.0)

    def test_only_unthrottled_samples_define_reachable_power(self) -> None:
        legacy_limited = [
            LearningChargePowerSample(
                ts=NOW - timedelta(minutes=index),
                power_w=1161.0,
            )
            for index in range(8)
        ]
        unthrottled = [
            LearningChargePowerSample(
                ts=NOW - timedelta(minutes=20 + index),
                power_w=2300.0,
                commanded_power_w=2400.0,
                charge_cap_w=2400.0,
            )
            for index in range(4)
        ]

        learned = learned_typical_charge_power_w(
            samples=legacy_limited + unthrottled,
            now=NOW,
        )

        self.assertEqual(learned, 2300.0)

    def test_learning_uses_sustained_upper_power_not_taper_median(self) -> None:
        measured_values = [900.0] * 12 + [2250.0, 2280.0, 2300.0, 2320.0]
        samples = [
            LearningChargePowerSample(
                ts=NOW - timedelta(minutes=index),
                power_w=power_w,
                commanded_power_w=2400.0,
                charge_cap_w=2400.0,
            )
            for index, power_w in enumerate(measured_values)
        ]

        learned = learned_typical_charge_power_w(
            samples=samples,
            now=NOW,
        )

        self.assertEqual(learned, 2290.0)


if __name__ == "__main__":
    unittest.main()
