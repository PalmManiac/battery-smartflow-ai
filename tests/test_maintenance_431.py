"""Regression tests for the V4.3.1 maintenance fixes."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.battery_protection import (  # noqa: E402
    next_cell_voltage_emergency_state,
)
from custom_components.battery_smartflow_ai.device_command import (  # noqa: E402
    clamp_number_power_request,
)
from custom_components.battery_smartflow_ai.device_profiles import (  # noqa: E402
    DEVICE_PROFILES,
)
from custom_components.battery_smartflow_ai.charge_commit_policy import (  # noqa: E402
    learned_commit_should_yield_to_discharge,
    learned_plan_charge_need_satisfied,
)
from custom_components.battery_smartflow_ai.decision_engine import (  # noqa: E402
    DecisionContext,
    DecisionEngine,
    PricePoint,
)
from custom_components.battery_smartflow_ai.strategy_state import (  # noqa: E402
    ChargeCommitState,
)


class Maintenance431Tests(unittest.TestCase):
    def test_live_zero_energy_plan_completes_learned_binding(self) -> None:
        plan = SimpleNamespace(
            status="ready",
            decision_reason="learned_charge_window_no_charge_needed",
            required_charge_energy_kwh=0.0,
            requested_charge_power_w=0.0,
            effective_window_slots=0,
            effective_window_minutes=0,
            optimal_charge_start=None,
        )

        self.assertTrue(
            learned_plan_charge_need_satisfied(
                commit_type="learned",
                learned_charge_plan=plan,
            )
        )

    def test_non_forced_learned_binding_yields_to_discharge(self) -> None:
        now = datetime(2026, 8, 4, 11, 30, tzinfo=timezone.utc)
        commit = ChargeCommitState(
            active=True,
            phase="active",
            commit_type="learned",
            source_reason="learned_charge_window_active",
            latest_start=now + timedelta(hours=1),
            requested_power_w=100.0,
        )

        self.assertTrue(
            learned_commit_should_yield_to_discharge(
                commit=commit,
                now=now,
                selected_reason="price_based_discharge",
            )
        )

        commit.phase = "forced"

        self.assertFalse(
            learned_commit_should_yield_to_discharge(
                commit=commit,
                now=now,
                selected_reason="price_based_discharge",
            )
        )

    def test_economic_discharge_beats_normal_learned_charge(self) -> None:
        now = datetime(2026, 8, 4, 11, 30, tzinfo=timezone.utc)
        prices = [
            PricePoint(
                start=now + timedelta(minutes=index * 15),
                end=now + timedelta(minutes=(index + 1) * 15),
                price=price,
            )
            for index, price in enumerate((0.20, 0.24, 0.3493, 0.38552))
        ]
        learned_plan = SimpleNamespace(
            status="ready",
            mode="charge",
            decision_reason="learned_charge_window_active",
            required_charge_energy_kwh=0.1,
            requested_charge_power_w=100.0,
        )
        ctx = DecisionContext(
            now=now,
            soc=74.0,
            soc_min=10.0,
            soc_max=100.0,
            emergency_soc=5.0,
            emergency_charge_w=300.0,
            max_charge_w=2400.0,
            max_discharge_w=2400.0,
            grid_import_w=942.0,
            grid_export_w=0.0,
            pv_w=0.0,
            house_load_w=942.0,
            price_now=0.3493,
            avg_charge_price=0.20,
            expensive_threshold=0.38552,
            very_expensive_threshold=0.50,
            profit_margin_pct=15.0,
            price_points=prices,
            ai_mode="automatic",
            manual_action=None,
            season="summer",
            profile=DEVICE_PROFILES["SF2400AC"],
            prev_discharge_w=0.0,
            prev_charge_w=100.0,
            battery_capacity_kwh=5.76,
            learned_charge_plan=learned_plan,
            learned_planning_enabled=True,
            automatic_strategy_active=True,
            automatic_discharge_allowed=True,
            automatic_planning_allowed=True,
        )

        engine = DecisionEngine()
        result = engine.evaluate(ctx)

        self.assertEqual(result.reason, "price_based_discharge")
        self.assertEqual(result.action, "discharge")
        learned_candidate = next(
            candidate
            for candidate in engine.last_strategy_selection["candidates"]
            if candidate["reason"] == "learned_charge_window_active"
        )
        self.assertEqual(learned_candidate["status"], "rejected")
        self.assertEqual(
            learned_candidate["selection_reason"],
            "economic_discharge_window",
        )

    def test_forced_learned_charge_keeps_deadline_priority(self) -> None:
        now = datetime(2026, 8, 4, 11, 30, tzinfo=timezone.utc)
        prices = [
            PricePoint(
                start=now + timedelta(minutes=index * 15),
                end=now + timedelta(minutes=(index + 1) * 15),
                price=price,
            )
            for index, price in enumerate((0.20, 0.24, 0.3493, 0.38552))
        ]
        learned_plan = SimpleNamespace(
            status="ready",
            mode="charge",
            decision_reason="learned_charge_window_latest_start_reached",
            required_charge_energy_kwh=0.5,
            requested_charge_power_w=1000.0,
        )
        ctx = DecisionContext(
            now=now,
            soc=20.0,
            soc_min=10.0,
            soc_max=100.0,
            emergency_soc=5.0,
            emergency_charge_w=300.0,
            max_charge_w=2400.0,
            max_discharge_w=2400.0,
            grid_import_w=942.0,
            grid_export_w=0.0,
            pv_w=0.0,
            house_load_w=942.0,
            price_now=0.3493,
            avg_charge_price=0.20,
            expensive_threshold=0.38552,
            very_expensive_threshold=0.50,
            profit_margin_pct=15.0,
            price_points=prices,
            ai_mode="automatic",
            manual_action=None,
            season="summer",
            profile=DEVICE_PROFILES["SF2400AC"],
            prev_discharge_w=0.0,
            prev_charge_w=0.0,
            battery_capacity_kwh=5.76,
            learned_charge_plan=learned_plan,
            learned_planning_enabled=True,
            automatic_strategy_active=True,
            automatic_discharge_allowed=True,
            automatic_planning_allowed=True,
        )

        result = DecisionEngine().evaluate(ctx)

        self.assertEqual(
            result.reason,
            "learned_charge_window_latest_start_reached",
        )
        self.assertEqual(result.action, "charge")

    def test_cell_voltage_emergency_charge_stays_latched_until_resume(self) -> None:
        active = False
        states = []

        for cell_v in (3.11, 3.10, 3.12, 3.09, 3.15, 3.17, 3.18):
            active = next_cell_voltage_emergency_state(
                previously_active=active,
                protection_enabled=True,
                lowest_cell_voltage=cell_v,
                warning_voltage=3.10,
                resume_voltage=3.18,
            )
            states.append(active)

        self.assertEqual(
            states,
            [False, True, True, True, True, True, False],
        )

    def test_cell_voltage_emergency_charge_resets_when_disabled(self) -> None:
        self.assertFalse(
            next_cell_voltage_emergency_state(
                previously_active=True,
                protection_enabled=False,
                lowest_cell_voltage=3.05,
                warning_voltage=3.10,
                resume_voltage=3.18,
            )
        )

    def test_zero_stop_bypasses_positive_entity_minimum(self) -> None:
        self.assertEqual(
            clamp_number_power_request(
                0.0,
                min_value=300.0,
                max_value=2400.0,
            ),
            0,
        )

    def test_positive_request_still_uses_live_entity_limits(self) -> None:
        self.assertEqual(
            clamp_number_power_request(
                120.0,
                min_value=300.0,
                max_value=2400.0,
            ),
            300,
        )
        self.assertEqual(
            clamp_number_power_request(
                2600.0,
                min_value=300.0,
                max_value=2400.0,
            ),
            2400,
        )

    def test_ac_profiles_wait_for_strategic_pv_exit_hysteresis(self) -> None:
        for profile_key in (
            "SF2400AC",
            "SF2400AC+",
            "SF2400Pro",
            "SF3000MixAC+",
            "SF4000MixAC+",
            "SF4000MixPro",
        ):
            with self.subTest(profile=profile_key):
                self.assertGreaterEqual(
                    DEVICE_PROFILES[profile_key][
                        "PV_CHARGE_EXIT_IMPORT_CYCLES"
                    ],
                    8,
                )


if __name__ == "__main__":
    unittest.main()
