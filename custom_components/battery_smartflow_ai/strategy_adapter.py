from __future__ import annotations

from typing import Any

from .decision_engine import DecisionResult
from .regulation_models import StrategyIntent
from .strategy_state import StrategicState, StrategyDecision, VisibleState


PRICE_CHARGE_REASONS = {
    "very_cheap_force_charge",
    "valley_boost_charge",
    "valley_boost_charge_mixed_forecast",
    "valley_opportunity_charge",
    "valley_opportunity_charge_mixed_forecast",
}

PLANNED_CHARGE_REASONS = {
    "planning_latest_start",
    "planning_forecast_poor",
    "planning_forecast_mixed",
    "planning_forecast_reality_override",
}

LEARNED_CHARGE_REASONS = {
    "learned_charge_window_active",
    "learned_charge_window_latest_start_reached",
    "learned_charge_window_deadline_too_close_start_now",
}

LEARNED_DEADLINE_REASONS = {
    "learned_charge_window_latest_start_reached",
    "learned_charge_window_deadline_too_close_start_now",
}

CHARGE_COMMIT_ACTIVE_REASON = "charge_commit_active"

IDLE_SAFE_REASONS = {
    "sensor_invalid",
    "soc_invalid",
    "grid_sensor_invalid",
    "soc_limits_invalid",
    "power_limits_invalid",
    "additional_battery_charging_block",
    "additional_battery_discharging_block",
    "pv_charge_blocked_by_discharge_protection",
    "soc_limit_upper",
    "soc_limit_lower",
    "soc_min_resume_block",
    "cell_voltage_cutoff_block",
    "cell_voltage_sensor_invalid",
}

CRITICAL_DATA_REASONS = {
    "sensor_invalid",
    "soc_invalid",
    "grid_sensor_invalid",
    "soc_limits_invalid",
    "power_limits_invalid",
    "cell_voltage_sensor_invalid",
}

PROTECTION_REASONS = {
    "cell_voltage_cutoff_block",
    "soc_limit_lower",
}


def _base_metadata(
    decision: DecisionResult,
    *,
    reason: str,
    action: str,
    ac_mode: str,
    charge_w: float,
    discharge_w: float,
) -> dict[str, Any]:
    return {
        "source_action": action,
        "source_ac_mode": ac_mode,
        "source_charge_w": charge_w,
        "source_discharge_w": discharge_w,
        "target_soc": decision.target_soc,
    }


def decision_to_strategy_decision(decision: DecisionResult) -> StrategyDecision:
    """Convert the Decision Engine result into the strategic model."""
    reason = str(decision.reason or "idle")
    action = str(decision.action or "idle")
    ac_mode = str(decision.ac_mode or "output")

    charge_w = max(0.0, float(decision.charge_w or 0.0))
    discharge_w = max(0.0, float(decision.discharge_w or 0.0))

    metadata = _base_metadata(
        decision,
        reason=reason,
        action=action,
        ac_mode=ac_mode,
        charge_w=charge_w,
        discharge_w=discharge_w,
    )

    # --------------------------------------------------
    # Protection / emergency
    # --------------------------------------------------
    if reason in PROTECTION_REASONS:
        return StrategyDecision(
            state=StrategicState.PROTECTION,
            visible_state=VisibleState.PROTECTION_ACTIVE,
            requested_mode="idle",
            requested_power_w=0.0,
            strategic_reason=reason,
            source_reason=reason,
            source_action=action,
            source_ac_mode=ac_mode,
            priority=1000,
            target_soc=decision.target_soc,
            allow_mode_switch=True,
            force=False,
            metadata=metadata,
        )

    if reason in {
        "emergency_latched_charge",
        "cell_voltage_emergency_charge",
    } or action == "emergency":
        return StrategyDecision(
            state=StrategicState.EMERGENCY_CHARGE,
            visible_state=VisibleState.EMERGENCY_CHARGE,
            requested_mode="input",
            requested_power_w=charge_w,
            strategic_reason=reason,
            source_reason=reason,
            source_action=action,
            source_ac_mode=ac_mode,
            priority=1000,
            target_soc=decision.target_soc,
            allow_mode_switch=True,
            force=True,
            metadata=metadata,
        )

    # --------------------------------------------------
    # Manual
    # --------------------------------------------------
    if reason == "manual_charge":
        return StrategyDecision(
            state=StrategicState.MANUAL_CHARGE,
            visible_state=VisibleState.MANUAL,
            requested_mode="input",
            requested_power_w=charge_w,
            strategic_reason=reason,
            source_reason=reason,
            source_action=action,
            source_ac_mode=ac_mode,
            priority=900,
            target_soc=decision.target_soc,
            allow_mode_switch=True,
            force=True,
            metadata=metadata,
        )

    if reason == "manual_constant_discharge":
        return StrategyDecision(
            state=StrategicState.MANUAL_DISCHARGE,
            visible_state=VisibleState.MANUAL,
            requested_mode="output",
            requested_power_w=discharge_w,
            strategic_reason=reason,
            source_reason=reason,
            source_action=action,
            source_ac_mode=ac_mode,
            priority=900,
            target_soc=decision.target_soc,
            allow_mode_switch=True,
            force=True,
            metadata=metadata,
        )

    if reason == "manual_discharge":
        return StrategyDecision(
            state=StrategicState.MANUAL_DISCHARGE,
            visible_state=VisibleState.MANUAL,
            requested_mode="output",
            requested_power_w=discharge_w,
            strategic_reason=reason,
            source_reason=reason,
            source_action=action,
            source_ac_mode=ac_mode,
            priority=900,
            target_soc=decision.target_soc,
            allow_mode_switch=True,
            force=True,
            metadata=metadata,
        )

    if reason == "manual_idle":
        return StrategyDecision(
            state=StrategicState.MANUAL_IDLE,
            visible_state=VisibleState.MANUAL,
            requested_mode="idle",
            requested_power_w=0.0,
            strategic_reason=reason,
            source_reason=reason,
            source_action=action,
            source_ac_mode=ac_mode,
            priority=900,
            target_soc=decision.target_soc,
            allow_mode_switch=True,
            force=True,
            metadata=metadata,
        )

    # --------------------------------------------------
    # Hard blockers / safe idle
    # --------------------------------------------------
    if reason in IDLE_SAFE_REASONS:
        return StrategyDecision(
            state=StrategicState.IDLE_SAFE,
            visible_state=(
                VisibleState.SAFE_IDLE
                if reason in CRITICAL_DATA_REASONS
                else VisibleState.WAITING_BLOCKED
            ),
            requested_mode="idle",
            requested_power_w=0.0,
            strategic_reason=reason,
            source_reason=reason,
            source_action=action,
            source_ac_mode=ac_mode,
            priority=800,
            target_soc=decision.target_soc,
            allow_mode_switch=True,
            force=False,
            metadata=metadata,
        )
        
    # --------------------------------------------------
    # Active AC charge commit
    # --------------------------------------------------
    if reason == CHARGE_COMMIT_ACTIVE_REASON:
        return StrategyDecision(
            state=StrategicState.AC_CHARGE_COMMITTED,
            visible_state=VisibleState.GRID_CHARGE,
            requested_mode="input",
            requested_power_w=charge_w,
            strategic_reason=reason,
            source_reason=reason,
            source_action=action,
            source_ac_mode=ac_mode,
            priority=700,
            target_soc=decision.target_soc,
            allow_mode_switch=True,
            force=False,
            metadata={
                **metadata,
                "charge_commit_active": True,
            },
        )

    # --------------------------------------------------
    # AC charging
    # --------------------------------------------------
    if reason in LEARNED_CHARGE_REASONS:
        return StrategyDecision(
            state=StrategicState.AC_CHARGE_LEARNED,
            visible_state=VisibleState.GRID_CHARGE,
            requested_mode="input",
            requested_power_w=charge_w,
            strategic_reason=reason,
            source_reason=reason,
            source_action=action,
            source_ac_mode=ac_mode,
            priority=650 if reason in LEARNED_DEADLINE_REASONS else 640,
            target_soc=decision.target_soc,
            allow_mode_switch=True,
            force=False,
            metadata=metadata,
        )

    if reason in PLANNED_CHARGE_REASONS:
        return StrategyDecision(
            state=StrategicState.AC_CHARGE_PLANNED,
            visible_state=VisibleState.GRID_CHARGE,
            requested_mode="input",
            requested_power_w=charge_w,
            strategic_reason=reason,
            source_reason=reason,
            source_action=action,
            source_ac_mode=ac_mode,
            priority=650 if reason == "planning_latest_start" else 630,
            target_soc=decision.target_soc,
            allow_mode_switch=True,
            force=False,
            metadata=metadata,
        )

    if reason in PRICE_CHARGE_REASONS:
        return StrategyDecision(
            state=StrategicState.AC_CHARGE_PRICE,
            visible_state=VisibleState.GRID_CHARGE,
            requested_mode="input",
            requested_power_w=charge_w,
            strategic_reason=reason,
            source_reason=reason,
            source_action=action,
            source_ac_mode=ac_mode,
            priority=620,
            target_soc=decision.target_soc,
            allow_mode_switch=True,
            force=False,
            metadata=metadata,
        )

    if reason == "summer_peak_reserve_charge":
        return StrategyDecision(
            state=StrategicState.AC_CHARGE_RESERVE,
            visible_state=VisibleState.RESERVE_CHARGE,
            requested_mode="input",
            requested_power_w=charge_w,
            strategic_reason="reserve_charge",
            source_reason=reason,
            source_action=action,
            source_ac_mode=ac_mode,
            priority=610,
            target_soc=decision.target_soc,
            allow_mode_switch=True,
            force=False,
            metadata=metadata,
        )

    # --------------------------------------------------
    # PV charging / passthrough
    # --------------------------------------------------
    if reason == "pv_surplus_charge":
        return StrategyDecision(
            state=StrategicState.PV_SURPLUS_CHARGE,
            visible_state=VisibleState.PV_CHARGE,
            requested_mode="input",
            requested_power_w=None,
            strategic_reason="pv_export_confirmed",
            source_reason=reason,
            source_action=action,
            source_ac_mode=ac_mode,
            priority=500,
            target_soc=decision.target_soc,
            allow_mode_switch=True,
            force=False,
            metadata=metadata,
        )

    if reason == "pv_house_load_passthrough" or action == "passthrough":
        return StrategyDecision(
            state=StrategicState.PASSTHROUGH,
            visible_state=VisibleState.LOAD_COVERAGE,
            requested_mode="output",
            requested_power_w=discharge_w,
            strategic_reason=reason,
            source_reason=reason,
            source_action=action,
            source_ac_mode=ac_mode,
            priority=400,
            target_soc=decision.target_soc,
            allow_mode_switch=True,
            force=False,
            metadata=metadata,
        )

    # --------------------------------------------------
    # Load coverage / discharge
    # --------------------------------------------------
    if reason == "offgrid_load_support":
        return StrategyDecision(
            state=StrategicState.OFFGRID_SUPPORT,
            visible_state=VisibleState.LOAD_COVERAGE,
            requested_mode="output",
            requested_power_w=discharge_w,
            strategic_reason=reason,
            source_reason=reason,
            source_action=action,
            source_ac_mode=ac_mode,
            priority=400,
            target_soc=decision.target_soc,
            allow_mode_switch=True,
            force=False,
            metadata=metadata,
        )

    if reason == "summer_cover_deficit":
        return StrategyDecision(
            state=StrategicState.LOAD_COVERAGE,
            visible_state=VisibleState.LOAD_COVERAGE,
            requested_mode="output",
            requested_power_w=None,
            strategic_reason="load_coverage",
            source_reason=reason,
            source_action=action,
            source_ac_mode=ac_mode,
            priority=450,
            target_soc=decision.target_soc,
            allow_mode_switch=True,
            force=False,
            metadata={
                **metadata,
                "legacy_discharge_request_w": discharge_w,
            },
        )

    if reason in {"adaptive_peak_discharge", "very_expensive_force_discharge"}:
        return StrategyDecision(
            state=StrategicState.ECONOMIC_DISCHARGE,
            visible_state=VisibleState.ECONOMIC_DISCHARGE,
            requested_mode="output",
            requested_power_w=discharge_w,
            strategic_reason=reason,
            source_reason=reason,
            source_action=action,
            source_ac_mode=ac_mode,
            priority=430,
            target_soc=decision.target_soc,
            allow_mode_switch=True,
            force=False,
            metadata=metadata,
        )

    if reason == "price_based_discharge":
        return StrategyDecision(
            state=StrategicState.ECONOMIC_DISCHARGE,
            visible_state=VisibleState.ECONOMIC_DISCHARGE,
            requested_mode="output",
            requested_power_w=discharge_w,
            strategic_reason=reason,
            source_reason=reason,
            source_action=action,
            source_ac_mode=ac_mode,
            priority=420,
            target_soc=decision.target_soc,
            allow_mode_switch=True,
            force=False,
            metadata=metadata,
        )

    # --------------------------------------------------
    # Wait / idle
    # --------------------------------------------------
    if reason == "learned_charge_window_wait":
        return StrategyDecision(
            state=StrategicState.HOLD,
            visible_state=VisibleState.WAITING_FOR_CHARGE_WINDOW,
            requested_mode="idle",
            requested_power_w=0.0,
            strategic_reason=reason,
            source_reason=reason,
            source_action=action,
            source_ac_mode=ac_mode,
            priority=300,
            target_soc=decision.target_soc,
            allow_mode_switch=False,
            force=False,
            metadata=metadata,
        )

    if reason == "learned_charge_window_no_charge_needed":
        return StrategyDecision(
            state=StrategicState.IDLE_READY,
            visible_state=VisibleState.READY,
            requested_mode="idle",
            requested_power_w=0.0,
            strategic_reason=reason,
            source_reason=reason,
            source_action=action,
            source_ac_mode=ac_mode,
            priority=200,
            target_soc=decision.target_soc,
            allow_mode_switch=True,
            force=False,
            metadata=metadata,
        )

    if action == "idle" or reason in {"idle", "state_idle", "standby"}:
        return StrategyDecision(
            state=StrategicState.IDLE_READY,
            visible_state=VisibleState.READY,
            requested_mode="idle",
            requested_power_w=0.0,
            strategic_reason="no_strategy_needed" if reason == "idle" else reason,
            source_reason=reason,
            source_action=action,
            source_ac_mode=ac_mode,
            priority=200,
            target_soc=decision.target_soc,
            allow_mode_switch=True,
            force=False,
            metadata=metadata,
        )

    # --------------------------------------------------
    # Conservative fallback
    # --------------------------------------------------
    if ac_mode == "input" and charge_w > 0.0:
        return StrategyDecision(
            state=StrategicState.AC_CHARGE_PLANNED,
            visible_state=VisibleState.GRID_CHARGE,
            requested_mode="input",
            requested_power_w=charge_w,
            strategic_reason=reason,
            source_reason=reason,
            source_action=action,
            source_ac_mode=ac_mode,
            priority=400,
            target_soc=decision.target_soc,
            allow_mode_switch=True,
            force=False,
            metadata=metadata,
        )

    if ac_mode == "output" and discharge_w > 0.0:
        return StrategyDecision(
            state=StrategicState.LOAD_COVERAGE,
            visible_state=VisibleState.LOAD_COVERAGE,
            requested_mode="output",
            requested_power_w=discharge_w,
            strategic_reason=reason,
            source_reason=reason,
            source_action=action,
            source_ac_mode=ac_mode,
            priority=400,
            target_soc=decision.target_soc,
            allow_mode_switch=True,
            force=False,
            metadata=metadata,
        )

    return StrategyDecision(
        state=StrategicState.IDLE_READY,
        visible_state=VisibleState.READY,
        requested_mode="idle",
        requested_power_w=0.0,
        strategic_reason="no_strategy_needed",
        source_reason=reason,
        source_action=action,
        source_ac_mode=ac_mode,
        priority=0,
        target_soc=decision.target_soc,
        allow_mode_switch=True,
        force=False,
        metadata=metadata,
    )


def strategy_decision_to_intent(
    strategy: StrategyDecision,
    *,
    pv_handover_policy: str = "default",
    load_coverage_priority: bool = False,
) -> StrategyIntent:
    """Convert a strategy decision into the unified regulation intent."""
    if strategy.state == StrategicState.EMERGENCY_CHARGE:
        intent = "emergency_charge"
    elif strategy.state == StrategicState.MANUAL_CHARGE:
        intent = "manual_charge"
    elif strategy.state == StrategicState.MANUAL_DISCHARGE:
        source_reason = str(strategy.source_reason or "")
        intent = (
            "manual_constant_discharge"
            if source_reason == "manual_constant_discharge"
            else "manual_discharge"
        )
    elif strategy.state in {
        StrategicState.AC_CHARGE_COMMITTED,
        StrategicState.AC_CHARGE_PLANNED,
        StrategicState.AC_CHARGE_PRICE,
        StrategicState.AC_CHARGE_LEARNED,
        StrategicState.AC_CHARGE_RESERVE,
    }:
        intent = "planned_charge"
    elif strategy.state == StrategicState.PV_SURPLUS_CHARGE:
        intent = "pv_charge"
    elif strategy.state == StrategicState.PASSTHROUGH:
        intent = "passthrough"
    elif strategy.state in {
        StrategicState.LOAD_COVERAGE,
        StrategicState.OFFGRID_SUPPORT,
    }:
        intent = "cover_deficit"
    elif strategy.state == StrategicState.ECONOMIC_DISCHARGE:
        source_reason = str(strategy.source_reason or "")
        intent = (
            "arbitrage_discharge"
            if source_reason == "price_based_discharge"
            else "peak_discharge"
        )
    else:
        intent = "idle"

    metadata = {
        **strategy.metadata,
        "strategy_state": strategy.state.value,
        "visible_state": strategy.visible_state.value,
        "strategic_reason": strategy.strategic_reason,
        "technical_reason": "none",
        "source_reason": strategy.source_reason,
        "source_action": strategy.source_action,
        "source_ac_mode": strategy.source_ac_mode,
        "strategy_priority": strategy.priority,
    }

    return StrategyIntent(
        intent=intent,
        requested_mode=strategy.requested_mode,
        requested_power_w=strategy.requested_power_w,
        reason=strategy.strategic_reason,
        priority=strategy.priority,
        allow_mode_switch=strategy.allow_mode_switch,
        force=strategy.force,
        pv_handover_policy=pv_handover_policy,
        load_coverage_priority=bool(load_coverage_priority),
        metadata=metadata,
    )


def decision_to_strategy_intent(
    decision: DecisionResult,
    *,
    pv_handover_policy: str = "default",
    load_coverage_priority: bool = False,
) -> StrategyIntent:
    """Compatibility entrypoint used by the coordinator."""
    strategy = decision_to_strategy_decision(decision)

    return strategy_decision_to_intent(
        strategy,
        pv_handover_policy=pv_handover_policy,
        load_coverage_priority=load_coverage_priority,
    )
