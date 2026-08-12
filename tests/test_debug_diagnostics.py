"""Tests for the native Home Assistant diagnostics download."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.debug_exporter import DEBUG_DIRECTORY  # noqa: E402
from custom_components.battery_smartflow_ai.diagnostics import _load_latest_package  # noqa: E402


class DebugDiagnosticsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.config_directory = Path(self.tempdir.name)
        self.directory = self.config_directory / DEBUG_DIRECTORY
        self.directory.mkdir(parents=True)

    def test_download_loads_and_redacts_latest_owned_package(self) -> None:
        path = self.directory / "bsfai_debug_2026-08-12_13-13-43.json"
        path.write_text(
            json.dumps({"meta": {"schema": "battery_smartflow_ai.debug"}, "token": "secret"}),
            encoding="utf-8",
        )

        result = _load_latest_package(
            str(path),
            config_directory=str(self.config_directory),
        )

        self.assertEqual(result["meta"]["schema"], "battery_smartflow_ai.debug")
        self.assertEqual(result["token"], "[REDACTED]")

    def test_download_rejects_file_outside_owned_directory(self) -> None:
        outside = self.config_directory / "unrelated.json"
        outside.write_text('{"private": true}', encoding="utf-8")

        result = _load_latest_package(
            str(outside),
            config_directory=str(self.config_directory),
        )

        self.assertEqual(result["status"], "debug_package_unavailable")


if __name__ == "__main__":
    unittest.main()
