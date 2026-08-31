from __future__ import annotations

import unittest

from custom_components.battery_smartflow_ai.charge_source_allocator import (
    ChargeSourceAllocator,
)


class ChargeSourceAllocatorDev8Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.allocator = ChargeSourceAllocator()

    def test_pv_covered_target_remains_total_device_input(self) -> None:
        result = self.allocator.allocate(
            charge_commit_active=True,
            allow_pv_blend=True,
            total_target_w=100.0,
            pv_w=600.0,
            house_load_w=500.0,
            max_grid_input_w=2400.0,
        )

        self.assertEqual(result.pv_allocated_w, 100.0)
        self.assertEqual(result.grid_requested_w, 0.0)
        self.assertEqual(result.device_input_w, 100.0)
        self.assertEqual(result.reason, "pv_covers_total_charge_target")

    def test_active_binding_absorbs_surplus_above_small_target(self) -> None:
        result = self.allocator.allocate(
            charge_commit_active=True,
            allow_pv_blend=True,
            total_target_w=100.0,
            pv_w=1150.0,
            house_load_w=450.0,
            max_grid_input_w=2400.0,
        )

        self.assertEqual(result.pv_available_w, 700.0)
        self.assertEqual(result.grid_requested_w, 0.0)
        self.assertEqual(result.device_input_w, 700.0)

    def test_partial_pv_uses_total_target_and_only_difference_from_grid(self) -> None:
        result = self.allocator.allocate(
            charge_commit_active=True,
            allow_pv_blend=True,
            total_target_w=1800.0,
            pv_w=1050.0,
            house_load_w=400.0,
            max_grid_input_w=2400.0,
        )

        self.assertEqual(result.pv_allocated_w, 650.0)
        self.assertEqual(result.grid_requested_w, 1150.0)
        self.assertEqual(result.device_input_w, 1800.0)

    def test_device_input_is_clamped_to_physical_limit(self) -> None:
        result = self.allocator.allocate(
            charge_commit_active=True,
            allow_pv_blend=True,
            total_target_w=3000.0,
            pv_w=4000.0,
            house_load_w=200.0,
            max_grid_input_w=2400.0,
        )

        self.assertEqual(result.device_input_w, 2400.0)

    def test_disabled_pv_blend_keeps_explicit_grid_target(self) -> None:
        result = self.allocator.allocate(
            charge_commit_active=True,
            allow_pv_blend=False,
            total_target_w=900.0,
            pv_w=1600.0,
            house_load_w=400.0,
            max_grid_input_w=2400.0,
        )

        self.assertEqual(result.pv_allocated_w, 0.0)
        self.assertEqual(result.grid_requested_w, 900.0)
        self.assertEqual(result.device_input_w, 900.0)

    def test_native_pv_has_priority_inside_total_charge_limit(self) -> None:
        result = self.allocator.allocate(
            charge_commit_active=True,
            allow_pv_blend=True,
            total_target_w=2400.0,
            pv_w=350.0,
            house_load_w=1000.0,
            max_grid_input_w=2400.0,
            native_pv_w=350.0,
            native_pv_valid=True,
        )

        self.assertEqual(result.native_pv_allocated_w, 350.0)
        self.assertEqual(result.grid_requested_w, 2050.0)
        self.assertEqual(result.device_input_w, 2050.0)
        self.assertEqual(result.pv_share_pct, 14.6)
        self.assertEqual(result.reason, "native_pv_priority_grid_fills_remainder")

    def test_native_pv_zero_is_valid_and_keeps_grid_target(self) -> None:
        result = self.allocator.allocate(
            charge_commit_active=True,
            allow_pv_blend=True,
            total_target_w=2400.0,
            pv_w=0.0,
            house_load_w=1000.0,
            max_grid_input_w=2400.0,
            native_pv_w=0.0,
            native_pv_valid=True,
        )

        self.assertEqual(result.native_pv_allocated_w, 0.0)
        self.assertEqual(result.device_input_w, 2400.0)
        self.assertEqual(result.reason, "grid_only_no_pv_surplus")

    def test_unavailable_native_pv_sensor_keeps_legacy_behavior(self) -> None:
        result = self.allocator.allocate(
            charge_commit_active=True,
            allow_pv_blend=True,
            total_target_w=2400.0,
            pv_w=350.0,
            house_load_w=1000.0,
            max_grid_input_w=2400.0,
            native_pv_w=350.0,
            native_pv_valid=False,
        )

        self.assertEqual(result.native_pv_allocated_w, 0.0)
        self.assertEqual(result.device_input_w, 2400.0)

    def test_native_pv_can_cover_complete_charge_target(self) -> None:
        result = self.allocator.allocate(
            charge_commit_active=True,
            allow_pv_blend=True,
            total_target_w=300.0,
            pv_w=0.0,
            house_load_w=0.0,
            max_grid_input_w=2400.0,
            native_pv_w=450.0,
            native_pv_valid=True,
        )

        self.assertEqual(result.native_pv_allocated_w, 300.0)
        self.assertEqual(result.grid_requested_w, 0.0)
        self.assertEqual(result.device_input_w, 0.0)
        self.assertEqual(result.reason, "native_pv_covers_total_charge_target")


if __name__ == "__main__":
    unittest.main()
