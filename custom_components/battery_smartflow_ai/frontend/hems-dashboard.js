/* Battery SmartFlow AI's standalone, read-only HEMS overview panel. */
class BatterySmartFlowDashboard extends HTMLElement {
  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  set narrow(narrow) {
    this._narrow = narrow;
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
    return `<article class="reading"><span>${this._escape(title)}</span><strong>${this._escape(this._value(entity))}</strong><small>${this._escape(hint || (entity ? this._label(entity) : "No matching sensor available"))}</small></article>`;
  }

  _flowRow(entities, title, terms, width) {
    const entity = this._find(entities, terms);
    return `<div class="flow-row"><span>${this._escape(title)}</span><div class="flow-track"><i style="width:${width}%"></i></div><strong>${this._escape(this._value(entity))}</strong></div>`;
  }

  _energyView(entities) {
    const flowSpecs = [
      ["PV → battery", ["economics_daily_pv_to_battery_kwh", "pv to battery", "pv zur batterie"]],
      ["Grid → battery", ["economics_daily_grid_to_battery_kwh", "grid to battery", "netz zur batterie"]],
      ["Battery → home", ["economics_daily_battery_to_home_kwh", "battery to home", "akku → haus", "akku zu haus"]],
      ["Battery → grid", ["economics_daily_battery_to_grid_kwh", "battery to grid", "akku → netz", "akku ins netz"]],
      ["Native PV → home", ["economics_daily_native_pv_to_home_kwh", "native pv to home", "native pv → haus", "direkt ins haus"]],
      ["Grid export", ["economics_daily_grid_export_kwh", "grid export", "netzeinspeisung", "netz export"]],
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
      <section class="section"><div class="section-head"><h2>Today's energy flows</h2><small>Measured BSFAI energy ledger</small></div>
        <div class="flow-grid">
          ${flowRows}
        </div>
      </section>
      <section class="section"><div class="section-head"><h2>Solar forecast</h2><small>Gross forecast versus usable remainder</small></div>
        <div class="reading-grid">
          ${this._reading(entities, "Usable · next 3 hours", [["forecast_next_3h_kwh"], ["usable pv forecast next 3 hours"], ["nutzbare pv-prognose", "nächste 3 stunden"]])}
          ${this._reading(entities, "Usable · next 6 hours", [["forecast_next_6h_kwh"], ["usable pv forecast next 6 hours"], ["nutzbare pv-prognose", "nächste 6 stunden"]])}
          ${this._reading(entities, "Usable · rest of today", [["forecast_remaining_today_kwh"], ["usable pv forecast remaining today"], ["nutzbare pv-prognose", "rest heute"]])}
          ${this._reading(entities, "Gross · rest of today", [["forecast_gross_remaining_today_kwh"], ["gross pv forecast remaining today"], ["pv-prognose brutto", "rest heute"]])}
          ${this._reading(entities, "Usable · tomorrow", [["forecast_tomorrow_kwh"], ["usable pv forecast tomorrow"], ["nutzbare pv-prognose", "morgen"]])}
          ${this._reading(entities, "Gross · tomorrow", [["forecast_gross_tomorrow_kwh"], ["gross pv forecast tomorrow"], ["pv-prognose brutto", "morgen"]])}
        </div>
        <p class="explain">Usable forecast is the portion expected to remain available after BSFAI's planning assumptions. Gross values show the imported forecast before that reduction.</p>
      </section>`;
  }

  _economicsView(entities) {
    return `
      <section class="section"><div class="section-head"><h2>Today's economics</h2><small>Daily value and costs</small></div>
        <div class="reading-grid">
          ${this._reading(entities, "Battery benefit", ["economics_daily_battery_benefit", "battery benefit today", "bilanz heute batterie-nutzen"])}
          ${this._reading(entities, "Avoided grid import", ["economics_daily_avoided_grid_import_cost", "avoided grid import cost", "vermiedene netzbezugskosten"])}
          ${this._reading(entities, "Grid charging cost", ["economics_daily_grid_charge_cost", "grid charging cost", "netzlade-kosten"])}
          ${this._reading(entities, "PV opportunity cost", ["economics_daily_pv_opportunity_cost", "pv opportunity cost", "pv-opportunitätskosten"])}
          ${this._reading(entities, "Export revenue", ["economics_daily_export_revenue", "export revenue", "einspeiseerlös"])}
          ${this._reading(entities, "Native PV self-consumption value", ["economics_daily_native_pv_self_consumption_value", "native pv self-consumption value", "wert native pv eigenverbrauch"])}
        </div>
      </section>
      <section class="section"><div class="section-head"><h2>Average realized values</h2><small>Based on BSFAI's energy and cost ledger</small></div>
        <div class="reading-grid">
          ${this._reading(entities, "Grid charging price", ["economics_average_grid_charge_price", "avg. grid charging price", "ø netzladepreis"])}
          ${this._reading(entities, "PV opportunity value", ["economics_average_pv_opportunity_value", "avg. pv opportunity value", "ø pv-opportunitätswert"])}
          ${this._reading(entities, "Export price", ["economics_average_export_price", "avg. export price", "ø einspeisepreis"])}
          ${this._reading(entities, "Battery discharge value", ["economics_average_battery_discharge_value", "avg. battery discharge value", "ø wert der batterieentladung"])}
          ${this._reading(entities, "Native PV to home return", ["economics_average_native_pv_to_home_return", "avg. pv to home return", "ø wert native pv direkt ins haus"])}
          ${this._reading(entities, "Economic efficiency", ["economics_total_economic_efficiency_pct", "economic efficiency", "wirtschaftlichkeit"])}
        </div>
        <p class="explain">Grid charging, PV opportunity, and export values are kept separate here. The blended battery acquisition price will be added when its dedicated sensor is implemented.</p>
      </section>`;
  }

  _nativeSystems(entities) {
    const overview = entities.find((entity) => Array.isArray(entity.attributes.systems));
    return overview ? overview.attributes.systems : [];
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

  _render() {
    if (!this.shadowRoot || !this._hass) return;
    const entities = this._entities();
    const metrics = [
      ["BATTERY", ["ladezustand", "soc", "battery level"]],
      ["PV POWER", ["pv power", "pv-leistung", "solar power", "solarleis"]],
      ["BATTERY POWER", ["batterieleistung", "battery power", "charge power"]],
      ["GRID POWER", ["netz-leistung", "grid power", "netzbezug"]],
      ["CURRENT PRICE", ["current electricity price", "strompreis aktuell", "preis jetzt"]],
    ];
    const cards = metrics.map(([title, terms]) => {
      const entity = this._find(entities, terms);
      return `<article class="metric"><span>${title}</span><strong>${this._escape(this._value(entity))}</strong><small>${this._escape(entity ? this._label(entity) : "Waiting for matching entity")}</small></article>`;
    }).join("");

    const systems = this._nativeSystems(entities);
    const packCount = systems.reduce((count, system) => count + (system.packs || []).length, 0);
    const lastUpdated = entities.reduce((latest, entity) => {
      const stamp = Date.parse(entity.last_updated || "");
      return Number.isFinite(stamp) && stamp > latest ? stamp : latest;
    }, 0);
    const updated = lastUpdated ? new Date(lastUpdated).toLocaleTimeString() : "No data yet";
    const activeContent = this._view === "energy"
      ? this._energyView(entities)
      : this._view === "economics"
        ? this._economicsView(entities)
        : `<section class="section"><div class="section-head"><h2>Hardware topology</h2><small>${systems.length} systems · ${packCount} packs</small></div>
          ${systems.length ? `<div class="systems">${systems.map((system) => {
            const systemEntities = this._deviceEntities(entities, system.name, null);
            const systemDetails = [
              ["Model", system.model], ["Profile", system.profile],
              ["Communication", system.transport], ["Status", system.status],
              ["Last data", system.data_age_seconds == null ? "—" : `${system.data_age_seconds}s ago`],
            ].map(([label, value]) => `<div class="detail-row"><span>${label}</span><strong>${this._escape(value || "—")}</strong></div>`).join("");
            const packCards = (system.packs || []).map((pack, index) => {
              const packNumber = index + 1;
              const packEntities = this._deviceEntities(entities, system.name, packNumber);
              const packRows = this._detailRows(packEntities);
              return `<article class="pack-card" tabindex="0"><strong>↳ Battery Pack ${packNumber}</strong><small>${this._escape(pack.model || "Zendure battery pack")}</small><aside class="hover-details"><h3>Battery Pack ${packNumber}</h3>${packRows || `<div class="detail-row"><span>Telemetry</span><strong>Not available</strong></div>`}</aside></article>`;
            }).join("");
            return `<article class="system-card" tabindex="0"><div class="system-head"><div><strong>${this._escape(system.name || "Zendure system")}</strong><small>${this._escape(system.model || system.profile || "Zendure hardware")}</small></div><span class="status ${system.online ? "" : "offline"}">${system.online ? "ONLINE" : "OFFLINE"}</span></div><div class="device-meta">${this._escape(system.transport || "Communication path unknown")} · ${this._escape(system.status || "Status unknown")}</div><div class="packs">${packCards || `<div class="device-meta">No battery packs detected</div>`}</div><aside class="hover-details"><h3>${this._escape(system.name || "Zendure system")}</h3>${systemDetails}${this._detailRows(systemEntities)}</aside></article>`;
          }).join("")}</div>` : `<div class="empty">The native hardware inventory is not available yet. Once the Zendure device inventory has been discovered, systems and attached battery packs will be shown here.</div>`}
        </section><section class="section"><div class="section-head"><h2>System signals</h2><small>${entities.length} matching entities</small></div><div class="inventory">${entities.slice(0, 40).map((entity) => `<div class="entity"><span>${this._escape(this._label(entity))}</span><strong>${this._escape(this._value(entity))}</strong></div>`).join("") || `<div class="empty">Waiting for Battery SmartFlow AI entities.</div>`}</div></section>`;

    this.shadowRoot.innerHTML = `
      <style>
        :host{display:block;min-height:100%;background:#101214;color:#e7e9eb;font-family:Inter,"Segoe UI",sans-serif;--line:#34383d;--muted:#a4a9af;--cyan:#16c4df;--green:#56cf83;--amber:#f0c34e}
        *{box-sizing:border-box}.shell{max-width:1500px;margin:auto;padding:28px clamp(18px,3vw,42px) 56px}
        header{display:flex;align-items:center;justify-content:space-between;gap:20px;margin-bottom:24px}h1{font-size:clamp(24px,3vw,36px);margin:0;font-weight:650;letter-spacing:-.03em}.sub{color:var(--muted);margin:8px 0 0}.badge{border:1px solid #365245;color:#a8e5ba;background:#1e3026;border-radius:999px;padding:9px 14px;font-size:13px;white-space:nowrap}
        .section{background:#1b1e21;border:1px solid var(--line);border-radius:14px;padding:20px;margin-top:18px}.section-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:16px}.section h2{font-size:17px;margin:0}.section-head small,.muted{color:var(--muted)}
        nav{display:flex;gap:8px;margin:8px 0 18px;border-bottom:1px solid var(--line);padding-bottom:12px}.tab{border:1px solid #41464b;background:#25292d;color:#c4c8cc;border-radius:8px;padding:9px 15px;font:inherit;cursor:pointer}.tab.active{border-color:#2388ad;background:#183847;color:#e5f8fc}.metrics{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px}.metric{min-height:125px;padding:18px;border:1px solid #41464b;border-top:3px solid var(--cyan);border-radius:11px;background:#292d31;display:flex;flex-direction:column;gap:11px}.metric:nth-child(2){border-top-color:var(--green)}.metric:nth-child(3){border-top-color:var(--amber)}.metric span{font-size:11px;letter-spacing:.11em;color:#b1b5b9}.metric strong{font-size:clamp(21px,2vw,30px);font-variant-numeric:tabular-nums}.metric small{color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
        .reading-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px}.reading{min-height:105px;padding:15px;border:1px solid #41464b;border-radius:10px;background:#272b2f;display:flex;flex-direction:column;gap:8px}.reading span{color:#bdc2c6;font-size:12px}.reading strong{font-size:22px;font-variant-numeric:tabular-nums}.reading small{color:var(--muted);line-height:1.35}.flow-grid{display:grid;gap:8px}.flow-row{display:grid;grid-template-columns:minmax(130px,1fr) 3fr minmax(85px,.7fr);gap:14px;align-items:center;padding:9px 0;border-bottom:1px solid var(--line)}.flow-row span{color:#c3c7ca}.flow-row strong{text-align:right;font-variant-numeric:tabular-nums}.flow-track{height:9px;background:#30353a;border-radius:999px;overflow:hidden}.flow-track i{display:block;width:48%;height:100%;background:linear-gradient(90deg,#1bb7df,#54d08a);border-radius:999px}.explain{color:var(--muted);font-size:12px;line-height:1.5;margin:14px 0 0}
        .systems{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:14px}.system-card{position:relative;padding:17px;background:#172b3a;border:1px solid #2476a8;border-left:4px solid var(--cyan);border-radius:11px}.system-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}.system-head strong{font-size:16px}.system-head small,.device-meta{display:block;color:#b7c4ce;margin-top:6px}.status{border:1px solid #40604c;background:#20352a;color:#a8e5ba;border-radius:999px;padding:5px 9px;font-size:11px;white-space:nowrap}.status.offline{border-color:#744849;background:#3a2526;color:#f2aaaa}.packs{margin:15px 0 0 14px;padding-left:16px;border-left:1px solid #388ebc;display:grid;gap:9px}.pack-card{position:relative;padding:12px;background:#202b35;border:1px solid #475563;border-radius:9px}.pack-card strong{display:block}.pack-card small{display:block;color:#aeb8c1;margin-top:5px}.hover-details{display:none;position:absolute;z-index:5;left:calc(100% + 12px);top:0;width:min(330px,70vw);padding:14px;background:#f7f8fa;color:#20242a;border:1px solid #d7dce2;border-radius:10px;box-shadow:0 12px 35px #0008}.system-card:hover>.hover-details,.system-card:focus-within>.hover-details,.pack-card:hover>.hover-details,.pack-card:focus-within>.hover-details{display:block}.hover-details h3{margin:0 0 9px;font-size:14px}.detail-row{display:flex;justify-content:space-between;gap:12px;padding:6px 0;border-bottom:1px solid #e5e7eb;font-size:12px}.detail-row span{color:#59616a}.detail-row strong{text-align:right}.empty{color:var(--muted);padding:18px;border:1px dashed #485058;border-radius:10px}.inventory{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:8px}.entity{display:flex;justify-content:space-between;gap:12px;padding:11px 12px;border-bottom:1px solid #34383d}.entity span{color:#c2c6ca}.entity strong{font-weight:550;text-align:right;font-variant-numeric:tabular-nums}.footer{color:#858c92;font-size:12px;margin:16px 2px}
        @media(max-width:900px){.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.topology{grid-template-columns:1fr}.link{height:20px;width:1px;margin:auto}}@media(max-width:520px){header{align-items:flex-start;flex-direction:column}.metrics{grid-template-columns:1fr 1fr}.metric{padding:13px}.section{padding:15px}}
      </style>
      <main class="shell">
        <header><div><h1>Battery SmartFlow AI</h1><p class="sub">Energy flow, storage and system status</p></div><div class="badge">● LIVE · updated ${this._escape(updated)}</div></header>
        <section class="section"><div class="section-head"><h2>Energy overview</h2><small>Live Home Assistant values</small></div><div class="metrics">${cards}</div></section>
        <nav aria-label="Dashboard views"><button class="tab ${this._view === "overview" ? "active" : ""}" data-view="overview">Overview</button><button class="tab ${this._view === "energy" ? "active" : ""}" data-view="energy">Energy & forecast</button><button class="tab ${this._view === "economics" ? "active" : ""}" data-view="economics">Economics</button></nav>
        ${activeContent}
        <p class="footer">The first dashboard preview is read-only. Existing BSFAI and Home Assistant controls remain unchanged.</p>
      </main>`;
    this.shadowRoot.querySelectorAll("[data-view]").forEach((button) => {
      button.addEventListener("click", () => {
        this._view = button.dataset.view;
        this._render();
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
