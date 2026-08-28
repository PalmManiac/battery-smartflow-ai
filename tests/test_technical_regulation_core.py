"""Issue #275 contracts for the platform-neutral regulation chain."""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
import unittest

from support import PACKAGE_ROOT, bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.core.clock import as_utc  # noqa: E402


class TechnicalRegulationCoreTests(unittest.TestCase):
    def test_regulation_modules_have_no_home_assistant_imports(self) -> None:
        for name in (
            "mode_arbiter.py",
            "regulation_power_controller.py",
            "grid_history.py",
            "device_command.py",
        ):
            tree = ast.parse((PACKAGE_ROOT / name).read_text(encoding="utf-8"))
            modules = {
                alias.name
                for node in ast.walk(tree)
                if isinstance(node, ast.Import)
                for alias in node.names
            }
            modules.update(
                node.module or ""
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom)
            )
            self.assertFalse(
                any(
                    module == "homeassistant"
                    or module.startswith("homeassistant.")
                    for module in modules
                ),
                name,
            )

    def test_domain_utc_normalization_is_platform_neutral(self) -> None:
        local = datetime(
            2026,
            8,
            28,
            15,
            0,
            tzinfo=timezone(timedelta(hours=2)),
        )
        self.assertEqual(
            as_utc(local),
            datetime(2026, 8, 28, 13, 0, tzinfo=UTC),
        )

    def test_naive_domain_timestamp_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            as_utc(datetime(2026, 8, 28, 13, 0))


if __name__ == "__main__":
    unittest.main()
