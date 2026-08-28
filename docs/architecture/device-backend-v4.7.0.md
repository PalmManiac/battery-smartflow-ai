# DeviceBackend-Grenze in V4.7.0

Issue #273 formalisiert den in #269 eingeführten Geräte-Ausgabepfad als
neutralen Backend-Port. Es entsteht kein zweiter Schreibpfad und keine neue
Hardwarekommunikation.

## Laufzeitpfad

```text
RuntimeSnapshot + DeviceCapabilities
        |
        v
DecisionEngine / Regulation
        |
        v
DeviceCommand
        |
        v
core.ports.DeviceBackend
        |
        v
HomeAssistantEntityBackend
        |
        v
bestehende Select-/Number-Writer und HA-Services
```

Der Coordinator bleibt Composition Root. Er verbindet das gewählte
`DeviceProfile`, dessen `DeviceCapabilities` und die konkrete Backend-
Implementierung.

## Neutraler Port

`DeviceBackend` besitzt bewusst nur:

- die unveränderlichen `DeviceCapabilities` des angebundenen Geräts und
- `execute(DeviceCommand) -> CommandExecutionResult`.

Die zwei bestehenden Ausführungsoptionen bleiben neutral und
verhaltensrelevant:

- `force_power` erzwingt einen technisch nötigen Leistungswrite, etwa bei
  Richtungswechsel oder Effectiveness-Retry.
- `power_before_mode` erhält die sichere Reihenfolge beim einmaligen INPUT-Stop
  für Manual-Standby.

Sie enthalten keine Entity-, Service-, Hersteller- oder Protokollinformation.

## Verantwortlichkeit des Core

Der Core erzeugt ausschließlich `DeviceCommand` mit:

- gewünschtem AC-Modus,
- Input-/Output-Leistung,
- Write-/Skip-Entscheidung,
- neutralem Grund und
- neutralen Diagnosemetadaten.

DecisionEngine, Strategy, Planning, Economics, MarketPrice, ModeArbiter und
PowerController kennen weder HA-Entities noch MQTT-Topics, Modbus-Register oder
Hersteller-APIs.

## Verantwortlichkeit des HA-Backends

`HomeAssistantEntityBackend` bildet einen Command auf die drei bereits
vorhandenen Writer ab:

- AC-Modus setzen,
- Input-Limit setzen,
- Output-Limit setzen.

Die Writer kapseln weiterhin:

- operation-spezifische Entity-Verfügbarkeit,
- HA-Serviceaufrufe,
- dynamische Number-Min-/Max-Grenzen,
- Istwert-/Cache-Abgleich,
- Null als Stop trotz positiver Entity-Mindestleistung und
- Cache-Update erst nach erfolgreichem Schreiben.

Availability ist damit nicht eine ungenaue globale Backend-Flagge: Sie wird für
die tatsächlich angeforderte Operation geprüft. Ein nicht verfügbares Entity
oder ein Servicefehler wird außerhalb der Strategie in ein neutrales
`CommandExecutionResult(FAILED)` übersetzt.

## Ergebnis und Fehler

`CommandExecutionResult` bleibt der gemeinsame neutrale Rückgabevertrag:

- `APPLIED`, `SKIPPED` oder `FAILED`,
- ausgeführter Modus-, Input- und Output-Write,
- neutraler Command-Grund und
- optionale bereinigte Fehlerbeschreibung.

`DeviceBackendExecutionError` transportiert dieses Ergebnis in den bestehenden
Coordinator-Fehlerpfad. Die Plattformursache wird nicht in Strategy oder
Planung gereicht und ein Teilwrite wird korrekt im Ergebnis festgehalten.

## Einheitliche Produktpfade

Alle produktiven Geräteoperationen laufen über `_device_backend.execute()`:

1. normaler Strategy-/Regulation-Command,
2. Safe-Idle bei ungültigen Pflichtdaten und
3. einmaliger Stop beim Eintritt in Manual-Standby.

Außerhalb des HA-Backends existiert kein direkter produktiver Aufruf der drei
Writer. Reihenfolge, Write-Schwellen, Latches und Retry-Verhalten bleiben
unverändert.

## Kompatibilität

Die #269-Namen bleiben als reine Re-Export-Fassade erhalten:

- `HomeAssistantEntityCommandExecutor` verweist auf
  `HomeAssistantEntityBackend`.
- `DeviceCommandExecutionError` verweist auf
  `DeviceBackendExecutionError`.

Vorhandene Imports erzeugen damit keine zweite Klasse und keinen alternativen
Pfad.

## Spätere Erweiterung

Ein künftiges MQTT-, Modbus- oder Direct-Backend kann denselben Port
implementieren und seine eigenen Capabilities bereitstellen. Eine spätere
Multi-Battery-Komposition kann mehrere Backend-Instanzen adressieren, ohne den
fachlichen `DeviceCommand` neu zu definieren.

#273 implementiert ausdrücklich nicht:

- kein Zendure-Direct-Backend,
- kein MQTT- oder Modbus-Backend,
- keinen weiteren Hersteller,
- keine Geräteerkennung,
- keine Multi-Battery-Orchestrierung und
- keine Änderung an Leistung, Strategie oder Regel-Tuning.
