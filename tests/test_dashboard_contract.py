"""Static contracts for the optional HEMS dashboard."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "battery_smartflow_ai"


class DashboardContractTests(unittest.TestCase):
    def test_static_dashboard_route_registration_is_serialized(self) -> None:
        dashboard = (COMPONENT / "dashboard.py").read_text(encoding="utf-8")

        self.assertIn("_STATIC_PATH_LOCK_KEY", dashboard)
        self.assertIn(
            "registration_lock = hass.data.setdefault(_STATIC_PATH_LOCK_KEY, asyncio.Lock())",
            dashboard,
        )
        registration = dashboard.split("async with registration_lock:", 1)[1].split(
            "await panel_custom.async_register_panel(", 1
        )[0]
        self.assertIn("if not hass.data.get(_STATIC_PATH_KEY):", registration)
        self.assertIn("await hass.http.async_register_static_paths(", registration)
        self.assertLess(
            registration.index("await hass.http.async_register_static_paths("),
            registration.index("hass.data[_STATIC_PATH_KEY] = True"),
        )

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

    def test_irrelevant_pv_cards_hide_but_reappear_for_configured_or_live_data(self) -> None:
        frontend = (COMPONENT / "frontend" / "hems-dashboard.js").read_text(
            encoding="utf-8"
        )

        self.assertIn("_configuredPowerSource(keys)", frontend)
        self.assertIn("if (!entity || [\"unknown\", \"unavailable\"].includes(entity.state)) return \"\";", frontend)
        self.assertIn("if (value === 0 && !this._configuredPowerSource(sourceKeys)) return \"\";", frontend)
        self.assertIn("const showForecast = forecastSources.length > 0 || forecastStatus === \"available\";", frontend)
        self.assertIn("this._scheduleRender();", frontend.split("set hass(hass) {", 1)[1].split("set narrow", 1)[0])

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
        self.assertIn('data-history-chart', frontend)
        self.assertIn('data-history-tooltip', frontend)
        self.assertIn('this._historyAxis(rangeValues, attrs, isCounter, isPower)', frontend)
        self.assertIn('const zeroClass = Math.abs(value) < axis.step * 1e-8', frontend)
        self.assertIn('class="chart-gridline${zeroClass}"', frontend)
        self.assertIn('const showLine = !isCounter || attrs.device_class === "monetary"', frontend)
        self.assertIn('this._updateHistoryTooltip(event)', frontend)
        self.assertIn('this._formatHistoryAxisValue(value, attrs.unit_of_measurement, axis.step)', frontend)
        self.assertIn('data-history-back', frontend)
        self.assertIn('href="/" data-home', frontend)
        self.assertIn('this._hass.navigate("/")', frontend)
        self.assertIn('sidebar_title="BSFAI Portal"', dashboard)
        self.assertNotIn("<h1>Battery SmartFlow AI Portal</h1>", frontend)
        self.assertIn("_findBatterySoc(this._entities(), entityId)", frontend)
        self.assertIn('terms.includes("soc")', frontend)
        self.assertIn('entity.entity_id.startsWith("sensor.")', frontend)
        self.assertIn('type: "recorder/get_statistics_metadata"', frontend)
        self.assertIn('type: "recorder/statistics_during_period"', frontend)
        self.assertIn('period: this._chartRange === "month" ? "day" : "hour"', frontend)
        self.assertIn("this._chartDataIsStatistic", frontend)
        self.assertIn('DASHBOARD_VERSION = "1.0.28"', dashboard)
        self.assertIn('module_url=f"{_PANEL_URL}?v=41"', dashboard)
        self.assertIn("_parseHistoryResponse(history, entityId)", frontend)
        self.assertIn("history[entityId]", frontend)
        self.assertIn("row.s ?? row.state", frontend)
        self.assertIn("row.lc ?? row.lu ?? row.last_changed", frontend)
        self.assertIn(".history-card{cursor:pointer;border-color:#16c4df80;box-shadow:", frontend)
        self.assertIn(".history-card:hover{border-color:var(--cyan);box-shadow:", frontend)
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
        self.assertIn(".pack-card.has-soc{background:#202b35}", frontend)
        self.assertIn(".pack-card.has-soc::before", frontend)
        self.assertIn("clip-path:inset(0 calc(100% - var(--soc-level)) 0 0 round 5px)", frontend)
        self.assertIn("inset:4px", frontend)
        self.assertIn("background:var(--soc-fill);border:1px solid var(--soc-border)", frontend)
        self.assertIn(".pack-card.has-soc::before{border-width:2px}", frontend)
        self.assertIn("border-radius:5px", frontend)
        self.assertIn(".pack-head{position:relative;z-index:1}", frontend)
        self.assertIn("--soc-border:rgba(196,72,48,.85)", frontend)
        self.assertIn("--soc-border:rgba(178,132,25,.85)", frontend)
        self.assertIn("--soc-border:rgba(37,145,77,.85)", frontend)
        self.assertIn('data-soc-band="${socBand}"', frontend)
        self.assertIn('class="pack-card${soc == null ? "" : " has-soc"}"', frontend)

    def test_hardware_details_match_complete_device_names_not_substrings(self) -> None:
        frontend = (COMPONENT / "frontend" / "hems-dashboard.js").read_text(
            encoding="utf-8"
        )
        device_match = frontend.split("  _deviceEntities(entities, deviceName, packNumber) {", 1)[1].split(
            "\n  _detailLabel(", 1
        )[0]

        self.assertIn("name === prefix", device_match)
        self.assertIn('name.startsWith(`${prefix} `)', device_match)
        self.assertIn('name.includes(` ${prefix} `)', device_match)
        self.assertIn('name.endsWith(` ${prefix}`)', device_match)
        self.assertNotIn("name.includes(prefix)", device_match)

    def test_price_per_kwh_values_use_four_decimals_in_cards_and_history(self) -> None:
        frontend = (COMPONENT / "frontend" / "hems-dashboard.js").read_text(
            encoding="utf-8"
        )
        dashboard = (COMPONENT / "dashboard.py").read_text(encoding="utf-8")

        self.assertIn('if (normalizedUnit.endsWith("/kwh")) return 4;', frontend)
        self.assertIn("_currencyCodeForUnit(normalizedUnit)", frontend)
        self.assertIn('style: "currency"', frontend)
        self.assertIn('currency: currencyCode', frontend)
        self.assertIn('Intl.supportedValuesOf("currency")', frontend)
        self.assertIn('"CHF"', frontend)
        self.assertIn('"JPY"', frontend)
        self.assertIn("const precision = this._displayPrecision(unit) ?? 1;", frontend)
        self.assertIn('DASHBOARD_VERSION = "1.0.28"', dashboard)
        self.assertIn('module_url=f"{_PANEL_URL}?v=41"', dashboard)

    def test_training_controls_and_reconfiguration_are_exposed_in_dashboard(self) -> None:
        dashboard = (COMPONENT / "dashboard.py").read_text(encoding="utf-8")
        frontend = (COMPONENT / "frontend" / "hems-dashboard.js").read_text(
            encoding="utf-8"
        )

        self.assertIn('"training_entries": training_entries', dashboard)
        self.assertIn('_regulation_training_active"', dashboard)
        self.assertIn('data-view="settings"', frontend)
        self.assertIn('data-training-start=', frontend)
        self.assertIn('data-training-stop=', frontend)
        self.assertIn('this._hass.callService("battery_smartflow_ai", service, data)', frontend)
        self.assertIn('data-reconfigure-entry=', frontend)
        self.assertIn('/config/integrations/integration/battery_smartflow_ai#config_entry=', frontend)

    def test_training_dashboard_labels_are_localized_and_redundant_branding_is_removed(self) -> None:
        frontend = (COMPONENT / "frontend" / "hems-dashboard.js").read_text(
            encoding="utf-8"
        )

        for label in (
            'menu_settings: ["Einstellungen & Training", "Settings & training"]',
            'training_title: ["Regelungstraining", "Regulation training"]',
            'start_training: ["Training starten", "Start training"]',
            'training_result_candidate_proposed:',
            'configure_entry: ["Integration konfigurieren", "Configure integration"]',
        ):
            self.assertIn(label, frontend)
        self.assertIn("entries.length > 1", frontend)
        self.assertNotIn("<h1>Battery SmartFlow AI Portal</h1>", frontend)
        self.assertIn(".history-card{cursor:pointer;border-color:#16c4df80;box-shadow:", frontend)
        self.assertIn(".history-card:hover{border-color:var(--cyan);box-shadow:", frontend)

    def test_training_dashboard_shows_directional_shadow_estimates(self) -> None:
        coordinator = (COMPONENT / "coordinator.py").read_text(encoding="utf-8")
        sensor = (COMPONENT / "sensor.py").read_text(encoding="utf-8")
        frontend = (COMPONENT / "frontend" / "hems-dashboard.js").read_text(
            encoding="utf-8"
        )

        self.assertIn('"regulation_training_evaluation": public_evaluation', coordinator)
        self.assertIn('"shadow_evaluation": evaluation', sensor)
        self.assertIn('resultState?.attributes?.shadow_evaluation', frontend)
        self.assertIn('result.relative_improvement', frontend)
        self.assertIn('result.baseline_score', frontend)
        self.assertIn('result.candidate_score', frontend)
        self.assertIn('training_score_explain', frontend)
        self.assertIn('data-training-candidate-action="apply"', frontend)
        self.assertIn('data-training-candidate-action="reset"', frontend)


if __name__ == "__main__":
    unittest.main()
