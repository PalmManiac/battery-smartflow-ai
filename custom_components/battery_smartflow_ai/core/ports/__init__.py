"""Platform-independent side-effect boundaries for the BSFAI core."""

from .state_store import (
    StateLoadResult,
    StateSaveResult,
    StateStore,
    StateStoreStatus,
)

__all__ = [
    "StateLoadResult",
    "StateSaveResult",
    "StateStore",
    "StateStoreStatus",
]
