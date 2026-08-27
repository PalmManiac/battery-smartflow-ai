# Clock-Grenze in V4.7.0

Issue #271 zentralisiert die Zeitbeschaffung für Core-Logik, ohne die Semantik
bereits persistierter Zeitstempel zu verändern.

## Laufzeitpfad

```text
Coordinator
    |
    v
core.ports.Clock
    |-- utc_now()    -> restart-feste Fach- und Persistenzzeit
    |-- local_now()  -> lokale Kalender-, Preis- und Lernplanung
    `-- monotonic()  -> ausschließlich prozesslokale Laufzeitabstände
    |
    v
HomeAssistantClock / SystemClock / TestClock
```

`HomeAssistantClock` übernimmt die in Home Assistant konfigurierte Zeitzone.
`SystemClock` ist die plattformunabhängige Produktionsimplementierung.
`TestClock` kann UTC-Zeit, lokale Zeit und monotone Laufzeit ohne reales Warten
deterministisch fortschreiben.

## Inventar und Zeitsemantik

| Bereich | Quelle im Core | Semantik | Begründung |
| --- | --- | --- | --- |
| DecisionEngine und RuntimeSnapshot | übergebenes `now` | aware UTC/Kalenderzeit | Preise, Forecasts und Deadlines benötigen absolute Vergleichbarkeit |
| ChargeCommit | `started_at`, `latest_start`, `deadline`, `valid_until` | UTC/Kalenderzeit, persistiert | Bindungen müssen nach einem Neustart korrekt weiterlaufen oder ablaufen |
| Lern- und Ladeplanung | aus `now` abgeleitete lokale Zeit | lokale Kalenderzeit | Wochentag, Tageszeit, Morgenlast und Preisfenster sind zeitzonenabhängig |
| Forecast | `Clock.local_now()` | lokale Kalenderzeit | Heute/Morgen und 3h-/6h-Fenster folgen der HA-Zeitzone |
| Economics und Energieakkumulator | übergebenes `sampled_at` | aware Kalenderzeit | Tageswechsel und anteilige Zuordnung über Mitternacht müssen deterministisch bleiben |
| ModeArbiter und Regulation | persistierte UTC-Zeitstempel | UTC/Kalenderzeit | Cooldowns, Latches und Holds werden heute gespeichert und müssen Neustarts überleben |
| CommandEffectiveness | persistiertes `last_retry_at` | UTC/Kalenderzeit | Wiederholschutz darf nach einem Neustart nicht sofort umgangen werden |
| Debug-Aufzeichnung | vom Coordinator übergebenes UTC-`now` | UTC/Kalenderzeit | Exportzeitfenster müssen als reale Zeitstempel verständlich bleiben |
| künftige rein prozesslokale Intervalle | `Clock.monotonic()` | monoton | unempfindlich gegen Systemzeitkorrekturen; niemals persistieren |

## Bewusste Entscheidung zu Cooldowns und Holds

Monotone Zeit wäre für einen ausschließlich im Prozess lebenden Cooldown ideal.
Die vorhandenen ModeArbiter-, Regulation- und CommandEffectiveness-Zeitpunkte
liegen jedoch im StateStore. Ein Wechsel auf monotone Sekunden würde ihre
Bedeutung bei einem Neustart zerstören, weil der monotone Zähler dann neu
beginnt. #271 erhält deshalb für diese vorhandenen Zustände bewusst die
UTC-Kalenderzeit.

`Clock.monotonic()` ist für neue oder später explizit als nicht persistent
klassifizierte Laufzeitintervalle verfügbar. Eine spätere Umstellung eines
bestehenden Zustands erfordert zuerst eine eigene Persistenz- und
Restart-Entscheidung.

## Deterministische Tests

Mit `TestClock` können Tests gezielt:

- Preis- und Forecast-Slots wechseln,
- einen lokalen Tageswechsel auslösen,
- Commit-Deadlines und Latest-Start erreichen,
- Holds und Cooldowns vor und nach Ablauf prüfen,
- Economics-Zeit über Mitternacht fortschreiben,
- monotone Laufzeit unabhängig von einer Kalenderzeitkorrektur prüfen.

Die fachlichen Komponenten behalten ihre bereits vorhandenen expliziten
`now`-/`sampled_at`-Parameter. Der Coordinator beschafft den Zeitpunkt einmal
über die Clock und reicht ihn weiter. Dadurch bleiben die Modelle frei von
Home-Assistant- und globalen Systemzeitfunktionen.

## Abgrenzung

#271 ändert keine Zeitdauer, keinen Deadline-Algorithmus und kein gespeichertes
Zeitformat. Direkte Zeit-Fallbacks in reinem Debug-Exportcode sind keine
Core-Entscheidungsquelle; der produktive Debugpfad erhält seine Zeit ebenfalls
vom Coordinator. Eine künftige vollständige Adapterzerlegung kann diese
Darstellungs-Fallbacks separat verschieben.
