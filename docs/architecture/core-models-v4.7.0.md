# V4.7.0: Gemeinsame Core-Datenmodelle

- Status: Implementierungsentscheidung für Issue #267
- Basis: `main` nach Merge von PR #293
- Zielarchitektur: `core-ha-target-architecture-v4.7.0.md`
- Scope: neutrale Modellgrenzen und kompatible Konsolidierung, kein RuntimeSnapshot

## Ergebnis

Gemeinsam verwendete, plattformunabhängige Modelle besitzen ab #267 den
kanonischen Importpfad:

```python
from custom_components.battery_smartflow_ai.core.models import ...
```

Die bisherigen Pfade bleiben während der schrittweisen V4.7-Migration als
Kompatibilitätsfassaden erhalten. Sie definieren keine zweiten Klassen, sondern
exportieren dieselben Klassenobjekte.

## Kanonische Modellgruppen

### Messwerte und fachliche Teilzustände

`core/models/states.py` definiert:

- `ValueValidity`
- `MeasuredValue[T]`
- `BatteryState`
- `GridState`
- `PVState`
- `OffGridState`
- `AdditionalBatteryState`

`MeasuredValue` trennt den Wert von seiner fachlichen Verwendbarkeit. Damit
bleiben insbesondere folgende Fälle unterscheidbar:

- echter numerischer Wert `0`
- fehlender Wert
- unbekannter Wert
- nicht verfügbarer Wert
- veralteter Wert
- ungültiger Wert

Die Modelle enthalten keine Entity-ID, HA-State-Objekte, Registries, Services
oder Übersetzungsschlüssel. Der spätere HA-Adapter ist dafür verantwortlich,
Home-Assistant-Zustände in diese neutralen Kategorien zu übersetzen.

Die Teilzustände werden in #267 noch nicht zu einem weiteren Sammelkontext
zusammengesetzt. Issue #268 führt genau eine zentrale Runtime-Eingabe ein und
ordnet dort auch Zeitstempel, Konfiguration, Forecast und Teilzustände zu.

### Strategie und Regelung

Die vorhandenen Modelle aus `regulation_models.py` und `strategy_state.py`
liegen kanonisch unter `core/models/`:

- `StrategyDecision`
- `StrategyIntent`
- `AutomaticStrategyResult`
- `ChargeCommitState`
- `ModeArbiterResult`
- `PowerControllerResult`
- `ChargeSourceAllocation`
- `DeviceCommand`
- `GridHistoryState`
- `RegulationRuntimeState`

Der bisherige Name `StrategyContext` bleibt als Alias für
`AutomaticStrategyResult` erhalten. Das Modell ist das Ergebnis der
AutomaticStrategy und keine zweite Runtime-Eingabe. Diese Einordnung verhindert
eine Doppelung mit dem in #268 entstehenden Eingabemodell.

`StrategyIntent` bleibt die fachliche gewünschte Wirkung. `DeviceCommand`
bleibt der technisch freigegebene neutrale Gerätebefehl. Die vorhandenen
Schreibflags des Commands werden in #267 nicht verändert; ihre endgültige
Zuordnung zur Core-/Backend-Grenze gehört zu #269.

### Marktpreise

Die bereits in V4.5/V4.6 konsolidierten Marktpreismodelle sind kanonische
Core-Modelle:

- `MarketPrice`
- `MarketPriceDirection`
- `MarketPriceValidity`
- `MarketPricePoint`
- `MarketPriceForecast`

Es entsteht kein zusätzliches `MarketState`, das dieselben Informationen nur
noch einmal verpackt. Insbesondere bleiben echter Nullpreis, negative Preise
und fehlende oder nicht verfügbare Preise unterscheidbar.

Der historische Importpfad `market_price.models` bleibt kompatibel und
exportiert dieselben Klassenobjekte.

### Wirtschaft

Die vorhandenen neutralen Modelle in `economics.py` bleiben gültig:

- `EconomicEnergyFlows`
- `PriceableEnergyFlows`
- `EconomicPowerFlows`
- `EnergyAccumulatorSnapshot`
- `EnergyAccumulationResult`
- `EconomicsSnapshot`

Sie werden in #267 nicht durch ein allgemeines `EconomicsState` dupliziert.
Die spätere physische Zuordnung des Economics-Lifecycles und seiner Persistenz
erfolgt mit dem dafür vorgesehenen Issue #276.

### Planung

Die vorhandenen Planungsmodelle wie `LearnedChargePlan`,
`LearningReadiness` und normalisierte Marktpreisintervalle werden nicht in ein
inhaltsleeres `PlanningState` kopiert. Issue #268 bindet die tatsächlich von
der Decision Engine benötigten Planungsdaten in die zentrale Eingabe ein.

### Gerätefähigkeiten

`DeviceCapabilities` beschreibt ausschließlich Fähigkeiten und technische
Grenzen, die der Core benötigt:

- maximale Eingangs- und Ausgangsleistung
- Passthrough-Unterstützung
- schneller Moduswechsel
- Off-Grid-Socket und Off-Grid-Input
- interne Off-Grid-Versorgungsgrenze

Das Modell enthält weder Hersteller noch Modellname noch Entity- oder
Serviceinformationen. `from_profile()` bildet das bestehende V4.6-Profil-
Dictionary verlustfrei auf diese Teilmenge ab. Das Profil-Dictionary selbst
bleibt in #267 unverändert; seine schrittweise Typisierung gehört zu #272.

## Kompatibilitätsregeln

- Bestehende Imports aus `regulation_models.py`, `strategy_state.py` und
  `market_price/models.py` bleiben funktionsfähig.
- Die Fassaden exportieren dieselben Klassenobjekte; es gibt keine parallelen
  Dataclass-Definitionen und keine Konvertierung im laufenden Steuerungspfad.
- Feldnamen, Standardwerte, Mutable-/Frozen-Verhalten und Command-Semantik der
  bestehenden Modelle bleiben unverändert.
- Store-, Config- und Diagnoseformate ändern sich nicht.
- Der Coordinator baut in #267 noch keinen neuen Snapshot.
- Kein Gerätelimit und keine Capability wird neu interpretiert.

## Nachweis

Die Core-Modelltests prüfen:

- Instanziierung ohne Home-Assistant-Objekte
- keine `homeassistant`-Imports unter `core/models/`
- explizite Unterscheidung von `0` und nicht verfügbarem Wert
- neutrale Abbildung vorhandener Geräteprofile
- Identität der alten und neuen Importpfade
- unveränderte Marktpreissemantik für Nullpreise

Die vollständige Regressionstestsuite schützt zusätzlich das bestehende
Strategie-, Regelungs-, Marktpreis-, Wirtschafts- und Home-Assistant-Verhalten.

## Bewusst nicht Teil von #267

- kein `RuntimeSnapshot`; dieser entsteht in #268
- keine Umstellung des Coordinators auf die neuen Teilzustände
- keine neue Command-Ausführung oder DeviceBackend-Implementierung
- keine StateStore- oder Clock-Abstraktion
- keine vollständige Typisierung der Geräteprofile
- keine Änderung an Planning- oder Economics-Lifecycle
- keine neue Strategie, Regelung oder Geräteunterstützung
