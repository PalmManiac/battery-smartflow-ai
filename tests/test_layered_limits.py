"""Tests for transport-neutral layered power and SoC limits."""

from __future__ import annotations

import unittest

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.core.models import (  # noqa: E402
    ControlBlocker,
    DirectionLimitRequest,
    LimitLayer,
    MeasuredValue,
    NamedLimit,
    NativeControlGate,
    PowerDirection,
    SocLimitRequest,
    ValueValidity,
    resolve_native_command_limits,
    resolve_power_limit,
    resolve_soc_limits,
)


def valid(value):
    return MeasuredValue.available(value)


def absent(validity):
    return MeasuredValue.absent(validity)


def request(
    direction=PowerDirection.CHARGE,
    *,
    profile=2400.0,
    strategy=2000.0,
    device=(),
    dynamic=(),
):
    return DirectionLimitRequest(
        direction=direction,
        profile_limit_w=profile,
        strategy_target_w=strategy,
        device_limits=device,
        dynamic_limits=dynamic,
    )


def safe_gate(**changes):
    values = {
        "profile_approved": True,
        "transport_available": True,
        "online": valid(True),
        "hems_active": valid(False),
        "protection_active": valid(False),
    }
    values.update(changes)
    return NativeControlGate(**values)


class LayeredPowerLimitTests(unittest.TestCase):
    def test_profile_limit_can_be_lower_than_reported_device_limit(self):
        result = resolve_power_limit(
            request(
                profile=1800,
                strategy=2200,
                device=(NamedLimit("reported_input", valid(2400)),),
            )
        )
        self.assertEqual(result.effective_limit_w, 1800)
        self.assertEqual(result.clamped_target_w, 1800)
        self.assertIs(result.limiting_layer, LimitLayer.PROFILE)

    def test_device_limit_can_be_lower_than_profile_limit(self):
        result = resolve_power_limit(
            request(
                strategy=2200,
                device=(NamedLimit("reported_input", valid(1600)),),
            )
        )
        self.assertEqual(result.clamped_target_w, 1600)
        self.assertIs(result.limiting_layer, LimitLayer.DEVICE)
        self.assertEqual(result.limiting_name, "reported_input")

    def test_dynamic_limit_can_be_the_smallest_limit(self):
        result = resolve_power_limit(
            request(
                strategy=2200,
                device=(NamedLimit("reported_input", valid(1800)),),
                dynamic=(NamedLimit("temperature_derating", valid(900)),),
            )
        )
        self.assertEqual(result.effective_limit_w, 900)
        self.assertIs(result.limiting_layer, LimitLayer.DYNAMIC)
        self.assertEqual(
            [item.layer for item in result.diagnostics],
            [
                LimitLayer.PROFILE,
                LimitLayer.DEVICE,
                LimitLayer.DYNAMIC,
                LimitLayer.STRATEGY,
            ],
        )

    def test_strategy_below_all_limits_is_not_clamped(self):
        result = resolve_power_limit(
            request(
                strategy=700,
                device=(NamedLimit("reported_input", valid(1800)),),
                dynamic=(NamedLimit("bms", valid(1500)),),
            )
        )
        self.assertEqual(result.clamped_target_w, 700)
        self.assertFalse(result.clamped)
        self.assertIs(result.limiting_layer, LimitLayer.STRATEGY)

    def test_charge_and_discharge_are_resolved_independently(self):
        result = resolve_native_command_limits(
            request(strategy=2200),
            request(
                PowerDirection.DISCHARGE,
                profile=800,
                strategy=1200,
            ),
            safe_gate(),
        )
        self.assertEqual(result.charge.clamped_target_w, 2200)
        self.assertEqual(result.discharge.clamped_target_w, 800)

    def test_valid_zero_device_limit_is_applied(self):
        result = resolve_power_limit(
            request(device=(NamedLimit("reported_input", valid(0)),))
        )
        self.assertEqual(result.clamped_target_w, 0)
        self.assertIs(result.limiting_layer, LimitLayer.DEVICE)

    def test_unusable_optional_runtime_limits_are_not_treated_as_zero(self):
        for validity in (
            ValueValidity.UNKNOWN,
            ValueValidity.STALE,
            ValueValidity.UNSUPPORTED,
            ValueValidity.INVALID,
            ValueValidity.OFFLINE,
        ):
            with self.subTest(validity=validity):
                result = resolve_power_limit(
                    request(
                        strategy=1000,
                        device=(NamedLimit("reported_input", absent(validity)),),
                    )
                )
                self.assertEqual(result.clamped_target_w, 1000)
                reported = next(
                    item
                    for item in result.diagnostics
                    if item.name == "reported_input"
                )
                self.assertEqual(reported.validity, validity)
                self.assertFalse(reported.applied)

    def test_unavailable_required_dynamic_limit_becomes_blocker(self):
        charge = request(
            dynamic=(
                NamedLimit(
                    "required_bms_limit",
                    absent(ValueValidity.STALE),
                    required=True,
                ),
            )
        )
        result = resolve_native_command_limits(
            charge,
            request(PowerDirection.DISCHARGE),
            safe_gate(),
        )
        self.assertIn(ControlBlocker.REQUIRED_LIMIT_UNAVAILABLE, result.blockers)
        self.assertFalse(result.command_allowed)

    def test_bad_runtime_value_cannot_raise_or_bypass_profile_limit(self):
        result = resolve_power_limit(
            request(
                profile=800,
                strategy=3000,
                device=(NamedLimit("reported_output", valid(9999)),),
            )
        )
        self.assertEqual(result.effective_limit_w, 800)
        self.assertEqual(result.clamped_target_w, 800)

    def test_hems_and_offline_remain_named_blockers_not_zero_limits(self):
        result = resolve_native_command_limits(
            request(strategy=600),
            request(PowerDirection.DISCHARGE, strategy=500),
            safe_gate(online=valid(False), hems_active=valid(True)),
        )
        self.assertEqual(result.charge.clamped_target_w, 600)
        self.assertEqual(result.discharge.clamped_target_w, 500)
        self.assertIn(ControlBlocker.DEVICE_OFFLINE, result.blockers)
        self.assertIn(ControlBlocker.HEMS_ACTIVE, result.blockers)
        self.assertFalse(result.command_allowed)

    def test_unknown_safety_states_fail_closed_with_exact_reasons(self):
        result = resolve_native_command_limits(
            request(),
            request(PowerDirection.DISCHARGE),
            safe_gate(
                online=absent(ValueValidity.OFFLINE),
                hems_active=absent(ValueValidity.NEVER_RECEIVED),
                protection_active=absent(ValueValidity.UNSUPPORTED),
            ),
        )
        self.assertEqual(
            result.blockers,
            (
                ControlBlocker.DEVICE_OFFLINE,
                ControlBlocker.HEMS_UNKNOWN,
                ControlBlocker.PROTECTION_UNKNOWN,
            ),
        )

    def test_unapproved_profile_and_transport_are_explicit_blockers(self):
        result = resolve_native_command_limits(
            request(),
            request(PowerDirection.DISCHARGE),
            safe_gate(profile_approved=False, transport_available=False),
        )
        self.assertIn(ControlBlocker.PROFILE_NOT_APPROVED, result.blockers)
        self.assertIn(ControlBlocker.TRANSPORT_UNAVAILABLE, result.blockers)


class LayeredSocLimitTests(unittest.TestCase):
    def test_soc_layers_use_highest_floor_and_lowest_ceiling(self):
        result = resolve_soc_limits(
            SocLimitRequest(
                profile_min_pct=0,
                profile_max_pct=100,
                strategy_min_pct=10,
                strategy_max_pct=90,
                device_min_pct=valid(5),
                device_max_pct=valid(85),
                dynamic_min_pct=valid(20),
                dynamic_max_pct=valid(80),
            )
        )
        self.assertEqual((result.min_pct, result.max_pct), (20, 80))
        self.assertIs(result.min_layer, LimitLayer.DYNAMIC)
        self.assertIs(result.max_layer, LimitLayer.DYNAMIC)
        self.assertTrue(result.valid)

    def test_absent_runtime_soc_limits_do_not_become_zero(self):
        result = resolve_soc_limits(
            SocLimitRequest(
                profile_min_pct=0,
                profile_max_pct=100,
                strategy_min_pct=15,
                strategy_max_pct=90,
                device_min_pct=absent(ValueValidity.UNKNOWN),
                device_max_pct=absent(ValueValidity.STALE),
                dynamic_min_pct=absent(ValueValidity.UNSUPPORTED),
                dynamic_max_pct=absent(ValueValidity.INVALID),
            )
        )
        self.assertEqual((result.min_pct, result.max_pct), (15, 90))
        self.assertTrue(result.valid)

    def test_conflicting_soc_layers_are_reported_invalid(self):
        result = resolve_soc_limits(
            SocLimitRequest(
                profile_min_pct=0,
                profile_max_pct=100,
                strategy_min_pct=10,
                strategy_max_pct=90,
                device_min_pct=valid(95),
                device_max_pct=valid(80),
                dynamic_min_pct=absent(ValueValidity.UNSUPPORTED),
                dynamic_max_pct=absent(ValueValidity.UNSUPPORTED),
            )
        )
        self.assertFalse(result.valid)


if __name__ == "__main__":
    unittest.main()
