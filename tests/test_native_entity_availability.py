"""Tests for optional transport-dependent native Zendure entities."""

import unittest
from types import SimpleNamespace

from support import bootstrap

bootstrap()

from custom_components.battery_smartflow_ai.core.models import (
    MeasuredValue,
    ValueValidity,
)
from custom_components.battery_smartflow_ai.native_entity_availability import (
    OPTIONAL_NATIVE_MAIN_SENSOR_KEYS,
    optional_native_main_sensor_available,
    optional_native_sensor_registry_action,
)


class OptionalNativeMainSensorAvailabilityTests(unittest.TestCase):
    def test_firmware_requires_an_observed_firmware_value(self):
        system = SimpleNamespace(
            firmware=MeasuredValue.available("4354"),
            measurements={},
        )
        self.assertTrue(optional_native_main_sensor_available(system, "firmware"))

        system.firmware = MeasuredValue.absent(ValueValidity.MISSING)
        self.assertFalse(optional_native_main_sensor_available(system, "firmware"))

    def test_wifi_status_accepts_zero_as_a_valid_disconnected_state(self):
        system = SimpleNamespace(
            firmware=MeasuredValue.absent(ValueValidity.MISSING),
            measurements={"wifiState": MeasuredValue.available(0)},
        )
        self.assertTrue(optional_native_main_sensor_available(system, "wifi_status"))

    def test_wifi_status_requires_a_valid_observation(self):
        system = SimpleNamespace(
            firmware=MeasuredValue.absent(ValueValidity.MISSING),
            measurements={
                "wifiState": MeasuredValue.absent(ValueValidity.MISSING)
            },
        )
        self.assertFalse(optional_native_main_sensor_available(system, "wifi_status"))
        self.assertFalse(
            optional_native_main_sensor_available(
                SimpleNamespace(firmware=None, measurements={}), "wifi_status"
            )
        )

    def test_only_firmware_and_wifi_status_are_optional(self):
        self.assertEqual(
            OPTIONAL_NATIVE_MAIN_SENSOR_KEYS,
            frozenset({"firmware", "wifi_status"}),
        )
        self.assertTrue(
            optional_native_main_sensor_available(SimpleNamespace(), "soc_pct")
        )

    def test_unsupported_existing_entity_is_disabled_by_integration_at_setup(self):
        self.assertEqual(
            optional_native_sensor_registry_action(
                available=False,
                disabled_by_integration=False,
                enabled=True,
                initializing=True,
            ),
            "disable",
        )

    def test_entity_disabled_by_integration_is_reenabled_when_value_arrives(self):
        self.assertEqual(
            optional_native_sensor_registry_action(
                available=True,
                disabled_by_integration=True,
                enabled=False,
                initializing=False,
            ),
            "enable",
        )

    def test_user_disabled_entity_is_never_changed_by_integration(self):
        self.assertIsNone(
            optional_native_sensor_registry_action(
                available=True,
                disabled_by_integration=False,
                enabled=False,
                initializing=True,
            )
        )

    def test_sensor_is_not_disabled_again_after_initial_setup(self):
        self.assertIsNone(
            optional_native_sensor_registry_action(
                available=False,
                disabled_by_integration=False,
                enabled=True,
                initializing=False,
            )
        )
