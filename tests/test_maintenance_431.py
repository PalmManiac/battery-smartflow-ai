"""Regression tests for the V4.3.1 maintenance fixes."""

from __future__ import annotations

import unittest

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.battery_protection import (  # noqa: E402
    next_cell_voltage_emergency_state,
)
from custom_components.battery_smartflow_ai.device_command import (  # noqa: E402
    clamp_number_power_request,
)
from custom_components.battery_smartflow_ai.device_profiles import (  # noqa: E402
    DEVICE_PROFILES,
)


class Maintenance431Tests(unittest.TestCase):
    def test_cell_voltage_emergency_charge_stays_latched_until_resume(self) -> None:
        active = False
        states = []

        for cell_v in (3.11, 3.10, 3.12, 3.09, 3.15, 3.17, 3.18):
            active = next_cell_voltage_emergency_state(
                previously_active=active,
                protection_enabled=True,
                lowest_cell_voltage=cell_v,
                warning_voltage=3.10,
                resume_voltage=3.18,
            )
            states.append(active)

        self.assertEqual(
            states,
            [False, True, True, True, True, True, False],
        )

    def test_cell_voltage_emergency_charge_resets_when_disabled(self) -> None:
        self.assertFalse(
            next_cell_voltage_emergency_state(
                previously_active=True,
                protection_enabled=False,
                lowest_cell_voltage=3.05,
                warning_voltage=3.10,
                resume_voltage=3.18,
            )
        )

    def test_zero_stop_bypasses_positive_entity_minimum(self) -> None:
        self.assertEqual(
            clamp_number_power_request(
                0.0,
                min_value=300.0,
                max_value=2400.0,
            ),
            0,
        )

    def test_positive_request_still_uses_live_entity_limits(self) -> None:
        self.assertEqual(
            clamp_number_power_request(
                120.0,
                min_value=300.0,
                max_value=2400.0,
            ),
            300,
        )
        self.assertEqual(
            clamp_number_power_request(
                2600.0,
                min_value=300.0,
                max_value=2400.0,
            ),
            2400,
        )

    def test_ac_profiles_wait_for_strategic_pv_exit_hysteresis(self) -> None:
        for profile_key in (
            "SF2400AC",
            "SF2400AC+",
            "SF2400Pro",
            "SF3000MixAC+",
            "SF4000MixAC+",
            "SF4000MixPro",
        ):
            with self.subTest(profile=profile_key):
                self.assertGreaterEqual(
                    DEVICE_PROFILES[profile_key][
                        "PV_CHARGE_EXIT_IMPORT_CYCLES"
                    ],
                    8,
                )


if __name__ == "__main__":
    unittest.main()
