"""Static integration contracts for the V4.4.0 Home Assistant wiring."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "battery_smartflow_ai"


class DebugIntegrationContractTests(unittest.TestCase):
    def test_manifest_and_runtime_version_match_v440_development(self) -> None:
        manifest_version = json.loads(
            (COMPONENT / "manifest.json").read_text(encoding="utf-8")
        )["version"]
        tree = ast.parse((COMPONENT / "const.py").read_text(encoding="utf-8"))
        runtime_version = next(
            node.value.value
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "INTEGRATION_VERSION"
                for target in node.targets
            )
            and isinstance(node.value, ast.Constant)
        )

        self.assertEqual(manifest_version, "4.4.0-dev1")
        self.assertEqual(runtime_version, manifest_version)

    def test_services_expose_only_supported_durations(self) -> None:
        services = (COMPONENT / "services.yaml").read_text(encoding="utf-8")

        self.assertIn("start_debug_recording:", services)
        self.assertIn("stop_debug_recording:", services)
        self.assertIn("integration: battery_smartflow_ai", services)
        for duration in (10, 30, 60, 120):
            self.assertIn(f'- "{duration}"', services)

        self.assertNotIn("            - 10\n", services)
        self.assertNotIn("- 0", services)

    def test_coordinator_keeps_inactive_path_before_sample_build(self) -> None:
        tree = ast.parse((COMPONENT / "coordinator.py").read_text(encoding="utf-8"))
        capture = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.AsyncFunctionDef)
            and node.name == "_async_capture_debug_sample"
        )
        statements = capture.body

        self.assertIsInstance(statements[1], ast.If)
        self.assertIn("not self._debug_recorder.is_active", ast.unparse(statements[1].test))
        self.assertIn("build_debug_sample", ast.unparse(capture))

    def test_file_export_runs_via_home_assistant_executor(self) -> None:
        source = (COMPONENT / "coordinator.py").read_text(encoding="utf-8")

        self.assertIn("await self.hass.async_add_executor_job", source)
        self.assertIn("export_debug_package", source)

    def test_native_diagnostics_download_and_auto_stop_refresh_are_wired(self) -> None:
        diagnostics = (COMPONENT / "diagnostics.py").read_text(encoding="utf-8")
        coordinator = (COMPONENT / "coordinator.py").read_text(encoding="utf-8")

        self.assertIn("async_get_config_entry_diagnostics", diagnostics)
        self.assertIn("debug_last_package_path", diagnostics)
        self.assertIn("self.hass.async_create_task(self.async_request_refresh())", coordinator)


if __name__ == "__main__":
    unittest.main()
