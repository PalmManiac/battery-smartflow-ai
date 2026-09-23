"""Contracts for the installable native Zendure development test."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "battery_smartflow_ai"


class NativeZendureHomeAssistantIntegrationTests(unittest.TestCase):
    def test_current_version_and_mqtt_dependency_are_packaged(self) -> None:
        manifest = json.loads(
            (COMPONENT / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["version"], "5.1.0-beta05")
        self.assertIn("paho-mqtt==2.1.0", manifest["requirements"])

    def test_options_flow_uses_a_password_field_and_never_suggests_token(self) -> None:
        source = (COMPONENT / "config_flow.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        method = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "_native_token_schema"
        )
        text = ast.unparse(method)
        self.assertIn("TextSelectorType.PASSWORD", text)
        self.assertNotIn("add_suggested_values_to_schema", text)
        self.assertIn("STORED_APP_TOKEN_MASK", text)
        self.assertNotIn("disable_native_zendure_test", text)

    def test_options_flow_asks_for_the_explicit_transport(self) -> None:
        source = (COMPONENT / "config_flow.py").read_text(encoding="utf-8")
        schema = source[
            source.index("def _native_device_schema"):
            source.index("def _native_device_summary")
        ]
        self.assertIn("CONF_NATIVE_ZENDURE_CONTROL_TRANSPORT", schema)
        self.assertIn('translation_key="zendure_transport"', schema)
        self.assertNotIn("CONF_NATIVE_ZENDURE_CONTROL_ENABLED", schema)
        self.assertIn("options[CONF_NATIVE_ZENDURE_CONTROL_ENABLED] = True", source)

    def test_legacy_installations_without_a_stored_choice_start_on_cloud(self) -> None:
        source = (COMPONENT / "config_flow.py").read_text(encoding="utf-8")
        schema = source[
            source.index("def _native_device_schema"):
            source.index("def _native_device_summary")
        ]
        self.assertIn(
            "if inherited is ZendureTransport.LOCAL_MQTT:\n                inherited = None",
            schema,
        )
        self.assertIn("else ZendureTransport.CLOUD_MQTT.value", schema)

    def test_legacy_local_setup_never_creates_a_broker_user(self) -> None:
        source = (COMPONENT / "config_flow.py").read_text(encoding="utf-8")
        legacy = (COMPONENT / "hardware" / "zendure" / "legacy.py").read_text(encoding="utf-8")
        self.assertIn("legacy_provisioning_default", source)
        self.assertIn("async_provision_legacy_device", source)
        self.assertNotIn("async_ensure_legacy_mqtt_users", source + legacy)

    def test_runtime_keeps_native_control_explicit_and_transport_typed(self) -> None:
        setup = (COMPONENT / "__init__.py").read_text(encoding="utf-8")
        runtime = (COMPONENT / "native_zendure_runtime.py").read_text(
            encoding="utf-8"
        )
        mqtt = (COMPONENT / "hardware" / "zendure" / "cloud_mqtt.py").read_text(encoding="utf-8")
        self.assertIn("coordinator.native_zendure.start()", setup)
        self.assertNotIn("await coordinator.native_zendure.start()", setup)
        self.assertNotIn("publish(", runtime)
        self.assertIn("SERVICE_VERIFY_NATIVE_WRITE", setup)
        self.assertIn("async_run_first_write_test", runtime)
        self.assertIn("NativeDeviceCommandGate", runtime)
        self.assertIn("async_execute_device_command", runtime)
        self.assertIn("native_runtime.control_enabled", (
            COMPONENT / "coordinator.py"
        ).read_text(encoding="utf-8"))
        self.assertNotIn("def publish", mqtt)
        self.assertIn("self._consume_captured_messages(capture.messages)", runtime)
        self.assertIn(
            "await self._async_poll_zensdk(now_monotonic=loop.time())", runtime
        )
        self.assertIn("ZENSDK_POLL_INTERVAL = 5.0", runtime)
        self.assertIn("ZENSDK_MAX_RETRY_INTERVAL = 60.0", runtime)
        self.assertIn("use_assigned_client_id=True", runtime)
        self.assertIn("await self._advance_local_handover()", runtime)

    def test_secret_is_not_exposed_by_sensor_or_diagnostic_surfaces(self) -> None:
        runtime = (COMPONENT / "native_zendure_runtime.py").read_text(
            encoding="utf-8"
        )
        sensor_method = runtime[runtime.index("def sensor_data"):runtime.index("def overview_attributes")]
        diagnostic_method = runtime[runtime.index("def diagnostic_data"):runtime.index("async def _async_run")]
        self.assertNotIn("_app_token", sensor_method)
        self.assertNotIn("_app_token", diagnostic_method)
        self.assertIn("ZendureDiagnosticSanitizer", diagnostic_method)

    def test_native_failure_cannot_block_legacy_first_refresh(self) -> None:
        source = (COMPONENT / "__init__.py").read_text(encoding="utf-8")
        self.assertLess(
            source.index("await coordinator.async_config_entry_first_refresh()"),
            source.index("coordinator.native_zendure.start()"),
        )

    def test_soc_outliers_cannot_reset_persistent_trade_accounting(self) -> None:
        source = (COMPONENT / "coordinator.py").read_text(encoding="utf-8")
        self.assertIn("evaluate_soc_for_accounting(", source)
        self.assertIn("soc=accounting_soc", source)
        self.assertIn('"soc_accounting_status": soc_accounting.status', source)

    def test_available_energy_retains_confirmed_soc_during_one_outlier(self) -> None:
        runtime = (COMPONENT / "native_zendure_runtime.py").read_text(encoding="utf-8")
        overview = (COMPONENT / "native_device_overview.py").read_text(encoding="utf-8")
        self.assertIn("def _update_available_energy_soc", runtime)
        self.assertIn("evaluate_soc_for_accounting(", runtime)
        self.assertIn('system_statistics.get("available_energy_soc_pct")', overview)

    def test_native_hardware_is_exposed_as_child_devices_not_config_inputs(self) -> None:
        sensor = (COMPONENT / "sensor.py").read_text(encoding="utf-8")
        identity = (COMPONENT / "native_registry_identity.py").read_text(
            encoding="utf-8"
        )
        config = (COMPONENT / "config_flow.py").read_text(encoding="utf-8")
        self.assertIn("class NativeZendureHardwareSensor", sensor)
        self.assertIn("via_device_id=integration_device.id", sensor)
        self.assertIn("via_device_id=_device_id_for_identifiers", sensor)
        self.assertIn(
            "async_get_device_by_identifier(\n            identifier,\n            config_entry_id,",
            sensor,
        )
        self.assertNotIn("via_device=", sensor)
        self.assertIn('return DOMAIN, f"native_zendure_{public_id}"', identity)
        self.assertIn("coordinator.native_zendure.hardware_overview()", sensor)
        self.assertIn("coordinator.async_add_listener", sensor)
        self.assertNotIn("native_hardware_soc_pct", config)
        self.assertNotIn("native_hardware_charge_power_w", config)

    def test_legacy_display_retention_does_not_change_runtime_freshness(self) -> None:
        sensor = (COMPONENT / "sensor.py").read_text(encoding="utf-8")
        overview = (COMPONENT / "native_device_overview.py").read_text(
            encoding="utf-8"
        )
        runtime = (COMPONENT / "native_zendure_runtime.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("legacy_display_retains_stale_value(parent, measured)", sensor)
        self.assertIn("LEGACY_DISPLAY_RETENTION_SECONDS = 300.0", overview)
        self.assertIn("maximum_age_seconds: float = 30.0", runtime)

    def test_safe_idle_capacity_reason_is_a_translated_enum_state(self) -> None:
        constants = ast.parse((COMPONENT / "const.py").read_text(encoding="utf-8"))
        enum_names = {"DECISION_REASON_ENUMS"}
        for node in constants.body:
            if not isinstance(node, ast.Assign):
                continue
            if not any(
                isinstance(target, ast.Name) and target.id in enum_names
                for target in node.targets
            ):
                continue
            self.assertIn("native_capacity_unavailable", ast.literal_eval(node.value))
        sensor_source = (COMPONENT / "sensor.py").read_text(encoding="utf-8")
        self.assertIn("options=STRATEGIC_REASON_ENUMS", sensor_source)
        self.assertIn(
            'STRATEGIC_REASON_ENUMS = [*STRATEGY_REASON_ENUMS, "native_capacity_unavailable"]',
            (COMPONENT / "const.py").read_text(encoding="utf-8"),
        )

        for filename in ("strings.json", "de.json", "en.json", "fr.json", "nl.json"):
            path = COMPONENT / (filename if filename == "strings.json" else f"translations/{filename}")
            sensors = json.loads(path.read_text(encoding="utf-8"))["entity"]["sensor"]
            for key in ("decision_reason", "strategic_reason"):
                self.assertIn("native_capacity_unavailable", sensors[key]["state"])

    def test_serial_is_device_metadata_but_not_part_of_entity_identity(self) -> None:
        sensor = (COMPONENT / "sensor.py").read_text(encoding="utf-8")
        entity = sensor[sensor.index("class NativeZendureHardwareSensor"):]
        self.assertIn("public_id", entity)
        self.assertIn("serial_number=item.serial_number", entity)
        self.assertNotIn("item.device_id", entity)
        self.assertNotIn("item.pack_id", entity)

    def test_pack_device_name_uses_parent_name_and_stable_position(self) -> None:
        sensor = (COMPONENT / "sensor.py").read_text(encoding="utf-8")
        self.assertIn("native_device_name(parent.display_name, parent.model)", sensor)
        self.assertIn("native_device_name(item.display_name, item.model)", sensor)
        self.assertIn("enumerate(parent.packs, start=1)", sensor)
        self.assertIn('"de": "Batterie-Pack"', sensor)
        self.assertNotIn("public_id[-6:]", sensor)

    def test_native_voltage_and_current_sensors_show_two_decimal_places(self) -> None:
        source = (COMPONENT / "sensor.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        descriptions = {
            next(
                keyword.value.value
                for keyword in node.keywords
                if keyword.arg == "key"
            ): node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and getattr(node.func, "id", None) == "NativeHardwareSensorDescription"
            and any(keyword.arg == "key" and isinstance(keyword.value, ast.Constant) for keyword in node.keywords)
        }
        for key in (
            "battery_voltage_v",
            "voltage_v",
            "current_a",
            "cell_min_v",
            "cell_max_v",
        ):
            precision = next(
                keyword.value.value
                for keyword in descriptions[key].keywords
                if keyword.arg == "suggested_display_precision"
            )
            self.assertEqual(precision, 2)

    def test_high_frequency_and_optional_pack_diagnostics_default_disabled(self) -> None:
        source = (COMPONENT / "sensor.py").read_text(encoding="utf-8")
        self.assertEqual(
            source.count(
                'key="last_message", translation_key="native_hardware_last_message"'
            ),
            2,
        )
        self.assertGreaterEqual(
            source.count("entity_registry_enabled_default=False"),
            6,
        )
        pack_section = source.split("NATIVE_PACK_SENSORS = (", 1)[1].split(
            "_SENSOR_DESCRIPTIONS", 1
        )[0]
        for key in ("fault_code", "protection_active", "last_message"):
            start = pack_section.index(f'key="{key}"')
            block = pack_section[start:start + 400]
            self.assertIn("entity_registry_enabled_default=False", block)
        global_last_message = source.index('key="native_zendure_last_message"')
        self.assertIn(
            "entity_registry_enabled_default=False",
            source[global_last_message:global_last_message + 500],
        )


if __name__ == "__main__":
    unittest.main()
