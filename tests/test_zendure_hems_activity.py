"""Contracts for Cloud-MQTT HEMS activity interpretation."""

from datetime import datetime, timedelta, timezone
import unittest

from support import bootstrap

bootstrap()

from custom_components.battery_smartflow_ai.core.models import ValueValidity  # noqa: E402
from custom_components.battery_smartflow_ai.zendure_hems_activity import (  # noqa: E402
    HEMS_ACTIVITY_SOURCE,
    HemsActivityTracker,
)


NOW = datetime(2026, 9, 4, tzinfo=timezone.utc)


class HemsActivityTrackerTests(unittest.TestCase):
    def test_restart_without_activity_stays_unknown_for_full_window(self):
        tracker = HemsActivityTracker(timeout_seconds=60)
        tracker.set_monitoring(True, observed_at=NOW)
        value = tracker.measurement(now=NOW + timedelta(seconds=60))
        self.assertIsNone(value.value)
        self.assertEqual(value.validity, ValueValidity.NEVER_RECEIVED)

    def test_confirmed_quiet_subscription_can_report_inactive_after_window(self):
        tracker = HemsActivityTracker(timeout_seconds=60)
        tracker.set_monitoring(True, observed_at=NOW)
        value = tracker.measurement(now=NOW + timedelta(seconds=61))
        self.assertFalse(value.value)
        self.assertTrue(value.valid)

    def test_energy_activity_is_immediately_active_for_only_its_tracker(self):
        first = HemsActivityTracker(timeout_seconds=60)
        second = HemsActivityTracker(timeout_seconds=60)
        for tracker in (first, second):
            tracker.set_monitoring(True, observed_at=NOW)
        first.observe_energy(observed_at=NOW + timedelta(seconds=5))
        self.assertTrue(first.measurement(now=NOW + timedelta(seconds=5)).value)
        self.assertIsNone(second.measurement(now=NOW + timedelta(seconds=5)).value)

    def test_activity_remains_active_until_complete_timeout(self):
        tracker = HemsActivityTracker(timeout_seconds=60)
        tracker.set_monitoring(True, observed_at=NOW)
        tracker.observe_energy(observed_at=NOW)
        self.assertTrue(tracker.measurement(now=NOW + timedelta(seconds=60)).value)
        self.assertFalse(tracker.measurement(now=NOW + timedelta(seconds=61)).value)

    def test_transport_loss_makes_prior_activity_stale_not_inactive(self):
        tracker = HemsActivityTracker(timeout_seconds=60)
        tracker.set_monitoring(True, observed_at=NOW)
        tracker.observe_energy(observed_at=NOW)
        tracker.set_monitoring(False, observed_at=NOW + timedelta(seconds=10))
        value = tracker.measurement(now=NOW + timedelta(seconds=90))
        self.assertIsNone(value.value)
        self.assertEqual(value.validity, ValueValidity.STALE)

    def test_reconnect_starts_a_new_complete_confirmation_window(self):
        tracker = HemsActivityTracker(timeout_seconds=60)
        tracker.set_monitoring(True, observed_at=NOW)
        tracker.set_monitoring(False, observed_at=NOW + timedelta(seconds=20))
        reconnected = NOW + timedelta(seconds=100)
        tracker.set_monitoring(True, observed_at=reconnected)
        self.assertIsNone(
            tracker.measurement(now=reconnected + timedelta(seconds=30)).value
        )

    def test_diagnostics_name_exact_activity_source(self):
        tracker = HemsActivityTracker(timeout_seconds=60)
        diagnostic = tracker.diagnostics(now=NOW)
        self.assertEqual(diagnostic.source, HEMS_ACTIVITY_SOURCE)
        self.assertFalse(diagnostic.monitoring)
        self.assertIsNone(diagnostic.last_activity_at)


if __name__ == "__main__":
    unittest.main()
