"""Behavioral coverage for native setup, inventory and additional measurements."""
from __future__ import annotations

import ast
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Mapping

import voluptuous as vol
from support import bootstrap

bootstrap()

from test_native_device_overview import observed_pack
from test_native_source_fusion import make_bootstrap, report

from custom_components.battery_smartflow_ai import const
from custom_components.battery_smartflow_ai.core.models import (
    MeasuredValue,
    ValueValidity,
)
from custom_components.battery_smartflow_ai.device_profiles import DEVICE_PROFILE_MODELS
from custom_components.battery_smartflow_ai.hardware.shelly_pro_3em import (
    validate_shelly_host,
)
from custom_components.battery_smartflow_ai.hardware.zendure.device_matrix import (
    VerificationLevel,
    preferred_local_transport,
    resolve_zendure_device,
)
from custom_components.battery_smartflow_ai.hardware.zendure.zensdk import (
    normalize_zensdk_ipv4,
)
from custom_components.battery_smartflow_ai.native_capacity import (
    native_capacity,
    pack_capacity_kwh,
)
from custom_components.battery_smartflow_ai.native_config_ui import (
    native_device_label,
    native_device_summary_line,
)
from custom_components.battery_smartflow_ai.native_device_overview import (
    _difference,
    _pack_status,
)
from custom_components.battery_smartflow_ai.native_device_setup import (
    SETUP_COMPLETE,
    SETUP_REQUIRED,
    reconcile_device_setups,
    save_device_setup,
    setup_is_complete,
)
from custom_components.battery_smartflow_ai.native_source_fusion import (
    NativeSourceFusion,
)
from custom_components.battery_smartflow_ai.price_currency import (
    price_input_profile,
    resolve_price_currency,
)


class NativeCapacityTests(unittest.TestCase):
    def test_mixed_packs_and_no_arbitrary_count_limit(self):
        packs = [observed_pack(f"F02N-test-{n}", "main") for n in range(9)]
        ab2000x = observed_pack("C04E-test", "main")
        ab2000x.pack_type = MeasuredValue.absent(ValueValidity.MISSING)
        packs.append(ab2000x)
        result = native_capacity(SimpleNamespace(packs=packs))
        self.assertEqual(result.pack_count, 10)
        self.assertEqual(result.capacity_kwh, 27.84)

    def test_missing_unknown_and_incomplete_are_not_zero_capacity(self):
        self.assertIsNone(native_capacity(None).pack_count)
        pack = observed_pack("Unknown-serial", "main")
        pack.pack_type = MeasuredValue.absent(ValueValidity.MISSING)
        self.assertEqual(native_capacity(SimpleNamespace(packs=[pack])).reason, "unknown_pack_profile")
        self.assertIsNone(native_capacity(SimpleNamespace(packs=[pack]), 2).capacity_kwh)

    def test_stale_pack_does_not_reuse_manual_capacity(self):
        pack = observed_pack("F02N-test", "main")
        pack.soc_pct = MeasuredValue.absent(ValueValidity.STALE)
        self.assertEqual(native_capacity(SimpleNamespace(packs=[pack])).reason, "pack_data_unavailable")

    def test_internal_large_pack_is_not_mistaken_for_ab1000(self):
        self.assertEqual(pack_capacity_kwh("B000-test", "70"), 8.0)
        self.assertEqual(pack_capacity_kwh(None, "5"), 2.88)

    def test_derived_values_keep_valid_zero_and_unknown_codes(self):
        self.assertEqual(_difference(MeasuredValue.available(3.22), MeasuredValue.available(3.21)).value, 0.01)
        self.assertEqual(_pack_status(MeasuredValue.available(0)).value, "idle")
        self.assertFalse(_pack_status(MeasuredValue.available(99)).valid)


class AdditionalDiagnosticTests(unittest.IsolatedAsyncioTestCase):
    async def test_heating_does_not_mean_protection_but_faults_block(self):
        now = datetime(2026, 9, 8, tzinfo=timezone.utc)
        fusion = NativeSourceFusion(await make_bootstrap())
        heating_only = fusion.apply(report(now, {"heatState": 1}))
        self.assertTrue(heating_only.state.heating_active.value)
        self.assertFalse(heating_only.state.protection_active.valid)
        normal = fusion.apply(report(now, {"is_error": 0}))
        self.assertFalse(normal.state.protection_active.value)
        error = fusion.apply(report(now, {"is_error": 1}))
        self.assertTrue(error.state.protection_active.value)

    async def test_raw_status_survives_source_fusion_and_expires(self):
        now = datetime(2026, 9, 8, tzinfo=timezone.utc)
        fusion = NativeSourceFusion(await make_bootstrap())
        result = fusion.apply(report(now, {"OTAState": 1, "solarPower2": 0}))
        self.assertEqual(result.state.diagnostics["OTAState"].value, 1)
        self.assertEqual(result.state.diagnostics["solarPower2"].value, 0)
        expired = fusion.snapshot("cloud_mqtt:device-1", now=now + timedelta(days=1))
        self.assertFalse(expired.state.diagnostics["OTAState"].valid)


class FlowBase:
    def __init_subclass__(cls, **kwargs):
        pass
    def async_show_form(self, **kwargs):
        return {"type": "form", **kwargs}
    def async_show_menu(self, **kwargs):
        return {"type": "menu", **kwargs}
    def async_create_entry(self, **kwargs):
        return {"type": "create_entry", **kwargs}
    def async_update_and_abort(self, entry, **kwargs):
        return {"type": "abort", "entry": entry, **kwargs}


class SelectorStub:
    """Only replace HA selectors; execute the real complete flow methods."""
    def __getattr__(self, name):
        if name in {"TextSelectorType", "SelectSelectorMode", "NumberSelectorMode"}:
            return SimpleNamespace(PASSWORD="password", DROPDOWN="dropdown", BOX="box")
        return lambda *args, **kwargs: (lambda value: value) if not name.endswith("Config") else kwargs


def load_flow_namespace():
    source = Path(__file__).parents[1] / "custom_components/battery_smartflow_ai/config_flow.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    nodes = [node for node in tree.body if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.Assign))]
    namespace = dict(vars(const))
    namespace.update(
        vol=vol, selector=SelectorStub(),
        Mapping=Mapping,
        config_entries=SimpleNamespace(ConfigFlow=FlowBase, OptionsFlow=FlowBase),
        resolve_zendure_device=resolve_zendure_device,
        VerificationLevel=VerificationLevel,
        normalize_zensdk_ipv4=normalize_zensdk_ipv4,
        preferred_local_transport=preferred_local_transport,
        DEVICE_PROFILE_MODELS=DEVICE_PROFILE_MODELS,
        resolve_price_currency=resolve_price_currency,
        price_input_profile=price_input_profile,
        native_device_label=native_device_label,
        native_device_summary_line=native_device_summary_line,
        validate_shelly_host=validate_shelly_host,
        SETUP_COMPLETE=SETUP_COMPLETE,
        reconcile_device_setups=reconcile_device_setups,
        save_device_setup=save_device_setup,
        setup_is_complete=setup_is_complete,
    )
    from custom_components.battery_smartflow_ai.core.models import ZendureTransport
    namespace["ZendureTransport"] = ZendureTransport
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"), namespace)
    return namespace


def load_flow_classes():
    return load_flow_namespace()["ZendureSmartFlowConfigFlow"]


class NativeSetupTests(unittest.IsolatedAsyncioTestCase):
    async def test_zensdk_ip_is_validated_and_persisted_per_device(self):
        namespace = load_flow_namespace()
        devices = await make_bootstrap(("device-1", "device-2"))
        first, second = devices.devices
        first_id = first.candidate.candidate_id
        second_id = second.candidate.candidate_id
        validate_ip = namespace["_validate_native_zensdk_ip"]
        update_ip = namespace["_update_native_zensdk_ip"]

        error, address, clear = validate_ip(
            {const.CONF_NATIVE_ZENDURE_ZENSDK_IP: "192.168.1.44"},
            first.candidate.identity,
        )
        self.assertIsNone(error)
        self.assertEqual(address, "192.168.1.44")
        self.assertFalse(clear)
        error, address, _clear = validate_ip(
            {const.CONF_NATIVE_ZENDURE_ZENSDK_IP: "8.8.8.8"},
            first.candidate.identity,
        )
        self.assertEqual(error, "invalid_zensdk_ip")
        self.assertIsNone(address)

        setup_map = reconcile_device_setups(devices.devices)
        setup_map["devices"][first_id]["transport"] = "zensdk"
        setup_map["devices"][second_id]["transport"] = "cloud_mqtt"
        saved = update_ip(setup_map, first_id, "192.168.1.44")
        self.assertEqual(saved["devices"][first_id]["zensdk_ip"], "192.168.1.44")
        self.assertNotIn("zensdk_ip", saved["devices"][second_id])

        cleared = update_ip(saved, first_id, None, clear=True)
        self.assertNotIn("zensdk_ip", cleared["devices"][first_id])

    async def test_new_setup_configures_each_supported_system_separately(self):
        flow = load_flow_classes()()
        flow.hass = SimpleNamespace(config=SimpleNamespace(currency="EUR"))
        flow._native_bootstrap = await make_bootstrap(("device-1", "device-2"))
        flow._native_options = {
            const.CONF_NATIVE_ZENDURE_APP_TOKEN: "private-test-token"
        }

        first = await flow.async_step_native_device({
            const.CONF_NATIVE_ZENDURE_SELECTED_DEVICE: "cloud_mqtt:device-1",
            const.CONF_NATIVE_ZENDURE_CONTROL_TRANSPORT: "cloud_mqtt",
            const.CONF_NATIVE_ZENDURE_CONTROL_ENABLED: False,
        })
        self.assertEqual(first["type"], "form")
        self.assertEqual(first["step_id"], "native_device")
        self.assertEqual(
            flow._native_setup_map["devices"]["cloud_mqtt:device-1"]["transport"],
            "cloud_mqtt",
        )

        second = await flow.async_step_native_device({
            const.CONF_NATIVE_ZENDURE_SELECTED_DEVICE: "cloud_mqtt:device-2",
            const.CONF_NATIVE_ZENDURE_CONTROL_TRANSPORT: "zensdk",
        })
        self.assertEqual(second["type"], "form")
        self.assertEqual(second["step_id"], "native_external")
        self.assertEqual(
            flow._native_options[const.CONF_NATIVE_ZENDURE_DEVICE_SETUPS][
                "devices"
            ]["cloud_mqtt:device-2"]["transport"],
            "zensdk",
        )
        self.assertEqual(
            flow._native_options[const.CONF_NATIVE_ZENDURE_SELECTED_DEVICE],
            "cloud_mqtt:device-1",
        )
        self.assertFalse(
            flow._native_options[const.CONF_NATIVE_ZENDURE_CONTROL_ENABLED]
        )

    async def test_options_setup_can_finish_while_an_unseen_device_is_offline(self):
        flow = load_flow_namespace()["ZendureSmartFlowOptionsFlow"]()
        flow.config_entry = SimpleNamespace(
            data={},
            options={
                const.CONF_NATIVE_ZENDURE_SELECTED_DEVICE: "cloud_mqtt:device-1",
                const.CONF_NATIVE_ZENDURE_CONTROL_TRANSPORT: "cloud_mqtt",
            },
        )
        flow._native_bootstrap = await make_bootstrap()
        flow._native_token = "private-test-token"
        flow._native_setup_map = reconcile_device_setups(
            flow._native_bootstrap.devices
        )
        flow._native_setup_map["devices"]["cloud_mqtt:device-1"].update(
            setup_status=SETUP_COMPLETE,
            transport="cloud_mqtt",
        )
        flow._native_setup_map["devices"]["cloud_mqtt:offline"] = {
            "setup_status": SETUP_REQUIRED,
            "online": False,
        }

        result = await flow.async_step_native_zendure_device({
            const.CONF_NATIVE_ZENDURE_SELECTED_DEVICE: "cloud_mqtt:device-1",
            const.CONF_NATIVE_ZENDURE_CONTROL_TRANSPORT: "cloud_mqtt",
        })

        self.assertEqual(result["type"], "create_entry")
        self.assertIn(
            "cloud_mqtt:offline",
            result["data"][const.CONF_NATIVE_ZENDURE_DEVICE_SETUPS]["devices"],
        )

    async def test_smart_mode_option_defaults_on_and_can_be_disabled(self):
        options_flow = load_flow_namespace()["ZendureSmartFlowOptionsFlow"]()
        options_flow.config_entry = SimpleNamespace(options={"unrelated": "keep"})

        form = await options_flow.async_step_smart_mode()
        key = next(iter(form["data_schema"].schema))
        self.assertEqual(key.schema, const.CONF_NATIVE_ZENDURE_ALWAYS_SMART_MODE_1)
        self.assertTrue(key.default)

        saved = await options_flow.async_step_smart_mode({key.schema: False})
        self.assertEqual(saved["type"], "create_entry")
        self.assertFalse(saved["data"][const.CONF_NATIVE_ZENDURE_ALWAYS_SMART_MODE_1])
        self.assertEqual(saved["data"]["unrelated"], "keep")

    async def test_native_selection_to_entry_needs_no_zha_hardware_entities(self):
        flow = load_flow_classes()()
        flow.hass = SimpleNamespace(config=SimpleNamespace(currency="EUR"))
        flow._native_bootstrap = await make_bootstrap()
        flow._native_options = {const.CONF_NATIVE_ZENDURE_APP_TOKEN: "private-test-token"}
        start = await flow.async_step_user()
        self.assertEqual(start["step_id"], "native_login")
        self.assertNotIn("menu_options", start)
        result = await flow.async_step_native_device({
            const.CONF_NATIVE_ZENDURE_SELECTED_DEVICE: "cloud_mqtt:device-1",
            const.CONF_NATIVE_ZENDURE_CONTROL_ENABLED: True,
        })
        keys = {key.schema for key in result["data_schema"].schema}
        self.assertNotIn(const.CONF_SOC_ENTITY, keys)
        self.assertNotIn(const.CONF_PACK_CAPACITY_KWH, keys)
        self.assertNotIn(const.CONF_OUTPUT_LIMIT_ENTITY, keys)
        self.assertIn(const.CONF_PV_ENTITY, keys)
        pv_key = next(
            key for key in result["data_schema"].schema
            if key.schema == const.CONF_PV_ENTITY
        )
        self.assertIsInstance(pv_key, vol.Optional)
        await flow.async_step_native_external({const.CONF_GRID_MODE: const.GRID_MODE_SINGLE})
        entry = await flow.async_step_grid({const.CONF_GRID_POWER_ENTITY: "sensor.grid"})
        self.assertEqual(entry["type"], "create_entry")
        self.assertEqual(entry["data"][const.CONF_DEVICE_PROFILE], "SF2400AC")
        self.assertNotIn(const.CONF_PV_ENTITY, entry["data"])
        self.assertNotIn(const.CONF_NATIVE_ZENDURE_APP_TOKEN, entry["data"])
        self.assertEqual(entry["options"][const.CONF_NATIVE_ZENDURE_APP_TOKEN], "private-test-token")
        self.assertTrue(
            entry["options"][const.CONF_NATIVE_ZENDURE_CONTROL_ENABLED]
        )

    async def test_invalid_device_cannot_create_entry(self):
        flow = load_flow_classes()()
        flow._native_bootstrap = await make_bootstrap()
        result = await flow.async_step_native_device({const.CONF_NATIVE_ZENDURE_SELECTED_DEVICE: "missing"})
        self.assertEqual(result["errors"]["base"], "device_not_found")

    def test_reconfiguration_hides_native_inputs_without_deleting_legacy_data(self):
        flow = load_flow_classes()()
        flow.hass = SimpleNamespace(config=SimpleNamespace(currency="EUR"))
        entry = SimpleNamespace(data={const.CONF_SOC_ENTITY: "sensor.old"}, options={const.CONF_NATIVE_ZENDURE_CONTROL_ENABLED: True})
        keys = {key.schema for key in flow._base_schema(entry).schema}
        self.assertNotIn(const.CONF_SOC_ENTITY, keys)
        self.assertEqual(entry.data[const.CONF_SOC_ENTITY], "sensor.old")

    def test_new_setup_has_no_legacy_entity_selection_route(self):
        flow = load_flow_classes()()
        flow.hass = SimpleNamespace(config=SimpleNamespace(currency="EUR"))
        self.assertFalse(hasattr(flow, "async_step_legacy"))
        select_source = (
            Path(__file__).parents[1]
            / "custom_components"
            / "battery_smartflow_ai"
            / "select.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("services.async_call", select_source)

    async def test_legacy_reconfigure_converts_entry_and_prunes_battery_ids(self):
        flow = load_flow_classes()()
        flow.hass = SimpleNamespace(config=SimpleNamespace(currency="EUR"))
        entry = SimpleNamespace(
            entry_id="old-entry",
            data={
                const.CONF_SOC_ENTITY: "sensor.old_soc",
                const.CONF_AC_MODE_ENTITY: "select.old_mode",
                const.CONF_INPUT_LIMIT_ENTITY: "number.old_input",
                const.CONF_OUTPUT_LIMIT_ENTITY: "number.old_output",
                const.CONF_NATIVE_PV_ENTITY: "sensor.old_native_pv",
                const.CONF_ADDITIONAL_BATTERY_CHARGE_ENTITY: "sensor.old_charge",
                const.CONF_OFFGRID_MODE_ENTITY: "select.old_offgrid",
                const.CONF_PV_ENTITY: "sensor.pv",
                const.CONF_GRID_MODE: const.GRID_MODE_SINGLE,
                const.CONF_GRID_POWER_ENTITY: "sensor.grid",
            },
            options={
                const.CONF_DEVICE_PROFILE: "SF2400AC",
                const.CONF_BATTERY_AC_POWER_ENTITY: "sensor.old_battery_power",
                const.CONF_NATIVE_ZENDURE_CONTROL_ENABLED: False,
                const.SETTING_LEARNED_PLANNING_ENABLED: True,
                const.CONF_LOWEST_CELL_VOLTAGE_PACK_1: "sensor.old_cell",
            },
        )
        flow._get_reconfigure_entry = lambda: entry
        start = await flow.async_step_reconfigure()
        self.assertEqual(start["step_id"], "native_login")
        self.assertIs(flow._migration_entry, entry)

        flow._user_input = dict(entry.data)
        flow._user_input[const.CONF_DEVICE_PROFILE] = "SF2400AC"
        flow._native_options = {
            const.CONF_NATIVE_ZENDURE_APP_TOKEN: "new-token",
            const.CONF_NATIVE_ZENDURE_CONTROL_ENABLED: False,
        }
        result = await flow.async_step_grid({})

        self.assertEqual(result["type"], "abort")
        self.assertEqual(result["entry"], entry)
        self.assertEqual(result["data"]["connection_type"], "native")
        self.assertNotIn(const.CONF_SOC_ENTITY, result["data"])
        self.assertNotIn(const.CONF_AC_MODE_ENTITY, result["data"])
        self.assertNotIn(const.CONF_INPUT_LIMIT_ENTITY, result["data"])
        self.assertNotIn(const.CONF_OUTPUT_LIMIT_ENTITY, result["data"])
        self.assertNotIn(const.CONF_NATIVE_PV_ENTITY, result["data"])
        self.assertNotIn(const.CONF_ADDITIONAL_BATTERY_CHARGE_ENTITY, result["data"])
        self.assertNotIn(const.CONF_OFFGRID_MODE_ENTITY, result["data"])
        self.assertNotIn(const.CONF_BATTERY_AC_POWER_ENTITY, result["options"])
        self.assertEqual(result["data"][const.CONF_PV_ENTITY], "sensor.pv")
        self.assertEqual(result["data"][const.CONF_GRID_POWER_ENTITY], "sensor.grid")
        self.assertEqual(result["options"][const.CONF_NATIVE_ZENDURE_APP_TOKEN], "new-token")
        self.assertTrue(result["options"][const.SETTING_LEARNED_PLANNING_ENABLED])
        self.assertNotIn(const.CONF_DEVICE_PROFILE, result["options"])
        self.assertNotIn(const.CONF_LOWEST_CELL_VOLTAGE_PACK_1, result["options"])

    def test_native_reconfiguration_keeps_pv_entity_optional(self):
        flow = load_flow_classes()()
        flow.hass = SimpleNamespace(config=SimpleNamespace(currency="EUR"))
        entry = SimpleNamespace(
            data={"connection_type": "native"},
            options={},
        )
        schema = flow._base_schema(entry).schema
        pv_key = next(key for key in schema if key.schema == const.CONF_PV_ENTITY)
        self.assertIsInstance(pv_key, vol.Optional)

    async def test_shelly_reconfigure_updates_options_without_unsupported_keyword(self):
        flow = load_flow_classes()()
        flow.hass = SimpleNamespace(config=SimpleNamespace(currency="EUR"))
        entry = SimpleNamespace(
            data={
                const.CONF_GRID_MODE: const.GRID_MODE_SHELLY_PRO_3EM,
                const.CONF_SHELLY_PRO_3EM_HOST: "192.168.2.1",
            },
            options={
                const.CONF_SHELLY_PRO_3EM_PASSWORD: "old-password",
                const.CONF_NATIVE_ZENDURE_CONTROL_ENABLED: True,
            },
        )
        flow._get_reconfigure_entry = lambda: entry
        flow._user_input = dict(entry.data)

        result = await flow.async_step_reconfigure_grid(
            {const.CONF_SHELLY_PRO_3EM_HOST: "192.168.2.150"}
        )

        self.assertEqual(result["type"], "abort")
        self.assertEqual(result["reason"], "reconfigure_success")
        self.assertEqual(
            result["data"][const.CONF_SHELLY_PRO_3EM_HOST], "192.168.2.150"
        )
        self.assertNotIn(const.CONF_SHELLY_PRO_3EM_PASSWORD, result["options"])
        self.assertNotIn("options_updates", result)

    async def test_shelly_modbus_reconfigure_uses_host_without_http_password(self):
        flow = load_flow_classes()()
        flow.hass = SimpleNamespace(config=SimpleNamespace(currency="EUR"))
        entry = SimpleNamespace(
            data={
                const.CONF_GRID_MODE: const.GRID_MODE_SHELLY_PRO_3EM_MODBUS,
                const.CONF_SHELLY_PRO_3EM_HOST: "192.168.2.1",
            },
            options={const.CONF_SHELLY_PRO_3EM_PASSWORD: "old-password"},
        )
        flow._get_reconfigure_entry = lambda: entry
        flow._user_input = dict(entry.data)

        schema = flow._grid_schema(
            const.GRID_MODE_SHELLY_PRO_3EM_MODBUS,
            entry,
        ).schema
        self.assertFalse(
            any(
                key.schema == const.CONF_SHELLY_PRO_3EM_PASSWORD
                for key in schema
            )
        )

        result = await flow.async_step_reconfigure_grid(
            {const.CONF_SHELLY_PRO_3EM_HOST: "192.168.2.150"}
        )
        self.assertEqual(result["type"], "abort")
        self.assertEqual(
            result["data"][const.CONF_SHELLY_PRO_3EM_HOST],
            "192.168.2.150",
        )
        self.assertNotIn(const.CONF_SHELLY_PRO_3EM_PASSWORD, result["options"])
