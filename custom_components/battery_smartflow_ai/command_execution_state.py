"""Persisted regulation state derived from confirmed device commands."""

from __future__ import annotations

from .core.models import (
    CommandExecutionResult,
    CommandExecutionStatus,
    DeviceCommand,
)


NATIVE_SETPOINTS_UNCHANGED = "native_setpoints_unchanged"


def confirmed_command_state_updates(
    command: DeviceCommand,
    result: CommandExecutionResult,
) -> dict[str, object]:
    """Return cache updates for a written or freshly confirmed active side.

    Home Assistant entity writers update this cache themselves. Native
    backends bypass those writers, so their successful feedback must advance
    the same regulator state explicitly.  After a restart, the requested
    setpoint can already match fresh native device state; that exact no-write
    result is equally safe to adopt as the next regulation baseline.
    """

    applied = result.status is CommandExecutionStatus.APPLIED
    confirmed_unchanged = bool(
        result.status is CommandExecutionStatus.SKIPPED
        and result.reason == NATIVE_SETPOINTS_UNCHANGED
    )
    if not applied and not confirmed_unchanged:
        return {}

    if command.ac_mode == "input" and (
        result.input_written or confirmed_unchanged
    ):
        value = int(round(max(0.0, float(command.input_limit_w or 0.0))))
        updates: dict[str, object] = {
            "last_set_mode": "input",
            "last_set_input_w": value,
            "last_set_output_w": 0,
        }
        if applied:
            updates["input_write_last_success_w"] = value
        return updates

    if command.ac_mode == "output" and (
        result.output_written or confirmed_unchanged
    ):
        value = int(round(max(0.0, float(command.output_limit_w or 0.0))))
        updates = {
            "last_set_mode": "output",
            "last_set_input_w": 0,
            "last_set_output_w": value,
        }
        if applied:
            updates["output_write_last_success_w"] = value
        return updates

    if result.mode_written:
        return {"last_set_mode": str(command.ac_mode)}

    return {}
