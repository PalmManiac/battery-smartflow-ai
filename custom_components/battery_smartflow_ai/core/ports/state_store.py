"""Neutral persistence contract for restart-safe BSFAI core state."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol


class StateStoreStatus(StrEnum):
    """Outcome of a persistence operation without platform exceptions."""

    LOADED = "loaded"
    EMPTY = "empty"
    SAVED = "saved"
    INVALID = "invalid"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class StateLoadResult:
    """Neutral load result containing only plain Python state."""

    status: StateStoreStatus
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    @property
    def usable(self) -> bool:
        """Return whether state can safely be merged with defaults."""

        return self.status is StateStoreStatus.LOADED


@dataclass(frozen=True, slots=True)
class StateSaveResult:
    """Neutral save result."""

    status: StateStoreStatus
    error: str | None = None

    @property
    def saved(self) -> bool:
        return self.status is StateStoreStatus.SAVED


class StateStore(Protocol):
    """Small backend-independent boundary for one versioned state document.

    The document stays flat for compatibility with existing installations.
    Component-owned serializers can be introduced behind this boundary without
    exposing Home Assistant Store objects, entry IDs or paths to the core.
    """

    async def load(self) -> StateLoadResult:
        """Load the persisted document or return a neutral fallback result."""

    async def save(self, data: dict[str, Any]) -> StateSaveResult:
        """Persist a plain Python document without leaking backend errors."""
