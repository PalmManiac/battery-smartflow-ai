"""Exercise optional price fields in the sensor assignment options flow."""

import unittest

from test_native_beta2 import load_flow_namespace


def make_flow():
    namespace = load_flow_namespace()
    namespace.update(
        ENERGY_GRID_MODE_NONE="none",
        ENERGY_GRID_MODE_SIGNED="signed",
        ENERGY_GRID_MODE_SPLIT="split",
    )
    flow = namespace["ZendureSmartFlowOptionsFlow"]()
    flow._group_choices = list
    flow._energy_scope_config = lambda: {"scopes": {}}
    return flow


class SensorAssignmentOptionsTests(unittest.IsolatedAsyncioTestCase):
    async def test_empty_prices_are_not_injected_into_new_or_existing_forms(self):
        flow = make_flow()
        for current in ({}, {"price_entity": "", "export_price_entity": ""}):
            result = flow._energy_scope_schema(current)(
                {"name": "Home", "grid_mode": "none"}
            )
            self.assertNotIn("price_entity", result)
            self.assertNotIn("export_price_entity", result)

    async def test_edit_suggests_existing_prices_without_restoring_cleared_values(self):
        flow = make_flow()
        flow._draft_energy_scope = {
            "price_entity": "sensor.buy_price",
            "export_price_entity": "sensor.sell_price",
            "group_ids": ["home"],
            "pv_sources": [],
        }
        flow._active_energy_scope_id = "scope"
        schema = flow._energy_scope_schema(flow._draft_energy_scope)
        keys = {key.schema: key for key in schema.schema}
        self.assertEqual(keys["price_entity"].description["suggested_value"], "sensor.buy_price")
        self.assertEqual(keys["export_price_entity"].description["suggested_value"], "sensor.sell_price")
        values = schema({"name": "Home", "grid_mode": "none", "price_entity": "sensor.buy_price"})
        self.assertNotIn("export_price_entity", values)
        await flow.async_step_energy_scope_edit(values)
        self.assertEqual(flow._draft_energy_scope["price_entity"], "sensor.buy_price")
        self.assertEqual(flow._draft_energy_scope["export_price_entity"], "")
        self.assertEqual(flow._draft_energy_scope["group_ids"], ["home"])


if __name__ == "__main__":
    unittest.main()
