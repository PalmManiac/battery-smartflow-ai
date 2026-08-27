"""Home Assistant implementation of the neutral BSFAI StateStore port."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from ...core.ports import (
    StateLoadResult,
    StateSaveResult,
    StateStoreStatus,
)


class HomeAssistantStateStore:
    """Keep the established HA Store key and flat payload fully compatible."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        version: int,
        key: str,
    ) -> None:
        self._store: Store[dict[str, Any]] = Store(hass, version, key)

    async def load(self) -> StateLoadResult:
        try:
            data = await self._store.async_load()
        except Exception as err:
            return StateLoadResult(
                status=StateStoreStatus.FAILED,
                error=f"{type(err).__name__}: {err}",
            )

        if data is None:
            return StateLoadResult(status=StateStoreStatus.EMPTY)
        if not isinstance(data, dict):
            return StateLoadResult(
                status=StateStoreStatus.INVALID,
                error=f"expected dict, got {type(data).__name__}",
            )
        return StateLoadResult(
            status=StateStoreStatus.LOADED,
            data=dict(data),
        )

    async def save(self, data: dict[str, Any]) -> StateSaveResult:
        try:
            await self._store.async_save(dict(data))
        except Exception as err:
            return StateSaveResult(
                status=StateStoreStatus.FAILED,
                error=f"{type(err).__name__}: {err}",
            )
        return StateSaveResult(status=StateStoreStatus.SAVED)
