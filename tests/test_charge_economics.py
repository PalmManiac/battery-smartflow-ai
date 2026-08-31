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
    trade_soc_min_reset_state,
)


NOW = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)


class ChargeEconomicsTests(unittest.TestCase):
    def test_single_transient_zero_soc_does_not_confirm_trade_reset(self) -> None:
        count, confirmed = trade_soc_min_reset_state(
            soc=0.0,
            soc_min=5.0,
            previous_count=0,
            previously_confirmed=False,
        )

        self.assertEqual(count, 1)
        self.assertFalse(confirmed)

        count, confirmed = trade_soc_min_reset_state(
            soc=55.0,
            soc_min=5.0,
            previous_count=count,
            previously_confirmed=confirmed,
        )

        self.assertEqual(count, 0)
        self.assertFalse(confirmed)

    def test_sustained_soc_min_confirms_trade_reset(self) -> None:
        count = 0
        confirmed = False

        for expected_count in (1, 2, 3):
            count, confirmed = trade_soc_min_reset_state(
                soc=5.0,
                soc_min=5.0,
                previous_count=count,
                previously_confirmed=confirmed,
            )
            self.assertEqual(count, expected_count)
            self.assertEqual(confirmed, expected_count == 3)

    def test_confirmed_trade_reset_clears_after_soc_recovers(self) -> None:
        count, confirmed = trade_soc_min_reset_state(
            soc=12.0,
            soc_min=5.0,
            previous_count=3,
            previously_confirmed=True,
        )

        self.assertEqual(count, 0)
        self.assertFalse(confirmed)

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
        self.assertAlmostEqual(pricing.price_per_kwh, 0.122)
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
        self.assertAlmostEqual(pricing.price_per_kwh, 0.122)
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
            pricing.price_per_kwh,
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
            pricing.price_per_kwh,
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
        self.assertEqual(pricing.price_per_kwh, 0.0)

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
        self.assertAlmostEqual(pricing.price_per_kwh, 0.192)
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
        self.assertAlmostEqual(delayed_pricing.price_per_kwh, -0.05)

    def test_legacy_eur_named_evidence_is_read_without_conversion(self) -> None:
        legacy_evidence = {
            "energy_wh": 1000.0,
            "cost_eur": 2.2,
            "grid_energy_wh": 1000.0,
            "pv_energy_wh": 0.0,
            "duration_seconds": 3600.0,
            "source": "grid_charge",
            "updated_at": NOW.isoformat(),
        }

        delayed_pricing = pricing_from_charge_evidence(
            legacy_evidence,
            now=NOW + timedelta(seconds=10),
        )

        self.assertIsNotNone(delayed_pricing)
        assert delayed_pricing is not None
        self.assertAlmostEqual(delayed_pricing.price_per_kwh, 2.2)

        updated_evidence = add_charge_evidence(
            legacy_evidence,
            pricing=delayed_pricing,
            duration_seconds=10.0,
            now=NOW + timedelta(seconds=10),
        )
        self.assertIsNotNone(updated_evidence)
        assert updated_evidence is not None
        self.assertIn("cost", updated_evidence)
        self.assertNotIn("cost_eur", updated_evidence)

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
        self.assertAlmostEqual(delayed_pricing.price_per_kwh, 0.122)
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
        self.assertAlmostEqual(pricing.price_per_kwh, 0.122)
        self.assertEqual(pricing.pv_part_w, 240.0)

    def test_native_pv_is_not_priced_as_grid_during_house_import(self) -> None:
        pricing = classify_charge_pricing(
            grid_import_w=5000.0,
            grid_export_w=0.0,
            decision_charge_w=2050.0,
            decision_ac_mode="input",
            price_now=0.20,
            feed_in_tariff=0.0,
            battery_charge_w=2400.0,
            decision_reason="charge_commit_active",
            native_pv_w=350.0,
            native_pv_valid=True,
        )

        self.assertEqual(pricing.grid_part_w, 2050.0)
        self.assertEqual(pricing.pv_part_w, 350.0)
        self.assertEqual(pricing.source, "mixed_grid_pv_charge")


if __name__ == "__main__":
    unittest.main()
