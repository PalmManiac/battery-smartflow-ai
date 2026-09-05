"""Successful native command feedback advances the regulator setpoint."""

from __future__ import annotations

import unittest

from support import bootstrap

bootstrap()

from custom_components.battery_smartflow_ai.command_execution_state import (  # noqa: E402
    applied_command_state_updates,
)
from custom_components.battery_smartflow_ai.core.models import (  # noqa: E402
    CommandExecutionResult,
    CommandExecutionStatus,
    DeviceCommand,
)


class CommandExecutionStateTests(unittest.TestCase):
    def test_applied_output_advances_previous_regulation_value(self) -> None:
        updates = applied_command_state_updates(
            DeviceCommand(
                "output",
                output_limit_w=807.0,
                should_write_output=True,
            ),
            CommandExecutionResult(
                CommandExecutionStatus.APPLIED,
                "awaiting_readback",
                output_written=True,
            ),
        )

        self.assertEqual(updates["last_set_mode"], "output")
        self.assertEqual(updates["last_set_output_w"], 807)
        self.assertEqual(updates["last_set_input_w"], 0)

    def test_applied_input_keeps_input_as_active_atomic_side(self) -> None:
        updates = applied_command_state_updates(
            DeviceCommand(
                "input",
                input_limit_w=425.0,
                output_limit_w=0.0,
                should_write_input=True,
                should_write_output=True,
            ),
            CommandExecutionResult(
                CommandExecutionStatus.APPLIED,
                "awaiting_readback",
                input_written=True,
                output_written=True,
            ),
        )

        self.assertEqual(updates["last_set_mode"], "input")
        self.assertEqual(updates["last_set_input_w"], 425)
        self.assertEqual(updates["last_set_output_w"], 0)

    def test_skipped_and_failed_commands_never_advance_cache(self) -> None:
        command = DeviceCommand(
            "output",
            output_limit_w=900.0,
            should_write_output=True,
        )

        for status in (
            CommandExecutionStatus.SKIPPED,
            CommandExecutionStatus.FAILED,
        ):
            with self.subTest(status=status):
                self.assertEqual(
                    applied_command_state_updates(
                        command,
                        CommandExecutionResult(
                            status,
                            "not_applied",
                            output_written=True,
                        ),
                    ),
                    {},
                )

    def test_mode_only_feedback_updates_no_power_value(self) -> None:
        updates = applied_command_state_updates(
            DeviceCommand("output", should_write_mode=True),
            CommandExecutionResult(
                CommandExecutionStatus.APPLIED,
                "applied",
                mode_written=True,
            ),
        )

        self.assertEqual(updates, {"last_set_mode": "output"})


if __name__ == "__main__":
    unittest.main()
