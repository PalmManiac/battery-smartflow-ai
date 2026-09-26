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

    def test_live_power_view_uses_only_configured_per_instance_sources(self) -> None:
        frontend = (COMPONENT / "frontend" / "hems-dashboard.js").read_text(
            encoding="utf-8"
        )
        live_view = frontend.split("  _livePowerView(entities) {", 1)[1].split(
            "\n  _energyView(", 1
        )[0]

        self.assertIn("this._panel.config.power_sources", live_view)
        self.assertNotIn("this._nativeSystems(entities)", live_view)
        self.assertNotIn("native_hardware_power_w", live_view)
        self.assertNotIn("native_hardware_pv_power_w", live_view)

    def test_history_view_uses_recorder_and_offers_mobile_home_navigation(self) -> None:
        frontend = (COMPONENT / "frontend" / "hems-dashboard.js").read_text(
            encoding="utf-8"
        )
        dashboard = (COMPONENT / "dashboard.py").read_text(encoding="utf-8")

        self.assertIn('type: "history/history_during_period"', frontend)
        self.assertIn('type: "recorder/get_statistics_metadata"', frontend)
        self.assertIn('type: "recorder/statistics_during_period"', frontend)
        self.assertIn('typeof row.start === "number" ? row.start : Date.parse(row.start || "")', frontend)
        self.assertIn('const rangeValues = visibleBuckets.length ? visibleBuckets : [0]', frontend)
        self.assertIn('period: this._chartRange === "month" ? "day" : "hour"', frontend)
        self.assertIn('this._chartDataIsStatistic', frontend)
        self.assertIn('data-history-entity=', frontend)
        self.assertIn('data-history-range=', frontend)
        self.assertIn('data-history-back', frontend)
        self.assertIn('href="/" data-home', frontend)
        self.assertIn('this._hass.navigate("/")', frontend)
        self.assertIn('sidebar_title="BSFAI Portal"', dashboard)
        self.assertIn("<h1>Battery SmartFlow AI Portal</h1>", frontend)
        self.assertIn("_findBatterySoc(this._entities(), entityId)", frontend)
        self.assertIn('terms.includes("soc")', frontend)
        self.assertIn('entity.entity_id.startsWith("sensor.")', frontend)
        self.assertIn('type: "recorder/get_statistics_metadata"', frontend)
        self.assertIn('type: "recorder/statistics_during_period"', frontend)
        self.assertIn('period: this._chartRange === "month" ? "day" : "hour"', frontend)
        self.assertIn("this._chartDataIsStatistic", frontend)
        self.assertIn('DASHBOARD_VERSION = "1.0.14"', dashboard)
        self.assertIn('module_url=f"{_PANEL_URL}?v=28"', dashboard)
        self.assertIn("_parseHistoryResponse(history, entityId)", frontend)
        self.assertIn("history[entityId]", frontend)
        self.assertIn("row.s ?? row.state", frontend)
        self.assertIn("row.lc ?? row.lu ?? row.last_changed", frontend)
        self.assertIn(".history-card:hover{border-color:var(--cyan)}", frontend)
        self.assertNotIn("transform:translateY(-1px)", frontend)
        self.assertIn("row.lu ?? row.last_changed", frontend)

    def test_hardware_pack_cards_show_a_safe_left_to_right_soc_fill(self) -> None:
        frontend = (COMPONENT / "frontend" / "hems-dashboard.js").read_text(
            encoding="utf-8"
        )

        self.assertIn("_findPackSoc(entities, systemName, packNumber)", frontend)
        self.assertIn("this._findPackSoc(entities, system.name, packNumber)", frontend)
        self.assertIn("!this._isSocLimitEntity(entity)", frontend)
        self.assertIn("Math.min(100, Math.max(0, Number(candidates[0].state)))", frontend)
        self.assertIn("style=\"--soc-level:${socLevel}%\"", frontend)
        self.assertIn(".pack-card.has-soc{background:linear-gradient(90deg", frontend)
        self.assertIn('data-soc-band="${socBand}"', frontend)
        self.assertIn('class="pack-card${soc == null ? "" : " has-soc"}"', frontend)

    def test_price_per_kwh_values_use_four_decimals_in_cards_and_history(self) -> None:
        frontend = (COMPONENT / "frontend" / "hems-dashboard.js").read_text(
            encoding="utf-8"
        )
        dashboard = (COMPONENT / "dashboard.py").read_text(encoding="utf-8")

        self.assertIn('if (normalizedUnit.endsWith("/kwh")) return 4;', frontend)
        self.assertIn('if (["eur", "€"].includes(normalizedUnit)) return 2;', frontend)
        self.assertIn("const precision = this._displayPrecision(unit) ?? 1;", frontend)
        self.assertIn('DASHBOARD_VERSION = "1.0.14"', dashboard)
        self.assertIn('module_url=f"{_PANEL_URL}?v=28"', dashboard)


if __name__ == "__main__":
    unittest.main()
