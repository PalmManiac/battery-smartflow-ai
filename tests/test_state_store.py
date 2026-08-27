"""Contracts for the neutral StateStore and its HA adapter."""

from __future__ import annotations

from pathlib import Path
import sys
from types import ModuleType
import unittest

from support import bootstrap


bootstrap()


class FakeHAStore:
    """Small controllable replacement for homeassistant.helpers.storage.Store."""

    loaded: object = None
    load_error: Exception | None = None
    save_error: Exception | None = None
    saved: dict[str, object] | None = None
    init_args: tuple[object, int, str] | None = None

    def __class_getitem__(cls, item: object) -> type[FakeHAStore]:
        return cls

    def __init__(self, hass: object, version: int, key: str) -> None:
        type(self).init_args = (hass, version, key)

    async def async_load(self) -> object:
        if type(self).load_error is not None:
            raise type(self).load_error
        return type(self).loaded

    async def async_save(self, data: dict[str, object]) -> None:
        if type(self).save_error is not None:
            raise type(self).save_error
        type(self).saved = data


helpers = ModuleType("homeassistant.helpers")
helpers.__path__ = []
storage = ModuleType("homeassistant.helpers.storage")
storage.Store = FakeHAStore
sys.modules["homeassistant.helpers"] = helpers
sys.modules["homeassistant.helpers.storage"] = storage

from custom_components.battery_smartflow_ai.adapters.home_assistant.state_store import (  # noqa: E402
    HomeAssistantStateStore,
)
from custom_components.battery_smartflow_ai.core.ports import (  # noqa: E402
    StateStoreStatus,
)


class StateStoreTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        FakeHAStore.loaded = None
        FakeHAStore.load_error = None
        FakeHAStore.save_error = None
        FakeHAStore.saved = None
        FakeHAStore.init_args = None
        self.hass = object()
        self.store = HomeAssistantStateStore(
            self.hass,
            version=1,
            key="battery_smartflow_ai.entry-id",
        )

    async def test_existing_store_identity_and_flat_payload_are_preserved(self) -> None:
        payload = {
            "economics_energy_state": {"charged_kwh": 1.5},
            "charge_commit_active": True,
            "learned_load_slots": {"12": 230.0},
        }
        FakeHAStore.loaded = payload

        result = await self.store.load()

        self.assertEqual(
            FakeHAStore.init_args,
            (self.hass, 1, "battery_smartflow_ai.entry-id"),
        )
        self.assertEqual(result.status, StateStoreStatus.LOADED)
        self.assertEqual(result.data, payload)
        self.assertIsNot(result.data, payload)

    async def test_empty_and_invalid_documents_are_safe_fallbacks(self) -> None:
        empty = await self.store.load()
        self.assertEqual(empty.status, StateStoreStatus.EMPTY)
        self.assertEqual(empty.data, {})

        FakeHAStore.loaded = ["not", "a", "mapping"]
        invalid = await self.store.load()
        self.assertEqual(invalid.status, StateStoreStatus.INVALID)
        self.assertFalse(invalid.usable)
        self.assertIn("expected dict", invalid.error or "")

    async def test_load_failure_becomes_neutral_result(self) -> None:
        FakeHAStore.load_error = OSError("storage unavailable")

        result = await self.store.load()

        self.assertEqual(result.status, StateStoreStatus.FAILED)
        self.assertFalse(result.usable)
        self.assertEqual(result.data, {})
        self.assertIn("storage unavailable", result.error or "")

    async def test_save_copies_payload_and_reports_success(self) -> None:
        payload = {"runtime_mode": {"ai_mode": "automatic"}}

        result = await self.store.save(payload)

        self.assertEqual(result.status, StateStoreStatus.SAVED)
        self.assertTrue(result.saved)
        self.assertEqual(FakeHAStore.saved, payload)
        self.assertIsNot(FakeHAStore.saved, payload)

    async def test_save_failure_becomes_neutral_result(self) -> None:
        FakeHAStore.save_error = OSError("disk full")

        result = await self.store.save({"profit": 1.0})

        self.assertEqual(result.status, StateStoreStatus.FAILED)
        self.assertFalse(result.saved)
        self.assertIn("disk full", result.error or "")

    def test_core_port_has_no_home_assistant_dependency(self) -> None:
        port = (
            Path(__file__).resolve().parents[1]
            / "custom_components"
            / "battery_smartflow_ai"
            / "core"
            / "ports"
            / "state_store.py"
        ).read_text(encoding="utf-8")
        coordinator = (
            Path(__file__).resolve().parents[1]
            / "custom_components"
            / "battery_smartflow_ai"
            / "coordinator.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn("homeassistant", port)
        self.assertNotIn("homeassistant.helpers.storage", coordinator)
        self.assertIn("HomeAssistantStateStore", coordinator)


if __name__ == "__main__":
    unittest.main()
