from __future__ import annotations

import unittest

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.native_statistics import (  # noqa: E402
    NativeEnergyAccumulator,
    derived_statistics,
    roundtrip_efficiency_pct,
)


class NativeStatisticsTests(unittest.TestCase):
    def test_accumulator_integrates_and_restores(self):
        accumulator = NativeEnergyAccumulator()
        accumulator.add(
            timestamp=100, charge_power_w=3600, discharge_power_w=0,
            pv_power_w=7200,
        )
        accumulator.add(
            timestamp=110, charge_power_w=3600, discharge_power_w=1800,
            pv_power_w=7200,
        )
        restored = NativeEnergyAccumulator.from_dict(accumulator.as_dict())
        self.assertAlmostEqual(restored.charged_kwh, 0.01)
        self.assertAlmostEqual(restored.discharged_kwh, 0.005)
        self.assertAlmostEqual(restored.pv_energy_kwh, 0.02)

    def test_pv_accumulator_is_independent_from_battery_measurements(self):
        accumulator = NativeEnergyAccumulator()
        accumulator.add(
            timestamp=100, charge_power_w=None, discharge_power_w=None,
            pv_power_w=3600,
        )
        accumulator.add(
            timestamp=110, charge_power_w=None, discharge_power_w=None,
            pv_power_w=3600,
        )
        self.assertAlmostEqual(accumulator.pv_energy_kwh, 0.01)
        self.assertIsNone(accumulator.last_charge_timestamp)
        self.assertIsNone(accumulator.last_discharge_timestamp)

    def test_discharge_continues_when_charge_measurement_is_stale(self):
        accumulator = NativeEnergyAccumulator()
        accumulator.add(timestamp=100, charge_power_w=None, discharge_power_w=3600)
        accumulator.add(timestamp=110, charge_power_w=None, discharge_power_w=3600)
        self.assertAlmostEqual(accumulator.discharged_kwh, 0.01)
        self.assertEqual(accumulator.charged_kwh, 0.0)
        restored = NativeEnergyAccumulator.from_dict(accumulator.as_dict())
        restored.add(timestamp=120, charge_power_w=None, discharge_power_w=3600)
        self.assertAlmostEqual(restored.discharged_kwh, 0.02)

    def test_invalid_channel_does_not_bridge_gap_or_block_other_channel(self):
        accumulator = NativeEnergyAccumulator()
        accumulator.add(timestamp=100, charge_power_w=3600, discharge_power_w=3600)
        accumulator.add(timestamp=110, charge_power_w=None, discharge_power_w=3600)
        accumulator.add(timestamp=120, charge_power_w=3600, discharge_power_w=3600)
        self.assertAlmostEqual(accumulator.charged_kwh, 0.0)
        self.assertAlmostEqual(accumulator.discharged_kwh, 0.02)
        accumulator.add(timestamp=130, charge_power_w=3600, discharge_power_w=None)
        self.assertAlmostEqual(accumulator.charged_kwh, 0.01)
        self.assertAlmostEqual(accumulator.discharged_kwh, 0.02)

    def test_legacy_timestamp_does_not_bridge_unknown_channel_state(self):
        restored = NativeEnergyAccumulator.from_dict({
            "charged_kwh": 1.0,
            "discharged_kwh": 2.0,
            "last_timestamp": 100,
        })
        restored.add(timestamp=110, charge_power_w=None, discharge_power_w=3600)
        self.assertEqual(restored.discharged_kwh, 2.0)

    def test_device_without_pv_does_not_publish_a_false_zero_total(self):
        accumulator = NativeEnergyAccumulator()
        accumulator.add(timestamp=100, charge_power_w=500, discharge_power_w=0)
        self.assertNotIn("pv_energy_kwh", accumulator.as_dict())

    def test_accumulator_does_not_bridge_offline_gap(self):
        accumulator = NativeEnergyAccumulator()
        accumulator.add(timestamp=100, charge_power_w=3600, discharge_power_w=0)
        accumulator.add(timestamp=1000, charge_power_w=3600, discharge_power_w=0)
        self.assertEqual(accumulator.charged_kwh, 0.0)

    def test_roundtrip_requires_positive_charge_and_limits_display(self):
        self.assertEqual(roundtrip_efficiency_pct(10, 8.56), 85.6)
        self.assertIsNone(roundtrip_efficiency_pct(0, 0))
        self.assertEqual(roundtrip_efficiency_pct(10, 12), 100.0)

    def test_available_energy_and_estimated_switch_count(self):
        stats = derived_statistics(soc_pct=50, capacity_kwh=5.76, switch_count=7)
        self.assertEqual(stats.available_energy_kwh, 2.88)
        self.assertEqual(stats.switch_count, 7)
        self.assertTrue(stats.switch_count_is_estimate)

    def test_invalid_inputs_are_unknown(self):
        stats = derived_statistics(
            soc_pct="unknown",
            capacity_kwh=5.76,
            charged_kwh=0,
            discharged_kwh=1,
        )
        self.assertIsNone(stats.available_energy_kwh)
        self.assertIsNone(stats.roundtrip_efficiency_pct)
