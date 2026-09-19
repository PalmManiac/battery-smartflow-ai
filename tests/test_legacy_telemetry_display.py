"""Regression coverage for sparse Legacy MQTT presentation values."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import unittest

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.core.models import (  # noqa: E402
    MeasuredValue,
    ValueValidity,
    ZendureTransport,
)
from custom_components.battery_smartflow_ai.native_device_overview import (  # noqa: E402
    LEGACY_DISPLAY_RETENTION_SECONDS,
    legacy_display_retains_stale_value,
)


class LegacyTelemetryDisplayTests(unittest.TestCase):
    def _parent(self, last_message_at, transports, profile_key="Hyper 2000"):
        return SimpleNamespace(
            available_transports=transports,
            last_message_at=last_message_at,
            profile_key=profile_key,
        )

    def test_cloud_legacy_telemetry_keeps_stale_value_visible(self) -> None:
        now = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)
        parent = self._parent(
            now - timedelta(seconds=120),
            (ZendureTransport.CLOUD_MQTT,),
        )
        measured = MeasuredValue(
            value=55.0,
            validity=ValueValidity.STALE,
            observed_at=now - timedelta(seconds=200),
        )

        self.assertTrue(legacy_display_retains_stale_value(parent, measured, now=now))

    def test_stale_value_stays_unavailable_after_legacy_liveness_expires(self) -> None:
        now = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)
        parent = self._parent(
            now - timedelta(
                seconds=LEGACY_DISPLAY_RETENTION_SECONDS + 1
            ),
            (ZendureTransport.CLOUD_MQTT,),
        )
        measured = MeasuredValue(
            value=55.0,
            validity=ValueValidity.STALE,
            observed_at=now - timedelta(seconds=400),
        )

        self.assertFalse(legacy_display_retains_stale_value(parent, measured, now=now))

    def test_non_legacy_devices_do_not_retain_stale_values(self) -> None:
        now = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)
        parent = self._parent(
            now,
            (ZendureTransport.ZENSDK,),
            profile_key="SF2400AC",
        )
        measured = MeasuredValue(
            value=55.0,
            validity=ValueValidity.STALE,
            observed_at=now - timedelta(seconds=200),
        )

        self.assertFalse(legacy_display_retains_stale_value(parent, measured, now=now))


if __name__ == "__main__":
    unittest.main()
