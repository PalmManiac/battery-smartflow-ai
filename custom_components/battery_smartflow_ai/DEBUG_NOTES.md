# DEBUG_NOTES – Battery SmartFlow AI

Protokoll identifizierter Bugs, Root Causes, Fixes und Learnings. **Einträge in umgekehrter chronologischer Reihenfolge (neueste zuerst).**

---

## Inhaltsverzeichnis

1. [Bug-Einträge](#bug-einträge)
2. [Diagnostic Signals](#diagnostic-signals)
3. [Diagnostic Checklists](#diagnostic-checklists)
4. [Search Index](#search-index)
5. [Zukunftsarbeit](#zukunftsarbeit)

---

## Bug-Einträge

### BUG-010: BYD-Entladeschutz ("Akku Pause") überlebt HA-Neustart nicht
**Symptom:** BYD-Modus kehrt zu "Akku automatisch" zurück nach HA-Neustart.

**Root Cause:** `_byd_discharge_paused` war nur im RAM, nicht in HA Store persistiert.

**Fix:** `_byd_discharge_paused` in `_persist` dict + Init aus Store laden. **Files:** `coordinator.py`

---

### BUG-009: Wallbox-Hysterese verursacht vorzeitiges Lade-Stopp
**Symptom:** Wallbox stoppt nach 5 Min, schnelle An-Aus-Zyklen in Logs.

**Root Cause:** Wallbox-Power-Spiken (~50W), Hysterese `delay_off = 45s` zu kurz.

**Fix:** `delay_off_s = 300` (5 min) erhöht. **Files:** `coordinator.py`

---

### BUG-008: PV-Nachtlad-Ziel-SoC ignoriert PV-Prognose
**Symptom:** BYD-Ziel-SoC immer 100%, ignoriert PV-Prognose.

**Root Cause:** `pv_for_battery` nutzte hardcodiertes 5 kWh statt `daytime_consumption_w`.

**Fix:** Formel: `pv_for_battery = max(0, pv_forecast_kwh - daytime_consumption_w*10/1000)`. **Files:** `coordinator.py`

---

### BUG-007: ArbitrageRule verursacht teure Entladung
**Symptom:** Batterie entlädt um 06:00 (teuer) statt bis 05:00 Günstig-Fenster zu nutzen.

**Root Cause:** ArbitrageRule Priorität zu hoch, vor PlanningRule.

**Fix:** ArbitrageRule nach PlanningRule verschieben + Margin 15% → 27%. **Files:** `decision_engine.py`, `const.py`

---

### BUG-006: BYD-Modbus-Modus-Schreiben alle 10s (Spam)
**Symptom:** Wiederholte `"Akku Pause"` Writes zu Modbus alle 10s.

**Root Cause:** Kein State-Guard, Modus wird jeden Zyklus geschrieben.

**Fix:** `if current_mode != target_mode` Guard + Flag tracken. Writes: 8640/Tag → 2/Nacht. **Files:** `coordinator.py`

---

### BUG-005: Nachtlad-Status bleibt "charging" nach 05:00
**Symptom:** `night_charge_status` aktualisiert nicht nach Fenster-Ende.

**Root Cause:** Cleanup-Logik fehlte nach 05:00.

**Fix:** Fenster-Austritt: `if now >= 05:00 and _byd_night_active` → Modus reset + Status `"inactive"`. **Files:** `coordinator.py`, `sensor.py`

---

### BUG-004: Zendure-Priorität vor BYD nicht erzwungen
**Symptom:** BYD lädt zu 100% während Zendure bei 70%.

**Root Cause:** Nachtlad-Formel berechnete beide unabhängig.

**Fix:** Sequenzielle Formel: `z_charge = min(z_gap, need)`, dann `byd = max(0, need - z_charge)`. **Files:** `coordinator.py`

---

### BUG-003: Preis offline → alles offline
**Symptom:** Wenn Octopus-Preis offline, `ai_status = standby` auch mit PV-Überschuss.

**Root Cause:** Price-Check blockiert alle Rules.

**Fix:** PvRule vor Price-Rules evaluieren. Skip nur price-abhängige Rules wenn price = None. **Files:** `decision_engine.py`

---

### BUG-002: Hysterese-Fluttern nach HA-Start
**Symptom:** Erste 10 Min: Wallbox An/Aus-Zyklen, BYD-Modus springt.

**Root Cause:** `_pending_since` nicht initialisiert, falsche Transition erkannt.

**Fix:** `_pending_since = None` init + `is None` Guard vor Timedelta-Vergleich. **Files:** `coordinator.py`

---

### BUG-001: Gewinn-Berechnung zählt doppelt
**Symptom:** `profit_eur` springt zu 100€ nach 30 Min Entladung.

**Root Cause:** `discharge_kwh` war kumulativ statt Delta pro Zyklus.

**Fix:** Delta-Tracking: `_last_discharge_kwh` pro Zyklus, nur `(current - last) × price` addieren. **Files:** `coordinator.py`

---

**Entitäts-Details → siehe ENTITY_REGISTRY.md**

---

## Diagnostic Checklists

### Checklist: Batterie lädt nachts (00–05) nicht
**Symptom:** BYD/Zendure laden nicht während Günstig-Fenster.

- [ ] Coordinator läuft? (`sensor.battery_smartflow_ai_status` = `ok`)
- [ ] BYD-Modus-Entität konfiguriert? (`input_select.akku_steuerung_sma_wr` aktualisiert?)
- [ ] Zeit im Fenster? (00:00 ≤ now < 05:00)
- [ ] PV-Prognose vorhanden?
- [ ] Logs: Grep nach `_manage_byd_night_charge`

---

### Checklist: Wallbox stoppt Laden vorzeitig
**Symptom:** Wallbox stoppt nach 5 min, obwohl Auto angesteckt.

- [ ] Hysterese-Delay ≥ 300s?
- [ ] Nach HA-Start 1–2 Min warten vor Test?
- [ ] `sensor.wallbox_power` auf Spikes prüfen?
- [ ] Netzfluss stabil? (`sensor.grid_power` fluktuiert?)

---

### Checklist: Entscheidungs-Engine gibt falsche Aktion
**Symptom:** `sensor.battery_smartflow_ai_recommendation` = `standby` obwohl Ladung nötig.

- [ ] Alle Input-Sensoren gültig? (`sensor.battery_smartflow_ai_status` = `ok`)
- [ ] SoC innerhalb Grenzen?
- [ ] Emergency triggered? (SoC ≤ `emergency_soc`)
- [ ] Modus = `manual`? (überschreibt alles)
- [ ] Logs für Rule-Evaluierung aktiviert? (`_LOGGER.debug()` in `decision_engine.py`)

---

**Zuletzt aktualisiert:** 2026-03-16
