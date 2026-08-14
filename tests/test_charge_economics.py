"""Regression tests for PV opportunity-cost accounting."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.charge_economics import (  # noqa: E402
    add_charge_evidence,
    classify_charge_pricing,
    pricing_from_charge_evidence,
    resolve_feed_in_tariff,
)


NOW = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)


class ChargeEconomicsTests(unittest.TestCase):
    def test_config_data_tariff_overrides_stale_zero_option(self) -> None:
        self.assertEqual(
            resolve_feed_in_tariff(
                data={"feed_in_tariff": 0.1221},
                options={"feed_in_tariff": 0.0},
            ),
            0.1221,
        )

    def test_legacy_options_tariff_remains_supported_without_data_key(self) -> None:
        self.assertEqual(
            resolve_feed_in_tariff(
                data={},
                options={"feed_in_tariff": 0.1221},
            ),
            0.1221,
        )

    def test_pv_surplus_uses_feed_in_tariff_as_opportunity_cost(self) -> None:
        pricing = classify_charge_pricing(
            grid_import_w=0.0,
            grid_export_w=120.0,
            decision_charge_w=1800.0,
            decision_ac_mode="input",
            price_now=0.31,
            feed_in_tariff=0.122,
            battery_charge_w=1760.0,
            decision_reason="pv_surplus_charge",
        )

        self.assertTrue(pricing.active)
        self.assertFalse(pricing.is_grid_charge)
        self.assertAlmostEqual(pricing.price_eur_kwh, 0.122)
        self.assertEqual(pricing.source, "pv_surplus_export")
        self.assertEqual(pricing.grid_part_w, 0.0)
        self.assertEqual(pricing.pv_part_w, 1760.0)

    def test_pv_surplus_ignores_insignificant_import_pulse(self) -> None:
        pricing = classify_charge_pricing(
            grid_import_w=80.0,
            grid_export_w=0.0,
            decision_charge_w=1800.0,
            decision_ac_mode="input",
            price_now=0.31,
            feed_in_tariff=0.122,
            battery_charge_w=1760.0,
            decision_reason="pv_surplus_charge",
        )

        self.assertTrue(pricing.active)
        self.assertFalse(pricing.is_grid_charge)
        self.assertAlmostEqual(pricing.price_eur_kwh, 0.122)
        self.assertEqual(pricing.source, "pv_or_free_low_import")
        self.assertEqual(pricing.grid_part_w, 0.0)
        self.assertEqual(pricing.pv_part_w, 1760.0)

    def test_price_charge_does_not_use_pv_surplus_tolerance(self) -> None:
        pricing = classify_charge_pricing(
            grid_import_w=80.0,
            grid_export_w=0.0,
            decision_charge_w=1800.0,
            decision_ac_mode="input",
            price_now=0.31,
            feed_in_tariff=0.122,
            battery_charge_w=1760.0,
            decision_reason="valley_opportunity_charge",
        )

        self.assertTrue(pricing.active)
        self.assertFalse(pricing.is_grid_charge)
        self.assertEqual(pricing.source, "mixed_grid_pv_charge")
        self.assertAlmostEqual(
            pricing.price_eur_kwh,
            ((80.0 * 0.31) + (1680.0 * 0.122)) / 1760.0,
        )
        self.assertEqual(pricing.grid_part_w, 80.0)
        self.assertEqual(pricing.pv_part_w, 1680.0)

    def test_pv_surplus_still_prices_material_grid_share(self) -> None:
        pricing = classify_charge_pricing(
            grid_import_w=400.0,
            grid_export_w=0.0,
            decision_charge_w=1800.0,
            decision_ac_mode="input",
            price_now=0.31,
            feed_in_tariff=0.122,
            battery_charge_w=1760.0,
            decision_reason="pv_surplus_charge",
        )

        self.assertTrue(pricing.active)
        self.assertTrue(pricing.is_grid_charge)
        self.assertEqual(pricing.source, "mixed_grid_pv_charge")
        self.assertAlmostEqual(
            pricing.price_eur_kwh,
            ((400.0 * 0.31) + (1360.0 * 0.122)) / 1760.0,
        )
        self.assertEqual(pricing.grid_part_w, 400.0)
        self.assertEqual(pricing.pv_part_w, 1360.0)

    def test_unconfigured_tariff_preserves_zero_cost_fallback(self) -> None:
        pricing = classify_charge_pricing(
            grid_import_w=0.0,
            grid_export_w=100.0,
            decision_charge_w=1000.0,
            decision_ac_mode="input",
            price_now=0.30,
            feed_in_tariff=0.0,
            battery_charge_w=980.0,
            decision_reason="pv_surplus_charge",
        )

        self.assertTrue(pricing.active)
        self.assertEqual(pricing.price_eur_kwh, 0.0)

    def test_mixed_charge_uses_weighted_grid_and_pv_price(self) -> None:
        pricing = classify_charge_pricing(
            grid_import_w=400.0,
            grid_export_w=0.0,
            decision_charge_w=1000.0,
            decision_ac_mode="input",
            price_now=0.30,
            feed_in_tariff=0.12,
            battery_charge_w=1000.0,
            decision_reason="valley_opportunity_charge",
        )

        self.assertTrue(pricing.active)
        self.assertTrue(pricing.is_grid_charge)
        self.assertEqual(pricing.source, "mixed_grid_pv_charge")
        self.assertAlmostEqual(pricing.price_eur_kwh, 0.192)
        self.assertEqual(pricing.grid_part_w, 400.0)
        self.assertEqual(pricing.pv_part_w, 600.0)

    def test_negative_grid_price_is_not_lost_in_pending_evidence(self) -> None:
        pricing = classify_charge_pricing(
            grid_import_w=1000.0,
            grid_export_w=0.0,
            decision_charge_w=1000.0,
            decision_ac_mode="input",
            price_now=-0.05,
            feed_in_tariff=0.12,
            battery_charge_w=1000.0,
            decision_reason="valley_opportunity_charge",
        )
        evidence = add_charge_evidence(
            None,
            pricing=pricing,
            duration_seconds=10.0,
            now=NOW,
        )
        delayed_pricing = pricing_from_charge_evidence(
            evidence,
            now=NOW + timedelta(seconds=10),
        )

        self.assertIsNotNone(delayed_pricing)
        assert delayed_pricing is not None
        self.assertAlmostEqual(delayed_pricing.price_eur_kwh, -0.05)

    def test_delayed_soc_delta_keeps_preceding_pv_price_evidence(self) -> None:
        pricing = classify_charge_pricing(
            grid_import_w=0.0,
            grid_export_w=80.0,
            decision_charge_w=1200.0,
            decision_ac_mode="input",
            price_now=0.28,
            feed_in_tariff=0.122,
            battery_charge_w=1160.0,
            decision_reason="pv_surplus_charge",
        )

        evidence = add_charge_evidence(
            None,
            pricing=pricing,
            duration_seconds=10.0,
            now=NOW,
        )
        evidence = add_charge_evidence(
            evidence,
            pricing=pricing,
            duration_seconds=10.0,
            now=NOW + timedelta(seconds=10),
        )

        delayed_pricing = pricing_from_charge_evidence(
            evidence,
            now=NOW + timedelta(seconds=20),
        )

        self.assertIsNotNone(delayed_pricing)
        assert delayed_pricing is not None
        self.assertAlmostEqual(delayed_pricing.price_eur_kwh, 0.122)
        self.assertEqual(delayed_pricing.source, "pv_surplus_export")
        self.assertEqual(delayed_pricing.grid_part_w, 0.0)
        self.assertAlmostEqual(delayed_pricing.pv_part_w, 1160.0)

    def test_measured_charge_survives_new_idle_decision(self) -> None:
        pricing = classify_charge_pricing(
            grid_import_w=0.0,
            grid_export_w=50.0,
            decision_charge_w=0.0,
            decision_ac_mode="idle",
            price_now=0.25,
            feed_in_tariff=0.122,
            battery_charge_w=240.0,
            decision_reason="idle",
        )

        self.assertTrue(pricing.active)
        self.assertAlmostEqual(pricing.price_eur_kwh, 0.122)
        self.assertEqual(pricing.pv_part_w, 240.0)


if __name__ == "__main__":
    unittest.main()
