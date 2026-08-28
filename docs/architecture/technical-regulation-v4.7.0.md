# V4.7.0: Technische Regelung

- Status: Umsetzung für Issue #275
- Scope: klare Core-Grenzen ohne Regler-Tuning
- Eingang: `StrategyIntent`
- Ausgang: `DeviceCommand`

## Eindeutige Verarbeitung

Die technische Regelung besteht aus einer gerichteten Kette:

`StrategyIntent → ModeArbiter → RegulationPowerController → DeviceCommandBuilder`

| Baustein | Verantwortung | Nicht verantwortlich für |
| --- | --- | --- |
| `ModeArbiter` | Modusfreigabe, Latches, Holds, Cooldowns, Übergänge und Ramp-down-Modi | Preise, Wirtschaftlichkeit oder Auswahl einer Strategie |
| `RegulationPowerController` | Leistung, Near-Zero-Regelung, Grid-Ziel, Deadbands, Schritte und wirksame Gerätegrenzen | Moduswechsel oder strategische Lade-/Entladeauswahl |
| `DeviceCommandBuilder` | finalen neutralen `DeviceCommand` und nötige Schreibabsicht erzeugen | HA-Serviceaufrufe oder erneute Fach-/Regelentscheidung |

`GridHistoryState` ist die einzige zusammengefasste Sicht auf aktuellen Netzwert,
kurze und mittlere Durchschnitte, Änderungen sowie stabile Import-/Exportzyklen.

## Plattformgrenze

ModeArbiter, RegulationPowerController, GridHistory und DeviceCommandBuilder
benötigen keine Home-Assistant-States, Services oder Zeit-Hilfsfunktionen. Aware
Zeitstempel werden über die neutrale Core-Zeitfunktion nach UTC normalisiert.
Der Coordinator erzeugt Eingaben, verdrahtet die Stufen und übergibt den fertigen
`DeviceCommand` an das konfigurierte `DeviceBackend`.

## Profile und Fähigkeiten

Profil-Dictionaries werden ausschließlich in den bestehenden Buildern in
`ModeArbiterConfig`, `RegulationPowerConfig` und `GridHistoryConfig` übersetzt.
Die Regler selbst verwenden diese typisierten Konfigurationen. Hardwaregrenzen
und technische Freigaben werden bevorzugt aus `DeviceCapabilities` übernommen;
es gibt keine Modellnamen-Abfragen in der Regelung.

## Verhaltensgarantie

Die vorhandenen Parameter und Zustandsübergänge bleiben unverändert. Das gilt
insbesondere für INPUT-nach-OUTPUT-Sperren, Flapping-Schutz, stabile Import- und
Exportzyklen, PV-/Entlade-/Passthrough-Latches, Post-Load-Drop- und
Post-Output-Overshoot-Holds, Ramp-down, Near-Zero-Regelung und profilabhängige
Grenzen.
