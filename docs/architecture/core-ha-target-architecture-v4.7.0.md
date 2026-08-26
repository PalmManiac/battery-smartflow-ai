# V4.7.0: Zielarchitektur für Core und Home-Assistant-Adapter

- Status: Architekturentscheidung für Issue #266
- Basis: `main` bei `aeca37faea9f62d73f80ed0a93ee51e747e31dbc`
- Release-Basis: Tag `4.6.0` bei `9b2ae4f4e04b0b0624dbbcf85dbe86664f687162`
- Vorarbeit: `ha-dependency-inventory-v4.7.0.md`
- Scope: Zielgrenzen und Migrationsroute, keine Laufzeitänderung

## Entscheidung in Kürze

V4.7 entwickelt BSFAI innerhalb der bestehenden Home-Assistant-Integration zu
einer Architektur mit drei klaren Verantwortungsbereichen:

1. **Home-Assistant-Schicht** für Lifecycle, Config Entries, Entities,
   Registries, Services, Diagnostics und Update-Takt.
2. **Home-Assistant-Adapter** für normalisierte Eingaben, Persistenz, Zeit und
   die Ausführung neutraler Gerätebefehle über den heutigen Entity-Pfad.
3. **BSFAI Core** für Strategie, Planung, Schutz, Regelung, Marktpreise,
   Wirtschaft, Profile, neutrale Zustände und neutrale Befehle.

Der Coordinator bleibt zunächst Home-Assistant-`DataUpdateCoordinator` und
Composition Root. Er verdrahtet Adapter und Core, soll aber schrittweise
fachliche Zuständigkeiten abgeben.

V4.7 erzeugt weder ein separates Installationspaket noch einen Standalone-
Controller. Es führt auch kein neues Gerätebackend ein. Die physische
Paketstruktur wird nur dann erweitert, wenn ein nachfolgendes Issue tatsächlich
Code an die neue Grenze verschiebt.

## Zielbild

```text
Home Assistant
  Lifecycle · ConfigEntry · Entities · Services · Registries · Diagnostics
                              |
                              v
Home-Assistant-Adapter
  Snapshot-Aufbau · Quellen · HAStateStore · HAClock · HAEntityDeviceBackend
                              |
                  neutrale Modelle und Ports
                              |
                              v
BSFAI Core
  Strategy · Planning · Protection · Regulation · MarketPrice · Economics
  DeviceProfile · DeviceCapabilities · StrategyIntent · DeviceCommand
```

Die erlaubte Import- und Aufrufrichtung ist:

```text
Home-Assistant-Schicht  --->  Home-Assistant-Adapter  --->  Core
          |                                                  ^
          +--------------------------------------------------+

Core  -X->  Home-Assistant-Adapter
Core  -X->  Home-Assistant-Schicht
```

Der Core definiert neutrale Modelle und bei tatsächlichem Bedarf kleine Ports.
Die Adapter implementieren diese Ports. Nur die Home-Assistant-Schicht erzeugt
die konkreten Implementierungen und verbindet sie mit dem Core.

## Bewusste Grenzen von V4.7

Die Zielarchitektur bedeutet ausdrücklich nicht:

- kein zweites Produkt neben der Custom Integration
- kein PyPI-Paket und keine neue Release-Artefaktstruktur
- kein Docker-, Linux- oder Standalone-Runtime
- kein neuer Hersteller und kein neues Batterieprofil
- kein Zendure-Direct-, MQTT- oder Modbus-Backend
- keine Multi-Battery-Koordination
- keine neue Strategie und kein Regler-Neutuning
- kein kompletter Coordinator-Rewrite
- keine sofortige Verschiebung aller neutral wirkenden Dateien

Die Architektur ist auf spätere Erweiterbarkeit ausgerichtet, wird aber nur an
heutigen Kopplungen und dem heutigen Gerätepfad konkretisiert.

## Schichten und Verantwortlichkeiten

### Home-Assistant-Schicht

Diese Schicht kennt Home Assistant vollständig und darf HA-APIs direkt nutzen.

Verantwortlich für:

- `async_setup`, `async_setup_entry`, Unload und Migration
- Config Flow und Options Flow
- Config Entries und HA-spezifische Validierung
- Sensor-, Number-, Select- und spätere Button-Entities
- Entity Registry und Device Registry
- DeviceInfo, Device Classes, State Classes und Entity Categories
- Übersetzungen und HA-Anzeigenamen
- HA Services und ServiceCall
- DataUpdateCoordinator-Lifecycle und Update-Planung
- Home-Assistant-Diagnostics und Debug-Download
- HA-Verfügbarkeit und Darstellung von unavailable/unknown
- Mapping neutraler Core-Ergebnisse auf Entity-Zustände und Attribute

Bleibt am Paketanfang:

- `__init__.py`
- `config_flow.py`
- `coordinator.py`
- `sensor.py`
- `number.py`
- `select.py`
- `diagnostics.py`
- `manifest.json`, `services.yaml`, Übersetzungen und Strings

Diese Dateien werden nicht künstlich unter `ha/entities/` verschoben. Home
Assistant erwartet Config Flow und Plattformmodule an ihren heutigen
Importpfaden. Ihre Lage ist daher Teil der Integrationsschnittstelle.

### Home-Assistant-Adapter

Adapter übersetzen zwischen HA-Objekten und neutralen Core-Verträgen. Sie
enthalten keine Strategieentscheidung.

Verantwortlich für:

- Lesen der konfigurierten HA-Entities
- Unterscheiden von fehlend, unknown, unavailable, ungültig und gültig
- Einheiten-, Vorzeichen- und Werte-Normalisierung
- Aufbau eines neutralen RuntimeSnapshot
- Provider-/Entity-Parsing für Forecasts und Marktpreise
- Abbildung des bestehenden HA-Store-Schemas auf neutrale Teilzustände
- Bereitstellung von Kalenderzeit, Zeitzone und monotoner Laufzeit
- Ausführung eines neutralen DeviceCommand über Select-/Number-Services
- Entity-Verfügbarkeit, Servicefehler und HA-spezifische Retries
- Abbildung neutraler Fehler auf `UpdateFailed` oder HA-Verfügbarkeit

Adapter dürfen Home Assistant und Core-Modelle importieren. Sie dürfen weder
Wirtschaftlichkeit entscheiden noch Zielmodus oder Zielleistung strategisch
bestimmen.

### BSFAI Core

Der Core enthält fachliche und technische Batterieentscheidungen, aber keine
Plattformdetails.

Verantwortlich für:

- Decision Engine und Regeln
- AutomaticStrategy
- StrategyIntent und ChargeCommit
- Schutz- und Blockierungslogik
- ModeArbiter
- RegulationPowerController und Near-Zero-Regelung
- ChargeSourceAllocator
- Lernplanung und klassische Ladeplanung
- MarketPrice-Modelle, Normalisierung und Planungssicht
- EconomicsEngine und Energieakkumulation
- DeviceProfile und DeviceCapabilities
- neutrale Laufzeit- und Persistenzmodelle
- DeviceCommand als neutrale gewünschte Geräteaktion
- neutrale Reason-, Status- und Ergebniswerte

Der Core darf nur importieren:

- Python-Standardbibliothek
- andere Core-Module
- neutrale, explizit freigegebene gemeinsame Typen während der Migration

Der Core darf nicht importieren oder kennen:

- `homeassistant.*`
- `hass`, ConfigEntry, HA State oder ServiceCall
- Entity- oder Device-Registry
- Entity-IDs als fachliche Pflichtfelder
- HA Services, Plattformnamen oder Übersetzungsschlüssel
- `UpdateFailed`, CoordinatorEntity oder HA Storage
- Zendure-Service- oder Entity-Namen
- MQTT Topics, Modbus Register oder Hersteller-APIs

## Composition Root und Update-Zyklus

`ZendureSmartFlowCoordinator` bleibt während V4.7 die Composition Root. Er
erzeugt die konkreten Adapter und Core-Komponenten, koordiniert aber
perspektivisch nur noch den Ablauf.

Der Zielablauf eines Updates ist:

1. HA startet einen Coordinator-Zyklus.
2. Der HA-Eingabeadapter liest die konfigurierten Entity-States.
3. Der Adapter normalisiert die Werte und baut einen RuntimeSnapshot.
4. Der Core bewertet Snapshot, Konfiguration, Profil und bisherigen
   RuntimeState.
5. Strategy/Decision Engine erzeugt einen StrategyIntent.
6. ModeArbiter entscheidet die technische Modusfreigabe.
7. RegulationPowerController berechnet die Leistung.
8. Der Core erzeugt einen DeviceCommand und aktualisierte neutrale Zustände.
9. Der HAEntityDeviceBackend-Adapter führt den DeviceCommand über den heutigen
   Select-/Number-Pfad aus.
10. Der HAStateStore-Adapter speichert kompatible Zustände.
11. Der Coordinator veröffentlicht ein neutrales Ergebnis als HA-Entity-Daten
    und behandelt HA-spezifische Fehler.

Der heutige Code erfüllt die Schritte 4 bis 8 bereits in wesentlichen Teilen.
V4.7 trennt vor allem die Ein- und Ausgänge sowie Zustandsbesitz aus dem
Coordinator heraus.

## Neutrale Ein- und Ausgabeverträge

### RuntimeSnapshot

`RuntimeSnapshot` ist der Arbeitsname für die neutrale Eingabegrenze. Die
endgültigen Modellnamen und Felder werden in Issue #267 und #268 festgelegt.

Der Snapshot enthält normalisierte Fachwerte, beispielsweise:

- Batteriezustand und SoC
- Netzimport, Netzeinspeisung und signierte Netzleistung
- PV-Leistung und Hauslast
- Batterie-Lade- und Entladeleistung
- normalisierte Import- und Exportpreise
- normalisierten PV- und Preis-Forecast
- Planungs- und Lernplanungszustand
- Off-Grid- und Zusatzakku-Zustand
- Zellschutz- und Datenqualitätszustand
- aktive Benutzerkonfiguration
- DeviceProfile und DeviceCapabilities
- bewussten Snapshot-Zeitstempel

Nicht enthalten sind:

- Entity-IDs
- HA State-Objekte oder deren Attribute-Dictionaries
- Registry-Objekte
- HA Services
- Übersetzungsschlüssel
- konkrete Backend-/Protokollinformationen

### Verhältnis zu vorhandenen Kontexten

Es werden nicht drei konkurrierende Kontextmodelle aufgebaut:

- `DecisionContext` ist der heutige breite, neutrale Snapshot-Vorläufer für die
  Decision Engine.
- `StrategyContext` in `regulation_models.py` ist tatsächlich das Ergebnis der
  AutomaticStrategy mit Gewichtung, Saisonkontext und Metadaten. Der Name ist
  daher missverständlich und kein zweiter RuntimeSnapshot.
- Ein zukünftiger RuntimeSnapshot soll vorhandene Felder konsolidieren und
  `DecisionContext` entweder ersetzen oder als interne Projektion beliefern.

Issue #267 entscheidet die Modellgrenzen. Issue #268 führt anschließend genau
eine zentrale Runtime-Eingabe ein. Bis dahin wird kein paralleles
Sammel-Dataclass angelegt.

### CoreResult

Der Core braucht langfristig einen neutralen Ergebnisvertrag. Der Name
`CoreResult` ist vorläufig und wird in den Modell-Issues bestätigt.

Er kann bündeln:

- StrategyIntent
- ModeArbiterResult
- PowerControllerResult
- DeviceCommand
- aktualisierte neutrale RuntimeStates
- EconomicsSnapshot
- neutrale Status-, Reason- und Datenqualitätswerte

HA-Entity-Zustände oder Services gehören nicht in dieses Ergebnis.

### DeviceCommand

`DeviceCommand` bleibt die neutrale Ausgabe zum Geräteadapter. Der Core
beschreibt gewünschte Wirkung:

- Modus
- Input-/Output-Leistung
- Grund und Priorität
- Force-/Schutzstatus, sofern fachlich neutral

Der Core beschreibt nicht:

- Entity-ID
- HA-Domain oder Service
- MQTT Topic
- Modbus Register
- Hersteller-API

Das heutige Modell enthält zusätzlich `should_write_*`, `skipped` und
`skip_reason`. Diese Felder schützen bestehendes Verhalten und werden nicht in
Issue #266 entfernt. Issue #269 entscheidet anhand des realen Schreibpfads,
welche Schreiboptimierung langfristig Core-Verantwortung und welche
Backend-Verantwortung ist.

## Ports und Adapter

Ports werden nur eingeführt, wenn ein heutiger Seiteneffekt entkoppelt werden
muss. V4.7 legt keine leeren Interfaces für hypothetische Systeme an.

### StateStore

Core-seitiger Zweck:

- neutrale Teilzustände laden und speichern
- keine Kenntnis von HA Storage, Entry-ID oder Dateipfad

HA-Implementierung:

- verwendet weiterhin `homeassistant.helpers.storage.Store`
- liest das bestehende Store-Schema
- führt Legacy-/Versionsmigrationen aus
- bildet neutrale Teilzustände verlustfrei auf das kompatible Schema ab

Das heutige flache `_persist`-Dictionary wird nicht auf einmal ersetzt. Issue
#270 ordnet zuerst Besitz und Serialisierung der Teilzustände zu.

### Clock

Zeit wird semantisch getrennt:

- UTC-Kalenderzeit für persistierbare Deadlines, Tageswechsel und
  Restart-Kompatibilität
- lokale Zeitzone für Preisfenster, Forecast und Lernplanung
- monotone Laufzeit für rein prozesslokale Intervalle, sofern diese nicht über
  einen Neustart erhalten werden müssen

Eine Clock-Abstraktion darf persistierte Holds/Cooldowns nicht blind auf
monotone Zeit umstellen. Issue #271 legt je Zustand fest, ob Kalender- oder
Laufzeitsemantik gilt.

### DeviceBackend

Der Core definiert langfristig eine kleine Ausführungsgrenze für
DeviceCommand. Die erste und in V4.7 einzige Implementierung kapselt den
heutigen HA-Entity-Pfad.

Vorläufiger Verantwortungszuschnitt:

- Core entscheidet Intent, Modusfreigabe und Zielleistung.
- Backend prüft HA-Entity-Verfügbarkeit und setzt den Befehl technisch um.
- Backend behandelt HA-Servicefehler und bestätigt ausgeführte Werte neutral.
- DeviceCapabilities beschreiben erlaubte Fähigkeiten; sie führen keine
  Herstellerabfrage im Core aus.

Safe-Idle, Manual-Standby und Schutzstopps müssen dieselbe Grenze verwenden wie
der Normalpfad. Das Backend darf nicht nur den glücklichen DeviceCommand-Pfad
abdecken.

Issue #273 führt ausschließlich diese Grenze und den vorhandenen
Home-Assistant-Entity-Adapter ein. Es entstehen weder ein Zendure-Direct-
Backend noch eine zweite Hardwareanbindung.

### Vorhandene Quellprotokolle

MarketPrice besitzt bereits `PriceSource`, `StateGetter`, `PriceNormalizer` und
`ForecastAdapter`. Diese Verträge werden bevorzugt weiterverwendet, statt neue
generische Provider-Interfaces daneben zu stellen.

`GenericStatePriceSource` ist trotz Protocol technisch ein HA-Adapter, weil es
Entity-ID, State, Attribute, unknown und unavailable kennt. Es kann später
physisch in die HA-Adapterstruktur wandern; `PriceSourceReading`,
`StaticPriceSource`, Normalisierung und MarketPrice-Modelle bleiben neutral.

Bei `forecast.py` werden HA-State-Erfassung und neutrale Berechnung getrennt,
statt das gesamte Modul in den Core zu verschieben.

## Ziel-Paketstruktur

Die Struktur ist ein erreichbares Endbild, keine Anweisung, alle Verzeichnisse
sofort anzulegen:

```text
custom_components/battery_smartflow_ai/
  __init__.py                     # HA lifecycle / composition entry
  config_flow.py                  # HA config and options flow
  coordinator.py                  # HA update scheduling / composition root
  sensor.py                       # HA entities
  number.py
  select.py
  diagnostics.py
  const.py                        # compatibility facade during migration

  adapters/
    home_assistant/
      snapshot_builder.py         # HA states -> RuntimeSnapshot
      forecast_source.py          # HA/provider forecast acquisition
      market_price_source.py      # HA State price acquisition
      state_store.py              # compatible HA Store implementation
      clock.py                    # HA timezone / wall-time adapter
      device_backend.py           # current Select/Number write path

  core/
    models/                       # neutral shared states and results
    strategy/                     # DecisionEngine, AutomaticStrategy, commit
    regulation/                   # arbiter, controller, grid history, commands
    planning/                     # classic and learned planning
    market_price/                 # neutral price models and normalization
    economics/                    # accumulator and EconomicsEngine
    profiles/                     # profiles and capabilities
    ports/                        # only real Clock/StateStore/DeviceBackend ports
```

Nicht jedes heutige Einzelmodul braucht ein eigenes Unterpaket. Kleine Helfer
werden nach fachlichem Besitz gruppiert. Ein Unterpaket entsteht erst, wenn
mindestens eine echte Abhängigkeitsgrenze oder mehrere zusammengehörige Module
es rechtfertigen.

### Warum kein vollständiges `ha/`-Paket?

Home Assistant lädt `config_flow.py` und Entity-Plattformen wie `sensor.py`,
`number.py` und `select.py` über feste Integrationspfade. Eine vollständige
Verschiebung nach `ha/entities/` würde Wrapper oder besondere Loaderlogik
erzwingen, ohne fachliche Kopplung zu reduzieren.

Die HA-Plattformmodule bleiben deshalb sichtbar am Paketanfang. Nur
wiederverwendbare Adapterimplementierungen werden unter
`adapters/home_assistant/` gekapselt.

## Abbildung heutiger Module auf das Ziel

| Heutiger Bereich | Zielverantwortung | Vorgehen |
| --- | --- | --- |
| `__init__.py`, `config_flow.py` | HA-Schicht | Pfad und Aufgabe behalten |
| `sensor.py`, `number.py`, `select.py`, `diagnostics.py` | HA-Schicht | Neutralen Coordinator-/Core-Output konsumieren |
| `coordinator.py` | HA-Schicht / Composition Root | I/O und Scheduling behalten, Fachlogik schrittweise delegieren |
| `const.py` | Übergangsfassade | HA-Meta von Fachkonstanten trennen, Werte stabil re-exportieren |
| `decision_engine.py` | Core Strategy | `DecisionContext` später aus RuntimeSnapshot ableiten |
| `automatic_strategy.py` | Core Strategy | Bestehende neutrale Funktionen übernehmen |
| `strategy_adapter.py`, `strategy_state.py` | Core Strategy/Models | Doppelungen bei Issue #267 konsolidieren |
| `charge_commit_policy.py` | Core Strategy/Execution | Lifecycle aus Coordinator schrittweise herauslösen |
| `battery_protection.py` | Core Protection | Zustandsmodell und Persistenzbesitz explizit machen |
| `mode_arbiter.py` | Core Regulation | `dt_util` durch neutrale Zeitsemantik ersetzen |
| `regulation_power_controller.py`, `power_controller.py` | Core Regulation | Verhalten unverändert übernehmen; Legacy-Rolle später klären |
| `regulation_models.py` | Core Models/Regulation | Modelle aufteilen, aber keine parallelen Duplikate anlegen |
| `device_command.py` | Core Regulation/Execution | Neutralen Command erhalten; Schreibflags in #269 prüfen |
| `grid_history.py`, `command_effectiveness.py` | Core Regulation | Zustandsbesitz und Backend-Feedback klar definieren |
| `charge_source_allocator.py` | Core Execution | Neutralen Rechenkern übernehmen |
| `learned_planning.py` | Core Planning | Zeitzone/Clock explizit injizieren |
| `forecast.py` | geteilt | HA-Erfassung in Adapter, Summary/Berechnung in Core |
| `market_price/models.py`, `planning.py`, Normalisierung | Core MarketPrice | Bestehende Verträge erhalten |
| `market_price/sources.py` | geteilt | State-Quelle in HA-Adapter, neutrale Reading-/Source-Verträge im Core |
| `market_price/legacy_import.py` | Adapter/Kompatibilität | Provider-Parsing außerhalb tiefer Core-Entscheidungen halten |
| `economics.py`, `economic_efficiency.py` | Core Economics | Deterministische Engine und Snapshots übernehmen |
| `charge_economics.py` | Core Economics/Strategy | Fachlichen Besitz bei #275 klären |
| `device_profiles.py` | Core Profiles | DeviceCapabilities typisieren, Werte/Fallbacks unverändert lassen |
| Debug-Modelle und Exporter | HA-Diagnose mit neutralen Daten | Kein Teil der Steuerungs-Core-Grenze; Secret-Filter erhalten |

## Konfigurationsgrenze

ConfigEntry bleibt ausschließlich HA-seitig. Der Core erhält neutrale,
validierte Konfiguration.

Während der Migration gilt:

- bestehende Config- und Options-Schlüssel bleiben stabil
- alte Einträge werden weiter durch HA-Migrationscode gelesen
- der Adapter übersetzt ConfigEntry in neutrale Konfigurationsmodelle
- der Core schreibt ConfigEntry niemals selbst
- Number-/Select-Entities ändern Optionen weiterhin über die HA-Schicht

Issue #267 kann Konfiguration von Messzustand trennen, ohne die gespeicherten
HA-Schlüssel umzubenennen.

## Fehler- und Verfügbarkeitsgrenze

Der Core arbeitet mit neutraler Datenqualität, nicht mit HA-Zustandsstrings.

Der HA-Adapter übersetzt beispielsweise:

- fehlende Entity -> nicht konfiguriert oder fehlend
- `unknown` -> unbekannt
- `unavailable` -> nicht verfügbar
- nicht numerischer Wert -> ungültig
- veralteter Wert -> stale

Der Core entscheidet anhand neutraler Gültigkeit und Schutzregeln. Er kennt
keine Entity-Verfügbarkeit.

Core-Fehler werden als neutrale Ergebnisse oder fachliche Exceptions
zurückgegeben. Erst der Coordinator übersetzt sie bei Bedarf in `UpdateFailed`,
Logging oder Entity-Verfügbarkeit.

## Diagnose- und Übersetzungsgrenze

Der Core liefert stabile maschinenlesbare Reasons und strukturierte neutrale
Diagnosedaten. Er liefert keine lokalisierten Texte.

Die HA-Schicht verantwortet:

- Übersetzungsschlüssel und sichtbare Namen
- Entity-Attribute und Kategorien
- Debug-Aufzeichnung und Export
- Secret-Filter und Dateipfad
- Auswahl, welche neutralen Werte dauerhaft als Sensor sichtbar sind

Das zeitbegrenzte JSON-Debug-Paket bleibt der bevorzugte Tiefendiagnoseweg.
Die Core-Trennung rechtfertigt keine neuen permanenten Debug-Sensoren.

## Kompatibilitätsregeln

Jeder spätere Refactoring-Schritt muss folgende Grenzen einhalten:

1. ConfigEntry-Daten und Options bleiben lesbar.
2. Entity IDs und Unique IDs bleiben stabil, sofern keine dokumentierte
   Migration unvermeidbar ist.
3. Das HA-Store-Schema bleibt kompatibel lesbar und wird versioniert migriert.
4. Geräteprofile und deren numerische Werte werden nicht durch Strukturarbeit
   neu abgestimmt.
5. Strategy-Reasons, Latches, Holds, Cooldowns und Ramp-down-Verhalten bleiben
   fachlich gleich.
6. MarketPrice unterscheidet weiterhin `0`, negative Preise und fehlende Werte.
7. Economics zählt normalen PV-Export nicht als Batterienutzen.
8. Safe-Idle, Zellschutz, Off-Grid und Zusatzakku-Blocker bleiben wirksam.
9. Der heutige Zendure-/HA-Entity-Gerätepfad bleibt die einzige reale
   Implementierung in V4.7.
10. Nach jedem Extraktionsschritt laufen fokussierte und vollständige
    Regressionstests.

## Schrittweise Migrationsroute

Die Route folgt den vorhandenen V4.7-Issues und vermeidet einen Big-Bang-
Umbau.

### Stufe 1: Modelle und Eingabegrenze

Issues #267 und #268:

- vorhandene Dataclasses und Dictionaries konsolidieren
- `DecisionContext` und den missverständlich benannten `StrategyContext`
  einordnen
- genau einen neutralen RuntimeSnapshot etablieren
- Snapshot zunächst im Coordinator/HA-Adapter bauen
- bestehende Engine-APIs über Kompatibilitätsadapter weiter bedienen

Stopppunkt: Gleiche Eingaben müssen zu gleichen DecisionResult-/Intent-Werten
führen. Noch keine Persistenz- oder Gerätebackend-Änderung.

### Stufe 2: Ausgabepfad, Persistenz und Zeit

Issues #269 bis #271:

- Normal-, Safe-Idle- und Manual-Standby-Pfade über eine Command-Grenze führen
- StateStore-Besitz pro Teilzustand definieren
- bestehendes HA-Store-Schema über einen HAStateStore weiterverwenden
- Zeit- und Zeitzonenzugriffe über explizite Clock-/Zeitwerte ersetzen

Stopppunkt: Entity-Schreibsequenz, Store-Inhalt und Restart-Verhalten müssen
vor und nach dem Schritt äquivalent sein.

### Stufe 3: Profile, Capabilities und Backend-Grenze

Issues #272 und #273:

- bestehende Profil-Dictionaries schrittweise typisieren
- Capability-Namen neutral konsolidieren
- vorhandenen HA-Entity-Schreibpfad als einzige Backend-Implementierung kapseln
- keine neuen Hersteller-, Protokoll- oder Hardwarepfade ergänzen

Stopppunkt: Alle unterstützten Profile erzeugen dieselben Limits, Moduswechsel
und Commands wie zuvor.

### Stufe 4: Fachmodule konsolidieren

Issues #274 bis #276:

- Decision Engine und Strategy ohne Verhaltensänderung gliedern
- ModeArbiter und PowerController klar kapseln
- Forecast-/MarketPrice-Erfassung von neutraler Berechnung trennen
- Economics-Lifecycle und Persistenzgrenze festigen

Stopppunkt: Szenario- und Regelungsregressionen müssen unverändert bestehen.

### Stufe 5: Cleanup und Nachweis

Issues #277 bis #280:

- erst jetzt nachgewiesen toten Legacy-Code entfernen
- HA-Sensoren, Übersetzungen und Diagnose konsolidieren
- echte Core-Imports ohne installierte `homeassistant`-Stubs testen
- Rückwärtskompatibilität und vollständige Regression absichern

Stopppunkt: Ein neutraler Core-Test darf kein `homeassistant` in `sys.modules`
benötigen; HA-Integrationsfunktionen behalten gesonderte HA-Tests.

## Architekturregeln für Pull Requests

Ab dem ersten Entkopplungs-PR gelten folgende überprüfbare Regeln:

- Neue Dateien unter `core/` dürfen kein `homeassistant` importieren.
- Core-Modelle enthalten keine Entity-ID als Pflichtfeld.
- Adapter dürfen Core importieren; Core darf Adapter nicht importieren.
- HA-Serviceaufrufe entstehen nur in HA-Schicht oder HA-Adapter.
- Neue persistente Core-Zustände besitzen neutrale Serialisierung und einen
  kompatiblen HA-StateStore-Pfad.
- Neue Zeitlogik erhält Zeit oder Clock explizit; keine verstreuten neuen
  `datetime.now()`-/`dt_util.utcnow()`-Aufrufe im Core.
- Neue Gerätefähigkeiten werden über DeviceCapabilities beschrieben, nicht
  durch Modellnamenabfragen im Core.
- Ein Refactoring-PR enthält keine beiläufige neue Funktionalität oder
  Reglerabstimmung.
- Temporäre Kompatibilitäts-Re-Exports sind dokumentiert und besitzen einen
  geplanten Entfernungspunkt.

Diese Regeln können später durch einen kleinen statischen Importtest ergänzt
werden. Issue #266 fügt noch keine neue Build- oder CI-Infrastruktur hinzu.

## Architekturentscheidungen, die bewusst vertagt bleiben

Folgende Details müssen aus den nachfolgenden Implementierungs-Issues entstehen:

- endgültige Feldaufteilung von RuntimeSnapshot und Teilzuständen
- endgültiger Name von `StrategyContext`
- genaue `CoreResult`-Struktur
- sync/async-Form des StateStore-Ports
- exakte DeviceBackend-Signatur und Bestätigungsmodell
- Besitz der heutigen `should_write_*`-Optimierung
- Aufteilung des flachen Persistenzschemas
- Zeitpunkt und Umfang physischer Dateiverschiebungen
- eventuelle spätere Auslagerung des Core in ein separates Paket nach V4.7

Diese Punkte jetzt festzuschreiben wäre Architektur ohne ausreichende
Implementierungsevidenz.

## Review nach Issue #265 und #266

Die Inventur und diese Zieldefinition bestätigen das langfristige
Architekturmodell grundsätzlich, mit vier Anpassungen an die reale Codebasis:

1. **Kein Rewrite:** Große Teile des Core existieren bereits als neutrale
   Module und werden konsolidiert statt neu gebaut.
2. **Kein vollständiges `ha/`-Verzeichnis:** HA-Plattformdateien bleiben wegen
   ihrer Loader-Verträge am Paketanfang; nur Adapter werden gekapselt.
3. **Kein paralleler Kontext:** `DecisionContext` ist Snapshot-Vorläufer,
   `StrategyContext` ist AutomaticStrategy-Ergebnis. Issue #267/#268
   konsolidieren diese Rollen.
4. **Coordinator strangulieren, nicht ersetzen:** I/O bleibt dort zunächst
   stabil, während Fachlogik und Zustandsbesitz schrittweise delegiert werden.

Die geplante Reihenfolge #267 bis #280 bleibt damit sinnvoll. Vor Issue #267
ist kein zusätzliches Architektur-Issue erforderlich.

## Abgleich mit den Akzeptanzkriterien von Issue #266

- Zielgrenze Core/HA: **über Schichten, Importregeln und Update-Zyklus definiert**
- Core-Verantwortlichkeiten: **fachlich und technisch abgegrenzt**
- HA-Verantwortlichkeiten: **Lifecycle, Entities, I/O und Darstellung zugeordnet**
- DeviceBackend: **als kleine spätere Grenze mit genau einer V4.7-Implementierung berücksichtigt**
- weitere Plattformen/Hersteller: **durch neutrale Verträge möglich, aber nicht implementiert**
- keine stärkere Zendure-/HA-Bindung: **durch verbotene Core-Abhängigkeiten abgesichert**
- Grundlage für Folge-Issues: **Modulabbildung, Migrationsstufen und Stopppunkte dokumentiert**

## Nicht Teil dieser Änderung

- keine neue Python-Paketstruktur im Laufzeitcode
- keine Modulverschiebung oder Importänderung
- kein RuntimeSnapshot-, CoreResult-, Port- oder Adaptercode
- keine Änderung an Coordinator, Strategy, Regelung oder Planung
- keine Persistenz-, Config- oder Entity-Migration
- kein neues Backend oder Geräteprofil
- keine Versionsänderung
