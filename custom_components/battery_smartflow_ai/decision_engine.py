from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, List, Literal, Optional

from .const import MANUAL_CONST_DISCHARGE
from .forecast import ForecastSummary
from .power_controller import PowerController, PowerContext


AiMode = Literal["automatic", "summer", "winter", "manual"]
ZendureMode = Literal["input", "output"]
ActionType = Literal["idle", "charge", "discharge", "emergency", "passthrough"]


@dataclass
class PricePoint:
    start: datetime
    end: datetime
    price: float


@dataclass
class DecisionContext:
    now: datetime

    soc: float
    soc_min: float
    soc_max: float

    emergency_soc: float
    emergency_charge_w: float

    max_charge_w: float
    max_discharge_w: float

    grid_import_w: float
    grid_export_w: float
    pv_w: float
    house_load_w: float

    price_now: Optional[float]
    avg_charge_price: Optional[float]
    expensive_threshold: float
    very_expensive_threshold: float
    profit_margin_pct: float
    price_points: List[PricePoint]

    ai_mode: AiMode
    manual_action: Optional[str]
    season: Literal["winter", "summer"]

    profile: dict
    prev_discharge_w: float
    prev_charge_w: float

    battery_capacity_kwh: float

    additional_battery_charge_w: float = 0.0
    additional_battery_discharge_w: float = 0.0
    pv_charge_start_export_w: float = 80.0

    peak_factor: float = 1.35
    valley_factor: float = 0.85
    very_cheap_price: Optional[float] = None
    
    # V4.2.3-Beta3:
    # Opportunity cost of using PV for charging instead of exporting it.
    # If no feed-in tariff is available, 0.0 is conservative: only zero/negative
    # grid prices may override currently useful PV.
    feed_in_tariff: float = 0.0

    # V3.5.0 cell voltage protection
    cell_voltage_emergency_active: bool = False

    # V4.0.0 optional forecast input
    forecast: Optional[ForecastSummary] = None

    # V4.1.0 learned charge-window planning
    # Passed in from coordinator as an object from learned_planning.py.
    # Keep this typed as Any to avoid circular imports.
    learned_charge_plan: Any | None = None
    learned_planning_enabled: bool = False

    # Runtime counters / debounce
    pv_charge_start_counter: int = 0
    pv_charge_stop_counter: int = 0
    forecast_wait_block_counter: int = 0
    pv_charge_latched: bool = False

    # Protection state from coordinator
    discharge_blocked_by_soc_min: bool = False
    cell_voltage_discharge_blocked: bool = False

    # SF800Pro PV house-load passthrough state
    pv_houseload_passthrough_active: bool = False
    pv_houseload_passthrough_target_w: float = 0.0
    pv_houseload_passthrough_stop_reason: str = "none"
    
    # V4.2.x Off-Grid / Inselsteckdose
    offgrid_power_w: float = 0.0
    offgrid_mode: str = "not_configured"
    offgrid_available: bool = False
    offgrid_active: bool = False
    offgrid_load_active: bool = False
    offgrid_source_active: bool = False
    
    # V4.3.0-dev5.2 unified AutomaticStrategy context
    automatic_strategy_active: bool = False
    automatic_weighting: str = "inactive"
    automatic_pv_weight: float = 0.0
    automatic_price_weight: float = 0.0
    automatic_reserve_weight: float = 0.0
    automatic_forecast_weight: float = 0.0
    automatic_discharge_allowed: bool = False
    automatic_discharge_reason: str = "not_evaluated"
    
    # V4.3.0-dev5.3 strategic peak-reserve context
    automatic_peak_reserve_allowed: bool = False
    automatic_peak_reserve_reason: str = "not_evaluated"

    # V4.3.0-dev5.4 optional valley-charge context
    automatic_valley_charge_allowed: bool = False
    automatic_valley_charge_reason: str = "not_evaluated"    


@dataclass
class DecisionResult:
    action: ActionType
    ac_mode: ZendureMode
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
        if float(ctx.additional_battery_charge_w or 0.0) > 0.0:
            return engine._idle_result(
                ctx,
                reason="additional_battery_charging_block",
            )
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
            and ctx.ai_mode in ("automatic", "winter")
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
                ctx.price_now is not None
                and ctx.price_now >= ctx.very_expensive_threshold
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
            ctx.price_now is not None
            and ctx.avg_charge_price is not None
            and ctx.soc > ctx.soc_min
            and ctx.ai_mode in ("automatic", "winter")
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
        - classic planning remains fallback
        """
        if not bool(getattr(ctx, "learned_planning_enabled", False)):
            return None

        plan = getattr(ctx, "learned_charge_plan", None)
        if plan is None:
            return None

        if ctx.ai_mode not in ("automatic", "winter"):
            return None

        if ctx.soc >= ctx.soc_max:
            return None

        if ctx.price_now is None or not ctx.price_points:
            return None

        if ctx.battery_capacity_kwh <= 0 or ctx.max_charge_w <= 0:
            return None

        if float(ctx.additional_battery_charge_w or 0.0) > 0.0:
            return None

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

        if decision_reason == "learned_charge_window_no_charge_needed":
            return None

        if mode == "wait" or decision_reason == "learned_charge_window_wait":
            # Learned waiting must not suppress classic immediate charging rules.
            # If the learned planner only wants to wait, continue with the normal
            # planning / valley / forecast rules below.
            return None

        if mode == "charge" or decision_reason in (
            "learned_charge_window_active",
            "learned_charge_window_latest_start_reached",
            "learned_charge_window_deadline_too_close_start_now",
        ):
            planned_power_w = float(
                getattr(plan, "effective_charge_power_w", 0.0) or 0.0
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
                    target_soc=ctx.soc_max,
                ),
            )

        return None


class PlanningRule(BaseRule):
    def evaluate(self, engine, ctx):
        if engine._pv_morning_transition_active(ctx):
            return None
        return engine._evaluate_adaptive_planning(ctx)


class VeryCheapRule(BaseRule):
    def evaluate(self, engine, ctx):
        if ctx.ai_mode not in ("automatic", "winter"):
            return None

        if ctx.price_now is None or ctx.very_cheap_price is None:
            return None

        if ctx.soc >= ctx.soc_max:
            return None

        if float(ctx.price_now) > float(ctx.very_cheap_price):
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

        if ctx.price_now is None:
            return None

        if ctx.soc >= ctx.soc_max:
            return None

        if not ctx.price_points:
            return None

        prices = [p.price for p in ctx.price_points]
        if not prices:
            return None

        valley_threshold = engine._compute_valley_threshold(prices, ctx.valley_factor)

        if ctx.price_now > valley_threshold:
            return None

        if ctx.pv_w < 100:
            return None
            
        # V4.2.3-Beta3:
        # Valley boost is still optional grid charging. If useful PV is already
        # available and grid energy is not cheaper than PV opportunity cost,
        # keep PV charging priority.
        if engine._optional_grid_charge_should_wait_for_pv(ctx):
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

        if ctx.price_now is None:
            return None

        if ctx.soc >= ctx.soc_max:
            return None

        if not ctx.price_points:
            return None

        if not engine._is_valley_price_now(ctx):
            return None

        # V4.2.3-Beta3:
        # Valley opportunity is only optional grid charging. It must not take over
        # while useful PV is available or already charging the battery, unless grid
        # energy is economically better than using/exporting PV.
        if engine._optional_grid_charge_should_wait_for_pv(ctx):
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
        if not engine._pv_houseload_passthrough_enabled(ctx):
            return None

        if ctx.ai_mode == "summer" or (
            ctx.ai_mode == "automatic" and ctx.season == "summer"
        ):
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
        
        
class AutomaticSummerPeakReserveRule(BaseRule):
    """Strategic peak reserve for unified Automatic mode.

    V4.3.0-dev5.3:
    The historic class name remains temporarily, but the rule is no longer
    activated through the detected summer season. AutomaticStrategy provides
    the high-level permission; DecisionEngine validates the actual future peak,
    energy need, target SoC and economic charge window.
    """

    def evaluate(self, engine, ctx):
        if not engine._automatic_summer_peak_reserve_enabled(ctx):
            return None

        if ctx.soc >= ctx.soc_max:
            return None

        if ctx.price_now is None or not ctx.price_points:
            return None
            
        # V4.2.8:
        # Peak-reserve charging must not be limited to the formal valley
        # threshold only. On generally expensive days, the cheapest useful slot
        # before a later peak can still be above the calculated valley threshold.
        #
        # It must, however, never start during the high-price/peak window itself.
        if not engine._automatic_summer_peak_reserve_charge_window(ctx):
            return None

        target_soc = engine._automatic_summer_peak_target_soc(ctx)
        if target_soc is None:
            return None

        if float(ctx.soc) >= float(target_soc):
            return None

        expected_peak_price = engine._automatic_summer_expected_peak_price(ctx)
        if expected_peak_price is None:
            return None

        # Grid charging must still be economically meaningful compared to the
        # upcoming high-price window. Feed-in tariff must not block this case.
        min_profit_factor = 1.0 + (float(ctx.profit_margin_pct or 0.0) / 100.0)
        if float(ctx.price_now) * min_profit_factor > float(expected_peak_price):
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
        planning = engine._evaluate_adaptive_planning(ctx)
        if planning is not None:
            return None

        if ctx.soc >= ctx.soc_max:
            return None

        if (
            engine._pv_houseload_passthrough_enabled(ctx)
            and bool(ctx.pv_houseload_passthrough_active)
        ):
            return None

        export_w = float(ctx.grid_export_w or 0.0)
        import_w = float(ctx.grid_import_w or 0.0)
        prev_charge_w = float(ctx.prev_charge_w or 0.0)
        prev_discharge_w = float(ctx.prev_discharge_w or 0.0)
        start_export_threshold = float(ctx.pv_charge_start_export_w or 0.0)

        has_direct_surplus = export_w >= start_export_threshold

        protection_active = (
            engine._low_soc_protection_strict(ctx)
            and engine._discharge_protection_active(ctx)
        )

        # A previous 60 W discharge keepalive must not suppress PV surplus charge.
        # If there is real PV surplus, PV charging may take over even when
        # prev_discharge_w is still > 0 from the previous cycle.
        discharge_active = prev_discharge_w > 0.0
        if discharge_active and not engine._pv_surplus_blocks_discharge(ctx):
            return None

        prices = [p.price for p in ctx.price_points] if ctx.price_points else []
        valley_active = (
            ctx.ai_mode in ("automatic", "winter")
            and ctx.season == "winter"
            and ctx.price_now is not None
            and len(prices) > 0
            and ctx.price_now <= engine._compute_valley_threshold(prices, ctx.valley_factor)
        )

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
        )

        if not start_allowed and not keepalive_charge:
            return None

        charge_w = engine._delta_charge(ctx)

        if protection_active and engine._low_soc_pv_charge_requires_export(ctx):
            # SF800Pro / Low-SoC-Schutz:
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
                # Beim SF800Pro darf INPUT nicht künstlich über 80 W gehalten werden,
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


class SummerRule(BaseRule):
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
                    
                if engine._automatic_summer_should_hold_peak_reserve(ctx):
                    return engine._idle_result(
                        ctx,
                        reason="summer_peak_reserve_hold",
                    )

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
                                ctx.profile.get("DEADBAND_W", 30.0),
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
        self._rules = [
            EmergencyRule(),
            AdditionalBatteryBlockRule(),
            AdditionalBatteryDischargeBlockRule(),
            ManualRule(),
            VeryCheapRule(),
            PvHouseLoadPassthroughRule(),
            AutomaticSummerPeakReserveRule(),
            PvRule(),
            PeakRule(),
            ArbitrageRule(),
            LearnedPlanningRule(),
            PlanningRule(),
            ValleyBoostRule(),
            ValleyOpportunityRule(),
            SummerRule(),
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
        if not self._additional_battery_discharge_blocks_charge(ctx):
            return None

        return self._idle_result(
            ctx,
            reason="additional_battery_discharging_block",
        )

    def _profile_flag(self, ctx: DecisionContext, key: str, default: bool = False) -> bool:
        try:
            return bool(ctx.profile.get(key, default))
        except Exception:
            return bool(default)

    def _low_soc_protection_strict(self, ctx: DecisionContext) -> bool:
        return self._profile_flag(ctx, "LOW_SOC_PROTECTION_STRICT", False)

    def _low_soc_pv_charge_requires_export(self, ctx: DecisionContext) -> bool:
        return self._profile_flag(ctx, "LOW_SOC_PV_CHARGE_REQUIRES_EXPORT", False)

    def _low_soc_discharge_requires_cell_resume(self, ctx: DecisionContext) -> bool:
        return self._profile_flag(ctx, "LOW_SOC_DISCHARGE_REQUIRES_CELL_RESUME", False)

    def _pv_houseload_passthrough_enabled(self, ctx: DecisionContext) -> bool:
        return self._profile_flag(ctx, "PV_HOUSELOAD_PASSTHROUGH", False)
        
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

        export_w = float(ctx.grid_export_w or 0.0)
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
        export_w = max(0.0, float(ctx.grid_export_w or 0.0))
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

        if ctx.price_now is None:
            return False

        try:
            price_now = float(ctx.price_now)
        except Exception:
            return False

        try:
            pv_opportunity_price = max(0.0, float(ctx.feed_in_tariff or 0.0))
        except Exception:
            pv_opportunity_price = 0.0

        # Small epsilon avoids oscillation on equal/rounded values.
        return price_now <= (pv_opportunity_price - 0.001)

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
        
    def _pv_surplus_should_prefer_pv_charge(self, ctx: DecisionContext) -> bool:
        """Return True when normal valley-opportunity charging should not
        replace PV surplus charging.

        Valley opportunity charging is only an optional cheap-price charge.
        If PV surplus charging is already active/latched or clearly possible,
        PV charging should keep priority. This prevents strategy flapping
        between pv_surplus_charge and valley_opportunity_charge.

        Important:
        During an active INPUT/PV charge phase the charge itself can create
        temporary grid import. That import must not be interpreted as a reason
        to switch from PV surplus charging to valley-opportunity charging.
        """

        if ctx.soc >= ctx.soc_max:
            return False

        export_w = float(ctx.grid_export_w or 0.0)
        import_w = float(ctx.grid_import_w or 0.0)
        pv_w = float(ctx.pv_w or 0.0)
        house_load_w = float(ctx.house_load_w or 0.0)
        start_export_threshold = float(ctx.pv_charge_start_export_w or 0.0)

        # Strongest rule:
        # If PV charge is latched, ValleyOpportunity must not take over.
        # The PV charge hysteresis / latch logic is responsible for deciding
        # when PV charging has really ended.
        if bool(ctx.pv_charge_latched):
            return True

        # If PV charge start confirmation is currently running, do not switch
        # to valley opportunity for one or two cycles.
        if int(ctx.pv_charge_start_counter or 0) > 0:
            return True

        # If PV charge stop confirmation is counting, keep ValleyOpportunity out
        # until the PV hysteresis has fully released.
        if int(ctx.pv_charge_stop_counter or 0) > 0:
            return True

        # Direct export means PV surplus is actually available.
        if export_w >= max(40.0, start_export_threshold * 0.50):
            return True

        # Fallback when the grid export signal is noisy or delayed:
        # PV clearly exceeds the known house load and there is no strong import.
        if (
            pv_w >= house_load_w + max(80.0, start_export_threshold * 0.50)
            and import_w <= 180.0
        ):
            return True

        return False

    def _compute_base_price(self, prices: List[float]) -> float:
        return sum(prices) / len(prices)

    def _compute_peak_threshold(self, prices: List[float], peak_factor: float) -> float:
        base_price = self._compute_base_price(prices)
        return max(base_price * peak_factor, base_price + 0.03)

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
        if not ctx.price_points:
            return None

        prices = [p.price for p in ctx.price_points]
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
            feed_in_floor = max(0.0, float(ctx.feed_in_tariff or 0.0)) * (
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

        # Do not force valid economic discharge to the configured expensive
        # threshold. The configured threshold remains relevant when no real
        # charge price exists and for the separate very-expensive force logic.
        effective = min(effective, market_peak_threshold)

        return effective

    def _with_thresholds(self, ctx: DecisionContext, result: DecisionResult) -> DecisionResult:
        prices = [p.price for p in ctx.price_points] if ctx.price_points else []
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

        if ctx.price_now is None:
            return False

        effective_threshold = self._compute_effective_discharge_threshold(ctx)
        if effective_threshold is None:
            return False

        return float(ctx.price_now) >= float(effective_threshold)
        
    def _automatic_summer_peak_reserve_enabled(
        self,
        ctx: DecisionContext,
    ) -> bool:
        """Return whether Automatic may evaluate strategic peak reserve.

        V4.3.0-dev5.3:
        The historic method name remains temporarily for compatibility with the
        existing helper chain. The permission is no longer tied to the detected
        summer season.

        Dev6 may rename the complete helper family after all automatic
        summer/winter paths have been migrated.
        """
        return bool(
            ctx.ai_mode == "automatic"
            and ctx.automatic_strategy_active
            and ctx.automatic_peak_reserve_allowed
            and ctx.price_now is not None
            and bool(ctx.price_points)
            and ctx.battery_capacity_kwh > 0
        )


    def _automatic_summer_future_peak_slots(
        self,
        ctx: DecisionContext,
    ) -> list[PricePoint]:
        if not self._automatic_summer_peak_reserve_enabled(ctx):
            return []

        prices = [p.price for p in ctx.price_points]
        if not prices:
            return []

        peak_threshold = self._compute_peak_threshold(prices, ctx.peak_factor)

        future_slots = [
            p
            for p in ctx.price_points
            if p.end > ctx.now
            and (
                p.price >= peak_threshold
                or p.price >= float(ctx.very_expensive_threshold)
            )
        ]

        return sorted(future_slots, key=lambda p: p.start)


    def _automatic_summer_expected_peak_price(
        self,
        ctx: DecisionContext,
    ) -> float | None:
        slots = self._automatic_summer_future_peak_slots(ctx)
        if not slots:
            return None

        try:
            return max(float(p.price) for p in slots)
        except Exception:
            return None


    def _automatic_summer_peak_reserve_charge_window(
        self,
        ctx: DecisionContext,
    ) -> bool:
        """Return True when current price is a useful charge slot before a later
        Automatic-summer peak.

        This is intentionally broader than _is_valley_price_now(). The formal
        valley threshold can be too strict on generally expensive days.
        """

        if not self._automatic_summer_peak_reserve_enabled(ctx):
            return False

        if ctx.price_now is None or not ctx.price_points:
            return False

        future_slots = self._automatic_summer_future_peak_slots(ctx)
        future_slots = [p for p in future_slots if p.start > ctx.now]
        if not future_slots:
            return False

        next_peak = min(future_slots, key=lambda p: p.start)
        expected_peak_price = self._automatic_summer_expected_peak_price(ctx)
        if expected_peak_price is None:
            return False

        prices = [p.price for p in ctx.price_points]
        if not prices:
            return False

        market_peak_threshold = self._compute_peak_threshold(
            prices,
            ctx.peak_factor,
        )

        price_now = float(ctx.price_now)

        # Never charge into an already active high-price/peak window.
        if price_now >= float(market_peak_threshold):
            return False

        # Additional safety: if the current price is already close to the
        # expected peak, do not switch back to INPUT.
        if price_now >= float(expected_peak_price) * 0.85:
            return False

        candidate_slots = [
            p
            for p in ctx.price_points
            if p.end > ctx.now and p.start <= next_peak.start
        ]

        if not candidate_slots:
            return False

        candidate_prices = [float(p.price) for p in candidate_slots]
        local_min = min(candidate_prices)
        local_max = max(candidate_prices)

        # Allow the cheaper part of the remaining pre-peak window.
        cheap_band_limit = local_min + max(
            0.015,
            (local_max - local_min) * 0.35,
        )

        if price_now <= cheap_band_limit:
            return True

        # Urgency fallback:
        # If the peak is approaching and the battery is still clearly below the
        # target reserve, allow charging even if the current slot is not among
        # the very cheapest remaining slots.
        target_soc = self._automatic_summer_peak_target_soc(ctx)
        if target_soc is None:
            return False

        soc_gap_pct = max(0.0, float(target_soc) - float(ctx.soc))
        required_kwh = float(ctx.battery_capacity_kwh) * (soc_gap_pct / 100.0)

        charge_power_kw = max(0.1, float(ctx.max_charge_w or 0.0) / 1000.0)
        hours_needed = max(0.25, required_kwh / charge_power_kw)

        hours_until_peak = max(
            0.0,
            (next_peak.start - ctx.now).total_seconds() / 3600.0,
        )

        return bool(
            required_kwh > 0.15
            and hours_until_peak <= hours_needed * 1.25
            and price_now < float(expected_peak_price) * 0.80
        )


    def _automatic_summer_peak_target_soc(
        self,
        ctx: DecisionContext,
    ) -> float | None:
        expected_peak = self._automatic_summer_expected_peak_price(ctx)
        if expected_peak is None:
            return None

        prices = [p.price for p in ctx.price_points] if ctx.price_points else []
        if not prices:
            return None

        peak_threshold = self._compute_peak_threshold(prices, ctx.peak_factor)

        # Severity-based target. This is intentionally simple and conservative for
        # V4.2.4: avoid a large architecture change, but stop entering extreme peaks
        # with only 60-70% SoC.
        if expected_peak >= float(ctx.very_expensive_threshold):
            target_soc = 95.0
        elif expected_peak >= peak_threshold * 1.35:
            target_soc = 90.0
        elif expected_peak >= peak_threshold * 1.15:
            target_soc = 85.0
        else:
            target_soc = 80.0

        return max(
            float(ctx.soc_min),
            min(float(ctx.soc_max), float(target_soc)),
        )


    def _automatic_summer_should_hold_peak_reserve(
        self,
        ctx: DecisionContext,
    ) -> bool:
        """Return True when Automatic summer mode should preserve energy for later,
        higher price slots instead of discharging too early.
        """

        if not self._automatic_summer_peak_reserve_enabled(ctx):
            return False

        if ctx.soc <= ctx.soc_min:
            return False

        target_soc = self._automatic_summer_peak_target_soc(ctx)
        if target_soc is None:
            return False

        # Only hold when the battery is still below the desired reserve level.
        if float(ctx.soc) >= float(target_soc):
            return False

        future_slots = [
            p for p in self._automatic_summer_future_peak_slots(ctx)
            if p.start > ctx.now
        ]
        if not future_slots:
            return False

        future_peak = max(float(p.price) for p in future_slots)

        if ctx.price_now is None:
            return False

        # Do not block discharge when the current slot is already one of the best
        # slots. Only preserve energy if a clearly better price is still ahead.
        return future_peak >= float(ctx.price_now) + max(0.03, float(ctx.price_now) * 0.10)

    def _is_effective_discharge_price_reached(self, ctx: DecisionContext) -> bool:
        if ctx.price_now is None:
            return False

        effective_threshold = self._compute_effective_discharge_threshold(ctx)
        if effective_threshold is None:
            return False

        return float(ctx.price_now) >= float(effective_threshold)

    def _is_valley_price_now(self, ctx: DecisionContext) -> bool:
        if ctx.price_now is None or not ctx.price_points:
            return False

        prices = [p.price for p in ctx.price_points]
        if not prices:
            return False

        valley_threshold = self._compute_valley_threshold(prices, ctx.valley_factor)
        return float(ctx.price_now) <= float(valley_threshold)

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

    def _profile_for_discharge(self, profile: dict) -> dict:
        mapped = dict(profile)
        mapped["DEADBAND_W"] = profile.get("DISCHARGE_DEADBAND_W", profile.get("DEADBAND_W"))
        mapped["KP_UP"] = profile.get("DISCHARGE_KP_UP", profile.get("KP_UP"))
        mapped["KP_DOWN"] = profile.get("DISCHARGE_KP_DOWN", profile.get("KP_DOWN"))
        mapped["MAX_STEP_UP"] = profile.get("DISCHARGE_MAX_STEP_UP", profile.get("MAX_STEP_UP"))
        mapped["MAX_STEP_DOWN"] = profile.get("DISCHARGE_MAX_STEP_DOWN", profile.get("MAX_STEP_DOWN"))
        return mapped

    def _profile_for_charge(self, profile: dict) -> dict:
        mapped = dict(profile)
        mapped["DEADBAND_W"] = profile.get("CHARGE_DEADBAND_W", profile.get("DEADBAND_W"))
        mapped["KP_UP"] = profile.get("CHARGE_KP_UP", profile.get("KP_UP"))
        mapped["KP_DOWN"] = profile.get("CHARGE_KP_DOWN", profile.get("KP_DOWN"))
        mapped["MAX_STEP_UP"] = profile.get("CHARGE_MAX_STEP_UP", profile.get("MAX_STEP_UP"))
        mapped["MAX_STEP_DOWN"] = profile.get("CHARGE_MAX_STEP_DOWN", profile.get("MAX_STEP_DOWN"))
        return mapped

    def _to_power_ctx(self, ctx: DecisionContext, mode: Literal["charge", "discharge"]) -> PowerContext:
        effective_profile = (
            self._profile_for_discharge(ctx.profile)
            if mode == "discharge"
            else self._profile_for_charge(ctx.profile)
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
            profile=effective_profile,
        )

    def _delta_discharge(self, ctx: DecisionContext) -> float:
        return PowerController.delta_discharge(self._to_power_ctx(ctx, "discharge"))

    def _delta_charge(self, ctx: DecisionContext) -> float:
        return PowerController.delta_charge(self._to_power_ctx(ctx, "charge"))

    def _detect_adaptive_peak(self, ctx: DecisionContext) -> bool:
        if not ctx.price_points or ctx.price_now is None:
            return False

        prices = [p.price for p in ctx.price_points]
        if not prices:
            return False

        threshold = self._compute_peak_threshold(prices, ctx.peak_factor)

        if ctx.price_now >= threshold:
            return True

        future_slots = sorted(
            [p for p in ctx.price_points if p.start > ctx.now],
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
        if (
            ctx.ai_mode not in ("automatic", "winter")
            or not ctx.price_points
            or ctx.price_now is None
            or ctx.soc >= ctx.soc_max
            or ctx.battery_capacity_kwh <= 0
            or ctx.max_charge_w <= 0
        ):
            return None

        prices = [p.price for p in ctx.price_points]
        if not prices:
            return None

        if ctx.very_cheap_price is not None and ctx.price_now <= ctx.very_cheap_price:
            return None

        valley_threshold = self._compute_valley_threshold(prices, ctx.valley_factor)
        if ctx.price_now > valley_threshold:
            return None

        peak_threshold = self._compute_peak_threshold(prices, ctx.peak_factor)

        peak_slots = [p for p in ctx.price_points if p.price >= peak_threshold]
        future_peaks = [p for p in peak_slots if p.start > ctx.now]

        if not future_peaks:
            return None

        expected_peak_price = max(p.price for p in future_peaks)

        min_profit_factor = 1 + (ctx.profit_margin_pct / 100)
        required_peak_price = ctx.price_now * min_profit_factor

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

        future_prices = [p for p in ctx.price_points if ctx.now <= p.start <= next_peak]

        if future_prices:
            energy_per_slot = charge_power_kw * 0.25
            if energy_per_slot > 0:
                required_slots = max(1, math.ceil(required_kwh / energy_per_slot))
                cheapest_slots = sorted(future_prices, key=lambda p: p.price)[:required_slots]

                if not cheapest_slots:
                    return None

                cheapest_prices = [p.price for p in cheapest_slots]
                if ctx.price_now > max(cheapest_prices):
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

    def evaluate(self, ctx: DecisionContext) -> DecisionResult:
        for rule in self._rules:
            result = rule.evaluate(self, ctx)
            if result:
                return result

        return self._idle_result(
            ctx,
            reason="idle",
        )
