"""Behavioral coverage for native setup, inventory and additional measurements."""
from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import unittest
import voluptuous as vol

from support import bootstrap
bootstrap()

from custom_components.battery_smartflow_ai import const
from custom_components.battery_smartflow_ai.core.models import MeasuredValue, ValueValidity
from custom_components.battery_smartflow_ai.native_capacity import native_capacity, pack_capacity_kwh
from custom_components.battery_smartflow_ai.native_device_overview import _difference, _pack_status
from custom_components.battery_smartflow_ai.native_source_fusion import NativeSourceFusion
from custom_components.battery_smartflow_ai.zendure_device_matrix import preferred_local_transport, resolve_zendure_device
from custom_components.battery_smartflow_ai.native_config_ui import native_device_label, native_device_summary_line
from custom_components.battery_smartflow_ai.price_currency import price_input_profile, resolve_price_currency
from custom_components.battery_smartflow_ai.device_profiles import DEVICE_PROFILE_MODELS
from test_native_source_fusion import make_bootstrap, report
from test_native_device_overview import observed_pack


class NativeCapacityTests(unittest.TestCase):
    def test_mixed_packs_and_no_arbitrary_count_limit(self):
        packs = [observed_pack(f"F02N-test-{n}", "main") for n in range(9)]
        packs.append(observed_pack("C04E-test", "main"))
        result = native_capacity(SimpleNamespace(packs=packs))
        self.assertEqual(result.pack_count, 10)
        self.assertEqual(result.capacity_kwh, 27.84)

    def test_missing_unknown_and_incomplete_are_not_zero_capacity(self):
        self.assertIsNone(native_capacity(None).pack_count)
        pack = observed_pack("Unknown-serial", "main")
        self.assertEqual(native_capacity(SimpleNamespace(packs=[pack])).reason, "unknown_pack_profile")
        self.assertIsNone(native_capacity(SimpleNamespace(packs=[pack]), 2).capacity_kwh)

    def test_stale_pack_does_not_reuse_manual_capacity(self):
        pack = observed_pack("F02N-test", "main")
        pack.soc_pct = MeasuredValue.absent(ValueValidity.STALE)
        self.assertEqual(native_capacity(SimpleNamespace(packs=[pack])).reason, "pack_data_unavailable")

    def test_internal_large_pack_is_not_mistaken_for_ab1000(self):
        self.assertEqual(pack_capacity_kwh("B000-test", "70"), 8.0)
        self.assertIsNone(pack_capacity_kwh(None, "5"))

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


class SelectorStub:
    """Only replace HA selectors; execute the real complete flow methods."""
    def __getattr__(self, name):
        if name in {"TextSelectorType", "SelectSelectorMode", "NumberSelectorMode"}:
            return SimpleNamespace(PASSWORD="password", DROPDOWN="dropdown", BOX="box")
        return lambda *args, **kwargs: (lambda value: value) if not name.endswith("Config") else kwargs


def load_flow_classes():
    source = Path(__file__).parents[1] / "custom_components/battery_smartflow_ai/config_flow.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    nodes = [node for node in tree.body if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.Assign))]
    namespace = dict(vars(const))
    namespace.update(
        vol=vol, selector=SelectorStub(),
        config_entries=SimpleNamespace(ConfigFlow=FlowBase, OptionsFlow=FlowBase),
        resolve_zendure_device=resolve_zendure_device,
        preferred_local_transport=preferred_local_transport,
        DEVICE_PROFILE_MODELS=DEVICE_PROFILE_MODELS,
        resolve_price_currency=resolve_price_currency,
        price_input_profile=price_input_profile,
        native_device_label=native_device_label,
        native_device_summary_line=native_device_summary_line,
    )
    from custom_components.battery_smartflow_ai.core.models import ZendureTransport
    namespace["ZendureTransport"] = ZendureTransport
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"), namespace)
    return namespace["ZendureSmartFlowConfigFlow"]


class NativeSetupTests(unittest.IsolatedAsyncioTestCase):
    async def test_native_selection_to_entry_needs_no_zha_hardware_entities(self):
        flow = load_flow_classes()()
        flow.hass = SimpleNamespace(config=SimpleNamespace(currency="EUR"))
        flow._native_bootstrap = await make_bootstrap()
        flow._native_options = {const.CONF_NATIVE_ZENDURE_APP_TOKEN: "private-test-token"}
        menu = await flow.async_step_user()
        self.assertEqual(menu["menu_options"][0], "native_login")
        result = await flow.async_step_native_device({
            const.CONF_NATIVE_ZENDURE_SELECTED_DEVICE: "cloud_mqtt:device-1",
            const.CONF_NATIVE_ZENDURE_CONTROL_ENABLED: True,
        })
        keys = {key.schema for key in result["data_schema"].schema}
        self.assertNotIn(const.CONF_SOC_ENTITY, keys)
        self.assertNotIn(const.CONF_PACK_CAPACITY_KWH, keys)
        self.assertNotIn(const.CONF_OUTPUT_LIMIT_ENTITY, keys)
        self.assertIn(const.CONF_PV_ENTITY, keys)
        await flow.async_step_native_external({const.CONF_PV_ENTITY: "sensor.pv", const.CONF_GRID_MODE: const.GRID_MODE_SINGLE})
        entry = await flow.async_step_grid({const.CONF_GRID_POWER_ENTITY: "sensor.grid"})
        self.assertEqual(entry["type"], "create_entry")
        self.assertEqual(entry["data"][const.CONF_DEVICE_PROFILE], "SF2400AC")
        self.assertNotIn(const.CONF_NATIVE_ZENDURE_APP_TOKEN, entry["data"])
        self.assertEqual(entry["options"][const.CONF_NATIVE_ZENDURE_APP_TOKEN], "private-test-token")

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
