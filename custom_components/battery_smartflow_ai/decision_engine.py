from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, List, Literal, Optional

from .const import MANUAL_CONST_DISCHARGE
from .core.models.runtime import AiMode, DecisionContext, RuntimeSnapshot
from .market_price import (
    MarketPrice,
    MarketPriceDirection,
    MarketPricePoint,
    planning_price_points,
)
from .price_math import peak_threshold
from .power_controller import PowerController, PowerContext


DeviceACMode = Literal["input", "output"]
ActionType = Literal["idle", "charge", "discharge", "emergency", "passthrough"]

# V4.3.0-dev5.8.2:
# Strategic learned/classic planning is no longer started for the final
# few percentage points below the configured maximum SoC.
PLANNING_NEAR_MAX_SOC_MARGIN_PCT = 3.0

NON_FORCED_LEARNED_CHARGE_REASONS = {
    "learned_charge_window_active",
}


def compute_pv_attributable_export_w(
    grid_export_w: float,
    battery_discharge_w: float = 0.0,
    previous_discharge_w: float = 0.0,
    last_output_w: float = 0.0,
    additional_battery_discharge_w: float = 0.0,
) -> float:
    """Return grid export that cannot be explained by battery discharge."""

    export_w = max(0.0, float(grid_export_w or 0.0))
    main_battery_export_w = max(
        0.0,
        float(battery_discharge_w or 0.0),
        float(previous_discharge_w or 0.0),
        float(last_output_w or 0.0),
    )
    additional_battery_export_w = max(
        0.0,
        float(additional_battery_discharge_w or 0.0),
    )

    return max(
        0.0,
        export_w
        - main_battery_export_w
        - additional_battery_export_w,
    )


def advance_pv_charge_hysteresis(
    *,
    start_counter: int,
    stop_counter: int,
    latched: bool,
    grid_import_w: float,
    grid_export_w: float,
    pv_w: float,
    pv_charge_start_export_w: float,
    battery_discharge_w: float = 0.0,
    previous_discharge_w: float = 0.0,
    last_output_w: float = 0.0,
    additional_battery_discharge_w: float = 0.0,
    mppt_clips_without_output: bool = False,
) -> tuple[int, int, bool]:
    """Advance the source-aware PV charge latch by one update cycle."""

    start_threshold = float(pv_charge_start_export_w or 0.0)

    start_required_cycles = 2
    stop_required_cycles = 8

    hold_export_threshold = max(20.0, start_threshold * 0.5)
    small_import_tolerance_w = 100.0
    hard_import_threshold_w = 140.0
    weak_export_threshold = max(10.0, start_threshold * 0.15)

    export_w = max(0.0, float(grid_export_w or 0.0))
    import_w = max(0.0, float(grid_import_w or 0.0))
    pv_power_w = max(0.0, float(pv_w or 0.0))
    output_command_w = max(0.0, float(last_output_w or 0.0))

    pv_attributable_export_w = compute_pv_attributable_export_w(
        grid_export_w=export_w,
        battery_discharge_w=battery_discharge_w,
        previous_discharge_w=previous_discharge_w,
        last_output_w=output_command_w,
        additional_battery_discharge_w=additional_battery_discharge_w,
    )
    battery_discharge_source_active = bool(
        max(
            0.0,
            float(battery_discharge_w or 0.0),
            float(previous_discharge_w or 0.0),
            output_command_w,
            float(additional_battery_discharge_w or 0.0),
        )
        > 25.0
    )
    battery_source_dominates_export = bool(
        battery_discharge_source_active
        and pv_attributable_export_w <= weak_export_threshold
    )

    minimum_plausible_pv_w = max(
        20.0,
        min(80.0, start_threshold * 0.25),
    )
    pv_source_plausible = bool(
        pv_power_w >= minimum_plausible_pv_w
        or (
            mppt_clips_without_output
            and pv_attributable_export_w >= hold_export_threshold
        )
    )
    output_command_active = output_command_w > 25.0

    has_start_surplus = bool(
        not output_command_active
        and pv_source_plausible
        and pv_attributable_export_w >= start_threshold
    )
    has_hold_surplus = bool(
        pv_source_plausible
        and pv_attributable_export_w >= hold_export_threshold
    )
    import_is_small = import_w <= small_import_tolerance_w

    real_weakness = bool(
        import_w >= hard_import_threshold_w
        and (
            not pv_source_plausible
            or pv_attributable_export_w <= weak_export_threshold
        )
    )

    if latched:
        start_counter = 0

        if output_command_active or battery_source_dominates_export:
            # A stale/false latch must release while OUTPUT is still the source
            # of export. Count this conflict twice to clear within four cycles.
            stop_counter += 2
        elif not pv_source_plausible:
            # Strong import plus no plausible PV source is unambiguous. Two
            # cycles are enough; otherwise retain the normal debounce.
            stop_counter += 4 if real_weakness else 1
        elif real_weakness:
            stop_counter += 1
        elif has_hold_surplus or import_is_small:
            stop_counter = 0
        else:
            stop_counter += 1

        if stop_counter >= stop_required_cycles:
            latched = False
            stop_counter = 0

    else:
        stop_counter = 0

        if has_start_surplus:
            start_counter += 1
        else:
            start_counter = 0

        if start_counter >= start_required_cycles:
            latched = True
            start_counter = 0
            stop_counter = 0

    return start_counter, stop_counter, latched


PricePoint = MarketPricePoint


@dataclass
class DecisionResult:
    action: ActionType
    ac_mode: DeviceACMode
    charge_w: float
    discharge_w: float
    reason: str
    target_soc: Optional[float] = None

    current_peak_threshold: Optional[float] = None
    current_valley_threshold: Optional[float] = None
    economic_discharge_threshold: Optional[float] = None
    effective_discharge_threshold: Optional[float] = None


class BaseRule:
    def evaluate(
        self,
        engine: "DecisionEngine",
        ctx: DecisionContext,
    ) -> Optional[DecisionResult]:
        raise NotImplementedError


class EmergencyRule(BaseRule):
    def evaluate(self, engine, ctx):
        if ctx.soc <= ctx.emergency_soc or ctx.cell_voltage_emergency_active:
            return engine._with_thresholds(
                ctx,
                DecisionResult(
                    action="emergency",
                    ac_mode="input",
                    charge_w=min(ctx.max_charge_w, ctx.emergency_charge_w),
                    discharge_w=0.0,
                    reason=(
                        "cell_voltage_emergency_charge"
                        if ctx.cell_voltage_emergency_active and ctx.soc > ctx.emergency_soc
                        else "emergency_latched_charge"
                    ),
                ),
            )
        return None


class AdditionalBatteryBlockRule(BaseRule):
    def evaluate(self, engine, ctx):
        # V4.3.0-dev7:
        # Directional additional-battery blockers are applied after all
        # candidates have been collected. Returning terminal idle here would
        # suppress valid same-direction charging or discharging strategies.
        return None


class AdditionalBatteryDischargeBlockRule(BaseRule):
    def evaluate(self, engine, ctx):
        # Zusatzakku-Entladung darf nur Ladeentscheidungen verhindern.
        # Sie darf keine Entladung blockieren, insbesondere keine manuelle
        # konstante Entladung.
        return None


class PeakRule(BaseRule):
    def evaluate(self, engine, ctx):
        if engine._pv_surplus_blocks_discharge(ctx):
            return None

        if (
            ctx.soc > ctx.soc_min
            and ctx.ai_mode == "automatic"
            and engine._automatic_discharge_context_allows(ctx)
        ):
            if (
                engine._detect_adaptive_peak(ctx)
                and engine._is_market_discharge_window(ctx)
                and engine._is_effective_discharge_price_reached(ctx)
            ):
                discharge_w = engine._delta_discharge(ctx)
                discharge_w = max(
                    float(discharge_w or 0.0),
                    engine._discharge_keepalive_w(ctx),
                )

                return engine._with_thresholds(
                    ctx,
                    DecisionResult(
                        action="discharge",
                        ac_mode="output",
                        charge_w=0.0,
                        discharge_w=discharge_w,
                        reason="adaptive_peak_discharge",
                    ),
                )

            if (
                engine._current_import_price(ctx) is not None
                and engine._current_import_price(ctx)
                >= ctx.very_expensive_threshold
            ):
                discharge_w = engine._delta_discharge(ctx)
                discharge_w = max(
                    float(discharge_w or 0.0),
                    engine._discharge_keepalive_w(ctx),
                )

                return engine._with_thresholds(
                    ctx,
                    DecisionResult(
                        action="discharge",
                        ac_mode="output",
                        charge_w=0.0,
                        discharge_w=discharge_w,
                        reason="very_expensive_force_discharge",
                    ),
                )
        return None


class ArbitrageRule(BaseRule):
    def evaluate(self, engine, ctx):
        if engine._pv_surplus_blocks_discharge(ctx):
            return None
            
        if (
            engine._current_import_price(ctx) is not None
            and ctx.avg_charge_price is not None
            and ctx.soc > ctx.soc_min
            and ctx.ai_mode == "automatic"
            and engine._automatic_discharge_context_allows(ctx)
            and engine._is_market_discharge_window(ctx)
            and engine._is_effective_discharge_price_reached(ctx)
        ):
            discharge_w = engine._delta_discharge(ctx)
            discharge_w = max(
                float(discharge_w or 0.0),
                engine._discharge_keepalive_w(ctx),
            )

            return engine._with_thresholds(
                ctx,
                DecisionResult(
                    action="discharge",
                    ac_mode="output",
                    charge_w=0.0,
                    discharge_w=discharge_w,
                    reason="price_based_discharge",
                ),
            )
        return None


class LearnedPlanningRule(BaseRule):
    def evaluate(self, engine, ctx):
        """V4.1.0 learned charge-window planning.

        Safe activation gate:
        - completely inactive unless learned_planning_enabled is True
        - only uses plans with status ready/active
        - only handles learned wait/charge decisions
        - classic planning remains fallback until a usable learned plan exists
        """
        if not engine._learned_planning_has_usable_charge_need(ctx):
            return None

        plan = getattr(ctx, "learned_charge_plan", None)
        status = str(getattr(plan, "status", "") or "")
        mode = str(getattr(plan, "mode", "") or "")
        decision_reason = str(getattr(plan, "decision_reason", "") or "")

        if status not in ("ready", "active"):
            return None

        required_kwh = float(
            getattr(plan, "required_charge_energy_kwh", 0.0) or 0.0
        )
        if required_kwh <= 0.0:
            return None
            
        # V4.3.0-dev5.8:
        # The learned planner calculates the actual battery energy that is
        # missing until its planning deadline. Convert that energy need into
        # the SoC target of the charge binding instead of always charging to
        # the configured maximum SoC.
        #
        # required_charge_energy_kwh is already limited by the planner to the
        # physically chargeable energy up to soc_max.
        required_soc_pct = (
            float(required_kwh)
            / float(ctx.battery_capacity_kwh)
        ) * 100.0

        learned_target_soc = min(
            float(ctx.soc_max),
            max(
                float(ctx.soc),
                float(ctx.soc) + required_soc_pct,
            ),
        )

        if decision_reason == "learned_charge_window_no_charge_needed":
            return None

        if mode == "wait" or decision_reason == "learned_charge_window_wait":
            # A waiting learned plan is a real HOLD candidate. The central
            # candidate selector rejects only competing grid-charge candidates;
            # PV charging, passthrough and economic discharge may still win with
            # their higher active priority.
            return engine._idle_result(
                ctx,
                reason="learned_charge_window_wait",
            )

        if mode == "charge" or decision_reason in (
            "learned_charge_window_active",
            "learned_charge_window_latest_start_reached",
            "learned_charge_window_deadline_too_close_start_now",
        ):
            planned_power_w = float(
                getattr(plan, "requested_charge_power_w", 0.0) or 0.0
            )

            if planned_power_w <= 0.0:
                planned_power_w = float(ctx.max_charge_w)

            charge_w = min(
                float(ctx.max_charge_w),
                max(100.0, planned_power_w),
            )

            reason = (
                decision_reason
                if decision_reason
                in (
                    "learned_charge_window_active",
                    "learned_charge_window_latest_start_reached",
                    "learned_charge_window_deadline_too_close_start_now",
                )
                else "learned_charge_window_active"
            )

            block = engine._charge_blocked_by_additional_battery_discharge(ctx)
            if block is not None:
                return block

            return engine._with_thresholds(
                ctx,
                DecisionResult(
                    action="charge",
                    ac_mode="input",
                    charge_w=charge_w,
                    discharge_w=0.0,
                    reason=reason,
                    target_soc=learned_target_soc,
                ),
            )

        return None


class PlanningRule(BaseRule):
    def evaluate(self, engine, ctx):
        if not engine._automatic_planning_context_allows(ctx):
            return None

        if engine._pv_morning_transition_active(ctx):
            return None

        return engine._evaluate_adaptive_planning(ctx)


class VeryCheapRule(BaseRule):
    def evaluate(self, engine, ctx):
        if ctx.ai_mode != "automatic":
            return None

        price_now = engine._current_import_price(ctx)
        if price_now is None or ctx.very_cheap_price is None:
            return None

        if ctx.soc >= ctx.soc_max:
            return None

        if float(price_now) > float(ctx.very_cheap_price):
            return None

        # V4.2.3-Beta3:
        # Do not let a user-defined very-cheap threshold blindly suppress useful
        # PV charging. PV should keep priority unless grid energy is really
        # cheaper than the PV opportunity cost, e.g. zero/negative prices or
        # price below feed-in tariff.
        if engine._optional_grid_charge_should_wait_for_pv(ctx):
            return None

        block = engine._charge_blocked_by_additional_battery_discharge(ctx)
        if block is not None:
            return block

        return engine._with_thresholds(
            ctx,
            DecisionResult(
                action="charge",
                ac_mode="input",
                charge_w=float(ctx.max_charge_w),
                discharge_w=0.0,
                reason="very_cheap_force_charge",
                target_soc=ctx.soc_max,
            ),
        )


class ValleyBoostRule(BaseRule):
    def evaluate(self, engine, ctx):
        if engine._pv_morning_transition_active(ctx):
            return None

        # V4.3.0-dev5.4:
        # Optional valley charging in Automatic is no longer enabled through
        # the detected winter season.
        if not engine._automatic_valley_charge_context_allows(ctx):
            return None

        price_now = engine._current_import_price(ctx)
        price_points = engine._import_price_points(ctx)
        if price_now is None:
            return None

        if ctx.soc >= ctx.soc_max:
            return None

        if not price_points:
            return None

        prices = [p.price for p in price_points]
        if not prices:
            return None

        valley_threshold = engine._compute_valley_threshold(prices, ctx.valley_factor)

        if price_now > valley_threshold:
            return None

        if ctx.pv_w < 100:
            return None
            
        # V4.2.3-Beta3:
        # Valley boost is still optional grid charging. If useful PV is already
        # available and grid energy is not cheaper than PV opportunity cost,
        # keep PV charging priority.
        if engine._market_grid_charge_should_wait_for_pv(ctx):
            return None

        soc_gap_pct = max(0.0, ctx.soc_max - ctx.soc)
        base_required_kwh = ctx.battery_capacity_kwh * (soc_gap_pct / 100.0)

        if engine._forecast_supports_waiting(ctx, base_required_kwh):
            return None

        charge_w = ctx.max_charge_w
        reason = "valley_boost_charge"

        if engine._forecast_available(ctx) and engine._forecast_outlook(ctx) == "mixed":
            charge_w = max(300.0, float(ctx.max_charge_w) * 0.75)
            reason = "valley_boost_charge_mixed_forecast"

        block = engine._charge_blocked_by_additional_battery_discharge(ctx)
        if block is not None:
            return block

        return engine._with_thresholds(
            ctx,
            DecisionResult(
                action="charge",
                ac_mode="input",
                charge_w=charge_w,
                discharge_w=0.0,
                reason=reason,
            ),
        )


class ValleyOpportunityRule(BaseRule):
    def evaluate(self, engine, ctx):
        if engine._pv_morning_transition_active(ctx):
            return None

        # V4.3.0-dev5.4:
        # Valley opportunity is controlled by the unified AutomaticStrategy
        # context instead of the legacy winter season.
        if not engine._automatic_valley_charge_context_allows(ctx):
            return None

        if engine._current_import_price(ctx) is None:
            return None

        if ctx.soc >= ctx.soc_max:
            return None

        if not engine._import_price_points(ctx):
            return None

        if not engine._is_valley_price_now(ctx):
            return None

        # V4.2.3-Beta3:
        # Valley opportunity is only optional grid charging. It must not take over
        # while useful PV is available or already charging the battery, unless grid
        # energy is economically better than using/exporting PV.
        if engine._market_grid_charge_should_wait_for_pv(ctx):
            return None

        if not engine._is_real_pv_underperforming(ctx):
            return None

        soc_gap_pct = max(0.0, ctx.soc_max - ctx.soc)
        required_kwh = ctx.battery_capacity_kwh * (soc_gap_pct / 100.0)

        if required_kwh <= 0.0:
            return None

        charge_w = float(ctx.max_charge_w)
        reason = "valley_opportunity_charge"

        if engine._forecast_available(ctx):
            outlook = engine._forecast_outlook(ctx)

            if outlook == "good":
                if int(ctx.forecast_wait_block_counter or 0) < 2:
                    return None
                charge_w = max(400.0, float(ctx.max_charge_w) * 0.70)

            elif outlook == "mixed":
                charge_w = max(500.0, float(ctx.max_charge_w) * 0.80)
                reason = "valley_opportunity_charge_mixed_forecast"

        charge_w = max(charge_w, 400.0)

        block = engine._charge_blocked_by_additional_battery_discharge(ctx)
        if block is not None:
            return block

        return engine._with_thresholds(
            ctx,
            DecisionResult(
                action="charge",
                ac_mode="input",
                charge_w=charge_w,
                discharge_w=0.0,
                reason=reason,
                target_soc=ctx.soc_max,
            ),
        )


class PvHouseLoadPassthroughRule(BaseRule):
    def evaluate(self, engine, ctx):
        if not bool(ctx.pv_sensor_valid):
            return None

        if not engine._pv_houseload_passthrough_enabled(ctx):
            return None

        if ctx.ai_mode == "summer":
            return None

        if not bool(ctx.pv_houseload_passthrough_active):
            return None

        target_w = max(0.0, float(ctx.pv_houseload_passthrough_target_w or 0.0))
        if target_w <= 0.0:
            return None

        return engine._with_thresholds(
            ctx,
            DecisionResult(
                action="passthrough",
                ac_mode="output",
                charge_w=0.0,
                discharge_w=min(target_w, float(ctx.max_discharge_w)),
                reason="pv_house_load_passthrough",
            ),
        )
        
        
class ReserveChargeRule(BaseRule):
    """Season-neutral strategic reserve charge for Automatic mode."""

    def evaluate(self, engine, ctx):
        if not engine._reserve_charge_enabled(ctx):
            return None

        if ctx.soc >= ctx.soc_max:
            return None

        price_now = engine._current_import_price(ctx)
        if price_now is None or not engine._import_price_points(ctx):
            return None
            
        # V4.2.8:
        # Peak-reserve charging must not be limited to the formal valley
        # threshold only. On generally expensive days, the cheapest useful slot
        # before a later peak can still be above the calculated valley threshold.
        #
        # It must, however, never start during the high-price/peak window itself.
        if not engine._reserve_charge_window(ctx):
            return None

        target_soc = engine._reserve_target_soc(ctx)
        if target_soc is None:
            return None

        if float(ctx.soc) >= float(target_soc):
            return None

        expected_peak_price = engine._reserve_expected_peak_price(ctx)
        if expected_peak_price is None:
            return None

        # Grid charging must still be economically meaningful compared to the
        # upcoming high-price window. Feed-in tariff must not block this case.
        min_profit_factor = 1.0 + (float(ctx.profit_margin_pct or 0.0) / 100.0)
        if float(price_now) * min_profit_factor > float(expected_peak_price):
            return None
            
        # A rejected optional peak-reserve charge must fall through to the next
        # DecisionEngine rule. The Coordinator cannot safely turn this decision into
        # terminal idle, because that would suppress PV surplus charging, learned
        # planning and other valid lower-priority decisions.
        effective_discharge_threshold = (
            engine._compute_effective_discharge_threshold(ctx)
        )

        if (
            effective_discharge_threshold is not None
            and float(price_now)
            >= float(effective_discharge_threshold)
        ):
            return None

        block = engine._charge_blocked_by_additional_battery_discharge(ctx)
        if block is not None:
            return block

        return engine._with_thresholds(
            ctx,
            DecisionResult(
                action="charge",
                ac_mode="input",
                charge_w=float(ctx.max_charge_w),
                discharge_w=0.0,
                reason="summer_peak_reserve_charge",
                target_soc=float(target_soc),
            ),
        )


class PvRule(BaseRule):
    def evaluate(self, engine, ctx):
        if not bool(ctx.pv_sensor_valid):
            return None

        planning = engine._evaluate_adaptive_planning(ctx)
        if planning is not None:
            return None

        if ctx.soc >= ctx.soc_max:
            return None

        export_w = float(ctx.grid_export_w or 0.0)
        import_w = float(ctx.grid_import_w or 0.0)
        prev_charge_w = float(ctx.prev_charge_w or 0.0)
        prev_discharge_w = float(ctx.prev_discharge_w or 0.0)
        start_export_threshold = float(ctx.pv_charge_start_export_w or 0.0)

        pv_attributable_export_w = engine._pv_attributable_export_w(ctx)
        has_direct_surplus = (
            pv_attributable_export_w >= start_export_threshold
        )
        battery_discharge_source_active = bool(
            max(
                0.0,
                float(ctx.battery_discharge_w or 0.0),
                float(ctx.prev_discharge_w or 0.0),
                float(ctx.last_output_w or 0.0),
                float(ctx.additional_battery_discharge_w or 0.0),
            )
            > 25.0
        )
        source_verified_hold_surplus = bool(
            pv_attributable_export_w
            >= max(20.0, start_export_threshold * 0.50)
        )

        protection_active = (
            engine._low_soc_protection_strict(ctx)
            and engine._discharge_protection_active(ctx)
        )

        # A previous 60 W discharge keepalive must not suppress PV surplus charge.
        # If there is real PV surplus, PV charging may take over even when
        # prev_discharge_w is still > 0 from the previous cycle.
        discharge_active = max(
            prev_discharge_w,
            float(ctx.last_output_w or 0.0),
        ) > 0.0
        if discharge_active and not engine._pv_surplus_blocks_discharge(ctx):
            return None

        start_counter = int(ctx.pv_charge_start_counter or 0)
        stop_counter = int(ctx.pv_charge_stop_counter or 0)

        charge_already_active = bool(ctx.pv_charge_latched)

        sf800_passthrough_enabled = engine._pv_houseload_passthrough_enabled(ctx)

        soft_start_ready = (
            False
            if (
                sf800_passthrough_enabled
                or (protection_active and engine._low_soc_pv_charge_requires_export(ctx))
            )
            else engine._pv_soft_start_ready(ctx)
        )

        required_start_cycles = 6 if sf800_passthrough_enabled else 2

        # V4.2.7:
        # Do not let a short early-morning PV/export pulse immediately interrupt
        # an active house-load discharge. During active discharge, require a
        # longer stable export confirmation before switching to INPUT/PV charge.
        if discharge_active and not charge_already_active:
            required_start_cycles = max(required_start_cycles, 6)

        # The user-configured "PV-Ladestart ab Einspeisung" must be a real
        # hard start threshold for new PV charging.
        #
        # Soft-start may help to keep or smooth an already active PV charge,
        # but it must not start a new INPUT/PV charge below the configured
        # export threshold. Otherwise BSFAI can enter PV charging too early
        # during weak morning PV and cause INPUT/OUTPUT/status flicker.
        start_allowed = (
            has_direct_surplus
            and start_counter >= required_start_cycles
        )

        # Laufende PV-Ladung deutlich stärker halten.
        # Solange keine echte anhaltende Schwäche vorliegt, bleiben wir im PV-Zweig.
        stop_due_to_weakness = (
            stop_counter >= 8
            and import_w > 140.0
            and export_w < max(10.0, start_export_threshold * 0.15)
        )

        keepalive_charge = (
            charge_already_active
            and not stop_due_to_weakness
            and (
                not battery_discharge_source_active
                or source_verified_hold_surplus
            )
        )

        if not start_allowed and not keepalive_charge:
            return None

        charge_w = engine._delta_charge(ctx)

        if protection_active and engine._low_soc_pv_charge_requires_export(ctx):
            # Capability-driven DC-PV / low-SoC protection:
            # In der Entlade-Sperrzone darf PV nur dann in den Akku,
            # wenn wirklich stabiler Export vorhanden ist.
            # Kein Soft-Start, kein Akku-Vorrang, kein Laden bei Netzbezug.
            if not has_direct_surplus:
                return None

            if not charge_already_active and start_counter < 2:
                return None

            if import_w > 30.0:
                return None

            charge_w = min(float(charge_w), max(0.0, export_w))

        # Wenn die PV-Ladung bereits läuft, soll primär die Leistung geregelt werden,
        # nicht der ganze Ladezustand verloren gehen.
        if keepalive_charge:
            if sf800_passthrough_enabled:
                # Devices without safe INPUT keepalive must not be held above 80 W,
                # wenn kein echter stabiler Export vorhanden ist.
                if not has_direct_surplus:
                    return None
            else:
                charge_w = max(charge_w, engine._charge_keepalive_w(ctx))

        if (
            soft_start_ready
            and keepalive_charge
            and not sf800_passthrough_enabled
        ):
            if import_w <= 60.0:
                charge_w = max(charge_w, 80.0)

        charge_w = min(float(charge_w), float(ctx.max_charge_w))

        if charge_w > 0:
            block = engine._charge_blocked_by_additional_battery_discharge(ctx)
            if block is not None:
                return block

            return engine._with_thresholds(
                ctx,
                DecisionResult(
                    action="charge",
                    ac_mode="input",
                    charge_w=charge_w,
                    discharge_w=0.0,
                    reason="pv_surplus_charge",
                ),
            )

        return None


class AutarkyLoadCoverageRule(BaseRule):
    def evaluate(self, engine, ctx):
        # V4.3.0-dev5.2:
        # The internal "summer" key is the explicit user-selected Autarkie mode.
        # Automatic no longer enters this unconditional house-load coverage
        # branch based on legacy season detection.
        if ctx.ai_mode == "summer":
            if (
                ctx.soc > ctx.soc_min
                and not (
                    engine._low_soc_protection_strict(ctx)
                    and engine._discharge_protection_active(ctx)
                )
            ):
                # V4.2.3-Beta5:
                # Do not request summer house-load discharge while PV already
                # nearly covers the load and real grid import is small/absent.
                # This avoids false summer_cover_deficit decisions during
                # active PV surplus charging.
                if engine._pv_surplus_blocks_discharge(ctx):
                    return None
                    
                discharge_w = engine._delta_discharge(ctx)

                # V4.2.7:
                # Keep active summer house-load coverage alive across short
                # sensor/load dips. A single cycle with calculated 0 W must not
                # immediately collapse to idle and create an INPUT/OUTPUT/idle
                # sawtooth.
                if discharge_w <= 0.0:
                    prev_discharge_w = max(
                        0.0,
                        float(ctx.prev_discharge_w or 0.0),
                    )
                    export_w = max(0.0, float(ctx.grid_export_w or 0.0))
                    import_w = max(0.0, float(ctx.grid_import_w or 0.0))

                    export_guard_w = max(
                        40.0,
                        float(ctx.profile.get("EXPORT_GUARD_W", 80.0) or 80.0),
                    )

                    hold_import_tolerance_w = max(
                        80.0,
                        float(ctx.profile.get("TARGET_IMPORT_W", 10.0) or 10.0)
                        + float(
                            ctx.profile.get(
                                "DISCHARGE_DEADBAND_W",
                                30.0,
                            )
                            or 30.0
                        ),
                    )

                    if (
                        prev_discharge_w > 0.0
                        and export_w <= export_guard_w
                        and import_w <= hold_import_tolerance_w
                    ):
                        discharge_w = max(
                            engine._discharge_keepalive_w(ctx),
                            min(prev_discharge_w, float(ctx.max_discharge_w)),
                        )

                if discharge_w > 0:
                    return engine._with_thresholds(
                        ctx,
                        DecisionResult(
                            action="discharge",
                            ac_mode="output",
                            charge_w=0.0,
                            discharge_w=discharge_w,
                            reason="summer_cover_deficit",
                        ),
                    )
            return engine._idle_result(
                ctx,
                reason="idle",
            )
        return None


class ManualRule(BaseRule):
    def evaluate(self, engine, ctx):
        if ctx.ai_mode != "manual":
            return None

        if ctx.manual_action == "charge":
            block = engine._charge_blocked_by_additional_battery_discharge(ctx)
            if block is not None:
                return block

            return engine._with_thresholds(
                ctx,
                DecisionResult(
                    action="charge",
                    ac_mode="input",
                    charge_w=ctx.max_charge_w,
                    discharge_w=0.0,
                    reason="manual_charge",
                ),
            )

        if ctx.manual_action == MANUAL_CONST_DISCHARGE:
            return engine._with_thresholds(
                ctx,
                DecisionResult(
                    action="discharge",
                    ac_mode="output",
                    charge_w=0.0,
                    discharge_w=float(ctx.max_discharge_w),
                    reason="manual_constant_discharge",
                ),
            )

        if ctx.manual_action == "discharge":
            discharge_w = engine._delta_discharge(ctx)
            return engine._with_thresholds(
                ctx,
                DecisionResult(
                    action="discharge",
                    ac_mode="output",
                    charge_w=0.0,
                    discharge_w=discharge_w,
                    reason="manual_discharge",
                ),
            )

        return engine._idle_result(
            ctx,
            reason="manual_idle",
        )


class DecisionEngine:
    def __init__(self):
        self._collecting_candidates = False
        self._last_strategy_selection: dict[str, Any] = {
            "candidate_count": 0,
            "eligible_candidate_count": 0,
            "selected_rule": "fallback",
            "selected_reason": "idle",
            "selected_state": "idle_ready",
            "selected_priority": 200,
            "candidates": [],
        }
        self._rules = [
            EmergencyRule(),
            AdditionalBatteryBlockRule(),
            AdditionalBatteryDischargeBlockRule(),
            ManualRule(),
            VeryCheapRule(),
            PvHouseLoadPassthroughRule(),

            # Real PV surplus keeps the highest normal charging priority.
            PvRule(),

            # A selected learned or classic charge window must be evaluated before
            # optional peak reserve and economic discharge. Otherwise the current
            # discharge price can prevent a planned charge from ever starting.
            LearnedPlanningRule(),
            PlanningRule(),

            # Optional strategic charging may only take over when no planned charge
            # and no usable PV surplus decision exists.
            ReserveChargeRule(),
            ValleyBoostRule(),
            ValleyOpportunityRule(),

            # Economic discharge is evaluated only after all valid charging plans.
            PeakRule(),
            ArbitrageRule(),

            AutarkyLoadCoverageRule(),
        ]

    def _idle_result(self, ctx: DecisionContext, reason: str = "idle") -> DecisionResult:
        """
        Neutraler Idle-Zustand:
        OUTPUT + 0 W statt INPUT + 0 W, damit kein versteckter Lade-/Akku-Bias entsteht.
        """
        return self._with_thresholds(
            ctx,
            DecisionResult(
                action="idle",
                ac_mode="output",
                charge_w=0.0,
                discharge_w=0.0,
                reason=reason,
            ),
        )

    def _additional_battery_discharge_blocks_charge(
        self,
        ctx: DecisionContext,
    ) -> bool:
        """Return True when a second battery is discharging.

        This must only block charging decisions. Discharging decisions,
        especially manual constant discharge, must remain allowed.
        """
        return float(ctx.additional_battery_discharge_w or 0.0) > 50.0

    def _charge_blocked_by_additional_battery_discharge(
        self,
        ctx: DecisionContext,
    ) -> DecisionResult | None:
        # V4.3.0-dev7 collects the actual charging candidate first and applies
        # the directional blocker centrally. This lets a valid discharging
        # candidate continue instead of turning the whole cycle into idle.
        if self._collecting_candidates:
            return None

        if not self._additional_battery_discharge_blocks_charge(ctx):
            return None

        return self._idle_result(
            ctx,
            reason="additional_battery_discharging_block",
        )

    @property
    def last_strategy_selection(self) -> dict[str, Any]:
        """Return diagnostics for the most recent candidate selection."""

        return {
            **self._last_strategy_selection,
            "candidates": [
                dict(candidate)
                for candidate in self._last_strategy_selection.get(
                    "candidates",
                    [],
                )
            ],
        }

    def _context_validation_reason(
        self,
        ctx: DecisionContext,
    ) -> str | None:
        """Return the first critical context error that requires safe idle."""

        if not bool(ctx.soc_limits_valid):
            return "soc_limits_invalid"
        if not bool(ctx.power_limits_valid):
            return "power_limits_invalid"
        return None

    def _candidate_rejection_reason(
        self,
        ctx: DecisionContext,
        strategy: Any,
        result: DecisionResult,
    ) -> str | None:
        """Return a directional or planning rejection reason for a candidate."""

        state = str(getattr(strategy.state, "value", strategy.state))
        requested_mode = str(strategy.requested_mode or "idle")
        requested_power_w = strategy.requested_power_w
        active_direction = bool(
            result.action != "idle"
            or requested_power_w is None
            or float(requested_power_w or 0.0) > 0.0
        )

        protection_states = {
            "protection",
            "emergency_charge",
        }
        manual_states = {
            "manual_charge",
            "manual_discharge",
            "manual_idle",
        }

        if (
            state not in protection_states
            and state not in manual_states
            and not bool(ctx.grid_sensor_valid)
            and active_direction
        ):
            return "grid_sensor_invalid"

        if state not in protection_states and active_direction:
            if (
                requested_mode == "output"
                and float(ctx.additional_battery_charge_w or 0.0) > 0.0
            ):
                return "additional_battery_charging_block"

            if (
                requested_mode == "input"
                and self._additional_battery_discharge_blocks_charge(ctx)
            ):
                return "additional_battery_discharging_block"

        if (
            self._learned_planning_waits_for_window(ctx)
            and str(result.reason or "") != "very_cheap_force_charge"
            and state
            in {
                "ac_charge_planned",
                "ac_charge_price",
                "ac_charge_reserve",
            }
        ):
            return "learned_charge_window_wait"

        return None

    def _strategy_for_candidate(self, result: DecisionResult) -> Any:
        """Convert a rule result through the canonical V4.3 strategy adapter."""

        # Local import avoids the existing module-load cycle:
        # strategy_adapter still accepts the legacy DecisionResult model.
        from .strategy_adapter import decision_to_strategy_decision

        return decision_to_strategy_decision(result)

    def _profile_flag(self, ctx: DecisionContext, key: str, default: bool = False) -> bool:
        try:
            return bool(ctx.profile.get(key, default))
        except Exception:
            return bool(default)

    def _low_soc_protection_strict(self, ctx: DecisionContext) -> bool:
        return self._profile_flag(ctx, "LOW_SOC_PROTECTION_STRICT", False)

    def _low_soc_pv_charge_requires_export(self, ctx: DecisionContext) -> bool:
        return self._profile_flag(ctx, "LOW_SOC_PV_CHARGE_REQUIRES_EXPORT", False)

    def _pv_houseload_passthrough_enabled(self, ctx: DecisionContext) -> bool:
        return ctx.capabilities.supports_pv_house_load_passthrough
        
    def _automatic_valley_charge_context_allows(
        self,
        ctx: DecisionContext,
    ) -> bool:
        """Return whether AutomaticStrategy permits optional valley charging.

        This permission does not replace the existing price, forecast, PV,
        battery or protection checks inside the individual valley rules.
        """

        return bool(
            ctx.ai_mode == "automatic"
            and ctx.automatic_strategy_active
            and ctx.automatic_valley_charge_allowed
        )
        
    def _automatic_planning_context_allows(
        self,
        ctx: DecisionContext,
    ) -> bool:
        """Return whether AutomaticStrategy permits strategic charge planning.

        This permission does not replace learned-planning readiness, price,
        forecast, deadline, energy-need, SoC or protection checks.
        """

        # Strategic grid-charge planning belongs exclusively to Automatic.
        if ctx.ai_mode != "automatic":
            return False

        return bool(
            ctx.automatic_strategy_active
            and ctx.automatic_planning_allowed
        )
        
    def _automatic_discharge_context_allows(
        self,
        ctx: DecisionContext,
    ) -> bool:
        """Return whether AutomaticStrategy permits economic discharge.

        This permission never replaces the normal price, market-window, SoC or
        protection checks. It only removes the legacy season branch from the
        Automatic discharge decision.
        """

        if ctx.ai_mode != "automatic":
            return True

        return bool(
            ctx.automatic_strategy_active
            and ctx.automatic_discharge_allowed
        )

    def _learned_planning_waits_for_window(
        self,
        ctx: DecisionContext,
    ) -> bool:
        """Return whether a usable learned plan deliberately waits.

        A ready learned plan has already evaluated the required energy, charge
        duration, complete price curve and deadline. While it waits for its
        selected window, simpler grid-charge rules must not start an earlier
        charge binding. This is only a grid-charge constraint: emergency/manual
        charge, real PV surplus, passthrough and economic discharge remain free.
        """

        if not self._learned_planning_has_usable_charge_need(ctx):
            return False

        plan = getattr(ctx, "learned_charge_plan", None)
        status = str(getattr(plan, "status", "") or "")
        mode = str(getattr(plan, "mode", "") or "")
        decision_reason = str(
            getattr(plan, "decision_reason", "") or ""
        )

        return bool(
            status in ("ready", "active")
            and (
                mode == "wait"
                or decision_reason == "learned_charge_window_wait"
            )
        )

    @staticmethod
    def _import_market_price(ctx: DecisionContext) -> MarketPrice | None:
        """Return the canonical import market context."""

        market_price = getattr(ctx, "import_market_price", None)
        if (
            not isinstance(market_price, MarketPrice)
            or market_price.direction is not MarketPriceDirection.IMPORT
        ):
            return None
        return market_price

    def _current_import_price(
        self,
        ctx: DecisionContext,
    ) -> float | None:
        market_price = self._import_market_price(ctx)
        if market_price is None or not market_price.valid:
            return None
        return float(market_price.current_price)

    def _import_price_points(
        self,
        ctx: DecisionContext,
    ) -> list[MarketPricePoint]:
        market_price = self._import_market_price(ctx)
        return planning_price_points(market_price)

    @staticmethod
    def _current_export_price(ctx: DecisionContext) -> float | None:
        market_price = getattr(ctx, "export_market_price", None)
        if (
            not isinstance(market_price, MarketPrice)
            or market_price.direction is not MarketPriceDirection.EXPORT
            or not market_price.valid
        ):
            return None
        return float(market_price.current_price)

    def _market_grid_charge_should_wait_for_pv(
        self,
        ctx: DecisionContext,
    ) -> bool:
        """Apply the existing PV opportunity check to canonical planning price."""

        if not self._pv_power_is_relevant_for_charging(ctx):
            return False
        price_now = self._current_import_price(ctx)
        if price_now is None:
            return True
        try:
            pv_opportunity_price = max(
                0.0,
                float(self._current_export_price(ctx) or 0.0),
            )
        except Exception:
            pv_opportunity_price = 0.0
        return price_now > (pv_opportunity_price - 0.001)

    def _learned_planning_has_usable_charge_need(
        self,
        ctx: DecisionContext,
    ) -> bool:
        """Return whether learned planning has an actionable energy plan."""

        if not bool(getattr(ctx, "learned_planning_enabled", False)):
            return False

        plan = getattr(ctx, "learned_charge_plan", None)
        if plan is None:
            return False

        # A ready learned plan has already evaluated the complete price curve,
        # required energy, PV forecast and deadline. The coarse Automatic gate
        # must not delay an already active learned window.
        if not bool(
            ctx.ai_mode == "automatic"
            and ctx.automatic_strategy_active
        ):
            return False

        # Dev5.8.2 remains authoritative: do not reserve tiny strategic grid
        # charges for the final percentage points below maximum SoC.
        if float(ctx.soc) >= (
            float(ctx.soc_max) - PLANNING_NEAR_MAX_SOC_MARGIN_PCT
        ):
            return False

        if (
            self._current_import_price(ctx) is None
            or not self._import_price_points(ctx)
            or ctx.battery_capacity_kwh <= 0
            or ctx.max_charge_w <= 0
        ):
            return False

        status = str(getattr(plan, "status", "") or "")
        required_kwh = float(
            getattr(plan, "required_charge_energy_kwh", 0.0) or 0.0
        )

        return bool(
            status in ("ready", "active")
            and required_kwh > 0.0
        )

    def _discharge_protection_active(self, ctx: DecisionContext) -> bool:
        return bool(
            ctx.discharge_blocked_by_soc_min
            or ctx.cell_voltage_discharge_blocked
        )
        
    def _pv_surplus_blocks_discharge(self, ctx: DecisionContext) -> bool:
        """Return True when real PV surplus should prevent price/peak discharge.

        This must block a new economic discharge when there is real PV export,
        but it must not kill an already active discharge just because the
        output regulation briefly overshoots into small export.

        A small previous discharge keepalive, e.g. 60 W, is not treated as a
        real active discharge.
        """

        export_w = self._pv_attributable_export_w(ctx)
        import_w = float(ctx.grid_import_w or 0.0)
        prev_discharge_w = float(ctx.prev_discharge_w or 0.0)
        start_export_threshold = float(ctx.pv_charge_start_export_w or 80.0)

        surplus_threshold_w = max(40.0, start_export_threshold * 0.50)

        if export_w <= surplus_threshold_w:
            return False

        if import_w > 30.0:
            return False

        keepalive_w = float(self._discharge_keepalive_w(ctx) or 60.0)
        real_active_discharge_threshold_w = max(120.0, keepalive_w * 1.5)

        # If a real discharge is already active, do not let the DecisionEngine
        # collapse to idle because of short export. The V4.2 ModeArbiter and
        # PowerController handle the ramp-down / exit stability.
        if prev_discharge_w >= real_active_discharge_threshold_w:
            return False

        # No real active discharge, only idle/old keepalive:
        # PV surplus should block starting or keeping economic discharge.
        return True

    def _pv_attributable_export_w(self, ctx: DecisionContext) -> float:
        """Return export that cannot be explained by battery discharge.

        Grid export alone is not proof of PV surplus while OUTPUT is active:
        regulation overshoot or a small discharge keepalive can create the same
        signal. Subtract the strongest available main-battery discharge signal
        and any configured additional-battery discharge before PV logic may use
        the remaining export.
        """

        return compute_pv_attributable_export_w(
            grid_export_w=float(ctx.grid_export_w or 0.0),
            battery_discharge_w=float(
                ctx.battery_discharge_w or 0.0
            ),
            previous_discharge_w=float(
                ctx.prev_discharge_w or 0.0
            ),
            last_output_w=float(
                ctx.last_output_w or 0.0
            ),
            additional_battery_discharge_w=float(
                ctx.additional_battery_discharge_w or 0.0
            ),
        )
        
    def _pv_power_is_relevant_for_charging(self, ctx: DecisionContext) -> bool:
        """Return True when current PV should keep priority over optional grid charge.

        This intentionally does not rely only on grid export. During active INPUT
        charging the device may absorb PV directly, so the grid export sensor can
        stay near 0 W even though PV is clearly available and already charging the
        battery.
        """

        if ctx.soc >= ctx.soc_max:
            return False

        if self._additional_battery_discharge_blocks_charge(ctx):
            return False

        pv_w = max(0.0, float(ctx.pv_w or 0.0))
        house_load_w = max(0.0, float(ctx.house_load_w or 0.0))
        export_w = self._pv_attributable_export_w(ctx)
        import_w = max(0.0, float(ctx.grid_import_w or 0.0))
        prev_charge_w = max(0.0, float(ctx.prev_charge_w or 0.0))

        start_export_threshold = max(
            0.0,
            float(ctx.pv_charge_start_export_w or 0.0),
        )

        # Direct export is the strongest signal.
        if export_w >= max(30.0, start_export_threshold * 0.40):
            return True

        # If PV is already charging the battery, grid export may be 0.
        # Keep PV priority as long as PV power is meaningful.
        if prev_charge_w > 0.0 and pv_w >= max(180.0, house_load_w * 0.75):
            return True

        # Strong standalone PV signal: PV clearly covers house load and leaves
        # meaningful remaining power for charging.
        if pv_w >= house_load_w + max(120.0, start_export_threshold):
            return True

        # Fallback for low house-load systems: PV is clearly available and there
        # is no strong external import pressure.
        if pv_w >= max(300.0, house_load_w * 1.50) and import_w <= 250.0:
            return True

        return False

    def _grid_charge_is_cheaper_than_pv(self, ctx: DecisionContext) -> bool:
        """Return True when grid charging is economically better than using PV.

        PV is not strictly free if exporting would earn a feed-in tariff. The
        opportunity cost of PV is therefore the feed-in tariff. If no tariff is
        configured/passed, 0.0 is used, which means only zero or negative grid
        prices may override PV.
        """

        current_import_price = self._current_import_price(ctx)
        if current_import_price is None:
            return False

        try:
            price_now = float(current_import_price)
        except Exception:
            return False

        try:
            pv_opportunity_price = max(
                0.0,
                float(self._current_export_price(ctx) or 0.0),
            )
        except Exception:
            pv_opportunity_price = 0.0

        # Equal prices are economically equivalent. This also lets a zero or
        # negative grid price override PV when no feed-in tariff is configured,
        # without introducing a fixed tolerance that depends on the currency.
        return price_now <= pv_opportunity_price

    def _optional_grid_charge_should_wait_for_pv(self, ctx: DecisionContext) -> bool:
        """Return True when optional grid charging should not override current PV.

        Applies to opportunity/comfort charging, not to emergency, manual charge,
        learned/deadline charge or other hard safety reasons.
        """

        if not self._pv_power_is_relevant_for_charging(ctx):
            return False

        if self._grid_charge_is_cheaper_than_pv(ctx):
            return False

        return True
        
    def _compute_base_price(self, prices: List[float]) -> float:
        return sum(prices) / len(prices)

    def _compute_peak_threshold(self, prices: List[float], peak_factor: float) -> float:
        return peak_threshold(prices, peak_factor)

    def _compute_valley_threshold(self, prices: List[float], valley_factor: float) -> float:
        base_price = self._compute_base_price(prices)
        return base_price * valley_factor

    def _compute_economic_discharge_threshold(self, ctx: DecisionContext) -> Optional[float]:
        if ctx.avg_charge_price is None:
            return None
        try:
            avg_charge_price = float(ctx.avg_charge_price)
            margin_pct = float(ctx.profit_margin_pct)
        except Exception:
            return None
        if avg_charge_price < 0:
            return None
        return avg_charge_price * (1.0 + margin_pct / 100.0)

    def _compute_effective_discharge_threshold(self, ctx: DecisionContext) -> Optional[float]:
        price_points = self._import_price_points(ctx)
        if not price_points:
            return None

        prices = [p.price for p in price_points]
        if not prices:
            return None

        market_peak_threshold = self._compute_peak_threshold(prices, ctx.peak_factor)
        valley_threshold = self._compute_valley_threshold(prices, ctx.valley_factor)
        economic_threshold = self._compute_economic_discharge_threshold(ctx)

        try:
            configured_expensive_threshold = float(ctx.expensive_threshold)
        except Exception:
            configured_expensive_threshold = 0.0

        configured_expensive_threshold = max(0.0, configured_expensive_threshold)

        avg_charge_price = ctx.avg_charge_price
        try:
            avg_charge_price_float = (
                float(avg_charge_price)
                if avg_charge_price is not None
                else None
            )
        except Exception:
            avg_charge_price_float = None

        avg_price_missing_or_zero = (
            avg_charge_price_float is None
            or avg_charge_price_float <= 0.0001
        )

        # V4.2.6 refinement:
        # If the average charge price is missing or effectively zero, do not use
        # the market peak threshold as a hard fallback. Also do not collapse to
        # the valley threshold alone, because that would allow discharge too
        # early on normal prices.
        #
        # Use a dynamic market fallback between valley and peak anchor.
        # The configured threshold is only a soft anchor, not a hard floor.
        market_anchor = max(
            valley_threshold,
            market_peak_threshold * 0.82,
        )

        safety_floor = max(0.0, valley_threshold)

        try:
            feed_in_floor = max(
                0.0,
                float(self._current_export_price(ctx) or 0.0),
            ) * (
                1.0 + float(ctx.profit_margin_pct or 0.0) / 100.0
            )
            safety_floor = max(safety_floor, feed_in_floor)
        except Exception:
            pass

        configured_anchor = max(0.0, configured_expensive_threshold)

        market_mid_threshold = valley_threshold + (
            max(0.0, market_anchor - valley_threshold) * 0.55
        )

        if configured_anchor > 0.0:
            configured_blend_threshold = (
                configured_anchor * 0.65
                + market_anchor * 0.35
            )
            dynamic_missing_price_threshold = max(
                market_mid_threshold,
                configured_blend_threshold,
            )
        else:
            dynamic_missing_price_threshold = market_mid_threshold

        missing_price_fallback_threshold = max(
            safety_floor,
            dynamic_missing_price_threshold,
        )

        # Safety cap:
        # Never let the missing-price fallback become the full peak threshold again.
        missing_price_fallback_threshold = min(
            missing_price_fallback_threshold,
            market_peak_threshold * 0.90,
        )

        if economic_threshold is None:
            return missing_price_fallback_threshold

        if avg_price_missing_or_zero:
            return missing_price_fallback_threshold

        market_anchor = market_peak_threshold * 0.82

        effective = (market_anchor * 0.70) + (economic_threshold * 0.30)

        effective = max(effective, economic_threshold)

        # V4.2.6 refinement:
        # Do not let a very low but non-zero average charge price collapse the
        # effective discharge threshold exactly to the valley threshold.
        # The valley threshold remains the lower market reference, but the
        # effective discharge threshold should stay slightly above it unless the
        # calculated economic threshold itself is higher.
        dynamic_valley_floor = valley_threshold + (
            max(0.0, market_anchor - valley_threshold) * 0.35
        )

        effective = max(effective, dynamic_valley_floor)

        # V4.3.2-Beta3 / Issue #156:
        # Keep the effective discharge threshold inside the current market band.
        # A high economic threshold still influences the calculation, but it must
        # not move the effective market threshold above the dynamic peak.
        # Otherwise normal economic discharge can become impossible for the day.
        market_effective_cap = market_peak_threshold * 0.90
        effective = max(
            dynamic_valley_floor,
            min(effective, market_effective_cap),
        )

        return effective

    def _with_thresholds(self, ctx: DecisionContext, result: DecisionResult) -> DecisionResult:
        price_points = self._import_price_points(ctx)
        prices = [p.price for p in price_points]
        if prices:
            result.current_peak_threshold = self._compute_peak_threshold(prices, ctx.peak_factor)
            result.current_valley_threshold = self._compute_valley_threshold(prices, ctx.valley_factor)
        else:
            result.current_peak_threshold = None
            result.current_valley_threshold = None

        result.economic_discharge_threshold = self._compute_economic_discharge_threshold(ctx)
        result.effective_discharge_threshold = self._compute_effective_discharge_threshold(ctx)
        return result

    def _is_market_discharge_window(self, ctx: DecisionContext) -> bool:
        """Return whether the current price may be used for economic discharge.

        V4.3.0-dev5.4.1:
        The effective discharge threshold is the authoritative economic and
        market threshold.

        The former additional 90%-of-peak market anchor could block discharge
        even when the displayed effective discharge threshold had clearly been
        exceeded. That made the effective threshold misleading and delayed
        discharge until almost the absolute daily peak.
        """

        current_import_price = self._current_import_price(ctx)
        if current_import_price is None:
            return False

        effective_threshold = self._compute_effective_discharge_threshold(ctx)
        if effective_threshold is None:
            return False

        return float(current_import_price) >= float(effective_threshold)
        
    def _reserve_charge_enabled(
        self,
        ctx: DecisionContext,
    ) -> bool:
        """Return whether Automatic may evaluate strategic reserve charging."""
        return bool(
            ctx.ai_mode == "automatic"
            and ctx.automatic_strategy_active
            and ctx.automatic_peak_reserve_allowed
            and self._current_import_price(ctx) is not None
            and bool(self._import_price_points(ctx))
            and ctx.battery_capacity_kwh > 0
        )


    def _reserve_future_peak_slots(
        self,
        ctx: DecisionContext,
    ) -> list[PricePoint]:
        if not self._reserve_charge_enabled(ctx):
            return []

        price_points = self._import_price_points(ctx)
        prices = [p.price for p in price_points]
        if not prices:
            return []

        peak_threshold = self._compute_peak_threshold(prices, ctx.peak_factor)

        future_slots = [
            p
            for p in price_points
            if p.end > ctx.now
            and (
                p.price >= peak_threshold
                or p.price >= float(ctx.very_expensive_threshold)
            )
        ]

        return sorted(future_slots, key=lambda p: p.start)


    def _reserve_expected_peak_price(
        self,
        ctx: DecisionContext,
    ) -> float | None:
        slots = self._reserve_future_peak_slots(ctx)
        if not slots:
            return None

        try:
            return max(float(p.price) for p in slots)
        except Exception:
            return None


    def _reserve_charge_window(
        self,
        ctx: DecisionContext,
    ) -> bool:
        """Return whether the current slot is useful for peak-reserve charging.

        V4.3.0-dev5.8:
        Peak-reserve charging must prefer the cheapest amount of energy that is
        actually required before the next high-price window.

        The former broad 35-percent price band could start AC charging too early,
        e.g. at 0.20 per kWh although sufficient 0.15 per kWh slots were still
        available later.

        The peak slot itself is never considered a charging candidate.
        """

        if not self._reserve_charge_enabled(ctx):
            return False

        price_now = self._current_import_price(ctx)
        price_points = self._import_price_points(ctx)
        if price_now is None or not price_points:
            return False

        future_slots = self._reserve_future_peak_slots(ctx)
        future_slots = [
            p
            for p in future_slots
            if p.start > ctx.now
        ]

        if not future_slots:
            return False

        next_peak = min(
            future_slots,
            key=lambda p: p.start,
        )

        expected_peak_price = (
            self._reserve_expected_peak_price(ctx)
        )

        if expected_peak_price is None:
            return False

        prices = [
            float(p.price)
            for p in price_points
        ]

        if not prices:
            return False

        market_peak_threshold = self._compute_peak_threshold(
            prices,
            ctx.peak_factor,
        )

        price_now = float(price_now)

        # Never charge inside an active high-price / peak window.
        if price_now >= float(market_peak_threshold):
            return False

        # Do not charge when the current price is already too close
        # to the expected peak price.
        if price_now >= float(expected_peak_price) * 0.85:
            return False

        target_soc = self._reserve_target_soc(ctx)

        if target_soc is None:
            return False

        soc_gap_pct = max(
            0.0,
            float(target_soc) - float(ctx.soc),
        )

        required_kwh = (
            float(ctx.battery_capacity_kwh)
            * (soc_gap_pct / 100.0)
        )

        if required_kwh <= 0.0:
            return False

        charge_power_kw = max(
            0.1,
            float(ctx.max_charge_w or 0.0) / 1000.0,
        )

        hours_needed = max(
            0.25,
            required_kwh / charge_power_kw,
        )

        # Only real pre-peak slots are candidates.
        # The peak slot itself must never widen the acceptable price range.
        candidate_slots = [
            p
            for p in price_points
            if (
                p.end > ctx.now
                and p.start < next_peak.start
            )
        ]

        if not candidate_slots:
            return False

        # Determine the price ceiling of the cheapest amount of energy
        # that is actually required before the peak.
        remaining_kwh = float(required_kwh)
        required_price_ceiling: float | None = None

        cheapest_slots = sorted(
            candidate_slots,
            key=lambda p: (
                float(p.price),
                p.start,
            ),
        )

        for slot in cheapest_slots:
            usable_start = max(
                ctx.now,
                slot.start,
            )
            usable_end = min(
                next_peak.start,
                slot.end,
            )

            usable_hours = max(
                0.0,
                (
                    usable_end - usable_start
                ).total_seconds()
                / 3600.0,
            )

            if usable_hours <= 0.0:
                continue

            slot_energy_kwh = (
                charge_power_kw * usable_hours
            )

            if slot_energy_kwh <= 0.0:
                continue

            required_price_ceiling = float(slot.price)
            remaining_kwh -= slot_energy_kwh

            if remaining_kwh <= 0.0:
                break

        # Enough future charging capacity exists:
        # start only when the current slot belongs to the price range
        # actually needed for the reserve.
        if (
            remaining_kwh <= 0.0
            and required_price_ceiling is not None
            and price_now <= required_price_ceiling
        ):
            return True

        # Urgency fallback:
        # If there is no longer enough comfortable time to wait,
        # charging must start even at a less attractive price.
        hours_until_peak = max(
            0.0,
            (
                next_peak.start - ctx.now
            ).total_seconds()
            / 3600.0,
        )

        return bool(
            required_kwh > 0.15
            and hours_until_peak <= hours_needed * 1.25
            and price_now
            < float(expected_peak_price) * 0.80
        )


    def _reserve_target_soc(
        self,
        ctx: DecisionContext,
    ) -> float | None:
        """Return the target SoC for strategic peak-reserve charging.

        V4.3.0-dev5.6:
        Once Automatic starts a strategic AC charge in a valid economical
        pre-peak window, the configured maximum SoC is authoritative.

        The former fixed 80/85/90/95 percent severity levels could end an
        otherwise valid charge prematurely, even with a poor PV outlook and a
        user-configured maximum SoC of 100 percent.
        """

        expected_peak = self._reserve_expected_peak_price(ctx)
        if expected_peak is None:
            return None

        if not self._import_price_points(ctx):
            return None

        return max(
            float(ctx.soc_min),
            min(100.0, float(ctx.soc_max)),
        )


    def _is_effective_discharge_price_reached(self, ctx: DecisionContext) -> bool:
        current_import_price = self._current_import_price(ctx)
        if current_import_price is None:
            return False

        effective_threshold = self._compute_effective_discharge_threshold(ctx)
        if effective_threshold is None:
            return False

        return float(current_import_price) >= float(effective_threshold)

    def _is_valley_price_now(self, ctx: DecisionContext) -> bool:
        price_now = self._current_import_price(ctx)
        price_points = self._import_price_points(ctx)
        if price_now is None or not price_points:
            return False

        prices = [p.price for p in price_points]
        if not prices:
            return False

        valley_threshold = self._compute_valley_threshold(prices, ctx.valley_factor)
        return float(price_now) <= float(valley_threshold)

    def _forecast_available(self, ctx: DecisionContext) -> bool:
        return bool(
            ctx.forecast is not None
            and getattr(ctx.forecast, "status", None) == "available"
        )

    def _forecast_outlook(self, ctx: DecisionContext) -> str:
        if not self._forecast_available(ctx):
            return "unknown"
        return str(getattr(ctx.forecast, "pv_outlook", "unknown") or "unknown")

    def _forecast_remaining_today_kwh(self, ctx: DecisionContext) -> float:
        if not self._forecast_available(ctx):
            return 0.0
        try:
            return max(0.0, float(getattr(ctx.forecast, "remaining_today_kwh", 0.0) or 0.0))
        except Exception:
            return 0.0

    def _forecast_tomorrow_kwh(self, ctx: DecisionContext) -> float:
        if not self._forecast_available(ctx):
            return 0.0
        try:
            return max(0.0, float(getattr(ctx.forecast, "tomorrow_kwh", 0.0) or 0.0))
        except Exception:
            return 0.0

    def _forecast_next_3h_kwh(self, ctx: DecisionContext) -> float:
        if not self._forecast_available(ctx):
            return 0.0
        try:
            return max(0.0, float(getattr(ctx.forecast, "next_3h_kwh", 0.0) or 0.0))
        except Exception:
            return 0.0

    def _forecast_next_6h_kwh(self, ctx: DecisionContext) -> float:
        if not self._forecast_available(ctx):
            return 0.0
        try:
            return max(0.0, float(getattr(ctx.forecast, "next_6h_kwh", 0.0) or 0.0))
        except Exception:
            return 0.0

    def _forecast_required_kwh_factor(self, ctx: DecisionContext) -> float:
        if self._forecast_outlook(ctx) == "good":
            return 0.60
        if self._forecast_outlook(ctx) == "mixed":
            return 0.90
        if self._forecast_outlook(ctx) == "poor":
            return 1.15
        return 1.00

    def _forecast_supports_waiting(
        self,
        ctx: DecisionContext,
        base_required_kwh: float,
    ) -> bool:
        if not self._forecast_available(ctx):
            return False

        if self._forecast_outlook(ctx) != "good":
            return False

        required = max(0.0, float(base_required_kwh or 0.0))
        if required <= 0.0:
            return True

        next_3h_kwh = self._forecast_next_3h_kwh(ctx)
        next_6h_kwh = self._forecast_next_6h_kwh(ctx)
        remaining_today_kwh = self._forecast_remaining_today_kwh(ctx)
        tomorrow_kwh = self._forecast_tomorrow_kwh(ctx)

        enough_soon = next_3h_kwh >= max(0.8, required * 0.25)
        enough_next = next_6h_kwh >= max(1.2, required * 0.40)
        enough_today = remaining_today_kwh >= max(1.5, required * 0.55)
        enough_tomorrow = tomorrow_kwh >= max(2.0, required * 0.95)

        return enough_soon or enough_next or enough_today or enough_tomorrow

    def _is_real_pv_underperforming(self, ctx: DecisionContext) -> bool:
        export_w = float(ctx.grid_export_w or 0.0)
        import_w = float(ctx.grid_import_w or 0.0)
        pv_w = float(ctx.pv_w or 0.0)
        start_export_threshold = float(ctx.pv_charge_start_export_w or 0.0)

        weak_export = export_w < max(40.0, start_export_threshold * 0.50)
        weak_pv = pv_w < max(250.0, start_export_threshold * 2.0)
        real_import = import_w > 80.0

        return (weak_export and weak_pv) or real_import

    def _charge_keepalive_w(self, ctx: DecisionContext) -> float:
        return min(float(ctx.max_charge_w), 80.0)

    def _discharge_keepalive_w(self, ctx: DecisionContext) -> float:
        try:
            keepalive = float(ctx.profile.get("KEEPALIVE_MIN_OUTPUT_W", 60.0) or 60.0)
        except Exception:
            keepalive = 60.0

        return max(
            0.0,
            min(
                float(ctx.max_discharge_w),
                keepalive,
            ),
        )

    def _pv_morning_transition_active(self, ctx: DecisionContext) -> bool:
        if ctx.ai_mode == "manual":
            return False

        if ctx.soc >= ctx.soc_max:
            return False

        if float(ctx.prev_charge_w or 0.0) > 0.0:
            return False

        if float(ctx.prev_discharge_w or 0.0) > 0.0:
            return False

        if float(ctx.last_output_w or 0.0) > 0.0:
            return False

        pv_w = float(ctx.pv_w or 0.0)
        export_w = float(ctx.grid_export_w or 0.0)
        import_w = float(ctx.grid_import_w or 0.0)
        house_load_w = float(ctx.house_load_w or 0.0)
        start_threshold = float(ctx.pv_charge_start_export_w or 0.0)

        near_export = export_w >= max(10.0, start_threshold * 0.20)
        pv_covering_load = pv_w >= max(180.0, house_load_w * 0.80)
        small_import = import_w <= max(120.0, start_threshold)

        return pv_covering_load and small_import and near_export

    def _pv_soft_start_ready(self, ctx: DecisionContext) -> bool:
        if ctx.soc >= ctx.soc_max:
            return False

        pv_w = float(ctx.pv_w or 0.0)
        export_w = float(ctx.grid_export_w or 0.0)
        import_w = float(ctx.grid_import_w or 0.0)
        house_load_w = float(ctx.house_load_w or 0.0)
        start_threshold = float(ctx.pv_charge_start_export_w or 0.0)

        pv_nearly_covers_load = pv_w >= max(200.0, house_load_w * 0.90)
        small_import = import_w <= 60.0
        some_export = export_w >= max(10.0, start_threshold * 0.15)

        return pv_nearly_covers_load and small_import and some_export

    def _to_power_ctx(self, ctx: DecisionContext, mode: Literal["charge", "discharge"]) -> PowerContext:
        prefix = "DISCHARGE" if mode == "discharge" else "CHARGE"
        target_grid_w = (
            float(ctx.profile["DISCHARGE_TARGET_IMPORT_W"])
            if mode == "discharge"
            else float(ctx.profile.get("TARGET_EXPORT_W", 10.0))
        )

        return PowerContext(
            soc=ctx.soc,
            soc_min=ctx.soc_min,
            soc_max=ctx.soc_max,
            max_charge_w=ctx.max_charge_w,
            max_discharge_w=ctx.max_discharge_w,
            grid_import_w=ctx.grid_import_w,
            grid_export_w=ctx.grid_export_w,
            prev_discharge_w=ctx.prev_discharge_w,
            prev_charge_w=ctx.prev_charge_w,
            target_grid_w=target_grid_w,
            deadband_w=float(ctx.profile[f"{prefix}_DEADBAND_W"]),
            export_guard_w=float(ctx.profile["EXPORT_GUARD_W"]),
            kp_up=float(ctx.profile[f"{prefix}_KP_UP"]),
            kp_down=float(ctx.profile[f"{prefix}_KP_DOWN"]),
            max_step_up_w=float(ctx.profile[f"{prefix}_MAX_STEP_UP"]),
            max_step_down_w=float(ctx.profile[f"{prefix}_MAX_STEP_DOWN"]),
            keepalive_min_deficit_w=float(
                ctx.profile["KEEPALIVE_MIN_DEFICIT_W"]
            ),
            keepalive_min_output_w=float(
                ctx.profile["KEEPALIVE_MIN_OUTPUT_W"]
            ),
        )

    def _delta_discharge(self, ctx: DecisionContext) -> float:
        return PowerController.delta_discharge(self._to_power_ctx(ctx, "discharge"))

    def _delta_charge(self, ctx: DecisionContext) -> float:
        return PowerController.delta_charge(self._to_power_ctx(ctx, "charge"))

    def _detect_adaptive_peak(self, ctx: DecisionContext) -> bool:
        price_now = self._current_import_price(ctx)
        price_points = self._import_price_points(ctx)
        if not price_points or price_now is None:
            return False

        prices = [p.price for p in price_points]
        if not prices:
            return False

        threshold = self._compute_peak_threshold(prices, ctx.peak_factor)

        if price_now >= threshold:
            return True

        future_slots = sorted(
            [p for p in price_points if p.start > ctx.now],
            key=lambda p: p.start,
        )

        for slot in future_slots:
            minutes_ahead = (slot.start - ctx.now).total_seconds() / 60
            if minutes_ahead > 60:
                break
            if slot.price >= threshold * 1.15:
                return True

        return False

    def _evaluate_adaptive_planning(self, ctx: DecisionContext) -> Optional[DecisionResult]:
        if self._learned_planning_waits_for_window(ctx):
            return None

        price_now = self._current_import_price(ctx)
        price_points = self._import_price_points(ctx)
        if (
            not self._automatic_planning_context_allows(ctx)
            or not price_points
            or price_now is None
            or float(ctx.soc) >= (
                float(ctx.soc_max) - PLANNING_NEAR_MAX_SOC_MARGIN_PCT
            )
            or ctx.battery_capacity_kwh <= 0
            or ctx.max_charge_w <= 0
        ):
            return None

        prices = [p.price for p in price_points]
        if not prices:
            return None

        if ctx.very_cheap_price is not None and price_now <= ctx.very_cheap_price:
            return None

        valley_threshold = self._compute_valley_threshold(prices, ctx.valley_factor)
        if price_now > valley_threshold:
            return None

        peak_threshold = self._compute_peak_threshold(prices, ctx.peak_factor)

        peak_slots = [p for p in price_points if p.price >= peak_threshold]
        future_peaks = [p for p in peak_slots if p.start > ctx.now]

        if not future_peaks:
            return None

        expected_peak_price = max(p.price for p in future_peaks)

        min_profit_factor = 1 + (ctx.profit_margin_pct / 100)
        required_peak_price = price_now * min_profit_factor

        if expected_peak_price < required_peak_price:
            return None

        next_peak = min(p.start for p in future_peaks)

        future_peaks_sorted = sorted(future_peaks, key=lambda p: p.start)
        second_peak = future_peaks_sorted[1].start if len(future_peaks_sorted) >= 2 else None

        soc_gap_pct = max(0.0, ctx.soc_max - ctx.soc)
        base_required_kwh = ctx.battery_capacity_kwh * (soc_gap_pct / 100.0)

        if second_peak is not None:
            hours_between_peaks = (second_peak - next_peak).total_seconds() / 3600.0
            if hours_between_peaks < 6:
                base_required_kwh *= 1.4

        if self._forecast_supports_waiting(ctx, base_required_kwh):
            if not (
                self._is_valley_price_now(ctx)
                and self._is_real_pv_underperforming(ctx)
                and int(ctx.forecast_wait_block_counter or 0) >= 2
            ):
                return None

        required_kwh = base_required_kwh * self._forecast_required_kwh_factor(ctx)
        required_kwh = max(required_kwh, min(base_required_kwh, 0.25))

        charge_power_kw = ctx.max_charge_w / 1000.0
        if charge_power_kw <= 0:
            return None

        hours_needed = required_kwh / charge_power_kw
        hours_needed = max(hours_needed * 1.10, 0.25)

        latest_start = next_peak - timedelta(hours=hours_needed)

        future_prices = [p for p in price_points if ctx.now <= p.start <= next_peak]

        if future_prices:
            energy_per_slot = charge_power_kw * 0.25
            if energy_per_slot > 0:
                required_slots = max(1, math.ceil(required_kwh / energy_per_slot))
                cheapest_slots = sorted(future_prices, key=lambda p: p.price)[:required_slots]

                if not cheapest_slots:
                    return None

                cheapest_prices = [p.price for p in cheapest_slots]
                if price_now > max(cheapest_prices):
                    return None

        if ctx.now >= latest_start:
            reason = "planning_latest_start"
            if self._forecast_available(ctx):
                outlook = self._forecast_outlook(ctx)
                if outlook == "poor":
                    reason = "planning_forecast_poor"
                elif outlook == "mixed":
                    reason = "planning_forecast_mixed"
                elif (
                    outlook == "good"
                    and self._is_real_pv_underperforming(ctx)
                    and int(ctx.forecast_wait_block_counter or 0) >= 2
                ):
                    reason = "planning_forecast_reality_override"

            block = self._charge_blocked_by_additional_battery_discharge(ctx)
            if block is not None:
                return block

            return self._with_thresholds(
                ctx,
                DecisionResult(
                    action="charge",
                    ac_mode="input",
                    charge_w=ctx.max_charge_w,
                    discharge_w=0.0,
                    reason=reason,
                    target_soc=ctx.soc_max,
                ),
            )

        return None

    def _context_error_candidate(
        self,
        ctx: RuntimeSnapshot,
        reason: str,
    ) -> dict[str, Any]:
        """Build the sole candidate for an invalid critical context."""

        result = self._idle_result(ctx, reason=reason)
        strategy = self._strategy_for_candidate(result)
        return self._evaluated_candidate(
            index=-1,
            rule_name="ContextValidation",
            result=result,
            strategy=strategy,
        )

    def _collect_rule_candidates(
        self,
        ctx: RuntimeSnapshot,
    ) -> list[tuple[int, str, DecisionResult]]:
        """Collect every admissible rule result in deterministic rule order."""

        candidates: list[tuple[int, str, DecisionResult]] = []
        self._collecting_candidates = True
        try:
            for index, rule in enumerate(self._rules):
                result = rule.evaluate(self, ctx)
                if result is not None:
                    candidates.append((index, rule.__class__.__name__, result))
        finally:
            self._collecting_candidates = False

        if not candidates:
            candidates.append(
                (
                    len(self._rules),
                    "SafeIdleFallback",
                    self._idle_result(ctx, reason="idle"),
                )
            )
        return candidates

    def _evaluated_candidate(
        self,
        *,
        index: int,
        rule_name: str,
        result: DecisionResult,
        strategy: Any,
        rejection_reason: str | None = None,
    ) -> dict[str, Any]:
        """Create the normalized representation used by candidate selection."""

        return {
            "index": int(index),
            "rule": rule_name,
            "result": result,
            "strategy": strategy,
            "state": str(getattr(strategy.state, "value", strategy.state)),
            "reason": str(result.reason or "idle"),
            "priority": int(strategy.priority),
            "requested_mode": str(strategy.requested_mode or "idle"),
            "rejection_reason": rejection_reason,
        }

    def _evaluate_candidates(
        self,
        ctx: RuntimeSnapshot,
        raw_candidates: list[tuple[int, str, DecisionResult]],
    ) -> list[dict[str, Any]]:
        """Normalize candidates and apply central strategic permissions."""

        evaluated: list[dict[str, Any]] = []
        for index, rule_name, result in raw_candidates:
            strategy = self._strategy_for_candidate(result)
            evaluated.append(
                self._evaluated_candidate(
                    index=index,
                    rule_name=rule_name,
                    result=result,
                    strategy=strategy,
                    rejection_reason=self._candidate_rejection_reason(
                        ctx, strategy, result
                    ),
                )
            )

        # A normal learned charge window must not outrank an actually available
        # economic-discharge candidate. Deadline/latest-start reasons remain
        # eligible because those are the explicitly forced planning fallback.
        economic_discharge_available = any(
            candidate["rejection_reason"] is None
            and candidate["state"] == "economic_discharge"
            and str(candidate["result"].action or "") == "discharge"
            for candidate in evaluated
        )
        if economic_discharge_available:
            for candidate in evaluated:
                if (
                    candidate["state"] == "ac_charge_learned"
                    and candidate["reason"] in NON_FORCED_LEARNED_CHARGE_REASONS
                    and candidate["rejection_reason"] is None
                ):
                    candidate["rejection_reason"] = "economic_discharge_window"
        return evaluated

    def _safe_idle_candidate(
        self,
        ctx: RuntimeSnapshot,
        *,
        reason: str,
        rule_name: str,
        index: int,
    ) -> dict[str, Any]:
        """Build an eligible safe-idle candidate."""

        result = self._idle_result(ctx, reason=reason)
        return self._evaluated_candidate(
            index=index,
            rule_name=rule_name,
            result=result,
            strategy=self._strategy_for_candidate(result),
        )

    def _select_candidate(
        self,
        ctx: RuntimeSnapshot,
        evaluated: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Select by protections first, then priority and stable rule order."""

        eligible = [
            candidate
            for candidate in evaluated
            if candidate["rejection_reason"] is None
        ]
        eligible_active = [
            candidate for candidate in eligible if int(candidate["priority"]) > 300
        ]
        safe_idle_rejections = [
            candidate
            for candidate in evaluated
            if candidate["rejection_reason"]
            in {
                "additional_battery_charging_block",
                "additional_battery_discharging_block",
                "grid_sensor_invalid",
            }
        ]

        # A critical grid-data outage always becomes safe idle unless an
        # emergency or explicit manual action is already eligible. Directional
        # blockers become terminal only when no valid opposite strategy remains.
        if (
            safe_idle_rejections or not bool(ctx.grid_sensor_valid)
        ) and not eligible_active:
            reason = (
                "grid_sensor_invalid"
                if not bool(ctx.grid_sensor_valid)
                else str(safe_idle_rejections[0]["rejection_reason"])
            )
            selected = self._safe_idle_candidate(
                ctx,
                reason=reason,
                rule_name="DirectionalBlocker",
                index=len(self._rules) + 1,
            )
            eligible.append(selected)
            evaluated.append(selected)
        elif eligible:
            # max() is stable for equal keys, preserving the rule-order tie-break.
            selected = max(eligible, key=lambda candidate: int(candidate["priority"]))
        else:
            selected = self._safe_idle_candidate(
                ctx,
                reason="idle",
                rule_name="SafeIdleFallback",
                index=len(self._rules) + 2,
            )
            eligible.append(selected)
            evaluated.append(selected)
        return selected, eligible

    def _record_strategy_selection(
        self,
        evaluated: list[dict[str, Any]],
        eligible: list[dict[str, Any]],
        selected: dict[str, Any],
        *,
        selected_reason: str = "highest_priority",
    ) -> None:
        """Publish a stable diagnostic view without leaking internal objects."""

        diagnostics: list[dict[str, Any]] = []
        for candidate in evaluated:
            if candidate is selected:
                status = "selected"
                reason = selected_reason
            elif candidate["rejection_reason"] is not None:
                status = "rejected"
                reason = str(candidate["rejection_reason"])
            else:
                status = "not_selected"
                reason = (
                    "lower_priority"
                    if int(candidate["priority"]) < int(selected["priority"])
                    else "rule_order_tiebreak"
                )
            diagnostics.append(
                {
                    "rule": str(candidate["rule"]),
                    "state": str(candidate["state"]),
                    "reason": str(candidate["reason"]),
                    "priority": int(candidate["priority"]),
                    "requested_mode": str(candidate["requested_mode"]),
                    "status": status,
                    "selection_reason": reason,
                }
            )

        self._last_strategy_selection = {
            "candidate_count": len(evaluated),
            "eligible_candidate_count": len(eligible),
            "selected_rule": str(selected["rule"]),
            "selected_reason": str(selected["reason"]),
            "selected_state": str(selected["state"]),
            "selected_priority": int(selected["priority"]),
            "candidates": diagnostics,
        }

    def evaluate(self, ctx: RuntimeSnapshot) -> DecisionResult:
        """Evaluate every admissible rule and select the highest priority.

        Rule order remains the deterministic tie-breaker only. It no longer
        decides which strategy wins before the V4.3 priority model is applied.
        """

        context_error = self._context_validation_reason(ctx)
        if context_error is not None:
            selected = self._context_error_candidate(ctx, context_error)
            self._record_strategy_selection(
                [selected],
                [selected],
                selected,
                selected_reason="critical_context_invalid",
            )
            return selected["result"]

        evaluated = self._evaluate_candidates(
            ctx,
            self._collect_rule_candidates(ctx),
        )
        selected, eligible = self._select_candidate(ctx, evaluated)
        self._record_strategy_selection(evaluated, eligible, selected)
        return selected["result"]
