from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .regulation_models import (
    DeviceCommand,
    ModeArbiterResult,
    PowerControllerResult,
    StrategyIntent,
)


# ZHA uses very small tolerances. For BSFAI we start slightly more conservative
# to reduce Home Assistant service calls and device stress.
DEFAULT_MIN_POWER_WRITE_DELTA_W = 15.0


@dataclass
class DeviceCommandConfig:
    min_power_write_delta_w: float = DEFAULT_MIN_POWER_WRITE_DELTA_W


class DeviceCommandBuilder:
    """Build final device command from the V4.2.0 regulation chain.

    This layer does not decide strategy and does not calculate power.
    It only translates the resolved technical mode and final power into the
    command shape needed by the Home Assistant/Zendure entities.

    V4.2.0:
    - Mode changes are always written.
    - Relevant power changes are written.
    - Small power changes are skipped.
    - The opposite limit is only zeroed when necessary.
    """

    def __init__(self, config: DeviceCommandConfig | None = None) -> None:
        self.config = config or DeviceCommandConfig()

    def build(
        self,
        *,
        intent: StrategyIntent,
        arbiter: ModeArbiterResult,
        power: PowerControllerResult,
        current_ac_mode: str | None,
        last_input_limit_w: float = 0.0,
        last_output_limit_w: float = 0.0,
    ) -> DeviceCommand:
        resolved_mode = arbiter.resolved_mode

        if resolved_mode == "input":
            return self._build_input_command(
                intent=intent,
                arbiter=arbiter,
                power=power,
                current_ac_mode=current_ac_mode,
                last_input_limit_w=last_input_limit_w,
                last_output_limit_w=last_output_limit_w,
            )

        if resolved_mode in ("output", "ramp_down_output"):
            return self._build_output_command(
                intent=intent,
                arbiter=arbiter,
                power=power,
                current_ac_mode=current_ac_mode,
                last_input_limit_w=last_input_limit_w,
                last_output_limit_w=last_output_limit_w,
            )

        if resolved_mode == "ramp_down_input":
            return self._build_input_command(
                intent=intent,
                arbiter=arbiter,
                power=power,
                current_ac_mode=current_ac_mode,
                last_input_limit_w=last_input_limit_w,
                last_output_limit_w=last_output_limit_w,
            )

        if resolved_mode == "hold":
            return self._build_hold_command(
                intent=intent,
                arbiter=arbiter,
                power=power,
                current_ac_mode=current_ac_mode,
                last_input_limit_w=last_input_limit_w,
                last_output_limit_w=last_output_limit_w,
            )

        # idle fallback: keep output mode with 0 W as neutral command.
        # This avoids accidental INPUT keepalive behavior on sensitive devices.
        return self._build_idle_command(
            intent=intent,
            arbiter=arbiter,
            power=power,
            current_ac_mode=current_ac_mode,
            last_input_limit_w=last_input_limit_w,
            last_output_limit_w=last_output_limit_w,
        )

    def _build_input_command(
        self,
        *,
        intent: StrategyIntent,
        arbiter: ModeArbiterResult,
        power: PowerControllerResult,
        current_ac_mode: str | None,
        last_input_limit_w: float,
        last_output_limit_w: float,
    ) -> DeviceCommand:
        input_limit_w = max(0.0, float(power.final_power_w or 0.0))

        should_write_mode = current_ac_mode != "input"

        # On mode switch, write the active side even if the watt value is close.
        # Otherwise use the normal write tolerance.
        should_write_input = should_write_mode or self._power_changed_enough(
            new_value=input_limit_w,
            old_value=last_input_limit_w,
        )

        # In INPUT mode the output side must be zero. Write it only if needed,
        # except on a real mode switch where we zero it proactively.
        should_write_output = should_write_mode or self._zero_write_needed(
            old_value=last_output_limit_w,
        )

        skipped = (
            not should_write_mode
            and not should_write_input
            and not should_write_output
        )

        return DeviceCommand(
            ac_mode="input",
            input_limit_w=round(input_limit_w, 2),
            output_limit_w=0.0,
            reason=power.reason or arbiter.reason or intent.reason,
            should_write_mode=bool(should_write_mode),
            should_write_input=bool(should_write_input),
            should_write_output=bool(should_write_output),
            skipped=bool(skipped),
            skip_reason="unchanged_within_tolerance" if skipped else "none",
            metadata={
                "intent": intent.intent,
                "requested_mode": intent.requested_mode,
                "resolved_mode": arbiter.resolved_mode,
                "mode_allowed": arbiter.allowed,
                "arbiter_reason": arbiter.reason,
                "power_reason": power.reason,
                "current_ac_mode": current_ac_mode,
                "last_input_limit_w": round(float(last_input_limit_w or 0.0), 2),
                "last_output_limit_w": round(float(last_output_limit_w or 0.0), 2),
                "min_power_write_delta_w": float(
                    self.config.min_power_write_delta_w
                ),
            },
        )

    def _build_output_command(
        self,
        *,
        intent: StrategyIntent,
        arbiter: ModeArbiterResult,
        power: PowerControllerResult,
        current_ac_mode: str | None,
        last_input_limit_w: float,
        last_output_limit_w: float,
    ) -> DeviceCommand:
        output_limit_w = max(0.0, float(power.final_power_w or 0.0))

        should_write_mode = current_ac_mode != "output"

        # On mode switch, write the active side even if the watt value is close.
        # Otherwise use the normal write tolerance.
        should_write_output = should_write_mode or self._power_changed_enough(
            new_value=output_limit_w,
            old_value=last_output_limit_w,
        )

        # In OUTPUT mode the input side must be zero. Write it only if needed,
        # except on a real mode switch where we zero it proactively.
        should_write_input = should_write_mode or self._zero_write_needed(
            old_value=last_input_limit_w,
        )

        skipped = (
            not should_write_mode
            and not should_write_input
            and not should_write_output
        )

        return DeviceCommand(
            ac_mode="output",
            input_limit_w=0.0,
            output_limit_w=round(output_limit_w, 2),
            reason=power.reason or arbiter.reason or intent.reason,
            should_write_mode=bool(should_write_mode),
            should_write_input=bool(should_write_input),
            should_write_output=bool(should_write_output),
            skipped=bool(skipped),
            skip_reason="unchanged_within_tolerance" if skipped else "none",
            metadata={
                "intent": intent.intent,
                "requested_mode": intent.requested_mode,
                "resolved_mode": arbiter.resolved_mode,
                "mode_allowed": arbiter.allowed,
                "arbiter_reason": arbiter.reason,
                "power_reason": power.reason,
                "current_ac_mode": current_ac_mode,
                "last_input_limit_w": round(float(last_input_limit_w or 0.0), 2),
                "last_output_limit_w": round(float(last_output_limit_w or 0.0), 2),
                "min_power_write_delta_w": float(
                    self.config.min_power_write_delta_w
                ),
            },
        )
        
    def _build_hold_command(
        self,
        *,
        intent: StrategyIntent,
        arbiter: ModeArbiterResult,
        power: PowerControllerResult,
        current_ac_mode: str | None,
        last_input_limit_w: float,
        last_output_limit_w: float,
    ) -> DeviceCommand:
        """Hold current technical mode without forcing a neutral mode switch.

        HOLD means: the ModeArbiter does not allow the requested mode yet.
        It should not automatically become OUTPUT 0 W, because that can cause
        visible INPUT/OUTPUT status flicker during PV transition phases.

        If the current mode is known, keep it and zero the active power.
        If the current mode is unknown, fall back to neutral OUTPUT 0 W.
        """

        ac_mode: Literal["input", "output"] = (
            "input" if current_ac_mode == "input" else "output"
        )

        should_write_mode = current_ac_mode not in ("input", "output")

        should_write_input = self._zero_write_needed(
            old_value=last_input_limit_w,
        )
        should_write_output = self._zero_write_needed(
            old_value=last_output_limit_w,
        )

        skipped = (
            not should_write_mode
            and not should_write_input
            and not should_write_output
        )

        return DeviceCommand(
            ac_mode=ac_mode,
            input_limit_w=0.0,
            output_limit_w=0.0,
            reason=power.reason or arbiter.reason or intent.reason,
            should_write_mode=bool(should_write_mode),
            should_write_input=bool(should_write_input),
            should_write_output=bool(should_write_output),
            skipped=bool(skipped),
            skip_reason="hold_current_mode_zero_power" if skipped else "none",
            metadata={
                "intent": intent.intent,
                "requested_mode": intent.requested_mode,
                "resolved_mode": arbiter.resolved_mode,
                "mode_allowed": arbiter.allowed,
                "arbiter_reason": arbiter.reason,
                "power_reason": power.reason,
                "current_ac_mode": current_ac_mode,
                "hold_ac_mode": ac_mode,
                "last_input_limit_w": round(float(last_input_limit_w or 0.0), 2),
                "last_output_limit_w": round(float(last_output_limit_w or 0.0), 2),
                "min_power_write_delta_w": float(
                    self.config.min_power_write_delta_w
                ),
            },
        )

    def _build_idle_command(
        self,
        *,
        intent: StrategyIntent,
        arbiter: ModeArbiterResult,
        power: PowerControllerResult,
        current_ac_mode: str | None,
        last_input_limit_w: float,
        last_output_limit_w: float,
    ) -> DeviceCommand:
        ac_mode: Literal["input", "output"] = "output"

        should_write_mode = current_ac_mode != ac_mode

        # Idle must reliably zero both sides if there is still a relevant limit.
        should_write_input = self._zero_write_needed(
            old_value=last_input_limit_w,
        )
        should_write_output = self._zero_write_needed(
            old_value=last_output_limit_w,
        )

        # If switching to neutral OUTPUT, write the mode and zero both sides.
        if should_write_mode:
            should_write_input = True
            should_write_output = True

        skipped = (
            not should_write_mode
            and not should_write_input
            and not should_write_output
        )

        return DeviceCommand(
            ac_mode=ac_mode,
            input_limit_w=0.0,
            output_limit_w=0.0,
            reason=power.reason or arbiter.reason or intent.reason,
            should_write_mode=bool(should_write_mode),
            should_write_input=bool(should_write_input),
            should_write_output=bool(should_write_output),
            skipped=bool(skipped),
            skip_reason="unchanged_within_tolerance" if skipped else "none",
            metadata={
                "intent": intent.intent,
                "requested_mode": intent.requested_mode,
                "resolved_mode": arbiter.resolved_mode,
                "mode_allowed": arbiter.allowed,
                "arbiter_reason": arbiter.reason,
                "power_reason": power.reason,
                "current_ac_mode": current_ac_mode,
                "last_input_limit_w": round(float(last_input_limit_w or 0.0), 2),
                "last_output_limit_w": round(float(last_output_limit_w or 0.0), 2),
                "min_power_write_delta_w": float(
                    self.config.min_power_write_delta_w
                ),
            },
        )

    def _power_changed_enough(
        self,
        *,
        new_value: float,
        old_value: float,
    ) -> bool:
        return abs(float(new_value) - float(old_value)) >= float(
            self.config.min_power_write_delta_w
        )

    def _zero_write_needed(
        self,
        *,
        old_value: float,
    ) -> bool:
        return abs(float(old_value or 0.0)) >= float(
            self.config.min_power_write_delta_w
        )