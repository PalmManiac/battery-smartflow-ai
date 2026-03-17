from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Literal, Optional

from .power_controller import PowerController, PowerContext
from .const import MANUAL_CONST_DISCHARGE


# --------------------------------------------------
# TYPES
# --------------------------------------------------

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

    # Zusatzakku + Wallbox Koordination
    additional_battery_charge_w: float = 0.0
    additional_battery_discharge_w: float = 0.0
    wallbox_active_w: float = 0.0

    # --- Planning tuning ---
    peak_factor: float = 1.35
    valley_factor: float = 0.85
    very_cheap_price: Optional[float] = None

    # --- PV-Forecast-basierte Nachtladung (v3.2) ---
    pv_forecast_kwh: float = -1.0             # -1 = Feature deaktiviert / Sensor unavailable
    additional_battery_soc: float = -1.0      # -1 = kein Zusatzakku konfiguriert
    additional_battery_capacity_kwh: float = 0.0
    daily_consumption_kwh: float = 12.0
    bridge_kwh: float = 1.5
    nighttime_kwh: float = 0.0                # Hausverbrauch bis 05:00 (0 tagsüber)
    pv_self_consumption_kwh: float = 5.0      # PV direkt Hausverbrauch tagsüber (nicht in Batterie)


@dataclass
class DecisionResult:
    action: ActionType
    ac_mode: ZendureMode
    charge_w: float
    discharge_w: float
    reason: str
    target_soc: Optional[float] = None


# ==================================================
# RULE BASE
# ==================================================

class BaseRule:
    def evaluate(
        self,
        engine: "DecisionEngine",
        ctx: DecisionContext,
    ) -> Optional[DecisionResult]:
        raise NotImplementedError


# ==================================================
# RULES
# ==================================================

class EmergencyRule(BaseRule):
    def evaluate(self, engine, ctx):
        if ctx.soc <= ctx.emergency_soc:
            return DecisionResult(
                action="emergency",
                ac_mode="input",
                charge_w=min(ctx.max_charge_w, ctx.emergency_charge_w),
                discharge_w=0.0,
                reason="emergency_latched_charge",
            )
        return None


class PeakRule(BaseRule):
    def evaluate(self, engine, ctx):
        if engine._byd_blocks_discharge(ctx) or engine._wallbox_blocks_discharge(ctx):
            return None
        if (
            ctx.soc > ctx.soc_min + 5
            and ctx.ai_mode in ("automatic", "winter")
            and not engine._is_real_export(ctx)
        ):
            if engine._detect_adaptive_peak(ctx):
                discharge_w = engine._delta_discharge(ctx)
                return DecisionResult(
                    action="discharge",
                    ac_mode="output",
                    charge_w=0.0,
                    discharge_w=discharge_w,
                    reason="adaptive_peak_discharge",
                )

            if (
                ctx.price_now is not None
                and ctx.price_now >= ctx.very_expensive_threshold
            ):
                discharge_w = engine._delta_discharge(ctx)
                return DecisionResult(
                    action="discharge",
                    ac_mode="output",
                    charge_w=0.0,
                    discharge_w=discharge_w,
                    reason="very_expensive_force_discharge",
                )
        return None


class ArbitrageRule(BaseRule):
    def evaluate(self, engine, ctx):
        if engine._byd_blocks_discharge(ctx) or engine._wallbox_blocks_discharge(ctx):
            return None
        if (
            ctx.price_now is not None
            and ctx.avg_charge_price is not None
            and ctx.price_now >= ctx.expensive_threshold
            and ctx.price_now > ctx.avg_charge_price
            and ctx.soc > ctx.soc_min + 5
            and ctx.ai_mode in ("automatic", "winter")
            and not engine._is_real_export(ctx)
        ):
            discharge_w = engine._delta_discharge(ctx)
            return DecisionResult(
                action="discharge",
                ac_mode="output",
                charge_w=0.0,
                discharge_w=discharge_w,
                reason="price_based_discharge",
            )
        return None


class PlanningRule(BaseRule):
    def evaluate(self, engine, ctx):
        if engine._byd_blocks_charge(ctx):
            return None
        return engine._evaluate_adaptive_planning(ctx)


class NightChargeRule(BaseRule):
    """Lädt Zendure im GO-Günstigfenster (00:00–05:00 UTC) wenn PV-Nachtladen aktiv und Ladebedarf besteht.

    Feuert unabhängig von Peakstunden – ergänzt PlanningRule für GO-Tarif-Szenarien
    ohne erkannte teure Stunden.
    """

    def evaluate(self, engine, ctx):
        # automatic/winter: immer erlaubt
        # manual + constant_discharge: GO-Fenster überschreibt die Abend-Automation
        # manual + andere Aktionen (manuell angeordnetes Entladen etc.): nicht eingreifen
        if ctx.ai_mode not in ("automatic", "winter", "manual"):
            return None
        if ctx.ai_mode == "manual" and getattr(ctx, "manual_action", "") not in (
            "", "standby", "constant_discharge",
        ):
            return None
        # Nur wenn PV-Nachtladen aktiviert (pv_forecast_kwh >= 0 = Feature on)
        if ctx.pv_forecast_kwh < 0:
            return None
        # Nur im Nachtfenster (00:00–05:00 UTC)
        if not (0 <= ctx.now.hour < 5):
            return None
        # Zendure bereits am Ziel?
        if ctx.soc >= ctx.soc_max:
            return None
        # BYD entlädt → kein Laden (Standard-Guard)
        if engine._byd_blocks_charge(ctx):
            return None

        # Zendure-Ladebedarf berechnen (identische Formel wie coordinator)
        z_usable = max(0.0, (ctx.soc - ctx.soc_min) / 100.0 * ctx.battery_capacity_kwh)
        z_capacity = ctx.battery_capacity_kwh * (ctx.soc_max - ctx.soc_min) / 100.0
        byd_usable = (
            max(0.0, ctx.additional_battery_soc / 100.0 * ctx.additional_battery_capacity_kwh)
            if ctx.additional_battery_soc >= 0 else 0.0
        )
        # Haushaltslast abziehen: PV-Anteil, der direkt an den Verbraucher geht (nicht in Batterie)
        _pv_for_battery = max(0.0, ctx.pv_forecast_kwh - ctx.pv_self_consumption_kwh)
        target_total = min(
            z_capacity + ctx.additional_battery_capacity_kwh,
            ctx.bridge_kwh + ctx.nighttime_kwh
            + max(0.0, ctx.daily_consumption_kwh - _pv_for_battery),
        )
        charge_needed = max(0.0, target_total - (z_usable + byd_usable))
        z_charge = min(max(0.0, z_capacity - z_usable), charge_needed)

        if z_charge < 0.2:  # Vernachlässigbarer Zendure-Bedarf
            return None

        if ctx.max_charge_w <= 0:
            return None

        return DecisionResult(
            action="charge",
            ac_mode="input",
            charge_w=ctx.max_charge_w,
            discharge_w=0.0,
            reason="night_charge_go_window",
        )


class ValleyBoostRule(BaseRule):
    def evaluate(self, engine, ctx):
        if engine._byd_blocks_charge(ctx):
            return None
        # Nur im Wintermodus
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

        base_price = engine._compute_base_price(prices)
        valley_threshold = base_price * ctx.valley_factor

        # Kein Valley -> kein Boost
        if ctx.price_now > valley_threshold:
            return None

        # Nur wenn tatsächlich PV vorhanden ist
        if ctx.pv_w < 100:
            return None

        if ctx.max_charge_w <= 0:
            return None

        return DecisionResult(
            action="charge",
            ac_mode="input",
            charge_w=ctx.max_charge_w,
            discharge_w=0.0,
            reason="valley_boost_charge",
        )


class PvRule(BaseRule):
    def evaluate(self, engine, ctx):
        if ctx.ai_mode == "manual":
            return None
        if engine._byd_blocks_charge(ctx):
            return None
        # Wenn wir gerade aktiv planen zu laden,
        # soll PV diese Entscheidung nicht überschreiben
        planning = engine._evaluate_adaptive_planning(ctx)
        if planning is not None:
            return None

        if ctx.soc < ctx.soc_max:
            charge_w = engine._delta_charge(ctx)

            if charge_w > 0:
                return DecisionResult(
                    action="charge",
                    ac_mode="input",
                    charge_w=charge_w,
                    discharge_w=0.0,
                    reason="pv_surplus_charge",
                )

        return None


class SummerRule(BaseRule):
    def evaluate(self, engine, ctx):
        if engine._byd_blocks_discharge(ctx) or engine._wallbox_blocks_discharge(ctx):
            return None
        if (
            ctx.ai_mode == "summer"
            or (ctx.ai_mode == "automatic" and ctx.season == "summer")
        ):
            if ctx.soc > ctx.soc_min and not engine._is_real_export(ctx):
                discharge_w = engine._delta_discharge(ctx)
                if discharge_w > 0:
                    return DecisionResult(
                        action="discharge",
                        ac_mode="output",
                        charge_w=0.0,
                        discharge_w=discharge_w,
                        reason="summer_cover_deficit",
                    )
        return None


class ManualRule(BaseRule):
    def evaluate(self, engine, ctx):
        if ctx.ai_mode != "manual":
            return None

        if ctx.manual_action == "charge":
            return DecisionResult(
                action="charge",
                ac_mode="input",
                charge_w=ctx.max_charge_w,
                discharge_w=0.0,
                reason="manual_charge",
            )

        if ctx.manual_action == MANUAL_CONST_DISCHARGE:
            return DecisionResult(
                action="discharge",
                ac_mode="output",
                charge_w=0.0,
                discharge_w=float(ctx.max_discharge_w),
                reason="manual_constant_discharge",
            )

        if ctx.manual_action == "discharge":
            discharge_w = engine._delta_discharge(ctx)
            return DecisionResult(
                action="discharge",
                ac_mode="output",
                charge_w=0.0,
                discharge_w=discharge_w,
                reason="manual_discharge",
            )

        return DecisionResult(
            action="idle",
            ac_mode="input",
            charge_w=0.0,
            discharge_w=0.0,
            reason="manual_idle",
        )


# ==================================================
# ENGINE
# ==================================================

class DecisionEngine:
    def __init__(self):
        self._rules = [
            EmergencyRule(),
            PeakRule(),
            ArbitrageRule(),
            PlanningRule(),
            NightChargeRule(),   # Prio 5: GO-Fenster Nachtladung (Fix 4)
            ValleyBoostRule(),
            PvRule(),
            SummerRule(),
            ManualRule(),
        ]

    # -------------------------------------------------
    # Helper methods
    # -------------------------------------------------

    _EXPORT_THRESHOLD_W: float = 120.0

    def _is_real_export(self, ctx: DecisionContext) -> bool:
        """True wenn Netto-Export > 120W (Zähler exportiert signifikant ins Netz)."""
        net = ctx.grid_import_w - ctx.grid_export_w
        return net < -self._EXPORT_THRESHOLD_W

    def _byd_blocks_discharge(self, ctx: DecisionContext) -> bool:
        """BYD lädt → Zendure darf nicht entladen (Energie-Loop verhindern)."""
        return float(ctx.additional_battery_charge_w or 0.0) > 0.0

    def _byd_blocks_charge(self, ctx: DecisionContext) -> bool:
        """BYD entlädt → Zendure darf nicht laden (Energie-Loop verhindern)."""
        return float(ctx.additional_battery_discharge_w or 0.0) > 0.0

    def _wallbox_blocks_discharge(self, ctx: DecisionContext) -> bool:
        """Wallbox lädt → Zendure darf nicht entladen."""
        return float(ctx.wallbox_active_w or 0.0) > 0.0

    def _compute_base_price(self, prices: List[float]) -> float:
        avg_price = sum(prices) / len(prices)
        median_price = statistics.median(prices)
        return min(avg_price, median_price)

    def _compute_peak_threshold(self, prices: List[float], peak_factor: float) -> float:
        base_price = self._compute_base_price(prices)
        return max(
            base_price * peak_factor,
            base_price + 0.03,
        )

    def _compute_valley_threshold(self, prices: List[float], valley_factor: float) -> float:
        base_price = self._compute_base_price(prices)
        return base_price * valley_factor

    # -------------------------------------------------
    # Delta delegation
    # -------------------------------------------------

    def _to_power_ctx(self, ctx: DecisionContext) -> PowerContext:
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
            profile=ctx.profile,
        )

    def _delta_discharge(self, ctx: DecisionContext) -> float:
        return PowerController.delta_discharge(self._to_power_ctx(ctx))

    def _delta_charge(self, ctx: DecisionContext) -> float:
        return PowerController.delta_charge(self._to_power_ctx(ctx))

    # -------------------------------------------------
    # Peak detection
    # -------------------------------------------------

    def _detect_adaptive_peak(self, ctx: DecisionContext) -> bool:
        if not ctx.price_points or ctx.price_now is None:
            return False

        prices = [p.price for p in ctx.price_points]
        if not prices:
            return False

        threshold = self._compute_peak_threshold(prices, ctx.peak_factor)

        # Normal peak detection
        if ctx.price_now >= threshold:
            return True

        # ------------------------------------------------
        # Early spike detection
        # ------------------------------------------------
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

    # -------------------------------------------------
    # PV-Forecast-basierte Ziel-SoC-Berechnung (v3.2)
    # -------------------------------------------------

    def _calc_pv_aware_zendure_target_soc(self, ctx: DecisionContext) -> Optional[float]:
        """Berechnet den PV-bewussten Zendure-Ziel-SoC.

        Gibt None zurück wenn:
        - Feature deaktiviert (pv_forecast_kwh < 0)
        - Sensor nicht verfügbar

        Formeln:
            z_usable    = max(0; (soc - soc_min) / 100 × battery_capacity_kwh)
            byd_usable  = max(0; additional_battery_soc / 100 × additional_battery_capacity_kwh)
            z_capacity  = battery_capacity_kwh × (soc_max - soc_min) / 100
            total_max   = z_capacity + additional_battery_capacity_kwh
            target_total = min(total_max; bridge_kwh + max(0; daily_consumption_kwh - pv_forecast_kwh))
            charge_needed = max(0; target_total - (z_usable + byd_usable))
            z_charge    = min(z_capacity - z_usable; charge_needed)
            z_target_soc = min(soc_max; soc + z_charge / battery_capacity_kwh × 100)
        """
        if ctx.pv_forecast_kwh < 0:
            return None  # Feature deaktiviert oder Sensor unavailable

        z_usable = max(0.0, (ctx.soc - ctx.soc_min) / 100.0 * ctx.battery_capacity_kwh)

        byd_usable = 0.0
        if ctx.additional_battery_soc >= 0 and ctx.additional_battery_capacity_kwh > 0:
            byd_usable = max(0.0, ctx.additional_battery_soc / 100.0 * ctx.additional_battery_capacity_kwh)

        total_avail = z_usable + byd_usable

        z_capacity = ctx.battery_capacity_kwh * (ctx.soc_max - ctx.soc_min) / 100.0
        total_max = z_capacity + ctx.additional_battery_capacity_kwh

        _pv_for_battery = max(0.0, ctx.pv_forecast_kwh - ctx.pv_self_consumption_kwh)
        target_total = min(
            total_max,
            ctx.bridge_kwh + ctx.nighttime_kwh + max(0.0, ctx.daily_consumption_kwh - _pv_for_battery),
        )

        charge_needed = max(0.0, target_total - total_avail)
        z_charge = min(max(0.0, z_capacity - z_usable), charge_needed)

        z_target_soc = min(
            ctx.soc_max,
            ctx.soc + z_charge / ctx.battery_capacity_kwh * 100.0,
        )
        return round(z_target_soc, 1)

    # -------------------------------------------------
    # Adaptive planning
    # -------------------------------------------------

    def _evaluate_adaptive_planning(self, ctx: DecisionContext) -> Optional[DecisionResult]:
        if (
            ctx.ai_mode not in ("automatic", "winter")
            or not ctx.price_points
            or ctx.price_now is None
            or ctx.battery_capacity_kwh <= 0
            or ctx.max_charge_w <= 0
        ):
            return None

        # PV-aware effective_soc_max: ersetzt ctx.soc_max wenn Feature aktiv
        effective_soc_max = ctx.soc_max
        pv_target = self._calc_pv_aware_zendure_target_soc(ctx)
        if pv_target is not None:
            effective_soc_max = pv_target

        # Guard: Bereits am Ziel?
        if ctx.soc >= effective_soc_max:
            return None

        prices = [p.price for p in ctx.price_points]
        if not prices:
            return None

        # ------------------------------------------------
        # Optional absolute cheap price filter
        # ------------------------------------------------
        if ctx.very_cheap_price is not None and ctx.price_now > ctx.very_cheap_price:
            return None

        # ------------------------------------------------
        # Valley factor check
        # ------------------------------------------------
        valley_threshold = self._compute_valley_threshold(prices, ctx.valley_factor)

        if ctx.price_now > valley_threshold:
            return None

        # ------------------------------------------------
        # Peak detection
        # ------------------------------------------------
        peak_threshold = self._compute_peak_threshold(prices, ctx.peak_factor)

        peak_slots = [p for p in ctx.price_points if p.price >= peak_threshold]
        future_peaks = [p for p in peak_slots if p.start > ctx.now]

        if not future_peaks:
            return None

        # ------------------------------------------------
        # Expected peak price
        # ------------------------------------------------
        expected_peak_price = max(p.price for p in future_peaks)

        # ------------------------------------------------
        # Profitability check
        # ------------------------------------------------
        min_profit_factor = 1 + (ctx.profit_margin_pct / 100)
        required_peak_price = ctx.price_now * min_profit_factor

        if expected_peak_price < required_peak_price:
            return None

        next_peak = min(p.start for p in future_peaks)

        # ------------------------------------------------
        # Detect second peak (multi-peak protection)
        # ------------------------------------------------
        future_peaks_sorted = sorted(future_peaks, key=lambda p: p.start)
        second_peak = future_peaks_sorted[1].start if len(future_peaks_sorted) >= 2 else None

        soc_gap_pct = max(0.0, effective_soc_max - ctx.soc)
        required_kwh = ctx.battery_capacity_kwh * (soc_gap_pct / 100.0)

        # ------------------------------------------------
        # Multi-peak protection
        # ------------------------------------------------
        if second_peak is not None:
            hours_between_peaks = (second_peak - next_peak).total_seconds() / 3600.0

            # Wenn Peaks sehr dicht sind -> mehr Energie reservieren
            if hours_between_peaks < 6:
                required_kwh *= 1.4

        charge_power_kw = ctx.max_charge_w / 1000.0
        if charge_power_kw <= 0:
            return None

        hours_needed = required_kwh / charge_power_kw
        hours_needed = max(hours_needed * 1.10, 0.25)

        latest_start = next_peak - timedelta(hours=hours_needed)

        # ------------------------------------------------
        # Smart cheapest charging window
        # ------------------------------------------------
        future_prices = [
            p for p in ctx.price_points
            if ctx.now <= p.start <= next_peak
        ]

        if future_prices:
            energy_per_slot = charge_power_kw * 0.25  # 15 Minuten

            if energy_per_slot > 0:
                required_slots = max(1, math.ceil(required_kwh / energy_per_slot))

                cheapest_slots = sorted(
                    future_prices,
                    key=lambda p: p.price,
                )[:required_slots]

                if not cheapest_slots:
                    return None

                cheapest_prices = [p.price for p in cheapest_slots]

                if ctx.price_now > max(cheapest_prices):
                    return None

        # ------------------------------------------------
        # Latest start trigger
        # ------------------------------------------------
        if ctx.now >= latest_start:
            return DecisionResult(
                action="charge",
                ac_mode="input",
                charge_w=ctx.max_charge_w,
                discharge_w=0.0,
                reason="planning_latest_start",
                target_soc=effective_soc_max,
            )

        return None

    # -------------------------------------------------
    # MAIN EVALUATION
    # -------------------------------------------------

    def evaluate(self, ctx: DecisionContext) -> DecisionResult:
        for rule in self._rules:
            result = rule.evaluate(self, ctx)
            if result:
                return result

        return DecisionResult(
            action="idle",
            ac_mode="input",
            charge_w=0.0,
            discharge_w=0.0,
            reason="idle",
        )
