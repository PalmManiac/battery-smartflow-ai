from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .regulation_models import (
    GridHistoryState,
    ModeArbiterResult,
    PowerControllerResult,
    StrategyIntent,
)


DEFAULT_TARGET_IMPORT_W = 10.0
DEFAULT_EXPORT_GUARD_W = 80.0

DEFAULT_DISCHARGE_DEADBAND_W = 30.0
DEFAULT_DISCHARGE_KP_UP = 0.65
DEFAULT_DISCHARGE_KP_DOWN = 0.90
DEFAULT_DISCHARGE_MAX_STEP_UP = 550.0
DEFAULT_DISCHARGE_MAX_STEP_DOWN = 800.0

DEFAULT_CHARGE_DEADBAND_W = 30.0
DEFAULT_CHARGE_KP_UP = 0.65
DEFAULT_CHARGE_KP_DOWN = 0.90
DEFAULT_CHARGE_MAX_STEP_UP = 550.0
DEFAULT_CHARGE_MAX_STEP_DOWN = 800.0

DEFAULT_KEEPALIVE_MIN_OUTPUT_W = 60.0
DEFAULT_DISCHARGE_EXIT_EXPORT_CYCLES = 3


@dataclass
class RegulationPowerConfig:
    target_import_w: float = DEFAULT_TARGET_IMPORT_W
    export_guard_w: float = DEFAULT_EXPORT_GUARD_W
    keepalive_min_output_w: float = DEFAULT_KEEPALIVE_MIN_OUTPUT_W
    discharge_exit_export_cycles: int = DEFAULT_DISCHARGE_EXIT_EXPORT_CYCLES

    discharge_deadband_w: float = DEFAULT_DISCHARGE_DEADBAND_W
    discharge_kp_up: float = DEFAULT_DISCHARGE_KP_UP
    discharge_kp_down: float = DEFAULT_DISCHARGE_KP_DOWN
    discharge_max_step_up: float = DEFAULT_DISCHARGE_MAX_STEP_UP
    discharge_max_step_down: float = DEFAULT_DISCHARGE_MAX_STEP_DOWN

    charge_deadband_w: float = DEFAULT_CHARGE_DEADBAND_W
    charge_kp_up: float = DEFAULT_CHARGE_KP_UP
    charge_kp_down: float = DEFAULT_CHARGE_KP_DOWN
    charge_max_step_up: float = DEFAULT_CHARGE_MAX_STEP_UP
    charge_max_step_down: float = DEFAULT_CHARGE_MAX_STEP_DOWN

    max_input_w: float = 2400.0
    max_output_w: float = 2400.0


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


def build_regulation_power_config(profile: dict[str, Any]) -> RegulationPowerConfig:
    """Build technical power-controller config from device profile."""

    return RegulationPowerConfig(
        target_import_w=_profile_float(
            profile,
            "TARGET_IMPORT_W",
            DEFAULT_TARGET_IMPORT_W,
        ),
        export_guard_w=_profile_float(
            profile,
            "EXPORT_GUARD_W",
            DEFAULT_EXPORT_GUARD_W,
        ),
        keepalive_min_output_w=_profile_float(
            profile,
            "KEEPALIVE_MIN_OUTPUT_W",
            DEFAULT_KEEPALIVE_MIN_OUTPUT_W,
        ),
        discharge_exit_export_cycles=_profile_int(
            profile,
            "DISCHARGE_EXIT_EXPORT_CYCLES",
            DEFAULT_DISCHARGE_EXIT_EXPORT_CYCLES,
        ),
        discharge_deadband_w=_profile_float(
            profile,
            "DISCHARGE_DEADBAND_W",
            _profile_float(profile, "DEADBAND_W", DEFAULT_DISCHARGE_DEADBAND_W),
        ),
        discharge_kp_up=_profile_float(
            profile,
            "DISCHARGE_KP_UP",
            _profile_float(profile, "KP_UP", DEFAULT_DISCHARGE_KP_UP),
        ),
        discharge_kp_down=_profile_float(
            profile,
            "DISCHARGE_KP_DOWN",
            _profile_float(profile, "KP_DOWN", DEFAULT_DISCHARGE_KP_DOWN),
        ),
        discharge_max_step_up=_profile_float(
            profile,
            "DISCHARGE_MAX_STEP_UP",
            _profile_float(profile, "MAX_STEP_UP", DEFAULT_DISCHARGE_MAX_STEP_UP),
        ),
        discharge_max_step_down=_profile_float(
            profile,
            "DISCHARGE_MAX_STEP_DOWN",
            _profile_float(profile, "MAX_STEP_DOWN", DEFAULT_DISCHARGE_MAX_STEP_DOWN),
        ),
        charge_deadband_w=_profile_float(
            profile,
            "CHARGE_DEADBAND_W",
            _profile_float(profile, "DEADBAND_W", DEFAULT_CHARGE_DEADBAND_W),
        ),
        charge_kp_up=_profile_float(
            profile,
            "CHARGE_KP_UP",
            _profile_float(profile, "KP_UP", DEFAULT_CHARGE_KP_UP),
        ),
        charge_kp_down=_profile_float(
            profile,
            "CHARGE_KP_DOWN",
            _profile_float(profile, "KP_DOWN", DEFAULT_CHARGE_KP_DOWN),
        ),
        charge_max_step_up=_profile_float(
            profile,
            "CHARGE_MAX_STEP_UP",
            _profile_float(profile, "MAX_STEP_UP", DEFAULT_CHARGE_MAX_STEP_UP),
        ),
        charge_max_step_down=_profile_float(
            profile,
            "CHARGE_MAX_STEP_DOWN",
            _profile_float(profile, "MAX_STEP_DOWN", DEFAULT_CHARGE_MAX_STEP_DOWN),
        ),
        max_input_w=_profile_float(profile, "MAX_INPUT_W", 2400.0),
        max_output_w=_profile_float(profile, "MAX_OUTPUT_W", 2400.0),
    )


class RegulationPowerController:
    """Technical power calculation for the V4.2.0 regulation chain.

    This controller does not decide strategy and does not decide whether a mode
    may switch. It only calculates the concrete power for an already resolved
    technical mode.
    """

    def __init__(self, config: RegulationPowerConfig | None = None) -> None:
        self.config = config or RegulationPowerConfig()

    def calculate(
        self,
        *,
        intent: StrategyIntent,
        arbiter: ModeArbiterResult,
        grid: GridHistoryState,
        previous_input_w: float = 0.0,
        previous_output_w: float = 0.0,
    ) -> PowerControllerResult:
        if not arbiter.allowed:
            return PowerControllerResult(
                raw_target_w=0.0,
                limited_target_w=0.0,
                applied_step_w=0.0,
                final_power_w=0.0,
                profile_limited=False,
                step_limited=False,
                reason=f"blocked_by_arbiter_{arbiter.reason}",
                metadata={
                    "resolved_mode": arbiter.resolved_mode,
                    "intent": intent.intent,
                },
            )

        if arbiter.resolved_mode == "idle":
            return self._idle_result(intent=intent, arbiter=arbiter)

        if arbiter.resolved_mode == "hold":
            return PowerControllerResult(
                raw_target_w=0.0,
                limited_target_w=0.0,
                applied_step_w=0.0,
                final_power_w=0.0,
                profile_limited=False,
                step_limited=False,
                reason="hold_no_power_change",
                metadata={
                    "resolved_mode": arbiter.resolved_mode,
                    "intent": intent.intent,
                },
            )

        if arbiter.resolved_mode == "ramp_down_output":
            return self._ramp_down_output(
                intent=intent,
                arbiter=arbiter,
                previous_output_w=previous_output_w,
            )

        if arbiter.resolved_mode == "ramp_down_input":
            return self._ramp_down_input(
                intent=intent,
                arbiter=arbiter,
                previous_input_w=previous_input_w,
            )

        if arbiter.resolved_mode == "output":
            return self._calculate_output(
                intent=intent,
                arbiter=arbiter,
                grid=grid,
                previous_output_w=previous_output_w,
            )

        if arbiter.resolved_mode == "input":
            return self._calculate_input(
                intent=intent,
                arbiter=arbiter,
                grid=grid,
                previous_input_w=previous_input_w,
            )

        return self._idle_result(intent=intent, arbiter=arbiter)

    def _control_grid_w(self, grid: GridHistoryState) -> float:
        """Weighted grid value for fast but smooth regulation.

        V4.2.0:
        - fast load changes react mostly to the current grid value
        - calm near-target operation uses more averaging
        - normal operation stays balanced
        """

        grid_now_w = float(grid.grid_now_w or 0.0)
        grid_avg_short_w = float(grid.grid_avg_short_w or 0.0)
        grid_avg_medium_w = float(grid.grid_avg_medium_w or 0.0)

        if bool(grid.fast_load_rise_detected) or bool(grid.fast_load_drop_detected):
            # ZHA-inspired fast reaction path:
            # On large load changes, the current P1/grid value must dominate.
            return (grid_now_w * 0.85) + (grid_avg_short_w * 0.15)

        if int(grid.near_target_cycles or 0) >= 2:
            # Calm near-target path:
            # Avoid nervous corrections around the target import value.
            return (
                (grid_now_w * 0.50)
                + (grid_avg_short_w * 0.30)
                + (grid_avg_medium_w * 0.20)
            )

        # Normal path:
        # Slightly more direct than before, but still smoothed.
        return (grid_now_w * 0.65) + (grid_avg_short_w * 0.35)

    def _discharge_keepalive_w(self) -> float:
        """Minimum output while a discharge intent is active."""

        return max(
            0.0,
            min(
                float(self.config.max_output_w),
                float(self.config.keepalive_min_output_w),
            ),
        )

    def _calculate_output(
        self,
        *,
        intent: StrategyIntent,
        arbiter: ModeArbiterResult,
        grid: GridHistoryState,
        previous_output_w: float,
    ) -> PowerControllerResult:
        prev = max(0.0, float(previous_output_w or 0.0))
        control_grid_w = self._control_grid_w(grid)

        if intent.intent == "manual_constant_discharge":
            raw_target = (
                float(intent.requested_power_w)
                if intent.requested_power_w is not None
                else float(self.config.max_output_w)
            )
            return self._limit_output_step(
                raw_target_w=raw_target,
                previous_output_w=prev,
                reason="manual_constant_output_step_limited",
                metadata={
                    "intent": intent.intent,
                    "resolved_mode": arbiter.resolved_mode,
                    "control_grid_w": round(control_grid_w, 2),
                },
            )

        if intent.intent == "passthrough":
            raw_target = (
                float(intent.requested_power_w)
                if intent.requested_power_w is not None
                else 0.0
            )
            return self._limit_output_step(
                raw_target_w=raw_target,
                previous_output_w=prev,
                reason="passthrough_output_step_limited",
                metadata={
                    "intent": intent.intent,
                    "resolved_mode": arbiter.resolved_mode,
                    "control_grid_w": round(control_grid_w, 2),
                },
            )

        requested = (
            float(intent.requested_power_w)
            if intent.requested_power_w is not None
            else 0.0
        )

        error_w = control_grid_w - float(self.config.target_import_w)

        if abs(error_w) <= float(self.config.discharge_deadband_w):
            raw_target = prev
            reason = "output_inside_deadband"
        elif error_w > 0.0:
            delta = error_w * float(self.config.discharge_kp_up)

            if bool(grid.fast_load_rise_detected):
                # Large new load: react faster, but still respect step limits later.
                delta *= 1.25
                reason = "output_fast_increase_to_reduce_import"
            else:
                reason = "output_increase_to_reduce_import"

            raw_target = prev + delta

        else:
            # Export / too much output.
            delta = abs(error_w) * float(self.config.discharge_kp_down)

            if bool(grid.fast_load_drop_detected):
                # Load dropped: reduce faster, but do not switch mode here.
                # ModeArbiter keeps OUTPUT stable and the step limiter prevents a hard jump.
                delta *= 1.15
                reason = "output_fast_decrease_to_avoid_export"
            else:
                reason = "output_decrease_to_avoid_export"

            raw_target = prev - delta

        # For strategic discharge decisions, never exceed the strategy request.
        if requested > 0.0:
            raw_target = min(raw_target, requested)

        # Keep economic/automatic discharge alive while the strategy still requests
        # OUTPUT. Without this, small target overshoots can collapse output to 0 W
        # and cause a discharge/idle sawtooth.
        if (
            intent.intent
            in (
                "cover_deficit",
                "peak_discharge",
                "arbitrage_discharge",
                "manual_discharge",
            )
            and arbiter.resolved_mode == "output"
            and arbiter.allowed
        ):
            keepalive_w = self._discharge_keepalive_w()

            exit_export_cycles = max(
                1,
                int(self.config.discharge_exit_export_cycles),
            )

            # Keep discharge alive until export is stable enough to really exit.
            # A single short export cycle must not collapse the output to 0 W.
            if grid.stable_export_cycles < exit_export_cycles and raw_target <= keepalive_w:
                raw_target = keepalive_w
                reason = f"{reason}_discharge_keepalive"

        return self._limit_output_step(
            raw_target_w=raw_target,
            previous_output_w=prev,
            reason=reason,
            metadata={
                "intent": intent.intent,
                "resolved_mode": arbiter.resolved_mode,
                "control_grid_w": round(control_grid_w, 2),
                "requested_power_w": requested,
                "error_w": round(error_w, 2),
            },
        )

    def _calculate_input(
        self,
        *,
        intent: StrategyIntent,
        arbiter: ModeArbiterResult,
        grid: GridHistoryState,
        previous_input_w: float,
    ) -> PowerControllerResult:
        prev = max(0.0, float(previous_input_w or 0.0))
        control_grid_w = self._control_grid_w(grid)

        if intent.intent == "pv_charge":
            # PV charge is a delta controller:
            # The current grid value is measured AFTER the current battery charge.
            # Therefore remaining export must increase the existing input limit,
            # while real import must reduce it.
            target_import_w = float(self.config.target_import_w)
            error_w = target_import_w - float(control_grid_w)

            if abs(error_w) <= float(self.config.charge_deadband_w):
                raw_target = prev
                reason = "pv_input_inside_deadband"

            elif error_w > 0.0:
                # Export / below target import:
                # increase charging, but keep step limits active later.
                delta = error_w * float(self.config.charge_kp_up)

                if bool(grid.fast_load_drop_detected):
                    delta *= 1.15
                    reason = "pv_input_fast_increase_from_export"
                else:
                    reason = "pv_input_increase_from_export"

                raw_target = prev + delta

            else:
                # Import / too much charging:
                # reduce charging, but do not switch mode here.
                delta = abs(error_w) * float(self.config.charge_kp_down)

                if bool(grid.fast_load_rise_detected):
                    delta *= 1.25
                    reason = "pv_input_fast_decrease_to_avoid_import"
                else:
                    reason = "pv_input_decrease_to_avoid_import"

                raw_target = prev - delta

            return self._limit_input_step(
                raw_target_w=raw_target,
                previous_input_w=prev,
                reason=reason,
                metadata={
                    "intent": intent.intent,
                    "resolved_mode": arbiter.resolved_mode,
                    "control_grid_w": round(control_grid_w, 2),
                    "target_import_w": round(target_import_w, 2),
                    "requested_power_w": None,
                    "error_w": round(error_w, 2),
                    "previous_input_w": round(prev, 2),
                },
            )

        # Planned/manual/emergency charging uses the strategy request.
        raw_target = (
            float(intent.requested_power_w)
            if intent.requested_power_w is not None
            else 0.0
        )

        return self._limit_input_step(
            raw_target_w=raw_target,
            previous_input_w=prev,
            reason=f"{intent.intent}_input_requested_power",
            metadata={
                "intent": intent.intent,
                "resolved_mode": arbiter.resolved_mode,
                "control_grid_w": round(control_grid_w, 2),
                "requested_power_w": raw_target,
            },
        )

    def _ramp_down_output(
        self,
        *,
        intent: StrategyIntent,
        arbiter: ModeArbiterResult,
        previous_output_w: float,
    ) -> PowerControllerResult:
        prev = max(0.0, float(previous_output_w or 0.0))
        raw_target = 0.0

        return self._limit_output_step(
            raw_target_w=raw_target,
            previous_output_w=prev,
            reason="ramp_down_output_step_limited",
            metadata={
                "intent": intent.intent,
                "resolved_mode": arbiter.resolved_mode,
            },
        )

    def _ramp_down_input(
        self,
        *,
        intent: StrategyIntent,
        arbiter: ModeArbiterResult,
        previous_input_w: float,
    ) -> PowerControllerResult:
        prev = max(0.0, float(previous_input_w or 0.0))
        raw_target = 0.0

        return self._limit_input_step(
            raw_target_w=raw_target,
            previous_input_w=prev,
            reason="ramp_down_input_step_limited",
            metadata={
                "intent": intent.intent,
                "resolved_mode": arbiter.resolved_mode,
            },
        )

    def _idle_result(
        self,
        *,
        intent: StrategyIntent,
        arbiter: ModeArbiterResult,
    ) -> PowerControllerResult:
        return PowerControllerResult(
            raw_target_w=0.0,
            limited_target_w=0.0,
            applied_step_w=0.0,
            final_power_w=0.0,
            profile_limited=False,
            step_limited=False,
            reason="idle_zero_power",
            metadata={
                "intent": intent.intent,
                "resolved_mode": arbiter.resolved_mode,
            },
        )

    def _limit_output_step(
        self,
        *,
        raw_target_w: float,
        previous_output_w: float,
        reason: str,
        metadata: dict[str, Any],
    ) -> PowerControllerResult:
        prev = max(0.0, float(previous_output_w or 0.0))
        raw = max(0.0, float(raw_target_w or 0.0))

        profile_limited_target = min(raw, float(self.config.max_output_w))
        profile_limited = profile_limited_target != raw

        if profile_limited_target > prev:
            allowed_delta = min(
                profile_limited_target - prev,
                float(self.config.discharge_max_step_up),
            )
            final = prev + allowed_delta
        else:
            allowed_delta = -min(
                prev - profile_limited_target,
                float(self.config.discharge_max_step_down),
            )
            final = prev + allowed_delta

        final = max(0.0, min(final, float(self.config.max_output_w)))

        step_limited = abs(final - profile_limited_target) > 0.01
        applied_step = final - prev

        return PowerControllerResult(
            raw_target_w=round(raw, 2),
            limited_target_w=round(profile_limited_target, 2),
            applied_step_w=round(applied_step, 2),
            final_power_w=round(final, 2),
            profile_limited=bool(profile_limited),
            step_limited=bool(step_limited),
            reason=reason,
            metadata=metadata,
        )

    def _limit_input_step(
        self,
        *,
        raw_target_w: float,
        previous_input_w: float,
        reason: str,
        metadata: dict[str, Any],
    ) -> PowerControllerResult:
        prev = max(0.0, float(previous_input_w or 0.0))
        raw = max(0.0, float(raw_target_w or 0.0))

        profile_limited_target = min(raw, float(self.config.max_input_w))
        profile_limited = profile_limited_target != raw

        if profile_limited_target > prev:
            allowed_delta = min(
                profile_limited_target - prev,
                float(self.config.charge_max_step_up),
            )
            final = prev + allowed_delta
        else:
            allowed_delta = -min(
                prev - profile_limited_target,
                float(self.config.charge_max_step_down),
            )
            final = prev + allowed_delta

        final = max(0.0, min(final, float(self.config.max_input_w)))

        step_limited = abs(final - profile_limited_target) > 0.01
        applied_step = final - prev

        return PowerControllerResult(
            raw_target_w=round(raw, 2),
            limited_target_w=round(profile_limited_target, 2),
            applied_step_w=round(applied_step, 2),
            final_power_w=round(final, 2),
            profile_limited=bool(profile_limited),
            step_limited=bool(step_limited),
            reason=reason,
            metadata=metadata,
        )
