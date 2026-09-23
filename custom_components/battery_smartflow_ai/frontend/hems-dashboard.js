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
      return terms.some((term) => search.includes(term));
    });
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

    const hardware = entities.filter((entity) => {
      const text = `${entity.entity_id} ${this._label(entity)}`.toLowerCase();
      return /battery|batterie|pack|solarflow|zendure|hardware|gerät|device/.test(text);
    });
    const packs = hardware.filter((entity) => /pack|akku|battery-pack|batteriepack/.test(`${entity.entity_id} ${this._label(entity)}`.toLowerCase()));
    const systems = hardware.filter((entity) => !packs.includes(entity));
    const lastUpdated = entities.reduce((latest, entity) => {
      const stamp = Date.parse(entity.last_updated || "");
      return Number.isFinite(stamp) && stamp > latest ? stamp : latest;
    }, 0);
    const updated = lastUpdated ? new Date(lastUpdated).toLocaleTimeString() : "No data yet";

    this.shadowRoot.innerHTML = `
      <style>
        :host{display:block;min-height:100%;background:#101214;color:#e7e9eb;font-family:Inter,"Segoe UI",sans-serif;--line:#34383d;--muted:#a4a9af;--cyan:#16c4df;--green:#56cf83;--amber:#f0c34e}
        *{box-sizing:border-box}.shell{max-width:1500px;margin:auto;padding:28px clamp(18px,3vw,42px) 56px}
        header{display:flex;align-items:center;justify-content:space-between;gap:20px;margin-bottom:24px}h1{font-size:clamp(24px,3vw,36px);margin:0;font-weight:650;letter-spacing:-.03em}.sub{color:var(--muted);margin:8px 0 0}.badge{border:1px solid #365245;color:#a8e5ba;background:#1e3026;border-radius:999px;padding:9px 14px;font-size:13px;white-space:nowrap}
        .section{background:#1b1e21;border:1px solid var(--line);border-radius:14px;padding:20px;margin-top:18px}.section-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:16px}.section h2{font-size:17px;margin:0}.section-head small,.muted{color:var(--muted)}
        .metrics{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px}.metric{min-height:125px;padding:18px;border:1px solid #41464b;border-top:3px solid var(--cyan);border-radius:11px;background:#292d31;display:flex;flex-direction:column;gap:11px}.metric:nth-child(2){border-top-color:var(--green)}.metric:nth-child(3){border-top-color:var(--amber)}.metric span{font-size:11px;letter-spacing:.11em;color:#b1b5b9}.metric strong{font-size:clamp(21px,2vw,30px);font-variant-numeric:tabular-nums}.metric small{color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
        .topology{display:grid;grid-template-columns:minmax(220px,1fr) 32px minmax(220px,2fr);align-items:center;gap:10px}.hub,.node{border-radius:11px;padding:16px;background:#173b57;border:1px solid #267bb4}.hub{border-left:4px solid var(--cyan)}.hub strong,.node strong{display:block}.hub small,.node small{display:block;color:#c0ccd6;margin-top:6px}.link{height:1px;background:#38a6dc}.nodes{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px}.node{background:#202f4a;border-color:#3271bc}.pack .node{background:#242a30;border-color:#57616b}.empty{color:var(--muted);padding:18px;border:1px dashed #485058;border-radius:10px}.inventory{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:8px}.entity{display:flex;justify-content:space-between;gap:12px;padding:11px 12px;border-bottom:1px solid #34383d}.entity span{color:#c2c6ca}.entity strong{font-weight:550;text-align:right;font-variant-numeric:tabular-nums}.footer{color:#858c92;font-size:12px;margin:16px 2px}
        @media(max-width:900px){.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.topology{grid-template-columns:1fr}.link{height:20px;width:1px;margin:auto}}@media(max-width:520px){header{align-items:flex-start;flex-direction:column}.metrics{grid-template-columns:1fr 1fr}.metric{padding:13px}.section{padding:15px}}
      </style>
      <main class="shell">
        <header><div><h1>Battery SmartFlow AI</h1><p class="sub">Energy flow, storage and system status</p></div><div class="badge">● LIVE · updated ${this._escape(updated)}</div></header>
        <section class="section"><div class="section-head"><h2>Energy overview</h2><small>Live Home Assistant values</small></div><div class="metrics">${cards}</div></section>
        <section class="section"><div class="section-head"><h2>Hardware topology</h2><small>${systems.length} systems · ${packs.length} packs detected</small></div>
          ${systems.length ? `<div class="topology"><div class="hub"><strong>SmartFlow HEMS</strong><small>Battery systems and connected storage</small></div><div class="link"></div><div class="nodes">${systems.slice(0, 8).map((entity) => `<div class="node"><strong>${this._escape(this._label(entity))}</strong><small>${this._escape(this._value(entity))}</small></div>`).join("")}${packs.slice(0, 12).map((entity) => `<div class="node pack"><strong>↳ ${this._escape(this._label(entity))}</strong><small>${this._escape(this._value(entity))}</small></div>`).join("")}</div></div>` : `<div class="empty">Hardware entities will appear here as soon as Home Assistant exposes them.</div>`}
        </section>
        <section class="section"><div class="section-head"><h2>System signals</h2><small>${entities.length} matching entities</small></div><div class="inventory">${entities.slice(0, 40).map((entity) => `<div class="entity"><span>${this._escape(this._label(entity))}</span><strong>${this._escape(this._value(entity))}</strong></div>`).join("") || `<div class="empty">Waiting for Battery SmartFlow AI entities.</div>`}</div></section>
        <p class="footer">The first dashboard preview is read-only. Existing BSFAI and Home Assistant controls remain unchanged.</p>
      </main>`;
  }

  _escape(value) {
    return String(value).replace(/[&<>"']/g, (char) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[char]);
  }
}

customElements.define("battery-smartflow-ai-hems-dashboard", BatterySmartFlowDashboard);
