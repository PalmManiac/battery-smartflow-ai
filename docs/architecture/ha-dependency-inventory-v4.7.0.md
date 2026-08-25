# V4.7.0: Inventar der Home-Assistant-Abhängigkeiten

Status: Bestandsaufnahme für Issue #265  
Analysierter Stand: `main` bei `563e51c0e4184def3a17412e356d63e68d088078`  
Analyseumfang: `custom_components/battery_smartflow_ai/**/*.py` und die zugehörigen Tests

## Zweck und Abgrenzung

Dieses Dokument erfasst die tatsächlichen Home-Assistant-Kopplungen vor dem
Core-Refactoring. Es beschreibt den Istzustand und mögliche Grenzen für Issue
#266. Es führt keine Architekturänderung ein und bewertet kein bestehendes
Regelverhalten neu.

Als direkte HA-Abhängigkeit gelten insbesondere:

- Importe aus `homeassistant.*`
- Zugriffe auf `hass`, States, Services, Config Entries und Registries
- HA Storage und HA-Zeitfunktionen
- Entity-IDs oder HA-State-Objekte an einer fachlichen Modulgrenze
- HA-Schreibvorgänge innerhalb eines Core-Kandidaten

Eine Entity-ID in einer ausdrücklichen HA-Adapterklasse ist dabei kein Fehler.
Entscheidend ist, ob Fachlogik sie als Pflichtinformation benötigt.

## Kurzfazit

Die Codebasis ist weiter auf dem Weg zur Core-Trennung als die aktuelle
Verzeichnisstruktur vermuten lässt:

- Die meisten Rechen-, Strategie-, Preis-, Wirtschafts- und Regelmodule
  importieren Home Assistant nicht direkt.
- Die fachliche Ausgabekette
  `DecisionEngine -> StrategyIntent -> ModeArbiter -> PowerController -> DeviceCommand`
  ist bereits im Code vorhanden.
- `EconomicsEngine`, `MarketPrice`-Modelle, `AutomaticStrategy`,
  `RegulationPowerController`, `DeviceCommandBuilder` und zahlreiche
  Schutz-/Hilfsmodule sind bereits weitgehend deterministisch und neutral.
- Der zentrale Engpass ist `coordinator.py`: In 7.287 Zeilen bündelt er HA-I/O,
  Config, Snapshot-Aufbau, Persistenz, Zeit, Strategie-Orchestrierung,
  ChargeCommit, Hysteresen, Planung, Economics, Geräteausführung und Diagnose.
- Drei überschaubare Importkopplungen verhindern heute trotz neutraler
  Fach-APIs echte HA-freie Nutzung: `decision_engine.py` importiert eine
  Fachkonstante aus dem HA-gebundenen `const.py`; `mode_arbiter.py` und
  `learned_planning.py` verwenden `homeassistant.util.dt`.
- `forecast.py` mischt neutral brauchbare Forecast-Berechnung mit direktem
  Lesen von HA-Entities und HA-Zeitfunktionen und braucht deshalb eine klare
  Adaptergrenze.
- Die vorhandenen Fachtests laufen ohne gestartetes Home Assistant, installieren
  dafür aber in `tests/support.py` kleine `homeassistant.*`-Module als Stubs.
  Das belegt gute fachliche Testbarkeit, aber noch keine importierbare
  HA-unabhängige Core-Paketgrenze.

## Gemessene direkte Kopplung

Direkte `homeassistant.*`-Importe kommen in 11 Python-Dateien vor:

| Modul | Direkte HA-Abhängigkeit | Einordnung |
| --- | --- | --- |
| `__init__.py` | Lifecycle, Services, ConfigEntry | HA-Schicht behalten |
| `config_flow.py` | Config/Options Flow, Selektoren | HA-Schicht behalten |
| `const.py` | `homeassistant.const.Platform` | Gemischtes Modul aufteilen |
| `coordinator.py` | ConfigEntry, HomeAssistant, Store, DataUpdateCoordinator, `dt_util` | Stärkster Entkopplungskandidat |
| `diagnostics.py` | HomeAssistant, ConfigEntry | HA-Schicht behalten |
| `forecast.py` | HomeAssistant, `hass.states`, `dt_util` | HA-Lesen von Berechnung trennen |
| `learned_planning.py` | `dt_util` | Zeit-/Zeitzonenquelle neutralisieren |
| `mode_arbiter.py` | `dt_util` | UTC-Normalisierung neutralisieren |
| `number.py` | HA Number-Entity und ConfigEntry | HA-Schicht behalten |
| `select.py` | HA Select-Entity und ConfigEntry | HA-Schicht behalten |
| `sensor.py` | Sensor-Entity, Registry, DeviceInfo, `dt_util` | HA-Schicht behalten |

`ai_status.py` und `decision_engine.py` haben keinen direkten HA-Import, laden aber
Fachkonstanten aus `const.py`. `decision_engine.py` lädt beispielsweise
`MANUAL_CONST_DISCHARGE` aus `const.py`. Da `const.py` bereits beim Import
`homeassistant.const.Platform` lädt, sind beide Module transitiv an eine
vorhandene HA-Python-Installation oder einen Test-Stub gebunden.

## Tatsächlicher Laufzeitfluss

Der heutige Hauptpfad liegt fast vollständig in
`ZendureSmartFlowCoordinator._async_update_data()`:

1. Der Coordinator liest konfigurierte Entity-IDs über `hass.states`.
2. Er normalisiert Messwerte, Preise, Forecasts, Konfiguration und persistierte
   Laufzeitzustände.
3. Er aktualisiert Lernhistorie, Schutzstatus, Latches und ChargeCommit.
4. Er baut einen großen `DecisionContext` aus neutralen Python-Werten.
5. `DecisionEngine` erzeugt ein `DecisionResult`.
6. `strategy_adapter.py` übersetzt es in einen `StrategyIntent`.
7. `ModeArbiter` entscheidet die technische Modusfreigabe.
8. `RegulationPowerController` berechnet die Leistung.
9. `DeviceCommandBuilder` erzeugt einen `DeviceCommand`.
10. Der Coordinator führt den Befehl über `_set_ac_mode()`,
    `_set_input_limit()` und `_set_output_limit()` mit HA-Serviceaufrufen aus.
11. Ergebnis, Regelzustand, Economics, Diagnose und persistente Werte werden
    wieder im Coordinator zusammengeführt und gespeichert.

Damit existieren bereits neutrale Ein- und Ausgabebausteine. Die problematische
Kopplung liegt vor allem in ihrer Orchestrierung und Zustandsverwaltung.

## Modulmatrix der Core-Kandidaten

### Bereits weitgehend Core-fähig

Diese Module importieren Home Assistant nicht direkt und arbeiten überwiegend
mit Python-Dataclasses, Enums, Mappings und primitiven Werten:

| Bereich | Module | Verbleibende Hinweise |
| --- | --- | --- |
| Automatik | `automatic_strategy.py` | Große Parameterliste; später Snapshot-/Teilmodelle prüfen |
| Schutz | `battery_protection.py` | Zustandsübergänge sind neutral; Persistenz liegt im Coordinator |
| ChargeCommit-Helfer | `charge_commit_policy.py`, `strategy_state.py` | Kernmodell neutral; Erstellung, Speicherung und Lebenszyklus liegen stark im Coordinator |
| Ladequellen | `charge_source_allocator.py` | Neutraler Rechenkern |
| Wirtschaft | `economics.py`, `economic_efficiency.py`, `charge_economics.py` | Engine serialisiert neutral; Tageswechsel und HA-Store liegen im Coordinator |
| Marktpreise | `market_price/models.py`, `adapters.py`, `export_price.py`, `legacy_import.py`, `planning.py` | Provider-neutral; Quellenerfassung gesondert betrachten |
| Regelmodelle | `regulation_models.py` | Neutral, aber `metadata: dict[str, Any]` ist eine bewusst schwache Typgrenze |
| Regelung | `regulation_power_controller.py`, `power_controller.py`, `grid_history.py` | Neutral und mit explizitem Kontext testbar |
| Befehlsbildung | `device_command.py` | Keine Entity-ID/Services; technische Schreibflags gehören langfristig an die Backend-Grenze |
| Geräteprofile | `device_profiles.py` | Keine HA-Imports; derzeit untypisierte Dictionaries statt expliziter Capabilities |
| Strategieübersetzung | `strategy_adapter.py` | Neutraler Übergang von DecisionResult zu StrategyIntent |
| Sonstige Rechenhelfer | `command_effectiveness.py`, `price_currency.py`, `price_math.py`, `manual_standby.py`, `factor_display.py` | Neutral; Aufrufer/Schichtzuordnung in Issue #266 klären |

### Teilweise HA-gebunden

#### `decision_engine.py`

- Fachlich neutraler `DecisionContext` und deterministische Regeln.
- Keine Zugriffe auf `hass`, Services oder Entity-IDs.
- Transitive HA-Abhängigkeit über `const.py`.
- `DecisionContext` ist bereits ein Snapshot-Vorläufer, enthält aber viele lose
  Felder, ein untypisiertes Profil-Dictionary und `Any` für die Lernplanung.
- `ForecastSummary` stammt aus dem gemischten HA-/Berechnungsmodul
  `forecast.py`.

Einstufung: **weitgehend Core-fähig, kleine Importgrenze plus Modellkonsolidierung nötig**.

#### `mode_arbiter.py`

- Keine States, Services, Entity-IDs oder HA-Objekte.
- Nutzt `dt_util.as_utc()` an vier Stellen für Zeitvergleiche.
- Die aktuelle API erhält `now` bereits als Parameter; eine Clock ist für die
  Auswertung selbst daher nicht zwingend, wohl aber eine neutrale
  UTC-Normalisierung und später monotone Laufzeitsemantik für Cooldowns/Holds.

Einstufung: **fachlich Core-fähig, kleine HA-Zeitkopplung entfernen**.

#### `learned_planning.py`

- Planungsmodelle und Berechnungen sind neutral aufgebaut.
- Nutzt HA für lokale Zeitzone und `as_local()`.
- `now` wird den öffentlichen Berechnungen bereits übergeben.
- Zeitzone ist derzeit globale HA-Umgebung statt explizite Eingabe.

Einstufung: **Core-Kandidat mit expliziter Zeit-/Zeitzonengrenze**.

#### `forecast.py`

- `ForecastSummary`, Intervallauswertung und Outlook-Klassifizierung sind
  fachlich neutral nutzbar.
- Dasselbe Modul liest jedoch direkt `hass.states`, kennt Entity-IDs und
  konkrete Attributschemas (`detailedHourly`, `detailedForecast`).
- Es ruft `dt_util.utcnow()`, `parse_datetime()` und `as_local()` intern auf.
- Provider-/HA-Erfassung, Zeitnormalisierung und Forecast-Berechnung sind damit
  in einem Modul vermischt.

Einstufung: **teilweise bis stark HA-gebunden; neutralen Parser/Rechenkern von HA-Quelle trennen**.

#### `market_price/sources.py`

- Importiert Home Assistant nicht, definiert jedoch mit `StateLike`,
  `StateGetter` und `GenericStatePriceSource(entity_id, state_getter)` bewusst
  einen strukturellen HA-State-Adapter.
- Das Protocol hält die Abhängigkeit technisch klein, aber Entity-ID,
  `state`, `attributes`, `last_updated`, `unknown` und `unavailable` sind
  Plattformsemantik.
- `PriceSourceReading` und `StaticPriceSource` sind neutral.

Einstufung: **neutrales Quellprotokoll plus HA-spezifische Implementierung im selben Modul; später physisch trennen**.

#### `const.py`

- Mischt HA-Integrationsmetadaten (`Platform`, `PLATFORMS`, Config-Schlüssel)
  mit fachlichen Modi, Defaults, Status- und Regelkonstanten.
- Diese Mischung erzeugt unnötige transitive HA-Imports in Fachmodulen.
- Konfigurationsschlüssel und historische persistierte Werte dürfen bei einer
  späteren Aufteilung nicht umbenannt oder semantisch verändert werden.

Einstufung: **gemischte Grenzdatei; HA-Meta und stabile Fachkonstanten trennen**.

### Stark HA-gebunden und zugleich fachlich überladen

#### `coordinator.py`

Der Coordinator ist legitimerweise HA-gebunden, enthält aber zusätzlich große
Mengen Core-Kandidaten. Direkte HA-Aufgaben sind:

- `DataUpdateCoordinator`-Lifecycle
- `ConfigEntry` und `hass.config.currency`
- Entity-Auswahl und `hass.states.get`
- HA-Serviceaufrufe für Select-/Number-Entities
- `Store.async_load()` und `Store.async_save()`
- Executor-/Task-Anbindung und Update-Fehler
- HA-Zeitfunktionen und HA-Konfigurationsverzeichnis
- Zusammenstellung der Entity-/Sensor-Ausgabedaten

Im selben Objekt liegen derzeit fachliche oder plattformneutrale Kandidaten:

- Aufbau des heutigen Laufzeit-Snapshots/`DecisionContext`
- ChargeCommit-Lifecycle, Abbruch-, Preis- und Wartezustände
- PV-, Entlade-, Passthrough- und Zellschutz-Hysteresen
- Saisonerkennung
- Lernhistorie und Lernplanungszustände
- RegulationRuntimeState und CommandEffectivenessState
- Economics-/Energieakkumulator-Lebenszyklus und Tageswechsel
- Off-Grid- und Zusatzakku-Normalisierung
- Orchestrierung der vollständigen Strategie-/Regelkette

Die HA-Serviceaufrufe sind auf drei Methoden konzentriert, aber
`DeviceCommand` wird noch im Coordinator interpretiert. Sonderpfade wie
Safe-Idle und manueller Standby rufen diese Schreibmethoden teilweise direkt
auf. Eine spätere Backend-Grenze muss deshalb nicht nur den Normalpfad, sondern
auch Schutz-/Stopppfade abdecken.

Einstufung: **stark HA-gebunden; HA-Adapter behalten, fachliche Orchestrierung und Zustand schrittweise herauslösen**.

### Unverändert in der HA-Schicht belassen

- `__init__.py`: Setup, Unload, Migration und HA Services
- `config_flow.py`: Config Flow und Options Flow
- `sensor.py`: Sensorbeschreibungen, Registry, DeviceInfo und Darstellung
- `number.py`: HA Number-Entities und ConfigEntry-Updates
- `select.py`: HA Select-Entities
- `diagnostics.py`: HA-Diagnostics-Einstieg und Executor-Anbindung
- Übersetzungen, `services.yaml` und Manifest

Diese Module sind keine Entkopplungsfehler. Sie sollen später neutrale
Ergebnisse konsumieren, bleiben selbst aber plattformspezifisch.

## Inventar nach Kopplungsart

### State-Lesen und Entity-IDs

- Zentral in `coordinator.py` über `_state()`, `_attr()` und mehrere direkte
  `self.hass.states.get()`-Aufrufe.
- `forecast.py` liest Forecast-States und Attribute selbst.
- `market_price/sources.py` kapselt einen injizierten State-Getter, trägt aber
  Entity-ID und HA-State-Semantik in der Quellimplementierung.
- `SelectedEntities` ist korrekt als Adapterkonfiguration einzuordnen und darf
  nicht Teil eines zukünftigen Core-Snapshots werden.

### HA-Schreibvorgänge

- Direkte Geräte-Schreibvorgänge liegen in `coordinator.py`:
  `_set_ac_mode()`, `_set_input_limit()` und `_set_output_limit()`.
- Der Normalpfad nutzt zuvor `DeviceCommandBuilder`.
- Safe-Idle und Manual-Standby besitzen direkte Sonderpfade.
- Keine der untersuchten Strategy-, Arbiter-, Power- oder Economics-Klassen
  ruft HA Services selbst auf.

### Config Entries und Benutzerkonfiguration

- `coordinator.py` liest `entry.data` und `entry.options` beim Aufbau von
  Entities, Geräteprofil und Runtime-Settings.
- `config_flow.py`, `number.py`, `select.py` und `__init__.py` verwenden
  ConfigEntry erwartungsgemäß in der HA-Schicht.
- Fachmodule erhalten bereits Werte oder Dictionaries statt ConfigEntry.
- Das untypisierte `profile: dict` und große Settings-/Context-Parameter bleiben
  jedoch schwache Grenzen.

### Persistenz

- Die einzige HA-Storage-Instanz ist `Store` in `coordinator.py`.
- Ein einziges großes `_persist`-Dictionary mischt unter anderem:
  - UI-/Runtime-Modus
  - letzte Gerätesollwerte
  - ChargeCommit
  - Hysteresen und Holds
  - RegulationRuntimeState
  - CommandEffectiveness
  - Economics und Energieakkumulator
  - Lernplanung und Historie
  - Saison- und Schutzstatus
  - Debug-Status
- `EconomicsEngine` besitzt bereits neutrales `to_state()`/`from_state()`.
- `RegulationRuntimeState` und `ChargeCommitState` sind bereits neutrale
  Dataclasses; ihre Abbildung ins flache Store-Dictionary liegt im Coordinator.

Das ist die wichtigste Grundlage für das spätere StateStore-Issue: zuerst
Besitz und Schema der Teilzustände klären, dann einen Store abstrahieren. Das
bestehende Store-Schema muss wegen Upgrade-Kompatibilität lesbar bleiben.

### Zeit

- `coordinator.py` nutzt `dt_util` breit für aktuelle Zeit, UTC-/Lokalzeit,
  Parsing, Tageswechsel, Persistenz und Debug.
- `mode_arbiter.py` nutzt nur UTC-Normalisierung; `now` wird bereits injiziert.
- `learned_planning.py` hängt an der HA-Standardzeitzone.
- `forecast.py` liest aktuelle Zeit intern statt sie vollständig zu erhalten.
- Debug-Module nutzen unabhängig von HA `datetime.now(timezone.utc)`; sie sind
  Plattformcode und kein vorrangiger Core-Blocker.
- Es gibt derzeit keine erkennbare monotone Zeitquelle für Holds/Cooldowns;
  diese verwenden persistierbare Kalenderzeitstempel. Issue #271 sollte die
  gewünschte Semantik ausdrücklich festlegen, bevor Verhalten geändert wird.

### Registry, Diagnose und Logger

- Entity Registry wird nur in `sensor.py` verwendet und gehört zur HA-Schicht.
- DeviceInfo/Entity-Beschreibungen liegen in den Entity-Modulen.
- HA Diagnostics liegt in `diagnostics.py`; die Debug-Datenmodelle und der
  Exporter importieren HA nicht.
- Fachmodule nutzen reguläres Python-Logging oder keine Logger-Abhängigkeit;
  es wurde keine HA-spezifische Loggerkopplung im Strategy-/Economics-/Regelcode
  gefunden.

## Testbarkeitsbefund

Die bestehenden Tests zeigen zwei Ebenen:

1. Viele Fachmodule werden bereits direkt mit Dataclasses und festen
   Zeitstempeln getestet. Besonders Economics, MarketPrice, DecisionEngine,
   ModeArbiter, RegulationPowerController und DeviceCommand besitzen echte
   Unit-/Szenariotests ohne gestarteten Coordinator.
2. `tests/support.py` installiert vor diesen Imports minimale Stubs für
   `homeassistant.const`, `homeassistant.core`, `homeassistant.config_entries`
   und `homeassistant.util.dt`.

Damit ist die Fachlogik heute gut isoliert testbar, aber die Stubs kaschieren
die drei transitiven Zeit-/Const-Kopplungen. Ein belastbarer späterer
Core-Nachweis sollte ausgewählte Module in einem Prozess importieren und testen
können, in dem `homeassistant` überhaupt nicht in `sys.modules` installiert
ist.

## Belastbare Grenzen für Issue #266

Aus dem Istcode folgen diese Grenzen, ohne eine Zielstruktur vorwegzunehmen:

1. **Bestehende neutrale Modelle erhalten.** `DecisionContext`,
   `StrategyIntent`, Regulation-Modelle, `DeviceCommand`, MarketPrice und
   Economics-Snapshots sind Ausgangspunkte, keine Wegwerfstrukturen.
2. **Coordinator als Adapter und Composition Root behandeln.** Er darf HA
   kennen, sollte langfristig aber keine gesamte Fachdomäne besitzen.
3. **Inputs an einer Stelle normalisieren.** Entity-IDs und HA States enden vor
   einem neutralen Snapshot/Context.
4. **Outputs an einer Stelle ausführen.** Alle Normal-, Schutz- und Stopppfade
   laufen über dieselbe Backend-/Command-Grenze.
5. **Fachkonstanten aus HA-Meta lösen.** Dafür müssen keine Werte oder
   Config-Schlüssel geändert werden.
6. **Zeit zunächst explizit machen.** Vor einer Clock-Abstraktion unterscheiden,
   welche Zeit kalender-/zeitzonenabhängig und welche laufzeitbezogen ist.
7. **Persistenz nach Besitz aufteilen.** Erst Teilzustände und Migration
   definieren, dann StateStore einführen; keine blinde Umbenennung des heutigen
   Store-Schemas.
8. **Forecast und MarketPrice-Quellen als Adapter erkennen.** Provider-/HA-
   Parsing bleibt außerhalb der neutralen Modelle und Berechnungen.
9. **Keine neue Geräteabstraktion aus Annahmen bauen.** Der heutige
   Select-/Number-Servicepfad ist die einzige reale Backend-Implementierung und
   muss die Schnittstellenanforderungen liefern.

## Risiken für die weitere Reihenfolge

- Issue #266 sollte vor dem Verschieben von Dateien entscheiden, ob zunächst
  nur Importgrenzen oder bereits neue Pakete geschaffen werden. Reine
  Verzeichnisarbeit löst den Coordinator-Engpass nicht.
- Issue #267 und #268 überlappen mit dem vorhandenen `DecisionContext` und
  `StrategyContext`. Vor neuen Modellen ist zu klären, welche davon konsolidiert
  oder umbenannt werden; ein paralleler zweiter Snapshot wäre Doppelung.
- Issue #269 muss Safe-Idle und Manual-Standby zusammen mit dem normalen
  DeviceCommand-Pfad erfassen.
- Issue #270 muss das bestehende flache Persistenzschema migrierbar halten.
- Issue #271 darf Cooldown-/Hold-Semantik nicht unbeabsichtigt von
  restartfähiger Kalenderzeit auf rein monotone Zeit ändern.
- `forecast.py` und `market_price/sources.py` sollten nicht pauschal als Core
  verschoben werden; beide enthalten reale Adapteranteile.
- `device_profiles.py` ist neutral, aber Capability-Namen und Profilwerte sind
  noch Dictionaries. Eine Typisierung darf keine Profil-Fallbacks oder
  Regelparameter verändern.

## Abgleich mit den Akzeptanzkriterien von Issue #265

- Direkte HA-Abhängigkeiten im Fachcode: **identifiziert und nach Kopplungsart erfasst**.
- Wichtigste Core-Kandidaten: **in der Modulmatrix benannt**.
- HA-spezifische Bereiche: **von Core-Kandidaten getrennt eingeordnet**.
- Problematische Kopplungen: **Coordinator, Forecast, Zeit und `const.py` dokumentiert**.
- Grundlage für Folge-Issues: **konkrete Grenzen und Reihenfolgerisiken festgehalten**.
- Breaking Changes: **keine eingeführt; diese Änderung dokumentiert ausschließlich den Istzustand**.

## Nicht Teil dieser Bestandsaufnahme

- keine neue Paket-/Verzeichnisstruktur
- kein RuntimeSnapshot- oder StateStore-Code
- keine Clock- oder DeviceBackend-Schnittstelle
- keine Änderung an Strategy, Regelung, Profilen oder Persistenz
- keine Entity-ID-, Config- oder Store-Migration
- keine neue Geräte- oder Herstellerunterstützung
