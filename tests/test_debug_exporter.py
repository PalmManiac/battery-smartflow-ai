"""Tests for safe V4.4.0 JSON debug-package export."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.debug_exporter import (  # noqa: E402
    DEBUG_DIRECTORY,
    DebugExportError,
    export_debug_package,
)
from custom_components.battery_smartflow_ai.debug_package import (  # noqa: E402
    DebugPackage,
    DebugSample,
)


class DebugExporterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.config_directory = Path(self.tempdir.name)
        self.created_at = datetime(2026, 8, 12, 14, 5, 6, tzinfo=timezone.utc)

    def package(self, *, version: str = "4.4.0-dev1") -> DebugPackage:
        return DebugPackage(
            integration_version=version,
            created_at=self.created_at,
            recording_start=self.created_at - timedelta(minutes=10),
            recording_end=self.created_at,
            config={"token": "must-not-leak", "device": "SF2400AC"},
            samples=[
                DebugSample(
                    timestamp=self.created_at,
                    raw_values={"soc": 50.0},
                )
            ],
            summary={"sample_count": 1},
        )

    def test_exports_utf8_json_atomically_below_fixed_debug_directory(self) -> None:
        result = export_debug_package(
            self.package(),
            config_directory=self.config_directory,
        )

        self.assertEqual(result.path.parent, self.config_directory / DEBUG_DIRECTORY)
        self.assertRegex(
            result.path.name,
            r"^bsfai_v4\.4\.0-dev1_debug_2026-08-12_14-05-06_000000\.json$",
        )
        self.assertGreater(result.size_bytes, 0)
        self.assertEqual(result.size_bytes, result.path.stat().st_size)
        data = json.loads(result.path.read_text(encoding="utf-8"))
        self.assertEqual(data["samples"][0]["raw_values"]["soc"], 50.0)
        self.assertEqual(data["config"]["token"], "[REDACTED]")
        self.assertFalse(list(result.path.parent.glob("*.tmp")))

    def test_filename_sanitizes_untrusted_version_text(self) -> None:
        result = export_debug_package(
            self.package(version="../4.4.0 test"),
            config_directory=self.config_directory,
        )

        self.assertEqual(result.path.parent, self.config_directory / DEBUG_DIRECTORY)
        self.assertNotIn("..", result.path.name)
        self.assertNotIn(" ", result.path.name)

    def test_same_timestamp_never_overwrites_an_existing_package(self) -> None:
        first = export_debug_package(
            self.package(),
            config_directory=self.config_directory,
        )
        second = export_debug_package(
            self.package(),
            config_directory=self.config_directory,
        )

        self.assertTrue(first.path.exists())
        self.assertTrue(second.path.exists())
        self.assertNotEqual(first.path, second.path)
        self.assertTrue(second.path.stem.endswith("_1"))

    def test_rejects_oversized_package_without_creating_file(self) -> None:
        with self.assertRaisesRegex(DebugExportError, "exceeds"):
            export_debug_package(
                self.package(),
                config_directory=self.config_directory,
                max_export_bytes=10,
            )

        self.assertFalse((self.config_directory / DEBUG_DIRECTORY).exists())

    def test_atomic_replace_failure_removes_temporary_file(self) -> None:
        with patch(
            "custom_components.battery_smartflow_ai.debug_exporter.os.replace",
            side_effect=OSError("simulated failure"),
        ):
            with self.assertRaisesRegex(DebugExportError, "simulated failure"):
                export_debug_package(
                    self.package(),
                    config_directory=self.config_directory,
                )

        directory = self.config_directory / DEBUG_DIRECTORY
        self.assertTrue(directory.is_dir())
        self.assertEqual(list(directory.iterdir()), [])

    def test_retention_removes_only_old_bsfai_packages(self) -> None:
        directory = self.config_directory / DEBUG_DIRECTORY
        directory.mkdir(parents=True)
        old_files: list[Path] = []
        for index in range(3):
            path = directory / f"bsfai_v4.4.0_debug_old_{index}.json"
            path.write_text("{}", encoding="utf-8")
            timestamp = 100 + index
            os.utime(path, (timestamp, timestamp))
            old_files.append(path)
        foreign = directory / "user_notes.json"
        foreign.write_text("keep", encoding="utf-8")

        result = export_debug_package(
            self.package(),
            config_directory=self.config_directory,
            max_retained_packages=2,
        )

        retained = list(directory.glob("bsfai_*_debug_*.json"))
        self.assertEqual(len(retained), 2)
        self.assertEqual(result.removed_old_packages, 2)
        self.assertTrue(result.path.exists())
        self.assertTrue(foreign.exists())
        self.assertFalse(old_files[0].exists())
        self.assertFalse(old_files[1].exists())

    def test_invalid_limits_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "max_export_bytes"):
            export_debug_package(
                self.package(),
                config_directory=self.config_directory,
                max_export_bytes=0,
            )
        with self.assertRaisesRegex(ValueError, "max_retained_packages"):
            export_debug_package(
                self.package(),
                config_directory=self.config_directory,
                max_retained_packages=0,
            )


if __name__ == "__main__":
    unittest.main()
