"""Small deterministic test doubles for the platform-independent core."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from .models.device import (
    CommandExecutionResult,
    CommandExecutionStatus,
    DeviceCapabilities,
)
from .models.regulation import DeviceCommand
from .ports.state_store import (
    StateLoadResult,
    StateSaveResult,
    StateStoreStatus,
)


class MemoryStateStore:
    """Keep one detached state document in memory for domain tests."""

    def __init__(self, initial: dict[str, Any] | None = None) -> None:
        self._data = deepcopy(initial)

    async def load(self) -> StateLoadResult:
        if self._data is None:
            return StateLoadResult(StateStoreStatus.EMPTY)
        return StateLoadResult(StateStoreStatus.LOADED, deepcopy(self._data))

    async def save(self, data: dict[str, Any]) -> StateSaveResult:
        self._data = deepcopy(data)
        return StateSaveResult(StateStoreStatus.SAVED)


@dataclass
class FakeDeviceBackend:
    """Record neutral device commands and report deterministic success."""

    capabilities: DeviceCapabilities
    commands: list[DeviceCommand] = field(default_factory=list)

    async def execute(
        self,
        command: DeviceCommand,
        *,
        force_power: bool = True,
        power_before_mode: bool = False,
    ) -> CommandExecutionResult:
        self.commands.append(deepcopy(command))
        return CommandExecutionResult(
            CommandExecutionStatus.APPLIED,
            "fake_backend_applied",
            mode_written=command.should_write_mode,
            input_written=command.should_write_input and force_power,
            output_written=command.should_write_output and force_power,
        )
