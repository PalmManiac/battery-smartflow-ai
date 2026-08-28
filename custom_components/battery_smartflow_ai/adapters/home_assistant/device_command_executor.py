"""Compatibility facade for the Issue #269 command-executor names."""

from ...core.ports.device_backend import DeviceBackendExecutionError
from .device_backend import HomeAssistantEntityBackend

HomeAssistantEntityCommandExecutor = HomeAssistantEntityBackend
DeviceCommandExecutionError = DeviceBackendExecutionError

__all__ = [
    "DeviceCommandExecutionError",
    "HomeAssistantEntityCommandExecutor",
]
