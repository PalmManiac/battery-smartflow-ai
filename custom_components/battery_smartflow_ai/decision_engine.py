from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Literal, Optional

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
    pv_charge_start_export_w: float = 80.0

    peak_factor: float = 1.35
    valley_factor: float = 0.85
    very_cheap_price: Optional[float] = None

    # V3.5.0 cell voltage protection
    cell_voltage_emergency_active: bool = False

    # V4.0.0 optional forecast input
    forecast: Optional[ForecastSummary] = None

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


class PeakRule(BaseRule):
    def evaluate(self, engine, ctx):
        export_active = float(ctx.grid_export_w or 0.0) > 80.0
        discharge_active = float(ctx.prev_discharge_w or 0.0) > 0.0

        if export_active and not discharge_active:
            return None

        if ctx.soc > ctx.soc_min and ctx.ai_mode in ("automatic", "winter"):
            if (
                engine._detect_adaptive_peak(ctx)
                and engine._is_effective_discharge_price_reached(ctx)
            ):
                discharge_w = engine._delta_discharge(ctx)
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
        export_active = float(ctx.grid_export_w or 0.0) > 80.0
        discharge_active = float(ctx.prev_discharge_w or 0.0) > 0.0

        if export_active and not discharge_active:
            return None

        if (
            ctx.price_now is not None
            and ctx.avg_charge_price is not None
            and ctx.soc > ctx.soc_min
            and ctx.ai_mode in ("automatic", "winter")
            and engine._is_market_discharge_window(ctx)
            and engine._is_effective_discharge_price_reached(ctx)
        ):
            discharge_w = engine._delta_discharge(ctx)
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

        if ctx.ai_mode not in ("winter", "automatic") or ctx.season != "winter":
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

        soc_gap_pct = max(0.0, ctx.soc_max - ctx.soc)
        base_required_kwh = ctx.battery_capacity_kwh * (soc_gap_pct / 100.0)

        if engine._forecast_supports_waiting(ctx, base_required_kwh):
            return None

        charge_w = ctx.max_charge_w
        reason = "valley_boost_charge"

        if engine._forecast_available(ctx) and engine._forecast_outlook(ctx) == "mixed":
            charge_w = max(300.0, float(ctx.max_charge_w) * 0.75)
            reason = "valley_boost_charge_mixed_forecast"

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

        if ctx.ai_mode not in ("automatic", "winter") or ctx.season != "winter":
            return None

        if ctx.price_now is None:
            return None

        if ctx.soc >= ctx.soc_max:
            return None

        if not ctx.price_points:
            return None

        if not engine._is_valley_price_now(ctx):
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

        discharge_active = prev_discharge_w > 0.0
        if discharge_active:
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

        if soft_start_ready and not keepalive_charge and not sf800_passthrough_enabled:
            if import_w <= 60.0:
                charge_w = max(charge_w, 80.0)

        charge_w = min(float(charge_w), float(ctx.max_charge_w))

        if charge_w > 0:
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
        if (
            ctx.ai_mode == "summer"
            or (ctx.ai_mode == "automatic" and ctx.season == "summer")
        ):
            if (
                ctx.soc > ctx.soc_min
                and not (
                    engine._low_soc_protection_strict(ctx)
                    and engine._discharge_protection_active(ctx)
                )
            ):
                discharge_w = engine._delta_discharge(ctx)
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
            ManualRule(),
            VeryCheapRule(),
            PvHouseLoadPassthroughRule(),
            PvRule(),
            PeakRule(),
            ArbitrageRule(),
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

    def _discharge_protection_active(self, ctx: DecisionContext) -> bool:
        return bool(
            ctx.discharge_blocked_by_soc_min
            or ctx.cell_voltage_discharge_blocked
        )

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

        if economic_threshold is None:
            return market_peak_threshold

        market_anchor = market_peak_threshold * 0.82
        effective = (market_anchor * 0.70) + (economic_threshold * 0.30)

        effective = max(effective, economic_threshold)
        effective = max(effective, valley_threshold)
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
        if ctx.price_now is None or not ctx.price_points:
            return False

        prices = [p.price for p in ctx.price_points]
        if not prices:
            return False

        market_peak_threshold = self._compute_peak_threshold(prices, ctx.peak_factor)
        market_anchor = market_peak_threshold * 0.82

        return float(ctx.price_now) >= float(market_anchor)

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
