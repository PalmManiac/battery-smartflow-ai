# DeviceProfile und DeviceCapabilities in V4.7.0

Issue #272 trennt technische Fähigkeiten von Regel-Tuning, ohne den bestehenden
Profil-, Options- oder Diagnosevertrag zu verändern.

## Modell

```text
DeviceProfile
  |-- key / label                Auswahl und Darstellung
  |-- DeviceCapabilities        Fähigkeiten und technische Grenzen
  `-- settings                  Regel-, Schutz- und Backend-Tuning

DeviceProfile.as_legacy_mapping()
  `-- unverändertes V4.6-Dictionary für UI, Overrides und Diagnose
```

`DeviceProfile` und `DeviceCapabilities` liegen im neutralen Core und können
ohne Home Assistant instanziiert und getestet werden. `settings` ist eine
unveränderliche Mapping-Sicht. Damit gibt es im laufenden Modell einen klaren
Besitzer, während die etablierte Dictionary-Darstellung kompatibel bleibt.

## Verantwortlichkeiten

### DeviceCapabilities

Capabilities beantworten, was ein Backend beziehungsweise Gerät technisch
kann. Dazu gehören:

- maximale Eingangs- und Ausgangsleistung
- Laden, Entladen, AC-Laden und Leistungsgrenzen
- Passthrough
- DC-PV-/Hauslast-Passthrough als bestehende, engere Teilfähigkeit
- schneller Moduswechsel
- neutrales OUTPUT 0
- sichere INPUT-Keepalive-Leistung
- erforderlicher stabiler Export vor INPUT
- Off-Grid-Socket und Off-Grid-Input
- maximale interne Off-Grid-Versorgung
- MPPT-Clipping ohne OUTPUT

Die Modelle enthalten weder Hersteller- noch Modellnamen, Entity-IDs, Services
oder Home-Assistant-Objekte.

### DeviceProfile.settings

Settings beschreiben das unveränderte Verhalten, nicht die Existenz einer
Gerätefähigkeit:

- Grid-History- und Hystereseparameter
- ModeArbiter-Zeiten und Zyklusgrenzen
- Charge-/Discharge-Reglerparameter
- Ziel-Netzbezug, Export-Guard und Keepalive-Schwellen
- Schutz- und SoC-Wiederfreigaberegeln
- Off-Grid-Aktivitätsschwellen
- bestehendes DC-PV-/Hauslast-Passthrough-Tuning

Kein Wert wurde in #272 neu abgestimmt.

## Core-Verwendung

- `RuntimeSnapshot.capabilities` stellt die neutrale Capability-Sicht bereit.
- Die DecisionEngine entscheidet Passthrough über
  `ctx.capabilities.supports_passthrough`, nicht über einen Modellnamen.
- Der ModeArbiter erhält Fähigkeiten typisiert; seine Zeiten und Zähler kommen
  weiterhin aus den Settings.
- Der RegulationPowerController erhält technische Leistungsgrenzen typisiert;
  KP-, Deadband- und Step-Werte bleiben Settings.
- Der Coordinator verwendet die typisierte Off-Grid- und MPPT-Sicht. Die
  Dictionary-Fassade bleibt für Options-Overrides und bestehende Diagnosen.

Strategy, MarketPrice und Economics erhalten dadurch kein neues Zendure-Wissen.

## Legacy- und Übergangsfelder

Die fünf Felder

- `DEADBAND_W`
- `KP_UP`
- `KP_DOWN`
- `MAX_STEP_UP`
- `MAX_STEP_DOWN`

sind keine kanonischen V4.7-Reglerwerte. Sie bleiben ausschließlich erhalten,
damit alte gespeicherte Overrides und die bereits vorhandenen gerichteten
Fallbacks weiter funktionieren. Neue Profile sollen die getrennten
`CHARGE_*`- und `DISCHARGE_*`-Felder setzen.

Die Aktivierung `PV_HOUSELOAD_PASSTHROUGH` ist als engere Capability typisiert.
Die übrigen `PV_HOUSELOAD_PASSTHROUGH_*`-Tuning-Schlüssel und historischen `sf800_*`-
Persistenz-/Diagnosenamen bleiben ebenfalls kompatibel, solange ihre
zustandsbehaftete Regelung noch im Coordinator liegt. Die fachliche Freigabe
erfolgt bereits über die neutrale Passthrough-Capability. Eine Umbenennung der
persistierten Keys wäre eine eigene Migration und gehört nicht in #272.

## Registry und Fallback

`DEVICE_PROFILE_MODELS` ist die typisierte V4.7-Registry. Das bisherige
`DEVICE_PROFILES` bleibt als stabile Mapping-Fassade verfügbar. Für unbekannte
Profil-IDs bleibt `SF2400AC` unverändert der Default.

Alle elf vorhandenen Profile werden in Tests vom typisierten Modell zurück in
die alte Mapping-Form überführt und müssen dabei exakt denselben Schlüssel-
und Wertebestand liefern. Auch Hardwaregrenzen und Profil-Overrides bleiben
damit unverändert.

## Erweiterung um weitere Hersteller

Ein späteres Profil benötigt:

1. neutrale `DeviceCapabilities`,
2. bestätigte technische Limits,
3. explizite Settings für tatsächlich abweichendes Regelverhalten und
4. ein separates Backend für die technische Befehlsausführung.

Core-Strategien dürfen dafür weder Hersteller- noch Modellabfragen erhalten.
#272 führt kein weiteres Backend und keinen neuen Hersteller ein.
