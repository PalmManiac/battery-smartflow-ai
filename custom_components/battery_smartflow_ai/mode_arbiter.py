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

DEFAULT_OFFGRID_LOAD_ACTIVE_W = 50.0


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

    supports_offgrid_socket: bool = False
    supports_offgrid_input: bool = False
    offgrid_max_internal_supply_w: float = 0.0
    offgrid_load_active_w: float = DEFAULT_OFFGRID_LOAD_ACTIVE_W
    offgrid_load_blocks_ac_charge: bool = False
    offgrid_input_affects_energy_balance: bool = False


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
            DEFAULT_PV_CHARGE_LATCH_MIN_HOLD_S,
        ),
        pv_charge_exit_import_cycles=_profile_int(
            profile,
            "PV_CHARGE_EXIT_IMPORT_CYCLES",
            DEFAULT_PV_CHARGE_EXIT_IMPORT_CYCLES,
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
        supports_offgrid_socket=_profile_bool(
            profile,
            "SUPPORTS_OFFGRID_SOCKET",
            False,
        ),
        supports_offgrid_input=_profile_bool(
            profile,
            "SUPPORTS_OFFGRID_INPUT",
            False,
        ),
        offgrid_max_internal_supply_w=_profile_float(
            profile,
            "OFFGRID_MAX_INTERNAL_SUPPLY_W",
            0.0,
        ),
        offgrid_load_active_w=_profile_float(
            profile,
            "OFFGRID_LOAD_ACTIVE_W",
            DEFAULT_OFFGRID_LOAD_ACTIVE_W,
        ),
        offgrid_load_blocks_ac_charge=_profile_bool(
            profile,
            "OFFGRID_LOAD_BLOCKS_AC_CHARGE",
            False,
        ),
        offgrid_input_affects_energy_balance=_profile_bool(
            profile,
            "OFFGRID_INPUT_AFFECTS_ENERGY_BALANCE",
            False,
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
        discharge_allowed: bool = True,
        offgrid_power_w: float = 0.0,
        offgrid_mode: str = "not_configured",
        offgrid_load_active: bool = False,
        offgrid_source_active: bool = False,
    ) -> ModeArbiterResult:
        now_utc = dt_util.as_utc(now)
        requested_mode = intent.requested_mode

        metadata: dict[str, Any] = {
            "intent": intent.intent,
            "requested_power_w": intent.requested_power_w,
            "intent_reason": intent.reason,
            "allow_mode_switch": intent.allow_mode_switch,
            "force": intent.force,
            "discharge_allowed": bool(discharge_allowed),
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
            "pv_charge_exit_import_cycles": int(
                self.config.pv_charge_exit_import_cycles
            ),
            "discharge_exit_export_cycles": int(
                self.config.discharge_exit_export_cycles
            ),
            "offgrid_power_w": float(offgrid_power_w or 0.0),
            "offgrid_mode": str(offgrid_mode or "not_configured"),
            "offgrid_load_active": bool(offgrid_load_active),
            "offgrid_source_active": bool(offgrid_source_active),
            "supports_offgrid_socket": bool(self.config.supports_offgrid_socket),
            "supports_offgrid_input": bool(self.config.supports_offgrid_input),
            "offgrid_max_internal_supply_w": float(
                self.config.offgrid_max_internal_supply_w
            ),
            "offgrid_load_active_w": float(self.config.offgrid_load_active_w),
            "offgrid_load_blocks_ac_charge": False,
            "offgrid_strategy_policy": "independent_observation",
            "offgrid_input_affects_energy_balance": bool(
                self.config.offgrid_input_affects_energy_balance
            ),
        }

        # V4.3.0-dev8:
        # Off-Grid load is diagnostic context only. It is not a reason to block
        # INPUT, force OUTPUT or interfere with an active AC charge binding.

        # Hard discharge protection must override active output holds.
        # This is intentionally checked before force intents and before
        # post/active holds, so low-SoC/cell protection can never be bypassed
        # by ramp_down_output, discharge latch or passthrough hold.
        if not bool(discharge_allowed) and (
            requested_mode == "output"
            or runtime.active_regulation_state in (
                "discharge_active",
                "passthrough_active",
            )
        ):
            return ModeArbiterResult(
                requested_mode=requested_mode,
                resolved_mode="idle",
                allowed=False,
                reason="discharge_blocked_by_strategy",
                active_regulation_state="neutral_hold",
                active_hold_remaining_s=0.0,
                cooldown_remaining_s=0.0,
                metadata=metadata,
            )

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
            grid=grid,
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

        V4.3.0-dev5.7:
        Automatic fast PV handover may clear obsolete OUTPUT-related holds once
        OUTPUT has actually reached 0 W and real PV export is still present.

        Autarky/stable handover keeps the existing conservative hold behavior.
        Hardware profiles that explicitly require stable export remain authoritative.
        """

        requested_mode = intent.requested_mode

        pv_handover_policy = str(
            getattr(
                intent,
                "pv_handover_policy",
                "default",
            )
            or "default"
        )

        load_coverage_priority = bool(
            getattr(
                intent,
                "load_coverage_priority",
                False,
            )
        )

        last_output_w = max(
            0.0,
            float(runtime.last_output_limit_w or 0.0),
        )

        current_export_active = (
            float(grid.grid_now_w or 0.0) < 0.0
        )

        stable_export_cycles = int(
            grid.stable_export_cycles or 0
        )

        required_export_cycles = max(
            1,
            int(
                self.config.stable_export_cycles_for_pv_charge
            ),
        )

        # Device capability remains authoritative:
        # A device that explicitly requires stable export may not use only the
        # strategic fast policy as permission to switch into INPUT.
        hardware_export_requirement_met = bool(
            not self.config.requires_stable_export_for_input
            or stable_export_cycles >= required_export_cycles
        )

        fast_pv_handover_ready = bool(
            requested_mode == "input"
            and intent.intent == "pv_charge"
            and pv_handover_policy == "fast"
            and not load_coverage_priority
            and last_output_w <= 0.0
            and current_export_active
            and hardware_export_requirement_met
        )

        post_load_drop_remaining_s = self._remaining_until_s(
            now_utc,
            runtime.post_load_drop_hold_until,
        )

        if (
            requested_mode == "input"
            and post_load_drop_remaining_s > 0.0
            and intent.intent == "pv_charge"
        ):
            # Automatic fast handover:
            # Once OUTPUT is really zero, an old load-drop timer no longer has
            # anything to ramp down. Let normal INPUT evaluation continue.
            if fast_pv_handover_ready:
                pass
            else:
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
                        "pv_handover_policy": pv_handover_policy,
                        "last_output_limit_w": last_output_w,
                        "current_export_active": current_export_active,
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
            # Automatic:
            # Real export + OUTPUT already at zero is enough unless the hardware
            # profile explicitly requires additional stable-export confirmation.
            if fast_pv_handover_ready:
                pass

            # Stable/default compatibility path:
            # Keep the existing conservative early-clear condition.
            elif (
                last_output_w <= 0.0
                and stable_export_cycles >= required_export_cycles
                and current_export_active
            ):
                return ModeArbiterResult(
                    requested_mode=requested_mode,
                    resolved_mode="input",
                    allowed=True,
                    reason=(
                        "post_output_overshoot_"
                        "cleared_for_stable_pv_charge"
                    ),
                    active_regulation_state="pv_charge_active",
                    active_hold_remaining_s=0.0,
                    cooldown_remaining_s=0.0,
                    metadata={
                        **metadata,
                        "post_output_overshoot_remaining_s": round(
                            post_output_overshoot_remaining_s,
                            1,
                        ),
                        "pv_handover_policy": pv_handover_policy,
                        "last_output_limit_w": last_output_w,
                        "stable_export_cycles": stable_export_cycles,
                        "required_export_cycles": required_export_cycles,
                        "current_export_active": current_export_active,
                    },
                )

            else:
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
                        "pv_handover_policy": pv_handover_policy,
                        "last_output_limit_w": last_output_w,
                        "stable_export_cycles": stable_export_cycles,
                        "required_export_cycles": required_export_cycles,
                        "current_export_active": current_export_active,
                    },
                )

        if (
            requested_mode == "input"
            and intent.intent == "pv_charge"
            and bool(grid.fast_load_drop_detected)
            and runtime.active_regulation_state == "discharge_active"
        ):
            # A fast-load-drop flag can survive for a short time after OUTPUT has
            # already reached zero. Do not restart another artificial ramp-down in
            # Automatic fast mode.
            if fast_pv_handover_ready:
                return None

            return ModeArbiterResult(
                requested_mode=requested_mode,
                resolved_mode="ramp_down_output",
                allowed=True,
                reason="fast_load_drop_ramp_down_output",
                active_regulation_state="discharge_active",
                active_hold_remaining_s=float(
                    self.config.post_load_drop_hold_s
                ),
                cooldown_remaining_s=0.0,
                metadata={
                    **metadata,
                    "pv_handover_policy": pv_handover_policy,
                    "last_output_limit_w": last_output_w,
                    "current_export_active": current_export_active,
                },
            )

        return None

    def _evaluate_active_min_hold(
        self,
        *,
        now_utc: datetime,
        intent: StrategyIntent,
        grid: GridHistoryState,
        runtime: RegulationRuntimeState,
        metadata: dict[str, Any],
    ) -> ModeArbiterResult | None:
        """Keep active regulation states alive for their minimum hold time."""

        requested_mode = intent.requested_mode

        if runtime.active_regulation_state == "pv_charge_active":
            strategic_pv_latch = intent.metadata.get("pv_charge_latched")

            # Issue #207:
            # The strategic source check is authoritative. Once it has released
            # the PV latch, the technical minimum hold must not keep INPUT alive.
            if strategic_pv_latch is False:
                return None

            stable_import_cycles = int(grid.stable_import_cycles or 0)
            exit_import_cycles = max(
                1,
                int(self.config.pv_charge_exit_import_cycles),
            )

            # Do not let the minimum hold override a real PV-charge exit.
            # The status may be kept briefly during marginal conditions, but
            # once import is stable enough, the PV charge latch must be allowed
            # to end even if the minimum hold time is still running.
            if stable_import_cycles >= exit_import_cycles:
                return None

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
                        "stable_import_cycles": stable_import_cycles,
                        "pv_charge_exit_import_cycles": exit_import_cycles,
                    },
                )

        if runtime.active_regulation_state == "discharge_active":
            remaining_s = self._latch_remaining_s(
                now_utc=now_utc,
                started_ts=runtime.discharge_latch_started_ts,
                hold_s=self.config.discharge_latch_min_hold_s,
            )

            if remaining_s > 0.0 and requested_mode != "output":
                pv_handover_policy = str(
                    getattr(
                        intent,
                        "pv_handover_policy",
                        "default",
                    )
                    or "default"
                )

                load_coverage_priority = bool(
                    getattr(
                        intent,
                        "load_coverage_priority",
                        False,
                    )
                )

                last_output_w = max(
                    0.0,
                    float(runtime.last_output_limit_w or 0.0),
                )

                current_export_active = (
                    float(grid.grid_now_w or 0.0) < 0.0
                )

                stable_export_cycles = int(
                    grid.stable_export_cycles or 0
                )

                required_export_cycles = max(
                    1,
                    int(
                        self.config.stable_export_cycles_for_pv_charge
                    ),
                )

                hardware_export_requirement_met = bool(
                    not self.config.requires_stable_export_for_input
                    or stable_export_cycles >= required_export_cycles
                )

                fast_pv_handover_ready = bool(
                    requested_mode == "input"
                    and intent.intent == "pv_charge"
                    and pv_handover_policy == "fast"
                    and not load_coverage_priority
                    and last_output_w <= 0.0
                    and current_export_active
                    and hardware_export_requirement_met
                )

                # Automatic fast PV handover:
                # A historical discharge latch must not keep OUTPUT alive after the
                # actual output command has already reached zero.
                if fast_pv_handover_ready:
                    return None

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
                        "discharge_hold_remaining_s": round(
                            remaining_s,
                            1,
                        ),
                        "pv_handover_policy": pv_handover_policy,
                        "last_output_limit_w": last_output_w,
                        "current_export_active": current_export_active,
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
            last_output_w = max(
                0.0,
                float(runtime.last_output_limit_w or 0.0),
            )

            # Issue #207:
            # Export observed while OUTPUT is still commanded cannot authorize
            # INPUT. First ramp the output command to zero; a later cycle must
            # confirm that the export remains before PV charging may start.
            if last_output_w > 0.0:
                return ModeArbiterResult(
                    requested_mode="input",
                    resolved_mode="ramp_down_output",
                    allowed=True,
                    reason="pv_charge_wait_output_zero",
                    active_regulation_state="discharge_active",
                    active_hold_remaining_s=0.0,
                    cooldown_remaining_s=0.0,
                    metadata={
                        **metadata,
                        "last_output_limit_w": last_output_w,
                    },
                )

            exit_import_cycles = max(
                1,
                int(self.config.pv_charge_exit_import_cycles),
            )

            # Keep an already active PV charge alive until import is stable
            # enough to really exit. Stable export is required for starting PV
            # charge, not for keeping an already active PV charge alive.
            if runtime.active_regulation_state == "pv_charge_active":
                stable_import_cycles = int(grid.stable_import_cycles or 0)

                if stable_import_cycles < exit_import_cycles:
                    return ModeArbiterResult(
                        requested_mode="input",
                        resolved_mode="input",
                        allowed=True,
                        reason="pv_charge_latch_keep_active",
                        active_regulation_state="pv_charge_active",
                        active_hold_remaining_s=0.0,
                        cooldown_remaining_s=0.0,
                        metadata={
                            **metadata,
                            "stable_import_cycles": stable_import_cycles,
                            "pv_charge_exit_import_cycles": exit_import_cycles,
                        },
                    )

                return ModeArbiterResult(
                    requested_mode="input",
                    resolved_mode="idle",
                    allowed=False,
                    reason="pv_charge_latch_exit_import_stable",
                    active_regulation_state="neutral_hold",
                    active_hold_remaining_s=0.0,
                    cooldown_remaining_s=0.0,
                    metadata={
                        **metadata,
                        "stable_import_cycles": stable_import_cycles,
                        "pv_charge_exit_import_cycles": exit_import_cycles,
                    },
                )

            # V4.3.0-dev5.7:
            # PV handover policy is defined by the strategic layer.
            #
            # fast:
            #   Automatic mode has already confirmed real PV surplus through
            #   its strategic hysteresis. Do not repeat the same stable-export
            #   confirmation in the technical layer.
            #
            # stable:
            #   Autarky mode keeps an additional technical export confirmation
            #   so changing clouds do not cause rapid INPUT/OUTPUT switching.
            #
            # default:
            #   Conservative compatibility behavior.
            pv_handover_policy = str(
                getattr(
                    intent,
                    "pv_handover_policy",
                    "default",
                )
                or "default"
            )

            load_coverage_priority = bool(
                getattr(
                    intent,
                    "load_coverage_priority",
                    False,
                )
            )

            current_export_active = (
                float(grid.grid_now_w or 0.0) < 0.0
            )

            stable_export_cycles = int(
                grid.stable_export_cycles or 0
            )

            required_export_cycles = max(
                1,
                int(
                    self.config.stable_export_cycles_for_pv_charge
                ),
            )

            # A new PV charge must still be based on a real current export.
            # Historical export counters alone are not sufficient.
            if not current_export_active:
                return ModeArbiterResult(
                    requested_mode="input",
                    resolved_mode="hold",
                    allowed=False,
                    reason="pv_charge_wait_current_export",
                    active_regulation_state=runtime.active_regulation_state,
                    active_hold_remaining_s=0.0,
                    cooldown_remaining_s=0.0,
                    metadata={
                        **metadata,
                        "pv_handover_policy": pv_handover_policy,
                        "load_coverage_priority": load_coverage_priority,
                        "grid_now_w": float(grid.grid_now_w or 0.0),
                        "last_output_limit_w": last_output_w,
                        "stable_export_cycles": stable_export_cycles,
                        "required_export_cycles": required_export_cycles,
                    },
                )

            # Fast Automatic handover:
            # The strategic PV latch already confirmed the surplus. Once real
            # export is still present, do not wait for another historical
            # stable-export confirmation.
            if (
                pv_handover_policy == "fast"
                and not load_coverage_priority
            ):
                return ModeArbiterResult(
                    requested_mode="input",
                    resolved_mode="input",
                    allowed=True,
                    reason="pv_charge_fast_handover",
                    active_regulation_state="pv_charge_active",
                    active_hold_remaining_s=0.0,
                    cooldown_remaining_s=0.0,
                    metadata={
                        **metadata,
                        "pv_handover_policy": pv_handover_policy,
                        "load_coverage_priority": load_coverage_priority,
                        "grid_now_w": float(grid.grid_now_w or 0.0),
                        "last_output_limit_w": last_output_w,
                        "stable_export_cycles": stable_export_cycles,
                        "required_export_cycles": required_export_cycles,
                    },
                )

            # Stable/default handover:
            # Keep an additional technical export confirmation. This is used by
            # Autarky mode and remains the conservative compatibility path.
            if stable_export_cycles < required_export_cycles:
                return ModeArbiterResult(
                    requested_mode="input",
                    resolved_mode="hold",
                    allowed=False,
                    reason="pv_charge_wait_stable_export",
                    active_regulation_state=runtime.active_regulation_state,
                    active_hold_remaining_s=0.0,
                    cooldown_remaining_s=0.0,
                    metadata={
                        **metadata,
                        "pv_handover_policy": pv_handover_policy,
                        "load_coverage_priority": load_coverage_priority,
                        "grid_now_w": float(grid.grid_now_w or 0.0),
                        "last_output_limit_w": last_output_w,
                        "stable_export_cycles": stable_export_cycles,
                        "required_export_cycles": required_export_cycles,
                    },
                )

            return ModeArbiterResult(
                requested_mode="input",
                resolved_mode="input",
                allowed=True,
                reason="pv_charge_stable_handover",
                active_regulation_state="pv_charge_active",
                active_hold_remaining_s=0.0,
                cooldown_remaining_s=0.0,
                metadata={
                    **metadata,
                    "pv_handover_policy": pv_handover_policy,
                    "load_coverage_priority": load_coverage_priority,
                    "grid_now_w": float(grid.grid_now_w or 0.0),
                    "last_output_limit_w": last_output_w,
                    "stable_export_cycles": stable_export_cycles,
                    "required_export_cycles": required_export_cycles,
                },
            )

        # Some devices should not enter INPUT without stable export unless it is
        # a planned/grid charge.
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

    def _state_for_intent(self, intent: str) -> str:
        if intent == "pv_charge":
            return "pv_charge_active"

        if intent == "passthrough":
            return "passthrough_active"

        if intent in (
            "cover_deficit",
            "peak_discharge",
            "arbitrage_discharge",
            "manual_discharge",
            "manual_constant_discharge",
        ):
            return "discharge_active"

        if intent in (
            "planned_charge",
            "manual_charge",
            "emergency_charge",
        ):
            return "input_active"

        return "none"
