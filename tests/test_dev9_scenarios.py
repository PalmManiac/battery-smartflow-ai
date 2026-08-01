"""Dev9 regression scenarios for modes, fallbacks and optional data."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
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
    PricePoint,
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


if __name__ == "__main__":
    unittest.main()
