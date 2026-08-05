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
    advance_pv_charge_hysteresis,
    compute_pv_attributable_export_w,
    DecisionContext,
    DecisionEngine,
    PricePoint,
)
from custom_components.battery_smartflow_ai.mode_arbiter import (  # noqa: E402
    ModeArbiter,
)
from custom_components.battery_smartflow_ai.regulation_models import (  # noqa: E402
    GridHistoryState,
    RegulationRuntimeState,
    StrategyIntent,
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

    def test_last_output_command_is_removed_from_pv_export(self) -> None:
        self.assertEqual(
            compute_pv_attributable_export_w(
                grid_export_w=500.0,
                battery_discharge_w=0.0,
                previous_discharge_w=0.0,
                last_output_w=500.0,
            ),
            0.0,
        )

    def test_output_caused_export_cannot_start_pv_latch(self) -> None:
        state = (0, 0, False)

        for _ in range(3):
            state = advance_pv_charge_hysteresis(
                start_counter=state[0],
                stop_counter=state[1],
                latched=state[2],
                grid_import_w=0.0,
                grid_export_w=500.0,
                pv_w=0.0,
                pv_charge_start_export_w=80.0,
                last_output_w=500.0,
            )

        self.assertEqual(state, (0, 0, False))

    def test_export_without_plausible_pv_cannot_start_normal_latch(self) -> None:
        state = (0, 0, False)

        for _ in range(3):
            state = advance_pv_charge_hysteresis(
                start_counter=state[0],
                stop_counter=state[1],
                latched=state[2],
                grid_import_w=0.0,
                grid_export_w=500.0,
                pv_w=0.0,
                pv_charge_start_export_w=80.0,
                last_output_w=0.0,
                mppt_clips_without_output=False,
            )

        self.assertEqual(state, (0, 0, False))

    def test_real_pv_export_still_starts_normal_latch(self) -> None:
        state = (0, 0, False)

        for _ in range(2):
            state = advance_pv_charge_hysteresis(
                start_counter=state[0],
                stop_counter=state[1],
                latched=state[2],
                grid_import_w=0.0,
                grid_export_w=500.0,
                pv_w=700.0,
                pv_charge_start_export_w=80.0,
                last_output_w=0.0,
                mppt_clips_without_output=False,
            )

        self.assertEqual(state, (0, 0, True))

    def test_false_pv_latch_exits_quickly_without_pv_source(self) -> None:
        first_state = advance_pv_charge_hysteresis(
            start_counter=0,
            stop_counter=0,
            latched=True,
            grid_import_w=500.0,
            grid_export_w=0.0,
            pv_w=0.0,
            pv_charge_start_export_w=80.0,
        )
        second_state = advance_pv_charge_hysteresis(
            start_counter=first_state[0],
            stop_counter=first_state[1],
            latched=first_state[2],
            grid_import_w=500.0,
            grid_export_w=0.0,
            pv_w=0.0,
            pv_charge_start_export_w=80.0,
        )

        self.assertEqual(first_state, (0, 4, True))
        self.assertEqual(second_state, (0, 0, False))

    def test_sf800_mppt_export_can_confirm_pv_source(self) -> None:
        state = (0, 0, False)

        for _ in range(2):
            state = advance_pv_charge_hysteresis(
                start_counter=state[0],
                stop_counter=state[1],
                latched=state[2],
                grid_import_w=0.0,
                grid_export_w=100.0,
                pv_w=0.0,
                pv_charge_start_export_w=80.0,
                last_output_w=0.0,
                mppt_clips_without_output=True,
            )

        self.assertEqual(state, (0, 0, True))

    def test_fast_pv_handover_waits_for_output_zero(self) -> None:
        result = ModeArbiter().evaluate(
            now=datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc),
            intent=StrategyIntent(
                intent="pv_charge",
                requested_mode="input",
                requested_power_w=500.0,
                reason="pv_surplus_charge",
                pv_handover_policy="fast",
            ),
            grid=GridHistoryState(
                grid_now_w=-500.0,
                stable_export_cycles=3,
            ),
            runtime=RegulationRuntimeState(
                last_output_limit_w=500.0,
            ),
            current_ac_mode=None,
        )

        self.assertEqual(result.resolved_mode, "ramp_down_output")
        self.assertEqual(result.reason, "pv_charge_wait_output_zero")

    def test_fast_pv_handover_remains_available_after_output_zero(self) -> None:
        result = ModeArbiter().evaluate(
            now=datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc),
            intent=StrategyIntent(
                intent="pv_charge",
                requested_mode="input",
                requested_power_w=500.0,
                reason="pv_surplus_charge",
                pv_handover_policy="fast",
            ),
            grid=GridHistoryState(
                grid_now_w=-500.0,
                stable_export_cycles=3,
            ),
            runtime=RegulationRuntimeState(
                last_output_limit_w=0.0,
            ),
            current_ac_mode=None,
        )

        self.assertEqual(result.resolved_mode, "input")
        self.assertEqual(result.reason, "pv_charge_fast_handover")

    def test_released_strategic_pv_latch_ends_technical_input_hold(self) -> None:
        result = ModeArbiter().evaluate(
            now=datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc),
            intent=StrategyIntent(
                intent="idle",
                requested_mode="idle",
                requested_power_w=0.0,
                reason="idle",
                metadata={"pv_charge_latched": False},
            ),
            grid=GridHistoryState(
                grid_now_w=500.0,
                stable_import_cycles=2,
            ),
            runtime=RegulationRuntimeState(
                active_regulation_state="pv_charge_active",
                pv_charge_latch_started_ts=datetime(
                    2026,
                    8,
                    5,
                    11,
                    59,
                    30,
                    tzinfo=timezone.utc,
                ),
            ),
            current_ac_mode="input",
        )

        self.assertEqual(result.resolved_mode, "idle")
        self.assertTrue(result.allowed)


if __name__ == "__main__":
    unittest.main()
