from __future__ import annotations

from typing import Any

from .decision_engine import DecisionResult
from .regulation_models import StrategyIntent


def decision_to_strategy_intent(decision: DecisionResult) -> StrategyIntent:
    """Convert the existing Decision Engine result into a StrategyIntent.

    The Decision Engine remains the strategic layer. This adapter translates
    the old action/mode/reason result into a semantic intent for the new
    technical regulation chain.

    Important:
    input/output alone is not enough. PV charging, planned grid charging,
    emergency charging and manual charging are all technically INPUT, but
    require different handling in the ModeArbiter and PowerController.
    """

    reason = str(decision.reason or "idle")
    action = str(decision.action or "idle")
    ac_mode = str(decision.ac_mode or "output")

    charge_w = max(0.0, float(decision.charge_w or 0.0))
    discharge_w = max(0.0, float(decision.discharge_w or 0.0))

    metadata: dict[str, Any] = {
        "source_action": action,
        "source_ac_mode": ac_mode,
        "source_charge_w": charge_w,
        "source_discharge_w": discharge_w,
        "target_soc": decision.target_soc,
    }

    # ---------------------------------------------------------------------
    # Emergency / hard priority
    # ---------------------------------------------------------------------
    if reason in {
        "emergency_latched_charge",
        "cell_voltage_emergency_charge",
    } or action == "emergency":
        return StrategyIntent(
            intent="emergency_charge",
            requested_mode="input",
            requested_power_w=charge_w,
            reason=reason,
            priority=100,
            allow_mode_switch=True,
            force=True,
            metadata=metadata,
        )

    # ---------------------------------------------------------------------
    # Manual
    # ---------------------------------------------------------------------
    if reason == "manual_charge":
        return StrategyIntent(
            intent="manual_charge",
            requested_mode="input",
            requested_power_w=charge_w,
            reason=reason,
            priority=90,
            allow_mode_switch=True,
            force=True,
            metadata=metadata,
        )

    if reason == "manual_constant_discharge":
        return StrategyIntent(
            intent="manual_constant_discharge",
            requested_mode="output",
            requested_power_w=discharge_w,
            reason=reason,
            priority=90,
            allow_mode_switch=True,
            force=True,
            metadata=metadata,
        )

    if reason == "manual_discharge":
        return StrategyIntent(
            intent="manual_discharge",
            requested_mode="output",
            requested_power_w=discharge_w,
            reason=reason,
            priority=90,
            allow_mode_switch=True,
            force=True,
            metadata=metadata,
        )

    if reason == "manual_idle":
        return StrategyIntent(
            intent="idle",
            requested_mode="idle",
            requested_power_w=0.0,
            reason=reason,
            priority=80,
            allow_mode_switch=True,
            force=True,
            metadata=metadata,
        )

    # ---------------------------------------------------------------------
    # Off-Grid / Inselsteckdose
    # ---------------------------------------------------------------------
    if reason == "offgrid_load_support":
        return StrategyIntent(
            intent="cover_deficit",
            requested_mode="output",
            requested_power_w=discharge_w,
            reason=reason,
            priority=70,
            allow_mode_switch=True,
            force=False,
            metadata=metadata,
        )

    # ---------------------------------------------------------------------
    # PV / passthrough
    # ---------------------------------------------------------------------
    if reason == "pv_surplus_charge":
        return StrategyIntent(
            intent="pv_charge",
            requested_mode="input",
            requested_power_w=None,
            reason=reason,
            priority=50,
            allow_mode_switch=True,
            force=False,
            metadata=metadata,
        )

    if reason == "pv_house_load_passthrough" or action == "passthrough":
        return StrategyIntent(
            intent="passthrough",
            requested_mode="output",
            requested_power_w=discharge_w,
            reason=reason,
            priority=55,
            allow_mode_switch=True,
            force=False,
            metadata=metadata,
        )

    # ---------------------------------------------------------------------
    # Planned / price-based charging
    # ---------------------------------------------------------------------
    if reason in {
        "very_cheap_force_charge",
        "valley_boost_charge",
        "valley_boost_charge_mixed_forecast",
        "planning_latest_start",
        "planning_forecast_poor",
        "planning_forecast_mixed",
        "planning_forecast_reality_override",
        "valley_opportunity_charge",
        "valley_opportunity_charge_mixed_forecast",
        "learned_charge_window_active",
        "learned_charge_window_latest_start_reached",
        "learned_charge_window_deadline_too_close_start_now",
    }:
        return StrategyIntent(
            intent="planned_charge",
            requested_mode="input",
            requested_power_w=charge_w,
            reason=reason,
            priority=60,
            allow_mode_switch=True,
            force=False,
            metadata=metadata,
        )

    if reason == "learned_charge_window_wait":
        return StrategyIntent(
            intent="idle",
            requested_mode="idle",
            requested_power_w=0.0,
            reason=reason,
            priority=40,
            allow_mode_switch=False,
            force=False,
            metadata=metadata,
        )

    if reason == "summer_cover_deficit":
        # V4.2.3:
        # summer_cover_deficit is a dynamic house-load covering intent.
        # The old DecisionEngine discharge_w is only a legacy delta result and must
        # not cap the new V4.2 PowerController. Let the regulation controller derive
        # the concrete OUTPUT power from grid history/current import.
        return StrategyIntent(
            intent="cover_deficit",
            requested_mode="output",
            requested_power_w=None,
            reason=reason,
            priority=45,
            allow_mode_switch=True,
            force=False,
            metadata={
                **metadata,
                "legacy_discharge_request_w": discharge_w,
            },
        )

    if reason in {
        "adaptive_peak_discharge",
        "very_expensive_force_discharge",
    }:
        return StrategyIntent(
            intent="peak_discharge",
            requested_mode="output",
            requested_power_w=discharge_w,
            reason=reason,
            priority=65,
            allow_mode_switch=True,
            force=False,
            metadata=metadata,
        )

    if reason == "price_based_discharge":
        return StrategyIntent(
            intent="arbitrage_discharge",
            requested_mode="output",
            requested_power_w=discharge_w,
            reason=reason,
            priority=55,
            allow_mode_switch=True,
            force=False,
            metadata=metadata,
        )

    # ---------------------------------------------------------------------
    # Blocked / idle / protection states
    # ---------------------------------------------------------------------
    if action == "idle" or reason in {
        "idle",
        "sensor_invalid",
        "additional_battery_charging_block",
        "additional_battery_discharging_block",
        "pv_charge_blocked_by_discharge_protection",
        "soc_limit_upper",
        "soc_limit_lower",
        "soc_min_resume_block",
        "cell_voltage_cutoff_block",
    }:
        return StrategyIntent(
            intent="idle",
            requested_mode="idle",
            requested_power_w=0.0,
            reason=reason,
            priority=30,
            allow_mode_switch=True,
            force=False,
            metadata=metadata,
        )

    # ---------------------------------------------------------------------
    # Conservative fallback
    # ---------------------------------------------------------------------
    if ac_mode == "input" and charge_w > 0.0:
        return StrategyIntent(
            intent="planned_charge",
            requested_mode="input",
            requested_power_w=charge_w,
            reason=reason,
            priority=40,
            allow_mode_switch=True,
            force=False,
            metadata=metadata,
        )

    if ac_mode == "output" and discharge_w > 0.0:
        return StrategyIntent(
            intent="cover_deficit",
            requested_mode="output",
            requested_power_w=discharge_w,
            reason=reason,
            priority=40,
            allow_mode_switch=True,
            force=False,
            metadata=metadata,
        )

    return StrategyIntent(
        intent="idle",
        requested_mode="idle",
        requested_power_w=0.0,
        reason=reason,
        priority=0,
        allow_mode_switch=True,
        force=False,
        metadata=metadata,
    )