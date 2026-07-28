from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


CommandDirection = Literal["none", "input", "output"]
RetryDirection = Literal["input", "output"] | None


@dataclass(frozen=True)
class CommandEffectivenessConfig:
    """Limits for bounded active-command recovery."""

    min_target_w: float = 60.0
    active_power_threshold_w: float = 30.0
    min_output_grid_import_w: float = 60.0
    mismatch_confirm_cycles: int = 3
    retry_cooldown_s: float = 60.0
    max_retries: int = 3


@dataclass
class CommandEffectivenessState:
    """Persistable state for one active INPUT/OUTPUT command episode."""

    direction: CommandDirection = "none"
    mismatch_cycles: int = 0
    retry_count: int = 0
    last_retry_at: datetime | None = None


@dataclass
class CommandEffectivenessResult:
    """Result of one effectiveness check."""

    state: CommandEffectivenessState
    status: str
    reason: str
    retry_direction: RetryDirection
    target_w: float
    measured_w: float


def evaluate_command_effectiveness(
    *,
    now: datetime,
    requested_mode: str,
    input_target_w: float,
    output_target_w: float,
    battery_charge_w: float,
    battery_discharge_w: float,
    battery_sensor_valid: bool,
    grid_import_w: float,
    current_ac_mode: str | None,
    active_command_write_pending: bool,
    previous: CommandEffectivenessState,
    config: CommandEffectivenessConfig | None = None,
) -> CommandEffectivenessResult:
    """Detect a lost active command without creating an unbounded write loop.

    The Number entity can still show the requested value after Zendure-HA or the
    device stopped applying it. Therefore the desired active direction is also
    checked against measured battery power.

    A retry is proposed only after several consecutive mismatches. OUTPUT also
    requires real grid import so a battery that is legitimately idle while PV
    covers the load is not restarted.
    """

    cfg = config or CommandEffectivenessConfig()

    input_target = max(0.0, float(input_target_w or 0.0))
    output_target = max(0.0, float(output_target_w or 0.0))

    direction: CommandDirection = "none"
    target_w = 0.0
    measured_w = 0.0

    if requested_mode == "input" and input_target >= cfg.min_target_w:
        direction = "input"
        target_w = input_target
        measured_w = max(0.0, float(battery_charge_w or 0.0))
    elif requested_mode == "output" and output_target >= cfg.min_target_w:
        direction = "output"
        target_w = output_target
        measured_w = max(0.0, float(battery_discharge_w or 0.0))

    if direction == "none":
        return _result(
            state=CommandEffectivenessState(),
            status="inactive",
            reason="no_active_power_command",
            target_w=target_w,
            measured_w=measured_w,
        )

    if previous.direction != direction:
        return _result(
            state=CommandEffectivenessState(direction=direction),
            status="monitoring",
            reason="active_direction_started",
            target_w=target_w,
            measured_w=measured_w,
        )

    state = CommandEffectivenessState(
        direction=direction,
        mismatch_cycles=max(0, int(previous.mismatch_cycles or 0)),
        retry_count=max(0, int(previous.retry_count or 0)),
        last_retry_at=previous.last_retry_at,
    )

    if not battery_sensor_valid:
        state.mismatch_cycles = 0
        return _result(
            state=state,
            status="unavailable",
            reason="battery_power_sensor_invalid",
            target_w=target_w,
            measured_w=measured_w,
        )

    if str(current_ac_mode or "") != direction:
        state.mismatch_cycles = 0
        return _result(
            state=state,
            status="waiting",
            reason="ac_mode_not_yet_active",
            target_w=target_w,
            measured_w=measured_w,
        )

    if measured_w > cfg.active_power_threshold_w:
        state.mismatch_cycles = 0
        state.retry_count = 0
        state.last_retry_at = None
        return _result(
            state=state,
            status="effective",
            reason="measured_power_active",
            target_w=target_w,
            measured_w=measured_w,
        )

    if (
        direction == "output"
        and max(0.0, float(grid_import_w or 0.0))
        < cfg.min_output_grid_import_w
    ):
        state.mismatch_cycles = 0
        return _result(
            state=state,
            status="waiting",
            reason="no_relevant_grid_import",
            target_w=target_w,
            measured_w=measured_w,
        )

    if active_command_write_pending:
        state.mismatch_cycles = 0
        return _result(
            state=state,
            status="waiting",
            reason="active_command_write_pending",
            target_w=target_w,
            measured_w=measured_w,
        )

    state.mismatch_cycles = min(
        max(1, int(cfg.mismatch_confirm_cycles)),
        state.mismatch_cycles + 1,
    )

    if state.mismatch_cycles < max(1, int(cfg.mismatch_confirm_cycles)):
        return _result(
            state=state,
            status="confirming",
            reason="measured_power_missing",
            target_w=target_w,
            measured_w=measured_w,
        )

    if state.retry_count >= max(0, int(cfg.max_retries)):
        return _result(
            state=state,
            status="exhausted",
            reason="maximum_retries_reached",
            target_w=target_w,
            measured_w=measured_w,
        )

    if state.last_retry_at is not None:
        elapsed_s = max(0.0, (now - state.last_retry_at).total_seconds())
        if elapsed_s < max(0.0, float(cfg.retry_cooldown_s)):
            return _result(
                state=state,
                status="cooldown",
                reason="retry_cooldown_active",
                target_w=target_w,
                measured_w=measured_w,
            )

    return _result(
        state=state,
        status="retry_due",
        reason="active_command_not_effective",
        retry_direction=direction,
        target_w=target_w,
        measured_w=measured_w,
    )


def record_effectiveness_retry(
    *,
    now: datetime,
    direction: str,
    previous: CommandEffectivenessState,
) -> CommandEffectivenessState:
    """Record a retry only after Home Assistant accepted the service call."""

    normalized: CommandDirection = (
        direction if direction in ("input", "output") else "none"
    )

    if previous.direction != normalized:
        previous = CommandEffectivenessState(direction=normalized)

    return CommandEffectivenessState(
        direction=normalized,
        mismatch_cycles=0,
        retry_count=max(0, int(previous.retry_count or 0)) + 1,
        last_retry_at=now,
    )


def _result(
    *,
    state: CommandEffectivenessState,
    status: str,
    reason: str,
    target_w: float,
    measured_w: float,
    retry_direction: RetryDirection = None,
) -> CommandEffectivenessResult:
    return CommandEffectivenessResult(
        state=state,
        status=status,
        reason=reason,
        retry_direction=retry_direction,
        target_w=round(float(target_w or 0.0), 2),
        measured_w=round(float(measured_w or 0.0), 2),
    )
