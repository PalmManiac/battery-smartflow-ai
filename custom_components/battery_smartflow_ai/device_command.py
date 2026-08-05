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


def clamp_number_power_request(
    requested_w: float,
    *,
    min_value: float | None = None,
    max_value: float | None = None,
) -> int:
    """Clamp a power request while preserving zero as the stop command.

    Zendure Number entities may expose a positive live minimum such as 300 W.
    That minimum applies to active charge/discharge commands, but not to the
    special 0 W command used to stop the active direction.
    """

    requested = max(0.0, float(requested_w or 0.0))
    if requested == 0.0:
        return 0

    effective = requested
    if min_value is not None:
        effective = max(float(min_value), effective)
    if max_value is not None:
        effective = min(float(max_value), effective)

    return int(round(effective, 0))


@dataclass
class DeviceCommandConfig:
    min_power_write_delta_w: float = DEFAULT_MIN_POWER_WRITE_DELTA_W


class DeviceCommandBuilder:
    """Build final device command from the V4.2.0 regulation chain.

    This layer does not decide strategy and does not calculate power.
    It only translates the resolved technical mode and final power into the
    command shape needed by the Home Assistant/Zendure entities.

    V4.3.0-dev6.1:
    - Mode changes are always written.
    - Relevant power changes are written.
    - Small power changes are skipped.
    - Directional commands are sent only through the active power entity.
      Current Zendure-HA versions include mode and opposite-limit zeroing in
      that command; a separate zero write would turn it into a stop command.

    V4.3.0-dev6.2:
    - The active Number entity is part of the write decision. A stale internal
      cache can no longer hide a real entity-state mismatch.
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
        current_input_limit_w: float | None = None,
        current_output_limit_w: float | None = None,
        max_input_w: float | None = None,
        max_output_w: float | None = None,
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
                current_input_limit_w=current_input_limit_w,
                max_input_w=max_input_w,
            )

        if resolved_mode in ("output", "ramp_down_output"):
            return self._build_output_command(
                intent=intent,
                arbiter=arbiter,
                power=power,
                current_ac_mode=current_ac_mode,
                last_input_limit_w=last_input_limit_w,
                last_output_limit_w=last_output_limit_w,
                current_output_limit_w=current_output_limit_w,
                max_output_w=max_output_w,
            )

        if resolved_mode == "ramp_down_input":
            return self._build_input_command(
                intent=intent,
                arbiter=arbiter,
                power=power,
                current_ac_mode=current_ac_mode,
                last_input_limit_w=last_input_limit_w,
                last_output_limit_w=last_output_limit_w,
                current_input_limit_w=current_input_limit_w,
                max_input_w=max_input_w,
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
        current_input_limit_w: float | None,
        max_input_w: float | None,
    ) -> DeviceCommand:
        input_limit_w = max(0.0, float(power.final_power_w or 0.0))
        if max_input_w is not None:
            input_limit_w = min(
                input_limit_w,
                max(0.0, float(max_input_w or 0.0)),
            )

        should_write_mode = current_ac_mode != "input"

        # The active number write is the complete directional command in
        # Zendure-HA. Repeat it on a mode switch or when our opposite-side cache
        # is stale, even if the active watt value itself is unchanged.
        should_write_input = (
            should_write_mode
            or self._power_changed_enough(
                new_value=input_limit_w,
                old_value=last_input_limit_w,
            )
            or self._zero_write_needed(
                old_value=last_output_limit_w,
            )
            or self._live_value_differs(
                expected_value=input_limit_w,
                current_value=current_input_limit_w,
            )
        )

        # Do not write outputLimit=0 separately. Zendure-HA already includes
        # outputLimit=0 in every inputLimit command. A second zero write is
        # interpreted as a full stop (smartMode=0).
        should_write_output = False

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
                "current_input_limit_w": current_input_limit_w,
                "effective_max_input_w": max_input_w,
                "opposite_limit_zeroed_by_active_command": True,
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
        current_output_limit_w: float | None,
        max_output_w: float | None,
    ) -> DeviceCommand:
        output_limit_w = max(0.0, float(power.final_power_w or 0.0))
        if max_output_w is not None:
            output_limit_w = min(
                output_limit_w,
                max(0.0, float(max_output_w or 0.0)),
            )

        should_write_mode = current_ac_mode != "output"

        # The active number write is the complete directional command in
        # Zendure-HA. Repeat it on a mode switch or when our opposite-side cache
        # is stale, even if the active watt value itself is unchanged.
        should_write_output = (
            should_write_mode
            or self._power_changed_enough(
                new_value=output_limit_w,
                old_value=last_output_limit_w,
            )
            or self._zero_write_needed(
                old_value=last_input_limit_w,
            )
            or self._live_value_differs(
                expected_value=output_limit_w,
                current_value=current_output_limit_w,
            )
        )

        # Do not write inputLimit=0 separately. Zendure-HA already includes
        # inputLimit=0 in every outputLimit command. A second zero write is
        # interpreted as a full stop (smartMode=0).
        should_write_input = False

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
                "current_output_limit_w": current_output_limit_w,
                "effective_max_output_w": max_output_w,
                "opposite_limit_zeroed_by_active_command": True,
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

        has_power_to_stop = (
            self._zero_write_needed(old_value=last_input_limit_w)
            or self._zero_write_needed(old_value=last_output_limit_w)
        )

        # Stop once through the currently active side. Its zero command already
        # clears both limits in Zendure-HA.
        should_write_input = bool(
            ac_mode == "input"
            and (should_write_mode or has_power_to_stop)
        )
        should_write_output = bool(
            ac_mode == "output"
            and (should_write_mode or has_power_to_stop)
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
                "single_stop_command": True,
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

        has_power_to_stop = (
            self._zero_write_needed(old_value=last_input_limit_w)
            or self._zero_write_needed(old_value=last_output_limit_w)
        )

        # Neutral idle is always represented by one outputLimit=0 command.
        # That command clears both sides and keeps the device in OUTPUT mode.
        should_write_input = False
        should_write_output = bool(should_write_mode or has_power_to_stop)

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
                "single_stop_command": True,
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

    def _live_value_differs(
        self,
        *,
        expected_value: float,
        current_value: float | None,
    ) -> bool:
        if current_value is None:
            return False

        return abs(float(expected_value) - float(current_value)) >= float(
            self.config.min_power_write_delta_w
        )
