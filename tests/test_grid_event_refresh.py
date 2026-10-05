"""Tests for event-driven regulation refresh decisions."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

from support import bootstrap

bootstrap()

from custom_components.battery_smartflow_ai.const import (  # noqa: E402
    GRID_EVENT_REFRESH_MIN_INTERVAL_S,
)
from custom_components.battery_smartflow_ai.grid_event_refresh import (  # noqa: E402
    grid_refresh_delay,
    grid_value_changed,
)


class GridEventRefreshTests(unittest.TestCase):
    def test_refresh_callback_uses_thread_safe_home_assistant_scheduler(self) -> None:
        coordinator_path = (
            Path(__file__).resolve().parents[1]
            / "custom_components"
            / "battery_smartflow_ai"
            / "coordinator.py"
        )
        tree = ast.parse(coordinator_path.read_text(encoding="utf-8"))
        coordinator_class = next(
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef)
            and node.name == "ZendureSmartFlowCoordinator"
        )
        flush_method = next(
            node
            for node in coordinator_class.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "_flush_grid_event_refresh"
        )
        calls = [
            ast.unparse(node)
            for node in ast.walk(flush_method)
            if isinstance(node, ast.Call)
        ]

        self.assertIn("self.hass.add_job(self.async_request_refresh)", calls)
        self.assertNotIn(
            "self.hass.async_create_task(self.async_request_refresh())",
            calls,
        )

    def test_only_meaningful_numeric_changes_trigger(self) -> None:
        self.assertTrue(grid_value_changed("unknown", "120"))
        self.assertTrue(grid_value_changed(None, "120"))
        self.assertTrue(grid_value_changed("120", "122"))
        self.assertFalse(grid_value_changed("120", "120.4"))
        self.assertFalse(grid_value_changed("120", "120"))
        self.assertTrue(grid_value_changed("120", "unavailable"))
        self.assertFalse(grid_value_changed("unavailable", "unknown"))
        self.assertFalse(grid_value_changed("invalid", "nan"))
        self.assertFalse(grid_value_changed("invalid", "inf"))

    def test_first_event_is_immediate_and_later_events_are_rate_limited(self) -> None:
        self.assertEqual(
            grid_refresh_delay(
                now_monotonic=10.0,
                last_refresh_monotonic=None,
                min_interval_s=GRID_EVENT_REFRESH_MIN_INTERVAL_S,
            ),
            0.0,
        )
        self.assertEqual(
            grid_refresh_delay(
                now_monotonic=10.5,
                last_refresh_monotonic=10.0,
                min_interval_s=GRID_EVENT_REFRESH_MIN_INTERVAL_S,
            ),
            GRID_EVENT_REFRESH_MIN_INTERVAL_S - 0.5,
        )

    def test_elapsed_interval_allows_immediate_refresh(self) -> None:
        self.assertEqual(
            grid_refresh_delay(
                now_monotonic=10.0 + GRID_EVENT_REFRESH_MIN_INTERVAL_S,
                last_refresh_monotonic=10.0,
                min_interval_s=GRID_EVENT_REFRESH_MIN_INTERVAL_S,
            ),
            0.0,
        )


if __name__ == "__main__":
    unittest.main()
