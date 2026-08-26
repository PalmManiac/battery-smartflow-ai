# V4.7.0: Neutraler RuntimeSnapshot

- Status: Implementierungsentscheidung für Issue #268
- Basis: `main` nach Merge von PR #295
- Modellgrundlage: `core-models-v4.7.0.md`
- Scope: zentrale Core-Eingabe, keine Command-, Store- oder Backend-Änderung

## Entscheidung

`RuntimeSnapshot` ist die einzige zentrale Laufzeiteingabe der Decision Engine.
Der bisherige Name `DecisionContext` bleibt als Identitätsalias erhalten:

```python
DecisionContext is RuntimeSnapshot
```

Es gibt keine Konvertierung zwischen zwei Sammelmodellen und keine doppelte
Dataclass-Definition. Bestehende Tests und Aufrufer dürfen den alten Namen
während der V4.7-Migration weiterverwenden.

## Aufbaugrenze

Der Home-Assistant-Coordinator bleibt zunächst Composition Root. Er liest die
konfigurierten HA-States, normalisiert Einheiten und Vorzeichen, klärt
Verfügbarkeit und erzeugt anschließend einen `RuntimeSnapshot`.

Die Decision Engine erhält nur diesen vorbereiteten Snapshot. Sie liest keine
HA-States, Registries oder Services. Die Snapshot-Klasse selbst importiert kein
Home Assistant und kann in reinen Unit Tests erzeugt werden.

Ein separates `snapshot_builder.py` wird in #268 noch nicht eingeführt. Der
Builder würde momentan lediglich die sehr große lokale Konstruktion aus dem
Coordinator verschieben, ohne den State-Lesevorgang schon sauber abzugrenzen.
Die physische Adapterextraktion erfolgt später entlang der in #266 festgelegten
Migrationsroute.

## Inhalt

Der Snapshot führt den bestehenden, verhaltensrelevanten Decision-Engine-
Vertrag an einem neutralen Ort zusammen:

- zentraler, zeitzonenbewusster Zeitstempel
- SoC, SoC-Grenzen und Batterieleistungen
- Netzbezug und Einspeisung
- PV-Leistung und abgeleitete Hauslast
- Import- und Export-Marktpreise
- Preisgrenzen und wirtschaftliche Parameter
- Forecast und Lernladeplan
- Modus, Saison und relevante Benutzerkonfiguration
- Charge-/Discharge-Historie und Debounce-Zustände
- Schutz- und Zellspannungszustände
- Off-Grid- und Zusatzakku-Zustände
- Ergebnis der AutomaticStrategy
- Geräteprofil und daraus ableitbare DeviceCapabilities
- explizite Datenqualitätsflags

Nicht enthalten sind Entity-IDs, HA-State-Objekte, ConfigEntry, Registry-
Objekte, Services, Entity-Klassen oder Übersetzungsschlüssel.

## Typisierte Sichten

Um den bestehenden Decision-Engine-Vertrag ohne Big-Bang-Rewrite zu erhalten,
bleiben die heute verwendeten flachen Felder zunächst stabil. Derselbe Snapshot
stellt daraus die in #267 definierten Modelle bereit:

- `snapshot.battery -> BatteryState`
- `snapshot.grid -> GridState`
- `snapshot.pv -> PVState`
- `snapshot.offgrid -> OffGridState`
- `snapshot.additional_battery -> AdditionalBatteryState`
- `snapshot.capabilities -> DeviceCapabilities`
- `snapshot.automatic_strategy -> AutomaticStrategyResult`

Diese Sichten sind keine zweite Datenhaltung. Sie werden deterministisch aus
dem Snapshot erzeugt und können von nachfolgenden Core-Extraktionen schrittweise
übernommen werden.

## Gültigkeit

Messwert und Verfügbarkeit bleiben getrennt:

- ein gültiger Wert `0` bleibt ein echter Messwert
- ein nicht konfigurierter Netzsensor wird `MISSING`
- ein konfigurierter, aber ungültiger Netzsensor wird `INVALID`
- ein ungültiger PV-Sensor liefert keinen erfundenen Nullwert
- ein nicht verfügbarer Off-Grid-Pfad bleibt explizit fehlend

Die bestehenden booleschen Schutzflags bleiben für die Decision Engine
kompatibel. Die typisierten Sichten machen ihre fachliche Bedeutung zusätzlich
für neue Core-Komponenten verfügbar.

## Marktpreis, Planung und Wirtschaft

Der Snapshot trägt die kanonischen `MarketPrice`-Objekte für Import und Export.
Nullpreis, negative Preise und fehlende Preise behalten ihre V4.5/V4.6-
Semantik.

Forecast und Lernladeplan bleiben ihre vorhandenen neutralen Modelle. Es wird
kein zweites `PlanningState` erzeugt. Wirtschaftlich relevante Eingaben wie
durchschnittlicher Ladepreis, Preisgrenzen und Profit-Marge sind Teil desselben
Snapshots; der persistente Economics-Lifecycle bleibt unverändert und wird erst
in #276 weiter extrahiert.

## Laufzeitintegration

Der Coordinator erzeugt sowohl für die eigentliche Entscheidung als auch für
die spätere Transparenzberechnung einen `RuntimeSnapshot`. Die Decision Engine
typisiert ihren öffentlichen Eingang als `RuntimeSnapshot`.

Alle bestehenden Regeln arbeiten während dieses Schritts weiter mit den
kompatiblen Feldern. Dadurch ändert sich weder Regelreihenfolge noch Strategie,
Zielleistung, Hysterese, Planning oder Schutzverhalten.

## Kompatibilität und Folgeschritte

- `DecisionContext` bleibt als Alias verfügbar.
- Bestehende Test-Fixtures müssen nicht auf einmal migriert werden.
- Feldnamen und Defaultwerte bleiben stabil.
- Kein Store-, Config- oder Diagnoseformat ändert sich.
- Kein Command- oder Geräte-Schreibpfad ändert sich.
- #269 kann auf demselben Snapshot den neutralen Ausgabevertrag bearbeiten.
- Die spätere Adapterextraktion kann die Snapshot-Konstruktion aus dem
  Coordinator herauslösen, ohne die Core-Schnittstelle erneut zu ändern.

## Nachweis

Die Tests prüfen:

- `DecisionContext is RuntimeSnapshot`
- Instanziierung ohne Home-Assistant-Objekte
- direkte Decision-Engine-Auswertung eines vorbereiteten Snapshots
- typisierte Battery-, Grid-, PV- und Capability-Sichten
- explizite Gültigkeit ungültiger Eingangsdaten
- keine `homeassistant`-Imports unter `core/models/`
- vollständige Verhaltensregression des bestehenden Systems

## Nicht Teil von #268

- kein zweiter StrategyContext
- keine Änderung an StrategyIntent oder DeviceCommand
- kein DeviceBackend
- kein StateStore oder Clock-Port
- keine Profilmigration
- keine neue Strategie oder Reglerabstimmung
- keine neue Plattform oder Geräteunterstützung
