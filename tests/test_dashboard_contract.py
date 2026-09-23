"""Static contracts for the optional HEMS dashboard."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "battery_smartflow_ai"


class DashboardContractTests(unittest.TestCase):
    def test_forecast_sensors_are_resolved_by_registered_unique_ids(self) -> None:
        dashboard = (COMPONENT / "dashboard.py").read_text(encoding="utf-8")
        frontend = (COMPONENT / "frontend" / "hems-dashboard.js").read_text(
            encoding="utf-8"
        )

        for key in (
            "forecast_status",
            "forecast_remaining_today_kwh",
            "forecast_tomorrow_kwh",
            "forecast_gross_remaining_today_kwh",
            "forecast_gross_tomorrow_kwh",
            "forecast_next_3h_kwh",
            "forecast_next_6h_kwh",
        ):
            self.assertIn(f'"{key}"', dashboard)

        self.assertIn('"prognose status"', frontend)

    def test_system_signals_exclude_controls_and_hardware_details(self) -> None:
        frontend = (COMPONENT / "frontend" / "hems-dashboard.js").read_text(
            encoding="utf-8"
        )

        self.assertIn('entity.entity_id.startsWith("sensor.")', frontend)
        self.assertIn('registryEntry?.platform === "battery_smartflow_ai"', frontend)
        self.assertIn("!hardwareIds.has(entity.entity_id)", frontend)
        self.assertIn("systemSignals.map((entity)", frontend)
        self.assertNotIn("entities.slice(0, 40)", frontend)
        self.assertIn("overflow-wrap:anywhere}", frontend)


if __name__ == "__main__":
    unittest.main()
