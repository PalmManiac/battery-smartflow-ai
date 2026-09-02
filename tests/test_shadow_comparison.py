"""Read-only V5 native-to-Z-HA shadow comparison contracts."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.core.models import (  # noqa: E402
    MeasuredValue,
    ValueValidity,
)
from custom_components.battery_smartflow_ai.core.shadow_comparison import (  # noqa: E402
    ShadowBinding,
    ShadowComparator,
    ShadowComparisonStatus,
    ShadowDeviceSnapshot,
    ShadowFieldRule,
    ShadowPackSnapshot,
    ShadowValue,
)


NOW = datetime(2026, 9, 2, 16, 0, tzinfo=timezone.utc)


def value(
    raw,
    *,
    at=NOW,
    unit=None,
    derived=False,
    validity=ValueValidity.VALID,
):
    measurement = (
        MeasuredValue.available(raw, observed_at=at)
        if validity is ValueValidity.VALID
        else MeasuredValue.absent(validity, observed_at=at)
    )
    return ShadowValue(measurement, unit=unit, derived=derived)


def pack(pack_id, **values):
    return ShadowPackSnapshot(pack_id, values)


def device(system_id, values=None, packs=None):
    return ShadowDeviceSnapshot(system_id, values or {}, packs or {})


def compare(native_values, reference_values, *, rules=None):
    comparator = ShadowComparator(rules)
    report = comparator.compare_device(
        device("native-1", native_values),
        device("zha-1", reference_values),
        ShadowBinding("native-1", "zha-1", {}),
    )
    return {item.field: item for item in report.comparisons}


class ShadowFieldComparisonTests(unittest.TestCase):
    def test_identical_and_valid_zero_are_compared(self):
        result = compare(
            {"soc_pct": value(0.0, unit="%")},
            {"soc_pct": value(0.0, unit="%")},
        )["soc_pct"]
        self.assertIs(result.status, ShadowComparisonStatus.IDENTICAL)
        self.assertEqual(result.native_value, 0.0)

    def test_explicit_evidence_based_tolerance_is_applied(self):
        result = compare(
            {"soc_pct": value(50.4, unit="%")},
            {"soc_pct": value(50.0, unit="%")},
            rules={"soc_pct": ShadowFieldRule(absolute_tolerance=0.5)},
        )["soc_pct"]
        self.assertIs(result.status, ShadowComparisonStatus.WITHIN_TOLERANCE)

    def test_no_tolerance_is_guessed(self):
        result = compare(
            {"soc_pct": value(50.1, unit="%")},
            {"soc_pct": value(50.0, unit="%")},
        )["soc_pct"]
        self.assertIs(result.status, ShadowComparisonStatus.MISMATCH)

    def test_noncomparable_timestamp_gap_is_classified_separately(self):
        result = compare(
            {"charge_power_w": value(500.0, at=NOW, unit="W")},
            {
                "charge_power_w": value(
                    100.0,
                    at=NOW - timedelta(seconds=12),
                    unit="W",
                )
            },
            rules={
                "charge_power_w": ShadowFieldRule(
                    absolute_tolerance=10,
                    max_time_delta_seconds=5,
                )
            },
        )["charge_power_w"]
        self.assertIs(
            result.status,
            ShadowComparisonStatus.TIME_SHIFT_PLAUSIBLE,
        )
        self.assertEqual(result.time_delta_seconds, 12)

    def test_missing_and_unsupported_are_distinct(self):
        result = compare(
            {
                "native_missing": value(
                    None,
                    validity=ValueValidity.NEVER_RECEIVED,
                ),
                "unsupported": value(
                    None,
                    validity=ValueValidity.UNSUPPORTED,
                ),
                "reference_missing": value(4),
            },
            {
                "native_missing": value(4),
                "reference_missing": value(
                    None,
                    validity=ValueValidity.UNKNOWN,
                ),
                "unsupported": value(4),
            },
        )
        self.assertIs(
            result["native_missing"].status,
            ShadowComparisonStatus.NATIVE_MISSING,
        )
        self.assertIs(
            result["reference_missing"].status,
            ShadowComparisonStatus.REFERENCE_MISSING,
        )
        self.assertIs(
            result["unsupported"].status,
            ShadowComparisonStatus.UNSUPPORTED,
        )

    def test_native_extra_information_is_not_an_error(self):
        result = compare(
            {"native_pv_input_4_w": value(700, unit="W")},
            {},
        )["native_pv_input_4_w"]
        self.assertIs(result.status, ShadowComparisonStatus.NATIVE_ONLY)

    def test_derived_zha_value_is_not_a_required_native_property(self):
        result = compare(
            {},
            {"next_calibration": value("2026-10-01", derived=True)},
        )["next_calibration"]
        self.assertIs(
            result.status,
            ShadowComparisonStatus.DERIVED_REFERENCE_ONLY,
        )

    def test_type_unit_sign_and_scale_errors_are_classified(self):
        result = compare(
            {
                "type": value("500", unit="W"),
                "unit": value(500, unit="W"),
                "sign": value(-500, unit="W"),
                "scale": value(5000, unit="W"),
            },
            {
                "type": value(500, unit="W"),
                "unit": value(0.5, unit="kW"),
                "sign": value(500, unit="W"),
                "scale": value(500, unit="W"),
            },
        )
        self.assertIs(result["type"].status, ShadowComparisonStatus.TYPE_MISMATCH)
        self.assertIs(result["unit"].status, ShadowComparisonStatus.UNIT_MISMATCH)
        self.assertIs(result["sign"].status, ShadowComparisonStatus.SIGN_MISMATCH)
        self.assertIs(result["scale"].status, ShadowComparisonStatus.SCALE_MISMATCH)


class ShadowIdentityAndReportTests(unittest.TestCase):
    def test_multiple_devices_are_compared_only_by_explicit_binding(self):
        native = {
            "native-a": device("native-a", {"soc_pct": value(20)}),
            "native-b": device("native-b", {"soc_pct": value(80)}),
        }
        reference = {
            "zha-a": device("zha-a", {"soc_pct": value(80)}),
            "zha-b": device("zha-b", {"soc_pct": value(20)}),
        }
        reports = ShadowComparator().compare_many(
            native,
            reference,
            (
                ShadowBinding("native-a", "zha-b", {}),
                ShadowBinding("native-b", "zha-a", {}),
            ),
        )
        self.assertEqual(len(reports), 2)
        self.assertEqual([item.mismatches for item in reports], [0, 0])

    def test_pack_order_cannot_affect_explicit_stable_mapping(self):
        native = device(
            "native-1",
            packs={
                "native-pack-a": pack("native-pack-a", soc_pct=value(30)),
                "native-pack-b": pack("native-pack-b", soc_pct=value(70)),
            },
        )
        reference = device(
            "zha-1",
            packs={
                "zha-pack-b": pack("zha-pack-b", soc_pct=value(70)),
                "zha-pack-a": pack("zha-pack-a", soc_pct=value(30)),
            },
        )
        report = ShadowComparator().compare_device(
            native,
            reference,
            ShadowBinding(
                "native-1",
                "zha-1",
                {
                    "native-pack-a": "zha-pack-a",
                    "native-pack-b": "zha-pack-b",
                },
            ),
        )
        self.assertEqual(report.within_tolerance, 2)
        self.assertEqual(report.mismatches, 0)
        self.assertEqual(
            {item.scope for item in report.comparisons},
            {"pack:native-pack-a", "pack:native-pack-b"},
        )

    def test_unmapped_packs_are_not_guessed_by_position(self):
        native = device(
            "native-1",
            packs={"native-pack": pack("native-pack", soc_pct=value(50))},
        )
        reference = device(
            "zha-1",
            packs={"zha-pack": pack("zha-pack", soc_pct=value(50))},
        )
        report = ShadowComparator().compare_device(
            native,
            reference,
            ShadowBinding("native-1", "zha-1", {}),
        )
        self.assertEqual(report.compared_fields, 0)

    def test_duplicate_or_missing_bindings_are_rejected(self):
        native = {"native": device("native")}
        reference = {"zha": device("zha")}
        with self.assertRaisesRegex(ValueError, "unique"):
            ShadowComparator().compare_many(
                native,
                reference,
                (
                    ShadowBinding("native", "zha", {}),
                    ShadowBinding("native", "other", {}),
                ),
            )
        with self.assertRaisesRegex(ValueError, "missing"):
            ShadowComparator().compare_many(
                native,
                reference,
                (ShadowBinding("unknown", "zha", {}),),
            )

    def test_report_has_compact_statistics(self):
        report = ShadowComparator(
            {"power_w": ShadowFieldRule(5, 2)}
        ).compare_device(
            device(
                "native",
                {
                    "exact": value(1),
                    "power_w": value(104, unit="W"),
                    "bad": value(9),
                    "extra": value(2),
                },
            ),
            device(
                "zha",
                {
                    "exact": value(1),
                    "power_w": value(100, unit="W"),
                    "bad": value(8),
                },
            ),
            ShadowBinding("native", "zha", {}),
        )
        self.assertEqual(report.compared_fields, 4)
        self.assertEqual(report.within_tolerance, 2)
        self.assertEqual(report.mismatches, 1)
        self.assertEqual(report.last_mismatch.field, "bad")
        self.assertEqual(
            report.status_counts[ShadowComparisonStatus.NATIVE_ONLY],
            1,
        )

    def test_shadow_module_has_no_native_write_surface(self):
        source = Path(
            "custom_components/battery_smartflow_ai/core/shadow_comparison.py"
        ).read_text(encoding="utf-8")
        for forbidden in (
            "DeviceCommand",
            "DeviceBackend",
            "async_execute",
            "publish(",
            "set_input_limit",
            "set_output_limit",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
