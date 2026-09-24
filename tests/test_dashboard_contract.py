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
        dashboard = (COMPONENT / "dashboard.py").read_text(encoding="utf-8")
        frontend = (COMPONENT / "frontend" / "hems-dashboard.js").read_text(
            encoding="utf-8"
        )

        self.assertIn('"system_signal_entity_ids"', dashboard)
        self.assertIn('"native_zendure_status"', dashboard)
        self.assertIn('"native_zendure_error"', dashboard)
        self.assertIn('"forecast_status"', dashboard)
        self.assertIn('signalIds.has(entity.entity_id.toLowerCase())', frontend)
        self.assertIn("systemSignals.map((entity)", frontend)
        self.assertNotIn("entities.slice(0, 40)", frontend)
        self.assertIn("overflow-wrap:anywhere}", frontend)

    def test_daily_energy_flows_are_registered_and_resolved_by_unique_id(self) -> None:
        dashboard = (COMPONENT / "dashboard.py").read_text(encoding="utf-8")
        frontend = (COMPONENT / "frontend" / "hems-dashboard.js").read_text(
            encoding="utf-8"
        )

        for key in (
            "economics_daily_grid_to_battery_kwh",
            "economics_daily_pv_to_battery_kwh",
            "economics_daily_grid_export_kwh",
            "economics_daily_battery_to_home_kwh",
            "economics_daily_battery_to_grid_kwh",
            "economics_daily_native_pv_to_home_kwh",
        ):
            self.assertIn(f'"{key}"', dashboard)
            self.assertIn(f'"{key}"', frontend)

        self.assertIn('this._find(entities, [sensorKey])', frontend)

    def test_history_view_uses_recorder_and_offers_mobile_home_navigation(self) -> None:
        frontend = (COMPONENT / "frontend" / "hems-dashboard.js").read_text(
            encoding="utf-8"
        )
        dashboard = (COMPONENT / "dashboard.py").read_text(encoding="utf-8")

        self.assertIn('type: "history/history_during_period"', frontend)
        self.assertIn('data-history-entity=', frontend)
        self.assertIn('data-history-range=', frontend)
        self.assertIn('data-history-back', frontend)
        self.assertIn('href="/" data-home', frontend)
        self.assertIn('this._hass.navigate("/")', frontend)
        self.assertIn('DASHBOARD_VERSION = "1.0.7"', dashboard)
        self.assertIn('module_url=f"{_PANEL_URL}?v=21"', dashboard)


if __name__ == "__main__":
    unittest.main()
