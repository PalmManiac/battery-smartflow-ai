"""Regression tests for persistent economic SoC accounting."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.soc_plausibility import (  # noqa: E402
    evaluate_soc_for_accounting,
)


NOW = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)
BASE = {
    "capacity_kwh": 9.0,
    "max_charge_w": 2400.0,
    "max_discharge_w": 2400.0,
}


class SocPlausibilityTests(unittest.TestCase):
    def test_first_sample_establishes_accounting_baseline(self) -> None:
        result = evaluate_soc_for_accounting(
            raw_soc=80.0,
            previous_soc=None,
            previous_at=None,
            now=NOW,
            pending_soc=None,
            pending_count=0,
            **BASE,
        )

        self.assertTrue(result.accepted)
        self.assertEqual(result.accounting_soc, 80.0)
        self.assertEqual(result.status, "baseline")

    def test_single_impossible_drop_does_not_change_accounting_soc(self) -> None:
        result = evaluate_soc_for_accounting(
            raw_soc=1.0,
            previous_soc=90.0,
            previous_at=NOW,
            now=NOW + timedelta(seconds=10),
            pending_soc=None,
            pending_count=0,
            **BASE,
        )

        self.assertFalse(result.accepted)
        self.assertEqual(result.accounting_soc, 90.0)
        self.assertEqual(result.status, "rejected_physical_outlier")
        self.assertEqual(result.pending_soc, 1.0)
        self.assertEqual(result.pending_count, 1)

    def test_legacy_soc_without_timestamp_is_preserved_for_one_cycle(self) -> None:
        result = evaluate_soc_for_accounting(
            raw_soc=1.0,
            previous_soc=90.0,
            previous_at=None,
            now=NOW,
            pending_soc=None,
            pending_count=0,
            **BASE,
        )

        self.assertTrue(result.accepted)
        self.assertEqual(result.accounting_soc, 90.0)
        self.assertEqual(result.status, "timestamp_initialized")

    def test_consistent_discontinuity_is_eventually_accepted(self) -> None:
        first = evaluate_soc_for_accounting(
            raw_soc=1.0,
            previous_soc=90.0,
            previous_at=NOW,
            now=NOW + timedelta(seconds=10),
            pending_soc=None,
            pending_count=0,
            **BASE,
        )
        second = evaluate_soc_for_accounting(
            raw_soc=1.0,
            previous_soc=90.0,
            previous_at=NOW,
            now=NOW + timedelta(seconds=20),
            pending_soc=first.pending_soc,
            pending_count=first.pending_count,
            **BASE,
        )
        third = evaluate_soc_for_accounting(
            raw_soc=1.0,
            previous_soc=90.0,
            previous_at=NOW,
            now=NOW + timedelta(seconds=30),
            pending_soc=second.pending_soc,
            pending_count=second.pending_count,
            **BASE,
        )

        self.assertFalse(second.accepted)
        self.assertEqual(second.pending_count, 2)
        self.assertTrue(third.accepted)
        self.assertEqual(third.accounting_soc, 1.0)
        self.assertEqual(third.status, "confirmed_discontinuity")

    def test_long_gap_is_a_new_baseline(self) -> None:
        result = evaluate_soc_for_accounting(
            raw_soc=1.0,
            previous_soc=90.0,
            previous_at=NOW,
            now=NOW + timedelta(minutes=6),
            pending_soc=None,
            pending_count=0,
            **BASE,
        )

        self.assertTrue(result.accepted)
        self.assertEqual(result.status, "gap_baseline")
