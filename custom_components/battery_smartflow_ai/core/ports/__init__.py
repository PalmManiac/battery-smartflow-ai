"""Platform-independent side-effect boundaries for the BSFAI core."""

from .clock import Clock
from .device_backend import DeviceBackend, DeviceBackendExecutionError
from .state_store import (
    StateLoadResult,
    StateSaveResult,
    StateStore,
    StateStoreStatus,
)

__all__ = [
    "Clock",
    "DeviceBackend",
    "DeviceBackendExecutionError",
    "StateLoadResult",
    "StateSaveResult",
    "StateStore",
    "StateStoreStatus",
]
