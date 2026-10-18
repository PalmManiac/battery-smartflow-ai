"""Static contracts for the optional HEMS dashboard."""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "battery_smartflow_ai"


class DashboardContractTests(unittest.TestCase):
    def test_portal_exposes_smart_mode_setting(self) -> None:
        frontend = (COMPONENT / "frontend" / "hems-dashboard.js").read_text(
            encoding="utf-8"
        )

        self.assertIn('data-dashboard-setting="smart_mode"', frontend)
        self.assertIn('step.step_id === "smart_mode"', frontend)
        self.assertIn('native_zendure_always_smart_mode_1', frontend)

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

    def test_dashboard_module_cache_key_tracks_frontend_contents(self) -> None:
        dashboard = (COMPONENT / "dashboard.py").read_text(encoding="utf-8")

        self.assertIn("import hashlib", dashboard)
        self.assertIn("panel_module_version = hashlib.sha256(", dashboard)
        self.assertIn('(frontend_dir / "hems-dashboard.js").read_bytes()', dashboard)
        self.assertIn(
            'module_url=f"{_PANEL_URL}?v={panel_module_version}"',
            dashboard,
        )
        self.assertNotIn('module_url=f"{_PANEL_URL}?v=52"', dashboard)

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

    def test_energy_overview_uses_live_directional_power_sources(self) -> None:
        frontend = (COMPONENT / "frontend" / "hems-dashboard.js").read_text(
            encoding="utf-8"
        )
        dashboard = (COMPONENT / "dashboard.py").read_text(encoding="utf-8")
        live_flow = frontend.split("  _liveEnergyFlow(entities) {", 1)[1].split(
            "\n  _overviewMetrics(entities) {", 1
        )[0]

        self.assertIn('signed: true', live_flow)
        self.assertIn('flow === "forward" ? spec.from : flow === "reverse" ? spec.to : null', frontend)
        self.assertIn('direction === "reverse" ? "←"', frontend)
        self.assertIn('kind: "battery"', live_flow)
        self.assertIn('kind: "grid"', live_flow)
        self.assertIn('title: "house_load_source"', live_flow)
        self.assertIn('"house_load": entity_registry.async_get_entity_id(', dashboard)
        self.assertIn('energy_flow_hint:', frontend)
        self.assertIn('if (liveFlow) return liveFlow;', frontend)

    def test_energy_flow_diagram_animates_direction_and_grays_zero_flow(self) -> None:
        frontend = (COMPONENT / "frontend" / "hems-dashboard.js").read_text(
            encoding="utf-8"
        )

        self.assertIn('class="live-flow-map"', frontend)
        self.assertIn(
            '.flow-node-house{left:50%;top:56%;--flow-accent:#16c4df}',
            frontend,
        )
        live_flow = frontend.split("  _liveEnergyFlow(entities) {", 1)[1].split(
            "\n  _overviewMetrics(entities) {", 1
        )[0]
        self.assertIn('this._liveFlowNode("node_home", houseDetail, "house", "flow-node-house")', live_flow)
        self.assertNotIn('this._liveFlowNode("node_bus"', live_flow)
        self.assertNotIn('wire("house"', live_flow)
        self.assertIn("The central home circle represents the shared home connection", frontend)
        self.assertIn('class="live-flow-track ${direction}"', frontend)
        self.assertIn('.live-flow-track.idle{border-color:#626970;background:#51575d;box-shadow:none}', frontend)
        self.assertIn('.live-flow-track.forward::after,.live-flow-track.reverse::after{opacity:.92}', frontend)
        self.assertIn('.live-flow-track::after{left:-34px;right:auto;width:calc(100% + 34px);animation:none;will-change:auto}', frontend)
        self.assertIn('.live-flow-track.forward::after,.live-flow-track.reverse::after{animation:live-flow-streaks-transform var(--flow-duration,1.6s) linear infinite;will-change:transform}', frontend)
        self.assertIn('repeating-linear-gradient(110deg', frontend)
        self.assertIn('@keyframes live-flow-streaks-transform{to{transform:translateX(34px)}}', frontend)
        self.assertIn('animation-direction:reverse', frontend)
        self.assertIn('@media(prefers-reduced-motion:reduce){.live-flow-track.forward::after,.live-flow-track.reverse::after{animation:none;will-change:auto;transform:none}}', frontend)
        self.assertIn('this._liveFlowNode(nodeKey, batteryDetail(nodeKey), spec.kind)', frontend)

    def test_live_flow_uses_native_zendure_charge_and_discharge_when_needed(self) -> None:
        dashboard = (COMPONENT / "dashboard.py").read_text(encoding="utf-8")
        sensor = (COMPONENT / "sensor.py").read_text(encoding="utf-8")
        frontend = (COMPONENT / "frontend" / "hems-dashboard.js").read_text(
            encoding="utf-8"
        )

        self.assertIn('native_main_prefix = f"{unique_prefix}native_main_"', dashboard)
        self.assertIn('("_charge_power_w", "charge_entity")', dashboard)
        self.assertIn('("_discharge_power_w", "discharge_entity")', dashboard)
        self.assertIn('sources["native_battery_power"] = list(native_battery_power.values())', dashboard)
        self.assertIn("refresh_dashboard_native_sources", sensor)
        self.assertIn("hass.async_create_task(refresh_dashboard_native_sources())", sensor)
        self.assertIn("source.native_battery_power", frontend)
        self.assertIn("totalWatts += dischargeWatts - chargeWatts", frontend)
        self.assertIn('wire("battery",', frontend)
        self.assertIn('this._t(watts > 0 ? "discharge" : "charge")', frontend)

    def test_live_dashboard_patches_existing_dom_and_uses_energy_flow_schematic(self) -> None:
        frontend = (COMPONENT / "frontend" / "hems-dashboard.js").read_text(
            encoding="utf-8"
        )
        render = frontend.split("  _render() {", 1)[1].split("\n  _escape(value)", 1)[0]

        self.assertNotIn("this.shadowRoot.innerHTML =", render)
        self.assertIn("this._patchRenderNode(currentShell, nextShell)", render)
        self.assertIn("this._renderStyleReady = true", render)
        self.assertIn('data-render-key="flow-map"', frontend)
        self.assertIn('class="flow-wires"', frontend)
        self.assertIn("@keyframes energy-wire-flow", frontend)
        self.assertIn(".flow-wire.idle,.flow-wire.unavailable", frontend)
        self.assertIn("preserveAspectRatio=\"none\"", frontend)

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
        self.assertIn('DASHBOARD_VERSION = "1.0.43"', dashboard)
        self.assertIn('module_url=f"{_PANEL_URL}?v={panel_module_version}"', dashboard)
        self.assertIn("_parseHistoryResponse(history, entityId)", frontend)
        self.assertIn("history[entityId]", frontend)
        self.assertIn("row.s ?? row.state", frontend)
        self.assertIn("row.lc ?? row.lu ?? row.last_changed", frontend)
        self.assertIn(".history-card{transition:none}", frontend)
        self.assertIn(".history-card:hover{box-shadow:0 0 0 1px #16c4df35}", frontend)
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
        self.assertIn("_topologyFlowDirection(system, systemCount, systemEntities, entities)", frontend)
        self.assertIn("this._topologyFlowDirection(system, systems.length, systemEntities, entities)", frontend)
        self.assertIn("const packEntities = (system.packs || []).flatMap", frontend)
        self.assertIn("directionFrom(packEntities) || directionFrom(systemEntities || [])", frontend)
        self.assertIn(r"/\b(?:charge power|charging power|ladeleistung)\b/", frontend)
        self.assertIn(r"/\b(?:discharge power|discharging power|entladeleistung)\b/", frontend)
        self.assertIn('data-flow="${flowDirection}"', frontend)
        self.assertIn('return power > 0 ? "discharge" : "charge"', frontend)
        self.assertIn('Math.abs(power) >= 5', frontend)
        self.assertIn('class="pack-flow" aria-hidden="true"', frontend)
        self.assertIn('class="soap-bubble-track" style="${flowDelay}"', frontend)
        self.assertIn("will-change:transform", frontend)
        self.assertIn("animation-delay:var(--flow-delay,0s)", frontend)
        self.assertIn("animation-name:soap-bubbles-right", frontend)
        self.assertIn("animation-name:soap-bubbles-left", frontend)
        self.assertIn("@media(prefers-reduced-motion:reduce){.soap-bubble-track{animation:none", frontend)
        self.assertIn(".soap-bubble{position:absolute", frontend)
        self.assertIn("background:radial-gradient(circle at 30% 25%", frontend)
        self.assertIn("@keyframes soap-bubbles-right{from{transform:translateX(-50%)}to{transform:translateX(0)}}", frontend)
        self.assertIn("@keyframes soap-bubbles-left{from{transform:translateX(0)}to{transform:translateX(-50%)}}", frontend)
        self.assertIn(
            "const flowSeed = `${system.id || system.name || system.model || systemIndex}:${packNumber}`;",
            frontend,
        )
        self.assertIn("(phase * 31 + character.charCodeAt(0)) % 8000", frontend)
        self.assertIn("`--flow-delay:-${(flowPhase / 1000).toFixed(3)}s`", frontend)
        self.assertNotIn("performance.now() + systemIndex * 883 + packNumber * 557", frontend)
        self.assertIn("@keyframes soap-bubbles-right", frontend)
        self.assertIn("@keyframes soap-bubbles-left", frontend)
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
        self.assertIn('DASHBOARD_VERSION = "1.0.43"', dashboard)
        self.assertIn('module_url=f"{_PANEL_URL}?v={panel_module_version}"', dashboard)

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
        self.assertIn('class="section dashboard-area settings-area"', frontend)
        self.assertIn('class="section dashboard-area debug-area"', frontend)
        self.assertIn('class="section dashboard-area training-area"', frontend)
        self.assertIn('class="training-status-grid"', frontend)
        self.assertIn('class="training-controls"', frontend)
        self.assertIn('config/config_entries/options/flow', frontend)
        self.assertIn('class="section option-editor"', frontend)
        self.assertNotIn('/config/integrations/integration/battery_smartflow_ai#config_entry=', frontend)
        self.assertIn('"debug_active_entity": entity_registry.async_get_entity_id(', dashboard)
        self.assertIn('this._hass.callService("battery_smartflow_ai", service, data)', frontend)

    def test_portal_options_form_prefills_home_assistant_suggested_values(self) -> None:
        frontend = (COMPONENT / "frontend" / "hems-dashboard.js").read_text(
            encoding="utf-8"
        )

        self.assertIn('const value = this._optionFieldValue(field);', frontend)
        self.assertIn('description.suggested_value', frontend)
        self.assertIn('return field?.value ?? suggestedValue ?? field?.default ?? "";', frontend)

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
        self.assertIn(".history-card{transition:none}", frontend)
        self.assertIn(".history-card:hover{box-shadow:0 0 0 1px #16c4df35}", frontend)

    def test_training_dashboard_shows_directional_shadow_estimates(self) -> None:
        coordinator = (COMPONENT / "coordinator.py").read_text(encoding="utf-8")
        sensor = (COMPONENT / "sensor.py").read_text(encoding="utf-8")
        frontend = (COMPONENT / "frontend" / "hems-dashboard.js").read_text(
            encoding="utf-8"
        )

        self.assertIn('"regulation_training_evaluation": public_evaluation', coordinator)
        self.assertIn('"shadow_evaluation": evaluation', sensor)
        self.assertIn('resultState?.attributes?.shadow_evaluation', frontend)
        self.assertIn('training_sessions_aggregated', frontend)
        self.assertIn('training_charge_context', frontend)
        self.assertIn('evaluate_training_sessions(self._training_sessions)', coordinator)
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

    def test_training_dashboard_explains_sample_and_reversal_eligibility(self) -> None:
        coordinator = (COMPONENT / "coordinator.py").read_text(encoding="utf-8")
        dashboard = (COMPONENT / "dashboard.py").read_text(encoding="utf-8")
        frontend = (COMPONENT / "frontend" / "hems-dashboard.js").read_text(
            encoding="utf-8"
        )

        for field in (
            '"direction_sample_count"',
            '"unchanged_command_sample_count"',
            '"rejected_invalid_grid_count"',
            '"rejected_missing_error_count"',
            '"rejected_command_skip_count"',
            '"valid_sample_ratio"',
            '"minimum_confidence"',
            '"insufficient_reasons"',
        ):
            self.assertIn(field, coordinator)
        self.assertIn("eligibility_exclusion_counts", frontend)
        self.assertIn('"training_reversal_eligible_samples"', frontend)
        self.assertIn('"training_reversal_reason_unsupported_mode"', frontend)
        self.assertIn('"Not enough eligible PV/load data yet."', frontend)
        self.assertIn('"training_reason_low_confidence"', frontend)
        self.assertIn('"training_confidence_summary"', frontend)
        self.assertIn('DASHBOARD_VERSION = "1.0.43"', dashboard)
        self.assertIn('module_url=f"{_PANEL_URL}?v={panel_module_version}"', dashboard)


if __name__ == "__main__":
    unittest.main()
