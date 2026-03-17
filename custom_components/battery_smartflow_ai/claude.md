# Battery SmartFlow AI – Project Hub

🎯 **Zentrale Dokumentations-Übersicht für KI-gestützte Entwicklung und Debugging**

**Version:** 3.2.1
**Domain:** `battery_smartflow_ai`
**Zuletzt aktualisiert:** 2026-03-16

---

## 🤖 Claude Top-3 Anweisungen

**1. Vor Code lesen → Doc-Stack verwenden**
- Lesreihenfolge: ARCHITECTURE.md → CODE_MAP.md → DEBUG_NOTES.md → PATTERN_ANALYSIS.md
- Diese Docs enthalten **komprimiertes Wissen**, effizienter als Code-Scanning

**2. Debugging-Standard**
- DEBUG_NOTES.md durchsuchen (ähnliche Symptome?)
- PATTERN_ANALYSIS.md: 5 Heuristiken anwenden (State Guards, Persistence, Config, Hysterese, Dependencies)
- Dann Code untersuchen (mit CODE_MAP.md zur Navigation)

**3. State Management ist kritisch**
- 3 Ebenen: `_persist` (HA Store, restart-sicher) → `entry.options` (User) → Runtime Memory
- **Regel:** HA-Restart-Flags SOFORT in `_persist` dict schreiben
- Hysterese-Filter: `delay_off ≥ 300s` (Wallbox), `threshold = 80W` (hardcoded)

---

## 🚀 Schnelleinstieg

### **Projekt-Purpose**
Intelligente Home Assistant Integration zur optimierten Batterie-Steuerung mit:
- **Multi-Batterie-Koordination:** Zendure AC (2400W) + BYD DC (3600W)
- **Preis-Optimierung:** Günstige Fenster nutzen (z.B. GO Tariff 00–05)
- **PV-Integration:** Prognose-basierte Nachtladung (v3.2)
- **Decision-Engine:** 9-Rule-Prioritäts-System (Emergency → Peak → Arbitrage → Planning → Valley → PV → Summer → Manual → Standby)

### **Tech Stack**
- Python 3.11+
- Home Assistant Integration (DataUpdateCoordinator pattern)
- Modbus TCP (via SMA WR für BYD)
- No external APIs (local polling only)

---

## 📚 Dokumentationen (Verwendungszweck)

| Dokument | Zweck | Zielgruppe | Wann lesen |
|----------|-------|-----------|-----------|
| **[ARCHITECTURE.md](ARCHITECTURE.md)** | 🏗️ High-Level Design, Business Logic, Decision Rules, Night Charge | Architekten, Reviews | Vor größeren Änderungen |
| **[CODE_MAP.md](CODE_MAP.md)** | 🗺️ Datei-Struktur, Module, Verantwortlichkeiten, Datenfluss-Diagramm | Entwickler, Code-Navigation | Einstieg ins Projekt |
| **[ENTITY_REGISTRY.md](ENTITY_REGISTRY.md)** | 📋 Generated + Required Input Entities | Konfiguration, Integration | Setup Phase |
| **[DEBUG_NOTES.md](DEBUG_NOTES.md)** | 🐛 Dokumentierte Bugs, Root Causes, Diagnostic Checklisten | Debugging-Sessions | Fehler treten auf |
| **[PATTERN_ANALYSIS.md](PATTERN_ANALYSIS.md)** | 🧠 Failure Patterns, 5 Debugging-Heuristiken, Pre-Review Checklist | Code-Review, Debugging | Präventive Qualität |

---

## 🏗️ Architektur-Überblick

```
┌─────────────────────────────────────────────────┐
│  Home Assistant State Machine                   │
│  (Sensors: SoC, Grid, PV, Price, Forecast)    │
└────────────────┬────────────────────────────────┘
                 │ (read every 10s)
                 ▼
        ┌────────────────────────────┐
        │  ZendureSmartFlowCoordinator   │
        │  ─────────────────────────     │
        │  • _fetch_context()        │
        │  • _validate_inputs()      │
        │  • _run_decision_engine()  │
        │  • _manage_byd_night_charge()  │
        │  • _persist_context()      │
        └────────┬───────────────────┘
                 │
        ┌────────┴───────────┐
        ▼                    ▼
   ┌─────────────┐  ┌──────────────┐
   │Zendure AC   │  │BYD DC        │
   │2400W        │  │(via Modbus)  │
   │(select, #)  │  │(input_select)│
   └─────────────┘  └──────────────┘
```

**Kernkomponenten:**
1. **Coordinator** (1378 Zeilen) – Main Loop, State Management
2. **Decision Engine** (709 Zeilen) – Rule Evaluierung
3. **Entities** – Sensor, Number, Select, Switch (Platform Layer)
4. **Config Flow** – Setup UI + Validation

---

## 🔧 Häufige Aufgaben (Quick Links)

| Aufgabe | Gehe zu |
|---------|---------|
| 🐛 Bug Debuggen | DEBUG_NOTES.md → Symptom suchen → Heuristiken anwenden |
| 📝 Code-Review | PATTERN_ANALYSIS.md → Pre-Code-Review Checklist (#1–5) |
| 🔍 Architektur verstehen | CODE_MAP.md (30 min) → ARCHITECTURE.md (30 min) |
| ✨ Feature hinzufügen | ARCHITECTURE.md → Decision Engine/Config → PATTERN_ANALYSIS.md (#1–5) |
| 📊 Datenfluss verstehen | CODE_MAP.md → Datenfluss-Diagramm + Coordinator Loop |

---

## 📊 Projekt-Statistik

| Metrik | Wert |
|--------|------|
| **Gesamt Code** | 4131 Zeilen |
| **Größtes Modul** | coordinator.py (1378 Zeilen) |
| **Decision Rules** | 9 Rules (Emergency, Peak, Arbitrage, Planning, Valley, PV, Summer, Manual, Standby) |
| **Entity Types** | 4 (Sensor, Number, Select, Switch) |
| **Documented Bugs** | 10 (BUG-001 bis BUG-010) |
| **Update-Zyklus** | 10s (konstant) |
| **Nachtlad-Fenster** | 00:00–05:00 (GO Tariff) |
| **Hysterese-Filter** | 4+ (BYD charge/discharge, Wallbox) |

---

## ⚠️ Kritische Constraints

| Constraint | Impact | Workaround |
|-----------|--------|-----------|
| **State Persistence** | Flags müssen HA-Restart überleben | → Nutze `_persist` dict (HA Store) |
| **Hysterese-Stabilität** | Sensor-Rauschen bei Wallbox | → `delay_off ≥ 300s` (nicht 45s) |
| **Nachtlad-Fenster** | Zendure vor BYD laden | → Sequenzielle Berechnung (z erst, dann b) |
| **Input-Fehlertoleranz** | Wenn Preis offline → fallback nötig | → Heuristik #5 (Explicit Dependency) |
| **Config-Konsistenz** | Multiple Config-Quellen (const, options, Store) | → Heuristik #3 (Consolidate Config) |

---

## 🎯 Debugging-Heuristiken (Quick Reference)

Alle 5 Heuristiken in **PATTERN_ANALYSIS.md** mit Checklisten:

1. **"State Transitions Before Values"** – `if current != target` prüfen
2. **"Persistent-First State Design"** – State sofort in Store schreiben
3. **"Consolidate Config Sources"** – 1 immutable Config-Snapshot pro Zyklus
4. **"Sensor Noise = Parameter Tuning"** – Hysterese-Delay ≥ 2× Max-Noise
5. **"Explicit Dependency Resolution"** – Jede Rule: "funktioniert auch ohne..."

---

## 🧠 Memory Integration

Falls **claude-mem** verfügbar:
- `claude-mem:smart-explore` – Schnelle Funktions-Navigation
- `claude-mem:mem-search` – Debugging-Pattern Wiederverwendung

---

## 🔄 Update Policy

Wenn **Architektur oder Datenfluss ändert:**
- ARCHITECTURE.md aktualisieren
- CODE_MAP.md (Modul-Übersicht) anpassen
- PATTERN_ANALYSIS.md (falls neue Muster) erweitern
- DEBUG_NOTES.md (Zukunftsarbeit Section) aktualisieren

---

**Zuletzt aktualisiert:** 2026-03-16
**Erstellt für:** KI-gestützte Entwicklung & Debugging
**Maintain by:** Updating when architecture changes or new patterns emerge
