"""Execute neutral core commands through the existing HA entity write path."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from ...core.models.device import (
    CommandExecutionResult,
    CommandExecutionStatus,
)
from ...core.models.regulation import DeviceCommand


ModeWriter = Callable[[str], Awaitable[None]]
PowerWriter = Callable[..., Awaitable[None]]


class DeviceCommandExecutionError(RuntimeError):
    """Preserve the platform exception while exposing neutral failure feedback."""

    def __init__(self, result: CommandExecutionResult) -> None:
        super().__init__(result.error or result.reason)
        self.result = result


class HomeAssistantEntityCommandExecutor:
    """Map a neutral DeviceCommand to the current Select/Number writers.

    Entity IDs, services, availability checks, clamping and cache updates stay
    in the supplied Home Assistant writer callbacks. The core command contains
    no knowledge of those platform details.
    """

    def __init__(
        self,
        *,
        set_ac_mode: ModeWriter,
        set_input_limit: PowerWriter,
        set_output_limit: PowerWriter,
    ) -> None:
        self._set_ac_mode = set_ac_mode
        self._set_input_limit = set_input_limit
        self._set_output_limit = set_output_limit

    async def execute(
        self,
        command: DeviceCommand,
        *,
        force_power: bool = True,
        power_before_mode: bool = False,
    ) -> CommandExecutionResult:
        """Execute requested writes in the established order."""

        if command.skipped or not (
            command.should_write_mode
            or command.should_write_input
            or command.should_write_output
        ):
            return CommandExecutionResult(
                status=CommandExecutionStatus.SKIPPED,
                reason=command.skip_reason or command.reason,
            )

        mode_written = False
        input_written = False
        output_written = False

        async def write_power() -> None:
            nonlocal input_written, output_written
            if command.should_write_input:
                await self._set_input_limit(
                    command.input_limit_w,
                    force=force_power,
                )
                input_written = True
            if command.should_write_output:
                await self._set_output_limit(
                    command.output_limit_w,
                    force=force_power,
                )
                output_written = True

        try:
            if power_before_mode:
                await write_power()

            if command.should_write_mode:
                await self._set_ac_mode(command.ac_mode)
                mode_written = True

            if not power_before_mode:
                await write_power()
        except Exception as err:
            result = CommandExecutionResult(
                status=CommandExecutionStatus.FAILED,
                reason=command.reason,
                mode_written=mode_written,
                input_written=input_written,
                output_written=output_written,
                error=f"{type(err).__name__}: {err}",
            )
            raise DeviceCommandExecutionError(result) from err

        return CommandExecutionResult(
            status=CommandExecutionStatus.APPLIED,
            reason=command.reason,
            mode_written=mode_written,
            input_written=input_written,
            output_written=output_written,
        )
