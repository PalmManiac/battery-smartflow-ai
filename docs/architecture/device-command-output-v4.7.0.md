# V4.7.0: Neutraler DeviceCommand-Ausgabepfad

- Status: Implementierungsentscheidung für Issue #269
- Basis: `main` nach Merge von PR #296
- Eingabegrenze: `runtime-snapshot-v4.7.0.md`
- Scope: neutrale Core-Ausgabe und HA-Ausführung, kein neuer Gerätepfad

## Entscheidung

Der fachliche und technische Core erzeugt ausschließlich einen neutralen
`DeviceCommand`. Die Ausführung erfolgt über den Home-Assistant-Adapter
`HomeAssistantEntityCommandExecutor`:

```text
RuntimeSnapshot
  -> DecisionEngine
  -> StrategyIntent
  -> ModeArbiter
  -> RegulationPowerController
  -> DeviceCommand
  -> HomeAssistantEntityCommandExecutor
  -> bestehende Select-/Number-Writer
```

Der Command kennt keine Entity-ID, HA-Domain, Services, Registry-Objekte,
MQTT-Topics, Modbus-Register oder Hersteller-API.

## DeviceCommand

Der bestehende Command bleibt der kanonische neutrale Vertrag. Er enthält:

- gewünschte technische AC-Richtung
- Input- und Output-Limit
- stabilen Reason
- Schreibentscheidungen für Modus und beide Leistungsrichtungen
- Skip-Status und Skip-Reason
- plattformneutrale Diagnosemetadaten

Die vorhandenen `should_write_*`-Felder bleiben in #269 erhalten. Sie tragen
heute die bereits getestete Schreibschwellen-, Live-Wert- und
Richtungswechseloptimierung. Eine Entfernung oder grundlegende Neuverteilung
würde unnötig das Geräteverhalten verändern.

Die Felder sind keine HA-Entity-Information. Der Adapter entscheidet weiterhin,
welche konkrete Select-/Number-Entity und welcher Service den Wunsch umsetzt.

## Home-Assistant-Adapter

`adapters/home_assistant/device_command_executor.py` besitzt die technische
Ausführungsgrenze. Er erhält drei HA-seitige Writer-Callbacks:

- Modus setzen
- Input-Limit setzen
- Output-Limit setzen

Entity-Verfügbarkeit, dynamische Number-Grenzen, Cache-/Istwert-Abgleich,
Serviceaufruf und Cache-Update bleiben in diesen bestehenden Coordinator-
Writern. Der Adapter und der Core benötigen keine Entity-ID.

## Einheitliche Command-Pfade

Folgende Produktpfade verwenden dieselbe Ausführungsgrenze:

1. normaler Strategy-/Regulation-Command
2. Safe-Idle bei ungültigen Pflichtdaten
3. einmaliger Stop beim Eintritt in Manual-Standby

Es existieren außerhalb des Executors keine direkten produktiven Aufrufe der
drei Writer mehr.

### Normalbetrieb

Die bestehende Reihenfolge bleibt Modus vor aktiver Leistung. Die vom
`DeviceCommandBuilder` bestimmten Write-Flags und Toleranzen bleiben erhalten.
Effectiveness-Retries werden nur dann verbucht, wenn der Adapter den
entsprechenden Richtungswrite tatsächlich ausgeführt hat.

### Safe-Idle

Safe-Idle erzeugt einen neutralen Nullleistungs-Command für die aktive oder
zuletzt aktive Richtung. Das bisherige Verhalten bleibt erhalten:

- aktive INPUT-Seite wird über Input `0` gestoppt
- andernfalls wird aktive OUTPUT-Seite über Output `0` gestoppt
- ohne aktive oder bekannte Richtung wird kein Gerätewrite erfunden

### Manual-Standby

Manual-Standby bleibt passiv, nachdem der beim Eintritt notwendige Stop genau
einmal ausgeführt wurde. Bei vorherigem INPUT bleibt die etablierte Reihenfolge
erhalten:

1. Input-Leistung auf `0`
2. Modus auf OUTPUT

Bei vorherigem OUTPUT wird nur Output `0` geschrieben. Das bestehende
`manual_standby_stop_applied`-Latch bleibt unverändert.

## Neutrales Ausführungsfeedback

`CommandExecutionResult` meldet plattformneutral:

- `APPLIED`
- `SKIPPED`
- `FAILED`
- welche der drei technischen Operationen ausgeführt wurden
- neutralen Reason
- optional eine Fehlerbeschreibung

Der Coordinator speichert dieses Feedback für Diagnosezwecke. Ein HA-Fehler
wird nicht verschluckt: `DeviceCommandExecutionError` trägt das neutrale
Ergebnis und wirft den Fehler weiter in den bestehenden Coordinator-
Fehlerpfad. Dadurch ändert sich das Laufzeit-Fehlerverhalten nicht.

## Schreibschutz und Optimierung

Unverändert bleiben:

- minimale Leistungsänderung für einen Write
- Vergleich mit internem Cache und realem Entity-Wert
- dynamische Number-Min-/Max-Grenzen
- Null als besonderer Stop-Befehl trotz positiver Entity-Mindestleistung
- nur ein aktiver Richtungswrite
- kein zusätzlicher gegenüberliegender Nullwrite
- Force-Verhalten bei Richtungswechseln und Effectiveness-Retry
- Cache-Update erst nach erfolgreichem HA-Serviceaufruf

## Erweiterbarkeit

Der neutrale Command und das neutrale Feedback können später von weiteren
Backends verwendet werden. #269 implementiert ausdrücklich nur den vorhandenen
HA-Entity-Pfad. Es entstehen kein Zendure-Direct-, MQTT-, Modbus- oder weiteres
Hersteller-Backend.

Issue #273 kann die formale DeviceBackend-Port-Signatur aus dem nun realen
Ausführungsvertrag ableiten, ohne den Core-Command erneut zu ändern.

Dies ist mit [`device-backend-v4.7.0.md`](device-backend-v4.7.0.md) umgesetzt.
Der frühere Executor-Name bleibt als kompatibler Alias der kanonischen
`HomeAssistantEntityBackend`-Implementierung erhalten.

## Nachweis

Die Tests prüfen:

- Modus-vor-Leistung im Normalpfad
- Leistung-vor-Modus beim INPUT-Stop für Manual-Standby
- keine Plattformwrites für übersprungene Commands
- neutrales Fehlerfeedback bei fehlgeschlagenem Plattformwrite
- alle produktiven Coordinator-Writes laufen über den Executor
- vollständige Strategie-, Regelungs-, Safety- und Geräteverhaltensregression

## Nicht Teil von #269

- kein neues Hardware- oder Herstellerbackend
- keine neue HA-Entity
- keine Änderung an StrategyIntent oder Leistungsberechnung
- kein StateStore- oder Clock-Port
- keine Persistenzschema- oder Config-Migration
- keine Reglerabstimmung
