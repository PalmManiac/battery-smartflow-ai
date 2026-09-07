from __future__ import annotations

from datetime import datetime, timezone
import unittest

from custom_components.battery_smartflow_ai.core.models import (
    MeasuredValue,
    ValueValidity,
    ZendureTransport,
)
from custom_components.battery_smartflow_ai.native_read_source import (
    NativeReadSourceArbiter,
    ReadSourceStatus,
    SourceMeasurement,
)


NOW = datetime(2026, 9, 7, 10, 0, tzinfo=timezone.utc)


def source(transport, value, *, validity=ValueValidity.VALID, retained=False):
    measurement = (
        MeasuredValue.available(value, observed_at=NOW)
        if validity is ValueValidity.VALID
        else MeasuredValue.absent(validity, observed_at=NOW)
    )
    return SourceMeasurement(transport, measurement, retained)


class NativeReadSourceArbiterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.arbiter = NativeReadSourceArbiter()

    def test_callback_order_does_not_change_equal_source_selection(self) -> None:
        cloud = source(ZendureTransport.CLOUD_MQTT, 61.0)
        local = source(ZendureTransport.ZENSDK, 61.0)
        first = self.arbiter.select("soc_pct", (cloud, local))
        second = self.arbiter.select("soc_pct", (local, cloud))
        self.assertEqual(first.transport, ZendureTransport.ZENSDK)
        self.assertEqual(second.transport, ZendureTransport.ZENSDK)
        self.assertEqual(first.status, ReadSourceStatus.CONSISTENT)

    def test_valid_fallback_beats_stale_preferred_source(self) -> None:
        selected = self.arbiter.select(
            "soc_pct",
            (
                source(
                    ZendureTransport.ZENSDK,
                    None,
                    validity=ValueValidity.STALE,
                ),
                source(ZendureTransport.CLOUD_MQTT, 55.0),
            ),
        )
        self.assertEqual(selected.transport, ZendureTransport.CLOUD_MQTT)
        self.assertEqual(selected.measurement.value, 55.0)
        self.assertEqual(selected.status, ReadSourceStatus.FALLBACK)

    def test_retained_value_cannot_beat_fresh_value(self) -> None:
        selected = self.arbiter.select(
            "soc_pct",
            (
                source(ZendureTransport.LOCAL_MQTT, 40.0, retained=True),
                source(ZendureTransport.CLOUD_MQTT, 41.0),
            ),
        )
        self.assertEqual(selected.transport, ZendureTransport.CLOUD_MQTT)
        self.assertEqual(selected.measurement.value, 41.0)

    def test_fresh_safety_conflict_fails_closed(self) -> None:
        selected = self.arbiter.select(
            "hems_active",
            (
                source(ZendureTransport.ZENSDK, False),
                source(ZendureTransport.CLOUD_MQTT, True),
            ),
            safety_critical=True,
        )
        self.assertIsNone(selected.transport)
        self.assertFalse(selected.measurement.valid)
        self.assertEqual(selected.status, ReadSourceStatus.CONFLICT)

    def test_zero_is_a_valid_measurement(self) -> None:
        selected = self.arbiter.select(
            "charge_power_w",
            (source(ZendureTransport.ZENSDK, 0.0),),
        )
        self.assertTrue(selected.measurement.valid)
        self.assertEqual(selected.measurement.value, 0.0)

    def test_no_source_is_never_received(self) -> None:
        selected = self.arbiter.select("temperature_c", ())
        self.assertEqual(
            selected.measurement.validity,
            ValueValidity.NEVER_RECEIVED,
        )
        self.assertEqual(selected.status, ReadSourceStatus.UNAVAILABLE)


if __name__ == "__main__":
    unittest.main()
