"""Static contracts for the optional HEMS dashboard."""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "battery_smartflow_ai"


class DashboardContractTests(unittest.TestCase):
    def test_topology_reads_inventory_without_false_health_warning(self) -> None:
        frontend = (COMPONENT / "frontend" / "hems-dashboard.js").read_text(
            encoding="utf-8"
        )

        self.assertIn("Array.isArray(entity.attributes.systems)", frontend)
        self.assertIn(
            "ages.length > 0 && ages.length < systems.length",
            frontend,
        )

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
        self.assertIn('_SF2400AC_IMAGE_URL = "/battery_smartflow_ai/images/sf2400ac.png"', dashboard)
        self.assertIn('_SF2400AC_PLUS_IMAGE_URL = "/battery_smartflow_ai/images/sf2400ac-plus.png"', dashboard)
        self.assertIn('_SF2400ACPRO_IMAGE_URL = "/battery_smartflow_ai/images/sf2400acpro.png"', dashboard)
        self.assertIn('_SF1600AC_PLUS_IMAGE_URL = "/battery_smartflow_ai/images/sf1600ac-plus.png"', dashboard)
        self.assertIn('_HYPER2000_IMAGE_URL = "/battery_smartflow_ai/images/hyper2000.png"', dashboard)
        self.assertIn('_HUB2000_IMAGE_URL = "/battery_smartflow_ai/images/hub2000.png"', dashboard)
        self.assertIn('_SF800_IMAGE_URL = "/battery_smartflow_ai/images/sf800.png"', dashboard)
        self.assertIn('_SF800PRO_IMAGE_URL = "/battery_smartflow_ai/images/sf800pro.png"', dashboard)
        self.assertIn('_SF800PRO2_IMAGE_URL = "/battery_smartflow_ai/images/sf800pro2.png"', dashboard)
        self.assertIn('_SF800PLUS_IMAGE_URL = "/battery_smartflow_ai/images/sf800plus.png"', dashboard)
        self.assertIn("_SF2400AC_IMAGE_URL,", registration)
        self.assertIn("_SF2400AC_PLUS_IMAGE_URL,", registration)
        self.assertIn("_SF2400ACPRO_IMAGE_URL,", registration)
        self.assertIn("_SF1600AC_PLUS_IMAGE_URL,", registration)
        self.assertIn("_HYPER2000_IMAGE_URL,", registration)
        self.assertIn("_HUB2000_IMAGE_URL,", registration)
        self.assertIn("_SF800_IMAGE_URL,", registration)
        self.assertIn("_SF800PRO_IMAGE_URL,", registration)
        self.assertIn("_SF800PRO2_IMAGE_URL,", registration)
        self.assertIn("_SF800PLUS_IMAGE_URL,", registration)
        self.assertIn('"images" / "sf2400ac.png"', registration)
        self.assertIn('"images" / "sf2400acpro.png"', registration)
        self.assertIn('"images" / "sf1600ac-plus.png"', registration)
        self.assertIn('"images" / "hyper2000.png"', registration)
        self.assertIn('"images" / "hub2000.png"', registration)
        self.assertIn('"images" / "sf800.png"', registration)
        self.assertIn('"images" / "sf800pro.png"', registration)
        self.assertIn('"images" / "sf800pro2.png"', registration)
        self.assertIn('"images" / "sf800plus.png"', registration)
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
        self.assertIn('"native_zendure_watchdog"', dashboard)
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

    def test_energy_overview_has_colored_watermark_icons(self) -> None:
        frontend = (COMPONENT / "frontend" / "hems-dashboard.js").read_text(
            encoding="utf-8"
        )

        for metric_type in (
            "soc",
            "pv",
            "native-pv",
            "battery-power",
            "grid-power",
            "grid-import",
            "grid-export",
            "offgrid",
        ):
            self.assertIn(f'data-metric="{metric_type}"', frontend)
        self.assertIn('data-metric="grid-power"', frontend)
        self.assertIn('--metric-accent:#f06b6b', frontend)
        self.assertIn('class="metric-icon"', frontend)
        self.assertIn("right:-18px;bottom:-43px;width:52%", frontend)
        self.assertIn("drop-shadow(0 0 8px currentColor)", frontend)

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
        self.assertIn('DASHBOARD_VERSION = "1.0.35"', dashboard)
        self.assertIn('module_url=f"{_PANEL_URL}?v=45"', dashboard)
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
        self.assertIn("_topologyFlowDirection(system, systems.length)", frontend)
        self.assertIn('data-flow="${flowDirection}"', frontend)
        self.assertIn('return power > 0 ? "discharge" : "charge"', frontend)
        self.assertIn('Math.abs(power) < 5', frontend)
        self.assertIn('animation:bubbles-right 3s linear infinite', frontend)
        self.assertIn('animation:bubbles-left 3s linear infinite', frontend)
        self.assertIn('@media(prefers-reduced-motion:reduce)', frontend)
        self.assertIn('_topologyTransport(system.transport)', frontend)
        self.assertIn('this._t("transport_cloud_mqtt")', frontend)
        self.assertIn('this._t("transport_local")', frontend)
        self.assertIn('this._t("transport_zensdk")', frontend)
        self.assertIn('this._t("observation_mode")', frontend)
        self.assertIn('showSecondaryName ? `<small>${this._escape(secondaryName)}</small>` : ""', frontend)
        self.assertIn('_topologyDeviceImage(system)', frontend)
        self.assertIn('"/battery_smartflow_ai/images/sf2400ac.png?v=1"', frontend)
        self.assertIn('"/battery_smartflow_ai/images/sf2400ac-plus.png?v=1"', frontend)
        self.assertIn('"/battery_smartflow_ai/images/sf2400acpro.png?v=1"', frontend)
        self.assertIn('"solarflow 2400 pro", "solarflow 2400 ac pro", "sf2400pro", "sf2400acpro"', frontend)
        self.assertIn('if (/1600\\s*ac\\s*\\+/.test(rawModel))', frontend)
        self.assertIn('"/battery_smartflow_ai/images/sf1600ac-plus.png?v=1"', frontend)
        self.assertIn('["hyper 2000", "solarflow hyper 2000"].includes(model)', frontend)
        self.assertIn('"/battery_smartflow_ai/images/hyper2000.png?v=1"', frontend)
        self.assertIn('["hub 2000", "hub2000", "zendure hub 2000", "solarflow hub 2000"].includes(model)', frontend)
        self.assertIn('"/battery_smartflow_ai/images/hub2000.png?v=1"', frontend)
        self.assertIn('["solarflow 800", "sf800"].includes(model)', frontend)
        self.assertIn('"/battery_smartflow_ai/images/sf800.png?v=1"', frontend)
        self.assertIn('["solarflow 800 pro", "sf800pro"].includes(model)', frontend)
        self.assertIn('"/battery_smartflow_ai/images/sf800pro.png?v=1"', frontend)
        self.assertIn('["solarflow 800 pro 2", "sf800pro2"].includes(model)', frontend)
        self.assertIn('"/battery_smartflow_ai/images/sf800pro2.png?v=1"', frontend)
        self.assertIn('["solarflow 800 plus", "sf800plus"].includes(model)', frontend)
        self.assertIn('"/battery_smartflow_ai/images/sf800plus.png?v=1"', frontend)
        self.assertIn('class="system-device-image"', frontend)
        self.assertIn('.system-device-image{display:block;width:min(270px,48vw);height:82px', frontend)

        image_path = COMPONENT / "frontend" / "images" / "sf2400ac.png"
        self.assertTrue(image_path.is_file())
        self.assertEqual(image_path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
        plus_image_path = COMPONENT / "frontend" / "images" / "sf2400ac-plus.png"
        self.assertTrue(plus_image_path.is_file())
        self.assertEqual(plus_image_path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
        pro_image_path = COMPONENT / "frontend" / "images" / "sf2400acpro.png"
        self.assertTrue(pro_image_path.is_file())
        self.assertEqual(pro_image_path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
        plus_1600_image_path = COMPONENT / "frontend" / "images" / "sf1600ac-plus.png"
        self.assertTrue(plus_1600_image_path.is_file())
        self.assertEqual(plus_1600_image_path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
        hyper_image_path = COMPONENT / "frontend" / "images" / "hyper2000.png"
        self.assertTrue(hyper_image_path.is_file())
        self.assertEqual(hyper_image_path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
        hub_image_path = COMPONENT / "frontend" / "images" / "hub2000.png"
        self.assertTrue(hub_image_path.is_file())
        self.assertEqual(hub_image_path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
        sf800_image_path = COMPONENT / "frontend" / "images" / "sf800.png"
        self.assertTrue(sf800_image_path.is_file())
        self.assertEqual(sf800_image_path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
        sf800pro_image_path = COMPONENT / "frontend" / "images" / "sf800pro.png"
        self.assertTrue(sf800pro_image_path.is_file())
        self.assertEqual(sf800pro_image_path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
        sf800pro2_image_path = COMPONENT / "frontend" / "images" / "sf800pro2.png"
        self.assertTrue(sf800pro2_image_path.is_file())
        self.assertEqual(sf800pro2_image_path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
        sf800plus_image_path = COMPONENT / "frontend" / "images" / "sf800plus.png"
        self.assertTrue(sf800plus_image_path.is_file())
        self.assertEqual(sf800plus_image_path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")

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
        self.assertIn('DASHBOARD_VERSION = "1.0.35"', dashboard)
        self.assertIn('module_url=f"{_PANEL_URL}?v=45"', dashboard)

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
        self.assertIn('data-dashboard-setting="general"', frontend)
        self.assertIn('data-dashboard-setting="expert"', frontend)
        self.assertIn('data-dashboard-setting="debug-', frontend)
        self.assertIn('config/config_entries/options/flow', frontend)
        self.assertIn('class="section option-editor"', frontend)
        self.assertNotIn('/config/integrations/integration/battery_smartflow_ai#config_entry=', frontend)
        self.assertIn('"debug_active_entity": entity_registry.async_get_entity_id(', dashboard)
        self.assertIn('this._hass.callService("battery_smartflow_ai", service, data)', frontend)

    def test_training_dashboard_labels_are_localized_and_redundant_branding_is_removed(self) -> None:
        frontend = (COMPONENT / "frontend" / "hems-dashboard.js").read_text(
            encoding="utf-8"
        )

        for label in (
            'menu_settings: ["Einstellungen & Training", "Settings & training"]',
            'general_settings: ["Allgemein", "General"]',
            'expert_settings: ["Expertenmodus", "Expert mode"]',
            'debug_settings: ["Debug-Modus", "Debug mode"]',
            'training_title: ["Regelungstraining", "Regulation training"]',
            'start_training: ["Training starten", "Start training"]',
            'training_result_candidate_proposed:',
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
        self.assertIn('training_result_interrupted:', frontend)
        self.assertIn('training_interrupted_notice:', frontend)
        self.assertIn('resultState?.attributes?.interrupted === true', frontend)
        self.assertIn('"interrupted",', sensor)
        self.assertIn('data-training-candidate-action="apply"', frontend)
        self.assertIn('data-training-candidate-action="reset"', frontend)

    def test_watchdog_attributes_do_not_hide_dashboard_sensor_attributes(self) -> None:
        sensor = (COMPONENT / "sensor.py").read_text(encoding="utf-8")
        sensor_entity = sensor.split("class ZendureSmartFlowSensor", 1)[1]
        property_body = sensor_entity.split(
            "    def extra_state_attributes(self):", 1
        )[1].split("\n    @property", 1)[0]

        self.assertIn('runtime_key != "native_zendure_watchdog"', property_body)
        self.assertIn(
            'return getattr(self, "_attr_extra_state_attributes", None)',
            property_body,
        )
        self.assertIn('"native_zendure_device_count"', sensor)
        self.assertIn('"regulation_training_result"', sensor)

    def test_training_results_include_accessible_visual_score_comparison(self) -> None:
        frontend = (COMPONENT / "frontend" / "hems-dashboard.js").read_text(
            encoding="utf-8"
        )

        self.assertIn('class="training-score-chart" role="img"', frontend)
        self.assertIn('class="training-score-track"', frontend)
        self.assertIn('training_estimated_improvement:', frontend)
        self.assertIn('training_estimated_regression:', frontend)
        self.assertIn('training_estimated_no_change:', frontend)
        self.assertIn(".training-score-track i.candidate.better", frontend)
        self.assertIn(".training-score-track i.candidate.worse", frontend)


if __name__ == "__main__":
    unittest.main()
