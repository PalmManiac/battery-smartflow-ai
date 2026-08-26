"""RC6 regressions from Beat's RC5 overnight trace in Discussion #123."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import unittest

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.learned_planning import (  # noqa: E402
    compute_window_slots,
    effective_charge_power_w,
    optimize_charge_window,
    requested_charge_power_w,
    required_window_slots,
)
from custom_components.battery_smartflow_ai.market_price import (  # noqa: E402
    MarketPricePoint,
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
