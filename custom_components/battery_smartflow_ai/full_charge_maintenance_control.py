"""Apply a neutral maintenance request to the existing strategy boundary."""

from __future__ import annotations

from dataclasses import dataclass

from .core.full_charge_maintenance import (
    FullChargeMaintenanceDecision,
    MaintenanceWindow,
)
from .decision_engine import DecisionResult


_HARD_SAFETY_REASONS = frozenset({
    "sensor_invalid",
    "soc_invalid",
    "grid_sensor_invalid",
    "soc_limits_invalid",
    "power_limits_invalid",
    "cell_voltage_sensor_invalid",
    "cell_voltage_emergency_charge",
    "emergency_latched_charge",
})


@dataclass(frozen=True, slots=True)
class MaintenanceStrategyApplication:
    decision: DecisionResult
    effective_soc_max: float
    applied: bool = False


def apply_maintenance_charge_request(
    decision: DecisionResult,
    maintenance: FullChargeMaintenanceDecision | None,
    *,
    configured_soc_max: float,
    max_charge_w: float,
    grid_export_w: float,
    automation_allowed: bool,
) -> MaintenanceStrategyApplication:
    """Temporarily lift only the strategy target; never mutate stored limits."""

    if (
        maintenance is None
        or not maintenance.request_full_charge
        or not maintenance.temporary_user_limit_override
        or maintenance.target_soc_pct != 100.0
        or not automation_allowed
        or decision.action == "emergency"
        or str(decision.reason or "") in _HARD_SAFETY_REASONS
    ):
        return MaintenanceStrategyApplication(decision, configured_soc_max)

    charge_w = float(max_charge_w)
    reason = "planning_latest_start"
    if maintenance.selected_window is MaintenanceWindow.PV_SURPLUS:
        charge_w = min(
            float(max_charge_w),
            max(float(decision.charge_w or 0.0), float(grid_export_w), 0.0),
        )
        reason = "pv_surplus_charge"
    elif maintenance.selected_window is MaintenanceWindow.LOW_PRICE:
        reason = "valley_opportunity_charge"
    elif (
        maintenance.selected_window is MaintenanceWindow.EXISTING_STRATEGIC_CHARGE
        and decision.action == "charge"
    ):
        charge_w = max(float(decision.charge_w or 0.0), 0.0)
        reason = str(decision.reason or "charge_commit_active")

    return MaintenanceStrategyApplication(
        DecisionResult(
            action="charge",
            ac_mode="input",
            charge_w=charge_w,
            discharge_w=0.0,
            reason=reason,
            target_soc=100.0,
            current_peak_threshold=decision.current_peak_threshold,
            current_valley_threshold=decision.current_valley_threshold,
            economic_discharge_threshold=decision.economic_discharge_threshold,
            effective_discharge_threshold=decision.effective_discharge_threshold,
        ),
        effective_soc_max=100.0,
        applied=True,
    )
