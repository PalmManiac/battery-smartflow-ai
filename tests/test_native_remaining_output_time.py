"""Behavioral tests for the native estimated battery-empty timestamp."""

import unittest
from datetime import datetime, timedelta, timezone

from support import bootstrap

bootstrap()

from custom_components.battery_smartflow_ai.remaining_output_time import (
    RemainingOutputTime,
    remaining_output_minutes,
)


class RemainingOutputMinutesTests(unittest.TestCase):
    def test_positive_estimate_is_available_during_discharge(self):
        self.assertEqual(
            remaining_output_minutes(
                381,
                200,
                estimate_available=True,
                discharge_available=True,
            ),
            381,
        )

    def test_estimate_is_unavailable_when_idle_or_charging(self):
        for discharge_power_w in (0, -200):
            with self.subTest(discharge_power_w=discharge_power_w):
                self.assertIsNone(
                    remaining_output_minutes(
                        381,
                        discharge_power_w,
                        estimate_available=True,
                        discharge_available=True,
                    )
                )

    def test_estimate_is_unavailable_when_either_measurement_is_unavailable(self):
        self.assertIsNone(
            remaining_output_minutes(
                381,
                200,
                estimate_available=False,
                discharge_available=True,
            )
        )
        self.assertIsNone(
            remaining_output_minutes(
                381,
                200,
                estimate_available=True,
                discharge_available=False,
            )
        )

    def test_zero_negative_non_numeric_and_non_finite_estimates_are_rejected(self):
        for estimate in (0, -1, "381", True, float("nan"), float("inf")):
            with self.subTest(estimate=estimate):
                self.assertIsNone(
                    remaining_output_minutes(
                        estimate,
                        200,
                        estimate_available=True,
                        discharge_available=True,
                    )
                )


class RemainingOutputTimeTests(unittest.TestCase):
    def test_timestamp_is_timezone_aware_and_based_on_minutes(self):
        now = datetime(2026, 10, 2, 10, 0, tzinfo=timezone.utc)
        result = RemainingOutputTime().timestamp(381, now=now)
        self.assertEqual(result, now + timedelta(minutes=381))
        self.assertIsNotNone(result.tzinfo)

    def test_timestamp_stays_fixed_until_reported_minutes_change(self):
        estimate = RemainingOutputTime()
        now = datetime(2026, 10, 2, 10, 0, tzinfo=timezone.utc)
        first = estimate.timestamp(381, now=now)
        repeated = estimate.timestamp(381, now=now + timedelta(seconds=30))
        self.assertEqual(repeated, first)

        changed = estimate.timestamp(380, now=now + timedelta(minutes=1))
        self.assertEqual(changed, now + timedelta(minutes=1 + 380))

    def test_losing_discharge_clears_cache_before_a_new_estimate(self):
        estimate = RemainingOutputTime()
        now = datetime(2026, 10, 2, 10, 0, tzinfo=timezone.utc)
        first_minutes = estimate.remaining_minutes(
            381,
            200,
            estimate_available=True,
            discharge_available=True,
        )
        first = estimate.timestamp(first_minutes, now=now)
        idle_minutes = estimate.remaining_minutes(
            381,
            0,
            estimate_available=True,
            discharge_available=True,
        )
        self.assertIsNone(
            estimate.timestamp(idle_minutes, now=now + timedelta(seconds=5))
        )

        resumed_minutes = estimate.remaining_minutes(
            381,
            200,
            estimate_available=True,
            discharge_available=True,
        )
        resumed = estimate.timestamp(
            resumed_minutes,
            now=now + timedelta(minutes=2),
        )
        self.assertNotEqual(resumed, first)
        self.assertEqual(resumed, now + timedelta(minutes=2 + 381))

    def test_invalid_estimate_clears_cached_timestamp(self):
        estimate = RemainingOutputTime()
        now = datetime(2026, 10, 2, 10, 0, tzinfo=timezone.utc)
        estimate.timestamp(381, now=now)
        self.assertIsNone(estimate.timestamp(0, now=now + timedelta(seconds=1)))
        self.assertEqual(
            estimate.timestamp(381, now=now + timedelta(minutes=3)),
            now + timedelta(minutes=3 + 381),
        )
