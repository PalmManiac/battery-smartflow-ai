from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .regulation_models import (
    DeviceCommand,
    ModeArbiterResult,
    PowerControllerResult,
    StrategyIntent,
)


DEFAULT_MIN_POWER_WRITE_DELTA_W = 5.0


@dataclass
class DeviceCommandConfig:
    min_power_write_delta_w: float = DEFAULT_MIN_POWER_WRITE_DELTA_W


class DeviceCommandBuilder:
    """Build final device command from the V4.2.0 regulation chain.

    This layer does not decide strategy and does not calculate power.
    It only translates the resolved technical mode and final power into the
    command shape needed by the Home Assistant/Zendure entities.

    V4.2.0 transition:
    First used for diagnostics only. Later this becomes the authoritative
    command path.
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
            )

        if resolved_mode in ("output", "ramp_down_output"):
            return self._build_output_command(
                intent=intent,
                arbiter=arbiter,
                power=power,
                current_ac_mode=current_ac_mode,
                last_output_limit_w=last_output_limit_w,
            )

        if resolved_mode == "ramp_down_input":
            return self._build_input_command(
                intent=intent,
                arbiter=arbiter,
                power=power,
                current_ac_mode=current_ac_mode,
                last_input_limit_w=last_input_limit_w,
            )

        # hold/idle fallback: keep output mode with 0 W as neutral command.
        # This avoids accidental INPUT keepalive behavior on sensitive devices
        # once this command path becomes active.
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
    ) -> DeviceCommand:
        input_limit_w = max(0.0, float(power.final_power_w or 0.0))

        should_write_mode = current_ac_mode != "input"
        should_write_input = self._power_changed_enough(
            new_value=input_limit_w,
            old_value=last_input_limit_w,
        )

        # In INPUT mode output limit should be zeroed once the command path is active.
        return DeviceCommand(
            ac_mode="input",
            input_limit_w=round(input_limit_w, 2),
            output_limit_w=0.0,
            reason=power.reason or arbiter.reason or intent.reason,
            should_write_mode=bool(should_write_mode),
            should_write_input=bool(should_write_input),
            should_write_output=True,
            skipped=False,
            skip_reason="none",
            metadata={
                "intent": intent.intent,
                "requested_mode": intent.requested_mode,
                "resolved_mode": arbiter.resolved_mode,
                "mode_allowed": arbiter.allowed,
                "arbiter_reason": arbiter.reason,
                "power_reason": power.reason,
            },
        )

    def _build_output_command(
        self,
        *,
        intent: StrategyIntent,
        arbiter: ModeArbiterResult,
        power: PowerControllerResult,
        current_ac_mode: str | None,
        last_output_limit_w: float,
    ) -> DeviceCommand:
        output_limit_w = max(0.0, float(power.final_power_w or 0.0))

        should_write_mode = current_ac_mode != "output"
        should_write_output = self._power_changed_enough(
            new_value=output_limit_w,
            old_value=last_output_limit_w,
        )

        # In OUTPUT mode input limit should be zeroed once the command path is active.
        return DeviceCommand(
            ac_mode="output",
            input_limit_w=0.0,
            output_limit_w=round(output_limit_w, 2),
            reason=power.reason or arbiter.reason or intent.reason,
            should_write_mode=bool(should_write_mode),
            should_write_input=True,
            should_write_output=bool(should_write_output),
            skipped=False,
            skip_reason="none",
            metadata={
                "intent": intent.intent,
                "requested_mode": intent.requested_mode,
                "resolved_mode": arbiter.resolved_mode,
                "mode_allowed": arbiter.allowed,
                "arbiter_reason": arbiter.reason,
                "power_reason": power.reason,
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
        should_write_input = self._power_changed_enough(
            new_value=0.0,
            old_value=last_input_limit_w,
        )
        should_write_output = self._power_changed_enough(
            new_value=0.0,
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
            skip_reason="unchanged" if skipped else "none",
            metadata={
                "intent": intent.intent,
                "requested_mode": intent.requested_mode,
                "resolved_mode": arbiter.resolved_mode,
                "mode_allowed": arbiter.allowed,
                "arbiter_reason": arbiter.reason,
                "power_reason": power.reason,
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