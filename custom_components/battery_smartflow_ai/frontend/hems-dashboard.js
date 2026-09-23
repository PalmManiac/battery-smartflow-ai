/* Battery SmartFlow AI's standalone HEMS dashboard. */
class BatterySmartFlowDashboard extends HTMLElement {
  set hass(hass) {
    this._hass = hass;
    const active = this.shadowRoot && this.shadowRoot.activeElement;
    if (active && active.matches("input, select")) return;
    this._render();
  }

  set narrow(narrow) {
    this._narrow = narrow;
    this._render();
  }

  set panel(panel) {
    this._panel = panel;
    this._render();
  }

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._view = "overview";
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

  _t(key) {
    const locale = this._hass && this._hass.locale ? this._hass.locale.language : "";
    const german = String(locale || "").toLowerCase().startsWith("de");
    const labels = {
      overview: ["Übersicht", "Overview"], energy: ["Energie & Prognose", "Energy & forecast"], economics: ["Wirtschaftlichkeit", "Economics"], controls: ["Steuerung", "Controls"],
      subtitle: ["Energiefluss, Speicher und Systemstatus", "Energy flow, storage and system status"], live: ["LIVE · aktualisiert", "LIVE · updated"], energy_overview: ["Energieübersicht", "Energy overview"], live_values: ["Aktuelle Home-Assistant-Werte", "Live Home Assistant values"],
      battery: ["AKKU", "BATTERY"], pv_power: ["PV-LEISTUNG", "PV POWER"], battery_power: ["AKKULEISTUNG", "BATTERY POWER"], grid_power: ["NETZLEISTUNG", "GRID POWER"], current_price: ["AKTUELLER PREIS", "CURRENT PRICE"], waiting_entity: ["Warte auf passenden Sensor", "Waiting for matching entity"], no_data: ["Noch keine Daten", "No data yet"],
      flows_today: ["Energieflüsse heute", "Today's energy flows"], ledger: ["Gemessenes BSFAI-Energiebuch", "Measured BSFAI energy ledger"], solar_forecast: ["Solarprognose", "Solar forecast"], forecast_compare: ["Brutto-Prognose und nutzbarer Rest", "Gross forecast versus usable remainder"],
      near_term: ["Nächste Stunden · nutzbar", "Next few hours · usable"], forecast_today: ["Heute · Brutto und nutzbar", "Today · gross and usable"], forecast_tomorrow: ["Morgen · Brutto und nutzbar", "Tomorrow · gross and usable"],
      power_now: ["Momentanleistung", "Instantaneous power"], power_note: ["Live-Messwerte · Watt (W)", "Live readings · watts (W)"], daily_energy_note: ["Aufsummierte Energiemengen heute · Kilowattstunden (kWh)", "Accumulated energy today · kilowatt-hours (kWh)"], grid_net: ["Netzleistung (Bezug + / Einspeisung −)", "Grid power (import + / export −)"], grid_import: ["Netzbezug", "Grid import"], grid_export: ["Netzeinspeisung", "Grid export"], pv_source: ["PV-Leistung", "PV power"], native_pv_source: ["Native PV-Leistung", "Native PV power"], offgrid_source: ["Off-Grid-Ausgang", "Off-grid output"], house_load_source: ["Hauslast", "House load"], battery_source: ["Akku-Leistung", "Battery power"],
      source_unavailable: ["Quelle nicht verfügbar", "Source unavailable"], no_power_readings: ["Keine konfigurierten oder nativen Leistungswerte gefunden.", "No configured or native power readings found."], per_system: ["Je System", "Per system"], shared_metrics: ["Gemeinsamer Wert", "Shared value"],
      pv_battery: ["PV → Akku", "PV → battery"], grid_battery: ["Netz → Akku", "Grid → battery"], battery_home: ["Akku → Haus", "Battery → home"], battery_grid: ["Akku → Netz", "Battery → grid"], native_pv_home: ["Native PV → Haus", "Native PV → home"], grid_export: ["Netzeinspeisung", "Grid export"],
      usable_3h: ["Nutzbar · nächste 3 Stunden", "Usable · next 3 hours"], usable_6h: ["Nutzbar · nächste 6 Stunden", "Usable · next 6 hours"], usable_today: ["Nutzbar · Rest des Tages", "Usable · rest of today"], gross_today: ["Brutto · Rest des Tages", "Gross · rest of today"], usable_tomorrow: ["Nutzbar · morgen", "Usable · tomorrow"], gross_tomorrow: ["Brutto · morgen", "Gross · tomorrow"],
      forecast_explain: ["Die nutzbare Prognose berücksichtigt die Planungsannahmen von BSFAI. Die Bruttowerte zeigen die importierte Prognose vor dieser Reduktion.", "Usable forecast reflects BSFAI's planning assumptions. Gross values show the imported forecast before that reduction."], economics_today: ["Wirtschaftlichkeit heute", "Today's economics"], daily_costs: ["Tageswerte und Kosten", "Daily value and costs"], battery_benefit: ["Akku-Nutzen", "Battery benefit"], avoided_import: ["Vermiedene Netzbezugskosten", "Avoided grid import"], grid_charge_cost: ["Netzladekosten", "Grid charging cost"], pv_opportunity_cost: ["PV-Opportunitätskosten", "PV opportunity cost"], export_revenue: ["Einspeiseerlös", "Export revenue"], self_consumption_value: ["Wert nativer PV-Eigenverbrauch", "Native PV self-consumption value"], average_values: ["Durchschnittliche Ist-Werte", "Average realized values"], ledger_based: ["Basierend auf dem BSFAI-Energie- und Kostenbuch", "Based on BSFAI's energy and cost ledger"], grid_charge_price: ["Netzladepreis", "Grid charging price"], pv_opportunity_value: ["PV-Opportunitätswert", "PV opportunity value"], blended_charge_price: ["Gewichteter Akku-Ladepreis", "Blended battery charge price"], export_price: ["Einspeisepreis", "Export price"], discharge_value: ["Wert der Akkuentladung", "Battery discharge value"], native_pv_return: ["Ertrag native PV direkt ins Haus", "Native PV to home return"], efficiency: ["Wirtschaftlicher Wirkungsgrad", "Economic efficiency"],
      blended_explain: ["Der gewichtete Akku-Ladepreis berücksichtigt die verbuchte Netz- und PV-Ladeenergie. Netzladekosten und PV-Opportunitätswert stammen aus demselben Kostenbuch wie die separaten Preissensoren.", "The blended battery charge price is weighted by recorded grid- and PV-charged energy. Grid charging cost and PV opportunity value use the same cost ledger as the separate price sensors."],
      operating_mode: ["Betriebsart", "Operating mode"], existing_selects: ["Vorhandene BSFAI-Auswahl-Entitäten", "Existing BSFAI select entities"], no_selects: ["Keine BSFAI-Auswahl für Betriebsart oder manuelle Aktion gefunden.", "No BSFAI mode or manual-action select entities were found."], settings: ["BSFAI-Einstellungen", "BSFAI settings"], saved_ha: ["Änderungen werden über Home-Assistant-Zahlen-Entitäten gespeichert", "Changes are saved through Home Assistant number entities"], no_numbers: ["Keine BSFAI-Zahlenregler gefunden.", "No BSFAI number settings were found."],
      automatic: ["Automatik", "Automatic"], self_sufficient: ["Autarkie", "Self-sufficient"], manual: ["Manuell", "Manual"], standby: ["Standby", "Standby"], charge: ["Laden", "Charge"], discharge: ["Entladen", "Discharge"], constant_discharge: ["Konstante Entladung", "Constant discharge"],
      limits_group: ["Leistungs- und SoC-Grenzen", "Power and SoC limits"], price_group: ["Preisstrategie", "Price strategy"], forecast_group: ["PV und Prognose", "PV and forecast"], other_group: ["Weitere Einstellungen", "Other settings"], allowed_range: ["Zulässiger Bereich", "Allowed range"], apply: ["Übernehmen", "Apply"], saving: ["Speichere …", "Saving…"], saved: ["Gespeichert", "Saved"], failed: ["Fehler", "Failed"], manual_action_hint: ["Die manuelle Aktion wird über den separaten Aktionsregler gesteuert.", "Manual action is controlled with the separate action selector."],
      hardware_limits: ["Hardware-SoC-Grenzen", "Hardware SoC limits"], read_only: ["Nur lesbare Telemetrie", "Read-only telemetry"], hardware_explain: ["Diese Werte werden von der Hardware gemeldet. BSFAI stellt dafür keine unterstützte Schreibsteuerung bereit; sie dienen hier nur zur Information.", "These values are reported by the hardware. BSFAI does not expose a supported write control for them, so they are shown for reference only."], control_explain: ["Die Steuerung nutzt die vorhandenen BSFAI-Entitäten und Home-Assistant-Dienste. Das Dashboard schreibt nicht direkt an die Zendure-Hardware.", "Controls use existing BSFAI entities and Home Assistant services. The dashboard does not write directly to Zendure hardware."],
      systems: ["Systeme", "systems"], packs: ["Akku-Packs", "packs"], system: ["Zendure-System", "Zendure system"], zendure_hardware: ["Zendure-Hardware", "Zendure hardware"], dashboard_views: ["Dashboard-Ansichten", "Dashboard views"],
      details: ["Details", "Details"], hide_details: ["Schließen", "Close"], seconds_ago: ["Sek. zuvor", "s ago"],
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
    return `${entity.state}${unit ? ` ${unit}` : ""}`;
  }

  _find(entities, terms) {
    return entities.find((entity) => {
      const search = `${entity.entity_id} ${this._label(entity)}`.toLowerCase();
      return Array.isArray(terms[0])
        ? terms.some((group) => group.every((term) => search.includes(term)))
        : terms.some((term) => search.includes(term));
    });
  }

  _reading(entities, title, terms, hint = "") {
    const entity = this._find(entities, terms);
    return `<article class="reading"><span>${this._escape(title)}</span><strong>${this._escape(this._value(entity))}</strong><small>${this._escape(hint || (entity ? this._label(entity) : this._t("unavailable")))}</small></article>`;
  }

  _flowRow(entities, title, terms, width) {
    const entity = this._find(entities, terms);
    return `<div class="flow-row"><span>${this._escape(title)}</span><div class="flow-track"><i style="width:${width}%"></i></div><strong>${this._escape(this._value(entity))}</strong></div>`;
  }

  _powerCard(title, entityId, hint = "") {
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
    const source = entity ? this._label(entity) : (hint || entityId || this._t("source_unavailable"));
    return `<article class="reading power-reading"><span>${this._escape(title)}</span><strong>${this._escape(value)}</strong><small>${this._escape(source)}</small></article>`;
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
    const flowSpecs = [
      [this._t("pv_battery"), ["economics_daily_pv_to_battery_kwh", "pv to battery", "pv zur batterie"]],
      [this._t("grid_battery"), ["economics_daily_grid_to_battery_kwh", "grid to battery", "netz zur batterie"]],
      [this._t("battery_home"), ["economics_daily_battery_to_home_kwh", "battery to home", "akku → haus", "akku zu haus"]],
      [this._t("battery_grid"), ["economics_daily_battery_to_grid_kwh", "battery to grid", "akku → netz", "akku ins netz"]],
      [this._t("native_pv_home"), ["economics_daily_native_pv_to_home_kwh", "native pv to home", "native pv → haus", "direkt ins haus"]],
      [this._t("grid_export"), ["economics_daily_grid_export_kwh", "grid export", "netzeinspeisung", "netz export"]],
    ];
    const flowValues = flowSpecs.map(([, terms]) => {
      const entity = this._find(entities, terms);
      return entity && Number.isFinite(Number(entity.state)) ? Math.max(0, Number(entity.state)) : 0;
    });
    const largestFlow = Math.max(...flowValues, 0);
    const flowRows = flowSpecs.map(([title, terms], index) =>
      this._flowRow(entities, title, terms, largestFlow ? Math.round(flowValues[index] / largestFlow * 100) : 0)
    ).join("");
    return `
      ${this._livePowerView(entities)}
      <section class="section"><div class="section-head"><h2>${this._escape(this._t("flows_today"))}</h2><small>${this._escape(this._t("daily_energy_note"))}</small></div>
        <div class="flow-grid">
          ${flowRows}
        </div>
      </section>
      <section class="section"><div class="section-head"><h2>${this._escape(this._t("solar_forecast"))}</h2><small>${this._escape(this._t("forecast_compare"))}</small></div>
        <div class="forecast-groups">
          <div class="forecast-group"><h3>${this._escape(this._t("near_term"))}</h3><div class="reading-grid">
            ${this._reading(entities, this._t("usable_3h"), [["forecast_next_3h_kwh"], ["usable pv forecast next 3 hours"], ["nutzbare pv-prognose", "nächste 3 stunden"]])}
            ${this._reading(entities, this._t("usable_6h"), [["forecast_next_6h_kwh"], ["usable pv forecast next 6 hours"], ["nutzbare pv-prognose", "nächste 6 stunden"]])}
          </div></div>
          <div class="forecast-group"><h3>${this._escape(this._t("forecast_today"))}</h3><div class="reading-grid">
            ${this._reading(entities, this._t("usable_today"), [["forecast_remaining_today_kwh"], ["usable pv forecast remaining today"], ["nutzbare pv-prognose", "rest heute"]])}
            ${this._reading(entities, this._t("gross_today"), [["forecast_gross_remaining_today_kwh"], ["gross pv forecast remaining today"], ["pv-prognose brutto", "rest heute"]])}
          </div></div>
          <div class="forecast-group"><h3>${this._escape(this._t("forecast_tomorrow"))}</h3><div class="reading-grid">
            ${this._reading(entities, this._t("usable_tomorrow"), [["forecast_tomorrow_kwh"], ["usable pv forecast tomorrow"], ["nutzbare pv-prognose", "morgen"]])}
            ${this._reading(entities, this._t("gross_tomorrow"), [["forecast_gross_tomorrow_kwh"], ["gross pv forecast tomorrow"], ["pv-prognose brutto", "morgen"]])}
          </div></div>
        </div>
        <p class="explain">${this._escape(this._t("forecast_explain"))}</p>
      </section>`;
  }

  _economicsView(entities) {
    return `
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

  _deviceEntities(entities, deviceName, packNumber) {
    const prefix = String(deviceName || "").toLowerCase();
    if (!prefix) return [];
    const packPattern = /(battery|batterie|akku)[ -]?pack\s*0*([1-9]\d*)/i;
    return entities.filter((entity) => {
      const name = this._label(entity).toLowerCase();
      if (!name.startsWith(prefix)) return false;
      const packMatch = name.match(packPattern);
      return packNumber
        ? Boolean(packMatch && Number(packMatch[2]) === packNumber)
        : !packMatch;
    });
  }

  _detailRows(entities, limit = 5) {
    const preferred = /(soc|ladezustand|power|leistung|temperatur|temperature|status|transport|firmware|kapazität|capacity)/i;
    const ordered = [...entities].sort((a, b) => {
      return Number(preferred.test(this._label(b))) - Number(preferred.test(this._label(a)));
    });
    return ordered.slice(0, limit).map((entity) =>
      `<div class="detail-row"><span>${this._escape(this._label(entity))}</span><strong>${this._escape(this._value(entity))}</strong></div>`
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
      return `<article class="control-card"><label for="control-${this._escape(entity.entity_id)}">${this._escape(this._label(entity))}</label><select id="control-${this._escape(entity.entity_id)}" data-control-select="${this._escape(entity.entity_id)}">${(entity.attributes.options || []).map((option) => `<option value="${this._escape(option)}" ${option === entity.state ? "selected" : ""}>${this._escape(labels[option] || option)}</option>`).join("")}</select><button class="apply" data-apply-select="${this._escape(entity.entity_id)}">${this._escape(this._t("apply"))}</button>${isMode && entity.state === "manual" ? `<small>${this._escape(this._t("manual_action_hint"))}</small>` : ""}</article>`;
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

  _numberControlCard(entity) {
    const value = Number(entity.state);
    const min = Number(entity.attributes.min);
    const max = Number(entity.attributes.max);
    const step = Number(entity.attributes.step);
    if (!Number.isFinite(value) || !Number.isFinite(min) || !Number.isFinite(max)) return "";
    return `<article class="control-card"><label for="control-${this._escape(entity.entity_id)}">${this._escape(this._label(entity))}</label><div class="number-control"><input id="control-${this._escape(entity.entity_id)}" type="number" data-control-number="${this._escape(entity.entity_id)}" value="${value}" min="${min}" max="${max}" step="${Number.isFinite(step) && step > 0 ? step : 1}"><span>${this._escape(entity.attributes.unit_of_measurement || "")}</span></div><small>${this._escape(this._t("allowed_range"))}: ${min}–${max}${entity.attributes.unit_of_measurement ? ` ${this._escape(entity.attributes.unit_of_measurement)}` : ""}</small><button class="apply" data-apply-number="${this._escape(entity.entity_id)}">${this._escape(this._t("apply"))}</button></article>`;
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

  _metricCard(title, entityId) {
    const entity = entityId && this._hass && this._hass.states[entityId];
    return `<article class="metric"><span>${this._escape(title)}</span><strong>${this._escape(this._value(entity))}</strong><small>${this._escape(entity ? this._label(entity) : this._t("waiting_entity"))}</small></article>`;
  }

  _overviewMetrics(entities) {
    const sources = (this._panel && this._panel.config && this._panel.config.power_sources) || [];
    const groups = sources.map((source) => {
      const cards = [];
      if (source.soc) cards.push(this._metricCard(this._t("battery"), source.soc));
      if (source.pv) cards.push(this._metricCard(this._t("pv_power"), source.pv));
      if (source.native_pv) cards.push(this._metricCard(this._t("native_pv_source"), source.native_pv));
      if (source.battery_power) cards.push(this._metricCard(this._t("battery_power"), source.battery_power));
      if (source.grid_power) cards.push(this._metricCard(this._t("grid_power"), source.grid_power));
      else {
        if (source.grid_import) cards.push(this._metricCard(this._t("grid_import"), source.grid_import));
        if (source.grid_export) cards.push(this._metricCard(this._t("grid_export"), source.grid_export));
      }
      if (source.offgrid_power) cards.push(this._metricCard(this._t("offgrid_source"), source.offgrid_power));
      if (!cards.length) return "";
      return `<section class="metric-group"><h3>${this._escape(source.name || this._t("system"))}</h3><div class="metric-grid">${cards.join("")}</div></section>`;
    }).filter(Boolean);

    const price = this._find(entities, ["current electricity price", "strompreis aktuell", "preis jetzt"]);
    if (price) groups.push(`<section class="metric-group"><h3>${this._escape(this._t("shared_metrics"))}</h3><div class="metric-grid">${this._metricCard(this._t("current_price"), price.entity_id)}</div></section>`);
    if (groups.length) return groups.join("");

    const metrics = [
      [this._t("battery"), ["ladezustand", "soc", "battery level"]],
      [this._t("pv_power"), ["pv power", "pv-leistung", "solar power", "solarleis"]],
      [this._t("battery_power"), ["batterieleistung", "battery power", "charge power"]],
      [this._t("grid_power"), ["netz-leistung", "grid power", "netzbezug"]],
      [this._t("current_price"), ["current electricity price", "strompreis aktuell", "preis jetzt"]],
    ];
    return metrics.map(([title, terms]) => {
      const entity = this._find(entities, terms);
      return this._metricCard(title, entity && entity.entity_id);
    }).join("");
  }

  _render() {
    if (!this.shadowRoot || !this._hass) return;
    const entities = this._entities();
    const cards = this._overviewMetrics(entities);

    const systems = this._nativeSystems(entities);
    const packCount = systems.reduce((count, system) => count + (system.packs || []).length, 0);
    const lastUpdated = entities.reduce((latest, entity) => {
      const stamp = Date.parse(entity.last_updated || "");
      return Number.isFinite(stamp) && stamp > latest ? stamp : latest;
    }, 0);
    const updated = lastUpdated ? new Date(lastUpdated).toLocaleTimeString() : this._t("no_data");
    const activeContent = this._view === "energy"
      ? this._energyView(entities)
      : this._view === "economics"
        ? this._economicsView(entities)
        : this._view === "controls"
          ? this._controls(entities)
        : `<section class="section"><div class="section-head"><h2>${this._escape(this._t("topology"))}</h2><small>${systems.length} ${this._escape(this._t("systems"))} · ${packCount} ${this._escape(this._t("packs"))}</small></div>
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
              const packRows = this._detailRows(packEntities);
              return `<article class="pack-card"><div class="pack-head"><div><strong>↳ ${this._escape(this._t("battery_pack"))} ${packNumber}</strong><small>${this._escape(pack.model || this._t("zendure_pack"))}</small></div><button class="details-toggle" type="button" data-details-toggle="${detailId}" aria-controls="${detailId}" aria-expanded="false">${this._escape(this._t("details"))}</button></div><aside class="hover-details" id="${detailId}"><h3>${this._escape(this._t("battery_pack"))} ${packNumber}</h3>${packRows || `<div class="detail-row"><span>${this._escape(this._t("telemetry"))}</span><strong>${this._escape(this._t("unavailable"))}</strong></div>`}</aside></article>`;
            }).join("");
            const systemDetailId = `system-details-${systemIndex}`;
            return `<article class="system-card"><div class="system-head"><div><strong>${this._escape(system.name || this._t("system"))}</strong><small>${this._escape(system.model || system.profile || this._t("zendure_hardware"))}</small></div><div class="system-actions"><span class="status ${system.online ? "" : "offline"}">${this._escape(this._t(system.online ? "online" : "offline"))}</span><button class="details-toggle" type="button" data-details-toggle="${systemDetailId}" aria-controls="${systemDetailId}" aria-expanded="false">${this._escape(this._t("details"))}</button></div></div><div class="device-meta">${this._escape(system.transport || this._t("unknown_path"))} · ${this._escape(system.status || this._t("unknown_status"))}</div><div class="packs">${packCards || `<div class="device-meta">${this._escape(this._t("no_packs"))}</div>`}</div><aside class="hover-details" id="${systemDetailId}"><h3>${this._escape(system.name || this._t("system"))}</h3>${systemDetails}${this._detailRows(systemEntities)}</aside></article>`;
          }).join("")}</div>` : `<div class="empty">${this._escape(this._t("native_empty"))}</div>`}
        </section><section class="section"><div class="section-head"><h2>${this._escape(this._t("system_signals"))}</h2><small>${entities.length} ${this._escape(this._t("matching_entities"))}</small></div><div class="inventory">${entities.slice(0, 40).map((entity) => `<div class="entity"><span>${this._escape(this._label(entity))}</span><strong>${this._escape(this._value(entity))}</strong></div>`).join("") || `<div class="empty">${this._escape(this._t("waiting_entities"))}</div>`}</div></section>`;

    this.shadowRoot.innerHTML = `
      <style>
        :host{display:block;min-height:100%;background:#101214;color:#e7e9eb;font-family:Inter,"Segoe UI",sans-serif;--line:#34383d;--muted:#a4a9af;--cyan:#16c4df;--green:#56cf83;--amber:#f0c34e}
        *{box-sizing:border-box}.shell{max-width:1500px;margin:auto;padding:28px clamp(18px,3vw,42px) 56px}
        header{display:flex;align-items:center;justify-content:space-between;gap:20px;margin-bottom:24px}h1{font-size:clamp(24px,3vw,36px);margin:0;font-weight:650;letter-spacing:-.03em}.sub{color:var(--muted);margin:8px 0 0}.badge{border:1px solid #365245;color:#a8e5ba;background:#1e3026;border-radius:999px;padding:9px 14px;font-size:13px;white-space:nowrap}
        .section{background:#1b1e21;border:1px solid var(--line);border-radius:14px;padding:20px;margin-top:18px}.section-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:16px}.section h2{font-size:17px;margin:0}.section-head small,.muted{color:var(--muted)}
        nav{display:flex;gap:8px;margin:8px 0 18px;border-bottom:1px solid var(--line);padding-bottom:12px}.tab{border:1px solid #41464b;background:#25292d;color:#c4c8cc;border-radius:8px;padding:9px 15px;font:inherit;cursor:pointer}.tab.active{border-color:#2388ad;background:#183847;color:#e5f8fc}.metrics{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px}.metric{min-height:125px;padding:18px;border:1px solid #41464b;border-top:3px solid var(--cyan);border-radius:11px;background:#292d31;display:flex;flex-direction:column;gap:11px}.metric:nth-child(2){border-top-color:var(--green)}.metric:nth-child(3){border-top-color:var(--amber)}.metric span{font-size:11px;letter-spacing:.11em;color:#b1b5b9}.metric strong{font-size:clamp(21px,2vw,30px);font-variant-numeric:tabular-nums}.metric small{color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
        .reading-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px}.reading{min-height:105px;padding:15px;border:1px solid #41464b;border-radius:10px;background:#272b2f;display:flex;flex-direction:column;gap:8px}.reading span{color:#bdc2c6;font-size:12px}.reading strong{font-size:22px;font-variant-numeric:tabular-nums}.reading small{color:var(--muted);line-height:1.35}.forecast-groups{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px}.forecast-group{padding:12px;border:1px solid #343a40;border-radius:11px;background:#202428}.forecast-group h3{font-size:13px;color:#c7cbd0;margin:0 0 10px}.forecast-group .reading{min-height:92px;padding:12px}.forecast-group .reading-grid{grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}.flow-grid{display:grid;gap:8px}.flow-row{display:grid;grid-template-columns:minmax(130px,1fr) 3fr minmax(85px,.7fr);gap:14px;align-items:center;padding:9px 0;border-bottom:1px solid var(--line)}.flow-row span{color:#c3c7ca}.flow-row strong{text-align:right;font-variant-numeric:tabular-nums}.flow-track{height:9px;background:#30353a;border-radius:999px;overflow:hidden}.flow-track i{display:block;width:48%;height:100%;background:linear-gradient(90deg,#1bb7df,#54d08a);border-radius:999px}.explain{color:var(--muted);font-size:12px;line-height:1.5;margin:14px 0 0}.subsection{margin-top:18px}.subsection h3{font-size:14px;color:#c7cbd0;margin:0 0 10px}.control-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:11px}.control-card{padding:14px;border:1px solid #41464b;border-radius:10px;background:#272b2f;display:flex;flex-direction:column;gap:10px}.control-card label{font-size:13px;color:#d1d5d8}.control-card select,.control-card input{width:100%;background:#171a1d;color:#eef0f1;border:1px solid #4b535a;border-radius:7px;padding:10px;font:inherit}.number-control{display:flex;align-items:center;gap:8px}.number-control span{color:var(--muted);min-width:30px}.control-card small{color:var(--muted);font-size:11px}.apply{align-self:flex-end;border:1px solid #247b9b;background:#153746;color:#dff8ff;border-radius:7px;padding:7px 12px;font:inherit;cursor:pointer}.apply:disabled{opacity:.65;cursor:wait}
        .metric-groups{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr));gap:12px}.metric-group{padding:13px;border:1px solid #343a40;border-radius:11px;background:#202428}.metric-group h3{font-size:13px;color:#c7cbd0;margin:0 0 10px}.metric-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,150px),1fr));gap:10px}.metric-grid .metric{min-height:108px;padding:15px}.metric-grid .metric:nth-child(2){border-top-color:var(--green)}.metric-grid .metric:nth-child(3){border-top-color:var(--amber)}
        .systems{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:14px}.system-card{position:relative;padding:17px;background:#172b3a;border:1px solid #2476a8;border-left:4px solid var(--cyan);border-radius:11px}.system-head,.pack-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}.system-head strong,.pack-head strong{font-size:16px}.system-head small,.pack-head small,.device-meta{display:block;color:#b7c4ce;margin-top:6px}.system-actions{display:flex;align-items:center;gap:8px}.status{border:1px solid #40604c;background:#20352a;color:#a8e5ba;border-radius:999px;padding:5px 9px;font-size:11px;white-space:nowrap}.status.offline{border-color:#744849;background:#3a2526;color:#f2aaaa}.packs{margin:15px 0 0 14px;padding-left:16px;border-left:1px solid #388ebc;display:grid;gap:9px}.pack-card{position:relative;padding:12px;background:#202b35;border:1px solid #475563;border-radius:9px}.pack-card strong{display:block}.pack-card small{display:block;color:#aeb8c1;margin-top:5px}.details-toggle{border:1px solid #3f6578;background:#1a3442;color:#d9f5fb;border-radius:7px;padding:6px 9px;font:inherit;font-size:12px;cursor:pointer;white-space:nowrap}.details-toggle:hover,.details-toggle:focus-visible{border-color:var(--cyan);outline:none}.hover-details{display:none;position:absolute;z-index:5;left:12px;top:calc(100% + 9px);width:min(380px,calc(100vw - 56px));padding:14px;background:#f7f8fa;color:#20242a;border:1px solid #d7dce2;border-radius:10px;box-shadow:0 12px 35px #0008}.system-card.details-open>.hover-details,.pack-card.details-open>.hover-details{display:block}@media(hover:hover){.system-card:hover:not(:has(.pack-card:hover))>.hover-details,.pack-card:hover>.hover-details{display:block}}.hover-details h3{margin:0 0 9px;font-size:14px}.detail-row{display:flex;justify-content:space-between;gap:12px;padding:6px 0;border-bottom:1px solid #e5e7eb;font-size:12px}.detail-row span{color:#59616a}.detail-row strong{text-align:right}.empty{color:var(--muted);padding:18px;border:1px dashed #485058;border-radius:10px}.inventory{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:8px}.entity{display:flex;justify-content:space-between;gap:12px;padding:11px 12px;border-bottom:1px solid #34383d}.entity span{color:#c2c6ca}.entity strong{font-weight:550;text-align:right;font-variant-numeric:tabular-nums}.footer{color:#858c92;font-size:12px;margin:16px 2px}
        @media(max-width:900px){.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.topology{grid-template-columns:1fr}.link{height:20px;width:1px;margin:auto}}@media(max-width:520px){header{align-items:flex-start;flex-direction:column}.metrics{grid-template-columns:1fr 1fr}.systems{grid-template-columns:1fr}.metric{padding:13px}.section{padding:15px}}
      </style>
      <main class="shell">
        <header><div><h1>Battery SmartFlow AI</h1><p class="sub">${this._escape(this._t("subtitle"))}</p></div><div class="badge">● ${this._escape(this._t("live"))} ${this._escape(updated)}</div></header>
        <section class="section"><div class="section-head"><h2>${this._escape(this._t("energy_overview"))}</h2><small>${this._escape(this._t("live_values"))}</small></div><div class="metric-groups">${cards}</div></section>
        <nav aria-label="${this._escape(this._t("dashboard_views"))}"><button class="tab ${this._view === "overview" ? "active" : ""}" data-view="overview">${this._escape(this._t("overview"))}</button><button class="tab ${this._view === "energy" ? "active" : ""}" data-view="energy">${this._escape(this._t("energy"))}</button><button class="tab ${this._view === "economics" ? "active" : ""}" data-view="economics">${this._escape(this._t("economics"))}</button><button class="tab ${this._view === "controls" ? "active" : ""}" data-view="controls">${this._escape(this._t("controls"))}</button></nav>
        ${activeContent}
        <p class="footer">${this._escape(this._t("footer"))}</p>
      </main>`;
    this.shadowRoot.querySelectorAll("[data-view]").forEach((button) => {
      button.addEventListener("click", () => {
        this._view = button.dataset.view;
        this._render();
      });
    });
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
