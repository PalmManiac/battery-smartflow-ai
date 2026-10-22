"""Contracts for the V6 native-only device command path."""

from __future__ import annotations

import unittest
from pathlib import Path


COMPONENT = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "battery_smartflow_ai"
)


class NativeDeviceCommandPathTests(unittest.TestCase):
    def test_coordinator_has_no_home_assistant_entity_writer(self) -> None:
        coordinator = (COMPONENT / "coordinator.py").read_text(encoding="utf-8")

        self.assertNotIn("HomeAssistantEntityBackend", coordinator)
        self.assertNotIn("_device_backend", coordinator)
        self.assertNotIn("number.set_value", coordinator)
        self.assertNotIn("select.select_option", coordinator)

    def test_unconverted_entries_are_read_only_until_native_reconfigure(self) -> None:
        coordinator = (COMPONENT / "coordinator.py").read_text(encoding="utf-8")

        self.assertIn('"native_setup_required"', coordinator)
        self.assertIn('"native_control_disabled"', coordinator)
        self.assertIn("native_runtime.async_execute_device_command(command)", coordinator)

    def test_legacy_entity_writer_modules_are_removed(self) -> None:
        adapter = COMPONENT / "adapters" / "home_assistant"

        self.assertFalse((adapter / "device_backend.py").exists())
        self.assertFalse((adapter / "device_command_executor.py").exists())


if __name__ == "__main__":
    unittest.main()
