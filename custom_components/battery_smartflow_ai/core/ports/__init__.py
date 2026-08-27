"""Platform-independent side-effect boundaries for the BSFAI core."""

from .clock import Clock
from .state_store import (
    StateLoadResult,
    StateSaveResult,
    StateStore,
    StateStoreStatus,
)

__all__ = [
    "Clock",
    "StateLoadResult",
    "StateSaveResult",
    "StateStore",
    "StateStoreStatus",
]
