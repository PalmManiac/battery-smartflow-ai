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
DEFAULT_DISCHARGE_TARGET_IMPORT_W = 10.0
DEFAULT_EXPORT_GUARD_W = 80.0

DEFAULT_DISCHARGE_DEADBAND_W = 30.0
DEFAULT_DISCHARGE_KP_UP = 0.65
DEFAULT_DISCHARGE_KP_DOWN = 0.90
DEFAULT_DISCHARGE_MAX_STEP_UP = 550.0
DEFAULT_DISCHARGE_MAX_STEP_DOWN = 800.0

# V4.3.0-dev3:
# Active OUTPUT near-zero trim.
#
# These values are intentionally central defaults, not per-device profile
# micro-tuning. Device profiles may override them later, but dev3 should first
# prove that a common adaptive near-zero trim improves load coverage.
DEFAULT_DISCHARGE_NEAR_ZERO_DEADBAND_W = 12.0
DEFAULT_DISCHARGE_NEAR_ZERO_MIN_IMPORT_W = 25.0
DEFAULT_DISCHARGE_NEAR_ZERO_TRIM_STEP_W = 20.0
DEFAULT_DISCHARGE_NEAR_ZERO_MAX_TRIM_W = 80.0

# V4.3.0-dev3.1:
# Economically weighted grid targets.
#
# A small export is preferable to small import when export has a monetary
# value or when stored battery energy is cheaper than the feed-in tariff.
DEFAULT_ECONOMIC_EXPORT_TARGET_W = -15.0
DEFAULT_ECONOMIC_EXPORT_MARGIN_EUR_KWH = 0.01

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
    discharge_target_import_w: float = DEFAULT_DISCHARGE_TARGET_IMPORT_W
    export_guard_w: float = DEFAULT_EXPORT_GUARD_W
    keepalive_min_output_w: float = DEFAULT_KEEPALIVE_MIN_OUTPUT_W
    discharge_exit_export_cycles: int = DEFAULT_DISCHARGE_EXIT_EXPORT_CYCLES

    discharge_deadband_w: float = DEFAULT_DISCHARGE_DEADBAND_W
    discharge_kp_up: float = DEFAULT_DISCHARGE_KP_UP
    discharge_kp_down: float = DEFAULT_DISCHARGE_KP_DOWN
    discharge_max_step_up: float = DEFAULT_DISCHARGE_MAX_STEP_UP
    discharge_max_step_down: float = DEFAULT_DISCHARGE_MAX_STEP_DOWN
    
    discharge_near_zero_deadband_w: float = DEFAULT_DISCHARGE_NEAR_ZERO_DEADBAND_W
    discharge_near_zero_min_import_w: float = DEFAULT_DISCHARGE_NEAR_ZERO_MIN_IMPORT_W
    discharge_near_zero_trim_step_w: float = DEFAULT_DISCHARGE_NEAR_ZERO_TRIM_STEP_W
    discharge_near_zero_max_trim_w: float = DEFAULT_DISCHARGE_NEAR_ZERO_MAX_TRIM_W
    
    economic_export_target_w: float = DEFAULT_ECONOMIC_EXPORT_TARGET_W
    economic_export_margin_eur_kwh: float = (
        DEFAULT_ECONOMIC_EXPORT_MARGIN_EUR_KWH
    )

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
        discharge_target_import_w=_profile_float(
            profile,
            "DISCHARGE_TARGET_IMPORT_W",
            _profile_float(profile, "TARGET_IMPORT_W", DEFAULT_TARGET_IMPORT_W),
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
        discharge_near_zero_deadband_w=_profile_float(
            profile,
            "DISCHARGE_NEAR_ZERO_DEADBAND_W",
            DEFAULT_DISCHARGE_NEAR_ZERO_DEADBAND_W,
        ),
        discharge_near_zero_min_import_w=_profile_float(
            profile,
            "DISCHARGE_NEAR_ZERO_MIN_IMPORT_W",
            DEFAULT_DISCHARGE_NEAR_ZERO_MIN_IMPORT_W,
        ),
        discharge_near_zero_trim_step_w=_profile_float(
            profile,
            "DISCHARGE_NEAR_ZERO_TRIM_STEP_W",
            DEFAULT_DISCHARGE_NEAR_ZERO_TRIM_STEP_W,
        ),
        discharge_near_zero_max_trim_w=_profile_float(
            profile,
            "DISCHARGE_NEAR_ZERO_MAX_TRIM_W",
            DEFAULT_DISCHARGE_NEAR_ZERO_MAX_TRIM_W,
        ),
        economic_export_target_w=_profile_float(
            profile,
            "ECONOMIC_EXPORT_TARGET_W",
            DEFAULT_ECONOMIC_EXPORT_TARGET_W,
        ),
        economic_export_margin_eur_kwh=_profile_float(
            profile,
            "ECONOMIC_EXPORT_MARGIN_EUR_KWH",
            DEFAULT_ECONOMIC_EXPORT_MARGIN_EUR_KWH,
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
        
    def _control_grid_w_for_output(self, grid: GridHistoryState) -> float:
        """Weighted grid value for discharge/output regulation.

        OUTPUT must stay calm near the target, but real momentary import or
        export should dominate faster than the generic smoothed value.
        """

        base_control_w = self._control_grid_w(grid)

        grid_now_w = float(grid.grid_now_w or 0.0)
        grid_avg_short_w = float(grid.grid_avg_short_w or 0.0)

        target_import_w = float(self.config.discharge_target_import_w)
        deadband_w = float(self.config.discharge_deadband_w)
        export_guard_w = float(self.config.export_guard_w)

        # Fast import correction:
        # If the real current grid value is clearly importing, react mostly to
        # the current value. This prevents visible >100 W import before the
        # smoothed controller catches up.
        fast_import_threshold_w = target_import_w + max(60.0, deadband_w * 2.0)
        if grid_now_w > fast_import_threshold_w:
            return (grid_now_w * 0.85) + (grid_avg_short_w * 0.15)

        # Fast export correction:
        # If the real current value is clearly exporting, reduce output faster.
        # This still remains step-limited later and therefore avoids hard 0 W
        # collapses.
        fast_export_threshold_w = -max(60.0, export_guard_w * 0.75)
        if grid_now_w < fast_export_threshold_w:
            return (grid_now_w * 0.85) + (grid_avg_short_w * 0.15)

        return base_control_w
        
    def _control_grid_w_for_input(self, grid: GridHistoryState) -> float:
        """Weighted grid value for charge/input regulation.

        INPUT should use smoothing near the target, increase charging carefully
        on export, but reduce charging quickly on real import.
        """

        base_control_w = self._control_grid_w(grid)

        grid_now_w = float(grid.grid_now_w or 0.0)
        grid_avg_short_w = float(grid.grid_avg_short_w or 0.0)

        target_import_w = float(self.config.target_import_w)
        deadband_w = float(self.config.charge_deadband_w)

        # Fast import protection:
        # If charging causes real import, react quickly and reduce input.
        fast_import_threshold_w = target_import_w + max(50.0, deadband_w * 1.5)
        if grid_now_w > fast_import_threshold_w:
            return (grid_now_w * 0.90) + (grid_avg_short_w * 0.10)

        # Moderate export pickup:
        # If there is clear real export, increase charging a bit faster,
        # but less aggressively than import reduction.
        fast_export_threshold_w = -max(80.0, deadband_w * 2.5)
        if grid_now_w < fast_export_threshold_w:
            return (grid_now_w * 0.75) + (grid_avg_short_w * 0.25)

        return base_control_w

    def _discharge_keepalive_w(self) -> float:
        """Minimum output while a discharge intent is active."""

        return max(
            0.0,
            min(
                float(self.config.max_output_w),
                float(self.config.keepalive_min_output_w),
            ),
        )
     
    def _intent_metadata_float(
        self,
        intent: StrategyIntent,
        key: str,
    ) -> float | None:
        """Read an optional numeric value from StrategyIntent metadata."""
        try:
            value = intent.metadata.get(key)
            if value is None:
                return None
            return float(value)
        except (TypeError, ValueError, AttributeError):
            return None


    def _effective_target_import_w(
        self,
        *,
        intent: StrategyIntent,
        base_target_import_w: float,
        direction: str,
    ) -> tuple[float, dict[str, Any]]:
        """Return an economically weighted grid target.

        Positive values mean grid import.
        Negative values mean grid export.

        V4.3.0-dev3.1:
        - PV surplus charging prefers slight export when a feed-in tariff exists.
        - Active discharge prefers slight export only when stored battery energy
          is sufficiently cheaper than the feed-in tariff.
        - Strategic AC charging is not affected.
        """
        base_target_w = float(base_target_import_w)
        export_target_w = min(
            base_target_w,
            float(self.config.economic_export_target_w),
        )
        margin_eur_kwh = max(
            0.0,
            float(self.config.economic_export_margin_eur_kwh),
        )

        feed_in_tariff = self._intent_metadata_float(
            intent,
            "feed_in_tariff_eur_kwh",
        )
        battery_value = self._intent_metadata_float(
            intent,
            "battery_value_eur_kwh",
        )

        tariff_configured = bool(
            intent.metadata.get("feed_in_tariff_configured", False)
        )

        metadata: dict[str, Any] = {
            "economic_target_active": False,
            "economic_target_reason": "base_target",
            "economic_base_target_import_w": round(base_target_w, 2),
            "economic_effective_target_import_w": round(base_target_w, 2),
            "economic_export_target_w": round(export_target_w, 2),
            "economic_feed_in_tariff_eur_kwh": feed_in_tariff,
            "economic_battery_value_eur_kwh": battery_value,
            "economic_margin_eur_kwh": round(margin_eur_kwh, 4),
        }

        if (
            not tariff_configured
            or feed_in_tariff is None
            or float(feed_in_tariff) <= 0.0
        ):
            metadata["economic_target_reason"] = "feed_in_tariff_not_configured"
            return base_target_w, metadata

        # PV surplus charging:
        # Keep a small amount of export instead of risking paid grid import.
        # This explicitly excludes planned/manual/emergency AC charging.
        if direction == "input" and intent.intent == "pv_charge":
            metadata.update(
                {
                    "economic_target_active": True,
                    "economic_target_reason": "pv_feed_in_tariff_export_bias",
                    "economic_effective_target_import_w": round(
                        export_target_w,
                        2,
                    ),
                }
            )
            return export_target_w, metadata

        # Active regulated discharge:
        # Export bias is only justified when the stored energy is clearly cheaper
        # than the feed-in tariff.
        if (
            direction == "output"
            and intent.intent
            in (
                "cover_deficit",
                "peak_discharge",
                "arbitrage_discharge",
                "manual_discharge",
            )
        ):
            if battery_value is None:
                metadata["economic_target_reason"] = "battery_value_unknown"
                return base_target_w, metadata

            economic_export_allowed = (
                float(battery_value) + margin_eur_kwh
                < float(feed_in_tariff)
            )

            if economic_export_allowed:
                metadata.update(
                    {
                        "economic_target_active": True,
                        "economic_target_reason": (
                            "battery_value_below_feed_in_tariff"
                        ),
                        "economic_effective_target_import_w": round(
                            export_target_w,
                            2,
                        ),
                    }
                )
                return export_target_w, metadata

            metadata["economic_target_reason"] = (
                "battery_value_not_below_feed_in_tariff"
            )

        return base_target_w, metadata
     
    def _near_zero_output_import_trim(
        self,
        *,
        grid: GridHistoryState,
        target_import_w: float,
        previous_output_w: float,
    ) -> tuple[float, str, dict[str, Any]]:
        """Small extra OUTPUT trim for persistent import during active discharge.

        V4.3.0-dev3:
        The normal discharge deadband is intentionally stable, but it can leave
        50-100 W import standing forever. This trim only acts while OUTPUT is
        already active and only on confirmed/persistent import.

        It does not decide strategy and it does not switch modes.
        """
        prev = max(0.0, float(previous_output_w or 0.0))

        # Do not add extra trim during the initial OUTPUT startup/keepalive range.
        # Startup remains controlled by the existing KP and step limiter.
        if prev <= self._discharge_keepalive_w():
            return 0.0, "none", {
                "near_zero_active": False,
                "near_zero_reason": "startup_or_keepalive",
            }

        grid_now_w = float(grid.grid_now_w or 0.0)
        grid_avg_short_w = float(grid.grid_avg_short_w or 0.0)
        grid_avg_medium_w = float(grid.grid_avg_medium_w or 0.0)

        near_deadband_w = max(
            5.0,
            float(self.config.discharge_near_zero_deadband_w),
        )
        min_import_w = max(
            near_deadband_w,
            float(self.config.discharge_near_zero_min_import_w),
        )
        trim_step_w = max(
            1.0,
            float(self.config.discharge_near_zero_trim_step_w),
        )
        max_trim_w = max(
            trim_step_w,
            float(self.config.discharge_near_zero_max_trim_w),
        )

        # Do not trim upward if export is already present or was just detected.
        if int(getattr(grid, "stable_export_cycles", 0) or 0) > 0:
            return 0.0, "none", {
                "near_zero_active": False,
                "near_zero_reason": "export_guard_active",
                "near_zero_target_w": round(float(target_import_w), 2),
                "near_zero_grid_now_w": round(grid_now_w, 2),
                "near_zero_grid_avg_short_w": round(grid_avg_short_w, 2),
                "near_zero_deadband_w": round(near_deadband_w, 2),
            }

        trigger_now_w = float(target_import_w) + min_import_w
        trigger_short_w = float(target_import_w) + near_deadband_w

        persistent_import = (
            grid_now_w > trigger_now_w
            and grid_avg_short_w > trigger_short_w
        )

        if not persistent_import:
            return 0.0, "none", {
                "near_zero_active": False,
                "near_zero_reason": "inside_near_zero_band",
                "near_zero_target_w": round(float(target_import_w), 2),
                "near_zero_grid_now_w": round(grid_now_w, 2),
                "near_zero_grid_avg_short_w": round(grid_avg_short_w, 2),
                "near_zero_grid_avg_medium_w": round(grid_avg_medium_w, 2),
                "near_zero_deadband_w": round(near_deadband_w, 2),
            }

        confirmed_error_w = min(
            max(0.0, grid_now_w - float(target_import_w)),
            max(0.0, grid_avg_short_w - float(target_import_w)),
        )

        # Combine a minimum trim step with a proportional part.
        # This is deliberately small and still goes through the existing
        # output step limiter afterwards.
        trim_w = min(
            max_trim_w,
            max(trim_step_w, confirmed_error_w * 0.25),
        )

        return trim_w, "near_zero_persistent_import_trim", {
            "near_zero_active": True,
            "near_zero_reason": "persistent_import",
            "near_zero_target_w": round(float(target_import_w), 2),
            "near_zero_error_w": round(confirmed_error_w, 2),
            "near_zero_grid_now_w": round(grid_now_w, 2),
            "near_zero_grid_avg_short_w": round(grid_avg_short_w, 2),
            "near_zero_grid_avg_medium_w": round(grid_avg_medium_w, 2),
            "near_zero_deadband_w": round(near_deadband_w, 2),
            "near_zero_trim_w": round(trim_w, 2),
        }

    def _calculate_output(
        self,
        *,
        intent: StrategyIntent,
        arbiter: ModeArbiterResult,
        grid: GridHistoryState,
        previous_output_w: float,
    ) -> PowerControllerResult:
        prev = max(0.0, float(previous_output_w or 0.0))

        base_target_import_w = float(
            self.config.discharge_target_import_w
        )
        target_import_w, economic_target_metadata = (
            self._effective_target_import_w(
                intent=intent,
                base_target_import_w=base_target_import_w,
                direction="output",
            )
        )

        control_grid_w = self._control_grid_w_for_output(grid)

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

        error_w = control_grid_w - target_import_w

        near_zero_trim_w = 0.0
        near_zero_reason = "none"
        near_zero_metadata: dict[str, Any] = {
            "near_zero_active": False,
            "near_zero_reason": "not_evaluated",
        }

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
            
        # V4.3.0-dev3:
        # Near-zero import trim for active OUTPUT regulation.
        #
        # This acts only while OUTPUT is already active and confirmed import remains.
        # It does not switch modes and it still passes through the existing profile and
        # step limits in _limit_output_step().
        if (
            intent.intent in (
                "cover_deficit",
                "peak_discharge",
                "arbitrage_discharge",
                "manual_discharge",
            )
            and arbiter.resolved_mode == "output"
            and arbiter.allowed
        ):
            near_zero_trim_w, near_zero_reason, near_zero_metadata = (
                self._near_zero_output_import_trim(
                    grid=grid,
                    target_import_w=target_import_w,
                    previous_output_w=prev,
                )
            )

            if near_zero_trim_w > 0.0:
                raw_target += near_zero_trim_w
                reason = f"{reason}_{near_zero_reason}"

        # For strategic discharge decisions, never exceed the strategy request.
        if requested > 0.0:
            request_margin_w = 80.0
            raw_target = min(
                raw_target,
                requested + request_margin_w,
            )

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
                "grid_now_w": round(float(grid.grid_now_w or 0.0), 2),
                "grid_avg_short_w": round(float(grid.grid_avg_short_w or 0.0), 2),
                "grid_avg_medium_w": round(float(grid.grid_avg_medium_w or 0.0), 2),
                "control_grid_w": round(control_grid_w, 2),
                "target_import_w": round(float(target_import_w), 2),
                "requested_power_w": requested,
                "error_w": round(error_w, 2),
                "near_zero_trim_w": round(float(near_zero_trim_w or 0.0), 2),
                "near_zero_controller_reason": near_zero_reason,
                **near_zero_metadata,
                **economic_target_metadata,
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

            requested = (
                float(intent.requested_power_w)
                if intent.requested_power_w is not None
                else 0.0
            )

            base_target_import_w = float(self.config.target_import_w)
        target_import_w, economic_target_metadata = (
            self._effective_target_import_w(
                intent=intent,
                base_target_import_w=base_target_import_w,
                direction="input",
            )
        )

        control_grid_w = self._control_grid_w_for_input(grid)

        if intent.intent == "pv_charge":
            # PV charge is a delta controller:
            # The current grid value is measured AFTER the current battery charge.
            # Therefore remaining export may increase the existing input limit,
            # while real import must reduce it.
            #
            # Important for cloudy/fast-changing PV:
            # The smoothed control value can still contain old export while the
            # current grid value already shows import. Therefore the final PV
            # charge target is additionally capped by the current grid value.
            grid_now_w = float(grid.grid_now_w or 0.0)
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

            # Current-grid cap:
            # Because grid_now_w is measured after the current battery input,
            # the safe target is the previous input plus the current distance
            # to the desired import target.
            #
            # Examples:
            # - grid_now_w = -200 W export, target = 10 W:
            #   safe target may increase by about 210 W.
            # - grid_now_w = +200 W import, target = 10 W:
            #   safe target must decrease by about 190 W.
            #
            # This prevents PV charging from increasing based on stale smoothed
            # export when the sun is already dropping.
            current_grid_safe_target_w = max(
                0.0,
                prev + (target_import_w - grid_now_w),
            )

            current_grid_limited = False
            max_step_down_override_w: float | None = None

            if raw_target > current_grid_safe_target_w:
                raw_target = current_grid_safe_target_w
                current_grid_limited = True
                reason = f"{reason}_current_grid_cap"

                # If current import is above the target, reducing PV charge is
                # protective and should not be delayed by the normal charge
                # step-down limit. Increasing remains step-limited normally.
                if grid_now_w > target_import_w:
                    max_step_down_override_w = max(
                        float(self.config.charge_max_step_down),
                        prev - raw_target,
                    )

            return self._limit_input_step(
                raw_target_w=raw_target,
                previous_input_w=prev,
                reason=reason,
                metadata={
                    "intent": intent.intent,
                    "resolved_mode": arbiter.resolved_mode,
                    "grid_now_w": round(float(grid.grid_now_w or 0.0), 2),
                    "grid_avg_short_w": round(float(grid.grid_avg_short_w or 0.0), 2),
                    "grid_avg_medium_w": round(float(grid.grid_avg_medium_w or 0.0), 2),
                    "control_grid_w": round(control_grid_w, 2),
                    "target_import_w": round(float(target_import_w), 2),
                    "requested_power_w": requested,
                    "error_w": round(error_w, 2),
                    "current_grid_limited": bool(current_grid_limited),
                    **economic_target_metadata,
                },
                max_step_down_override_w=max_step_down_override_w,
            )

        # Planned/manual/emergency charging uses the strategy request.
        raw_target = requested

        return self._limit_input_step(
            raw_target_w=raw_target,
            previous_input_w=prev,
            reason=f"{intent.intent}_input_requested_power",
            metadata={
                "intent": intent.intent,
                "resolved_mode": arbiter.resolved_mode,
                "control_grid_w": round(control_grid_w, 2),
                "requested_power_w": raw_target,
                **economic_target_metadata,
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
            max_step_up = float(self.config.discharge_max_step_up)

            # Softer discharge start:
            # When output starts from 0 W / keepalive range, do not jump directly to a
            # high target. This prevents startup spikes while normal running regulation
            # can still use the profile step limit.
            if reason.startswith("output_") and prev <= self._discharge_keepalive_w():
                max_step_up = min(max_step_up, 300.0)

            allowed_delta = min(
                profile_limited_target - prev,
                max_step_up,
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
        max_step_down_override_w: float | None = None,
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
            max_step_down = (
                float(max_step_down_override_w)
                if max_step_down_override_w is not None
                else float(self.config.charge_max_step_down)
            )

            allowed_delta = -min(
                prev - profile_limited_target,
                max(0.0, max_step_down),
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
            metadata={
                **metadata,
                "max_step_down_override_w": (
                    round(float(max_step_down_override_w), 2)
                    if max_step_down_override_w is not None
                    else None
                ),
            },
        )
