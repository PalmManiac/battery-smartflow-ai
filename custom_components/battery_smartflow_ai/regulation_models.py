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

    metadata: dict[str, Any] = field(default_factory=dict)


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
class DeviceCommand:
    """Final command that may be written to Home Assistant/Zendure entities."""

    ac_mode: Literal["input", "output"]
    input_limit_w: float = 0.0
    output_limit_w: float = 0.0

    reason: str = "none"

    should_write_mode: bool = True
    should_write_input: bool = True
    should_write_output: bool = True

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
