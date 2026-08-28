# Core ohne Home Assistant testen (V4.7.0)

Issue #279 schließt die letzte technische Lücke zwischen neutralem Core und
seinen Tests: Core-Module lassen sich über den normalen Python-Paketpfad laden,
ohne dass Home Assistant installiert, gestartet oder durch Modul-Stubs
nachgebildet sein muss.

## Importgrenze

Python führt beim Import eines Untermoduls zuerst das Paketmodul
`custom_components.battery_smartflow_ai` aus. Dieses Paket lädt den
Home-Assistant-Lifecycle daher nur, wenn Home Assistant verfügbar ist. Im
realen Integrationsbetrieb bleiben `CONFIG_SCHEMA`, Coordinator, Services,
Setup, Unload und Migration unverändert aktiv. Ein alleiniger Core-Import lädt
dagegen weder Home Assistant noch den Coordinator.

Der Core behält seine bestehenden Regeln:

- keine `homeassistant`-Imports unter `core/`
- Plattformdaten kommen normalisiert über `RuntimeSnapshot`
- Geräte-I/O läuft über den neutralen `DeviceBackend`-Port
- Persistenz läuft über den neutralen `StateStore`-Port
- Zeitlogik erhält eine `Clock`

## Deterministische Testhilfen

`core.testing` stellt drei kleine Bausteine für eigenständige Domänentests
bereit:

- den bereits vorhandenen `TestClock` für kontrollierte Zeit
- `MemoryStateStore` für eine kopierte, flüchtige Zustandsablage
- `FakeDeviceBackend` für aufgezeichnete Befehle und neutrales Erfolgsfeedback

Die Doubles implementieren dieselben Ports wie die Home-Assistant-Adapter,
kennen aber weder Entities noch Services, Config Entries oder den Recorder.

## Ausführbarer Nachweis

`tests/test_core_without_home_assistant.py` startet einen isolierten
Python-Prozess. Er prüft zuerst, dass `homeassistant` nicht auffindbar ist, und
importiert danach über den regulären Paketpfad unter anderem RuntimeSnapshot,
DecisionEngine, Marktmodelle, TestClock, MemoryStateStore und
FakeDeviceBackend. Der Test wertet einen Snapshot aus, unterscheidet einen
gültigen Nullpreis von nicht verfügbaren Werten und führt Persistenz sowie
einen Gerätebefehl über die neutralen Ports aus. Abschließend wird erneut
geprüft, dass kein Home-Assistant-Modul geladen wurde.

Die breitere Szenariomatrix für Netzbezug, PV-Laden, strategisches Laden,
Charge-Commit, Schutzgrenzen, Off-grid/Zusatzakku, Near-zero, Cooldowns,
Haltezeiten und Tageswechsel bleibt in den jeweiligen Core-Tests. Issue #279
ändert dabei weder Produktverhalten noch Reglertuning.
