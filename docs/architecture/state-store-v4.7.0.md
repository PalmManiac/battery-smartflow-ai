# StateStore-Grenze in V4.7.0

Issue #270 trennt die persistente Zustandsablage von Home Assistant, ohne das
vorhandene Speicherformat bestehender Installationen zu verändern.

## Laufzeitpfad

```text
Coordinator und Core-Komponenten
        |
        | neutrale dict-Daten und neutrale Ergebnisse
        v
core.ports.StateStore
        |
        v
adapters.home_assistant.HomeAssistantStateStore
        |
        v
homeassistant.helpers.storage.Store
```

Der Core-Port kennt weder `HomeAssistant`, Config Entries, Store-Schlüssel noch
Dateipfade. Der HA-Adapter verwendet weiterhin Version `1` und den bisherigen
Schlüssel `battery_smartflow_ai.<entry_id>`. Auch der gespeicherte Payload bleibt
ein flaches Dictionary. Dadurch können vorhandene Daten ohne Formatmigration
weiter geladen werden.

## Zustandsbesitz

Das bestehende Dictionary wird in #270 bewusst nicht als große Migration
umgebaut. Die fachliche Verantwortung der bereits vorhandenen Teilzustände ist:

| Besitzer | Restart-relevante Beispiele | Serialisierung/Wiederherstellung |
| --- | --- | --- |
| Economics | `economics_energy_state`, `economics_money_state`, Tagesgrenze | `EnergyAccumulator.to_state/from_state`, `EconomicsEngine.to_state/from_state` |
| Strategische Planung | `charge_commit_*`, Lernslots und Leistungsproben | bestehende neutrale Zahlen, Strings, Listen und Dictionaries |
| Regulation und Schutz | Latches, Holds, Schutzsperren und letzte bestätigte Sollwerte | bestehendes flaches, JSON-kompatibles Schema |
| Coordinator-Laufzeit | `runtime_mode`, Saison und restart-relevante Anzeigezustände | Defaults plus kompatibles Überschreiben geladener Werte |
| Diagnose | wenige für die Laufzeit benötigte Diagnosewerte | keine zusätzlichen Debug-Pakete oder Rohdaten |

Kurzlebige Messwerte, vollständige Snapshots und HA-Objekte werden nicht neu
persistiert. Neue Core-Komponenten sollen ihren eigenen neutralen Teilzustand
serialisieren; der Coordinator führt diese Teile bis zu einer späteren,
expliziten Schemamigration verlustfrei im kompatiblen Dokument zusammen.

## Fehler- und Migrationsverhalten

- Fehlender Store ergibt einen leeren, sicheren Start mit den bisherigen
  Defaults.
- Ein nicht-dictionaryförmiger oder nicht lesbarer Store wird nicht in den
  Runtime-Zustand übernommen.
- Backend-Ausnahmen werden als neutrale Resultate zurückgegeben. Der
  Coordinator protokolliert sie in der HA-Plattformschicht und arbeitet mit
  Defaults beziehungsweise dem aktuellen In-Memory-Zustand weiter.
- Bestehende fachliche Migrationen und Normalisierungen bleiben erhalten:
  Preisfeldmigration, Begrenzung des Saison-Zählers, Entfernen obsoleter Keys
  sowie Wiederherstellung von Economics- und Runtime-Zuständen.
- Ein Speicherfehler unterbricht weder den Regelzyklus noch einen Safe-Idle-
  Schutzpfad. Der aktuelle Zustand bleibt im Speicher und der nächste Zyklus
  kann erneut speichern.

## Bewusste Grenze

Issue #270 führt keinen Datei- oder SQLite-Store ein und zieht keine
Zeitabstraktion aus #271 vor. Die kleine Schnittstelle bildet genau den heute
benötigten versionierten Zustandsdatensatz ab; weitere Backends können später
denselben neutralen Vertrag implementieren.
