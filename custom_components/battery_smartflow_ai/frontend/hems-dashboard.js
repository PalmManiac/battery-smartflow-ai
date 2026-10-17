/* Battery SmartFlow AI's standalone HEMS dashboard. */
const METRIC_ICONS = Object.freeze({
  soc: '<path d="M16 4h-1V2H9v2H8a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2zm0 16H8V6h8v14z"/><path d="M10 8h4v2h-4zm0 4h4v2h-4zm0 4h4v2h-4z"/>',
  pv: '<g fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.7"><circle cx="12" cy="12" r="3.5"/><path d="M12 2v2m0 16v2M4.93 4.93l1.42 1.42m11.3 11.3 1.42 1.42M2 12h2m16 0h2M4.93 19.07l1.42-1.42m11.3-11.3 1.42-1.42"/></g>',
  "native-pv": '<g fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.7"><path d="m5 5-2 14h18L19 5H5zM4 15h16M8 5l-1 14m5-14v14m5-14 1 14"/><path d="M12 2v1.5m-2-1.5h4"/></g>',
  "battery-power": '<g fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.7"><path d="M16 5h-1V3H9v2H8a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2z"/><path fill="currentColor" stroke="none" d="m13 7-4 6h3l-1 5 4-7h-3z"/></g>',
  "grid-power": '<g fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.7"><path d="m12 2-8 20m8-20 8 20M7 15h10M8.5 11h7M10 7h4M6 18h12M12 2v4"/></g>',
  "grid-import": '<g fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.7"><path d="m12 2-8 20m8-20 8 20M7 15h10M8.5 11h7M10 7h4M6 18h12"/><path d="M3 4v5m-2-2 2 2 2-2"/></g>',
  "grid-export": '<g fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.7"><path d="m12 2-8 20m8-20 8 20M7 15h10M8.5 11h7M10 7h4M6 18h12"/><path d="M21 9V4m-2 2 2-2 2 2"/></g>',
  home: '<path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1V10zm2 1v8h2v-6h8v6h2v-8l-5-3.9L5 11z"/>',
  offgrid: '<path d="M7 2v7h2V2H7zm8 0v7h2V2h-2zM5 10v2a7 7 0 0 0 6 6.93V22h2v-3.07A7 7 0 0 0 19 12v-2H5z"/>',
});

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
    this._renderStyleReady = false;
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
      const trainingStart = nodeFor("[data-training-start]");
      if (trainingStart) {
        const entryId = trainingStart.dataset.trainingStart;
        const duration = this.shadowRoot.querySelector(
          `[data-training-duration="${CSS.escape(entryId)}"]`
        );
        const direction = this.shadowRoot.querySelector(
          `[data-training-direction="${CSS.escape(entryId)}"]`
        );
        this._callTraining("start_regulation_training", trainingStart, {
          entry_id: entryId,
          duration_minutes: Number(duration && duration.value),
          direction: direction ? direction.value : "both",
        });
        return;
      }
      const trainingStop = nodeFor("[data-training-stop]");
      if (trainingStop) {
        this._callTraining("stop_regulation_training", trainingStop, {
          entry_id: trainingStop.dataset.trainingStop,
        });
        return;
      }
      const candidateAction = nodeFor("[data-training-candidate-action]");
      if (candidateAction) {
        const apply = candidateAction.dataset.trainingCandidateAction === "apply";
        if (!window.confirm(this._t(apply ? "training_apply_confirm" : "training_reset_confirm"))) return;
        this._callTraining(
          apply ? "apply_regulation_training_candidate" : "reset_regulation_training_candidate",
          candidateAction,
          { entry_id: candidateAction.dataset.entryId, confirm: true }
        );
        return;
      }
      const dashboardSetting = nodeFor("[data-dashboard-setting]");
      if (dashboardSetting) {
        const entryId = dashboardSetting.dataset.entryId;
        const setting = dashboardSetting.dataset.dashboardSetting;
        if (setting === "debug-start") {
          if (!window.confirm(this._t("debug_warning"))) return;
          const duration = this.shadowRoot.querySelector(`[data-debug-duration="${CSS.escape(entryId)}"]`);
          this._callTraining("start_debug_recording", dashboardSetting, {
            entry_id: entryId,
            duration_minutes: Number(duration?.value || 10),
          });
        } else if (setting === "debug-stop") {
          this._callTraining("stop_debug_recording", dashboardSetting, { entry_id: entryId });
        } else {
          this._openOptionsFlow(entryId, setting);
        }
        return;
      }
      const optionsNext = nodeFor("[data-options-next]");
      if (optionsNext) {
        this._submitOptionsFlow(optionsNext.dataset.optionsNext);
        return;
      }
      if (nodeFor("[data-options-submit]")) {
        this._submitOptionsFlow();
        return;
      }
      if (nodeFor("[data-options-close]")) {
        if (this._optionsFlowId) {
          this._hass.callApi("DELETE", `config/config_entries/options/flow/${this._optionsFlowId}`).catch(() => {});
        }
        this._optionsFlowId = null;
        this._optionsFlowBody = "";
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
      const applySelect = nodeFor("[data-apply-select]");
      if (applySelect) {
        const entityId = applySelect.dataset.applySelect;
        const select = this.shadowRoot.querySelector(`[data-control-select="${CSS.escape(entityId)}"]`);
        if (select) this._applyControl("select_option", entityId, { option: select.value });
        return;
      }
      const applyNumber = nodeFor("[data-apply-number]");
      if (applyNumber) {
        const entityId = applyNumber.dataset.applyNumber;
        const input = this.shadowRoot.querySelector(`[data-control-number="${CSS.escape(entityId)}"]`);
        const value = Number(input ? input.value : NaN);
        if (input && input.reportValidity() && Number.isFinite(value)) {
          this._applyControl("set_value", entityId, { value });
        }
        return;
      }
      const detailsButton = nodeFor("[data-details-toggle]");
      if (detailsButton) {
        const details = this.shadowRoot.getElementById(detailsButton.dataset.detailsToggle);
        const card = detailsButton.closest(".system-card, .pack-card");
        if (!details || !card) return;
        const open = card.classList.toggle("details-open");
        this._openDetailId = open ? detailsButton.dataset.detailsToggle : null;
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
        detailsButton.setAttribute("aria-expanded", String(open));
        detailsButton.textContent = this._t(open ? "hide_details" : "details");
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
    this.shadowRoot.addEventListener("pointermove", (event) => this._updateHistoryTooltip(event));
    this.shadowRoot.addEventListener("pointerout", (event) => {
      const fromChart = event.target instanceof Element ? event.target.closest("[data-history-chart]") : null;
      const toChart = event.relatedTarget instanceof Element ? event.relatedTarget.closest("[data-history-chart]") : null;
      if (fromChart && fromChart !== toChart) this._hideHistoryTooltip(fromChart);
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

  _sameRenderNode(current, next) {
    if (!current || current.nodeType !== next.nodeType) return false;
    if (current.nodeType !== Node.ELEMENT_NODE) return true;
    if (current.localName !== next.localName) return false;
    const currentKey = current.getAttribute("data-render-key");
    const nextKey = next.getAttribute("data-render-key");
    return !currentKey && !nextKey ? true : currentKey === nextKey;
  }

  _patchRenderNode(current, next) {
    if (current.nodeType === Node.TEXT_NODE) {
      if (current.data !== next.data) current.data = next.data;
      return;
    }
    if (current.nodeType !== Node.ELEMENT_NODE) return;
    for (const attribute of [...current.attributes]) {
      if (!next.hasAttribute(attribute.name)) current.removeAttribute(attribute.name);
    }
    for (const attribute of [...next.attributes]) {
      if (current.getAttribute(attribute.name) !== attribute.value) {
        current.setAttribute(attribute.name, attribute.value);
      }
    }
    if (current instanceof HTMLInputElement && current.type === "checkbox") {
      current.checked = next.checked;
    } else if (current instanceof HTMLInputElement && document.activeElement !== current) {
      current.value = next.value;
    }
    this._patchRenderChildren(current, next);
    if (current instanceof HTMLSelectElement && document.activeElement !== current) {
      current.value = next.value;
    }
  }

  _patchRenderChildren(currentParent, nextParent) {
    const nextChildren = [...nextParent.childNodes];
    for (let index = 0; index < nextChildren.length; index += 1) {
      const nextChild = nextChildren[index];
      let currentChild = currentParent.childNodes[index] || null;
      if (!this._sameRenderNode(currentChild, nextChild)) {
        const nextKey = nextChild.nodeType === Node.ELEMENT_NODE
          ? nextChild.getAttribute("data-render-key")
          : null;
        const matchingChild = nextKey
          ? [...currentParent.childNodes].slice(index + 1).find((child) =>
            this._sameRenderNode(child, nextChild))
          : null;
        if (matchingChild) {
          currentParent.insertBefore(matchingChild, currentChild);
          currentChild = matchingChild;
        } else {
          const replacement = nextChild.cloneNode(true);
          currentParent.insertBefore(replacement, currentChild);
          currentChild = replacement;
        }
      }
      this._patchRenderNode(currentChild, nextChild);
    }
    while (currentParent.childNodes.length > nextChildren.length) {
      currentParent.lastChild.remove();
    }
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
      observation_mode: ["Beobachtungsmodus", "Observation mode"], transport_cloud_mqtt: ["MQTT-Cloud", "MQTT-Cloud"], transport_local: ["Lokal", "Local"], transport_zensdk: ["ZenSDK", "ZenSDK"], transport_home_assistant: ["Home Assistant / Z-HA", "Home Assistant / Z-HA"],
      menu_settings: ["Einstellungen & Training", "Settings & training"],
      general_settings: ["Allgemein", "General"], expert_settings: ["Expertenmodus", "Expert mode"], smart_mode_settings: ["SmartMode-Verhalten", "Smart Mode behavior"], smart_mode_help: ["Bei Geräten mit direkter SmartMode-Steuerung: Aktiviert bleibt smartMode=1 im Leerlauf gesetzt. Deaktiviert nutzt das bisherige Modellverhalten.", "For devices with direct Smart Mode control: enabled keeps smartMode=1 while idle; disabled uses the existing model behavior."], debug_settings: ["Debug-Modus", "Debug mode"], settings_shortcuts: ["Einstellungen", "Settings"], settings_description: ["Diese Bereiche sind auch weiterhin über das Zahnrad-Menü erreichbar.", "These sections remain available from the gear menu as well."], debug_description: ["Technische Aufzeichnung für die Fehlersuche. Sie kann Sensor-, Geräte-, Energie- und Preiswerte enthalten. Prüfe das Paket vor dem Teilen auf private Informationen.", "Technical recording for troubleshooting. It may contain sensor, device, energy and price values. Review the package for private information before sharing."], debug_warning: ["Debug-Aufzeichnung starten? Sie kann Sensor-, Geräte-, Energie- und Preiswerte enthalten. Prüfe das Paket vor dem Teilen auf private Informationen.", "Start debug recording? It may contain sensor, device, energy and price values. Review the package for private information before sharing."], debug_active: ["Aufzeichnung läuft", "Recording active"], debug_idle: ["Keine Aufzeichnung aktiv", "No recording active"], debug_samples: ["Erfasste Datensätze", "Samples recorded"], debug_end: ["Endet", "Ends"], debug_duration: ["Aufzeichnungsdauer", "Recording duration"], debug_start: ["Debug-Aufzeichnung starten", "Start debug recording"], debug_stop: ["Aufzeichnung beenden und exportieren", "Stop and export recording"], debug_started: ["Aufzeichnung gestartet", "Recording started"], debug_stopped: ["Aufzeichnung beendet", "Recording stopped"], settings_saved: ["Einstellungen gespeichert.", "Settings saved."], settings_closed: ["Einstellungsdialog geschlossen.", "Settings dialog closed."], options_continue: ["Weiter", "Continue"], options_save: ["Speichern", "Save"], options_cancel: ["Schließen", "Close"],
      no_training_entries: ["Keine Regelungstrainings-Entität gefunden.", "No regulation training entity was found."],
      training_title: ["Regelungstraining", "Regulation training"], training_description: ["Das Training beobachtet Lade- und Entladephasen, ohne die aktive Regelung zu verändern.", "Training observes charge and discharge periods without changing active regulation."],
      training_status: ["Status", "Status"], training_active: ["Läuft", "Running"], training_idle: ["Inaktiv", "Idle"], training_samples: ["Trainingsdaten", "Training samples"], training_result: ["Ergebnis", "Result"], training_duration: ["Trainingsdauer", "Training duration"], training_direction: ["Trainingsrichtung", "Training direction"], training_both: ["Laden und Entladen", "Charge and discharge"], training_charge: ["Nur Laden", "Charging only"], training_discharge: ["Nur Entladen", "Discharging only"], start_training: ["Training starten", "Start training"], stop_training: ["Training beenden", "Stop training"],
      training_result_not_trained: ["Noch nicht trainiert", "Not trained"], training_result_training: ["Training läuft", "Training in progress"], training_result_candidate_proposed: ["Shadow-Kandidat verfügbar", "Shadow candidate available"], training_result_no_improvement: ["Keine sichere Verbesserung gefunden", "No safe improvement found"], training_result_insufficient_data: ["Weitere Trainingsdaten erforderlich", "More training data needed"], training_result_interrupted: ["Unterbrochen – Teildaten gesichert", "Interrupted – partial data saved"], training_interrupted_notice: ["Dieses Training wurde unterbrochen. Die bis zum letzten Sicherungspunkt erfassten Daten bleiben zur Auswertung erhalten; ein daraus berechneter Vorschlag kann nicht übernommen werden.", "This training was interrupted. Data captured up to the last checkpoint is available for review; any resulting proposal cannot be applied."],
      training_comparison: ["Vergleich mit aktuellem Profil", "Comparison with current profile"], training_direction_charge: ["Ladeverhalten", "Charging"], training_direction_discharge: ["Entladeverhalten", "Discharging"], training_need_more_data: ["Für diese Richtung liegen noch nicht genügend auswertbare Daten vor.", "There is not enough usable data for this direction yet."], training_samples_direction: ["Auswertbare Datensätze", "Usable samples"], training_sample_coverage: ["Auswertbar / erfasst", "Usable / captured"], training_unchanged_commands: ["Unveränderte aktive Befehle einbezogen", "Unchanged active commands included"], training_sample_exclusions: ["Ausgeschlossen (Netz / Fehlerwert / Befehl / Kontext / Profilabweichung)", "Excluded (grid / error / command / context / profile mismatch)"], training_confidence_summary: ["Gesamtkonfidenz / Mindestwert", "Overall confidence / minimum"], training_sessions_aggregated: ["Zusammengefasste Trainingsläufe", "Training runs combined"], training_sessions_ignored: ["Läufe mit anderem Profil ignoriert", "Runs with a different profile ignored"], training_charge_context: ["Ladekontexte (PV-reguliert / AC oder sonstig)", "Charging contexts (PV-regulated / AC or other)"], training_reason_too_few_samples: ["Mindestzahl auswertbarer Proben nicht erreicht.", "Minimum number of usable samples not reached."], training_reason_too_few_events: ["Zu wenige Reaktionsereignisse.", "Too few response events."], training_reason_low_confidence: ["Die Gesamtkonfidenz liegt unter dem erforderlichen Mindestwert.", "Overall confidence is below the required minimum."], training_reason_missing_baseline: ["Kein vollständiger Vergleich zum aktuellen Profil möglich.", "Could not build a complete comparison with the current profile."],
      training_reversal_shadow: ["Umkehrsperre · Schattenauswertung", "Reversal hold · shadow estimate"], training_reversal_threshold: ["Schwelle", "Threshold"], training_reversal_delayed: ["Simulierte Umkehrungen", "Simulated reversals"], training_reversal_overrides: ["Nicht geeignete Umkehrungen", "Ineligible reversals"], training_reversal_hold: ["Geschätzte Haltezeit", "Estimated hold time"], training_reversal_energy: ["Während der Sperre zurückgehaltene Energie", "Energy deferred during hold"], training_reversal_insufficient: ["Noch nicht genügend geeignete PV-/Lastdaten.", "Not enough eligible PV/load data yet."], training_reversal_eligible_samples: ["Geeignete / aktive Richtungsproben", "Eligible / active-direction samples"], training_reversal_observed: ["Beobachtete Richtungswechsel", "Observed reversals"], training_reversal_main_exclusion: ["Häufigster Ausschlussgrund", "Most common exclusion"], training_reversal_reason_unsupported_mode: ["Nicht im Automatik- oder Autarkiemodus", "Not in Automatic or Autarky mode"], training_reversal_reason_manual_action: ["Manueller Eingriff", "Manual action"], training_reversal_reason_strategy: ["Keine normale PV-/Laststrategie", "Not a standard PV/load strategy"], training_reversal_reason_profile: ["Regelungsprofil während des Laufs geändert", "Regulation profile changed during run"], training_reversal_reason_forced: ["Erzwungene oder unbekannte Strategie", "Forced or unknown strategy"], training_reversal_reason_priority: ["Priorität zu hoch oder unbekannt", "Priority too high or unknown"], training_reversal_reason_mode: ["Moduswechsel nicht freigegeben", "Mode change not allowed"], training_reversal_reason_protection: ["Entladung durch Schutz gesperrt", "Discharge blocked by protection"], training_reversal_reason_grid: ["Netzsensor ungültig", "Grid sensor invalid"], training_reversal_reason_command: ["Befehl nicht auswertbar", "Command not observable"], training_reversal_note: ["Nur Simulation: manuelle, erzwungene, höher priorisierte oder durch Schutz gesperrte Entscheidungen werden nicht verzögert. Keine Änderung an der aktiven Regelung.", "Simulation only: manual, forced, higher-priority, or protection-blocked decisions are not delayed. Active regulation is unchanged."],
      training_baseline: ["Aktuelles Profil", "Current profile"], training_candidate: ["Trainingsvorschlag", "Training candidate"], training_improvement: ["Verbesserung", "Improvement"], training_gain: ["Vorgeschlagener Faktor", "Proposed factor"], training_response_events: ["Reaktionsereignisse", "Response events"], training_confidence: ["Konfidenz", "Confidence"], training_overshoot: ["Überschwingen", "Overshoot"], training_score_explain: ["Kürzere Balken bedeuten eine geringere Abweichung von der gewünschten Reaktion. Das Ergebnis ist eine Schätzung und ändert die Regelung erst nach Übernahme.", "Shorter bars mean less deviation from the desired response. This is an estimate and does not change regulation until applied."], training_estimated_improvement: ["geringere Abweichung", "lower deviation"], training_estimated_regression: ["höhere Abweichung", "higher deviation"], training_estimated_no_change: ["keine Änderung", "no change"], training_candidate_rejected: ["Kein sicherer Vorschlag für diese Richtung.", "No safe candidate for this direction."], training_candidate_active: ["Trainingskandidat ist aktiv", "Training candidate is active"], training_applied: ["Kandidat aktiviert", "Candidate applied"], training_reset_done: ["Geräteprofil wiederhergestellt", "Device profile restored"], training_started: ["Training gestartet", "Training started"], training_stopped: ["Training beendet", "Training stopped"], training_failed: ["Training konnte nicht ausgeführt werden.", "Training could not be completed."], training_apply: ["Vorschlag übernehmen", "Apply candidate"], training_reset: ["Auf Geräteprofil zurücksetzen", "Restore device profile"], training_apply_confirm: ["Den vorgeschlagenen Kandidaten jetzt für diese BSFAI-Instanz aktivieren? Die Prognose ist eine vereinfachte Schätzung, keine Garantie. Du kannst jederzeit zum Geräteprofil zurückkehren.", "Apply this candidate to this BSFAI instance now? The estimate is simplified and not a guarantee. You can restore the device profile at any time."], training_reset_confirm: ["Den angewendeten Trainingskandidaten entfernen und zum Geräteprofil zurückkehren?", "Remove the applied training candidate and restore the device profile?"], training_result_candidate_active: ["Trainingskandidat aktiv", "Training candidate active"],
      overview: ["Übersicht", "Overview"], energy: ["Energie & Prognose", "Energy & forecast"], economics: ["Wirtschaftlichkeit", "Economics"], controls: ["Steuerung", "Controls"],
      subtitle: ["Energiefluss, Speicher und Systemstatus", "Energy flow, storage and system status"], live: ["LIVE · aktualisiert", "LIVE · updated"], energy_overview: ["Energieübersicht", "Energy overview"], live_values: ["Aktuelle Home-Assistant-Werte", "Live Home Assistant values"],
      battery: ["AKKU", "BATTERY"], pv_power: ["PV-LEISTUNG", "PV POWER"], battery_power: ["AKKULEISTUNG", "BATTERY POWER"], grid_power: ["NETZLEISTUNG", "GRID POWER"], current_price: ["AKTUELLER PREIS", "CURRENT PRICE"], waiting_entity: ["Warte auf passenden Sensor", "Waiting for matching entity"], no_data: ["Noch keine Daten", "No data yet"],
      flows_today: ["Energieflüsse heute", "Today's energy flows"], ledger: ["Gemessenes BSFAI-Energiebuch", "Measured BSFAI energy ledger"], solar_forecast: ["Solarprognose", "Solar forecast"], forecast_compare: ["Brutto-Prognose und nutzbarer Rest", "Gross forecast versus usable remainder"],
      near_term: ["Nächste Stunden · nutzbar", "Next few hours · usable"], forecast_today: ["Heute · Brutto und nutzbar", "Today · gross and usable"], forecast_tomorrow: ["Morgen · Brutto und nutzbar", "Tomorrow · gross and usable"],
      power_now: ["Momentanleistung", "Instantaneous power"], power_note: ["Live-Messwerte · Watt (W)", "Live readings · watts (W)"], daily_energy_note: ["Aufsummierte Energiemengen heute · Kilowattstunden (kWh)", "Accumulated energy today · kilowatt-hours (kWh)"], energy_flow_hint: ["Der mittlere Haus-Kreis steht für den gemeinsamen Hausanschluss und zeigt die gemessene Hauslast. Die Verbindungen zeigen Live-Messwerte; direkte Energiepfade zwischen PV, Netz und Akku werden nicht separat aufgeteilt. Netzbezug + / Einspeisung − · Akkuentladung + / Ladung −.", "The central home circle represents the shared home connection and shows measured household load. Connections show live readings; direct energy paths between PV, grid and battery are not separately allocated. Grid import + / export − · battery discharge + / charge −."], flow_idle: ["Kein aktiver Fluss", "No active flow"], flow_forward: ["Fluss nach rechts", "Flow to the right"], flow_reverse: ["Fluss nach links", "Flow to the left"], flow_unavailable: ["Messwert nicht verfügbar", "Reading unavailable"], grid_net: ["Netzleistung (Bezug + / Einspeisung −)", "Grid power (import + / export −)"], grid_import: ["Netzbezug", "Grid import"], grid_export: ["Netzeinspeisung", "Grid export"], pv_source: ["PV-Leistung", "PV power"], native_pv_source: ["Native PV-Leistung", "Native PV power"], offgrid_source: ["Off-Grid-Ausgang", "Off-grid output"], house_load_source: ["Hauslast", "House load"], battery_source: ["Akku-Leistung", "Battery power"],
      source_unavailable: ["Quelle nicht verfügbar", "Source unavailable"], no_power_readings: ["Keine konfigurierten oder nativen Leistungswerte gefunden.", "No configured or native power readings found."], per_system: ["Je System", "Per system"], shared_metrics: ["Gemeinsamer Wert", "Shared value"],
      pv_battery: ["PV → Akku", "PV → battery"], grid_battery: ["Netz → Akku", "Grid → battery"], battery_home: ["Akku → Haus", "Battery → home"], battery_grid: ["Akku → Netz", "Battery → grid"], native_pv_home: ["Native PV → Haus", "Native PV → home"], grid_export: ["Netzeinspeisung", "Grid export"],
      node_pv: ["PV", "PV"], node_native_pv: ["Native PV", "Native PV"], node_grid: ["Netz", "Grid"], node_battery: ["Akku", "Battery"], node_home: ["Haus", "Home"], node_bus: ["Hausnetz", "Home circuit"], node_site: ["Anlage", "Site"], node_system: ["System", "System"], source: ["Quelle", "Source"], destination: ["Ziel", "Destination"], relative_flow_scale: ["Balken relativ zum größten dargestellten Tagesfluss", "Bars are relative to the largest daily flow shown"],
      usable_3h: ["Nutzbar · nächste 3 Stunden", "Usable · next 3 hours"], usable_6h: ["Nutzbar · nächste 6 Stunden", "Usable · next 6 hours"], usable_today: ["Nutzbar · Rest des Tages", "Usable · rest of today"], gross_today: ["Brutto · Rest des Tages", "Gross · rest of today"], usable_tomorrow: ["Nutzbar · morgen", "Usable · tomorrow"], gross_tomorrow: ["Brutto · morgen", "Gross · tomorrow"],
      gross_amount: ["Brutto", "Gross"], usable_amount: ["Nutzbar", "Usable"], forecast_not_configured: ["Keine Prognosequelle konfiguriert", "No forecast source configured"], forecast_unavailable: ["Prognosedaten derzeit nicht verfügbar", "Forecast data is currently unavailable"],
      forecast_explain: ["Die nutzbare Prognose berücksichtigt die Planungsannahmen von BSFAI. Die Bruttowerte zeigen die importierte Prognose vor dieser Reduktion.", "Usable forecast reflects BSFAI's planning assumptions. Gross values show the imported forecast before that reduction."], economics_today: ["Wirtschaftlichkeit heute", "Today's economics"], daily_costs: ["Tageswerte und Kosten", "Daily value and costs"], battery_benefit: ["Akku-Nutzen", "Battery benefit"], avoided_import: ["Vermiedene Netzbezugskosten", "Avoided grid import"], grid_charge_cost: ["Netzladekosten", "Grid charging cost"], pv_opportunity_cost: ["PV-Opportunitätskosten", "PV opportunity cost"], export_revenue: ["Einspeiseerlös", "Export revenue"], self_consumption_value: ["Wert nativer PV-Eigenverbrauch", "Native PV self-consumption value"], average_values: ["Durchschnittliche Ist-Werte", "Average realized values"], ledger_based: ["Basierend auf dem BSFAI-Energie- und Kostenbuch", "Based on BSFAI's energy and cost ledger"], grid_charge_price: ["Netzladepreis", "Grid charging price"], pv_opportunity_value: ["PV-Opportunitätswert", "PV opportunity value"], blended_charge_price: ["Gewichteter Akku-Ladepreis", "Blended battery charge price"], export_price: ["Einspeisepreis", "Export price"], discharge_value: ["Wert der Akkuentladung", "Battery discharge value"], native_pv_return: ["Ertrag native PV direkt ins Haus", "Native PV to home return"], efficiency: ["Wirtschaftlicher Wirkungsgrad", "Economic efficiency"],
      price_context: ["Preis- und Ladeplanung", "Price and charge planning"], daily_average: ["Tagesdurchschnitt", "Daily average"], peak_threshold: ["Preisspitzen-Schwelle", "Peak threshold"], valley_threshold: ["Niedertarif-Schwelle", "Valley threshold"], planned_charge_need: ["Geplante Netz-Nachladung", "Planned grid top-up"], pv_credit: ["PV-Prognose in Ladeplanung", "PV forecast credited to plan"], peak_coverage: ["Geplante Abdeckung bis", "Planned coverage through"],
      forecast_source_label: ["Quelle", "Source"], forecast_source_unknown: ["nicht angegeben", "not specified"],
      blended_explain: ["Der gewichtete Akku-Ladepreis berücksichtigt die verbuchte Netz- und PV-Ladeenergie. Netzladekosten und PV-Opportunitätswert stammen aus demselben Kostenbuch wie die separaten Preissensoren.", "The blended battery charge price is weighted by recorded grid- and PV-charged energy. Grid charging cost and PV opportunity value use the same cost ledger as the separate price sensors."],
      operating_mode: ["Betriebsart", "Operating mode"], existing_selects: ["Vorhandene BSFAI-Auswahl-Entitäten", "Existing BSFAI select entities"], no_selects: ["Keine BSFAI-Auswahl für Betriebsart oder manuelle Aktion gefunden.", "No BSFAI mode or manual-action select entities were found."], settings: ["BSFAI-Einstellungen", "BSFAI settings"], saved_ha: ["Änderungen werden über Home-Assistant-Zahlen-Entitäten gespeichert", "Changes are saved through Home Assistant number entities"], no_numbers: ["Keine BSFAI-Zahlenregler gefunden.", "No BSFAI number settings were found."],
      home_assistant_sensor: ["Home-Assistant-Sensor", "Home Assistant sensor"], version: ["Integration", "Integration"], dashboard_version: ["Dashboard", "Dashboard"],
      automatic: ["Automatik", "Automatic"], self_sufficient: ["Autarkie", "Self-sufficient"], manual: ["Manuell", "Manual"], standby: ["Standby", "Standby"], charge: ["Laden", "Charge"], pv_surplus: ["PV-Überschussladen", "PV surplus charge"], discharge: ["Entladen", "Discharge"], constant_discharge: ["Konstante Entladung", "Constant discharge"],
      limits_group: ["Leistungs- und SoC-Grenzen", "Power and SoC limits"], price_group: ["Preisstrategie", "Price strategy"], forecast_group: ["PV und Prognose", "PV and forecast"], other_group: ["Weitere Einstellungen", "Other settings"], allowed_range: ["Zulässiger Bereich", "Allowed range"], apply: ["Übernehmen", "Apply"], saving: ["Speichere …", "Saving…"], saved: ["Gespeichert", "Saved"], failed: ["Fehler", "Failed"], manual_action_hint: ["Die manuelle Aktion wird über den separaten Aktionsregler gesteuert.", "Manual action is controlled with the separate action selector."],
      hardware_limits: ["Hardware-SoC-Grenzen", "Hardware SoC limits"], read_only: ["Nur lesbare Telemetrie", "Read-only telemetry"], hardware_explain: ["Diese Werte werden von der Hardware gemeldet. BSFAI stellt dafür keine unterstützte Schreibsteuerung bereit; sie dienen hier nur zur Information.", "These values are reported by the hardware. BSFAI does not expose a supported write control for them, so they are shown for reference only."], control_explain: ["Die Steuerung nutzt die vorhandenen BSFAI-Entitäten und Home-Assistant-Dienste. Das Dashboard schreibt nicht direkt an die Zendure-Hardware.", "Controls use existing BSFAI entities and Home Assistant services. The dashboard does not write directly to Zendure hardware."],
      systems: ["Systeme", "systems"], packs: ["Akku-Packs", "packs"], system: ["Zendure-System", "Zendure system"], zendure_hardware: ["Zendure-Hardware", "Zendure hardware"], dashboard_views: ["Dashboard-Ansichten", "Dashboard views"],
      details: ["Details", "Details"], hide_details: ["Schließen", "Close"], seconds_ago: ["Sek. zuvor", "s ago"],
      home_assistant: ["Home Assistant", "Home Assistant"], show_history: ["Verlauf ansehen", "View history"], back_to_dashboard: ["Zurück zum Dashboard", "Back to dashboard"], current_value: ["Aktueller Wert", "Current value"], sensor_history: ["Sensorverlauf", "Sensor history"], day: ["Tag", "Day"], week: ["Woche", "Week"], month: ["Monat", "Month"], history_chart: ["Sensorverlauf", "Sensor history"], history_empty: ["Für diesen Zeitraum sind keine aufgezeichneten Verlaufsdaten verfügbar.", "No recorded history is available for this period."], history_error: ["Der Verlauf konnte nicht geladen werden. Prüfe, ob Home Assistant die Sensorhistorie speichert.", "History could not be loaded. Check whether Home Assistant records this sensor."], history_note: ["Der Verlauf wird aus den in Home Assistant gespeicherten Sensorzuständen erstellt.", "History is built from sensor states recorded by Home Assistant."], history_counter_note: ["Bei Zählern zeigt das Diagramm die Zunahme je Zeitabschnitt. Rücksetzungen werden nicht als negative Energie dargestellt.", "For counters, the chart shows increases per interval. Resets are not shown as negative energy."], period_increase: ["Zunahme im Zeitraum", "Increase in period"], max_interval: ["Größtes Intervall", "Largest interval"], minimum: ["Minimum", "Minimum"], maximum: ["Maximum", "Maximum"], latest: ["Letzter Wert", "Latest"],
      system_health: ["Systemzustand", "System health"], all_online: ["Alle Systeme online", "All systems online"], attention: ["Prüfung erforderlich", "Attention required"], online_systems: ["Online", "Online"], offline_systems: ["Offline oder unbekannt", "Offline or unknown"], oldest_telemetry: ["Älteste Telemetrie", "Oldest telemetry"], minutes_ago: ["Min. zuvor", "min ago"],
        topology: ["Hardware-Topologie", "Hardware topology"], model: ["Modell", "Model"], profile: ["Profil", "Profile"], communication: ["Kommunikation", "Communication"], status: ["Status", "Status"], last_data: ["Letzte Daten", "Last data"], battery_pack: ["Akku-Pack", "Battery Pack"], zendure_pack: ["Zendure-Akku-Pack", "Zendure battery pack"], telemetry: ["Telemetrie", "Telemetry"], unavailable: ["Nicht verfügbar", "Not available"], online: ["ONLINE", "ONLINE"], offline: ["OFFLINE", "OFFLINE"], unknown_path: ["Kommunikationsweg unbekannt", "Communication path unknown"], unknown_status: ["Status unbekannt", "Status unknown"], no_packs: ["Keine Akku-Packs erkannt", "No battery packs detected"], native_empty: ["Die native Hardwareübersicht ist noch nicht verfügbar. Erkannte Zendure-Geräte und angeschlossene Akku-Packs erscheinen hier.", "The native hardware inventory is not available yet. Discovered Zendure systems and attached battery packs will appear here."], system_signals: ["Systemsignale", "System signals"], watchdog_online: ["Erreichbar", "Reachable"], watchdog_degraded: ["Verbindung instabil", "Connection unstable"], watchdog_offline: ["Nicht erreichbar", "Unreachable"], watchdog_unknown: ["Unbekannt", "Unknown"], watchdog_not_supported: ["Direktprüfung nicht verfügbar", "Direct check unavailable"], matching_entities: ["passende Entitäten", "matching entities"], waiting_entities: ["Warte auf Battery-SmartFlow-AI-Entitäten.", "Waiting for Battery SmartFlow AI entities."], footer: ["Battery SmartFlow AI · Steuerung über Home Assistant", "Battery SmartFlow AI · Home Assistant-powered controls"],
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
    const precision = this._displayPrecision(unit);
    const locale = this._hass && this._hass.locale ? this._hass.locale.language : undefined;
    const value = precision === null
      ? entity.state
      : numeric.toLocaleString(locale, { maximumFractionDigits: precision });
    return `${value}${unit ? ` ${unit}` : ""}`;
  }

  _displayPrecision(unit) {
    const normalizedUnit = String(unit || "").toLowerCase().replace(/\s+/g, "");
    if (normalizedUnit === "kwh") return 3;
    if (normalizedUnit.endsWith("/kwh")) return 4;
    if (normalizedUnit === "w" || normalizedUnit === "kw") return 1;

    const currencyCode = this._currencyCodeForUnit(normalizedUnit);
    if (!currencyCode) return null;

    try {
      return new Intl.NumberFormat(undefined, {
        style: "currency",
        currency: currencyCode,
      }).resolvedOptions().maximumFractionDigits;
    } catch (_error) {
      return null;
    }
  }

  _currencyCodeForUnit(normalizedUnit) {
    const symbolCodes = {
      "€": "EUR",
      "£": "GBP",
      "₹": "INR",
      "₩": "KRW",
      "₽": "RUB",
      "₺": "TRY",
    };
    if (symbolCodes[normalizedUnit]) return symbolCodes[normalizedUnit];

    const currencyCode = normalizedUnit.toUpperCase();
    if (!/^[A-Z]{3}$/.test(currencyCode)) return null;

    if (typeof Intl.supportedValuesOf === "function") {
      return Intl.supportedValuesOf("currency").includes(currencyCode)
        ? currencyCode
        : null;
    }
    if (typeof Intl.DisplayNames === "function") {
      const currencyName = new Intl.DisplayNames(undefined, {
        type: "currency",
      }).of(currencyCode);
      return currencyName && currencyName !== currencyCode ? currencyCode : null;
    }

    const fallbackCurrencies = [
      "AED", "ARS", "AUD", "BGN", "BHD", "BRL", "CAD", "CHF", "CLP",
      "CNY", "COP", "CZK", "DKK", "EUR", "GBP", "HKD", "HUF", "IDR",
      "ILS", "INR", "ISK", "JPY", "KRW", "KWD", "MXN", "MYR", "NOK",
      "NZD", "OMR", "PHP", "PLN", "QAR", "RON", "RUB", "SAR", "SEK",
      "SGD", "THB", "TRY", "TWD", "UAH", "USD", "VND", "ZAR",
    ];
    return fallbackCurrencies.includes(currencyCode) ? currencyCode : null;
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

  _configuredPowerSource(keys) {
    const sources = (this._panel && this._panel.config && this._panel.config.power_sources) || [];
    return sources.some((source) => keys.some((key) => Boolean(source[key])));
  }

  _optionalReading(entities, title, terms, sourceKeys = []) {
    const entity = this._find(entities, terms);
    if (!entity || ["unknown", "unavailable"].includes(entity.state)) return "";
    const value = Number(entity.state);
    if (!Number.isFinite(value)) return "";
    if (value === 0 && !this._configuredPowerSource(sourceKeys)) return "";
    const history = ` data-history-entity="${this._escape(entity.entity_id)}" role="button" tabindex="0" aria-label="${this._escape(`${title} · ${this._t("show_history")}`)}"`;
    return `<article class="reading history-card"${history}><span>${this._escape(title)}</span><strong>${this._escape(this._value(entity))}</strong><small>${this._escape(this._t("show_history"))}</small></article>`;
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

  _flowRow(entities, title, terms, width, source, destination, optionalSources = null) {
    const entity = this._find(entities, terms);
    const numeric = entity && !["unknown", "unavailable"].includes(entity.state) && Number.isFinite(Number(entity.state));
    if (optionalSources && (!numeric || (Number(entity.state) === 0 && !this._configuredPowerSource(optionalSources)))) return "";
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
      [this._t("pv_battery"), "economics_daily_pv_to_battery_kwh", "node_pv", "node_battery", ["pv", "native_pv"]],
      [this._t("grid_battery"), "economics_daily_grid_to_battery_kwh", "node_grid", "node_battery"],
      [this._t("battery_home"), "economics_daily_battery_to_home_kwh", "node_battery", "node_home"],
      [this._t("battery_grid"), "economics_daily_battery_to_grid_kwh", "node_battery", "node_grid"],
      [this._t("native_pv_home"), "economics_daily_native_pv_to_home_kwh", "node_native_pv", "node_home", ["native_pv"]],
      [this._t("grid_export"), "economics_daily_grid_export_kwh", "node_site", "node_grid", ["pv", "native_pv"]],
    ];
    const flowValues = flowSpecs.map(([, sensorKey]) => {
      const entity = this._find(entities, [sensorKey]);
      return entity && !["unknown", "unavailable"].includes(entity.state) && Number.isFinite(Number(entity.state))
        ? Math.max(0, Number(entity.state))
        : null;
    });
    const largestFlow = Math.max(...flowValues.filter((value) => value !== null), 0);
    const flowRows = flowSpecs.map(([title, sensorKey, source, destination, optionalSources], index) =>
      this._flowRow(entities, title, [sensorKey], largestFlow ? Math.round((flowValues[index] || 0) / largestFlow * 100) : 0, source, destination, optionalSources)
    ).join("");
    const forecastSources = (this._panel && this._panel.config && this._panel.config.forecast_sources) || [];
    const showForecast = forecastSources.length > 0 || forecastStatus === "available";
    return `
      ${this._livePowerView(entities)}
      <section class="section"><div class="section-head"><h2>${this._escape(this._t("flows_today"))}</h2><small>${this._escape(this._t("daily_energy_note"))}</small></div>
        <small class="flow-scale">${this._escape(this._t("relative_flow_scale"))}</small><div class="flow-grid">
          ${flowRows}
        </div>
      </section>
      ${showForecast ? `<section class="section"><div class="section-head"><h2>${this._escape(this._t("solar_forecast"))}</h2><small class="forecast-source-hint">${this._escape(`${this._t("forecast_compare")} · ${this._forecastSourceHint()}`)}</small></div>
        <div class="forecast-groups">
          <div class="forecast-group"><h3>${this._escape(this._t("near_term"))}</h3><div class="reading-grid">
            ${this._forecastReading(entities, this._t("usable_3h"), [["forecast_next_3h_kwh"], ["usable pv forecast next 3 hours"], ["nutzbare pv-prognose", "nächste 3 stunden"]], forecastStatus)}
            ${this._forecastReading(entities, this._t("usable_6h"), [["forecast_next_6h_kwh"], ["usable pv forecast next 6 hours"], ["nutzbare pv-prognose", "nächste 6 stunden"]], forecastStatus)}
          </div></div>
          ${this._forecastComparison(entities, this._t("forecast_today"), usableTodayTerms, grossTodayTerms, forecastMax, forecastStatus)}
          ${this._forecastComparison(entities, this._t("forecast_tomorrow"), usableTomorrowTerms, grossTomorrowTerms, forecastMax, forecastStatus)}
        </div>
        <p class="explain">${this._escape(forecastStatus === "available" ? this._t("forecast_explain") : this._t(forecastStatus === "not_configured" ? "forecast_not_configured" : "forecast_unavailable"))}</p>
      </section>` : ""}`;
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
          ${this._optionalReading(entities, this._t("pv_credit"), ["learned_planning_pv_forecast_credit_kwh", "pv forecast credited to the charge plan"], ["pv", "native_pv"])}
          ${this._reading(entities, this._t("peak_coverage"), ["learned_planning_coverage_end", "end of planned peak coverage"])}
        </div>
      </section>
      <section class="section"><div class="section-head"><h2>${this._escape(this._t("economics_today"))}</h2><small>${this._escape(this._t("daily_costs"))}</small></div>
        <div class="reading-grid">
          ${this._reading(entities, this._t("battery_benefit"), ["economics_daily_battery_benefit", "battery benefit today", "bilanz heute batterie-nutzen"])}
          ${this._reading(entities, this._t("avoided_import"), ["economics_daily_avoided_grid_import_cost", "avoided grid import cost", "vermiedene netzbezugskosten"])}
          ${this._reading(entities, this._t("grid_charge_cost"), ["economics_daily_grid_charge_cost", "grid charging cost", "netzlade-kosten"])}
          ${this._optionalReading(entities, this._t("pv_opportunity_cost"), ["economics_daily_pv_opportunity_cost", "pv opportunity cost", "pv-opportunitätskosten"], ["pv", "native_pv"])}
          ${this._optionalReading(entities, this._t("export_revenue"), ["economics_daily_export_revenue", "export revenue", "einspeiseerlös"], ["pv", "native_pv"])}
          ${this._optionalReading(entities, this._t("self_consumption_value"), ["economics_daily_native_pv_self_consumption_value", "native pv self-consumption value", "wert native pv eigenverbrauch"], ["native_pv"])}
        </div>
      </section>
      <section class="section"><div class="section-head"><h2>${this._escape(this._t("average_values"))}</h2><small>${this._escape(this._t("ledger_based"))}</small></div>
        <div class="reading-grid">
          ${this._reading(entities, this._t("grid_charge_price"), ["economics_average_grid_charge_price", "avg. grid charging price", "ø netzladepreis"])}
          ${this._optionalReading(entities, this._t("pv_opportunity_value"), ["economics_average_pv_opportunity_value", "avg. pv opportunity value", "ø pv-opportunitätswert"], ["pv", "native_pv"])}
          ${this._reading(entities, this._t("blended_charge_price"), ["economics_average_battery_charge_price", "avg. battery charge price", "ø akku-ladepreis"])}
          ${this._optionalReading(entities, this._t("export_price"), ["economics_average_export_price", "avg. export price", "ø einspeisepreis"], ["pv", "native_pv"])}
          ${this._reading(entities, this._t("discharge_value"), ["economics_average_battery_discharge_value", "avg. battery discharge value", "ø wert der batterieentladung"])}
          ${this._optionalReading(entities, this._t("native_pv_return"), ["economics_average_native_pv_to_home_return", "avg. pv to home return", "ø wert native pv direkt ins haus"], ["native_pv"])}
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

  _topologyTransport(value) {
    const transport = this._searchText(value);
    if (transport.includes("zensdk")) return this._t("transport_zensdk");
    if (transport.includes("cloud")) return this._t("transport_cloud_mqtt");
    if (transport.includes("local")) return this._t("transport_local");
    if (transport.includes("home assistant") || transport.includes("z ha")) {
      return this._t("transport_home_assistant");
    }
    return value || this._t("unknown_path");
  }

  _topologyStatus(value) {
    const status = String(value || "");
    return status.replace(/^observation mode/i, this._t("observation_mode")) || this._t("unknown_status");
  }

  _topologyDeviceImage(system) {
    const rawModel = String(system.model || system.name || "").toLowerCase();
    const model = this._searchText(rawModel);
    if (["solarflow 800 plus", "sf800plus"].includes(model)) {
      return "/battery_smartflow_ai/images/sf800plus.png?v=1";
    }
    if (["solarflow 800 pro 2", "sf800pro2"].includes(model)) {
      return "/battery_smartflow_ai/images/sf800pro2.png?v=1";
    }
    if (["solarflow 800 pro", "sf800pro"].includes(model)) {
      return "/battery_smartflow_ai/images/sf800pro.png?v=1";
    }
    if (["solarflow 800", "sf800"].includes(model)) {
      return "/battery_smartflow_ai/images/sf800.png?v=1";
    }
    if (["hub 2000", "hub2000", "zendure hub 2000", "solarflow hub 2000"].includes(model)) {
      return "/battery_smartflow_ai/images/hub2000.png?v=1";
    }
    if (["hyper 2000", "solarflow hyper 2000"].includes(model)) {
      return "/battery_smartflow_ai/images/hyper2000.png?v=1";
    }
    if (/1600\s*ac\s*\+/.test(rawModel)) {
      return "/battery_smartflow_ai/images/sf1600ac-plus.png?v=1";
    }
    if (/2400\s*ac\s*\+/.test(rawModel) || model.includes("2400 ac plus")) {
      return "/battery_smartflow_ai/images/sf2400ac-plus.png?v=1";
    }
    if (["solarflow 2400 pro", "solarflow 2400 ac pro", "sf2400pro", "sf2400acpro"].includes(model)) {
      return "/battery_smartflow_ai/images/sf2400acpro.png?v=1";
    }
    return model === "solarflow 2400 ac" || model === "sf2400ac"
      ? "/battery_smartflow_ai/images/sf2400ac.png?v=1"
      : "";
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
    const needsAttention = offline > 0 || (
      ages.length > 0 && ages.length < systems.length
    );
    return `<section class="section health-summary ${needsAttention ? "attention" : "healthy"}" aria-label="${this._escape(this._t("system_health"))}"><div class="section-head"><h2>${this._escape(this._t("system_health"))}</h2><span class="health-state">${this._escape(this._t(needsAttention ? "attention" : "all_online"))}</span></div><div class="health-grid"><article><small>${this._escape(this._t("online_systems"))}</small><strong>${online} / ${systems.length}</strong></article><article><small>${this._escape(this._t("offline_systems"))}</small><strong>${offline}</strong></article><article><small>${this._escape(this._t("oldest_telemetry"))}</small><strong>${this._escape(oldest == null ? this._t("unavailable") : this._formatAge(oldest))}</strong></article></div></section>`;
  }

  _deviceEntities(entities, deviceName, packNumber) {
    const prefix = this._searchText(deviceName);
    if (!prefix) return [];
    const packPattern = /(battery|batterie|akku)[ -]?pack\s*0*([1-9]\d*)/i;
    return entities.filter((entity) => {
      const name = this._searchText(`${entity.entity_id} ${this._label(entity)}`);
      const hasDeviceName = name === prefix ||
        name.startsWith(`${prefix} `) ||
        name.includes(` ${prefix} `) ||
        name.endsWith(` ${prefix}`);
      if (!hasDeviceName) return false;
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
      standby: this._t("standby"), charge: this._t("charge"), pv_surplus: this._t("pv_surplus"), discharge: this._t("discharge"), constant_discharge: this._t("constant_discharge"),
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

  _callTraining(service, button, data) {
    button.disabled = true;
    const feedback = {
      start_debug_recording: ["debug_started", "debug_start"],
      stop_debug_recording: ["debug_stopped", "debug_stop"],
      start_regulation_training: ["training_started", "start_training"],
      stop_regulation_training: ["training_stopped", "stop_training"],
      apply_regulation_training_candidate: ["training_applied", "training_apply"],
      reset_regulation_training_candidate: ["training_reset_done", "training_reset"],
    }[service] || ["training_failed", "apply"];
    button.textContent = this._t("saving");
    this._hass.callService("battery_smartflow_ai", service, data).then(() => {
      button.textContent = this._t(feedback[0]);
      this._scheduleRender();
    }).catch((error) => {
      button.textContent = this._t("training_failed");
      button.title = String(error);
    }).finally(() => {
      window.setTimeout(() => {
        if (!button.isConnected) return;
        button.disabled = false;
        button.textContent = this._t(feedback[1]);
      }, 1800);
    });
  }

  async _openOptionsFlow(entryId, stepId) {
    try {
      const flow = await this._hass.callApi("POST", "config/config_entries/options/flow", {
        handler: entryId,
      });
      this._optionsFlowId = flow.flow_id;
      const step = await this._hass.callApi("POST", `config/config_entries/options/flow/${flow.flow_id}`, {
        next_step_id: stepId,
      });
      this._renderOptionsFlow(step);
    } catch (error) {
      this._showNotice(String(error));
    }
  }

  _optionsFieldLabel(name) {
    const labels = {
      installed_pv_wp: ["Installierte PV-Leistung (Wp)", "Installed PV power (Wp)"],
      expert_mode_enabled: ["Expertenmodus aktivieren", "Enable expert mode"],
      learned_planning_enabled: ["Lernende Ladeplanung aktivieren", "Enable learned charge planning"],
      full_charge_maintenance_enabled: ["Regelmäßige Vollladung aktivieren", "Enable periodic full charge"],
      full_charge_maintenance_interval_days: ["Intervall in Tagen", "Interval in days"],
      cell_voltage_protection_enabled: ["Zellspannungs-Schutz aktivieren", "Enable cell-voltage protection"],
      cell_voltage_warning: ["Warnschwelle (V)", "Warning threshold (V)"],
      cell_voltage_cutoff: ["Abschaltschwelle (V)", "Cutoff threshold (V)"],
      cell_voltage_resume: ["Fortsetzen ab (V)", "Resume threshold (V)"],
      lowest_cell_voltage_pack_1: ["Niedrigste Zellspannung Akku-Pack 1", "Lowest cell voltage battery pack 1"],
      lowest_cell_voltage_pack_2: ["Niedrigste Zellspannung Akku-Pack 2", "Lowest cell voltage battery pack 2"],
      lowest_cell_voltage_pack_3: ["Niedrigste Zellspannung Akku-Pack 3", "Lowest cell voltage battery pack 3"],
      lowest_cell_voltage_pack_4: ["Niedrigste Zellspannung Akku-Pack 4", "Lowest cell voltage battery pack 4"],
      lowest_cell_voltage_pack_5: ["Niedrigste Zellspannung Akku-Pack 5", "Lowest cell voltage battery pack 5"],
      lowest_cell_voltage_pack_6: ["Niedrigste Zellspannung Akku-Pack 6", "Lowest cell voltage battery pack 6"],
      native_capacity_override_kwh: ["Manuelle Kapazitätskorrektur (kWh)", "Manual capacity override (kWh)"],
      native_zendure_always_smart_mode_1: ["SmartMode 1 auch im Standby beibehalten", "Keep Smart Mode 1 during standby"],
    }[name];
    if (labels) return labels[String(this._hass?.locale?.language || "").toLowerCase().startsWith("de") ? 0 : 1];
    return name.replaceAll("_", " ");
  }

  _renderOptionsFlow(step) {
    if (!step || step.type === "abort" || step.type === "create_entry") {
      const finished = step?.type === "create_entry";
      this._optionsFlowId = null;
      this._scheduleRender();
      this._showNotice(this._t(finished ? "settings_saved" : "settings_closed"));
      return;
    }
    const title = step.step_id === "general" ? this._t("general_settings")
      : step.step_id === "smart_mode" ? this._t("smart_mode_settings")
        : this._t("expert_settings");
    let content = "";
    if (step.type === "menu") {
      const menuLabel = { general: "general_settings", expert: "expert_settings", smart_mode: "smart_mode_settings", debug: "debug_settings" };
      content = (step.menu_options || []).filter((option) => menuLabel[option]).map((option) => `<button class="apply" type="button" data-options-next="${this._escape(option)}">${this._escape(this._t(menuLabel[option]))}</button>`).join("");
    } else if (step.type === "form") {
      const fields = (step.data_schema || []).map((field) => {
        const selector = field.selector || {};
        const fieldType = Object.keys(selector)[0];
        const config = selector[fieldType] || {};
        const name = this._escape(field.name);
        const label = this._escape(this._optionsFieldLabel(field.name));
        const value = field.default ?? field.value ?? "";
        if (fieldType === "boolean") return `<label class="option-field"><span>${label}${field.name === "native_zendure_always_smart_mode_1" ? `<small>${this._escape(this._t("smart_mode_help"))}</small>` : ""}</span><input type="checkbox" data-option-field="${name}" ${value ? "checked" : ""}></label>`;
        if (fieldType === "select") {
          const options = (config.options || []).map((option) => {
            const optionValue = typeof option === "object" ? option.value : option;
            const optionLabel = typeof option === "object" ? (option.label || option.value) : option;
            return `<option value="${this._escape(optionValue)}" ${String(optionValue) === String(value) ? "selected" : ""}>${this._escape(optionLabel)}</option>`;
          }).join("");
          return `<label class="option-field"><span>${label}</span><select data-option-field="${name}">${options}</select></label>`;
        }
        if (fieldType === "entity") {
          const domain = config.domain || "sensor";
          const entities = Object.keys(this._hass?.states || {}).filter((entityId) => !domain || entityId.startsWith(`${domain}.`)).sort();
          const options = [`<option value="">—</option>`, ...entities.map((entityId) => `<option value="${this._escape(entityId)}" ${entityId === value ? "selected" : ""}>${this._escape(this._hass.states[entityId]?.attributes?.friendly_name || entityId)}</option>`)].join("");
          return `<label class="option-field"><span>${label}</span><select data-option-field="${name}">${options}</select></label>`;
        }
        const number = fieldType === "number";
        return `<label class="option-field"><span>${label}</span><input data-option-field="${name}" type="${number ? "number" : "text"}" value="${this._escape(value)}" ${config.min !== undefined ? `min="${config.min}"` : ""} ${config.max !== undefined ? `max="${config.max}"` : ""} ${config.step !== undefined ? `step="${config.step}"` : ""}></label>`;
      }).join("");
      content = `${fields}<button class="apply" type="button" data-options-submit>${this._escape(step.step_id === "general" || step.step_id === "smart_mode" || step.step_id === "expert_cell_voltage_config" ? this._t("options_save") : this._t("options_continue"))}</button>`;
    }
    this._optionsFlowTitle = title;
    this._optionsFlowBody = content;
    this._scheduleRender();
  }

  async _submitOptionsFlow(nextStepId = null) {
    const data = {};
    if (nextStepId) {
      data.next_step_id = nextStepId;
    } else {
      const userInput = {};
      this.shadowRoot.querySelectorAll("[data-option-field]").forEach((field) => {
        userInput[field.dataset.optionField] = field.type === "checkbox" ? field.checked
          : field.type === "number" ? Number(field.value) : field.value;
      });
      Object.assign(data, userInput);
    }
    try {
      this._renderOptionsFlow(await this._hass.callApi(
        "POST",
        `config/config_entries/options/flow/${this._optionsFlowId}`,
        data,
      ));
    } catch (error) {
      this._showNotice(String(error));
    }
  }

  _showNotice(message) {
    this._notice = String(message || "");
    this._scheduleRender();
    window.setTimeout(() => {
      this._notice = "";
      this._scheduleRender();
    }, 3000);
  }

  _trainingView() {
    const entries = this._panel?.config?.training_entries || [];
    if (!entries.length) {
      return `<section class="section"><div class="empty">${this._escape(this._t("no_training_entries"))}</div></section>`;
    }
    const settingsCards = [];
    const debugCards = [];
    const trainingCards = [];
    entries.forEach((entry) => {
      const entryId = this._escape(entry.entry_id);
      const entryHeading = entries.length > 1
        ? `<h3 class="dashboard-entry-title">${this._escape(entry.title || this._t("system"))}</h3>`
        : "";
      const activeState = entry.active_entity && this._hass.states[entry.active_entity];
      const active = activeState?.state === "yes";
      const debugState = entry.debug_active_entity && this._hass.states[entry.debug_active_entity];
      const debugActive = ["yes", "on", "true"].includes(String(debugState?.state || "").toLowerCase());
      const debugSamples = entry.debug_samples_entity && this._hass.states[entry.debug_samples_entity]?.state || "0";
      const debugEnds = entry.debug_ends_entity && this._hass.states[entry.debug_ends_entity]?.state || "—";
      settingsCards.push(
        `<article class="dashboard-entry-card settings-entry">${entryHeading}<div class="settings-actions"><button class="apply" type="button" data-dashboard-setting="general" data-entry-id="${entryId}">${this._escape(this._t("general_settings"))}</button><button class="apply" type="button" data-dashboard-setting="expert" data-entry-id="${entryId}">${this._escape(this._t("expert_settings"))}</button><button class="apply" type="button" data-dashboard-setting="smart_mode" data-entry-id="${entryId}">${this._escape(this._t("smart_mode_settings"))}</button></div></article>`
      );
      debugCards.push(
        `<article class="dashboard-entry-card debug-entry">${entryHeading}<div class="detail-row"><span>${this._escape(this._t("training_status"))}</span><strong>${this._escape(this._t(debugActive ? "debug_active" : "debug_idle"))}</strong></div>${debugActive ? `<div class="detail-row"><span>${this._escape(this._t("debug_samples"))}</span><strong>${this._escape(debugSamples)}</strong></div><div class="detail-row"><span>${this._escape(this._t("debug_end"))}</span><strong>${this._escape(debugEnds)}</strong></div>` : `<div class="debug-duration"><label for="debug-duration-${entryId}">${this._escape(this._t("debug_duration"))}</label><select id="debug-duration-${entryId}" data-debug-duration="${entryId}"><option value="10">10 min</option><option value="30">30 min</option><option value="60">60 min</option><option value="120">120 min</option></select></div>`}<button class="apply" type="button" data-dashboard-setting="debug-${debugActive ? "stop" : "start"}" data-entry-id="${entryId}">${this._escape(this._t(debugActive ? "debug_stop" : "debug_start"))}</button></article>`
      );
      const samplesState = entry.samples_entity && this._hass.states[entry.samples_entity];
      const resultState = entry.result_entity && this._hass.states[entry.result_entity];
      const evaluation = resultState?.attributes?.shadow_evaluation;
      const candidateActive = resultState?.attributes?.candidate_active === true;
      const interrupted = resultState?.attributes?.interrupted === true || resultState?.state === "interrupted";
      const resultKey = interrupted
        ? "training_result_interrupted"
        : candidateActive
          ? "training_result_candidate_active"
          : `training_result_${resultState?.state || "not_trained"}`;
      const candidateAvailable = resultState?.attributes?.candidate_available === true;
      const candidateAction = candidateActive
        ? `<button class="apply" type="button" data-training-candidate-action="reset" data-entry-id="${entryId}" ${active ? "disabled" : ""}>${this._escape(this._t("training_reset"))}</button>`
        : candidateAvailable && evaluation?.status === "candidate_proposed"
          ? `<button class="apply" type="button" data-training-candidate-action="apply" data-entry-id="${entryId}">${this._escape(this._t("training_apply"))}</button>`
          : "";
      const poolSummary = evaluation && Number.isFinite(Number(evaluation.sessions_aggregated))
        ? `<p class="training-score-note">${this._escape(this._t("training_sessions_aggregated"))}: ${this._escape(Number(evaluation.sessions_aggregated).toLocaleString(this._hass?.locale?.language))}${Number(evaluation.sessions_excluded_incompatible) > 0 ? ` · ${this._escape(this._t("training_sessions_ignored"))}: ${this._escape(Number(evaluation.sessions_excluded_incompatible).toLocaleString(this._hass?.locale?.language))}` : ""}</p>`
        : "";
      const comparison = evaluation
        ? `<section class="training-comparison">${interrupted ? `<p class="training-score-note" role="note">${this._escape(this._t("training_interrupted_notice"))}</p>` : ""}<h4>${this._escape(this._t("training_comparison"))}</h4>${poolSummary}<div class="training-directions">${this._trainingDirectionResult("charge", evaluation.charge, evaluation.charge_context_counts)}${this._trainingDirectionResult("discharge", evaluation.discharge)}</div><p class="training-score-note">${this._escape(this._t("training_score_explain"))}</p>${candidateActive ? `<p class="training-muted">${this._escape(this._t("training_candidate_active"))}</p>` : ""}${candidateAction}</section>`
        : "";
      const reversal = evaluation?.reversal_hysteresis;
      const reversalLocale = this._hass?.locale?.language;
      const formatReversalCount = (value) => Number(value || 0).toLocaleString(reversalLocale);
      const reversalReasonKeys = {
        unsupported_mode: "training_reversal_reason_unsupported_mode",
        manual_action: "training_reversal_reason_manual_action",
        strategy_not_pv_or_load: "training_reversal_reason_strategy",
        forced_or_unknown_strategy: "training_reversal_reason_forced",
        priority_missing_or_high: "training_reversal_reason_priority",
        mode_change_denied: "training_reversal_reason_mode",
        discharge_protection: "training_reversal_reason_protection",
        invalid_grid: "training_reversal_reason_grid",
        command_not_observable: "training_reversal_reason_command",
      };
      const commonReversalExclusion = Object.entries(reversal?.eligibility_exclusion_counts || {})
        .filter(([, count]) => Number(count) > 0)
        .sort((left, right) => Number(right[1]) - Number(left[1]))[0];
      const reversalEligibilitySummary = reversal && Number.isFinite(Number(reversal.direction_sample_count))
        ? `<small>${this._escape(this._t("training_reversal_eligible_samples"))}: ${this._escape(formatReversalCount(reversal.eligible_sample_count))} / ${this._escape(formatReversalCount(reversal.direction_sample_count))}</small><small>${this._escape(this._t("training_reversal_observed"))}: ${this._escape(formatReversalCount(reversal.observed_reversal_count))}</small>`
        : "";
      const commonExclusionReason = commonReversalExclusion?.[0] === "profile_changed"
        ? (reversalLocale === "de" ? "Regelungsprofil während des Laufs geändert" : "Regulation profile changed during run")
        : commonReversalExclusion
          ? this._t(reversalReasonKeys[commonReversalExclusion[0]] || "training_reversal_reason_command")
          : "";
      const reversalExclusionSummary = commonReversalExclusion
        ? `<small>${this._escape(this._t("training_reversal_main_exclusion"))}: ${this._escape(commonExclusionReason)} (${this._escape(formatReversalCount(commonReversalExclusion[1]))})</small>`
        : "";
      const reversalShadow = reversal
        ? `<section class="training-comparison reversal-shadow"><h4>${this._escape(this._t("training_reversal_shadow"))}</h4>${reversal.status === "simulated" ? `<div class="training-result-stats"><div><small>${this._escape(this._t("training_reversal_threshold"))}</small><strong>${this._escape(Number(reversal.threshold_watt_seconds).toLocaleString(reversalLocale))} Ws</strong></div><div><small>${this._escape(this._t("training_reversal_delayed"))}</small><strong>${this._escape(formatReversalCount(reversal.held_reversal_count))} / ${this._escape(formatReversalCount(reversal.eligible_reversal_count))}</strong></div><div><small>${this._escape(this._t("training_reversal_overrides"))}</small><strong>${this._escape(formatReversalCount(reversal.override_reversal_count))}</strong></div><div><small>${this._escape(this._t("training_reversal_hold"))}</small><strong>${this._escape(Number(reversal.estimated_hold_seconds).toLocaleString(reversalLocale, { maximumFractionDigits: 1 }))} s</strong></div><div><small>${this._escape(this._t("training_reversal_energy"))}</small><strong>${this._escape(Number(reversal.estimated_withheld_energy_wh).toLocaleString(reversalLocale, { maximumFractionDigits: 2 }))} Wh</strong></div></div>` : `<p class="training-muted">${this._escape(this._t("training_reversal_insufficient"))}</p>`}${reversalEligibilitySummary}${reversalExclusionSummary}<p class="training-score-note">${this._escape(this._t("training_reversal_note"))}</p></section>`
        : "";
      trainingCards.push(
        `<article class="control-card training-entry-card">${entryHeading}<div class="training-status-grid"><div><small>${this._escape(this._t("training_status"))}</small><strong>${this._escape(this._t(active ? "training_active" : "training_idle"))}</strong></div><div><small>${this._escape(this._t("training_samples"))}</small><strong>${this._escape(samplesState?.state || "0")}</strong></div><div><small>${this._escape(this._t("training_result"))}</small><strong>${this._escape(this._t(resultKey))}</strong></div></div>${comparison}${reversalShadow}<div class="training-controls"><div class="training-control-grid"><div><label for="training-duration-${entryId}">${this._escape(this._t("training_duration"))}</label><select data-training-duration="${entryId}" id="training-duration-${entryId}"><option value="10">10 min</option><option value="30">30 min</option><option value="60">60 min</option><option value="120">120 min</option><option value="1440" selected>24 h</option></select></div><div><label for="training-direction-${entryId}">${this._escape(this._t("training_direction"))}</label><select data-training-direction="${entryId}" id="training-direction-${entryId}"><option value="both" selected>${this._escape(this._t("training_both"))}</option><option value="charge">${this._escape(this._t("training_charge"))}</option><option value="discharge">${this._escape(this._t("training_discharge"))}</option></select></div></div><div class="training-actions"><button class="apply" type="button" data-training-start="${entryId}" ${active ? "disabled" : ""}>${this._escape(this._t("start_training"))}</button><button class="apply" type="button" data-training-stop="${entryId}" ${active ? "" : "disabled"}>${this._escape(this._t("stop_training"))}</button></div></div></article>`
      );
    });
    const flowEditor = this._optionsFlowId ? `<section class="section option-editor"><div class="section-head"><h2>${this._escape(this._optionsFlowTitle || this._t("settings_shortcuts"))}</h2><small>${this._escape(this._t("settings_description"))}</small></div><div class="option-editor-body">${this._optionsFlowBody || ""}</div><button class="apply" type="button" data-options-close>${this._escape(this._t("options_cancel"))}</button></section>` : "";
    const notice = this._notice ? `<p class="settings-notice" role="status">${this._escape(this._notice)}</p>` : "";
    return `${notice}${flowEditor}<section class="section dashboard-area settings-area"><div class="section-head"><div><h2>${this._escape(this._t("settings_shortcuts"))}</h2><small>${this._escape(this._t("settings_description"))}</small></div></div><div class="dashboard-entry-grid">${settingsCards.join("")}</div></section><section class="section dashboard-area debug-area"><div class="section-head"><div><h2>${this._escape(this._t("debug_settings"))}</h2><small>${this._escape(this._t("debug_description"))}</small></div></div><div class="dashboard-entry-grid">${debugCards.join("")}</div></section><section class="section dashboard-area training-area"><div class="section-head"><div><h2>${this._escape(this._t("training_title"))}</h2><small>${this._escape(this._t("training_description"))}</small></div></div><div class="control-grid">${trainingCards.join("")}</div></section>`;
  }

  _trainingDirectionResult(direction, result, chargeContextCounts = null) {
    const title = this._t(direction === "charge" ? "training_direction_charge" : "training_direction_discharge");
    const locale = this._hass && this._hass.locale ? this._hass.locale.language : undefined;
    const sampleCount = Number.isFinite(Number(result?.sample_count)) ? Number(result.sample_count) : 0;
    const directionSampleCount = Number.isFinite(Number(result?.direction_sample_count))
      ? Number(result.direction_sample_count)
      : sampleCount;
    const formatCount = (value) => Number(value).toLocaleString(locale);
    const validRatio = Number.isFinite(Number(result?.valid_sample_ratio))
      ? Number(result.valid_sample_ratio)
      : null;
    const observedConfidence = Number.isFinite(Number(result?.confidence))
      ? Number(result.confidence)
      : null;
    const minimumConfidence = Number.isFinite(Number(result?.minimum_confidence))
      ? Number(result.minimum_confidence)
      : null;
    const contextSummary = direction === "charge" && chargeContextCounts
      ? `<small>${this._escape(this._t("training_charge_context"))}: ${this._escape(formatCount(chargeContextCounts.pv_regulation || 0))} / ${this._escape(formatCount(chargeContextCounts.fixed_or_other || 0))}</small>`
      : "";
    const qualitySummary = validRatio === null
      ? ""
      : `${contextSummary}<small>${this._escape(this._t("training_sample_coverage"))}: ${this._escape(formatCount(sampleCount))} / ${this._escape(formatCount(directionSampleCount))} (${this._escape(`${(validRatio * 100).toLocaleString(locale, { maximumFractionDigits: 1 })} %`)})</small><small>${this._escape(this._t("training_unchanged_commands"))}: ${this._escape(formatCount(result.unchanged_command_sample_count || 0))}</small><small>${this._escape(this._t("training_sample_exclusions"))}: ${this._escape(formatCount(result.rejected_invalid_grid_count || 0))} / ${this._escape(formatCount(result.rejected_missing_error_count || 0))} / ${this._escape(formatCount(result.rejected_command_skip_count || 0))} / ${this._escape(formatCount(result.rejected_context_count || 0))} / ${this._escape(formatCount(result.rejected_profile_mismatch_count || 0))}</small>${observedConfidence !== null && minimumConfidence !== null ? `<small>${this._escape(this._t("training_confidence_summary"))}: ${this._escape(`${(observedConfidence * 100).toLocaleString(locale, { maximumFractionDigits: 1 })} % / ${(minimumConfidence * 100).toLocaleString(locale, { maximumFractionDigits: 0 })} %`)}</small>` : ""}`;
    if (!result || result.decision === "insufficient_data") {
      const reasonKeys = {
        too_few_samples: "training_reason_too_few_samples",
        too_few_response_events: "training_reason_too_few_events",
        confidence_below_threshold: "training_reason_low_confidence",
        missing_baseline: "training_reason_missing_baseline",
      };
      const reasons = (Array.isArray(result?.insufficient_reasons) ? result.insufficient_reasons : [])
        .map((reason) => reasonKeys[reason])
        .filter(Boolean)
        .map((key) => `<small>${this._escape(this._t(key))}</small>`)
        .join("");
      return `<article class="training-direction"><h4>${this._escape(title)}</h4><p>${this._escape(this._t("training_need_more_data"))}</p>${reasons}${qualitySummary}</article>`;
    }
    const formatW = (value) => Number.isFinite(Number(value))
      ? `${Number(value).toLocaleString(locale, { maximumFractionDigits: 1 })} W`
      : "—";
    const improvement = Number.isFinite(Number(result.relative_improvement))
      ? `${(Math.abs(Number(result.relative_improvement)) * 100).toLocaleString(locale, { maximumFractionDigits: 1 })} %`
      : "—";
    const confidence = Number.isFinite(Number(result.confidence))
      ? `${(Number(result.confidence) * 100).toLocaleString(locale, { maximumFractionDigits: 0 })} %`
      : "—";
    const improvementValue = Number(result.relative_improvement);
    const hasImprovement = Number.isFinite(improvementValue);
    const outcomeClass = !hasImprovement || improvementValue === 0
      ? "neutral"
      : improvementValue > 0 ? "better" : "worse";
    const outcomeLabel = hasImprovement
      ? this._t(improvementValue > 0 ? "training_estimated_improvement" : improvementValue < 0 ? "training_estimated_regression" : "training_estimated_no_change")
      : "";
    const outcome = hasImprovement
      ? `<div class="training-outcome ${outcomeClass}"><strong>${this._escape(improvement)}</strong><span>${this._escape(outcomeLabel)}</span></div>`
      : "";
    const baselineScore = Number(result.baseline_score);
    const candidateScore = Number(result.candidate_score);
    const scoreScale = Math.max(0, baselineScore, candidateScore);
    const barWidth = (score) => scoreScale > 0 && Number.isFinite(score)
      ? Math.max(2, Math.min(100, (Math.max(0, score) / scoreScale) * 100))
      : 0;
    const accessibleChartLabel = `${title}: ${this._t("training_baseline")} ${formatW(baselineScore)}, ${this._t("training_candidate")} ${formatW(candidateScore)}`;
    const scoreChart = `<div class="training-score-chart" role="img" aria-label="${this._escape(accessibleChartLabel)}"><div class="training-score-row"><span>${this._escape(this._t("training_baseline"))}</span><div class="training-score-track"><i class="baseline" style="width:${barWidth(baselineScore)}%"></i></div><strong>${this._escape(formatW(baselineScore))}</strong></div><div class="training-score-row"><span>${this._escape(this._t("training_candidate"))}</span><div class="training-score-track"><i class="candidate ${outcomeClass}" style="width:${barWidth(candidateScore)}%"></i></div><strong>${this._escape(formatW(candidateScore))}</strong></div></div>`;
    const rejected = result.decision !== "proposed"
      ? `<p class="training-muted">${this._escape(this._t("training_candidate_rejected"))}</p>`
      : "";
    const overshootValue = Number(result.overshoot_rate);
    const overshoot = Number.isFinite(overshootValue)
      ? `<div><small>${this._escape(this._t("training_overshoot"))}</small><strong>${this._escape(`${(overshootValue * 100).toLocaleString(locale, { maximumFractionDigits: 1 })} %`)}</strong></div>`
      : "";
    const gain = Number(result.selected_gain_factor);
    const gainCard = Number.isFinite(gain) && result.decision === "proposed"
      ? `<div class="training-gain"><span>${this._escape(this._t("training_gain"))}</span><strong>${this._escape(`${gain.toLocaleString(locale, { maximumFractionDigits: 2 })} ×`)}</strong></div>`
      : "";
    const coverageStat = validRatio === null
      ? ""
      : `<div><small>${this._escape(this._t("training_sample_coverage"))}</small><strong>${this._escape(`${formatCount(sampleCount)} / ${formatCount(directionSampleCount)} (${(validRatio * 100).toLocaleString(locale, { maximumFractionDigits: 1 })} %)`)}</strong></div>`;
    return `<article class="training-direction"><div class="training-direction-head"><h4>${this._escape(title)}</h4>${outcome}</div>${scoreChart}${rejected}<div class="training-result-stats">${coverageStat}<div><small>${this._escape(this._t("training_response_events"))}</small><strong>${this._escape(Number(result.response_event_count).toLocaleString(locale))}</strong></div><div><small>${this._escape(this._t("training_confidence"))}</small><strong>${this._escape(confidence)}</strong></div>${overshoot}</div>${qualitySummary ? `<div class="training-score-note">${qualitySummary}</div>` : ""}${gainCard}</article>`;
  }

  _metricCard(title, entityId, fallbackTerms = [], metricType = "generic") {
    let entity = entityId && this._hass && this._hass.states[entityId];
    if (!entity || ["unknown", "unavailable"].includes(entity.state)) {
      entity = this._find(this._entities(), fallbackTerms);
    }
    if (title === this._t("battery")) {
      entity = this._findBatterySoc(this._entities(), entityId) || entity;
    }
    const history = entity ? ` data-history-entity="${this._escape(entity.entity_id)}" role="button" tabindex="0" aria-label="${this._escape(`${title} · ${this._t("show_history")}`)}"` : "";
    const icon = METRIC_ICONS[metricType]
      ? `<svg class="metric-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">${METRIC_ICONS[metricType]}</svg>`
      : "";
    return `<article class="metric${entity ? " history-card" : ""}" data-metric="${this._escape(metricType)}"${history}>${icon}<span>${this._escape(title)}</span><strong>${this._escape(this._value(entity))}</strong>${entity ? `<small>${this._escape(this._t("show_history"))}</small>` : `<small>${this._escape(this._t("waiting_entity"))}</small>`}</article>`;
  }

  _isSocLimitEntity(entity) {
    if (!entity) return false;
    const text = this._searchText(`${entity.entity_id} ${this._label(entity)}`);
    const terms = text.split(" ");
    const mentionsSoc = terms.includes("soc") || text.includes("state of charge") || terms.includes("ladezustand");
    const mentionsLimit = terms.some((term) => ["min", "minimum", "max", "maximum", "limit", "grenze", "reserve"].includes(term));
    return mentionsSoc && mentionsLimit || text.includes("hardware soc");
  }

  _findBatterySoc(entities, configuredEntityId) {
    const candidates = entities.filter((entity) =>
      entity.entity_id.startsWith("sensor.")
      && !this._isSocLimitEntity(entity)
      && !["unknown", "unavailable"].includes(entity.state)
      && Number.isFinite(Number(entity.state)));
    const configured = candidates.find((entity) => entity.entity_id === configuredEntityId);
    const configuredText = configured ? this._searchText(`${configured.entity_id} ${this._label(configured)}`) : "";
    if (configured && /state of charge|ladezustand|battery soc|akku soc|soc pct|soc percent/.test(configuredText)) {
      return configured;
    }
    const textFor = (entity) => this._searchText(`${entity.entity_id} ${this._label(entity)}`);
    const isPack = (entity) => /(?:battery|akku) pack|pack \d+/.test(textFor(entity));
    const systemLevel = candidates
      .filter((entity) => !isPack(entity))
      .find((entity) => /state of charge|ladezustand|soc pct|soc percent/.test(textFor(entity)));
    if (systemLevel) return systemLevel;

    if (configured) return configured;
    return candidates
      .filter((entity) => isPack(entity))
      .find((entity) => /state of charge|ladezustand|soc pct|soc percent/.test(textFor(entity))) || null;
  }

  _findPackSoc(entities, systemName, packNumber) {
    const textFor = (entity) => this._searchText(`${entity.entity_id} ${this._label(entity)}`);
    const candidates = this._deviceEntities(entities, systemName, packNumber).filter((entity) =>
      entity.entity_id.startsWith("sensor.")
      && !this._isSocLimitEntity(entity)
      && !["unknown", "unavailable"].includes(entity.state)
      && Number.isFinite(Number(entity.state))
      && (/\bsoc\b|state of charge|ladezustand|battery soc|akku soc|soc pct|soc percent/.test(textFor(entity)))
    );
    if (!candidates.length) return null;
    return Math.min(100, Math.max(0, Number(candidates[0].state)));
  }

  _topologyFlowDirection(system, systemCount, systemEntities, entities) {
    const sources = (this._panel && this._panel.config && this._panel.config.power_sources) || [];
    const normalizedSystem = this._searchText(`${system.name || ""} ${system.model || ""}`);
    const matchingSources = sources.filter((source) => {
      const normalizedSource = this._searchText(source.name || "");
      return normalizedSource && normalizedSystem && (
        normalizedSystem.includes(normalizedSource) || normalizedSource.includes(normalizedSystem)
      );
    });
    const source = matchingSources.length === 1
      ? matchingSources[0]
      : systemCount === 1 && sources.length === 1
        ? sources[0]
        : null;
    const powerEntity = source && source.battery_power && this._hass.states[source.battery_power];
    if (powerEntity && !["unknown", "unavailable"].includes(powerEntity.state)) {
      const power = Number(powerEntity.state);
      if (Number.isFinite(power) && Math.abs(power) >= 5) {
        // The configured battery power sensor is positive during discharge.
        return power > 0 ? "discharge" : "charge";
      }
    }

    // The topology also shows native Zendure packs that aren't configured as
    // dashboard power sources. Use their direct telemetry as a fallback.
    const directionFrom = (items) => {
      const totals = { charge: 0, discharge: 0 };
      for (const entity of items) {
        if (!entity.entity_id.startsWith("sensor.") || ["unknown", "unavailable"].includes(entity.state)) continue;
        const text = this._searchText(`${entity.entity_id} ${this._label(entity)}`);
        const direction = /\b(?:charge power|charging power|ladeleistung)\b/.test(text)
          ? "charge"
          : /\b(?:discharge power|discharging power|entladeleistung)\b/.test(text)
            ? "discharge"
            : "";
        const value = Number(entity.state);
        if (direction && Number.isFinite(value) && value >= 0) totals[direction] += value;
      }
      if (totals.charge < 5 && totals.discharge < 5) return "";
      if (Math.abs(totals.charge - totals.discharge) < 5) return "";
      return totals.discharge > totals.charge ? "discharge" : "charge";
    };
    const packEntities = (system.packs || []).flatMap((_, index) =>
      this._deviceEntities(entities, system.name, index + 1));
    return directionFrom(packEntities) || directionFrom(systemEntities || []);
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
      // Recorder statistics timestamps are serialized as epoch milliseconds.
      const time = typeof row.start === "number" ? row.start : Date.parse(row.start || "");
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
    const rangeValues = visibleBuckets.length ? visibleBuckets : [0];
    const isPower = attrs.device_class === "power" || String(attrs.unit_of_measurement || "").trim().toLowerCase() === "w";
    const showLine = !isCounter || attrs.device_class === "monetary";
    const axis = this._historyAxis(rangeValues, attrs, isCounter, isPower);
    const minValue = axis.min;
    const maxValue = axis.max;
    const span = maxValue - minValue || 1;
    const width = 900;
    const height = 300;
    const plotLeft = 92;
    const plotWidth = width - plotLeft;
    const plotHeight = height - 24;
    const chartPoints = buckets.map((value, index) => ({
      x: plotLeft + (index / Math.max(1, count - 1)) * plotWidth,
      y: height - (((value === null ? minValue : value) - minValue) / span) * plotHeight - 12,
      value,
      time: start + ((index + 0.5) / count) * (end - start),
    }));
    const path = showLine ? (() => {
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
    })() : "";
    const bars = !showLine ? chartPoints.map((point) => {
      const barWidth = plotWidth / count * 0.66;
      const zeroY = height - ((0 - minValue) / span) * plotHeight - 12;
      const barHeight = Math.abs(zeroY - point.y);
      return `<rect x="${(point.x - barWidth / 2).toFixed(1)}" y="${Math.min(zeroY, point.y).toFixed(1)}" width="${barWidth.toFixed(1)}" height="${barHeight.toFixed(1)}" rx="2" class="chart-bar"><title>${this._escape(`${this._formatHistoryTime(point.time)}: ${this._formatHistoryValue(point.value, attrs.unit_of_measurement)}`)}</title></rect>`;
    }).join("") : "";
    const line = path ? `<path d="${path}" class="chart-line"/>` : "";
    const labels = axis.ticks.map((value) => {
      const y = height - ((value - minValue) / span) * plotHeight - 12;
      const zeroClass = Math.abs(value) < axis.step * 1e-8 ? " chart-zero-gridline" : "";
      return `<g><line x1="${plotLeft}" x2="${width}" y1="${y.toFixed(1)}" y2="${y.toFixed(1)}" class="chart-gridline${zeroClass}"/><text x="0" y="${(y - 4).toFixed(1)}" class="chart-axis-label">${this._escape(this._formatHistoryAxisValue(value, attrs.unit_of_measurement, axis.step))}</text></g>`;
    }).join("");
    const chartPointsJson = this._escape(JSON.stringify(chartPoints.map((point) => ({ time: point.time, value: point.value }))));
    const hoverLayer = `<rect x="${plotLeft}" y="12" width="${plotWidth}" height="${plotHeight}" class="chart-hover-area"/>`;
    const hoverTooltip = `<div class="chart-hover-tooltip" data-history-tooltip role="status" aria-live="polite" hidden></div>`;
    const statusMessage = this._chartError
      ? `<div class="empty">${this._escape(this._t("history_error"))}</div>`
      : !populated
        ? `<div class="empty">${this._escape(this._t("history_empty"))}</div>`
        : "";
    const summary = points.length ? this._historySummary(points, attrs.unit_of_measurement, isCounter, buckets) : "";
    return `<section class="section history-section"><div class="section-head"><div><h2>${this._escape(this._label(entity))}</h2><small>${this._escape(attrs.unit_of_measurement || this._t("sensor_history"))}</small></div><button class="tab" type="button" data-history-back>${this._escape(this._t("back_to_dashboard"))}</button></div><div class="history-current"><span>${this._escape(this._t("current_value"))}</span><strong>${this._escape(this._value(entity))}</strong></div><div class="history-ranges">${[["hour", "1 h"], ["day", this._t("day")], ["week", this._t("week")], ["month", this._t("month")]].map(([range, label]) => `<button type="button" class="tab ${this._chartRange === range ? "active" : ""}" data-history-range="${range}">${this._escape(label)}</button>`).join("")}</div>${statusMessage || `<div class="history-chart-wrap"><svg class="history-chart" data-history-chart data-plot-left="${plotLeft}" data-plot-width="${plotWidth}" data-chart-points="${chartPointsJson}" data-chart-unit="${this._escape(attrs.unit_of_measurement || "")}" viewBox="0 0 ${width} ${height}" role="img" aria-label="${this._escape(this._t("history_chart"))}">${hoverLayer}${labels}${bars}${line}</svg>${hoverTooltip}</div>`}<div class="history-axis"><span>${this._escape(this._formatHistoryTime(start))}</span><span>${this._escape(this._formatHistoryTime(end))}</span></div>${summary ? `<div class="history-summary">${summary}</div>` : ""}<p class="explain">${this._escape(this._t(isCounter ? "history_counter_note" : "history_note"))}</p></section>`;
  }

  _historyAxis(values, attrs, isCounter, isPower) {
    const axisValues = values.filter(Number.isFinite);
    let min = isCounter ? 0 : Math.min(...axisValues);
    let max = Math.max(...axisValues);
    if (isPower || isCounter) {
      min = Math.min(0, min);
      max = Math.max(0, max);
    }
    if (min === max) max = min + Math.max(Math.abs(min) * 0.1, 1);

    const span = max - min;
    const minimumStep = 10 ** -4;
    const niceStep = (value, roundUp) => {
      const exponent = Math.floor(Math.log10(value));
      const magnitude = 10 ** exponent;
      const fraction = value / magnitude;
      const choices = [1, 2, 2.5, 5, 10];
      const choice = roundUp
        ? choices.find((candidate) => candidate >= fraction - 1e-10) || 10
        : [...choices].reverse().find((candidate) => candidate <= fraction + 1e-10) || 1;
      return choice * magnitude;
    };

    let step = Math.max(minimumStep, niceStep(span / 5, true));
    let axisMin = Math.floor(min / step + 1e-10) * step;
    let axisMax = Math.ceil(max / step - 1e-10) * step;
    let divisions = Math.round((axisMax - axisMin) / step);
    if (divisions < 5) {
      const extraDivisions = 5 - divisions;
      if (isPower && max <= 0) axisMin -= extraDivisions * step;
      else axisMax += extraDivisions * step;
      divisions = 5;
    }
    return {
      min: axisMin,
      max: axisMax,
      step,
      ticks: Array.from({ length: divisions + 1 }, (_, index) => Number((axisMin + index * step).toPrecision(12))),
    };
  }

  _formatHistoryAxisValue(value, unit, step) {
    const displayPrecision = this._displayPrecision(unit) ?? 1;
    const stepPrecision = Math.max(0, Math.min(4, Math.ceil(-Math.log10(step) - 1e-10)));
    const precision = Math.min(4, Math.max(displayPrecision, stepPrecision));
    const locale = this._hass && this._hass.locale ? this._hass.locale.language : undefined;
    return `${Number(value).toLocaleString(locale, { maximumFractionDigits: precision })}${unit ? ` ${unit}` : ""}`;
  }

  _updateHistoryTooltip(event) {
    const chart = event.target instanceof Element ? event.target.closest("[data-history-chart]") : null;
    if (!chart) return;
    let points;
    try {
      points = JSON.parse(chart.dataset.chartPoints || "[]");
    } catch (_error) {
      return;
    }
    const rect = chart.getBoundingClientRect();
    if (!rect.width || !points.length) return;
    const plotLeft = Number(chart.dataset.plotLeft || 0);
    const plotWidth = Number(chart.dataset.plotWidth || 1);
    const chartX = ((event.clientX - rect.left) / rect.width) * 900;
    const ratio = Math.min(1, Math.max(0, (chartX - plotLeft) / plotWidth));
    const index = Math.round(ratio * (points.length - 1));
    let point = points[index];
    if (!point || !Number.isFinite(point.value)) {
      point = points
        .filter((candidate) => candidate && Number.isFinite(candidate.value))
        .reduce((nearest, candidate) => !nearest || Math.abs(candidate.time - points[index].time) < Math.abs(nearest.time - points[index].time) ? candidate : nearest, null);
    }
    if (!point) return;
    const wrap = chart.parentElement;
    const tooltip = wrap && wrap.querySelector("[data-history-tooltip]");
    if (!tooltip) return;
    const wrapRect = wrap.getBoundingClientRect();
    tooltip.textContent = `${this._formatHistoryTime(point.time)} · ${this._formatHistoryValue(point.value, chart.dataset.chartUnit)}`;
    tooltip.style.left = `${Math.max(96, Math.min(wrapRect.width - 96, event.clientX - wrapRect.left))}px`;
    tooltip.style.top = `${Math.max(56, event.clientY - wrapRect.top)}px`;
    tooltip.hidden = false;
  }

  _hideHistoryTooltip(chart) {
    const wrap = chart && chart.parentElement;
    const tooltip = wrap && wrap.querySelector("[data-history-tooltip]");
    if (tooltip) tooltip.hidden = true;
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
    const precision = this._displayPrecision(unit) ?? 1;
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

  _powerWatts(entity) {
    if (!entity || ["unknown", "unavailable"].includes(entity.state)) return null;
    const value = Number(entity.state);
    if (!Number.isFinite(value)) return null;
    const unit = String(entity.attributes.unit_of_measurement || "W").trim();
    const factors = { W: 1, kW: 1000, MW: 1000000, mW: 0.001 };
    return Object.prototype.hasOwnProperty.call(factors, unit)
      ? value * factors[unit]
      : null;
  }

  _liveFlowNode(labelKey, detail = "", nodeType = "", placement = "") {
    const iconTypes = {
      node_pv: "pv",
      node_native_pv: "native-pv",
      node_battery: "battery-power",
      node_grid: "grid-power",
      node_home: "home",
      node_bus: "home",
      node_system: "offgrid",
    };
    const icon = METRIC_ICONS[iconTypes[labelKey]];
    const svg = icon
      ? `<svg class="live-flow-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">${icon}</svg>`
      : "";
    return `<div class="live-flow-node ${this._escape(placement)}" data-render-key="node:${this._escape(labelKey)}" data-node="${this._escape(labelKey)}"${nodeType ? ` data-node-type="${this._escape(nodeType)}"` : ""}>${svg}<span><strong>${this._escape(this._t(labelKey))}</strong>${detail ? `<small>${this._escape(detail)}</small>` : ""}</span></div>`;
  }

  _liveFlowBranch(spec, maxWatts, socText, side, row = 1) {
    let watts = this._powerWatts(spec.entity);
    if (spec.nonNegative && watts !== null && watts < -1) watts = null;
    let flow = watts === null ? "unavailable" : "idle";
    if (watts !== null && Math.abs(watts) >= 1) {
      flow = spec.signed && watts < 0 ? "reverse" : "forward";
    }
    const amount = watts === null ? "— W" : `${Math.abs(watts).toLocaleString(this._hass?.locale?.language, { maximumFractionDigits: 1 })} W`;
    const startsAt = flow === "forward" ? spec.from : flow === "reverse" ? spec.to : null;
    const nodeKey = side === "right"
      ? (spec.from === "node_bus" ? spec.to : spec.from)
      : side === "left"
        ? (spec.from === "node_bus" ? spec.to : spec.from)
        : null;
    const startsOnLeft = side === "left"
      ? startsAt === nodeKey
      : side === "right"
        ? startsAt === "node_bus"
        : startsAt === spec.from;
    const direction = flow === "idle" || flow === "unavailable"
      ? flow
      : startsOnLeft ? "forward" : "reverse";
    const arrow = direction === "forward" ? "→" : direction === "reverse" ? "←" : direction === "idle" ? "·" : "—";
    const status = flow === "idle" ? this._t("flow_idle") : flow === "unavailable" ? this._t("flow_unavailable") : "";
    const batteryDetail = (key) => key === "node_battery" && socText ? `${this._t("battery")}: ${socText}` : "";
    const history = spec.entity && spec.entity.entity_id && this._hass?.states?.[spec.entity.entity_id]
      ? ` data-history-entity="${this._escape(spec.entity.entity_id)}" role="button" tabindex="0" aria-label="${this._escape(`${this._t(spec.title)} · ${amount} · ${this._t("show_history")}`)}"`
      : "";
    const value = watts === null ? this._t("flow_unavailable") : amount;
    const accessibleDirection = direction === "forward" ? this._t("flow_forward") : direction === "reverse" ? this._t("flow_reverse") : status;
    const strength = watts === null || maxWatts <= 0 ? 0 : Math.min(1, Math.abs(watts) / maxWatts);
    const trackStyle = flow === "idle" || flow === "unavailable"
      ? ""
      : ` style="--flow-width:${(3 + strength * 3).toFixed(1)}px"`;
    const connection = `<div class="live-flow-connection" role="img" aria-label="${this._escape(`${this._t(spec.title)} · ${accessibleDirection}`)}"><div class="live-flow-measure"><small>${this._escape(this._t(spec.title))}</small><strong>${this._escape(value)}</strong></div><div class="live-flow-track ${direction}"${trackStyle}><span class="live-flow-arrow">${arrow}</span></div>${status ? `<small class="live-flow-status">${this._escape(status)}</small>` : ""}</div>`;
    const branch = `<div class="live-flow-branch side-${side} ${history ? "history-card" : ""}" data-flow="${this._escape(spec.kind)}"${side !== "full" ? ` style="--flow-row:${row}"` : ""}${history}>`;
    if (side === "right") {
      return `${branch}${connection}${this._liveFlowNode(nodeKey, batteryDetail(nodeKey), spec.kind)}</div>`;
    }
    if (side === "full") {
      return `${branch}${this._liveFlowNode(spec.from, batteryDetail(spec.from), spec.kind)}${connection}${this._liveFlowNode(spec.to, batteryDetail(spec.to), spec.kind)}</div>`;
    }
    return `${branch}${this._liveFlowNode(nodeKey, batteryDetail(nodeKey), spec.kind)}${connection}</div>`;
  }

  _liveEnergyFlow(entities) {
    const sources = (this._panel && this._panel.config && this._panel.config.power_sources) || [];
    const allowFallback = sources.length === 1;
    const groups = sources.map((source) => {
      const lanes = [];
      const seen = new Set();
      const resolve = (entityId, terms) => {
        if (entityId) {
          return this._hass?.states?.[entityId]
            || entities.find((entity) => entity.entity_id === entityId)
            || { entity_id: entityId, state: "unavailable", attributes: {} };
        }
        return terms ? this._find(entities, terms) : null;
      };
      const add = (entityId, terms, spec) => {
        const entity = resolve(entityId, terms);
        if (!entity || (entity.entity_id && seen.has(entity.entity_id))) return;
        if (entity.entity_id) seen.add(entity.entity_id);
        lanes.push({ ...spec, entity });
      };

      add(source.pv, allowFallback ? ["pv power", "pv leistung", "solar power", "solarleistung"] : null, {
        title: "pv_source", kind: "pv", from: "node_pv", to: "node_bus", side: "left", nonNegative: true,
      });
      add(source.native_pv, null, {
        title: "native_pv_source", kind: "native-pv", from: "node_native_pv", to: "node_bus", side: "left", nonNegative: true,
      });
      const batterySpec = {
        title: "battery_source", kind: "battery", from: "node_battery", to: "node_bus",
        signed: true, side: "right",
      };
      const configuredBattery = resolve(
        source.battery_power,
        allowFallback ? ["battery power", "batterieleistung", "native hardware power w"] : null,
      );
      let batteryLane = configuredBattery && this._powerWatts(configuredBattery) !== null
        ? { ...batterySpec, entity: configuredBattery }
        : null;
      if (!batteryLane && Array.isArray(source.native_battery_power) && source.native_battery_power.length) {
        let totalWatts = 0;
        let complete = true;
        for (const pair of source.native_battery_power) {
          const chargeEntity = resolve(pair.charge_entity, null);
          const dischargeEntity = resolve(pair.discharge_entity, null);
          const chargeWatts = this._powerWatts(chargeEntity);
          const dischargeWatts = this._powerWatts(dischargeEntity);
          if (chargeWatts !== null && dischargeWatts !== null) {
            totalWatts += dischargeWatts - chargeWatts;
          } else if (chargeWatts !== null && chargeWatts > 1 && (dischargeWatts === null || dischargeWatts <= 1)) {
            // A live positive reading identifies the active direction; Zendure reports charge and discharge separately.
            totalWatts -= chargeWatts;
          } else if (dischargeWatts !== null && dischargeWatts > 1 && (chargeWatts === null || chargeWatts <= 1)) {
            totalWatts += dischargeWatts;
          } else {
            complete = false;
            break;
          }
        }
        if (complete) batteryLane = { ...batterySpec, entity: null, watts: totalWatts, native: true };
      }
      if (!batteryLane && configuredBattery) {
        batteryLane = { ...batterySpec, entity: configuredBattery };
      }
      if (batteryLane) lanes.push(batteryLane);

      let gridLane = null;
      if (source.grid_power) {
        const entity = resolve(source.grid_power, null);
        if (entity) gridLane = { title: "grid_net", kind: "grid", entity, signed: true };
      } else if (source.grid_import || source.grid_export) {
        const importEntity = resolve(source.grid_import, !source.grid_import && allowFallback ? ["grid import", "netzbezug", "bezug"] : null);
        const exportEntity = resolve(source.grid_export, !source.grid_export && allowFallback ? ["grid export", "netzeinspeisung", "einspeisung"] : null);
        if (importEntity || exportEntity) {
          const importWatts = importEntity ? this._powerWatts(importEntity) : 0;
          const exportWatts = exportEntity ? this._powerWatts(exportEntity) : 0;
          const watts = importWatts === null || exportWatts === null ? null : importWatts - exportWatts;
          gridLane = { title: "grid_net", kind: "grid", entity: null, watts, signed: true, importEntity, exportEntity };
        }
      } else {
        const entity = resolve(null, allowFallback ? ["grid power", "netzleistung", "netzbezug"] : null);
        if (entity) gridLane = { title: "grid_net", kind: "grid", entity, signed: true };
      }
      if (gridLane) lanes.push(gridLane);
      add(source.house_load, allowFallback ? ["house_load", "house load", "hauslast", "hausverbrauch"] : null, {
        title: "house_load_source", kind: "house", side: "right", from: "node_bus", to: "node_home", nonNegative: true,
      });
      add(source.offgrid_power, allowFallback ? ["offgrid power", "off grid power", "off grid ausgang"] : null, {
        title: "offgrid_source", kind: "offgrid", side: "full", from: "node_system", to: "node_home", nonNegative: true,
      });
      if (!lanes.length) return "";
      const wattsFor = (lane) => {
        const value = lane.watts !== undefined ? lane.watts : this._powerWatts(lane.entity);
        return lane.nonNegative && value !== null && value < -1 ? null : value;
      };
      const maxWatts = Math.max(...lanes.map((lane) => {
        const value = wattsFor(lane);
        return value === null || (lane.nonNegative && value < -1) ? 0 : Math.abs(value);
      }));
      const socEntity = (source.soc && this._hass?.states?.[source.soc])
        || (allowFallback ? this._findBatterySoc(entities, null) : null);
      const socText = socEntity && !["unknown", "unavailable"].includes(socEntity.state)
        ? this._value(socEntity)
        : "";
      const pvLane = lanes.find((lane) => lane.kind === "pv") || lanes.find((lane) => lane.kind === "native-pv");
      const nativePvLane = lanes.find((lane) => lane.kind === "native-pv");
      const batteryWatts = batteryLane ? wattsFor(batteryLane) : null;
      const gridWatts = gridLane ? wattsFor(gridLane) : null;
      const houseLane = lanes.find((lane) => lane.kind === "house");
      const houseWatts = houseLane ? wattsFor(houseLane) : null;
      const pvWatts = pvLane ? wattsFor(pvLane) : null;
      const amount = (watts) => watts === null
        ? this._t("flow_unavailable")
        : `${Math.abs(watts).toLocaleString(this._hass?.locale?.language, { maximumFractionDigits: 1 })} W`;
      const direction = (watts, kind) => {
        if (watts === null) return this._t("flow_unavailable");
        if (Math.abs(watts) < 1) return this._t("flow_idle");
        if (kind === "grid") return this._t(watts > 0 ? "grid_import" : "grid_export");
        if (kind === "battery") return this._t(watts > 0 ? "discharge" : "charge");
        return "";
      };
      const nodeDetail = (watts, kind, extra = "") => {
        const detail = watts === null ? this._t("flow_unavailable") : `${amount(watts)}${direction(watts, kind) ? ` · ${direction(watts, kind)}` : ""}`;
        return [extra, detail].filter(Boolean).join(" · ");
      };
      const flowClass = (watts, nonNegative = false) => watts === null || (nonNegative && watts < -1)
        ? "unavailable"
        : Math.abs(watts) < 1
          ? "idle"
          : watts < 0 ? "reverse" : "forward";
      const wire = (key, path, watts, nonNegative = false) => {
        const state = flowClass(watts, nonNegative);
        return `<path class="flow-wire-base" d="${path}"/><path class="flow-wire ${state}" data-wire="${key}" d="${path}"/>`;
      };
      const pvDetail = [
        pvLane ? nodeDetail(pvWatts, "pv") : this._t("flow_unavailable"),
        nativePvLane && nativePvLane !== pvLane ? `${this._t("native_pv_source")}: ${amount(wattsFor(nativePvLane))}` : "",
      ].filter(Boolean).join(" · ");
      const batteryDetail = nodeDetail(
        batteryWatts,
        "battery",
        socText ? `${this._t("battery")}: ${socText}` : "",
      );
      const gridDetail = nodeDetail(gridWatts, "grid");
      const houseDetail = houseLane ? nodeDetail(houseWatts, "house") : this._t("flow_unavailable");
      const wires = [
        wire("pv", "M 135 76 C 204 80 224 135 263 160", pvWatts, true),
        wire("grid", "M 300 105 L 300 137", gridWatts),
        wire("battery", "M 465 76 C 396 80 376 135 337 160", batteryWatts),
      ].join("");
      const map = `<div class="live-flow-map" data-render-key="flow-map"><svg class="flow-wires" viewBox="0 0 600 300" preserveAspectRatio="none" aria-hidden="true">${wires}</svg>${this._liveFlowNode("node_pv", pvDetail, "pv", "flow-node-pv")}${this._liveFlowNode("node_grid", gridDetail, "grid", "flow-node-grid")}${this._liveFlowNode("node_battery", batteryDetail, "battery", "flow-node-battery")}${this._liveFlowNode("node_home", houseDetail, "house", "flow-node-house")}</div>`;
      const offgridLane = lanes.find((lane) => lane.kind === "offgrid");
      const offgrid = offgridLane
        ? `<div class="live-flow-offgrid">${this._liveFlowBranch(offgridLane, maxWatts, socText, "full")}</div>`
        : "";
      const groupKey = this._escape(source.entry_id || source.name || "system");
      return `<section class="live-flow-group" data-render-key="flow-group:${groupKey}"><h3>${this._escape(source.name || this._t("system"))}</h3>${map}${offgrid}</section>`;
    }).filter(Boolean);
    return groups.length
      ? `<div class="live-flow-overview">${groups.join("")}<p class="live-flow-note">${this._escape(this._t("energy_flow_hint"))}</p></div>`
      : "";
  }

  _overviewMetrics(entities) {
    const liveFlow = this._liveEnergyFlow(entities);
    if (liveFlow) return liveFlow;
    const sources = (this._panel && this._panel.config && this._panel.config.power_sources) || [];
    const groups = sources.map((source) => {
      const cards = [];
      if (source.soc) cards.push(this._metricCard(this._t("battery"), source.soc, ["battery soc", "ladezustand", "akku soc", "soc"], "soc"));
      if (source.pv) cards.push(this._metricCard(this._t("pv_power"), source.pv, ["pv power", "pv leistung", "solar power", "solarleistung"], "pv"));
      if (source.native_pv) cards.push(this._metricCard(this._t("native_pv_source"), source.native_pv, [], "native-pv"));
      if (source.battery_power) cards.push(this._metricCard(this._t("battery_power"), source.battery_power, ["battery power", "batterieleistung", "native hardware power w"], "battery-power"));
      if (source.grid_power) cards.push(this._metricCard(this._t("grid_power"), source.grid_power, ["grid power", "netzleistung", "netzbezug"], "grid-power"));
      else {
        if (source.grid_import) cards.push(this._metricCard(this._t("grid_import"), source.grid_import, ["grid import", "netzbezug", "bezug"], "grid-import"));
        if (source.grid_export) cards.push(this._metricCard(this._t("grid_export"), source.grid_export, ["grid export", "netzeinspeisung", "einspeisung"], "grid-export"));
      }
      if (source.offgrid_power) cards.push(this._metricCard(this._t("offgrid_source"), source.offgrid_power, ["offgrid power", "off grid power", "off grid ausgang"], "offgrid"));
      if (!cards.length) return "";
      return `<section class="metric-group"><h3>${this._escape(source.name || this._t("system"))}</h3><div class="metric-grid">${cards.join("")}</div></section>`;
    }).filter(Boolean);

    if (groups.length) return groups.join("");

    const metrics = [
      [this._t("battery"), ["ladezustand", "soc", "battery level"], "soc"],
      [this._t("pv_power"), ["pv power", "pv-leistung", "solar power", "solarleis"], "pv"],
      [this._t("battery_power"), ["batterieleistung", "battery power", "charge power"], "battery-power"],
      [this._t("grid_power"), ["netz-leistung", "grid power", "netzbezug"], "grid-power"],
    ];
    return metrics.map(([title, terms, metricType]) => {
      const entity = this._find(entities, terms);
      return this._metricCard(title, entity && entity.entity_id, [], metricType);
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
          : this._view === "settings"
            ? this._trainingView()
        : `${this._healthSummary(systems)}<section class="section"><div class="section-head"><h2>${this._escape(this._t("topology"))}</h2><small>${systems.length} ${this._escape(this._t("systems"))} · ${packCount} ${this._escape(this._t("packs"))}</small></div>
          ${systems.length ? `<div class="systems">${systems.map((system, systemIndex) => {
            const systemEntities = this._deviceEntities(entities, system.name, null);
            const flowDirection = this._topologyFlowDirection(system, systems.length, systemEntities, entities);
            const deviceImage = this._topologyDeviceImage(system);
            const secondaryName = system.model || system.profile || "";
            const showSecondaryName = secondaryName &&
              this._searchText(secondaryName) !== this._searchText(system.name);
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
              const soc = this._findPackSoc(entities, system.name, packNumber);
              const socLevel = soc == null ? "0" : String(soc);
              const socBand = soc == null ? "unknown" : soc < 20 ? "low" : soc < 50 ? "medium" : "high";
              const socLabel = this._escape(`${this._t("battery_pack")} ${packNumber} · ${socLevel} % SoC`);
              const flowSeed = `${system.id || system.name || system.model || systemIndex}:${packNumber}`;
              const flowPhase = [...flowSeed].reduce(
                (phase, character) => (phase * 31 + character.charCodeAt(0)) % 8000,
                0,
              );
              // Keep the phase stable across renders so state refreshes do not restart the animation.
              const flowDelay = flowDirection && soc != null
                ? `--flow-delay:-${(flowPhase / 1000).toFixed(3)}s`
                : "";
              const bubbles = `<span class="soap-bubble" data-bubble="1"></span><span class="soap-bubble" data-bubble="2"></span><span class="soap-bubble" data-bubble="3"></span><span class="soap-bubble" data-bubble="4"></span><span class="soap-bubble" data-bubble="5"></span><span class="soap-bubble" data-bubble="6"></span>`;
              const flowOverlay = flowDirection && soc != null
                ? `<div class="pack-flow" aria-hidden="true"><div class="soap-bubble-track" style="${flowDelay}"><div class="soap-bubble-run">${bubbles}</div><div class="soap-bubble-run">${bubbles}</div></div></div>`
                : "";
              const socAttrs = soc == null
                ? ""
                : ` style="--soc-level:${socLevel}%" data-soc-band="${socBand}"${flowDirection ? ` data-flow="${flowDirection}"` : ""} aria-label="${socLabel}"`;
              return `<article class="pack-card${soc == null ? "" : " has-soc"}"${socAttrs}>${flowOverlay}<div class="pack-head"><div><strong>↳ ${this._escape(this._t("battery_pack"))} ${packNumber}</strong><small>${this._escape(pack.model || this._t("zendure_pack"))}</small></div><button class="details-toggle" type="button" data-details-toggle="${detailId}" aria-controls="${detailId}" aria-expanded="false">${this._escape(this._t("details"))}</button></div><aside class="hover-details" id="${detailId}"><h3>${this._escape(this._t("battery_pack"))} ${packNumber}</h3>${packRows || `<div class="detail-row"><span>${this._escape(this._t("telemetry"))}</span><strong>${this._escape(this._t("unavailable"))}</strong></div>`}</aside></article>`;
            }).join("");
            const systemDetailId = `system-details-${systemIndex}`;
            return `<article class="system-card"><div class="system-head"><div>${deviceImage ? `<img class="system-device-image" src="${deviceImage}" alt="${this._escape(system.name || this._t("system"))}" title="${this._escape(system.name || this._t("system"))}" loading="lazy">` : `<strong>${this._escape(system.name || this._t("system"))}</strong>${showSecondaryName ? `<small>${this._escape(secondaryName)}</small>` : ""}`}</div><div class="system-actions"><span class="status ${system.online ? "" : "offline"}">${this._escape(this._t(system.online ? "online" : "offline"))}</span><button class="details-toggle" type="button" data-details-toggle="${systemDetailId}" aria-controls="${systemDetailId}" aria-expanded="false">${this._escape(this._t("details"))}</button></div></div><div class="device-meta">${this._escape(this._topologyTransport(system.transport))} · ${this._escape(this._topologyStatus(system.status))}</div><div class="packs">${packCards || `<div class="device-meta">${this._escape(this._t("no_packs"))}</div>`}</div><aside class="hover-details" id="${systemDetailId}"><h3>${this._escape(system.name || this._t("system"))}</h3>${systemDetails}${this._detailRows(systemEntities)}</aside></article>`;
          }).join("")}</div>` : `<div class="empty">${this._escape(this._t("native_empty"))}</div>`}
        </section><section class="section"><div class="section-head"><h2>${this._escape(this._t("system_signals"))}</h2><small>${systemSignals.length} ${this._escape(this._t("additional_signals"))}</small></div><div class="inventory signal-grid">${systemSignals.map((entity) => { const watchdog = entity.entity_id.includes("native_zendure_watchdog"); const watchdogState = watchdog ? String(entity.state || "unknown") : ""; const displayedValue = watchdog ? this._t(`watchdog_${watchdogState}`) : this._value(entity); return `<div class="entity signal-entity history-card${watchdog ? ` watchdog-signal watchdog-${this._escape(watchdogState)}` : ""}" data-history-entity="${this._escape(entity.entity_id)}" role="button" tabindex="0" aria-label="${this._escape(`${this._signalLabel(entity)} · ${displayedValue} · ${this._t("show_history")}`)}"><span>${this._escape(this._signalLabel(entity))}</span><strong class="signal-value" title="${this._escape(displayedValue)}">${watchdog ? `<i class="watchdog-light" aria-hidden="true"></i>` : ""}${this._escape(displayedValue)}</strong></div>`; }).join("") || `<div class="empty">${this._escape(this._t("waiting_entities"))}</div>`}</div></section>`;

    const markup = `
      <style>
        :host{display:block;min-height:100%;background:#101214;color:#e7e9eb;font-family:Inter,"Segoe UI",sans-serif;--line:#34383d;--muted:#a4a9af;--cyan:#16c4df;--green:#56cf83;--amber:#f0c34e}
        *{box-sizing:border-box}.shell{max-width:1500px;margin:auto;padding:28px clamp(18px,3vw,42px) 56px}
        header{display:flex;align-items:center;justify-content:space-between;gap:20px;margin-bottom:24px}h1{font-size:clamp(24px,3vw,36px);margin:0;font-weight:650;letter-spacing:-.03em}.sub{color:var(--muted);margin:8px 0 0}.versionline{display:block;color:var(--muted);font-size:11px;margin-top:6px}.badge{border:1px solid #365245;color:#a8e5ba;background:#1e3026;border-radius:999px;padding:9px 14px;font-size:13px;white-space:nowrap}
        .section{background:#1b1e21;border:1px solid var(--line);border-radius:14px;padding:20px;margin-top:18px}.section-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:16px}.section h2{font-size:17px;margin:0}.section-head small,.muted{color:var(--muted)}
        nav{display:flex;gap:8px;margin:8px 0 18px;border-bottom:1px solid var(--line);padding-bottom:12px}.tab{border:1px solid #41464b;background:#25292d;color:#c4c8cc;border-radius:8px;padding:9px 15px;font:inherit;cursor:pointer}.tab.active{border-color:#2388ad;background:#183847;color:#e5f8fc}.tab:focus-visible,.apply:focus-visible{outline:2px solid var(--cyan);outline-offset:2px}.metrics{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px}.metric{min-height:125px;padding:18px;border:1px solid #41464b;border-top:3px solid var(--cyan);border-radius:11px;background:#292d31;display:flex;flex-direction:column;gap:11px}.metric:nth-child(2){border-top-color:var(--green)}.metric:nth-child(3){border-top-color:var(--amber)}.metric span{font-size:11px;letter-spacing:.11em;color:#b1b5b9}.metric strong{font-size:clamp(21px,2vw,30px);font-variant-numeric:tabular-nums}.metric small{color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
        .reading-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px}.reading{min-height:105px;padding:15px;border:1px solid #41464b;border-radius:10px;background:#272b2f;display:flex;flex-direction:column;gap:8px}.reading span{color:#bdc2c6;font-size:12px}.reading strong{font-size:22px;font-variant-numeric:tabular-nums}.reading small{color:var(--muted);line-height:1.35}.forecast-groups{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,280px),1fr));gap:14px}.forecast-group{min-width:0;padding:12px;border:1px solid #343a40;border-radius:11px;background:#202428}.forecast-group h3{font-size:13px;color:#c7cbd0;margin:0 0 10px}.forecast-group .reading{min-height:92px;padding:12px}.forecast-group .reading-grid{grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}.flow-grid{display:grid;gap:8px}.flow-row{display:grid;grid-template-columns:minmax(130px,1fr) 3fr minmax(85px,.7fr);gap:14px;align-items:center;padding:9px 0;border-bottom:1px solid var(--line)}.flow-row span{color:#c3c7ca}.flow-row strong{text-align:right;font-variant-numeric:tabular-nums}.flow-track{height:9px;background:#30353a;border-radius:999px;overflow:hidden}.flow-track i{display:block;width:48%;height:100%;background:linear-gradient(90deg,#1bb7df,#54d08a);border-radius:999px}.explain{color:var(--muted);font-size:12px;line-height:1.5;margin:14px 0 0}.subsection{margin-top:18px}.subsection h3{font-size:14px;color:#c7cbd0;margin:0 0 10px}.control-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,230px),1fr));gap:11px}.control-card{min-width:0;padding:14px;border:1px solid #41464b;border-radius:10px;background:#272b2f;display:flex;flex-direction:column;gap:10px}.control-card label{font-size:13px;color:#d1d5d8}.control-card select,.control-card input{width:100%;min-width:0;background:#171a1d;color:#eef0f1;border:1px solid #4b535a;border-radius:7px;padding:10px;font:inherit}.number-control{display:flex;align-items:center;gap:8px}.number-control span{color:var(--muted);min-width:30px}.control-card small{color:var(--muted);font-size:11px}.apply{align-self:flex-end;border:1px solid #247b9b;background:#153746;color:#dff8ff;border-radius:7px;padding:7px 12px;font:inherit;cursor:pointer}.apply:disabled{opacity:.65;cursor:wait}
        .dashboard-area{margin-top:22px;padding:20px;border-color:var(--area-border);border-left:4px solid var(--area-accent);background:linear-gradient(135deg,var(--area-tint),#1b1e21 58%)}.settings-area{--area-accent:#35bddc;--area-border:#2c6174;--area-tint:#1a2930}.debug-area{--area-accent:#f0c34e;--area-border:#655634;--area-tint:#29261e}.training-area{--area-accent:#56cf83;--area-border:#315b43;--area-tint:#1b2921}.dashboard-area .section-head{justify-content:flex-start;align-items:flex-start;padding-bottom:13px;border-bottom:1px solid var(--area-border)}.dashboard-area .section-head h2{font-size:18px}.dashboard-area .section-head small{display:block;margin-top:6px;line-height:1.45}.dashboard-entry-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,280px),1fr));gap:12px}.dashboard-entry-card{min-width:0;padding:15px;border:1px solid #41464b;border-radius:10px;background:#24292d}.settings-entry{border-top:2px solid #35bddc}.debug-entry{border-top:2px solid #f0c34e}.dashboard-entry-title{margin:0 0 10px;color:#e7e9eb;font-size:14px}.settings-actions{display:flex;flex-wrap:wrap;gap:8px}.settings-actions .apply{align-self:auto}.dashboard-entry-card select{width:100%;min-width:0;background:#171a1d;color:#eef0f1;border:1px solid #4b535a;border-radius:7px;padding:10px;font:inherit}.debug-duration{display:grid;gap:6px}.debug-entry .apply{margin-top:8px}.training-entry-card{gap:12px;border-top:2px solid #56cf83}.training-status-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,145px),1fr));gap:8px}.training-status-grid>div{display:flex;flex-direction:column;gap:6px;min-width:0;padding:10px 12px;border:1px solid #3a4540;border-radius:8px;background:#202722}.training-status-grid small{color:var(--muted);font-size:11px}.training-status-grid strong{overflow-wrap:anywhere;font-variant-numeric:tabular-nums}.training-controls{padding-top:12px;border-top:1px solid #3a4540}.training-control-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,220px),1fr));gap:12px}.training-control-grid>div{display:grid;gap:6px}.training-control-grid select{width:100%;min-width:0;background:#171a1d;color:#eef0f1;border:1px solid #4b535a;border-radius:7px;padding:10px;font:inherit}.training-actions{display:flex;justify-content:flex-end;flex-wrap:wrap;gap:8px;margin-top:10px}.settings-notice{padding:10px 14px;border:1px solid #3f6578;border-radius:8px;background:#1e3440;color:#dff8ff}.option-editor{max-width:100%}.option-editor-body{display:grid;gap:10px}.option-editor .apply{margin-top:10px}.option-field{display:flex;align-items:center;justify-content:space-between;gap:14px;margin:10px 0;padding:10px;border:1px solid #343a40;border-radius:7px;background:#24282c}.option-field input[type=checkbox]{width:24px;height:24px}.option-field input:not([type=checkbox]),.option-field select{max-width:55%}.option-editor .apply[data-options-next]{display:block;width:100%;text-align:left;align-self:stretch}
        .metric-groups{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr));gap:12px}.metric-group{padding:13px;border:1px solid #343a40;border-radius:11px;background:#202428}.metric-group h3{font-size:13px;color:#c7cbd0;margin:0 0 10px}.metric-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,150px),1fr));gap:10px}.metric-grid .metric{min-height:108px;padding:15px}.metric-grid .metric:nth-child(2){border-top-color:var(--green)}.metric-grid .metric:nth-child(3){border-top-color:var(--amber)}
        .systems{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));gap:14px}.system-card{min-width:0;position:relative;padding:17px;background:#172b3a;border:1px solid #2476a8;border-left:4px solid var(--cyan);border-radius:11px}.system-head,.pack-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}.system-head>div:first-child,.pack-head>div:first-child{min-width:0;overflow-wrap:anywhere}.system-head strong,.pack-head strong{font-size:16px}.system-head small,.pack-head small,.device-meta{display:block;color:#b7c4ce;margin-top:6px}.system-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap;justify-content:flex-end}.status{border:1px solid #40604c;background:#20352a;color:#a8e5ba;border-radius:999px;padding:5px 9px;font-size:11px;white-space:nowrap}.status.offline{border-color:#744849;background:#3a2526;color:#f2aaaa}.packs{margin:15px 0 0 14px;padding-left:16px;border-left:1px solid #388ebc;display:grid;gap:9px}.pack-card{min-width:0;position:relative;padding:12px;background:#202b35;border:1px solid #475563;border-radius:9px}.pack-card.has-soc{background:#202b35}.pack-card.has-soc::before{content:"";position:absolute;z-index:0;inset:4px;box-sizing:border-box;background:var(--soc-fill);border:1px solid var(--soc-border);border-radius:5px;clip-path:inset(0 calc(100% - var(--soc-level)) 0 0 round 5px);pointer-events:none}.pack-card.has-soc::after{content:"";position:absolute;z-index:0;inset:5px;border-radius:4px;clip-path:inset(0 calc(100% - var(--soc-level)) 0 0 round 4px);pointer-events:none;opacity:0;background-image:radial-gradient(circle,transparent 43%,rgba(255,255,255,.58) 49%,rgba(255,255,255,.12) 57%,transparent 64%),radial-gradient(circle,transparent 43%,rgba(255,255,255,.4) 49%,rgba(255,255,255,.1) 57%,transparent 64%);background-size:30px 24px,42px 34px;background-position:0 0,10px 7px}.pack-card.has-soc[data-flow="charge"]::after{opacity:.7;animation:bubbles-right 3s linear infinite}.pack-card.has-soc[data-flow="discharge"]::after{opacity:.7;animation:bubbles-left 3s linear infinite}.pack-head{position:relative;z-index:1}@keyframes bubbles-right{from{background-position:0 0,10px 7px}to{background-position:120px 0,178px 7px}}@keyframes bubbles-left{from{background-position:120px 0,178px 7px}to{background-position:0 0,10px 7px}}@media(prefers-reduced-motion:reduce){.pack-card.has-soc[data-flow]::after{animation:none;opacity:.35}}.pack-card[data-soc-band="low"]{--soc-fill:rgba(240,118,91,.28);--soc-border:rgba(196,72,48,.85)}.pack-card[data-soc-band="medium"]{--soc-fill:rgba(240,195,78,.24);--soc-border:rgba(178,132,25,.85)}.pack-card[data-soc-band="high"]{--soc-fill:rgba(86,207,131,.24);--soc-border:rgba(37,145,77,.85)}.pack-card strong{display:block}.pack-card small{display:block;color:#aeb8c1;margin-top:5px}.details-toggle{border:1px solid #3f6578;background:#1a3442;color:#d9f5fb;border-radius:7px;padding:6px 9px;font:inherit;font-size:12px;cursor:pointer;white-space:nowrap}.details-toggle:hover,.details-toggle:focus-visible{border-color:var(--cyan);outline:2px solid var(--cyan);outline-offset:2px}.hover-details{display:none;position:absolute;z-index:5;left:12px;top:calc(100% + 9px);width:min(380px,calc(100vw - 56px));padding:14px;background:#f7f8fa;color:#20242a;border:1px solid #d7dce2;border-radius:10px;box-shadow:0 12px 35px #0008}.system-card.details-open>.hover-details,.pack-card.details-open>.hover-details{display:block}@media(hover:hover){.system-card:hover:not(:has(.pack-card:hover))>.hover-details,.pack-card:hover>.hover-details{display:block}}.hover-details h3{margin:0 0 9px;font-size:14px}.detail-row{display:flex;justify-content:space-between;gap:12px;padding:6px 0;border-bottom:1px solid #e5e7eb;font-size:12px}.detail-row span{color:#59616a}.detail-row strong{text-align:right;overflow-wrap:anywhere}.empty{color:var(--muted);padding:18px;border:1px dashed #485058;border-radius:10px}.inventory{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,240px),1fr));gap:8px}.entity{min-width:0;display:flex;justify-content:space-between;gap:12px;padding:11px 12px;border-bottom:1px solid #34383d}.entity span{color:#c2c6ca;overflow-wrap:anywhere}.entity strong{font-weight:550;text-align:right;font-variant-numeric:tabular-nums;overflow-wrap:anywhere}.signal-grid{grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr));gap:8px}.signal-entity{display:grid;grid-template-columns:minmax(0,1fr) minmax(5rem,auto);align-items:start}.signal-value{max-width:45%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.footer{color:#858c92;font-size:12px;margin:16px 2px}
        .health-summary{border-left:4px solid var(--green)}.health-summary.attention{border-left-color:var(--amber)}.health-state{border:1px solid #40604c;background:#20352a;color:#a8e5ba;border-radius:999px;padding:6px 10px;font-size:12px;white-space:nowrap}.health-summary.attention .health-state{border-color:#78633b;background:#3a3120;color:#f4d78b}.health-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.health-grid article{display:flex;flex-direction:column;gap:7px;padding:12px 14px;background:#25292d;border:1px solid #3a3f44;border-radius:9px}.health-grid small{color:var(--muted)}.health-grid strong{font-size:18px;font-variant-numeric:tabular-nums}
        @media(max-width:900px){.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.topology{grid-template-columns:1fr}.link{height:20px;width:1px;margin:auto}}@media(max-width:520px){header{align-items:flex-start;flex-direction:column}.metrics{grid-template-columns:1fr 1fr}.systems{grid-template-columns:1fr}.health-grid{grid-template-columns:1fr}.section-head{align-items:flex-start;flex-direction:column}.forecast-source-hint{max-width:100%;text-align:left}.hover-details{position:static;width:auto;max-width:100%;margin-top:12px;box-shadow:none}.system-card.details-open>.hover-details,.pack-card.details-open>.hover-details{display:block}.metric{padding:13px}.section{padding:15px}}@media(max-width:360px){nav{gap:5px;overflow-x:auto}.tab{flex:0 0 auto;padding:8px 10px}.metrics{grid-template-columns:1fr}.health-grid{gap:7px}}
        .flow-grid{display:grid;gap:9px;margin-top:10px}.flow-row{display:grid;grid-template-columns:minmax(85px,.8fr) minmax(110px,1.6fr) minmax(85px,.8fr) minmax(80px,.6fr);gap:12px;align-items:center;padding:8px 0;border-bottom:1px solid var(--line)}.flow-node{min-width:0;padding:9px 11px;border:1px solid #41464b;border-radius:9px;background:#272b2f}.flow-node small{display:block;color:var(--muted);font-size:10px}.flow-node strong{display:block;margin-top:3px;font-size:13px}.flow-route{min-width:0;display:flex;flex-direction:column;gap:5px}.flow-label{color:#c3c7ca;font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.flow-direction{display:flex;align-items:center;gap:8px;color:var(--cyan)}.flow-direction>span{font-size:20px;line-height:1}.flow-track{height:8px;flex:1;background:#30353a;border-radius:999px;overflow:hidden}.flow-track i{display:block;height:100%;background:linear-gradient(90deg,#1bb7df,#54d08a);border-radius:999px}.flow-route.unavailable .flow-track{background:repeating-linear-gradient(135deg,#363b40,#363b40 4px,#25292d 4px,#25292d 8px)}.flow-route.unavailable .flow-track i{display:none}.flow-value{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}.flow-scale{color:var(--muted)}
        @media(max-width:520px){.flow-row{grid-template-columns:minmax(0,1fr) minmax(0,1.2fr) minmax(0,1fr) minmax(0,.7fr);gap:6px}.flow-node{padding:8px 7px}.flow-node strong{font-size:12px;overflow-wrap:anywhere}.flow-label{font-size:10px}.flow-direction{gap:4px}.flow-direction>span{font-size:16px}.flow-value{font-size:12px}}@media(max-width:360px){.flow-row{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}.flow-route{grid-column:1 / -1}.flow-value{grid-column:2;text-align:right}}
        .forecast-source-hint{max-width:70%;text-align:right;line-height:1.4;overflow-wrap:anywhere}.forecast-day-chart{display:grid;gap:12px}.forecast-bar-row{display:grid;grid-template-columns:minmax(52px,.65fr) minmax(70px,2fr) minmax(72px,.85fr);gap:9px;align-items:center;font-size:12px}.forecast-bar-row>span{color:#c3c7ca}.forecast-bar-row>strong{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}.forecast-bar-track{height:11px;background:#30353a;border-radius:999px;overflow:hidden}.forecast-bar-track i{display:block;height:100%;background:linear-gradient(90deg,#1bb7df,#54d08a);border-radius:999px}.forecast-bar-row.unavailable .forecast-bar-track{background:repeating-linear-gradient(135deg,#363b40,#363b40 4px,#25292d 4px,#25292d 8px)}.forecast-bar-row.unavailable .forecast-bar-track i{display:none}
        @media(max-width:520px){.forecast-bar-row{grid-template-columns:minmax(0,.6fr) minmax(0,1fr) minmax(0,.8fr);gap:6px;font-size:11px}.forecast-bar-row>span,.forecast-bar-row>strong{overflow-wrap:anywhere}}
        @media(hover:hover){.system-card:hover:not(:has(.pack-card:hover))>.hover-details,.pack-card:hover>.hover-details{display:none}}
        .system-card.details-open>.hover-details,.pack-card.details-open>.hover-details{display:block!important}
        .signal-grid{grid-template-columns:repeat(auto-fit,minmax(min(100%,380px),1fr))}.signal-entity{grid-template-columns:minmax(0,1fr) minmax(8rem,35%);align-items:center}.signal-value{max-width:none;white-space:normal;overflow:visible;text-overflow:clip;overflow-wrap:anywhere}
        .history-card{cursor:pointer;border-color:#16c4df80;box-shadow:0 0 11px #16c4df32,inset 0 0 0 1px #16c4df1a;transition:border-color .15s ease,box-shadow .15s ease}.history-card:hover{border-color:var(--cyan);box-shadow:0 0 17px #16c4df60,inset 0 0 0 1px #16c4df35}.history-card:focus-visible{border-color:var(--cyan);box-shadow:0 0 0 2px #16c4df55,0 0 17px #16c4df60}.history-card small{font-size:11px}@media(prefers-reduced-motion:reduce){.history-card{transition:none}}.home-link{display:inline-flex;align-items:center;gap:7px;margin-top:12px;padding:9px 12px;border:1px solid #3f6578;border-radius:8px;background:#1a3442;color:#d9f5fb;text-decoration:none;font-size:13px}.home-link:hover,.home-link:focus-visible{border-color:var(--cyan);outline:2px solid var(--cyan);outline-offset:2px}.history-section .section-head>div{min-width:0;overflow-wrap:anywhere}.history-section .section-head small{display:block;margin-top:5px;overflow-wrap:anywhere}.history-current{display:flex;justify-content:space-between;align-items:center;gap:12px;margin:12px 0;padding:15px 17px;border:1px solid #41464b;border-left:3px solid var(--cyan);border-radius:10px;background:#272b2f}.history-current span{color:var(--muted)}.history-current strong{font-size:clamp(20px,3vw,28px);font-variant-numeric:tabular-nums}.history-ranges{display:flex;gap:7px;margin:14px 0;overflow-x:auto}.history-chart-wrap{position:relative;width:100%;padding:12px;border:1px solid #343a40;border-radius:11px;background:#202428;overflow:hidden}.history-chart{display:block;width:100%;height:auto;min-height:180px;overflow:visible}.chart-hover-area{fill:transparent;pointer-events:all}.chart-gridline{stroke:#41464b;stroke-width:1}.chart-gridline.chart-zero-gridline{stroke:#91a0a7;stroke-width:1.7;stroke-dasharray:5 3}.chart-axis-label{fill:#a4a9af;font-size:11px}.chart-line{fill:none;stroke:#16c4df;stroke-width:3;stroke-linecap:round;stroke-linejoin:round;vector-effect:non-scaling-stroke}.chart-bar{fill:#16c4df;opacity:.86}.chart-hover-tooltip{position:absolute;z-index:2;transform:translate(-50%,-100%);max-width:calc(100% - 24px);padding:7px 10px;border:1px solid #3f6578;border-radius:7px;background:#142d39;color:#e8f8fc;font-size:12px;font-variant-numeric:tabular-nums;white-space:nowrap;pointer-events:none;box-shadow:0 3px 10px #0006}.chart-hover-tooltip[hidden]{display:none}.history-axis{display:flex;justify-content:space-between;gap:10px;margin-top:8px;color:var(--muted);font-size:11px}.history-summary{display:flex;flex-wrap:wrap;gap:10px;margin-top:13px}.history-summary span{display:flex;gap:7px;padding:9px 12px;border:1px solid #41464b;border-radius:999px;background:#25292d;color:var(--muted);font-size:12px}.history-summary strong{color:#e7e9eb;font-variant-numeric:tabular-nums}
        @media(max-width:520px){.shell{padding:16px 12px 34px}.home-link{min-height:44px}.history-chart-wrap{padding:6px}.history-chart{min-height:160px}.history-current{padding:12px}.history-section .section-head{flex-direction:row;align-items:center}}
        .pack-card.has-soc::before{border-width:2px}
        .training-comparison{padding:12px;border:1px solid #3f6578;border-radius:9px;background:#1e292e}.training-comparison>h4,.training-direction h4{margin:0 0 9px;font-size:13px}.training-directions{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,260px),1fr));gap:8px}.training-direction{min-width:0;padding:12px;border:1px solid #41464b;border-radius:8px;background:#24292d}.training-direction-head{display:flex;align-items:flex-start;justify-content:space-between;gap:10px}.training-direction-head h4{margin:3px 0 10px}.training-outcome{display:flex;align-items:baseline;gap:5px;padding:5px 9px;border:1px solid #3f6578;border-radius:999px;background:#1d3440;color:#bceffc;font-size:11px;white-space:nowrap}.training-outcome strong{font-size:15px;font-variant-numeric:tabular-nums}.training-outcome.better{border-color:#386c51;background:#1e382a;color:#a8e5ba}.training-outcome.worse{border-color:#765b37;background:#3a3020;color:#f4d78b}.training-score-chart{display:grid;gap:9px;padding:10px 0}.training-score-row{display:grid;grid-template-columns:minmax(105px,.9fr) minmax(60px,2fr) minmax(54px,auto);gap:9px;align-items:center;font-size:11px}.training-score-row>span{color:#c2c7cb}.training-score-row>strong{font-variant-numeric:tabular-nums;text-align:right}.training-score-track{height:10px;border-radius:999px;background:#343a40;overflow:hidden}.training-score-track i{display:block;height:100%;min-width:2px;border-radius:999px;background:linear-gradient(90deg,#19b9dc,#45c9e2)}.training-score-track i.candidate.better{background:linear-gradient(90deg,#36bd7a,#77dc9f)}.training-score-track i.candidate.worse{background:linear-gradient(90deg,#db9d42,#f1c36a)}.training-result-stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(85px,1fr));gap:7px;margin-top:7px}.training-result-stats>div{display:flex;flex-direction:column;gap:4px;padding:8px;border:1px solid #383e43;border-radius:7px;background:#202428}.training-result-stats small{color:var(--muted);font-size:10px}.training-result-stats strong{font-size:13px;font-variant-numeric:tabular-nums}.training-gain{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-top:8px;padding:9px 10px;border-left:3px solid var(--cyan);border-radius:5px;background:#1d3038}.training-gain span{color:#c5d2d7;font-size:11px}.training-gain strong{font-variant-numeric:tabular-nums}.training-muted,.training-score-note{color:var(--muted);font-size:11px;line-height:1.45}.training-score-note{margin:9px 0 0}@media(max-width:520px){.training-score-row{grid-template-columns:minmax(78px,.9fr) minmax(35px,1.4fr) minmax(48px,auto);gap:6px}.training-direction{padding:9px}.training-outcome{gap:3px;padding:4px 7px;font-size:10px}.training-outcome strong{font-size:13px}}
        .system-device-image{display:block;width:min(270px,48vw);height:82px;object-fit:contain;object-position:left center}
        .watchdog-signal .signal-value{display:flex;align-items:center;justify-content:flex-end;gap:9px;max-width:none}.watchdog-light{display:inline-block;width:10px;height:10px;flex:0 0 10px;border-radius:50%;background:#8a9299;box-shadow:0 0 7px #8a929966}.watchdog-online .watchdog-light{background:#55d68b;box-shadow:0 0 10px #55d68b99}.watchdog-degraded .watchdog-light{background:#f4c45e;box-shadow:0 0 10px #f4c45e99}.watchdog-offline .watchdog-light{background:#f06b6b;box-shadow:0 0 10px #f06b6b99}
        .metric-grid .metric{position:relative;isolation:isolate;overflow:hidden}.metric-grid .metric::after{content:"";position:absolute;z-index:0;right:-18px;bottom:-43px;width:52%;aspect-ratio:1;border-radius:50%;background:var(--metric-accent);opacity:.065;filter:blur(1px);box-shadow:0 0 28px var(--metric-accent);pointer-events:none}.metric-grid .metric>span,.metric-grid .metric>strong,.metric-grid .metric>small{position:relative;z-index:2}.metric-grid .metric-icon{position:absolute;z-index:1;right:12px;bottom:7px;width:clamp(52px,27%,78px);height:auto;color:var(--metric-accent);fill:currentColor;opacity:.19;filter:drop-shadow(0 0 8px currentColor) drop-shadow(0 0 17px currentColor);pointer-events:none}.metric-grid .metric-icon g{fill:none;stroke:currentColor;stroke-linecap:round;stroke-linejoin:round;stroke-width:1.7}.metric-grid .metric[data-metric="soc"]{--metric-accent:#16c4df}.metric-grid .metric[data-metric="pv"],.metric-grid .metric[data-metric="native-pv"]{--metric-accent:#56cf83}.metric-grid .metric[data-metric="battery-power"]{--metric-accent:#f0c34e}.metric-grid .metric[data-metric="grid-power"],.metric-grid .metric[data-metric="grid-import"],.metric-grid .metric[data-metric="grid-export"]{--metric-accent:#f06b6b}.metric-grid .metric[data-metric="offgrid"]{--metric-accent:#30c9d4}.metric-grid .metric[data-metric]{border-top-color:var(--metric-accent)}
        .pack-card.has-soc::after{opacity:0;background-image:radial-gradient(circle at 17px 16px,rgba(255,255,255,.08) 0 5px,rgba(255,255,255,.82) 5.5px 6.2px,rgba(119,229,236,.58) 6.3px 7px,transparent 7.6px),radial-gradient(circle at 57px 29px,rgba(255,255,255,.06) 0 4px,rgba(255,255,255,.75) 4.5px 5.1px,rgba(160,186,255,.52) 5.2px 5.8px,transparent 6.4px),radial-gradient(circle at 84px 12px,rgba(255,255,255,.05) 0 3px,rgba(255,255,255,.68) 3.5px 4px,rgba(255,180,226,.45) 4.1px 4.7px,transparent 5.3px);background-size:96px 48px;background-repeat:repeat-x;background-position:0 50%;mix-blend-mode:screen;filter:drop-shadow(0 0 2px rgba(255,255,255,.28))}.pack-card.has-soc[data-flow="charge"]::after{opacity:.92;animation:soap-bubbles-right 8s linear infinite}.pack-card.has-soc[data-flow="discharge"]::after{opacity:.92;animation:soap-bubbles-left 8s linear infinite}@keyframes soap-bubbles-right{from{background-position:0 50%}to{background-position:96px 50%}}@keyframes soap-bubbles-left{from{background-position:96px 50%}to{background-position:0 50%}}@media(prefers-reduced-motion:reduce){.pack-card.has-soc[data-flow]::after{animation:none;opacity:.72}}
        .history-card{transition:none}.history-card:hover{box-shadow:0 0 0 1px #16c4df35}
        .pack-card.has-soc::after{display:none}
        .pack-flow{position:absolute;z-index:0;inset:5px;overflow:hidden;border-radius:4px;clip-path:inset(0 calc(100% - var(--soc-level)) 0 0 round 4px);pointer-events:none}.soap-bubble-track{position:absolute;inset:0 auto 0 0;display:flex;width:200%;height:100%;will-change:transform;animation-delay:var(--flow-delay,0s);animation-duration:8s;animation-timing-function:linear;animation-iteration-count:infinite}.pack-card[data-flow="charge"] .soap-bubble-track{animation-name:soap-bubbles-right}.pack-card[data-flow="discharge"] .soap-bubble-track{animation-name:soap-bubbles-left}.soap-bubble-run{position:relative;flex:0 0 50%;height:100%;overflow:hidden}.soap-bubble{position:absolute;bottom:9%;left:var(--bubble-x);width:var(--bubble-size);aspect-ratio:1;border:1px solid rgba(217,251,255,.72);border-radius:50%;background:radial-gradient(circle at 30% 25%,rgba(255,255,255,.38),rgba(151,238,255,.12) 32%,rgba(186,142,255,.14) 67%,rgba(255,255,255,.04));box-shadow:inset -2px -2px 4px rgba(145,204,255,.22),inset 2px 2px 3px rgba(255,255,255,.28),0 0 5px rgba(123,226,255,.32);opacity:.68}.soap-bubble::after{content:"";position:absolute;top:15%;left:23%;width:25%;height:15%;border-radius:50%;background:rgba(255,255,255,.62);filter:blur(.5px)}.soap-bubble[data-bubble="1"]{--bubble-x:7%;--bubble-size:13px;bottom:16%}.soap-bubble[data-bubble="2"]{--bubble-x:21%;--bubble-size:9px;bottom:48%}.soap-bubble[data-bubble="3"]{--bubble-x:38%;--bubble-size:16px;bottom:25%}.soap-bubble[data-bubble="4"]{--bubble-x:55%;--bubble-size:10px;bottom:58%}.soap-bubble[data-bubble="5"]{--bubble-x:72%;--bubble-size:14px;bottom:38%}.soap-bubble[data-bubble="6"]{--bubble-x:89%;--bubble-size:8px;bottom:19%}@keyframes soap-bubbles-right{from{transform:translateX(-50%)}to{transform:translateX(0)}}@keyframes soap-bubbles-left{from{transform:translateX(0)}to{transform:translateX(-50%)}}@media(prefers-reduced-motion:reduce){.soap-bubble-track{animation:none;transform:none;will-change:auto}}
        .live-flow-overview{display:grid;gap:11px}.live-flow-group{min-width:0;padding:13px;border:1px solid #343a40;border-radius:11px;background:#202428}.live-flow-group h3{margin:0 0 9px;color:#c7cbd0;font-size:13px}.live-flow-lanes{display:grid;gap:5px}.live-flow-row{display:grid;grid-template-columns:minmax(100px,.8fr) minmax(100px,1.7fr) minmax(100px,.8fr) minmax(78px,.55fr);gap:12px;align-items:center;padding:8px 5px;border-bottom:1px solid var(--line);border-radius:7px}.live-flow-row:last-child{border-bottom:0}.live-flow-node{min-width:0;display:flex;align-items:center;gap:9px;padding:8px 10px;border:1px solid #41464b;border-radius:9px;background:#272b2f}.live-flow-node>span{min-width:0}.live-flow-node strong{display:block;overflow-wrap:anywhere;font-size:13px}.live-flow-node small{display:block;margin-top:3px;color:var(--muted);font-size:10px}.live-flow-icon{flex:none;width:27px;height:27px;color:var(--flow-accent,#16c4df);fill:currentColor;filter:drop-shadow(0 0 6px currentColor);opacity:.88}.live-flow-icon g{fill:none;stroke:currentColor;stroke-linecap:round;stroke-linejoin:round;stroke-width:1.7}.live-flow-route{min-width:0;display:grid;gap:5px;color:var(--flow-accent,#16c4df)}.live-flow-route>small:first-child{color:#c3c7ca;font-size:11px;overflow-wrap:anywhere}.live-flow-track{position:relative;display:flex;align-items:center;justify-content:center;height:11px;border-radius:999px;background:#30353a;overflow:hidden}.live-flow-track>i{position:absolute;inset:0 auto 0 0;max-width:100%;border-radius:999px;background:linear-gradient(90deg,color-mix(in srgb,var(--flow-accent,#16c4df) 60%,transparent),var(--flow-accent,#16c4df));box-shadow:0 0 9px color-mix(in srgb,var(--flow-accent,#16c4df) 50%,transparent)}.live-flow-track>span{position:relative;z-index:1;color:#f0f2f3;font-size:15px;line-height:11px;text-shadow:0 1px 4px #111}.live-flow-route.reverse .live-flow-track>i{left:auto;right:0;background:linear-gradient(270deg,color-mix(in srgb,var(--flow-accent,#16c4df) 60%,transparent),var(--flow-accent,#16c4df))}.live-flow-route.idle .live-flow-track>i,.live-flow-route.unavailable .live-flow-track>i{display:none}.live-flow-route.unavailable .live-flow-track{background:repeating-linear-gradient(135deg,#363b40,#363b40 4px,#25292d 4px,#25292d 8px)}.live-flow-status{color:var(--muted);font-size:10px}.live-flow-value{color:#e7e9eb;text-align:right;font-size:14px;font-variant-numeric:tabular-nums;white-space:nowrap}.live-flow-row[data-flow="pv"],.live-flow-row[data-flow="native-pv"]{--flow-accent:#56cf83}.live-flow-row[data-flow="battery"]{--flow-accent:#f0c34e}.live-flow-row[data-flow="grid"],.live-flow-row[data-flow="grid-import"],.live-flow-row[data-flow="grid-export"]{--flow-accent:#f06b6b}.live-flow-row[data-flow="house"]{--flow-accent:#16c4df}.live-flow-row[data-flow="offgrid"]{--flow-accent:#30c9d4}.live-flow-note{margin:2px 2px 0;color:var(--muted);font-size:11px;line-height:1.45}@media(max-width:620px){.live-flow-row{grid-template-columns:minmax(82px,.9fr) minmax(72px,1.2fr) minmax(82px,.9fr) minmax(64px,.6fr);gap:6px;padding:7px 2px}.live-flow-node{gap:5px;padding:7px 6px}.live-flow-icon{width:21px;height:21px}.live-flow-node strong{font-size:11px}.live-flow-value{font-size:12px}}@media(max-width:390px){.live-flow-row{grid-template-columns:minmax(0,1fr) auto;gap:5px}.live-flow-route{grid-column:1/-1;grid-row:2}.live-flow-row .live-flow-node:nth-of-type(2){grid-column:1;grid-row:3}.live-flow-value{grid-column:2;grid-row:1}.live-flow-node{min-height:42px}.live-flow-node strong{font-size:12px}}
        @media(max-width:390px){.live-flow-row>.live-flow-node:nth-child(3){grid-column:2;grid-row:3}}.live-flow-track>i{background:linear-gradient(90deg,rgba(255,255,255,.18),var(--flow-accent,#16c4df));box-shadow:0 0 9px var(--flow-accent,#16c4df)}.live-flow-route.reverse .live-flow-track>i{background:linear-gradient(270deg,rgba(255,255,255,.18),var(--flow-accent,#16c4df))}
        .live-flow-map{display:grid;position:relative;isolation:isolate;grid-template-columns:minmax(110px,.78fr) minmax(90px,1.42fr) minmax(120px,.74fr) minmax(90px,1.42fr) minmax(110px,.78fr);grid-template-rows:repeat(var(--flow-rows),minmax(78px,auto));gap:10px 9px;align-items:center}.live-flow-branch{z-index:1;min-width:0;display:grid;align-items:center;gap:10px}.live-flow-branch.side-left{grid-column:1/3;grid-row:var(--flow-row);grid-template-columns:minmax(110px,.78fr) minmax(0,1.42fr)}.live-flow-branch.side-right{grid-column:4/6;grid-row:var(--flow-row);grid-template-columns:minmax(0,1.42fr) minmax(110px,.78fr)}.live-flow-hub{position:relative;z-index:1;grid-column:3;display:grid;align-items:center;justify-items:center;min-width:0}.live-flow-hub::before{content:"";position:absolute;z-index:-1;top:0;bottom:0;left:calc(50% - 2px);width:4px;border-radius:4px;background:#454b50}.live-flow-hub .live-flow-node{box-sizing:border-box;width:100%;justify-content:center;background:#202428;border-color:#596168}.live-flow-node{box-sizing:border-box}.live-flow-connection{min-width:0;display:grid;gap:5px}.live-flow-measure{min-width:0;display:flex;justify-content:space-between;align-items:baseline;gap:6px}.live-flow-measure small{min-width:0;overflow-wrap:anywhere;color:#c3c7ca;font-size:10px}.live-flow-measure strong{flex:none;color:#e7e9eb;font-size:12px;font-variant-numeric:tabular-nums;white-space:nowrap}.live-flow-track{position:relative;display:flex;align-items:center;justify-content:center;box-sizing:border-box;height:var(--flow-width,6px);min-height:4px;border:1px solid #596168;border-radius:999px;background:#454b50;overflow:hidden}.live-flow-track::after{content:"";position:absolute;inset:0;background-image:repeating-linear-gradient(110deg,transparent 0 9px,color-mix(in srgb,var(--flow-accent,#16c4df) 90%,white) 9px 13px,transparent 13px 22px);background-size:34px 100%;background-repeat:repeat-x;opacity:0;animation:live-flow-streaks var(--flow-duration,1.6s) linear infinite;will-change:background-position}.live-flow-track.forward::after,.live-flow-track.reverse::after{opacity:.92}.live-flow-track.reverse::after{animation-direction:reverse}.live-flow-arrow{position:absolute;z-index:1;color:#eef1f2;font-size:13px;line-height:1;text-shadow:0 1px 4px #111}.live-flow-track.idle{border-color:#626970;background:#51575d;box-shadow:none}.live-flow-track.idle .live-flow-arrow{color:#9ba1a6;text-shadow:none}.live-flow-track.unavailable{border-color:#454b50;background:repeating-linear-gradient(135deg,#363b40,#363b40 4px,#25292d 4px,#25292d 8px)}.live-flow-track.unavailable .live-flow-arrow{color:#858c91;text-shadow:none}.live-flow-status{color:var(--muted);font-size:10px}.live-flow-branch[data-flow="pv"],.live-flow-branch[data-flow="native-pv"]{--flow-accent:#56cf83}.live-flow-branch[data-flow="battery"]{--flow-accent:#f0c34e}.live-flow-branch[data-flow="grid"],.live-flow-branch[data-flow="grid-import"],.live-flow-branch[data-flow="grid-export"]{--flow-accent:#f06b6b}.live-flow-branch[data-flow="house"]{--flow-accent:#16c4df}.live-flow-branch[data-flow="offgrid"]{--flow-accent:#30c9d4}.live-flow-separate{margin-top:10px}.live-flow-branch.side-full{grid-template-columns:minmax(110px,.78fr) minmax(90px,1.42fr) minmax(110px,.78fr)}@keyframes live-flow-streaks{to{background-position:34px 0}}@media(max-width:760px){.live-flow-map{grid-template-columns:minmax(0,1fr);grid-template-rows:auto;gap:8px}.live-flow-hub{grid-column:1;grid-row:1!important}.live-flow-hub::before{display:none}.live-flow-branch.side-left,.live-flow-branch.side-right{grid-column:1;grid-row:auto;grid-template-columns:minmax(105px,.8fr) minmax(0,1.2fr)}.live-flow-branch.side-right{grid-template-columns:minmax(0,1.2fr) minmax(105px,.8fr)}.live-flow-branch.side-full{grid-template-columns:minmax(95px,.8fr) minmax(0,1.2fr) minmax(95px,.8fr)}}@media(prefers-reduced-motion:reduce){.live-flow-track::after{animation:none;will-change:auto;background-position:0 0}}
        /* Animate the repeated stripe layer with transforms to avoid per-frame background repaints. */
        .live-flow-track::after{left:-34px;right:auto;width:calc(100% + 34px);animation:none;will-change:auto}
        .live-flow-track.forward::after,.live-flow-track.reverse::after{animation:live-flow-streaks-transform var(--flow-duration,1.6s) linear infinite;will-change:transform}
        .live-flow-track.reverse::after{animation-direction:reverse}
        @keyframes live-flow-streaks-transform{to{transform:translateX(34px)}}
        @media(prefers-reduced-motion:reduce){.live-flow-track.forward::after,.live-flow-track.reverse::after{animation:none;will-change:auto;transform:none}}
        .live-flow-map{position:relative;display:block;isolation:isolate;width:100%;min-height:270px;aspect-ratio:2/1;max-height:390px;overflow:hidden;border:1px solid #343a40;border-radius:12px;background:radial-gradient(ellipse at 50% 56%,#1d3440 0,#202428 68%)}
        .flow-wires{position:absolute;inset:0;width:100%;height:100%;overflow:visible;pointer-events:none}
        .flow-wire-base,.flow-wire{fill:none;stroke-linecap:round;vector-effect:non-scaling-stroke}
        .flow-wire-base{stroke:#3a4248;stroke-width:8}
        .flow-wire{stroke:#555e64;stroke-width:3.2;stroke-dasharray:2 15;stroke-dashoffset:0;opacity:.5}
        .flow-wire[data-wire="pv"]{--wire-accent:#56cf83}.flow-wire[data-wire="grid"]{--wire-accent:#f06b6b}.flow-wire[data-wire="battery"]{--wire-accent:#f0c34e}
        .flow-wire.forward,.flow-wire.reverse{stroke:var(--wire-accent);opacity:.98;animation:energy-wire-flow 1.25s linear infinite}
        .flow-wire.reverse{animation-direction:reverse}
        .flow-wire.idle,.flow-wire.unavailable{animation:none;stroke:#596168;opacity:.58}
        @keyframes energy-wire-flow{to{stroke-dashoffset:-34}}
        .live-flow-map>.live-flow-node{position:absolute;z-index:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:5px;width:clamp(78px,18%,128px);height:auto;min-height:78px;aspect-ratio:1;padding:9px;border:1px solid color-mix(in srgb,var(--flow-accent,#16c4df) 68%,#41464b);border-radius:50%;background:radial-gradient(circle at 38% 28%,color-mix(in srgb,var(--flow-accent,#16c4df) 16%,#272b2f),#202428 72%);box-shadow:0 0 17px color-mix(in srgb,var(--flow-accent,#16c4df) 24%,transparent);text-align:center;transform:translate(-50%,-50%)}
        .live-flow-map>.live-flow-node>span{width:100%;min-width:0}.live-flow-map>.live-flow-node strong{font-size:clamp(11px,1.1vw,14px);line-height:1.15}.live-flow-map>.live-flow-node small{max-width:100%;color:#d0d6d9;font-size:clamp(9px,.85vw,11px);line-height:1.25;overflow-wrap:anywhere}
        .live-flow-map .live-flow-icon{width:clamp(20px,3vw,31px);height:clamp(20px,3vw,31px);margin-bottom:1px}
        .flow-node-pv{left:16%;top:18%;--flow-accent:#56cf83}.flow-node-grid{left:50%;top:18%;--flow-accent:#f06b6b}.flow-node-battery{left:84%;top:18%;--flow-accent:#f0c34e}.flow-node-house{left:50%;top:56%;--flow-accent:#16c4df}
        .live-flow-map>.flow-node-house{width:clamp(82px,16%,112px);min-height:82px}
        .live-flow-offgrid{margin-top:9px}.live-flow-note{margin:9px 2px 0}
        @media(max-width:620px){.live-flow-map{min-height:310px;aspect-ratio:1.25/1}.live-flow-map>.live-flow-node{width:clamp(76px,22%,96px);min-height:76px;padding:7px}.live-flow-map>.flow-node-house{width:clamp(78px,21%,90px);min-height:78px}.live-flow-map>.live-flow-node strong{font-size:11px}.live-flow-map>.live-flow-node small{font-size:9px}}
        @media(prefers-reduced-motion:reduce){.flow-wire.forward,.flow-wire.reverse{animation:none;stroke-dasharray:3 10;stroke-dashoffset:0}}
      </style>
      <main class="shell">
        <header><div><p class="sub">${this._escape(this._t("subtitle"))}</p><small class="versionline">${this._escape(this._t("version"))} ${this._escape(this._panel?.config?.integration_version || "—")} · ${this._escape(this._t("dashboard_version"))} ${this._escape(this._panel?.config?.dashboard_version || "—")}</small><a class="home-link" href="/" data-home>← ${this._escape(this._t("home_assistant"))}</a></div><div class="badge">● ${this._escape(this._t("live"))} ${this._escape(updated)}</div></header>
        <section class="section"><div class="section-head"><h2>${this._escape(this._t("energy_overview"))}</h2><small>${this._escape(this._t("live_values"))}</small></div><div class="metric-groups">${cards}</div></section>
        <nav aria-label="${this._escape(this._t("dashboard_views"))}"><button class="tab ${this._view === "overview" ? "active" : ""}" data-view="overview">${this._escape(this._t("overview"))}</button><button class="tab ${this._view === "energy" ? "active" : ""}" data-view="energy">${this._escape(this._t("energy"))}</button><button class="tab ${this._view === "economics" ? "active" : ""}" data-view="economics">${this._escape(this._t("economics"))}</button><button class="tab ${this._view === "controls" ? "active" : ""}" data-view="controls">${this._escape(this._t("controls"))}</button><button class="tab ${this._view === "settings" ? "active" : ""}" data-view="settings">${this._escape(this._t("menu_settings"))}</button></nav>
        ${activeContent}
        <p class="footer">${this._escape(this._t("footer"))}</p>
      </main>`;
    const template = document.createElement("template");
    if (this._renderStyleReady) {
      const styleEnd = markup.indexOf("</style>");
      template.innerHTML = markup.slice(styleEnd + "</style>".length);
      const currentShell = this.shadowRoot.querySelector(".shell");
      const nextShell = template.content.querySelector(".shell");
      if (currentShell && nextShell) this._patchRenderNode(currentShell, nextShell);
      else {
        template.innerHTML = markup;
        this._patchRenderChildren(this.shadowRoot, template.content);
      }
    } else {
      template.innerHTML = markup;
      this._patchRenderChildren(this.shadowRoot, template.content);
      this._renderStyleReady = true;
    }
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
  }

  _escape(value) {
    return String(value).replace(/[&<>"']/g, (char) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[char]);
  }
}

customElements.define("battery-smartflow-ai-hems-dashboard", BatterySmartFlowDashboard);
