# Pattern Analysis – Recurring Failure Modes & Debugging Heuristics

Systematische Analyse der 10 dokumentierten Bugs zur Identifikation übergeordneter Fehlermuster und höherstufiger Debugging-Heuristiken.

---

## Fehlerverteilung nach Root-Cause-Kategorie

```
State Management & Persistence     40% (4 Bugs: BUG-010, BUG-002, BUG-005, BUG-001)
├─ Runtime-State verloren nach Restart
├─ Initialization unvollständig
├─ State-Lifecycle nicht definiert
└─ Tracking-Logik (delta vs. cumulative)

State-Guards & Idempotenz          30% (3 Bugs: BUG-006, BUG-004, BUG-005)
├─ Wiederholte Writes ohne Bedingung
├─ Priorität nicht durchgesetzt
└─ Cleanup-Logik fehlte

Config-Konsistenz & Formeln        30% (3 Bugs: BUG-008, BUG-001, BUG-004)
├─ Config nicht in Formel integriert
├─ Delta-Tracking nicht konsistent
└─ Sequenzielle Abhängigkeiten ignoriert

Sensor-Stabilität & Parameter      20% (2 Bugs: BUG-009, BUG-002)
├─ Hysterese-Parameter zu aggressiv
└─ State-Initialization unvollständig

Rule-Priority & Fallback           20% (2 Bugs: BUG-007, BUG-003)
├─ Rule-Reihenfolge unzureichend
└─ Fallback-Logik fehlte
```

---

## Übergeordnete Fehlermuster (Kurzform)

| Pattern | Problem | Bug-IDs | Beispiel |
|---------|---------|---------|----------|
| **State Fragmentation** | State an 3+ Stellen (const, options, Store, RAM) | BUG-010, 005, 001, 002 | `_byd_discharge_paused` nur im RAM → nach Restart weg |
| **Missing State-Guards** | Schreiben ohne `if current != target` | BUG-006, 004, 005 | Modbus 8640×/Tag statt 2×/Nacht |
| **Config/Formula Mismatch** | User-Config nicht in Formel | BUG-008, 001, 004 | `pv = 5 kWh hardcoded` statt User-Config |
| **Sensor Noise Underestimation** | Hysterese zu kurz, Init incomplete | BUG-009, 002 | `delay_off = 45s` statt 300s → Fluttern |
| **Rule Priority Breaks** | Falsche Rule-Reihenfolge, kein Fallback | BUG-007, 003 | ArbitrageRule vor PlanningRule → zu früh entladen |

---

## 5 Debugging-Heuristiken (Kurzform)

### #1: "State Transitions Before Values"
**Aussage:** Immer `if current_state != desired_state:` vor Write-Op.

**Checkliste:** Logs zeigen wiederholte Writes desselben Wertes? → Heuristik #1

**Bugs:** BUG-006, BUG-004, BUG-005

---

### #2: "Persistent-First State Design"
**Aussage:** State, der HA-Restart überleben muss → sofort in `_persist` dict.

**Checkliste:** Flag überleben HA-Restart? NEIN → `_persist`

**Bugs:** BUG-010, BUG-002, BUG-001

---

### #3: "Consolidate Config Sources"
**Aussage:** Config-Snapshot auf Init erstellen, nur diesen nutzen (nicht const + options + Store).

**Checkliste:** Config aus 3+ Quellen? → Race-Condition

**Bugs:** BUG-008, BUG-001, BUG-004

---

### #4: "Sensor Noise = Parameter Tuning"
**Aussage:** Hysterese-Delay ≥ 2× Max-Sensor-Noise. Nach HA-Start: Init-Warmup brauchen.

**Checkliste:** Sensor flattert? → `delay_off` erhöhen. Nach Start instabil? → `_pending_since` init

**Bugs:** BUG-009, BUG-002

---

### #5: "Explicit Dependency Resolution"
**Aussage:** Jede Rule: dokumentieren "funktioniert auch ohne Input X?". Wenn NEIN → Fallback einbauen.

**Checkliste:** Wenn Tibber offline → welche Rules funktionieren? (min. PV + Manual)

**Bugs:** BUG-007, BUG-003

---

**Zuletzt aktualisiert:** 2026-03-16
