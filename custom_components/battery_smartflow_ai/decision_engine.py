from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Literal, Optional

from .const import MANUAL_CONST_DISCHARGE
from .power_controller import PowerController, PowerContext


AiMode = Literal["automatic", "summer", "winter", "manual"]
ZendureMode = Literal["input", "output"]
ActionType = Literal["idle", "charge", "discharge", "emergency"]


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

    peak_factor: float = 1.35
    valley_factor: float = 0.85
    very_cheap_price: Optional[float] = None

    # V3.5.0 cell voltage protection
    cell_voltage_emergency_active: bool = False


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
            return engine._with_thresholds(
                ctx,
                DecisionResult(
                    action="idle",
                    ac_mode="input",
                    charge_w=0.0,
                    discharge_w=0.0,
                    reason="additional_battery_charging_block",
                ),
            )
        return None


class PeakRule(BaseRule):
    def evaluate(self, engine, ctx):
        if float(ctx.grid_export_w or 0.0) > 80.0:
            return None
        if (
            ctx.soc > ctx.soc_min
            and ctx.ai_mode in ("automatic", "winter", "summer")
        ):
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
        if float(ctx.grid_export_w or 0.0) > 80.0:
            return None
        if (
            ctx.price_now is not None
            and ctx.avg_charge_price is not None
            and ctx.soc > ctx.soc_min
            and ctx.ai_mode in ("automatic", "winter", "summer")
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
        return engine._evaluate_adaptive_planning(ctx)


class ValleyBoostRule(BaseRule):
    def evaluate(self, engine, ctx):
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

        return engine._with_thresholds(
            ctx,
            DecisionResult(
                action="charge",
                ac_mode="input",
                charge_w=ctx.max_charge_w,
                discharge_w=0.0,
                reason="valley_boost_charge",
            ),
        )


class PvRule(BaseRule):
    def evaluate(self, engine, ctx):
        planning = engine._evaluate_adaptive_planning(ctx)
        if planning is not None:
            return None

        if ctx.soc >= ctx.soc_max:
            return None

        export_w = float(ctx.grid_export_w or 0.0)
        pv_w = float(ctx.pv_w or 0.0)
        prev_charge_w = float(ctx.prev_charge_w or 0.0)

        has_direct_surplus = export_w >= 80.0

        keepalive_charge = (
            prev_charge_w > 0.0
            and pv_w >= max(150.0, prev_charge_w * 0.35)
        )

        if not has_direct_surplus and not keepalive_charge:
            return None

        charge_w = engine._delta_charge(ctx)

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
            if ctx.soc > ctx.soc_min:
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

        return engine._with_thresholds(
            ctx,
            DecisionResult(
                action="idle",
                ac_mode="input",
                charge_w=0.0,
                discharge_w=0.0,
                reason="manual_idle",
            ),
        )


class DecisionEngine:
    def __init__(self):
        self._rules = [
            EmergencyRule(),
            AdditionalBatteryBlockRule(),
            PvRule(),
            PeakRule(),
            ArbitrageRule(),
            PlanningRule(),
            ValleyBoostRule(),
            SummerRule(),
            ManualRule(),
        ]

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
            ctx.ai_mode not in ("automatic", "winter", "summer")
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

        if ctx.very_cheap_price is not None and ctx.price_now > ctx.very_cheap_price:
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
        required_kwh = ctx.battery_capacity_kwh * (soc_gap_pct / 100.0)

        if second_peak is not None:
            hours_between_peaks = (second_peak - next_peak).total_seconds() / 3600.0
            if hours_between_peaks < 6:
                required_kwh *= 1.4

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
            return self._with_thresholds(
                ctx,
                DecisionResult(
                    action="charge",
                    ac_mode="input",
                    charge_w=ctx.max_charge_w,
                    discharge_w=0.0,
                    reason="planning_latest_start",
                    target_soc=ctx.soc_max,
                ),
            )

        return None

    def evaluate(self, ctx: DecisionContext) -> DecisionResult:
        for rule in self._rules:
            result = rule.evaluate(self, ctx)
            if result:
                return result

        return self._with_thresholds(
            ctx,
            DecisionResult(
                action="idle",
                ac_mode="input",
                charge_w=0.0,
                discharge_w=0.0,
                reason="idle",
            ),
        )
