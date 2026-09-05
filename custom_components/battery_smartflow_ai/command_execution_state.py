"""Persisted regulation state derived from successful device commands."""

from __future__ import annotations

from .core.models import (
    CommandExecutionResult,
    CommandExecutionStatus,
    DeviceCommand,
)


def applied_command_state_updates(
    command: DeviceCommand,
    result: CommandExecutionResult,
) -> dict[str, object]:
    """Return cache updates only for the successfully written active side.

    Home Assistant entity writers update this cache themselves. Native
    backends bypass those writers, so their successful feedback must advance
    the same regulator state explicitly.
    """

    if result.status is not CommandExecutionStatus.APPLIED:
        return {}

    if command.ac_mode == "input" and result.input_written:
        value = int(round(max(0.0, float(command.input_limit_w or 0.0))))
        return {
            "last_set_mode": "input",
            "last_set_input_w": value,
            "last_set_output_w": 0,
            "input_write_last_success_w": value,
        }

    if command.ac_mode == "output" and result.output_written:
        value = int(round(max(0.0, float(command.output_limit_w or 0.0))))
        return {
            "last_set_mode": "output",
            "last_set_input_w": 0,
            "last_set_output_w": value,
            "output_write_last_success_w": value,
        }

    if result.mode_written:
        return {"last_set_mode": str(command.ac_mode)}

    return {}
