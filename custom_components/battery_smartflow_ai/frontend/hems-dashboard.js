/* Battery SmartFlow AI's standalone HEMS dashboard. */
class BatterySmartFlowDashboard extends HTMLElement {
  set hass(hass) {
    this._hass = hass;
    const active = this.shadowRoot && this.shadowRoot.activeElement;
    if (active && active.matches("input, select")) return;
    this._scheduleRender();
  }

  set narrow(narrow) {
    this._narrow = narrow;
    this._scheduleRender();
  }

  set panel(panel) {
    this._panel = panel;
    this._scheduleRender();
  }

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._view = "overview";
    this._renderQueued = false;
    this._openDetailId = null;
    this._chartEntityId = null;
    this._chartOriginView = "overview";
    this._chartRange = "day";
    this._chartData = [];
    this._chartDataIsStatistic = false;
    this._chartError = "";
    this._chartRequestKey = "";
    this._chartRequestSerial = 0;
    this._pointerActive = false;
    this._renderDeferred = false;
    this.shadowRoot.addEventListener("pointerdown", () => {
      this._pointerActive = true;
    }, true);
    this._finishPointer = () => {
      this._pointerActive = false;
      if (this._renderDeferred) this._scheduleRender();
    };
    this.shadowRoot.addEventListener("click", (event) => {
      const path = event.composedPath();
      const nodeFor = (selector) => path.find((node) => node instanceof Element && node.matches(selector));
      const viewButton = nodeFor("[data-view]");
      if (viewButton) {
        this._view = viewButton.dataset.view;
        this.shadowRoot.querySelectorAll("[data-view]").forEach((tab) => {
          tab.classList.toggle("active", tab.dataset.view === this._view);
        });
        this._scheduleRender();
        return;
      }
      const historyButton = nodeFor("[data-history-entity]");
      if (historyButton) {
        this._openHistory(historyButton.dataset.historyEntity);
        return;
      }
      const rangeButton = nodeFor("[data-history-range]");
      if (rangeButton) {
        this._chartRange = rangeButton.dataset.historyRange;
        this._loadHistory();
        this._scheduleRender();
        return;
      }
      if (nodeFor("[data-history-back]")) {
        this._view = this._chartOriginView;
        this._scheduleRender();
        return;
      }
      if (nodeFor("[data-home]")) {
        event.preventDefault();
        if (this._hass && typeof this._hass.navigate === "function") {
          this._hass.navigate("/");
        } else {
          window.location.assign("/");
        }
      }
    });
    this.shadowRoot.addEventListener("keydown", (event) => {
      if ((event.key === "Enter" || event.key === " ") && event.target instanceof Element && event.target.matches("[data-history-entity]")) {
        event.preventDefault();
        event.target.click();
      }
    });
  }

  connectedCallback() {
    window.addEventListener("pointerup", this._finishPointer, true);
    window.addEventListener("pointercancel", this._finishPointer, true);
  }

  disconnectedCallback() {
    window.removeEventListener("pointerup", this._finishPointer, true);
    window.removeEventListener("pointercancel", this._finishPointer, true);
  }

  _scheduleRender() {
    if (this._pointerActive) {
      this._renderDeferred = true;
      return;
    }
    if (this._renderQueued) return;
    this._renderQueued = true;
    requestAnimationFrame(() => {
      this._renderQueued = false;
      this._render();
    });
  }

  _entities() {
    const states = Object.values((this._hass && this._hass.states) || {});
    return states
      .filter((state) => {
        const id = state.entity_id.toLowerCase();
        const name = String(state.attributes.friendly_name || "").toLowerCase();
        return (
          id.includes("battery_smartflow_ai") ||
          name.includes("battery smartflow ai") ||
          name.includes("solarflow") ||
          name.includes("zendure")
        );
      })
      .sort((a, b) => a.entity_id.localeCompare(b.entity_id));
  }

  _label(entity) {
    return entity.attributes.friendly_name || entity.entity_id;
  }

  _signalLabel(entity) {
    const original = this._label(entity);
    let label = original
      .replace(/^Battery SmartFlow AI\s*[–—-]\s*Steuerung\s*&\s*Planung\s*/i, "")
      .replace(/^SolarFlow 2400 AC\s*/i, "")
      .trim();
    label = label.replace(/^Battery-Pack\s*(\d+)\s*/i, "Akku-Pack $1 · ");
    return label.replace(/[\s·:–—-]+$/, "") || original;
  }

  _systemSignalEntities(entities) {
    const signalIds = new Set(
      (this._panel?.config?.system_signal_entity_ids || []).map((entityId) => entityId.toLowerCase())
    );
    return entities.filter((entity) => {
      return signalIds.has(entity.entity_id.toLowerCase());
    });
  }

  _searchText(value) {
    return String(value || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, " ")
      .trim();
  }

  _t(key) {
    const locale = this._hass && this._hass.locale ? this._hass.locale.language : "";
    const german = String(locale || "").toLowerCase().startsWith("de");
    if (key === "additional_signals") {
      return german ? "zusätzliche Status- und Diagnosesensoren" : "additional status and diagnostic sensors";
    }
    const labels = {
      overview: ["Übersicht", "Overview"], energy: ["Energie & Prognose", "Energy & forecast"], economics: ["Wirtschaftlichkeit", "Economics"], controls: ["Steuerung", "Controls"],
      subtitle: ["Energiefluss, Speicher und Systemstatus", "Energy flow, storage and system status"], live: ["LIVE · aktualisiert", "LIVE · updated"], energy_overview: ["Energieübersicht", "Energy overview"], live_values: ["Aktuelle Home-Assistant-Werte", "Live Home Assistant values"],
      battery: ["AKKU", "BATTERY"], pv_power: ["PV-LEISTUNG", "PV POWER"], battery_power: ["AKKULEISTUNG", "BATTERY POWER"], grid_power: ["NETZLEISTUNG", "GRID POWER"], current_price: ["AKTUELLER PREIS", "CURRENT PRICE"], waiting_entity: ["Warte auf passenden Sensor", "Waiting for matching entity"], no_data: ["Noch keine Daten", "No data yet"],
      flows_today: ["Energieflüsse heute", "Today's energy flows"], ledger: ["Gemessenes BSFAI-Energiebuch", "Measured BSFAI energy ledger"], solar_forecast: ["Solarprognose", "Solar forecast"], forecast_compare: ["Brutto-Prognose und nutzbarer Rest", "Gross forecast versus usable remainder"],
      near_term: ["Nächste Stunden · nutzbar", "Next few hours · usable"], forecast_today: ["Heute · Brutto und nutzbar", "Today · gross and usable"], forecast_tomorrow: ["Morgen · Brutto und nutzbar", "Tomorrow · gross and usable"],
      power_now: ["Momentanleistung", "Instantaneous power"], power_note: ["Live-Messwerte · Watt (W)", "Live readings · watts (W)"], daily_energy_note: ["Aufsummierte Energiemengen heute · Kilowattstunden (kWh)", "Accumulated energy today · kilowatt-hours (kWh)"], grid_net: ["Netzleistung (Bezug + / Einspeisung −)", "Grid power (import + / export −)"], grid_import: ["Netzbezug", "Grid import"], grid_export: ["Netzeinspeisung", "Grid export"], pv_source: ["PV-Leistung", "PV power"], native_pv_source: ["Native PV-Leistung", "Native PV power"], offgrid_source: ["Off-Grid-Ausgang", "Off-grid output"], house_load_source: ["Hauslast", "House load"], battery_source: ["Akku-Leistung", "Battery power"],
      source_unavailable: ["Quelle nicht verfügbar", "Source unavailable"], no_power_readings: ["Keine konfigurierten oder nativen Leistungswerte gefunden.", "No configured or native power readings found."], per_system: ["Je System", "Per system"], shared_metrics: ["Gemeinsamer Wert", "Shared value"],
      pv_battery: ["PV → Akku", "PV → battery"], grid_battery: ["Netz → Akku", "Grid → battery"], battery_home: ["Akku → Haus", "Battery → home"], battery_grid: ["Akku → Netz", "Battery → grid"], native_pv_home: ["Native PV → Haus", "Native PV → home"], grid_export: ["Netzeinspeisung", "Grid export"],
      node_pv: ["PV", "PV"], node_native_pv: ["Native PV", "Native PV"], node_grid: ["Netz", "Grid"], node_battery: ["Akku", "Battery"], node_home: ["Haus", "Home"], node_site: ["Anlage", "Site"], source: ["Quelle", "Source"], destination: ["Ziel", "Destination"], relative_flow_scale: ["Balken relativ zum größten dargestellten Tagesfluss", "Bars are relative to the largest daily flow shown"],
      usable_3h: ["Nutzbar · nächste 3 Stunden", "Usable · next 3 hours"], usable_6h: ["Nutzbar · nächste 6 Stunden", "Usable · next 6 hours"], usable_today: ["Nutzbar · Rest des Tages", "Usable · rest of today"], gross_today: ["Brutto · Rest des Tages", "Gross · rest of today"], usable_tomorrow: ["Nutzbar · morgen", "Usable · tomorrow"], gross_tomorrow: ["Brutto · morgen", "Gross · tomorrow"],
      gross_amount: ["Brutto", "Gross"], usable_amount: ["Nutzbar", "Usable"], forecast_not_configured: ["Keine Prognosequelle konfiguriert", "No forecast source configured"], forecast_unavailable: ["Prognosedaten derzeit nicht verfügbar", "Forecast data is currently unavailable"],
      forecast_explain: ["Die nutzbare Prognose berücksichtigt die Planungsannahmen von BSFAI. Die Bruttowerte zeigen die importierte Prognose vor dieser Reduktion.", "Usable forecast reflects BSFAI's planning assumptions. Gross values show the imported forecast before that reduction."], economics_today: ["Wirtschaftlichkeit heute", "Today's economics"], daily_costs: ["Tageswerte und Kosten", "Daily value and costs"], battery_benefit: ["Akku-Nutzen", "Battery benefit"], avoided_import: ["Vermiedene Netzbezugskosten", "Avoided grid import"], grid_charge_cost: ["Netzladekosten", "Grid charging cost"], pv_opportunity_cost: ["PV-Opportunitätskosten", "PV opportunity cost"], export_revenue: ["Einspeiseerlös", "Export revenue"], self_consumption_value: ["Wert nativer PV-Eigenverbrauch", "Native PV self-consumption value"], average_values: ["Durchschnittliche Ist-Werte", "Average realized values"], ledger_based: ["Basierend auf dem BSFAI-Energie- und Kostenbuch", "Based on BSFAI's energy and cost ledger"], grid_charge_price: ["Netzladepreis", "Grid charging price"], pv_opportunity_value: ["PV-Opportunitätswert", "PV opportunity value"], blended_charge_price: ["Gewichteter Akku-Ladepreis", "Blended battery charge price"], export_price: ["Einspeisepreis", "Export price"], discharge_value: ["Wert der Akkuentladung", "Battery discharge value"], native_pv_return: ["Ertrag native PV direkt ins Haus", "Native PV to home return"], efficiency: ["Wirtschaftlicher Wirkungsgrad", "Economic efficiency"],
      price_context: ["Preis- und Ladeplanung", "Price and charge planning"], daily_average: ["Tagesdurchschnitt", "Daily average"], peak_threshold: ["Preisspitzen-Schwelle", "Peak threshold"], valley_threshold: ["Niedertarif-Schwelle", "Valley threshold"], planned_charge_need: ["Geplante Netz-Nachladung", "Planned grid top-up"], pv_credit: ["PV-Prognose in Ladeplanung", "PV forecast credited to plan"], peak_coverage: ["Geplante Abdeckung bis", "Planned coverage through"],
      forecast_source_label: ["Quelle", "Source"], forecast_source_unknown: ["nicht angegeben", "not specified"],
      blended_explain: ["Der gewichtete Akku-Ladepreis berücksichtigt die verbuchte Netz- und PV-Ladeenergie. Netzladekosten und PV-Opportunitätswert stammen aus demselben Kostenbuch wie die separaten Preissensoren.", "The blended battery charge price is weighted by recorded grid- and PV-charged energy. Grid charging cost and PV opportunity value use the same cost ledger as the separate price sensors."],
      operating_mode: ["Betriebsart", "Operating mode"], existing_selects: ["Vorhandene BSFAI-Auswahl-Entitäten", "Existing BSFAI select entities"], no_selects: ["Keine BSFAI-Auswahl für Betriebsart oder manuelle Aktion gefunden.", "No BSFAI mode or manual-action select entities were found."], settings: ["BSFAI-Einstellungen", "BSFAI settings"], saved_ha: ["Änderungen werden über Home-Assistant-Zahlen-Entitäten gespeichert", "Changes are saved through Home Assistant number entities"], no_numbers: ["Keine BSFAI-Zahlenregler gefunden.", "No BSFAI number settings were found."],
      home_assistant_sensor: ["Home-Assistant-Sensor", "Home Assistant sensor"], version: ["Integration", "Integration"], dashboard_version: ["Dashboard", "Dashboard"],
      automatic: ["Automatik", "Automatic"], self_sufficient: ["Autarkie", "Self-sufficient"], manual: ["Manuell", "Manual"], standby: ["Standby", "Standby"], charge: ["Laden", "Charge"], discharge: ["Entladen", "Discharge"], constant_discharge: ["Konstante Entladung", "Constant discharge"],
      limits_group: ["Leistungs- und SoC-Grenzen", "Power and SoC limits"], price_group: ["Preisstrategie", "Price strategy"], forecast_group: ["PV und Prognose", "PV and forecast"], other_group: ["Weitere Einstellungen", "Other settings"], allowed_range: ["Zulässiger Bereich", "Allowed range"], apply: ["Übernehmen", "Apply"], saving: ["Speichere …", "Saving…"], saved: ["Gespeichert", "Saved"], failed: ["Fehler", "Failed"], manual_action_hint: ["Die manuelle Aktion wird über den separaten Aktionsregler gesteuert.", "Manual action is controlled with the separate action selector."],
      hardware_limits: ["Hardware-SoC-Grenzen", "Hardware SoC limits"], read_only: ["Nur lesbare Telemetrie", "Read-only telemetry"], hardware_explain: ["Diese Werte werden von der Hardware gemeldet. BSFAI stellt dafür keine unterstützte Schreibsteuerung bereit; sie dienen hier nur zur Information.", "These values are reported by the hardware. BSFAI does not expose a supported write control for them, so they are shown for reference only."], control_explain: ["Die Steuerung nutzt die vorhandenen BSFAI-Entitäten und Home-Assistant-Dienste. Das Dashboard schreibt nicht direkt an die Zendure-Hardware.", "Controls use existing BSFAI entities and Home Assistant services. The dashboard does not write directly to Zendure hardware."],
      systems: ["Systeme", "systems"], packs: ["Akku-Packs", "packs"], system: ["Zendure-System", "Zendure system"], zendure_hardware: ["Zendure-Hardware", "Zendure hardware"], dashboard_views: ["Dashboard-Ansichten", "Dashboard views"],
      details: ["Details", "Details"], hide_details: ["Schließen", "Close"], seconds_ago: ["Sek. zuvor", "s ago"],
      home_assistant: ["Home Assistant", "Home Assistant"], show_history: ["Verlauf ansehen", "View history"], back_to_dashboard: ["Zurück zum Dashboard", "Back to dashboard"], current_value: ["Aktueller Wert", "Current value"], sensor_history: ["Sensorverlauf", "Sensor history"], day: ["Tag", "Day"], week: ["Woche", "Week"], month: ["Monat", "Month"], history_chart: ["Sensorverlauf", "Sensor history"], history_empty: ["Für diesen Zeitraum sind keine aufgezeichneten Verlaufsdaten verfügbar.", "No recorded history is available for this period."], history_error: ["Der Verlauf konnte nicht geladen werden. Prüfe, ob Home Assistant die Sensorhistorie speichert.", "History could not be loaded. Check whether Home Assistant records this sensor."], history_note: ["Der Verlauf wird aus den in Home Assistant gespeicherten Sensorzuständen erstellt.", "History is built from sensor states recorded by Home Assistant."], history_counter_note: ["Bei Zählern zeigt das Diagramm die Zunahme je Zeitabschnitt. Rücksetzungen werden nicht als negative Energie dargestellt.", "For counters, the chart shows increases per interval. Resets are not shown as negative energy."], period_increase: ["Zunahme im Zeitraum", "Increase in period"], max_interval: ["Größtes Intervall", "Largest interval"], minimum: ["Minimum", "Minimum"], maximum: ["Maximum", "Maximum"], latest: ["Letzter Wert", "Latest"],
      system_health: ["Systemzustand", "System health"], all_online: ["Alle Systeme online", "All systems online"], attention: ["Prüfung erforderlich", "Attention required"], online_systems: ["Online", "Online"], offline_systems: ["Offline oder unbekannt", "Offline or unknown"], oldest_telemetry: ["Älteste Telemetrie", "Oldest telemetry"], minutes_ago: ["Min. zuvor", "min ago"],
      topology: ["Hardware-Topologie", "Hardware topology"], model: ["Modell", "Model"], profile: ["Profil", "Profile"], communication: ["Kommunikation", "Communication"], status: ["Status", "Status"], last_data: ["Letzte Daten", "Last data"], battery_pack: ["Akku-Pack", "Battery Pack"], zendure_pack: ["Zendure-Akku-Pack", "Zendure battery pack"], telemetry: ["Telemetrie", "Telemetry"], unavailable: ["Nicht verfügbar", "Not available"], online: ["ONLINE", "ONLINE"], offline: ["OFFLINE", "OFFLINE"], unknown_path: ["Kommunikationsweg unbekannt", "Communication path unknown"], unknown_status: ["Status unbekannt", "Status unknown"], no_packs: ["Keine Akku-Packs erkannt", "No battery packs detected"], native_empty: ["Die native Hardwareübersicht ist noch nicht verfügbar. Erkannte Zendure-Geräte und angeschlossene Akku-Packs erscheinen hier.", "The native hardware inventory is not available yet. Discovered Zendure systems and attached battery packs will appear here."], system_signals: ["Systemsignale", "System signals"], matching_entities: ["passende Entitäten", "matching entities"], waiting_entities: ["Warte auf Battery-SmartFlow-AI-Entitäten.", "Waiting for Battery SmartFlow AI entities."], footer: ["Battery SmartFlow AI · Steuerung über Home Assistant", "Battery SmartFlow AI · Home Assistant-powered controls"],
    };
    const value = labels[key];
    return value ? value[german ? 0 : 1] : key;
  }

  _value(entity) {
    if (!entity || ["unknown", "unavailable"].includes(entity.state)) {
      return "—";
    }
    const unit = entity.attributes.unit_of_measurement;
    const numeric = Number(entity.state);
    if (!Number.isFinite(numeric)) return `${entity.state}${unit ? ` ${unit}` : ""}`;
    const normalizedUnit = String(unit || "").toLowerCase().replace(/\s+/g, "");
    const precision = normalizedUnit === "kwh"
      ? 3
      : ["eur", "€", "eur/kwh", "€/kwh"].includes(normalizedUnit)
        ? 2
        : normalizedUnit === "w" || normalizedUnit === "kw"
          ? 1
          : null;
    const locale = this._hass && this._hass.locale ? this._hass.locale.language : undefined;
    const value = precision === null
      ? entity.state
      : numeric.toLocaleString(locale, { maximumFractionDigits: precision });
    return `${value}${unit ? ` ${unit}` : ""}`;
  }

  _find(entities, terms) {
    const groups = Array.isArray(terms[0]) ? terms : terms.map((term) => [term]);
    const configured = (this._panel && this._panel.config && this._panel.config.sensor_entities) || {};
    for (const group of groups) {
      for (const term of group) {
        const candidates = configured[term];
        for (const entityId of Array.isArray(candidates) ? candidates : candidates ? [candidates] : []) {
          const entity = this._hass && this._hass.states[entityId];
          if (entity && !["unknown", "unavailable"].includes(entity.state)) return entity;
        }
      }
    }
    return entities.find((entity) => {
      const search = this._searchText(`${entity.entity_id} ${this._label(entity)}`);
      return groups.some((group) => group.every((term) => search.includes(this._searchText(term))));
    });
  }

  _reading(entities, title, terms, hint = "") {
    const entity = this._find(entities, terms);
    const history = entity ? ` data-history-entity="${this._escape(entity.entity_id)}" role="button" tabindex="0" aria-label="${this._escape(`${title} · ${this._t("show_history")}`)}"` : "";
    return `<article class="reading${entity ? " history-card" : ""}"${history}><span>${this._escape(title)}</span><strong>${this._escape(this._value(entity))}</strong>${entity ? `<small>${this._escape(this._t("show_history"))}</small>` : `<small>${this._escape(hint || this._t("unavailable"))}</small>`}</article>`;
  }

  _forecastStatus(entities) {
    const entity = this._find(entities, ["forecast_status", "prognose status"]);
    return entity && !["unknown", "unavailable"].includes(entity.state) ? entity.state : "unavailable";
  }

  _forecastSourceHint() {
    const sources = (this._panel && this._panel.config && this._panel.config.forecast_sources) || [];
    const sourceText = sources.length ? sources.join(", ") : this._t("forecast_source_unknown");
    return `${this._t("forecast_source_label")}: ${sourceText}`;
  }

  _forecastReading(entities, title, terms, forecastStatus) {
    if (forecastStatus !== "available") {
      const message = forecastStatus === "not_configured" ? "forecast_not_configured" : "forecast_unavailable";
      return `<article class="reading"><span>${this._escape(title)}</span><strong>—</strong><small>${this._escape(this._t(message))}</small></article>`;
    }
    return this._reading(entities, title, terms);
  }

  _forecastComparison(entities, title, usableTerms, grossTerms, maxValue, forecastStatus) {
    const readValue = (terms) => {
      if (forecastStatus !== "available") return null;
      const entity = this._find(entities, terms);
      if (!entity || ["unknown", "unavailable"].includes(entity.state)) return null;
      const value = Number(entity.state);
      return Number.isFinite(value) ? Math.max(0, value) : null;
    };
    const rows = [
      [this._t("gross_amount"), grossTerms],
      [this._t("usable_amount"), usableTerms],
    ].map(([label, terms]) => {
      const value = readValue(terms);
      const width = value === null || maxValue <= 0 ? 0 : Math.min(100, value / maxValue * 100);
      const displayValue = value === null ? "—" : `${value.toLocaleString(this._hass && this._hass.locale ? this._hass.locale.language : undefined, { maximumFractionDigits: 3 })} kWh`;
      return `<div class="forecast-bar-row ${value === null ? "unavailable" : ""}"><span>${this._escape(label)}</span><div class="forecast-bar-track"><i style="width:${width}%"></i></div><strong>${this._escape(displayValue)}</strong></div>`;
    }).join("");
    return `<div class="forecast-group"><h3>${this._escape(title)}</h3><div class="forecast-day-chart">${rows}</div></div>`;
  }

  _flowRow(entities, title, terms, width, source, destination) {
    const entity = this._find(entities, terms);
    const numeric = entity && !["unknown", "unavailable"].includes(entity.state) && Number.isFinite(Number(entity.state));
    const displayedWidth = numeric ? Math.max(0, Math.min(100, width)) : 0;
    const history = entity ? ` data-history-entity="${this._escape(entity.entity_id)}" role="button" tabindex="0" aria-label="${this._escape(`${title} · ${this._t("show_history")}`)}"` : "";
    return `<div class="flow-row${entity ? " history-card" : ""}"${history}><div class="flow-node"><small>${this._escape(this._t("source"))}</small><strong>${this._escape(this._t(source))}</strong></div><div class="flow-route ${numeric ? "" : "unavailable"}" role="img" aria-label="${this._escape(title)}"><small class="flow-label">${this._escape(title)}</small><div class="flow-direction"><span>→</span><div class="flow-track"><i style="width:${displayedWidth}%"></i></div></div></div><div class="flow-node"><small>${this._escape(this._t("destination"))}</small><strong>${this._escape(this._t(destination))}</strong></div><strong class="flow-value">${this._escape(this._value(entity))}</strong></div>`;
  }

  _powerCard(title, entityId, hint = "") {
    const displayTitle = title.replace(/^Battery SmartFlow AI\s*[·:–—-]\s*/i, "");
    const entity = entityId && this._hass && this._hass.states[entityId];
    let value = entity ? this._value(entity) : "— W";
    if (entity && entity.state !== "unknown" && entity.state !== "unavailable") {
      const numeric = Number(entity.state);
      const unit = entity.attributes.unit_of_measurement;
      const wattFactors = { W: 1, kW: 1000, MW: 1000000, mW: 0.001 };
      if (Number.isFinite(numeric) && (!unit || Object.prototype.hasOwnProperty.call(wattFactors, unit))) {
        const watts = numeric * (unit ? wattFactors[unit] : 1);
        const locale = this._hass && this._hass.locale ? this._hass.locale.language : undefined;
        value = `${watts.toLocaleString(locale, { maximumFractionDigits: 1 })} W`;
      }
    }
    const history = entity ? ` data-history-entity="${this._escape(entity.entity_id)}" role="button" tabindex="0" aria-label="${this._escape(`${displayTitle} · ${this._t("show_history")}`)}"` : "";
    return `<article class="reading power-reading${entity ? " history-card" : ""}"${history}><span>${this._escape(displayTitle)}</span><strong>${this._escape(value)}</strong>${entity ? `<small>${this._escape(this._t("show_history"))}</small>` : `<small>${this._escape(hint || this._t("source_unavailable"))}</small>`}</article>`;
  }

  _livePowerView(entities) {
    const cards = [];
    const sources = (this._panel && this._panel.config && this._panel.config.power_sources) || [];
    sources.forEach((source) => {
      const prefix = source.name ? `${source.name} · ` : "";
      if (source.pv) cards.push(this._powerCard(`${prefix}${this._t("pv_source")}`, source.pv));
      if (source.native_pv) cards.push(this._powerCard(`${prefix}${this._t("native_pv_source")}`, source.native_pv));
      if (source.grid_power) cards.push(this._powerCard(`${prefix}${this._t("grid_net")}`, source.grid_power));
      else {
        if (source.grid_import) cards.push(this._powerCard(`${prefix}${this._t("grid_import")}`, source.grid_import));
        if (source.grid_export) cards.push(this._powerCard(`${prefix}${this._t("grid_export")}`, source.grid_export));
      }
      if (source.offgrid_power) cards.push(this._powerCard(`${prefix}${this._t("offgrid_source")}`, source.offgrid_power));
    });

    const houseLoads = entities.filter((entity) => {
      const search = `${entity.entity_id} ${this._label(entity)}`.toLowerCase();
      return /house_load|house load|hauslast/.test(search) && entity.attributes.unit_of_measurement === "W";
    });
    houseLoads.forEach((entity) => cards.push(this._powerCard(this._t("house_load_source"), entity.entity_id)));

    const systems = this._nativeSystems(entities);
    systems.forEach((system) => {
      const systemEntities = this._deviceEntities(entities, system.name, null);
      const power = systemEntities.find((entity) => /batterieleistung|battery power/.test(this._label(entity).toLowerCase()))
        || systemEntities.find((entity) => entity.entity_id.toLowerCase().includes("native_hardware_power_w"));
      const pv = systemEntities.find((entity) => /pv-leistung|pv power/.test(this._label(entity).toLowerCase()))
        || systemEntities.find((entity) => entity.entity_id.toLowerCase().includes("native_hardware_pv_power_w"));
      if (power) cards.push(this._powerCard(`${system.name} · ${this._t("battery_source")}`, power.entity_id));
      if (pv) cards.push(this._powerCard(`${system.name} · ${this._t("pv_source")}`, pv.entity_id));
    });

    return `<section class="section"><div class="section-head"><h2>${this._escape(this._t("power_now"))}</h2><small>${this._escape(this._t("power_note"))}</small></div><div class="reading-grid">${cards.join("") || `<div class="empty">${this._escape(this._t("no_power_readings"))}</div>`}</div></section>`;
  }

  _energyView(entities) {
    const forecastStatus = this._forecastStatus(entities);
    const grossTodayTerms = [["forecast_gross_remaining_today_kwh"], ["gross pv forecast remaining today"], ["pv-prognose brutto", "rest heute"]];
    const usableTodayTerms = [["forecast_remaining_today_kwh"], ["usable pv forecast remaining today"], ["nutzbare pv-prognose", "rest heute"]];
    const grossTomorrowTerms = [["forecast_gross_tomorrow_kwh"], ["gross pv forecast tomorrow"], ["pv-prognose brutto", "morgen"]];
    const usableTomorrowTerms = [["forecast_tomorrow_kwh"], ["usable pv forecast tomorrow"], ["nutzbare pv-prognose", "morgen"]];
    const forecastValues = [grossTodayTerms, usableTodayTerms, grossTomorrowTerms, usableTomorrowTerms].map((terms) => {
      if (forecastStatus !== "available") return null;
      const entity = this._find(entities, terms);
      const value = entity && !["unknown", "unavailable"].includes(entity.state) ? Number(entity.state) : NaN;
      return Number.isFinite(value) ? Math.max(0, value) : null;
    }).filter((value) => value !== null);
    const forecastMax = Math.max(...forecastValues, 0);
    const flowSpecs = [
      [this._t("pv_battery"), "economics_daily_pv_to_battery_kwh", "node_pv", "node_battery"],
      [this._t("grid_battery"), "economics_daily_grid_to_battery_kwh", "node_grid", "node_battery"],
      [this._t("battery_home"), "economics_daily_battery_to_home_kwh", "node_battery", "node_home"],
      [this._t("battery_grid"), "economics_daily_battery_to_grid_kwh", "node_battery", "node_grid"],
      [this._t("native_pv_home"), "economics_daily_native_pv_to_home_kwh", "node_native_pv", "node_home"],
      [this._t("grid_export"), "economics_daily_grid_export_kwh", "node_site", "node_grid"],
    ];
    const flowValues = flowSpecs.map(([, sensorKey]) => {
      const entity = this._find(entities, [sensorKey]);
      return entity && !["unknown", "unavailable"].includes(entity.state) && Number.isFinite(Number(entity.state))
        ? Math.max(0, Number(entity.state))
        : null;
    });
    const largestFlow = Math.max(...flowValues.filter((value) => value !== null), 0);
    const flowRows = flowSpecs.map(([title, sensorKey, source, destination], index) =>
      this._flowRow(entities, title, [sensorKey], largestFlow ? Math.round((flowValues[index] || 0) / largestFlow * 100) : 0, source, destination)
    ).join("");
    return `
      ${this._livePowerView(entities)}
      <section class="section"><div class="section-head"><h2>${this._escape(this._t("flows_today"))}</h2><small>${this._escape(this._t("daily_energy_note"))}</small></div>
        <small class="flow-scale">${this._escape(this._t("relative_flow_scale"))}</small><div class="flow-grid">
          ${flowRows}
        </div>
      </section>
      <section class="section"><div class="section-head"><h2>${this._escape(this._t("solar_forecast"))}</h2><small class="forecast-source-hint">${this._escape(`${this._t("forecast_compare")} · ${this._forecastSourceHint()}`)}</small></div>
        <div class="forecast-groups">
          <div class="forecast-group"><h3>${this._escape(this._t("near_term"))}</h3><div class="reading-grid">
            ${this._forecastReading(entities, this._t("usable_3h"), [["forecast_next_3h_kwh"], ["usable pv forecast next 3 hours"], ["nutzbare pv-prognose", "nächste 3 stunden"]], forecastStatus)}
            ${this._forecastReading(entities, this._t("usable_6h"), [["forecast_next_6h_kwh"], ["usable pv forecast next 6 hours"], ["nutzbare pv-prognose", "nächste 6 stunden"]], forecastStatus)}
          </div></div>
          ${this._forecastComparison(entities, this._t("forecast_today"), usableTodayTerms, grossTodayTerms, forecastMax, forecastStatus)}
          ${this._forecastComparison(entities, this._t("forecast_tomorrow"), usableTomorrowTerms, grossTomorrowTerms, forecastMax, forecastStatus)}
        </div>
        <p class="explain">${this._escape(forecastStatus === "available" ? this._t("forecast_explain") : this._t(forecastStatus === "not_configured" ? "forecast_not_configured" : "forecast_unavailable"))}</p>
      </section>`;
  }

  _economicsView(entities) {
    return `
      <section class="section"><div class="section-head"><h2>${this._escape(this._t("price_context"))}</h2><small>${this._escape(this._t("daily_costs"))}</small></div>
        <div class="reading-grid">
          ${this._reading(entities, this._t("current_price"), [["price_now"], ["current import price"], ["strompreis jetzt"]])}
          ${this._reading(entities, this._t("daily_average"), [["price_daily_average"], ["daily average price"], ["tagesdurchschnittspreis"]])}
          ${this._reading(entities, this._t("peak_threshold"), [["current_peak_threshold"], ["preisspitzen-schwelle"]])}
          ${this._reading(entities, this._t("valley_threshold"), [["current_valley_threshold"], ["niedertarif-schwelle"]])}
          ${this._reading(entities, this._t("planned_charge_need"), [["learned_planning_required_charge_energy_kwh"], ["planned grid top-up"]])}
          ${this._reading(entities, this._t("pv_credit"), ["learned_planning_pv_forecast_credit_kwh", "pv forecast credited to the charge plan"])}
          ${this._reading(entities, this._t("peak_coverage"), ["learned_planning_coverage_end", "end of planned peak coverage"])}
        </div>
      </section>
      <section class="section"><div class="section-head"><h2>${this._escape(this._t("economics_today"))}</h2><small>${this._escape(this._t("daily_costs"))}</small></div>
        <div class="reading-grid">
          ${this._reading(entities, this._t("battery_benefit"), ["economics_daily_battery_benefit", "battery benefit today", "bilanz heute batterie-nutzen"])}
          ${this._reading(entities, this._t("avoided_import"), ["economics_daily_avoided_grid_import_cost", "avoided grid import cost", "vermiedene netzbezugskosten"])}
          ${this._reading(entities, this._t("grid_charge_cost"), ["economics_daily_grid_charge_cost", "grid charging cost", "netzlade-kosten"])}
          ${this._reading(entities, this._t("pv_opportunity_cost"), ["economics_daily_pv_opportunity_cost", "pv opportunity cost", "pv-opportunitätskosten"])}
          ${this._reading(entities, this._t("export_revenue"), ["economics_daily_export_revenue", "export revenue", "einspeiseerlös"])}
          ${this._reading(entities, this._t("self_consumption_value"), ["economics_daily_native_pv_self_consumption_value", "native pv self-consumption value", "wert native pv eigenverbrauch"])}
        </div>
      </section>
      <section class="section"><div class="section-head"><h2>${this._escape(this._t("average_values"))}</h2><small>${this._escape(this._t("ledger_based"))}</small></div>
        <div class="reading-grid">
          ${this._reading(entities, this._t("grid_charge_price"), ["economics_average_grid_charge_price", "avg. grid charging price", "ø netzladepreis"])}
          ${this._reading(entities, this._t("pv_opportunity_value"), ["economics_average_pv_opportunity_value", "avg. pv opportunity value", "ø pv-opportunitätswert"])}
          ${this._reading(entities, this._t("blended_charge_price"), ["economics_average_battery_charge_price", "avg. battery charge price", "ø akku-ladepreis"])}
          ${this._reading(entities, this._t("export_price"), ["economics_average_export_price", "avg. export price", "ø einspeisepreis"])}
          ${this._reading(entities, this._t("discharge_value"), ["economics_average_battery_discharge_value", "avg. battery discharge value", "ø wert der batterieentladung"])}
          ${this._reading(entities, this._t("native_pv_return"), ["economics_average_native_pv_to_home_return", "avg. pv to home return", "ø wert native pv direkt ins haus"])}
          ${this._reading(entities, this._t("efficiency"), ["economics_total_economic_efficiency_pct", "economic efficiency", "wirtschaftlichkeit"])}
        </div>
        <p class="explain">${this._escape(this._t("blended_explain"))}</p>
      </section>`;
  }

  _nativeSystems(entities) {
    const systemsById = new Map();
    entities
      .filter((entity) => Array.isArray(entity.attributes.systems))
      .forEach((entity) => {
        entity.attributes.systems.forEach((system) => {
          if (!system || typeof system !== "object") return;
          const key = system.id || `${system.name || ""}|${system.model || ""}`;
          if (key && !systemsById.has(key)) systemsById.set(key, system);
        });
      });
    return [...systemsById.values()];
  }

  _formatAge(seconds) {
    if (seconds == null || !Number.isFinite(Number(seconds)) || Number(seconds) < 0) return this._t("unavailable");
    const age = Math.floor(Number(seconds));
    if (age < 60) return `${age} ${this._t("seconds_ago")}`;
    return `${Math.floor(age / 60)} ${this._t("minutes_ago")}`;
  }

  _healthSummary(systems) {
    if (!systems.length) return "";
    const online = systems.filter((system) => system.online).length;
    const offline = systems.length - online;
    const ages = systems.map((system) => system.data_age_seconds == null ? NaN : Number(system.data_age_seconds)).filter((age) => Number.isFinite(age) && age >= 0);
    const oldest = ages.length ? Math.max(...ages) : null;
    const needsAttention = offline > 0 || ages.length < systems.length;
    return `<section class="section health-summary ${needsAttention ? "attention" : "healthy"}" aria-label="${this._escape(this._t("system_health"))}"><div class="section-head"><h2>${this._escape(this._t("system_health"))}</h2><span class="health-state">${this._escape(this._t(needsAttention ? "attention" : "all_online"))}</span></div><div class="health-grid"><article><small>${this._escape(this._t("online_systems"))}</small><strong>${online} / ${systems.length}</strong></article><article><small>${this._escape(this._t("offline_systems"))}</small><strong>${offline}</strong></article><article><small>${this._escape(this._t("oldest_telemetry"))}</small><strong>${this._escape(oldest == null ? this._t("unavailable") : this._formatAge(oldest))}</strong></article></div></section>`;
  }

  _deviceEntities(entities, deviceName, packNumber) {
    const prefix = this._searchText(deviceName);
    if (!prefix) return [];
    const packPattern = /(battery|batterie|akku)[ -]?pack\s*0*([1-9]\d*)/i;
    return entities.filter((entity) => {
      const name = this._searchText(`${entity.entity_id} ${this._label(entity)}`);
      if (!name.includes(prefix)) return false;
      const packMatch = name.match(packPattern);
      return packNumber
        ? Boolean(packMatch && Number(packMatch[2]) === packNumber)
        : !packMatch;
    });
  }

  _detailLabel(entity, systemName = "", packNumber = null) {
    let label = entity.attributes.friendly_name || this._t("telemetry");
    const knownSystem = systemName || (this._currentSystems || [])
      .map((system) => system.name)
      .filter(Boolean)
      .sort((a, b) => b.length - a.length)
      .find((name) => label.toLowerCase().startsWith(name.toLowerCase()));
    const prefix = String(knownSystem || "").trim();
    if (prefix && label.toLowerCase().startsWith(prefix.toLowerCase())) {
      label = label.slice(prefix.length).replace(/^\s*[-–—:·|]?\s*/, "");
    }
    if (packNumber) {
      label = label.replace(new RegExp(`^(?:battery|batterie)[ -]?pack\\s*0*${packNumber}\\s*[-–—:·|]?\\s*`, "i"), "");
    }
    return label.trim() || this._t("telemetry");
  }

  _detailRows(entities, limit = 5, systemName = "", packNumber = null) {
    const preferred = /(soc|ladezustand|power|leistung|temperatur|temperature|status|transport|firmware|kapazität|capacity)/i;
    const ordered = [...entities].sort((a, b) => {
      return Number(preferred.test(this._label(b))) - Number(preferred.test(this._label(a)));
    });
    return ordered.slice(0, limit).map((entity) =>
      `<div class="detail-row"><span>${this._escape(this._detailLabel(entity, systemName, packNumber))}</span><strong>${this._escape(this._value(entity))}</strong></div>`
    ).join("");
  }

  _controls(entities) {
    const registry = (this._hass && this._hass.entities) || {};
    const integrationEntities = Object.values((this._hass && this._hass.states) || {}).filter((entity) => {
      const id = entity.entity_id.toLowerCase();
      const registryEntry = registry[entity.entity_id];
      return id.includes("battery_smartflow_ai") || (registryEntry && registryEntry.platform === "battery_smartflow_ai");
    });
    const controls = integrationEntities.filter((entity) => /^(number|select)\./.test(entity.entity_id.toLowerCase()));
    const selects = controls.filter((entity) => entity.entity_id.startsWith("select."));
    const numbers = controls.filter((entity) => entity.entity_id.startsWith("number."));
    const selectCards = selects.map((entity) => {
      const isMode = entity.entity_id.endsWith("_ai_mode");
      const labels = this._controlOptionLabels();
      return `<article class="control-card"><label for="control-${this._escape(entity.entity_id)}">${this._escape(this._controlLabel(entity))}</label><select id="control-${this._escape(entity.entity_id)}" data-control-select="${this._escape(entity.entity_id)}">${(entity.attributes.options || []).map((option) => `<option value="${this._escape(option)}" ${option === entity.state ? "selected" : ""}>${this._escape(labels[option] || option)}</option>`).join("")}</select><button class="apply" data-apply-select="${this._escape(entity.entity_id)}">${this._escape(this._t("apply"))}</button>${isMode && entity.state === "manual" ? `<small>${this._escape(this._t("manual_action_hint"))}</small>` : ""}</article>`;
    }).join("");
    const groupFor = (entity) => {
      const name = `${entity.entity_id} ${this._label(entity)}`.toLowerCase();
      if (/soc|akku-pack|battery.pack|max.charg|max.discharg|max lade|max entlade|notlad|emergency|anzahl akku/.test(name)) return "limits_group";
      if (/price|preis|peak|valley|talpreis|profit|marge|cheap|billig|expensive|teuer|schwelle/.test(name)) return "price_group";
      if (/pv|solar|forecast|prognose|grundlast|base.load/.test(name)) return "forecast_group";
      return "other_group";
    };
    const groupedNumbers = ["limits_group", "price_group", "forecast_group", "other_group"].map((group) => {
      const cards = numbers.filter((entity) => groupFor(entity) === group).map((entity) => this._numberControlCard(entity)).join("");
      return cards ? `<section class="subsection"><h3>${this._escape(this._t(group))}</h3><div class="control-grid">${cards}</div></section>` : "";
    }).join("");
    const hardwareLimits = integrationEntities.filter((entity) => {
      const text = `${entity.entity_id} ${this._label(entity)}`.toLowerCase();
      return entity.entity_id.startsWith("sensor.") && /hardware.*soc.*(min|minimum|max|maximum)|(soc.*(min|minimum|max|maximum).*hardware)/.test(text);
    });
    const hardwareCards = hardwareLimits.map((entity) => `<div class="entity"><span>${this._escape(this._label(entity))}</span><strong>${this._escape(this._value(entity))}</strong></div>`).join("");
    return `<section class="section"><div class="section-head"><h2>${this._escape(this._t("operating_mode"))}</h2><small>${this._escape(this._t("existing_selects"))}</small></div><div class="control-grid">${selectCards || `<div class="empty">${this._escape(this._t("no_selects"))}</div>`}</div></section>
      <section class="section"><div class="section-head"><h2>${this._escape(this._t("settings"))}</h2><small>${this._escape(this._t("saved_ha"))}</small></div>${groupedNumbers || `<div class="empty">${this._escape(this._t("no_numbers"))}</div>`}</section>
      ${hardwareCards ? `<section class="section"><div class="section-head"><h2>${this._escape(this._t("hardware_limits"))}</h2><small>${this._escape(this._t("read_only"))}</small></div><div class="inventory">${hardwareCards}</div><p class="explain">${this._escape(this._t("hardware_explain"))}</p></section>` : ""}
      <p class="explain">${this._escape(this._t("control_explain"))}</p>`;
  }

  _controlOptionLabels(entity) {
    const translations = {
      automatic: this._t("automatic"), summer: this._t("self_sufficient"), manual: this._t("manual"),
      standby: this._t("standby"), charge: this._t("charge"), discharge: this._t("discharge"), constant_discharge: this._t("constant_discharge"),
    };
    return translations;
  }

  _controlLabel(entity) {
    const label = this._label(entity);
    return label.replace(/^Battery SmartFlow AI\s*[–—-]\s*Steuerung\s*&\s*Planung\s*/i, "").trim() || label;
  }

  _numberControlCard(entity) {
    const value = Number(entity.state);
    const min = Number(entity.attributes.min);
    const max = Number(entity.attributes.max);
    const step = Number(entity.attributes.step);
    if (!Number.isFinite(value) || !Number.isFinite(min) || !Number.isFinite(max)) return "";
    return `<article class="control-card"><label for="control-${this._escape(entity.entity_id)}">${this._escape(this._controlLabel(entity))}</label><div class="number-control"><input id="control-${this._escape(entity.entity_id)}" type="number" data-control-number="${this._escape(entity.entity_id)}" value="${value}" min="${min}" max="${max}" step="${Number.isFinite(step) && step > 0 ? step : 1}"><span>${this._escape(entity.attributes.unit_of_measurement || "")}</span></div><small>${this._escape(this._t("allowed_range"))}: ${min}–${max}${entity.attributes.unit_of_measurement ? ` ${this._escape(entity.attributes.unit_of_measurement)}` : ""}</small><button class="apply" data-apply-number="${this._escape(entity.entity_id)}">${this._escape(this._t("apply"))}</button></article>`;
  }

  _applyControl(service, entityId, data) {
    const button = this.shadowRoot.querySelector(`[data-apply-${service === "set_value" ? "number" : "select"}="${CSS.escape(entityId)}"]`);
    if (!button) return;
    button.disabled = true;
    button.textContent = this._t("saving");
    const serviceData = Object.assign({ entity_id: entityId }, data);
    this._hass.callService(service === "set_value" ? "number" : "select", service, serviceData).then(() => {
      button.textContent = this._t("saved");
    }).catch((error) => {
      button.textContent = this._t("failed");
      button.title = String(error);
    });
    window.setTimeout(() => {
      if (!button.isConnected) return;
      button.disabled = false;
      button.textContent = this._t("apply");
    }, 1800);
  }

  _metricCard(title, entityId, fallbackTerms = []) {
    let entity = entityId && this._hass && this._hass.states[entityId];
    if (!entity || ["unknown", "unavailable"].includes(entity.state)) {
      entity = this._find(this._entities(), fallbackTerms);
    }
    if (title === this._t("battery") && this._isSocLimitEntity(entity)) {
      entity = this._findBatterySoc(this._entities());
    }
    const history = entity ? ` data-history-entity="${this._escape(entity.entity_id)}" role="button" tabindex="0" aria-label="${this._escape(`${title} · ${this._t("show_history")}`)}"` : "";
    return `<article class="metric${entity ? " history-card" : ""}"${history}><span>${this._escape(title)}</span><strong>${this._escape(this._value(entity))}</strong>${entity ? `<small>${this._escape(this._t("show_history"))}</small>` : `<small>${this._escape(this._t("waiting_entity"))}</small>`}</article>`;
  }

  _isSocLimitEntity(entity) {
    if (!entity) return false;
    const text = this._searchText(`${entity.entity_id} ${this._label(entity)}`);
    return /(?:soc|ladezustand|state of charge).*(?:min|minimum|max|maximum|limit)|(?:min|minimum|max|maximum|limit).*(?:soc|ladezustand|state of charge)|hardware.*soc/.test(text);
  }

  _findBatterySoc(entities) {
    const candidates = entities.filter((entity) =>
      !this._isSocLimitEntity(entity) && !["unknown", "unavailable"].includes(entity.state));
    const matches = (entity, terms) => {
      const text = this._searchText(`${entity.entity_id} ${this._label(entity)}`);
      return terms.every((term) => text.includes(this._searchText(term)));
    };
    return candidates.find((entity) => matches(entity, ["state of charge"]))
      || candidates.find((entity) => matches(entity, ["ladezustand"]))
      || candidates.find((entity) => matches(entity, ["battery", "soc"]))
      || candidates.find((entity) => matches(entity, ["akku", "soc"]))
      || candidates.find((entity) => matches(entity, ["soc"]));
  }

  _openHistory(entityId) {
    if (!entityId || !this._hass || !this._hass.states[entityId]) return;
    this._chartOriginView = this._view === "history" ? this._chartOriginView : this._view;
    this._chartEntityId = entityId;
    this._chartRange = "day";
    this._chartData = [];
    this._chartDataIsStatistic = false;
    this._chartError = "";
    this._chartRequestKey = "";
    this._view = "history";
    this._loadHistory();
    this._scheduleRender();
  }

  _loadHistory() {
    const entityId = this._chartEntityId;
    if (!entityId || !this._hass || typeof this._hass.callWS !== "function") return;
    const ranges = { hour: 60, day: 24 * 60, week: 7 * 24 * 60, month: 30 * 24 * 60 };
    const minutes = ranges[this._chartRange] || ranges.day;
    const end = new Date();
    const start = new Date(end.getTime() - minutes * 60 * 1000);
    const key = `${entityId}|${this._chartRange}|${Math.floor(end.getTime() / 30000)}`;
    if (key === this._chartRequestKey) return;
    this._chartRequestKey = key;
    this._chartData = [];
    this._chartDataIsStatistic = false;
    this._chartError = "";
    const requestSerial = ++this._chartRequestSerial;
    const loadStateHistory = () => this._hass.callWS({
      type: "history/history_during_period",
      start_time: start.toISOString(),
      end_time: end.toISOString(),
      entity_ids: [entityId],
      minimal_response: true,
      no_attributes: true,
      significant_changes_only: true,
    }).then((history) => ({ data: this._parseHistoryResponse(history, entityId), isStatistic: false }));
    const loadData = ["week", "month"].includes(this._chartRange)
      ? this._loadLongTermStatistics(entityId, start, end).catch(() => null).then((statistics) =>
        statistics && statistics.data.length ? statistics : loadStateHistory())
      : loadStateHistory();
    loadData.then(({ data, isStatistic }) => {
      if (requestSerial !== this._chartRequestSerial) return;
      this._chartData = data;
      this._chartDataIsStatistic = isStatistic;
      this._chartError = "";
      this._scheduleRender();
    }).catch((error) => {
      if (requestSerial !== this._chartRequestSerial) return;
      this._chartData = [];
      this._chartError = String(error && error.message ? error.message : error);
      this._scheduleRender();
    });
  }

  async _loadLongTermStatistics(entityId, start, end) {
    const metadata = await this._hass.callWS({
      type: "recorder/get_statistics_metadata",
      statistic_ids: [entityId],
    });
    const statistic = Array.isArray(metadata)
      ? metadata.find((item) => item.statistic_id === entityId)
      : null;
    if (!statistic) return null;

    const entity = this._hass.states[entityId];
    const stateClass = entity?.attributes?.state_class;
    const isCounter = stateClass === "total" || stateClass === "total_increasing";
    const types = isCounter
      ? ["change", "sum", "state"]
      : ["mean", "state"];
    const result = await this._hass.callWS({
      type: "recorder/statistics_during_period",
      start_time: start.toISOString(),
      end_time: end.toISOString(),
      statistic_ids: [entityId],
      period: this._chartRange === "month" ? "day" : "hour",
      types,
    });
    const rows = result && Array.isArray(result[entityId]) ? result[entityId] : [];
    const data = rows.map((row) => {
      const time = typeof row.start === "number" ? row.start * 1000 : Date.parse(row.start || "");
      const rawValue = isCounter ? row.sum ?? row.state : row.mean ?? row.state;
      const value = rawValue === null || rawValue === undefined ? Number.NaN : Number(rawValue);
      const rawDelta = row.change;
      const delta = rawDelta === null || rawDelta === undefined ? null : Number(rawDelta);
      return { time, value, delta };
    }).filter((row) => Number.isFinite(row.time) && (Number.isFinite(row.value) || Number.isFinite(row.delta)))
      .sort((a, b) => a.time - b.time);
    return { data, isStatistic: true };
  }

  _parseHistoryResponse(history, entityId) {
    const rows = history && Array.isArray(history[entityId])
      ? history[entityId]
      : Array.isArray(history) && Array.isArray(history[0])
        ? history[0]
        : Array.isArray(history)
          ? history
          : [];
    return rows
      .map((row) => {
        const rawTime = row.lc ?? row.lu ?? row.last_changed ?? row.last_updated;
        const time = typeof rawTime === "number"
          ? rawTime * 1000
          : Date.parse(rawTime || "");
        return { time, value: Number(row.s ?? row.state) };
      })
      .filter((row) => Number.isFinite(row.time) && Number.isFinite(row.value))
      .sort((a, b) => a.time - b.time);
  }

  _historyChart(entity) {
    const rangeMinutes = { hour: 60, day: 24 * 60, week: 7 * 24 * 60, month: 30 * 24 * 60 }[this._chartRange] || 1440;
    const end = Date.now();
    const start = end - rangeMinutes * 60 * 1000;
    const count = 72;
    const attrs = entity.attributes || {};
    const isCounter = attrs.state_class === "total_increasing" || attrs.state_class === "total";
    const buckets = Array.from({ length: count }, () => (isCounter ? 0 : null));
    const points = this._chartData;
    if (isCounter) {
      if (this._chartDataIsStatistic) {
        points.forEach((point) => {
          const delta = Number.isFinite(point.delta) ? point.delta : point.value;
          if (!Number.isFinite(delta) || delta <= 0) return;
          const bucket = Math.min(count - 1, Math.max(0, Math.floor((point.time - start) / (end - start) * count)));
          buckets[bucket] += delta;
        });
      } else for (let i = 1; i < points.length; i += 1) {
        let delta = points[i].value - points[i - 1].value;
        if (delta < 0) {
          if (attrs.state_class === "total" && points[i].value >= 0) delta = points[i].value;
          else continue;
        }
        if (delta === 0) continue;
        const bucket = Math.min(count - 1, Math.max(0, Math.floor((points[i].time - start) / (end - start) * count)));
        buckets[bucket] += delta;
      }
    } else {
      points.forEach((point) => {
        const bucket = Math.min(count - 1, Math.max(0, Math.floor((point.time - start) / (end - start) * count)));
        buckets[bucket] = point.value;
      });
      let previous = null;
      buckets.forEach((value, index) => {
        if (value !== null) previous = value;
        else if (previous !== null) buckets[index] = previous;
      });
    }
    const populated = isCounter ? buckets.some((value) => value > 0) : points.length > 0;
    const visibleBuckets = buckets.filter((value) => value !== null);
    const currentValue = Number(entity.state);
    const rangeValues = [...visibleBuckets, ...(Number.isFinite(currentValue) ? [currentValue] : [])];
    const minValue = isCounter ? 0 : Math.min(...rangeValues);
    const maxValue = Math.max(...rangeValues, isCounter ? 0 : minValue + 1);
    const span = maxValue - minValue || 1;
    const width = 900;
    const height = 300;
    const plotLeft = 92;
    const plotWidth = width - plotLeft;
    const chartPoints = buckets.map((value, index) => ({
      x: plotLeft + (index / Math.max(1, count - 1)) * plotWidth,
      y: height - (((value === null ? minValue : value) - minValue) / span) * (height - 24) - 12,
      value,
    }));
    const path = isCounter
      ? ""
      : (() => {
        let drawing = false;
        return chartPoints.map((point) => {
          if (point.value === null) {
            drawing = false;
            return "";
          }
          const command = drawing ? "L" : "M";
          drawing = true;
          return `${command}${point.x.toFixed(1)},${point.y.toFixed(1)}`;
        }).filter(Boolean).join(" ");
      })();
    const bars = isCounter ? chartPoints.map((point, index) => {
      const barWidth = plotWidth / count * 0.66;
      const barHeight = Math.max(0, (point.value / (maxValue || 1)) * (height - 24));
      return `<rect x="${(point.x - barWidth / 2).toFixed(1)}" y="${(height - barHeight).toFixed(1)}" width="${barWidth.toFixed(1)}" height="${barHeight.toFixed(1)}" rx="2" class="chart-bar"><title>${this._escape(`${this._formatHistoryTime(start + index / count * (end - start))}: ${this._formatHistoryValue(point.value, attrs.unit_of_measurement)}`)}</title></rect>`;
    }).join("") : "";
    const line = path ? `<path d="${path}" class="chart-line"/>` : "";
    const labels = [0, 1, 2, 3].map((index) => {
      const y = 18 + index * ((height - 36) / 3);
      const value = maxValue - (index / 3) * span;
      return `<g><line x1="${plotLeft}" x2="${width}" y1="${y}" y2="${y}" class="chart-gridline"/><text x="0" y="${y - 4}" class="chart-axis-label">${this._escape(this._formatHistoryValue(value, attrs.unit_of_measurement))}</text></g>`;
    }).join("");
    const statusMessage = this._chartError
      ? `<div class="empty">${this._escape(this._t("history_error"))}</div>`
      : !populated
        ? `<div class="empty">${this._escape(this._t("history_empty"))}</div>`
        : "";
    const summary = points.length ? this._historySummary(points, attrs.unit_of_measurement, isCounter, buckets) : "";
    return `<section class="section history-section"><div class="section-head"><div><h2>${this._escape(this._label(entity))}</h2><small>${this._escape(attrs.unit_of_measurement || this._t("sensor_history"))}</small></div><button class="tab" type="button" data-history-back>${this._escape(this._t("back_to_dashboard"))}</button></div><div class="history-current"><span>${this._escape(this._t("current_value"))}</span><strong>${this._escape(this._value(entity))}</strong></div><div class="history-ranges">${[["hour", "1 h"], ["day", this._t("day")], ["week", this._t("week")], ["month", this._t("month")]].map(([range, label]) => `<button type="button" class="tab ${this._chartRange === range ? "active" : ""}" data-history-range="${range}">${this._escape(label)}</button>`).join("")}</div>${statusMessage || `<div class="history-chart-wrap"><svg class="history-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${this._escape(this._t("history_chart"))}">${labels}${bars}${line}</svg></div>`}<div class="history-axis"><span>${this._escape(this._formatHistoryTime(start))}</span><span>${this._escape(this._formatHistoryTime(end))}</span></div>${summary ? `<div class="history-summary">${summary}</div>` : ""}<p class="explain">${this._escape(this._t(isCounter ? "history_counter_note" : "history_note"))}</p></section>`;
  }

  _formatHistoryTime(timestamp) {
    const date = new Date(timestamp);
    const options = this._chartRange === "hour" || this._chartRange === "day"
      ? { hour: "2-digit", minute: "2-digit" }
      : { day: "2-digit", month: "2-digit", hour: "2-digit" };
    return date.toLocaleString(this._hass && this._hass.locale ? this._hass.locale.language : undefined, options);
  }

  _formatHistoryValue(value, unit) {
    const locale = this._hass && this._hass.locale ? this._hass.locale.language : undefined;
    const normalizedUnit = String(unit || "").toLowerCase().replace(/\s+/g, "");
    const precision = normalizedUnit === "kwh" ? 3 : ["eur", "€", "eur/kwh", "€/kwh"].includes(normalizedUnit) ? 2 : 1;
    return `${Number(value).toLocaleString(locale, { maximumFractionDigits: precision })}${unit ? ` ${unit}` : ""}`;
  }

  _historySummary(points, unit, isCounter, buckets) {
    if (isCounter) {
      const increase = buckets.reduce((sum, value) => sum + value, 0);
      const maximumInterval = Math.max(0, ...buckets);
      return [[this._t("period_increase"), increase], [this._t("max_interval"), maximumInterval]]
        .map(([label, value]) => `<span>${this._escape(label)} <strong>${this._escape(this._formatHistoryValue(value, unit))}</strong></span>`)
        .join("");
    }
    const values = points.map((point) => point.value);
    const minimum = Math.min(...values);
    const maximum = Math.max(...values);
    const latest = values[values.length - 1];
    return [[this._t("minimum"), minimum], [this._t("maximum"), maximum], [this._t("latest"), latest]]
      .map(([label, value]) => `<span>${this._escape(label)} <strong>${this._escape(this._formatHistoryValue(value, unit))}</strong></span>`)
      .join("");
  }

  _overviewMetrics(entities) {
    const sources = (this._panel && this._panel.config && this._panel.config.power_sources) || [];
    const groups = sources.map((source) => {
      const cards = [];
      if (source.soc) cards.push(this._metricCard(this._t("battery"), source.soc, ["battery soc", "ladezustand", "akku soc", "soc"]));
      if (source.pv) cards.push(this._metricCard(this._t("pv_power"), source.pv, ["pv power", "pv leistung", "solar power", "solarleistung"]));
      if (source.native_pv) cards.push(this._metricCard(this._t("native_pv_source"), source.native_pv));
      if (source.battery_power) cards.push(this._metricCard(this._t("battery_power"), source.battery_power, ["battery power", "batterieleistung", "native hardware power w"]));
      if (source.grid_power) cards.push(this._metricCard(this._t("grid_power"), source.grid_power, ["grid power", "netzleistung", "netzbezug"]));
      else {
        if (source.grid_import) cards.push(this._metricCard(this._t("grid_import"), source.grid_import, ["grid import", "netzbezug", "bezug"]));
        if (source.grid_export) cards.push(this._metricCard(this._t("grid_export"), source.grid_export, ["grid export", "netzeinspeisung", "einspeisung"]));
      }
      if (source.offgrid_power) cards.push(this._metricCard(this._t("offgrid_source"), source.offgrid_power, ["offgrid power", "off grid power", "off grid ausgang"]));
      if (!cards.length) return "";
      return `<section class="metric-group"><h3>${this._escape(source.name || this._t("system"))}</h3><div class="metric-grid">${cards.join("")}</div></section>`;
    }).filter(Boolean);

    if (groups.length) return groups.join("");

    const metrics = [
      [this._t("battery"), ["ladezustand", "soc", "battery level"]],
      [this._t("pv_power"), ["pv power", "pv-leistung", "solar power", "solarleis"]],
      [this._t("battery_power"), ["batterieleistung", "battery power", "charge power"]],
      [this._t("grid_power"), ["netz-leistung", "grid power", "netzbezug"]],
    ];
    return metrics.map(([title, terms]) => {
      const entity = this._find(entities, terms);
      return this._metricCard(title, entity && entity.entity_id);
    }).join("");
  }

  _render() {
    if (!this.shadowRoot || !this._hass) return;
    if (this._pointerActive) {
      this._renderDeferred = true;
      return;
    }
    this._renderDeferred = false;
    const entities = this._entities();
    const cards = this._overviewMetrics(entities);

    const systems = this._nativeSystems(entities);
    this._currentSystems = systems;
    const systemSignals = this._systemSignalEntities(entities);
    const packCount = systems.reduce((count, system) => count + (system.packs || []).length, 0);
    const lastUpdated = entities.reduce((latest, entity) => {
      const stamp = Date.parse(entity.last_updated || "");
      return Number.isFinite(stamp) && stamp > latest ? stamp : latest;
    }, 0);
    const updated = lastUpdated ? new Date(lastUpdated).toLocaleTimeString() : this._t("no_data");
    const historyEntity = this._chartEntityId && this._hass.states[this._chartEntityId];
    const activeContent = this._view === "history" && historyEntity
      ? this._historyChart(historyEntity)
      : this._view === "energy"
      ? this._energyView(entities)
      : this._view === "economics"
        ? this._economicsView(entities)
        : this._view === "controls"
          ? this._controls(entities)
        : `${this._healthSummary(systems)}<section class="section"><div class="section-head"><h2>${this._escape(this._t("topology"))}</h2><small>${systems.length} ${this._escape(this._t("systems"))} · ${packCount} ${this._escape(this._t("packs"))}</small></div>
          ${systems.length ? `<div class="systems">${systems.map((system, systemIndex) => {
            const systemEntities = this._deviceEntities(entities, system.name, null);
            const systemDetails = [
              [this._t("model"), system.model], [this._t("profile"), system.profile],
              [this._t("communication"), system.transport], [this._t("status"), system.status],
              [this._t("last_data"), system.data_age_seconds == null ? "—" : `${system.data_age_seconds} ${this._t("seconds_ago")}`],
            ].map(([label, value]) => `<div class="detail-row"><span>${label}</span><strong>${this._escape(value || "—")}</strong></div>`).join("");
            const packCards = (system.packs || []).map((pack, index) => {
              const packNumber = index + 1;
              const detailId = `pack-details-${systemIndex}-${packNumber}`;
              const packEntities = this._deviceEntities(entities, system.name, packNumber);
              const packRows = this._detailRows(packEntities, 5, system.name, packNumber);
              return `<article class="pack-card"><div class="pack-head"><div><strong>↳ ${this._escape(this._t("battery_pack"))} ${packNumber}</strong><small>${this._escape(pack.model || this._t("zendure_pack"))}</small></div><button class="details-toggle" type="button" data-details-toggle="${detailId}" aria-controls="${detailId}" aria-expanded="false">${this._escape(this._t("details"))}</button></div><aside class="hover-details" id="${detailId}"><h3>${this._escape(this._t("battery_pack"))} ${packNumber}</h3>${packRows || `<div class="detail-row"><span>${this._escape(this._t("telemetry"))}</span><strong>${this._escape(this._t("unavailable"))}</strong></div>`}</aside></article>`;
            }).join("");
            const systemDetailId = `system-details-${systemIndex}`;
            return `<article class="system-card"><div class="system-head"><div><strong>${this._escape(system.name || this._t("system"))}</strong><small>${this._escape(system.model || system.profile || this._t("zendure_hardware"))}</small></div><div class="system-actions"><span class="status ${system.online ? "" : "offline"}">${this._escape(this._t(system.online ? "online" : "offline"))}</span><button class="details-toggle" type="button" data-details-toggle="${systemDetailId}" aria-controls="${systemDetailId}" aria-expanded="false">${this._escape(this._t("details"))}</button></div></div><div class="device-meta">${this._escape(system.transport || this._t("unknown_path"))} · ${this._escape(system.status || this._t("unknown_status"))}</div><div class="packs">${packCards || `<div class="device-meta">${this._escape(this._t("no_packs"))}</div>`}</div><aside class="hover-details" id="${systemDetailId}"><h3>${this._escape(system.name || this._t("system"))}</h3>${systemDetails}${this._detailRows(systemEntities)}</aside></article>`;
          }).join("")}</div>` : `<div class="empty">${this._escape(this._t("native_empty"))}</div>`}
        </section><section class="section"><div class="section-head"><h2>${this._escape(this._t("system_signals"))}</h2><small>${systemSignals.length} ${this._escape(this._t("additional_signals"))}</small></div><div class="inventory signal-grid">${systemSignals.map((entity) => `<div class="entity signal-entity history-card" data-history-entity="${this._escape(entity.entity_id)}" role="button" tabindex="0" aria-label="${this._escape(`${this._signalLabel(entity)} · ${this._t("show_history")}`)}"><span>${this._escape(this._signalLabel(entity))}</span><strong class="signal-value" title="${this._escape(this._value(entity))}">${this._escape(this._value(entity))}</strong></div>`).join("") || `<div class="empty">${this._escape(this._t("waiting_entities"))}</div>`}</div></section>`;

    this.shadowRoot.innerHTML = `
      <style>
        :host{display:block;min-height:100%;background:#101214;color:#e7e9eb;font-family:Inter,"Segoe UI",sans-serif;--line:#34383d;--muted:#a4a9af;--cyan:#16c4df;--green:#56cf83;--amber:#f0c34e}
        *{box-sizing:border-box}.shell{max-width:1500px;margin:auto;padding:28px clamp(18px,3vw,42px) 56px}
        header{display:flex;align-items:center;justify-content:space-between;gap:20px;margin-bottom:24px}h1{font-size:clamp(24px,3vw,36px);margin:0;font-weight:650;letter-spacing:-.03em}.sub{color:var(--muted);margin:8px 0 0}.versionline{display:block;color:var(--muted);font-size:11px;margin-top:6px}.badge{border:1px solid #365245;color:#a8e5ba;background:#1e3026;border-radius:999px;padding:9px 14px;font-size:13px;white-space:nowrap}
        .section{background:#1b1e21;border:1px solid var(--line);border-radius:14px;padding:20px;margin-top:18px}.section-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:16px}.section h2{font-size:17px;margin:0}.section-head small,.muted{color:var(--muted)}
        nav{display:flex;gap:8px;margin:8px 0 18px;border-bottom:1px solid var(--line);padding-bottom:12px}.tab{border:1px solid #41464b;background:#25292d;color:#c4c8cc;border-radius:8px;padding:9px 15px;font:inherit;cursor:pointer}.tab.active{border-color:#2388ad;background:#183847;color:#e5f8fc}.tab:focus-visible,.apply:focus-visible{outline:2px solid var(--cyan);outline-offset:2px}.metrics{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px}.metric{min-height:125px;padding:18px;border:1px solid #41464b;border-top:3px solid var(--cyan);border-radius:11px;background:#292d31;display:flex;flex-direction:column;gap:11px}.metric:nth-child(2){border-top-color:var(--green)}.metric:nth-child(3){border-top-color:var(--amber)}.metric span{font-size:11px;letter-spacing:.11em;color:#b1b5b9}.metric strong{font-size:clamp(21px,2vw,30px);font-variant-numeric:tabular-nums}.metric small{color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
        .reading-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px}.reading{min-height:105px;padding:15px;border:1px solid #41464b;border-radius:10px;background:#272b2f;display:flex;flex-direction:column;gap:8px}.reading span{color:#bdc2c6;font-size:12px}.reading strong{font-size:22px;font-variant-numeric:tabular-nums}.reading small{color:var(--muted);line-height:1.35}.forecast-groups{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,280px),1fr));gap:14px}.forecast-group{min-width:0;padding:12px;border:1px solid #343a40;border-radius:11px;background:#202428}.forecast-group h3{font-size:13px;color:#c7cbd0;margin:0 0 10px}.forecast-group .reading{min-height:92px;padding:12px}.forecast-group .reading-grid{grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}.flow-grid{display:grid;gap:8px}.flow-row{display:grid;grid-template-columns:minmax(130px,1fr) 3fr minmax(85px,.7fr);gap:14px;align-items:center;padding:9px 0;border-bottom:1px solid var(--line)}.flow-row span{color:#c3c7ca}.flow-row strong{text-align:right;font-variant-numeric:tabular-nums}.flow-track{height:9px;background:#30353a;border-radius:999px;overflow:hidden}.flow-track i{display:block;width:48%;height:100%;background:linear-gradient(90deg,#1bb7df,#54d08a);border-radius:999px}.explain{color:var(--muted);font-size:12px;line-height:1.5;margin:14px 0 0}.subsection{margin-top:18px}.subsection h3{font-size:14px;color:#c7cbd0;margin:0 0 10px}.control-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,230px),1fr));gap:11px}.control-card{min-width:0;padding:14px;border:1px solid #41464b;border-radius:10px;background:#272b2f;display:flex;flex-direction:column;gap:10px}.control-card label{font-size:13px;color:#d1d5d8}.control-card select,.control-card input{width:100%;min-width:0;background:#171a1d;color:#eef0f1;border:1px solid #4b535a;border-radius:7px;padding:10px;font:inherit}.number-control{display:flex;align-items:center;gap:8px}.number-control span{color:var(--muted);min-width:30px}.control-card small{color:var(--muted);font-size:11px}.apply{align-self:flex-end;border:1px solid #247b9b;background:#153746;color:#dff8ff;border-radius:7px;padding:7px 12px;font:inherit;cursor:pointer}.apply:disabled{opacity:.65;cursor:wait}
        .metric-groups{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr));gap:12px}.metric-group{padding:13px;border:1px solid #343a40;border-radius:11px;background:#202428}.metric-group h3{font-size:13px;color:#c7cbd0;margin:0 0 10px}.metric-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,150px),1fr));gap:10px}.metric-grid .metric{min-height:108px;padding:15px}.metric-grid .metric:nth-child(2){border-top-color:var(--green)}.metric-grid .metric:nth-child(3){border-top-color:var(--amber)}
        .systems{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));gap:14px}.system-card{min-width:0;position:relative;padding:17px;background:#172b3a;border:1px solid #2476a8;border-left:4px solid var(--cyan);border-radius:11px}.system-head,.pack-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}.system-head>div:first-child,.pack-head>div:first-child{min-width:0;overflow-wrap:anywhere}.system-head strong,.pack-head strong{font-size:16px}.system-head small,.pack-head small,.device-meta{display:block;color:#b7c4ce;margin-top:6px}.system-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap;justify-content:flex-end}.status{border:1px solid #40604c;background:#20352a;color:#a8e5ba;border-radius:999px;padding:5px 9px;font-size:11px;white-space:nowrap}.status.offline{border-color:#744849;background:#3a2526;color:#f2aaaa}.packs{margin:15px 0 0 14px;padding-left:16px;border-left:1px solid #388ebc;display:grid;gap:9px}.pack-card{min-width:0;position:relative;padding:12px;background:#202b35;border:1px solid #475563;border-radius:9px}.pack-card strong{display:block}.pack-card small{display:block;color:#aeb8c1;margin-top:5px}.details-toggle{border:1px solid #3f6578;background:#1a3442;color:#d9f5fb;border-radius:7px;padding:6px 9px;font:inherit;font-size:12px;cursor:pointer;white-space:nowrap}.details-toggle:hover,.details-toggle:focus-visible{border-color:var(--cyan);outline:2px solid var(--cyan);outline-offset:2px}.hover-details{display:none;position:absolute;z-index:5;left:12px;top:calc(100% + 9px);width:min(380px,calc(100vw - 56px));padding:14px;background:#f7f8fa;color:#20242a;border:1px solid #d7dce2;border-radius:10px;box-shadow:0 12px 35px #0008}.system-card.details-open>.hover-details,.pack-card.details-open>.hover-details{display:block}@media(hover:hover){.system-card:hover:not(:has(.pack-card:hover))>.hover-details,.pack-card:hover>.hover-details{display:block}}.hover-details h3{margin:0 0 9px;font-size:14px}.detail-row{display:flex;justify-content:space-between;gap:12px;padding:6px 0;border-bottom:1px solid #e5e7eb;font-size:12px}.detail-row span{color:#59616a}.detail-row strong{text-align:right;overflow-wrap:anywhere}.empty{color:var(--muted);padding:18px;border:1px dashed #485058;border-radius:10px}.inventory{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,240px),1fr));gap:8px}.entity{min-width:0;display:flex;justify-content:space-between;gap:12px;padding:11px 12px;border-bottom:1px solid #34383d}.entity span{color:#c2c6ca;overflow-wrap:anywhere}.entity strong{font-weight:550;text-align:right;font-variant-numeric:tabular-nums;overflow-wrap:anywhere}.signal-grid{grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr))}.signal-entity{display:grid;grid-template-columns:minmax(0,1fr) minmax(5rem,auto);align-items:start}.signal-value{max-width:45%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.footer{color:#858c92;font-size:12px;margin:16px 2px}
        .health-summary{border-left:4px solid var(--green)}.health-summary.attention{border-left-color:var(--amber)}.health-state{border:1px solid #40604c;background:#20352a;color:#a8e5ba;border-radius:999px;padding:6px 10px;font-size:12px;white-space:nowrap}.health-summary.attention .health-state{border-color:#78633b;background:#3a3120;color:#f4d78b}.health-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.health-grid article{display:flex;flex-direction:column;gap:7px;padding:12px 14px;background:#25292d;border:1px solid #3a3f44;border-radius:9px}.health-grid small{color:var(--muted)}.health-grid strong{font-size:18px;font-variant-numeric:tabular-nums}
        @media(max-width:900px){.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.topology{grid-template-columns:1fr}.link{height:20px;width:1px;margin:auto}}@media(max-width:520px){header{align-items:flex-start;flex-direction:column}.metrics{grid-template-columns:1fr 1fr}.systems{grid-template-columns:1fr}.health-grid{grid-template-columns:1fr}.section-head{align-items:flex-start;flex-direction:column}.forecast-source-hint{max-width:100%;text-align:left}.hover-details{position:static;width:auto;max-width:100%;margin-top:12px;box-shadow:none}.system-card.details-open>.hover-details,.pack-card.details-open>.hover-details{display:block}.metric{padding:13px}.section{padding:15px}}@media(max-width:360px){nav{gap:5px;overflow-x:auto}.tab{flex:0 0 auto;padding:8px 10px}.metrics{grid-template-columns:1fr}.health-grid{gap:7px}}
        .flow-grid{display:grid;gap:9px;margin-top:10px}.flow-row{display:grid;grid-template-columns:minmax(85px,.8fr) minmax(110px,1.6fr) minmax(85px,.8fr) minmax(80px,.6fr);gap:12px;align-items:center;padding:8px 0;border-bottom:1px solid var(--line)}.flow-node{min-width:0;padding:9px 11px;border:1px solid #41464b;border-radius:9px;background:#272b2f}.flow-node small{display:block;color:var(--muted);font-size:10px}.flow-node strong{display:block;margin-top:3px;font-size:13px}.flow-route{min-width:0;display:flex;flex-direction:column;gap:5px}.flow-label{color:#c3c7ca;font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.flow-direction{display:flex;align-items:center;gap:8px;color:var(--cyan)}.flow-direction>span{font-size:20px;line-height:1}.flow-track{height:8px;flex:1;background:#30353a;border-radius:999px;overflow:hidden}.flow-track i{display:block;height:100%;background:linear-gradient(90deg,#1bb7df,#54d08a);border-radius:999px}.flow-route.unavailable .flow-track{background:repeating-linear-gradient(135deg,#363b40,#363b40 4px,#25292d 4px,#25292d 8px)}.flow-route.unavailable .flow-track i{display:none}.flow-value{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}.flow-scale{color:var(--muted)}
        @media(max-width:520px){.flow-row{grid-template-columns:minmax(0,1fr) minmax(0,1.2fr) minmax(0,1fr) minmax(0,.7fr);gap:6px}.flow-node{padding:8px 7px}.flow-node strong{font-size:12px;overflow-wrap:anywhere}.flow-label{font-size:10px}.flow-direction{gap:4px}.flow-direction>span{font-size:16px}.flow-value{font-size:12px}}@media(max-width:360px){.flow-row{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}.flow-route{grid-column:1 / -1}.flow-value{grid-column:2;text-align:right}}
        .forecast-source-hint{max-width:70%;text-align:right;line-height:1.4;overflow-wrap:anywhere}.forecast-day-chart{display:grid;gap:12px}.forecast-bar-row{display:grid;grid-template-columns:minmax(52px,.65fr) minmax(70px,2fr) minmax(72px,.85fr);gap:9px;align-items:center;font-size:12px}.forecast-bar-row>span{color:#c3c7ca}.forecast-bar-row>strong{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}.forecast-bar-track{height:11px;background:#30353a;border-radius:999px;overflow:hidden}.forecast-bar-track i{display:block;height:100%;background:linear-gradient(90deg,#1bb7df,#54d08a);border-radius:999px}.forecast-bar-row.unavailable .forecast-bar-track{background:repeating-linear-gradient(135deg,#363b40,#363b40 4px,#25292d 4px,#25292d 8px)}.forecast-bar-row.unavailable .forecast-bar-track i{display:none}
        @media(max-width:520px){.forecast-bar-row{grid-template-columns:minmax(0,.6fr) minmax(0,1fr) minmax(0,.8fr);gap:6px;font-size:11px}.forecast-bar-row>span,.forecast-bar-row>strong{overflow-wrap:anywhere}}
        @media(hover:hover){.system-card:hover:not(:has(.pack-card:hover))>.hover-details,.pack-card:hover>.hover-details{display:none}}
        .system-card.details-open>.hover-details,.pack-card.details-open>.hover-details{display:block!important}
        .signal-grid{grid-template-columns:repeat(auto-fit,minmax(min(100%,380px),1fr))}.signal-entity{grid-template-columns:minmax(0,1fr) minmax(8rem,35%);align-items:center}.signal-value{max-width:none;white-space:normal;overflow:visible;text-overflow:clip;overflow-wrap:anywhere}
        .history-card{cursor:pointer;transition:border-color .15s ease,box-shadow .15s ease}.history-card:hover{border-color:var(--cyan)}.history-card:focus-visible{border-color:var(--cyan);box-shadow:0 0 0 2px #16c4df55}.history-card small{font-size:11px}.home-link{display:inline-flex;align-items:center;gap:7px;margin-top:12px;padding:9px 12px;border:1px solid #3f6578;border-radius:8px;background:#1a3442;color:#d9f5fb;text-decoration:none;font-size:13px}.home-link:hover,.home-link:focus-visible{border-color:var(--cyan);outline:2px solid var(--cyan);outline-offset:2px}.history-section .section-head>div{min-width:0;overflow-wrap:anywhere}.history-section .section-head small{display:block;margin-top:5px;overflow-wrap:anywhere}.history-current{display:flex;justify-content:space-between;align-items:center;gap:12px;margin:12px 0;padding:15px 17px;border:1px solid #41464b;border-left:3px solid var(--cyan);border-radius:10px;background:#272b2f}.history-current span{color:var(--muted)}.history-current strong{font-size:clamp(20px,3vw,28px);font-variant-numeric:tabular-nums}.history-ranges{display:flex;gap:7px;margin:14px 0;overflow-x:auto}.history-chart-wrap{width:100%;padding:12px;border:1px solid #343a40;border-radius:11px;background:#202428;overflow:hidden}.history-chart{display:block;width:100%;height:auto;min-height:180px;overflow:visible}.chart-gridline{stroke:#41464b;stroke-width:1}.chart-axis-label{fill:#a4a9af;font-size:11px}.chart-line{fill:none;stroke:#16c4df;stroke-width:3;stroke-linecap:round;stroke-linejoin:round;vector-effect:non-scaling-stroke}.chart-bar{fill:#16c4df;opacity:.86}.history-axis{display:flex;justify-content:space-between;gap:10px;margin-top:8px;color:var(--muted);font-size:11px}.history-summary{display:flex;flex-wrap:wrap;gap:10px;margin-top:13px}.history-summary span{display:flex;gap:7px;padding:9px 12px;border:1px solid #41464b;border-radius:999px;background:#25292d;color:var(--muted);font-size:12px}.history-summary strong{color:#e7e9eb;font-variant-numeric:tabular-nums}
        @media(max-width:520px){.shell{padding:16px 12px 34px}.home-link{min-height:44px}.history-chart-wrap{padding:6px}.history-chart{min-height:160px}.history-current{padding:12px}.history-section .section-head{flex-direction:row;align-items:center}}
      </style>
      <main class="shell">
        <header><div><h1>Battery SmartFlow AI Portal</h1><p class="sub">${this._escape(this._t("subtitle"))}</p><small class="versionline">${this._escape(this._t("version"))} ${this._escape(this._panel?.config?.integration_version || "—")} · ${this._escape(this._t("dashboard_version"))} ${this._escape(this._panel?.config?.dashboard_version || "—")}</small><a class="home-link" href="/" data-home>← ${this._escape(this._t("home_assistant"))}</a></div><div class="badge">● ${this._escape(this._t("live"))} ${this._escape(updated)}</div></header>
        <section class="section"><div class="section-head"><h2>${this._escape(this._t("energy_overview"))}</h2><small>${this._escape(this._t("live_values"))}</small></div><div class="metric-groups">${cards}</div></section>
        <nav aria-label="${this._escape(this._t("dashboard_views"))}"><button class="tab ${this._view === "overview" ? "active" : ""}" data-view="overview">${this._escape(this._t("overview"))}</button><button class="tab ${this._view === "energy" ? "active" : ""}" data-view="energy">${this._escape(this._t("energy"))}</button><button class="tab ${this._view === "economics" ? "active" : ""}" data-view="economics">${this._escape(this._t("economics"))}</button><button class="tab ${this._view === "controls" ? "active" : ""}" data-view="controls">${this._escape(this._t("controls"))}</button></nav>
        ${activeContent}
        <p class="footer">${this._escape(this._t("footer"))}</p>
      </main>`;
    if (this._openDetailId) {
      const openButton = [...this.shadowRoot.querySelectorAll("[data-details-toggle]")]
        .find((button) => button.dataset.detailsToggle === this._openDetailId);
      if (openButton) {
        const openCard = openButton.closest(".system-card, .pack-card");
        openCard?.classList.add("details-open");
        openButton.setAttribute("aria-expanded", "true");
        openButton.textContent = this._t("hide_details");
      } else {
        this._openDetailId = null;
      }
    }
    this.shadowRoot.querySelectorAll("[data-apply-select]").forEach((button) => {
      button.addEventListener("click", () => {
        const entityId = button.dataset.applySelect;
        const select = this.shadowRoot.querySelector(`[data-control-select="${CSS.escape(entityId)}"]`);
        const option = select ? select.value : undefined;
        if (option !== undefined) this._applyControl("select_option", entityId, { option });
      });
    });
    this.shadowRoot.querySelectorAll("[data-apply-number]").forEach((button) => {
      button.addEventListener("click", () => {
        const entityId = button.dataset.applyNumber;
        const input = this.shadowRoot.querySelector(`[data-control-number="${CSS.escape(entityId)}"]`);
        const value = Number(input ? input.value : NaN);
        if (input && input.reportValidity() && Number.isFinite(value)) this._applyControl("set_value", entityId, { value });
      });
    });
    this.shadowRoot.querySelectorAll("[data-details-toggle]").forEach((button) => {
      button.addEventListener("click", () => {
        const details = this.shadowRoot.getElementById(button.dataset.detailsToggle);
        const card = button.closest(".system-card, .pack-card");
        if (!details || !card) return;
        const open = card.classList.toggle("details-open");
        this._openDetailId = open ? button.dataset.detailsToggle : null;
        if (open) {
          this.shadowRoot.querySelectorAll(".details-open").forEach((otherCard) => {
            if (otherCard === card) return;
            otherCard.classList.remove("details-open");
            const otherButton = otherCard.querySelector("[data-details-toggle]");
            if (otherButton) {
              otherButton.setAttribute("aria-expanded", "false");
              otherButton.textContent = this._t("details");
            }
          });
        }
        button.setAttribute("aria-expanded", String(open));
        button.textContent = this._t(open ? "hide_details" : "details");
      });
    });
  }

  _escape(value) {
    return String(value).replace(/[&<>"']/g, (char) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[char]);
  }
}

customElements.define("battery-smartflow-ai-hems-dashboard", BatterySmartFlowDashboard);
