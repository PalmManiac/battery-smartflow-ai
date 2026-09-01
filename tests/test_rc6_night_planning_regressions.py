"""RC6 regressions from Beat's RC5 overnight trace in Discussion #123."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.learned_planning import (  # noqa: E402
    actionable_required_charge_energy_kwh,
    build_learned_charge_plan,
    compute_window_slots,
    effective_charge_power_w,
    minimum_actionable_charge_energy_kwh,
    optimize_charge_window,
    requested_charge_power_w,
    required_window_slots,
    LearnedSlotModel,
    LearningReadiness,
)
from custom_components.battery_smartflow_ai.market_price import (  # noqa: E402
    MarketPrice,
    MarketPriceDirection,
    MarketPriceForecast,
    MarketPricePoint,
    MarketPriceValidity,
)


class Rc6NightPlanningRegressionTests(unittest.TestCase):
    def _overnight_prices(self) -> list[MarketPricePoint]:
        start = datetime(2026, 8, 25, 23, 0, tzinfo=timezone.utc)
        return [
            MarketPricePoint(
                start=start + timedelta(minutes=15 * index),
                end=start + timedelta(minutes=15 * (index + 1)),
                price=0.2386 if index < 28 else 0.3047,
            )
            for index in range(40)
        ]

    def test_equal_price_preference_is_anchored_before_latest_start(self) -> None:
        points = self._overnight_prices()
        deadline = datetime(2026, 8, 26, 9, 0, tzinfo=timezone.utc)

        starts = []
        for now in (
            datetime(2026, 8, 26, 0, 31, tzinfo=timezone.utc),
            datetime(2026, 8, 26, 1, 0, tzinfo=timezone.utc),
        ):
            selected_start, *_ = optimize_charge_window(
                now=now,
                deadline=deadline,
                price_points=points,
                window_slots=16,
            )
            starts.append(selected_start)

        self.assertEqual(starts[0], datetime(2026, 8, 26, 1, 0, tzinfo=timezone.utc))
        self.assertEqual(starts[1], starts[0])

    def test_800_w_device_limit_plans_with_720_w_net_power(self) -> None:
        net_power = effective_charge_power_w(
            profile_charge_limit_w=800.0,
            learned_typical_charge_power_w=999.0,
            current_effective_charge_cap_w=800.0,
        )

        self.assertEqual(net_power, 720.0)
        self.assertEqual(
            required_window_slots(
                required_charge_energy_kwh=3.072,
                available_charge_power_w_value=net_power,
            ),
            18,
        )
        self.assertEqual(
            compute_window_slots(
                required_charge_energy_kwh=3.072,
                effective_charge_power_w_value=net_power,
            ),
            (20, 300),
        )

    def test_requested_input_compensates_for_storage_losses(self) -> None:
        start = datetime(2026, 8, 26, 1, 0, tzinfo=timezone.utc)
        end = start + timedelta(hours=4, minutes=30)

        requested = requested_charge_power_w(
            required_charge_energy_kwh=3.072,
            now=start,
            window_start=start,
            window_end=end,
            available_charge_power_w_value=800.0,
        )

        self.assertAlmostEqual(requested, 758.52, places=2)
        self.assertLessEqual(requested, 800.0)

    def test_joe_trace_ignores_need_below_one_soc_step(self) -> None:
        minimum = minimum_actionable_charge_energy_kwh(5.32)

        self.assertAlmostEqual(minimum, 0.0532)
        self.assertLess(0.026, minimum)
        for recalculated_need in (0.001, 0.002, 0.01, 0.026):
            with self.subTest(recalculated_need=recalculated_need):
                self.assertEqual(
                    actionable_required_charge_energy_kwh(
                        recalculated_need,
                        5.32,
                    ),
                    0.0,
                )

    def test_material_replanned_need_remains_actionable(self) -> None:
        minimum = minimum_actionable_charge_energy_kwh(5.32)

        self.assertGreater(0.141, minimum)
        self.assertEqual(
            actionable_required_charge_energy_kwh(0.141, 5.32),
            0.141,
        )

    def test_small_battery_keeps_physical_minimum_window_floor(self) -> None:
        self.assertEqual(
            minimum_actionable_charge_energy_kwh(1.92),
            0.05,
        )

    def test_joe_trace_does_not_build_a_new_micro_charge_window(self) -> None:
        now = datetime(2026, 9, 1, 1, 0, tzinfo=timezone.utc)
        points = tuple(
            MarketPricePoint(
                start=now + timedelta(minutes=15 * index),
                end=now + timedelta(minutes=15 * (index + 1)),
                price=0.33,
            )
            for index in range(24)
        )
        market = MarketPrice(
            direction=MarketPriceDirection.IMPORT,
            current_price=0.33,
            currency="EUR",
            unit="EUR/kWh",
            timestamp=now,
            source="test.joe_trace",
            validity=MarketPriceValidity.VALID,
            is_dynamic=True,
            is_fallback=False,
            forecast=MarketPriceForecast(points=points, timestamp=now),
        )
        model = LearnedSlotModel(
            slot_kwh=[0.01] * 96,
            slot_sample_count=[13] * 96,
            data_coverage=1.0,
            history_days=13,
            usable_days=13,
            night_window_days=13,
            morning_window_days=13,
            evening_window_days=13,
        )
        readiness = LearningReadiness(
            status="ready",
            history_days=13,
            usable_days=13,
            night_window_days=13,
            morning_window_days=13,
            evening_window_days=13,
            data_coverage=1.0,
        )

        with (
            patch(
                "custom_components.battery_smartflow_ai.learned_planning.expected_consumption_until",
                return_value=1.0,
            ),
            patch(
                "custom_components.battery_smartflow_ai.learned_planning.reserve_margin_kwh",
                return_value=0.3,
            ),
            patch(
                "custom_components.battery_smartflow_ai.learned_planning.forecast_adjustment_kwh",
                return_value=0.15,
            ),
            patch(
                "custom_components.battery_smartflow_ai.learned_planning.available_battery_energy_kwh",
                return_value=1.424,
            ),
            patch(
                "custom_components.battery_smartflow_ai.learned_planning.max_chargeable_energy_kwh",
                return_value=4.0,
            ),
        ):
            plan = build_learned_charge_plan(
                model=model,
                readiness=readiness,
                now=now,
                market_price=market,
                forecast=None,
                total_battery_capacity_kwh=5.32,
                current_soc=37.0,
                soc_min=10.0,
                soc_max=100.0,
                profile_charge_limit_w=2000.0,
                current_effective_charge_cap_w=2000.0,
                learned_typical_charge_power_w=2000.0,
            )

        self.assertAlmostEqual(plan.raw_required_charge_energy_kwh, 0.026)
        self.assertEqual(plan.required_charge_energy_kwh, 0.0)
        self.assertEqual(plan.mode, "ready")
        self.assertEqual(plan.requested_charge_power_w, 0.0)
        self.assertEqual(plan.effective_window_slots, 0)

    def test_control_context_uses_short_non_seasonal_labels(self) -> None:
        root = Path(__file__).resolve().parents[1]
        expected = {
            "de": ("Regelungskontext", "PV", "Preis", "Manuell"),
            "en": ("Control context", "PV", "Price", "Manual"),
            "fr": ("Contexte de régulation", "PV", "Prix", "Manuel"),
            "nl": ("Regelcontext", "PV", "Prijs", "Handmatig"),
        }

        for language, labels in expected.items():
            payload = json.loads(
                (root / "custom_components" / "battery_smartflow_ai" / "translations" / f"{language}.json").read_text(encoding="utf-8")
            )
            context = payload["entity"]["sensor"]["season_mode"]
            self.assertEqual(context["name"], labels[0])
            self.assertEqual(context["state"]["summer"], labels[1])
            self.assertEqual(context["state"]["winter"], labels[2])
            self.assertEqual(context["state"]["manual"], labels[3])


if __name__ == "__main__":
    unittest.main()
