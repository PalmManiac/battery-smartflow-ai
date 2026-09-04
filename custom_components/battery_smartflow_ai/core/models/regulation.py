from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal


StrategyIntentType = Literal[
    "idle",
    "pv_charge",
    "planned_charge",
    "manual_charge",
    "emergency_charge",
    "cover_deficit",
    "peak_discharge",
    "arbitrage_discharge",
    "manual_discharge",
    "manual_constant_discharge",
    "passthrough",
]

RequestedMode = Literal[
    "input",
    "output",
    "idle",
]

ResolvedMode = Literal[
    "input",
    "output",
    "idle",
    "hold",
    "ramp_down_output",
    "ramp_down_input",
]

RegulationState = Literal[
    "none",
    "pv_charge_active",
    "discharge_active",
    "passthrough_active",
    "neutral_hold",
]

CommandSkipReason = Literal[
    "none",
    "unchanged",
    "change_too_small",
    "invalid_entity",
    "cooldown_active",
    "mode_hold_active",
]

AutomaticWeighting = Literal[
    "inactive",
    "pv_oriented",
    "balanced",
    "price_oriented",
    "reserve_oriented",
]

SeasonContext = Literal[
    "neutral",
    "summer_like",
    "winter_like",
]

PvHandoverPolicy = Literal[
    "default",
    "fast",
    "stable",
]


@dataclass
class StrategyIntent:
    """Strategic intent produced from the Decision Engine result.

    This is the semantic bridge between the existing Decision Engine and the
    new technical regulation layer.

    Important:
    INPUT is not enough as a meaning. PV charging, planned grid charging and
    emergency charging are all INPUT technically, but they need different
    regulation behavior.
    """

    intent: StrategyIntentType
    requested_mode: RequestedMode
    requested_power_w: float | None
    reason: str

    priority: int = 0
    allow_mode_switch: bool = True
    force: bool = False

    # V4.3.0-dev5.7:
    # Technical handover behavior for PV charging.
    #
    # fast:
    #   Strategic PV confirmation is sufficient. The technical layer should
    #   avoid repeating the same export confirmation unnecessarily.
    #
    # stable:
    #   Preserve stronger technical hysteresis because continuous house-load
    #   coverage has priority and clouds must not cause INPUT/OUTPUT flapping.
    #
    # default:
    #   Conservative compatibility behavior.
    pv_handover_policy: PvHandoverPolicy = "default"
    load_coverage_priority: bool = False

    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AutomaticStrategyResult:
    """High-level weighting result produced by the automatic strategy."""

    active: bool = False

    weighting: AutomaticWeighting = "inactive"
    season_context: SeasonContext = "neutral"

    pv_weight: float = 0.0
    price_weight: float = 0.0
    reserve_weight: float = 0.0
    forecast_weight: float = 0.0

    reason: str = "not_evaluated"
    metadata: dict[str, Any] = field(default_factory=dict)


# Compatibility name used by V4.6 callers.  It is an output/result, not the
# runtime input model introduced by Issue #268.
StrategyContext = AutomaticStrategyResult


@dataclass
class GridHistoryState:
    """Short signed grid history used by the ModeArbiter and PowerController.

    Internal convention:
    grid_power_w > 0  = grid import / Netzbezug
    grid_power_w < 0  = grid export / Einspeisung
    """

    grid_now_w: float = 0.0
    grid_avg_short_w: float = 0.0
    grid_avg_medium_w: float = 0.0
    grid_delta_w: float = 0.0

    stable_import_cycles: int = 0
    stable_export_cycles: int = 0
    near_target_cycles: int = 0

    fast_load_rise_detected: bool = False
    fast_load_drop_detected: bool = False

    post_load_drop_hold_active: bool = False
    post_output_overshoot_hold_active: bool = False


@dataclass
class ModeArbiterResult:
    """Result of the technical mode permission layer."""

    requested_mode: RequestedMode
    resolved_mode: ResolvedMode

    allowed: bool
    reason: str

    active_regulation_state: RegulationState = "none"
    active_hold_remaining_s: float = 0.0
    cooldown_remaining_s: float = 0.0

    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PowerControllerResult:
    """Result of the technical power calculation layer."""

    raw_target_w: float = 0.0
    limited_target_w: float = 0.0
    applied_step_w: float = 0.0
    final_power_w: float = 0.0

    profile_limited: bool = False
    step_limited: bool = False

    reason: str = "none"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChargeSourceAllocation:
    """Calculated source split for an active strategic AC charge binding.

    V4.4.0-dev8:
    Source allocation plus the effective total AC input command. The device
    cannot distinguish PV power from grid power at its AC input.

    total_target_w:
        Strategic total battery charge target.

    pv_available_w:
        Estimated PV power remaining after house load.

    pv_allocated_w:
        AC-coupled PV contribution assigned to the total charge target.

    native_pv_available_w / native_pv_allocated_w:
        PV connected directly to the battery system. It is reserved first
        inside the physical total charge limit.

    grid_requested_w:
        Remaining AC/grid contribution required to reach the total target.

    device_input_w:
        AC input power to request from the battery. It includes AC-coupled PV
        but excludes native PV, which reaches the battery through its MPPTs.

    unfilled_w:
        Part of the total target that cannot be covered because the grid input
        limit is lower than the required remaining power.
    """

    active: bool = False

    total_target_w: float = 0.0
    pv_available_w: float = 0.0
    pv_allocated_w: float = 0.0
    native_pv_available_w: float = 0.0
    native_pv_allocated_w: float = 0.0
    grid_requested_w: float = 0.0
    device_input_w: float = 0.0
    unfilled_w: float = 0.0

    pv_share_pct: float = 0.0
    grid_share_pct: float = 0.0

    reason: str = "inactive"


@dataclass
class DeviceCommand:
    """Neutral device command produced by the core regulation layer."""

    ac_mode: Literal["input", "output"]
    input_limit_w: float = 0.0
    output_limit_w: float = 0.0
    min_soc_pct: float | None = None
    max_soc_pct: float | None = None

    reason: str = "none"

    should_write_mode: bool = True
    should_write_input: bool = True
    should_write_output: bool = True
    should_write_min_soc: bool = False
    should_write_max_soc: bool = False

    skipped: bool = False
    skip_reason: CommandSkipReason = "none"

    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RegulationRuntimeState:
    """Persistable runtime state for the new technical regulation layer."""

    last_resolved_mode: ResolvedMode = "idle"
    last_requested_mode: RequestedMode = "idle"

    last_ac_mode: str | None = None
    last_input_limit_w: float = 0.0
    last_output_limit_w: float = 0.0

    last_mode_change_ts: datetime | None = None
    last_command_ts: datetime | None = None

    active_regulation_state: RegulationState = "none"
    active_state_started_ts: datetime | None = None

    post_load_drop_hold_until: datetime | None = None
    post_output_overshoot_hold_until: datetime | None = None

    pv_charge_latch_started_ts: datetime | None = None
    discharge_latch_started_ts: datetime | None = None
    passthrough_latch_started_ts: datetime | None = None

    skipped_write_reason: str = "none"
