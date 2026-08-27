"""Contracts for the Home Assistant DeviceCommand execution boundary."""

from __future__ import annotations

import unittest
from pathlib import Path

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.adapters.home_assistant.device_command_executor import (  # noqa: E402
    DeviceCommandExecutionError,
    HomeAssistantEntityCommandExecutor,
)
from custom_components.battery_smartflow_ai.core.models import (  # noqa: E402
    CommandExecutionStatus,
    DeviceCommand,
)


class DeviceCommandExecutorTests(unittest.IsolatedAsyncioTestCase):
    def executor(
        self,
        calls: list[tuple[str, object]],
        *,
        fail_output: bool = False,
    ) -> HomeAssistantEntityCommandExecutor:
        async def set_mode(mode: str) -> None:
            calls.append(("mode", mode))

        async def set_input(watts: float, *, force: bool = False) -> None:
            calls.append(("input", (watts, force)))

        async def set_output(watts: float, *, force: bool = False) -> None:
            calls.append(("output", (watts, force)))
            if fail_output:
                raise RuntimeError("entity unavailable")

        return HomeAssistantEntityCommandExecutor(
            set_ac_mode=set_mode,
            set_input_limit=set_input,
            set_output_limit=set_output,
        )

    async def test_normal_command_preserves_mode_then_power_order(self) -> None:
        calls: list[tuple[str, object]] = []
        command = DeviceCommand(
            ac_mode="input",
            input_limit_w=600.0,
            reason="planned_charge",
            should_write_mode=True,
            should_write_input=True,
            should_write_output=False,
        )

        result = await self.executor(calls).execute(command, force_power=True)

        self.assertEqual(
            calls,
            [("mode", "input"), ("input", (600.0, True))],
        )
        self.assertEqual(result.status, CommandExecutionStatus.APPLIED)
        self.assertTrue(result.mode_written)
        self.assertTrue(result.input_written)
        self.assertFalse(result.output_written)

    async def test_manual_standby_can_stop_power_before_mode(self) -> None:
        calls: list[tuple[str, object]] = []
        command = DeviceCommand(
            ac_mode="output",
            input_limit_w=0.0,
            reason="manual_standby",
            should_write_mode=True,
            should_write_input=True,
            should_write_output=False,
        )

        result = await self.executor(calls).execute(
            command,
            power_before_mode=True,
        )

        self.assertEqual(
            calls,
            [("input", (0.0, True)), ("mode", "output")],
        )
        self.assertEqual(result.status, CommandExecutionStatus.APPLIED)

    async def test_skipped_command_performs_no_platform_write(self) -> None:
        calls: list[tuple[str, object]] = []
        command = DeviceCommand(
            ac_mode="output",
            reason="idle",
            should_write_mode=False,
            should_write_input=False,
            should_write_output=False,
            skipped=True,
            skip_reason="unchanged",
        )

        result = await self.executor(calls).execute(command)

        self.assertEqual(calls, [])
        self.assertEqual(result.status, CommandExecutionStatus.SKIPPED)
        self.assertEqual(result.reason, "unchanged")

    async def test_platform_failure_is_raised_with_neutral_feedback(self) -> None:
        calls: list[tuple[str, object]] = []
        command = DeviceCommand(
            ac_mode="output",
            output_limit_w=500.0,
            reason="cover_deficit",
            should_write_mode=False,
            should_write_input=False,
            should_write_output=True,
        )

        with self.assertRaises(DeviceCommandExecutionError) as raised:
            await self.executor(calls, fail_output=True).execute(command)

        result = raised.exception.result
        self.assertEqual(result.status, CommandExecutionStatus.FAILED)
        self.assertEqual(result.reason, "cover_deficit")
        self.assertIn("entity unavailable", result.error or "")
        self.assertFalse(result.output_written)

    def test_coordinator_routes_all_product_writes_through_executor(self) -> None:
        coordinator = (
            Path(__file__).resolve().parents[1]
            / "custom_components"
            / "battery_smartflow_ai"
            / "coordinator.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn("await self._set_ac_mode(", coordinator)
        self.assertNotIn("await self._set_input_limit(", coordinator)
        self.assertNotIn("await self._set_output_limit(", coordinator)
        self.assertGreaterEqual(
            coordinator.count("await self._execute_device_command("),
            3,
        )


if __name__ == "__main__":
    unittest.main()
