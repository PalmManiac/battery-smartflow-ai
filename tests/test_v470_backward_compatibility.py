"""V4.6-to-V4.7 lifecycle, entity, and device-profile contracts."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path
import subprocess
import sys
import textwrap
import unittest

from support import bootstrap


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "custom_components" / "battery_smartflow_ai"


class ConfigEntryUpgradeCompatibilityTests(unittest.TestCase):
    def test_existing_entries_setup_migrate_and_unload_without_recreation(self) -> None:
        script = f"import sys; sys.path.insert(0, {str(ROOT)!r})\n" + textwrap.dedent(
            """
            import asyncio
            from types import SimpleNamespace

            import custom_components.battery_smartflow_ai as integration

            class FakeCoordinator:
                instances = []

                def __init__(self, hass, entry):
                    self.hass = hass
                    self.entry = entry
                    self.refreshed = False
                    self.shutdown = False
                    self.instances.append(self)

                async def async_config_entry_first_refresh(self):
                    self.refreshed = True

                async def async_shutdown(self):
                    self.shutdown = True

            class FakeConfigEntries:
                def __init__(self):
                    self.forwarded = []
                    self.unloaded = []
                    self.updates = []

                async def async_forward_entry_setups(self, entry, platforms):
                    self.forwarded.append((entry.entry_id, tuple(str(p) for p in platforms)))

                async def async_unload_platforms(self, entry, platforms):
                    self.unloaded.append((entry.entry_id, tuple(str(p) for p in platforms)))
                    return True

                def async_update_entry(self, entry, **changes):
                    self.updates.append((entry.entry_id, changes))

            class FakeHass:
                def __init__(self):
                    self.data = {}
                    self.config_entries = FakeConfigEntries()

            async def exercise():
                integration.ZendureSmartFlowCoordinator = FakeCoordinator
                hass = FakeHass()
                entry = SimpleNamespace(
                    entry_id="existing-entry-id",
                    version=1,
                    data={"soc_entity": "sensor.existing_soc", "custom": "keep"},
                    options={"regulation_v42_enabled": False, "soc_min": 12.0},
                )

                assert await integration.async_setup_entry(hass, entry)
                coordinator = hass.data[integration.DOMAIN][entry.entry_id]
                assert coordinator.entry is entry
                assert coordinator.refreshed
                assert hass.config_entries.forwarded == [
                    (entry.entry_id, ("sensor", "number", "select"))
                ]

                assert await integration.async_migrate_entry(hass, entry)
                update = hass.config_entries.updates[-1][1]
                assert update["version"] == 4
                assert update["data"] == {
                    "soc_entity": "sensor.existing_soc",
                    "custom": "keep",
                    "pack_capacity_kwh": 2.88,
                    "v5_migration": {
                        "schema_version": 1,
                        "phase": "zha_transition",
                        "legacy_system_id": "config_entry:existing-entry-id",
                        "binding_state": "unmatched",
                        "native_candidate_id": None,
                        "native_control_enabled": False,
                        "legacy_zha_enabled": True,
                    },
                }
                assert update["options"] == {"soc_min": 12.0}

                current = SimpleNamespace(
                    entry_id="current-entry-id", version=4,
                    data={"soc_entity": "sensor.current_soc"},
                    options={"soc_min": 10.0},
                )
                update_count = len(hass.config_entries.updates)
                assert await integration.async_migrate_entry(hass, current)
                assert len(hass.config_entries.updates) == update_count

                assert await integration.async_unload_entry(hass, entry)
                assert coordinator.shutdown
                assert entry.entry_id not in hass.data[integration.DOMAIN]

            asyncio.run(exercise())
            print("V460_ENTRY_COMPATIBILITY_OK")
            """
        )
        completed = subprocess.run(
            [sys.executable, "-I", "-c", script],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("V460_ENTRY_COMPATIBILITY_OK", completed.stdout)


class EntityRegistryCompatibilityTests(unittest.TestCase):
    """Freeze the entity-description surface published by V4.6.0 final."""

    V460_DESCRIPTION_HASHES = {
        "sensor.py": (
            "_SENSOR_DESCRIPTIONS",
            "ad999147f51777d7f1be09e12e0b9b597cea0980e37bb069b07fc4265dc9b564",
        ),
        "number.py": (
            "NUMBERS",
            "46e58cb6d49573b342ae01b6579c82bf58c61d350b3c3bdc2221a486aad58ffb",
        ),
        "select.py": (
            "SELECTS",
            "fc9f1a3aff2cba4eed4fe9d57a06e8c1906fbae973b36bb79d36a71912c45a2b",
        ),
    }

    @staticmethod
    def _description_hash(filename: str, variable: str) -> str:
        tree = ast.parse((PACKAGE_ROOT / filename).read_text(encoding="utf-8"))
        value = next(
            node.value
            for node in tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == variable
        )
        canonical = ast.dump(value, include_attributes=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def test_entity_descriptions_match_v460_final(self) -> None:
        for filename, (variable, expected_hash) in self.V460_DESCRIPTION_HASHES.items():
            with self.subTest(platform=filename):
                self.assertEqual(
                    self._description_hash(filename, variable),
                    expected_hash,
                )

    def test_registry_identifiers_remain_stable(self) -> None:
        sensor = (PACKAGE_ROOT / "sensor.py").read_text(encoding="utf-8")
        number = (PACKAGE_ROOT / "number.py").read_text(encoding="utf-8")
        select = (PACKAGE_ROOT / "select.py").read_text(encoding="utf-8")

        self.assertIn('f"{DOMAIN}_{entry.entry_id}_{description.key}"', sensor)
        self.assertIn('f"{entry.entry_id}_{description.key}"', number)
        self.assertIn('f"{entry.entry_id}_{description.key}"', select)
        for source in (sensor, number, select):
            self.assertIn("(DOMAIN, entry.entry_id)", source)

        self.assertIn('identifiers={(DOMAIN, f"{entry.entry_id}_economics")}', sensor)
        self.assertIn("via_device=(DOMAIN, entry.entry_id)", sensor)


bootstrap()

from custom_components.battery_smartflow_ai.device_profiles import (  # noqa: E402
    DEVICE_PROFILE_MODELS,
    DEVICE_PROFILES,
)


class V460DeviceProfileCompatibilityTests(unittest.TestCase):
    EXPECTED_PROFILE_SURFACE = {
        "SF2400AC": (2400.0, 2400.0, False, True, True, True, 10.0, -10.0, 30.0),
        "SF2400Pro": (2400.0, 2400.0, False, True, True, True, 10.0, -5.0, 30.0),
        "SF2400AC+": (2400.0, 2400.0, False, True, True, True, 10.0, -10.0, 30.0),
        "SF800Pro": (1000.0, 800.0, True, False, False, False, 30.0, 0.0, 35.0),
    }

    def test_supported_v460_profiles_keep_limits_and_regulation_behavior(self) -> None:
        for key, expected in self.EXPECTED_PROFILE_SURFACE.items():
            with self.subTest(profile=key):
                profile = DEVICE_PROFILES[key]
                actual = (
                    profile["MAX_INPUT_W"],
                    profile["MAX_OUTPUT_W"],
                    profile["SUPPORTS_PASSTHROUGH"],
                    profile["SUPPORTS_OFFGRID_SOCKET"],
                    profile["SUPPORTS_OFFGRID_INPUT"],
                    profile["INPUT_KEEPALIVE_SAFE"],
                    profile["TARGET_IMPORT_W"],
                    profile["DISCHARGE_TARGET_IMPORT_W"],
                    profile["CHARGE_DEADBAND_W"],
                )
                self.assertEqual(actual, expected)
                self.assertEqual(
                    DEVICE_PROFILE_MODELS[key].as_legacy_mapping(),
                    profile,
                )


if __name__ == "__main__":
    unittest.main()
