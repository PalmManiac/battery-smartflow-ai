from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal


class StrategicState(StrEnum):
    PROTECTION = "protection"
    EMERGENCY_CHARGE = "emergency_charge"

    MANUAL_CHARGE = "manual_charge"
    MANUAL_DISCHARGE = "manual_discharge"
    MANUAL_IDLE = "manual_idle"

    AC_CHARGE_COMMITTED = "ac_charge_committed"
    AC_CHARGE_PLANNED = "ac_charge_planned"
    AC_CHARGE_PRICE = "ac_charge_price"
    AC_CHARGE_LEARNED = "ac_charge_learned"
    AC_CHARGE_RESERVE = "ac_charge_reserve"

    PV_SURPLUS_CHARGE = "pv_surplus_charge"

    LOAD_COVERAGE = "load_coverage"
    ECONOMIC_DISCHARGE = "economic_discharge"
    OFFGRID_SUPPORT = "offgrid_support"
    PASSTHROUGH = "passthrough"

    HOLD = "hold"
    IDLE_READY = "idle_ready"
    IDLE_SAFE = "idle_safe"


class VisibleState(StrEnum):
    READY = "ready"
    SAFE_IDLE = "safe_idle"
    PROTECTION_ACTIVE = "protection_active"
    EMERGENCY_CHARGE = "emergency_charge"
    MANUAL = "manual"

    GRID_CHARGE = "grid_charge"
    PV_CHARGE = "pv_charge"
    RESERVE_CHARGE = "reserve_charge"

    AUTARKY_COVER = "autarky_cover"
    LOAD_COVERAGE = "load_coverage"
    ECONOMIC_DISCHARGE = "economic_discharge"

    WAITING_FOR_CHARGE_WINDOW = "waiting_for_charge_window"
    WAITING_BLOCKED = "waiting_blocked"
    HOLD = "hold"


RequestedMode = Literal["input", "output", "idle"]

ChargeCommitPhase = Literal[
    "waiting",
    "active",
    "forced",
    "completed",
    "aborted",
]


@dataclass
class StrategyDecision:
    state: StrategicState
    visible_state: VisibleState
    requested_mode: RequestedMode
    requested_power_w: float | None
    strategic_reason: str
    source_reason: str
    source_action: str
    source_ac_mode: str
    priority: int
    target_soc: float | None = None
    allow_mode_switch: bool = True
    force: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChargeCommitState:
    active: bool = False

    # Runtime phase of the charge binding.
    #
    # waiting:
    #   The plan remains valid, but AC charging is currently paused.
    #
    # active:
    #   AC charging is currently economically permitted.
    #
    # forced:
    #   The latest possible start has been reached. Charging must continue
    #   so the required energy can still be available before the deadline.
    #
    # completed / aborted:
    #   Terminal diagnostic states. The persisted active flag is False.
    phase: ChargeCommitPhase = "waiting"

    commit_type: str = "none"
    source_state: str = ""
    source_reason: str = ""
    strategic_reason: str = ""

    target_soc: float | None = None
    max_soc: float | None = None

    started_at: datetime | None = None
    updated_at: datetime | None = None
    valid_until: datetime | None = None

    # Planning timestamps.
    optimal_start: datetime | None = None
    latest_start: datetime | None = None
    deadline: datetime | None = None

    # Economic boundary for planned/learned charging.
    acceptable_price_eur_kwh: float | None = None

    requested_power_w: float | None = None
    allow_pv_blend: bool = True
    abort_reason: str = "none"