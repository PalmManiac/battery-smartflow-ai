# CODE_MAP – Battery SmartFlow AI Integration

Strukturelle Übersicht der Integration mit Datei-Hierarchie, Verantwortlichkeiten und Datenfluss.

---

## Projekt-Übersicht

**Integration:** `battery_smartflow_ai` (Home Assistant Custom Component)
**Zweck:** Intelligente Batterie-Steuerung mit PV-Prognose, Preisoptimierung und Multiband-Koordination
**Sprache:** Python 3.11+
**Version:** 3.2.1
**Größe:** 4131 Zeilen Code über 13 Dateien

---

## Datei-Architektur

```
battery_smartflow_ai/
├── __init__.py                    (56 Zeilen) – Entry Point, Setup/Unload
├── coordinator.py                 (1378)      – Zentral-Koordinator, Daten-Management
├── decision_engine.py             (709)       – AI-Decision-Engine, Rule-Evaluierung
├── config_flow.py                 (532)       – Konfiguration UI (Entities, Settings)
├── sensor.py                      (354)       – Sensor-Entities (Status, Profit, etc.)
├── number.py                      (307)       – Number-Entities (SoC-Grenzen, Verbrauch)
├── const.py                       (229)       – Konstanten (Keys, Defaults, Schwellen)
├── power_controller.py            (123)       – Delta-Discharge Algorithmus (legacyV2)
├── ai_logic.py                    (147)       – AI-Logik für Entscheidungen
├── select.py                      (122)       – Select-Entities (Mode-Schalter)
├── switch.py                      (85)        – Switch-Entities (Ein/Aus)
├── device_profiles.py             (67)        – Geräte-Profile (Hardcoded)
└── constants.py                   (22)        – Zusatz-Konstanten

manifest.json                              – Metadaten, Version, Abhängigkeiten
docs/
├── HLD-BatterySmartFlowAi-v3.2.md        – High-Level Design (aktuell)
└── HLD-BatterySmartFlowAI.md             – High-Level Design (alt)
```

---

## Module – Schnell-Navigation

| Modul | Zeilen | Zweck | Siehe auch |
|-------|--------|-------|-----------|
| **coordinator.py** | 1378 | 10s-Loop, Input-Validierung, Decision-Engine-Aufruf, State-Persistierung | ARCHITECTURE.md |
| **decision_engine.py** | 709 | 9-Rule-Evaluierung (Emergency → Peak → … → Standby) | ARCHITECTURE.md |
| **config_flow.py** | 532 | Setup UI, Entity-Mapping, Runtime-Optionen | ENTITY_REGISTRY.md |
| **sensor.py** | 354 | Generated Sensor-Entities (Status, Profit, Nachtlad-Plan) | ENTITY_REGISTRY.md |
| **number.py** | 307 | Generated Number-Entities (SoC, Limits, Schwellen, Verbrauch) | ENTITY_REGISTRY.md |
| **const.py** | 229 | Config Keys, Settings, Defaults, Enums | Code lesen |
| **ai_logic.py** | 147 | Preis-Analyse, PV-Prognose, Fenster-Detection | Code lesen |
| **power_controller.py** | 123 | Delta-Discharge/Charge (legacy V2.0.4 Port) | Code lesen |
| **select.py** | 122 | Generated Select-Entities (ai_mode, etc.) | ENTITY_REGISTRY.md |
| **switch.py** | 85 | Generated Switch-Entity (pv_nachtladung) | ENTITY_REGISTRY.md |
| **device_profiles.py** | 67 | Hardware-Profile (Zendure, BYD) | Code lesen |
| **__init__.py** | 56 | HA Integration Lifecycle (setup, unload, migrate) | Code lesen |
| **constants.py** | 22 | Zusatz-Konstanten | Code lesen |

---

## Datenfluss – Update-Loop

```
[10s Timer] ─────────────────────────────────┐
                                             │
                                             ▼
                        ZendureSmartFlowCoordinator
                              │
                              │ _async_update_data()
                              │
                    ┌─────────┼─────────┐
                    │         │         │
                    ▼         ▼         ▼
            _fetch_context() ─ Input-Sensoren lesen
                    │         ─ HA Store laden
                    │         ─ Koordinaten berechnen
                    │
                    ▼
           _validate_inputs()
                    │
            (alle Sensoren ok?)
                    │
        ┌───────────┴───────────┐
        │ (JA)                  │ (NEIN)
        ▼                       ▼
   _run_decision_engine()   Status=sensor_invalid
        │                   (STOP)
        │
        ▼
   DecisionEngine.evaluate()
        │
        ├─ Rule #1 (Emergency) matches? → Rule.execute()
        ├─ Rule #2 (Peak) matches?
        ├─ Rule #3 (Arbitrage) matches?
        ├─ Rule #4 (Planning) matches?
        ├─ Rule #5 (Valley) matches?
        ├─ Rule #6 (PV) matches?
        ├─ Rule #7 (Summer) matches?
        ├─ Rule #8 (Manual) matches?
        └─ Rule #9 (Standby) DEFAULT
        │
        ▼
   Aktion: (charge W | discharge W | idle)
        │
        ├─ _manage_byd_night_charge()     [Special: 00–05 Fenster]
        ├─ _manage_zendure()              [AC-Mode, Limits]
        ├─ _manage_wallbox()              [Hysterese]
        │
        ▼
   PowerController.delta_discharge()
        │ (oder delta_charge)
        │
        ▼
   Output-Leistung (W) an HA Services
        │
        ▼
   _persist_context()
        │ (State → HA Store)
        │
        ▼
   Sensoren aktualisieren
        │
        ▼
   [Wait 10s] ──────── Loop ────────┐
                                     │
                                     └─→ [Back to Timer]
```

---

## Entity-Typen

Detaillierte Dokumentation → **ENTITY_REGISTRY.md**

Kurz: Sensor, Number, Select, Switch (alle via `CoordinatorEntity`)

---

## Integration mit claude-mem

```
claude-mem:smart-explore
  └─ Für schnelle Funktions-Navigation
     (z.B. "Finde alle Stellen wo profit aktualisiert wird")

claude-mem:mem-search
  └─ Für Wiederverwendung von Debugging-Patterns
     (z.B. "Hatten wir schon ein ähnliches Persist-Problem?")
```

---

## Weiterführende Dokumente

- **ARCHITECTURE.md** – Detaillierte Architektur & Decision-Engine
- **DEBUG_NOTES.md** – Dokumentierte Bugs & Fixes
- **PATTERN_ANALYSIS.md** – Recurring Failure Patterns & Heuristiken
- **HLD-BatterySmartFlowAi-v3.2.md** – High-Level Design (aktuell)

---

**Zuletzt aktualisiert:** 2026-03-16
**Version:** 3.2.1
