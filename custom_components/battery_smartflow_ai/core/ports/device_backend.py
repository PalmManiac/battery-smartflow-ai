"""Neutral command-execution boundary for device backends."""

from __future__ import annotations

from typing import Protocol

from ..models.device import CommandExecutionResult, DeviceCapabilities
from ..models.regulation import DeviceCommand


class DeviceBackendExecutionError(RuntimeError):
    """Expose neutral failure feedback without leaking a platform exception."""

    def __init__(self, result: CommandExecutionResult) -> None:
        super().__init__(result.error or result.reason)
        self.result = result


class DeviceBackend(Protocol):
    """Small backend contract shared by HA and future hardware adapters."""

    @property
    def capabilities(self) -> DeviceCapabilities:
        """Return the immutable capabilities of the attached device."""

    async def execute(
        self,
        command: DeviceCommand,
        *,
        force_power: bool = True,
        power_before_mode: bool = False,
    ) -> CommandExecutionResult:
        """Execute one neutral command and return neutral feedback."""
