from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.util import dt as dt_util

from .regulation_models import (
    GridHistoryState,
    ModeArbiterResult,
    RegulationRuntimeState,
    StrategyIntent,
)


DEFAULT_MODE_SWITCH_COOLDOWN_S = 30.0
DEFAULT_INPUT_AFTER_OUTPUT_BLOCK_S = 60.0
DEFAULT_OUTPUT_AFTER_INPUT_BLOCK_S = 30.0

DEFAULT_STABLE_EXPORT_CYCLES_FOR_PV_CHARGE = 3
DEFAULT_STABLE_IMPORT_CYCLES_FOR_DISCHARGE = 2

DEFAULT_PV_CHARGE_LATCH_MIN_HOLD_S = 120.0
DEFAULT_PV_CHARGE_EXIT_IMPORT_CYCLES = 3

DEFAULT_DISCHARGE_LATCH_MIN_HOLD_S = 60.0
DEFAULT_DISCHARGE_EXIT_EXPORT_CYCLES = 3

DEFAULT_PASSTHROUGH_LATCH_MIN_HOLD_S = 120.0
DEFAULT_PASSTHROUGH_EXIT_CYCLES = 3

DEFAULT_POST_LOAD_DROP_HOLD_S = 60.0
DEFAULT_POST_OUTPUT_OVERSHOOT_HOLD_S = 60.0

DEFAULT_EXTERNAL_BATTERY_DISCHARGE_BLOCK_W = 50.0


@dataclass
class ModeArbiterConfig:
    mode_switch_cooldown_s: float = DEFAULT_MODE_SWITCH_COOLDOWN_S
    input_after_output_block_s: float = DEFAULT_INPUT_AFTER_OUTPUT_BLOCK_S
    output_after_input_block_s: float = DEFAULT_OUTPUT_AFTER_INPUT_BLOCK_S

    stable_export_cycles_for_pv_charge: int = (
        DEFAULT_STABLE_EXPORT_CYCLES_FOR_PV_CHARGE
    )
    stable_import_cycles_for_discharge: int = (
        DEFAULT_STABLE_IMPORT_CYCLES_FOR_DISCHARGE
    )

    pv_charge_latch_min_hold_s: float = DEFAULT_PV_CHARGE_LATCH_MIN_HOLD_S
    pv_charge_exit_import_cycles: int = DEFAULT_PV_CHARGE_EXIT_IMPORT_CYCLES

    discharge_latch_min_hold_s: float = DEFAULT_DISCHARGE_LATCH_MIN_HOLD_S
    discharge_exit_export_cycles: int = DEFAULT_DISCHARGE_EXIT_EXPORT_CYCLES

    passthrough_latch_min_hold_s: float = DEFAULT_PASSTHROUGH_LATCH_MIN_HOLD_S
    passthrough_exit_cycles: int = DEFAULT_PASSTHROUGH_EXIT_CYCLES

    post_load_drop_hold_s: float = DEFAULT_POST_LOAD_DROP_HOLD_S
    post_output_overshoot_hold_s: float = DEFAULT_POST_OUTPUT_OVERSHOOT_HOLD_S

    external_battery_discharge_block_w: float = (
        DEFAULT_EXTERNAL_BATTERY_DISCHARGE_BLOCK_W
    )

    supports_passthrough: bool = False
    input_keepalive_safe: bool = True
    requires_stable_export_for_input: bool = False
    supports_fast_mode_switch: bool = True


def _profile_float(profile: dict[str, Any], key: str, default: float) -> float:
    try:
        return float(profile.get(key, default))
    except Exception:
        return float(default)


def _profile_int(profile: dict[str, Any], key: str, default: int) -> int:
    try:
        return int(profile.get(key, default))
    except Exception:
        return int(default)


def _profile_bool(profile: dict[str, Any], key: str, default: bool) -> bool:
    try:
        value = profile.get(key, default)

        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in ("true", "1", "yes", "on"):
                return True
            if normalized in ("false", "0", "no", "off", "none", ""):
                return False

        return bool(value)
    except Exception:
        return bool(default)


def build_mode_arbiter_config(profile: dict[str, Any]) -> ModeArbiterConfig:
    """Build ModeArbiterConfig from device profile/capabilities."""

    return ModeArbiterConfig(
        mode_switch_cooldown_s=_profile_float(
            profile,
            "MODE_SWITCH_COOLDOWN_S",
            DEFAULT_MODE_SWITCH_COOLDOWN_S,
        ),
        input_after_output_block_s=_profile_float(
            profile,
            "INPUT_AFTER_OUTPUT_BLOCK_S",
            DEFAULT_INPUT_AFTER_OUTPUT_BLOCK_S,
        ),
        output_after_input_block_s=_profile_float(
            profile,
            "OUTPUT_AFTER_INPUT_BLOCK_S",
            DEFAULT_OUTPUT_AFTER_INPUT_BLOCK_S,
        ),
        stable_export_cycles_for_pv_charge=_profile_int(
            profile,
            "STABLE_EXPORT_CYCLES_FOR_PV_CHARGE",
            DEFAULT_STABLE_EXPORT_CYCLES_FOR_PV_CHARGE,
        ),
        stable_import_cycles_for_discharge=_profile_int(
            profile,
            "STABLE_IMPORT_CYCLES_FOR_DISCHARGE",
            DEFAULT_STABLE_IMPORT_CYCLES_FOR_DISCHARGE,
        ),
        pv_charge_latch_min_hold_s=_profile_float(
            profile,
            "PV_CHARGE_LATCH_MIN_HOLD_S",
            _profile_float(
                profile,
                "PV_CHARGE_LATCH_HOLD_SECONDS",
                DEFAULT_PV_CHARGE_LATCH_MIN_HOLD_S,
            ),
        ),
        pv_charge_exit_import_cycles=_profile_int(
            profile,
            "PV_CHARGE_EXIT_IMPORT_CYCLES",
            _profile_int(
                profile,
                "PV_CHARGE_LATCH_STOP_CYCLES",
                DEFAULT_PV_CHARGE_EXIT_IMPORT_CYCLES,
            ),
        ),
        discharge_latch_min_hold_s=_profile_float(
            profile,
            "DISCHARGE_LATCH_MIN_HOLD_S",
            DEFAULT_DISCHARGE_LATCH_MIN_HOLD_S,
        ),
        discharge_exit_export_cycles=_profile_int(
            profile,
            "DISCHARGE_EXIT_EXPORT_CYCLES",
            DEFAULT_DISCHARGE_EXIT_EXPORT_CYCLES,
        ),
        passthrough_latch_min_hold_s=_profile_float(
            profile,
            "PASSTHROUGH_LATCH_MIN_HOLD_S",
            _profile_float(
                profile,
                "PV_HOUSELOAD_PASSTHROUGH_HOLD_SECONDS",
                DEFAULT_PASSTHROUGH_LATCH_MIN_HOLD_S,
            ),
        ),
        passthrough_exit_cycles=_profile_int(
            profile,
            "PASSTHROUGH_EXIT_CYCLES",
            _profile_int(
                profile,
                "PV_HOUSELOAD_PASSTHROUGH_EXPORT_STOP_CYCLES",
                DEFAULT_PASSTHROUGH_EXIT_CYCLES,
            ),
        ),
        post_load_drop_hold_s=_profile_float(
            profile,
            "POST_LOAD_DROP_HOLD_S",
            DEFAULT_POST_LOAD_DROP_HOLD_S,
        ),
        post_output_overshoot_hold_s=_profile_float(
            profile,
            "POST_OUTPUT_OVERSHOOT_HOLD_S",
            DEFAULT_POST_OUTPUT_OVERSHOOT_HOLD_S,
        ),
        external_battery_discharge_block_w=_profile_float(
            profile,
            "EXTERNAL_BATTERY_DISCHARGE_BLOCK_W",
            DEFAULT_EXTERNAL_BATTERY_DISCHARGE_BLOCK_W,
        ),
        supports_passthrough=_profile_bool(
            profile,
            "SUPPORTS_PASSTHROUGH",
            _profile_bool(profile, "PV_HOUSELOAD_PASSTHROUGH", False),
        ),
        input_keepalive_safe=_profile_bool(
            profile,
            "INPUT_KEEPALIVE_SAFE",
            True,
        ),
        requires_stable_export_for_input=_profile_bool(
            profile,
            "REQUIRES_STABLE_EXPORT_FOR_INPUT",
            False,
        ),
        supports_fast_mode_switch=_profile_bool(
            profile,
            "SUPPORTS_FAST_MODE_SWITCH",
            True,
        ),
    )


class ModeArbiter:
    """Technical mode permission layer.

    The Decision Engine says what should happen.
    The ModeArbiter decides whether the requested mode may technically happen now.
    """

    def __init__(self, config: ModeArbiterConfig | None = None) -> None:
        self.config = config or ModeArbiterConfig()

    def evaluate(
        self,
        *,
        now: datetime,
        intent: StrategyIntent,
        grid: GridHistoryState,
        runtime: RegulationRuntimeState,
        current_ac_mode: str | None,
        additional_battery_discharge_w: float = 0.0,
    ) -> ModeArbiterResult:
        now_utc = dt_util.as_utc(now)
        requested_mode = intent.requested_mode

        metadata: dict[str, Any] = {
            "intent": intent.intent,
            "requested_power_w": intent.requested_power_w,
            "grid_now_w": grid.grid_now_w,
            "grid_avg_short_w": grid.grid_avg_short_w,
            "stable_import_cycles": grid.stable_import_cycles,
            "stable_export_cycles": grid.stable_export_cycles,
            "current_ac_mode": current_ac_mode,
            "last_resolved_mode": runtime.last_resolved_mode,
            "last_ac_mode": runtime.last_ac_mode,
            "last_mode_change_ts": (
                runtime.last_mode_change_ts.isoformat()
                if runtime.last_mode_change_ts
                else None
            ),
            "active_regulation_state": runtime.active_regulation_state,
            "supports_fast_mode_switch": bool(self.config.supports_fast_mode_switch),
            "input_after_output_block_s": float(self.config.input_after_output_block_s),
            "output_after_input_block_s": float(self.config.output_after_input_block_s),
            "mode_switch_cooldown_s": float(self.config.mode_switch_cooldown_s),
            "stable_import_cycles_for_discharge": int(
                self.config.stable_import_cycles_for_discharge
            ),
            "stable_export_cycles_for_pv_charge": int(
                self.config.stable_export_cycles_for_pv_charge
            ),
            "discharge_exit_export_cycles": int(
                self.config.discharge_exit_export_cycles
            ),
        }

        # Emergency/manual force may switch modes immediately.
        if intent.force:
            return ModeArbiterResult(
                requested_mode=requested_mode,
                resolved_mode=(
                    requested_mode
                    if requested_mode in ("input", "output")
                    else "idle"
                ),
                allowed=True,
                reason="force_intent",
                active_regulation_state=self._state_for_intent(intent.intent),
                active_hold_remaining_s=0.0,
                cooldown_remaining_s=0.0,
                metadata=metadata,
            )

        # External battery discharge blocks charging, but not discharging.
        # It must also override an active PV/charge hold, otherwise a previous
        # charge latch could keep INPUT alive while another battery is discharging.
        additional_battery_discharge_active = (
            float(additional_battery_discharge_w or 0.0)
            > float(self.config.external_battery_discharge_block_w)
        )

        if additional_battery_discharge_active and (
            requested_mode == "input"
            or runtime.active_regulation_state == "pv_charge_active"
        ):
            return ModeArbiterResult(
                requested_mode=requested_mode,
                resolved_mode="idle",
                allowed=False,
                reason="external_battery_discharge_blocks_input",
                active_regulation_state="neutral_hold",
                active_hold_remaining_s=0.0,
                cooldown_remaining_s=0.0,
                metadata={
                    **metadata,
                    "additional_battery_discharge_w": float(
                        additional_battery_discharge_w or 0.0
                    ),
                },
            )

        # Post-load-drop / post-overshoot holds should react before normal mode checks.
        post_hold_result = self._evaluate_post_holds(
            now_utc=now_utc,
            intent=intent,
            grid=grid,
            runtime=runtime,
            metadata=metadata,
        )
        if post_hold_result is not None:
            return post_hold_result

        # Active latch minimum hold times must be evaluated before normal idle.
        # Otherwise an active discharge can collapse to idle for one cycle and
        # cause sawtooth behaviour.
        active_hold_result = self._evaluate_active_min_hold(
            now_utc=now_utc,
            intent=intent,
            runtime=runtime,
            metadata=metadata,
        )
        if active_hold_result is not None:
            return active_hold_result

        # Idle is allowed only after active holds had a chance to keep/ramp a
        # previous regulation state.
        if requested_mode == "idle":
            return ModeArbiterResult(
                requested_mode=requested_mode,
                resolved_mode="idle",
                allowed=True,
                reason=intent.reason or "idle",
                active_regulation_state="neutral_hold",
                active_hold_remaining_s=0.0,
                cooldown_remaining_s=0.0,
                metadata=metadata,
            )

        # If the strategy explicitly does not allow switching, hold.
        if not intent.allow_mode_switch:
            return ModeArbiterResult(
                requested_mode=requested_mode,
                resolved_mode="hold",
                allowed=False,
                reason="mode_switch_not_allowed_by_strategy",
                active_regulation_state=runtime.active_regulation_state,
                active_hold_remaining_s=0.0,
                cooldown_remaining_s=0.0,
                metadata=metadata,
            )

        cooldown_remaining_s = self._mode_cooldown_remaining_s(
            now_utc=now_utc,
            runtime=runtime,
            requested_mode=requested_mode,
            current_ac_mode=current_ac_mode,
        )

        if cooldown_remaining_s > 0.0 and self._is_real_mode_switch(
            current_ac_mode=current_ac_mode,
            requested_mode=requested_mode,
        ):
            return ModeArbiterResult(
                requested_mode=requested_mode,
                resolved_mode="hold",
                allowed=False,
                reason=(
                    "input_after_output_block_active"
                    if current_ac_mode == "output" and requested_mode == "input"
                    else "output_after_input_block_active"
                    if current_ac_mode == "input" and requested_mode == "output"
                    else "mode_switch_cooldown_active"
                ),
                active_regulation_state=runtime.active_regulation_state,
                active_hold_remaining_s=0.0,
                cooldown_remaining_s=cooldown_remaining_s,
                metadata=metadata,
            )

        if requested_mode == "input":
            return self._evaluate_input(
                now_utc=now_utc,
                intent=intent,
                grid=grid,
                runtime=runtime,
                metadata=metadata,
            )

        if requested_mode == "output":
            return self._evaluate_output(
                now_utc=now_utc,
                intent=intent,
                grid=grid,
                runtime=runtime,
                metadata=metadata,
            )

        return ModeArbiterResult(
            requested_mode=requested_mode,
            resolved_mode="idle",
            allowed=True,
            reason="fallback_idle",
            active_regulation_state="neutral_hold",
            active_hold_remaining_s=0.0,
            cooldown_remaining_s=0.0,
            metadata=metadata,
        )

    def _evaluate_post_holds(
        self,
        *,
        now_utc: datetime,
        intent: StrategyIntent,
        grid: GridHistoryState,
        runtime: RegulationRuntimeState,
        metadata: dict[str, Any],
    ) -> ModeArbiterResult | None:
        """Evaluate short post-event holds.

        These holds prevent immediate INPUT switching after a large load drop or
        after output overshoot. Instead, the PowerController can ramp output down.
        """

        requested_mode = intent.requested_mode

        post_load_drop_remaining_s = self._remaining_until_s(
            now_utc,
            runtime.post_load_drop_hold_until,
        )

        if (
            requested_mode == "input"
            and post_load_drop_remaining_s > 0.0
            and intent.intent == "pv_charge"
        ):
            return ModeArbiterResult(
                requested_mode=requested_mode,
                resolved_mode="ramp_down_output",
                allowed=True,
                reason="post_load_drop_ramp_down_output",
                active_regulation_state="discharge_active",
                active_hold_remaining_s=post_load_drop_remaining_s,
                cooldown_remaining_s=0.0,
                metadata={
                    **metadata,
                    "post_load_drop_remaining_s": round(
                        post_load_drop_remaining_s,
                        1,
                    ),
                },
            )

        post_output_overshoot_remaining_s = self._remaining_until_s(
            now_utc,
            runtime.post_output_overshoot_hold_until,
        )

        if (
            requested_mode == "input"
            and post_output_overshoot_remaining_s > 0.0
            and intent.intent == "pv_charge"
        ):
            return ModeArbiterResult(
                requested_mode=requested_mode,
                resolved_mode="ramp_down_output",
                allowed=True,
                reason="post_output_overshoot_ramp_down_output",
                active_regulation_state="discharge_active",
                active_hold_remaining_s=post_output_overshoot_remaining_s,
                cooldown_remaining_s=0.0,
                metadata={
                    **metadata,
                    "post_output_overshoot_remaining_s": round(
                        post_output_overshoot_remaining_s,
                        1,
                    ),
                },
            )

        if (
            requested_mode == "input"
            and intent.intent == "pv_charge"
            and bool(grid.fast_load_drop_detected)
            and runtime.active_regulation_state == "discharge_active"
        ):
            return ModeArbiterResult(
                requested_mode=requested_mode,
                resolved_mode="ramp_down_output",
                allowed=True,
                reason="fast_load_drop_ramp_down_output",
                active_regulation_state="discharge_active",
                active_hold_remaining_s=float(self.config.post_load_drop_hold_s),
                cooldown_remaining_s=0.0,
                metadata=metadata,
            )

        return None

    def _evaluate_active_min_hold(
        self,
        *,
        now_utc: datetime,
        intent: StrategyIntent,
        runtime: RegulationRuntimeState,
        metadata: dict[str, Any],
    ) -> ModeArbiterResult | None:
        """Keep active regulation states alive for their minimum hold time."""

        requested_mode = intent.requested_mode

        if runtime.active_regulation_state == "pv_charge_active":
            remaining_s = self._latch_remaining_s(
                now_utc=now_utc,
                started_ts=runtime.pv_charge_latch_started_ts,
                hold_s=self.config.pv_charge_latch_min_hold_s,
            )

            if remaining_s > 0.0 and requested_mode != "input":
                return ModeArbiterResult(
                    requested_mode=requested_mode,
                    resolved_mode="input",
                    allowed=True,
                    reason="pv_charge_min_hold_active",
                    active_regulation_state="pv_charge_active",
                    active_hold_remaining_s=remaining_s,
                    cooldown_remaining_s=0.0,
                    metadata={
                        **metadata,
                        "pv_charge_hold_remaining_s": round(remaining_s, 1),
                    },
                )

        if runtime.active_regulation_state == "discharge_active":
            remaining_s = self._latch_remaining_s(
                now_utc=now_utc,
                started_ts=runtime.discharge_latch_started_ts,
                hold_s=self.config.discharge_latch_min_hold_s,
            )

            if remaining_s > 0.0 and requested_mode != "output":
                return ModeArbiterResult(
                    requested_mode=requested_mode,
                    resolved_mode="ramp_down_output",
                    allowed=True,
                    reason="discharge_min_hold_ramp_down_output",
                    active_regulation_state="discharge_active",
                    active_hold_remaining_s=remaining_s,
                    cooldown_remaining_s=0.0,
                    metadata={
                        **metadata,
                        "discharge_hold_remaining_s": round(remaining_s, 1),
                    },
                )

        if runtime.active_regulation_state == "passthrough_active":
            remaining_s = self._latch_remaining_s(
                now_utc=now_utc,
                started_ts=runtime.passthrough_latch_started_ts,
                hold_s=self.config.passthrough_latch_min_hold_s,
            )

            if remaining_s > 0.0 and requested_mode != "output":
                return ModeArbiterResult(
                    requested_mode=requested_mode,
                    resolved_mode="output",
                    allowed=True,
                    reason="passthrough_min_hold_active",
                    active_regulation_state="passthrough_active",
                    active_hold_remaining_s=remaining_s,
                    cooldown_remaining_s=0.0,
                    metadata={
                        **metadata,
                        "passthrough_hold_remaining_s": round(remaining_s, 1),
                    },
                )

        return None

    def _remaining_until_s(
        self,
        now_utc: datetime,
        until_ts: datetime | None,
    ) -> float:
        if until_ts is None:
            return 0.0

        try:
            until_utc = dt_util.as_utc(until_ts)
            return max(0.0, (until_utc - now_utc).total_seconds())
        except Exception:
            return 0.0

    def _latch_remaining_s(
        self,
        *,
        now_utc: datetime,
        started_ts: datetime | None,
        hold_s: float,
    ) -> float:
        if started_ts is None:
            return 0.0

        try:
            started_utc = dt_util.as_utc(started_ts)
            elapsed_s = (now_utc - started_utc).total_seconds()
            return max(0.0, float(hold_s) - elapsed_s)
        except Exception:
            return 0.0

    def _evaluate_input(
        self,
        *,
        now_utc: datetime,
        intent: StrategyIntent,
        grid: GridHistoryState,
        runtime: RegulationRuntimeState,
        metadata: dict[str, Any],
    ) -> ModeArbiterResult:
        if intent.intent == "pv_charge":
            if (
                grid.stable_export_cycles
                < self.config.stable_export_cycles_for_pv_charge
            ):
                return ModeArbiterResult(
                    requested_mode="input",
                    resolved_mode="hold",
                    allowed=False,
                    reason="pv_charge_wait_stable_export",
                    active_regulation_state=runtime.active_regulation_state,
                    active_hold_remaining_s=0.0,
                    cooldown_remaining_s=0.0,
                    metadata=metadata,
                )

            return ModeArbiterResult(
                requested_mode="input",
                resolved_mode="input",
                allowed=True,
                reason="pv_charge_stable_export",
                active_regulation_state="pv_charge_active",
                active_hold_remaining_s=0.0,
                cooldown_remaining_s=0.0,
                metadata=metadata,
            )

        if (
            self.config.requires_stable_export_for_input
            and intent.intent not in (
                "planned_charge",
                "manual_charge",
                "emergency_charge",
            )
            and grid.stable_export_cycles
            < self.config.stable_export_cycles_for_pv_charge
        ):
            return ModeArbiterResult(
                requested_mode="input",
                resolved_mode="hold",
                allowed=False,
                reason="input_requires_stable_export",
                active_regulation_state=runtime.active_regulation_state,
                active_hold_remaining_s=0.0,
                cooldown_remaining_s=0.0,
                metadata=metadata,
            )

        return ModeArbiterResult(
            requested_mode="input",
            resolved_mode="input",
            allowed=True,
            reason=f"{intent.intent}_input_allowed",
            active_regulation_state=self._state_for_intent(intent.intent),
            active_hold_remaining_s=0.0,
            cooldown_remaining_s=0.0,
            metadata=metadata,
        )

    def _evaluate_output(
        self,
        *,
        now_utc: datetime,
        intent: StrategyIntent,
        grid: GridHistoryState,
        runtime: RegulationRuntimeState,
        metadata: dict[str, Any],
    ) -> ModeArbiterResult:
        if intent.intent in (
            "cover_deficit",
            "peak_discharge",
            "arbitrage_discharge",
        ):
            exit_cycles = max(
                1,
                int(self.config.discharge_exit_export_cycles),
            )

            if runtime.active_regulation_state == "discharge_active":
                if int(grid.stable_export_cycles or 0) < exit_cycles:
                    return ModeArbiterResult(
                        requested_mode="output",
                        resolved_mode="output",
                        allowed=True,
                        reason="discharge_latch_keep_active",
                        active_regulation_state="discharge_active",
                        active_hold_remaining_s=0.0,
                        cooldown_remaining_s=0.0,
                        metadata={
                            **metadata,
                            "stable_export_cycles": int(
                                grid.stable_export_cycles or 0
                            ),
                            "discharge_exit_export_cycles": exit_cycles,
                        },
                    )

                return ModeArbiterResult(
                    requested_mode="output",
                    resolved_mode="output",
                    allowed=True,
                    reason="discharge_latch_exit_export_stable",
                    active_regulation_state="discharge_active",
                    active_hold_remaining_s=0.0,
                    cooldown_remaining_s=0.0,
                    metadata={
                        **metadata,
                        "stable_export_cycles": int(
                            grid.stable_export_cycles or 0
                        ),
                        "discharge_exit_export_cycles": exit_cycles,
                    },
                )

            if (
                grid.stable_import_cycles
                < self.config.stable_import_cycles_for_discharge
            ):
                return ModeArbiterResult(
                    requested_mode="output",
                    resolved_mode="hold",
                    allowed=False,
                    reason="discharge_wait_stable_import",
                    active_regulation_state=runtime.active_regulation_state,
                    active_hold_remaining_s=0.0,
                    cooldown_remaining_s=0.0,
                    metadata=metadata,
                )

        if intent.intent == "passthrough" and not self.config.supports_passthrough:
            return ModeArbiterResult(
                requested_mode="output",
                resolved_mode="idle",
                allowed=False,
                reason="passthrough_not_supported",
                active_regulation_state="neutral_hold",
                active_hold_remaining_s=0.0,
                cooldown_remaining_s=0.0,
                metadata=metadata,
            )

        return ModeArbiterResult(
            requested_mode="output",
            resolved_mode="output",
            allowed=True,
            reason=f"{intent.intent}_output_allowed",
            active_regulation_state=self._state_for_intent(intent.intent),
            active_hold_remaining_s=0.0,
            cooldown_remaining_s=0.0,
            metadata=metadata,
        )

    def _mode_cooldown_remaining_s(
        self,
        *,
        now_utc: datetime,
        runtime: RegulationRuntimeState,
        requested_mode: str,
        current_ac_mode: str | None,
    ) -> float:
        if self.config.supports_fast_mode_switch:
            return 0.0

        if requested_mode not in ("input", "output"):
            return 0.0

        previous_mode = (
            str(runtime.last_ac_mode or "")
            if runtime.last_ac_mode
            else str(current_ac_mode or "")
        )

        if previous_mode not in ("input", "output"):
            return 0.0

        if previous_mode == requested_mode:
            return 0.0

        if runtime.last_mode_change_ts is None:
            return 0.0

        last_change = dt_util.as_utc(runtime.last_mode_change_ts)
        elapsed_s = (now_utc - last_change).total_seconds()

        if previous_mode == "output" and requested_mode == "input":
            block_s = float(self.config.input_after_output_block_s)
        elif previous_mode == "input" and requested_mode == "output":
            block_s = float(self.config.output_after_input_block_s)
        else:
            block_s = float(self.config.mode_switch_cooldown_s)

        remaining = block_s - elapsed_s
        return max(0.0, remaining)

    def _is_real_mode_switch(
        self,
        *,
        current_ac_mode: str | None,
        requested_mode: str,
    ) -> bool:
        if requested_mode not in ("input", "output"):
            return False

        if current_ac_mode not in ("input", "output"):
            return True

        return str(current_ac_mode) != str(requested_mode)

    def _state_for_intent(self, intent: str):
        if intent == "pv_charge":
            return "pv_charge_active"

        if intent in (
            "cover_deficit",
            "peak_discharge",
            "arbitrage_discharge",
            "manual_discharge",
            "manual_constant_discharge",
        ):
            return "discharge_active"

        if intent == "passthrough":
            return "passthrough_active"

        if intent in (
            "planned_charge",
            "manual_charge",
            "emergency_charge",
        ):
            return "pv_charge_active"

        return "none"
