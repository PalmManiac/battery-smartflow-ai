from __future__ import annotations

import unittest

from custom_components.battery_smartflow_ai.soc_sensor_grace import (
    SOC_SENSOR_GAP_GRACE_SECONDS,
    may_reuse_cached_soc_during_gap,
)


class SocSensorGraceTests(unittest.TestCase):
    def _may_reuse(self, **overrides: object) -> bool:
        values: dict[str, object] = {
            "age_seconds": 118.0,
            "automatic_mode": True,
            "active_command": True,
            "source_allows_grace": True,
            "cached_soc_pct": 60.0,
            "capacity_kwh": 5.0,
            "soc_min_pct": 10.0,
            "soc_max_pct": 100.0,
            "max_charge_w": 2_400.0,
            "max_discharge_w": 2_400.0,
        }
        values.update(overrides)
        return may_reuse_cached_soc_during_gap(**values)  # type: ignore[arg-type]

    def test_covers_the_two_minute_outage_shown_in_issue_732(self) -> None:
        self.assertEqual(SOC_SENSOR_GAP_GRACE_SECONDS, 120.0)
        self.assertTrue(self._may_reuse())

    def test_requires_active_automatic_control(self) -> None:
        self.assertFalse(self._may_reuse(automatic_mode=False))
        self.assertFalse(self._may_reuse(active_command=False))
        self.assertFalse(self._may_reuse(source_allows_grace=False))

    def test_expires_after_grace_or_rejects_impossible_age(self) -> None:
        self.assertTrue(self._may_reuse(age_seconds=120.0))
        self.assertFalse(self._may_reuse(age_seconds=120.01))
        self.assertFalse(self._may_reuse(age_seconds=-1.0))

    def test_requires_enough_soc_margin_for_worst_case_energy_movement(self) -> None:
        self.assertFalse(self._may_reuse(cached_soc_pct=10.5))
        self.assertFalse(self._may_reuse(cached_soc_pct=99.0))
        self.assertFalse(self._may_reuse(capacity_kwh=0.0))

    def test_rejects_invalid_or_non_finite_values(self) -> None:
        self.assertFalse(self._may_reuse(cached_soc_pct=101.0))
        self.assertFalse(self._may_reuse(soc_min_pct=100.0))
        self.assertFalse(self._may_reuse(max_discharge_w=0.0))
        self.assertFalse(self._may_reuse(age_seconds=float("nan")))


if __name__ == "__main__":
    unittest.main()
