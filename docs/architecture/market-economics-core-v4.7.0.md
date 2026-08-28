# V4.7.0: MarketPrice und Economics im Core

- Status: Prüfung und Bereinigung für Issue #276
- Scope: Plattformgrenzen und bestehende Fachsemantik, keine neue Berechnung

## Ergebnis der Prüfung

Die mit V4.6 eingeführten Bereiche besitzen bereits die vorgesehene gerichtete
Struktur:

`Plattformzustand / Konfiguration → PriceSource → Normalizer → MarketPrice → EconomicsEngine`

Die kanonischen `MarketPrice`-, Forecast- und Gültigkeitsmodelle liegen in
`core.models.market`. `market_price.models` ist nur eine identitätserhaltende
Kompatibilitätsausgabe derselben Klassen und erzeugt kein zweites Modell.

## Plattformgrenze

- `GenericStatePriceSource` ist ein Boundary-Adapter. Er erhält lediglich einen
  aufrufbaren State-Getter und eine minimale strukturelle State-Sicht.
- Providerattribute werden ausschließlich von `ForecastAdapter`-
  Implementierungen normalisiert.
- `PriceNormalizer`, Core-Modelle, Planung und `EconomicsEngine` kennen keine
  Entities, Registries, Services oder Provider.
- Die statische Einspeisevergütung durchläuft dieselbe Normalisierung wie ein
  dynamischer Wert; ein gültiger dynamischer Preis hat weiterhin Vorrang.

## Preisvertrag

Alle Core-Preise verwenden die aktive Währung pro kWh. Es findet keine
FX-Umrechnung statt. Dabei gelten ausdrücklich:

- `0` ist ein gültiger Preis,
- negative Preise sind gültig,
- missing, unknown, unavailable, stale und invalid bleiben von `0` getrennt,
- abweichende Währungen sind ungültig,
- MWh- und Cent-Einheiten werden ausschließlich am Adapter normalisiert.

## Economics-Lifecycle

`EnergyAccumulator` erhält einen expliziten aware Zeitstempel. Dadurch ist die
Zeitabhängigkeit deterministisch und direkt mit der neutralen `Clock` testbar,
ohne dass die Engine selbst Systemzeit liest. Neustarts stellen nur abgeschlossene
Summen wieder her; das gespeicherte letzte Sample wird bewusst nicht weiter
integriert, damit während eines Ausfalls keine Energie erfunden wird.

`EnergyAccumulator.to_state()` und `EconomicsEngine.to_state()` liefern nur
versionierte Python-Daten. Diese können innerhalb des vorhandenen
StateStore-Dokuments gespeichert werden; die Core-Module kennen weder das
Home-Assistant-Store-Objekt noch Pfad, Entry-ID oder Backend-Ausnahmen.

## Bestehende Wirtschaftsregeln

Netzladekosten, PV-Opportunitätskosten, Einspeiseertrag, vermiedene
Netzbezugskosten und Batterienutzen bleiben getrennte Größen. Normale
PV-Einspeisung wird weiterhin nicht als Batterienutzen doppelt gezählt.
