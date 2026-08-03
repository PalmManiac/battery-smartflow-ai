# 📘 Battery SmartFlow AI – Anleitung

**Intelligente, wirtschaftliche und stabile Steuerung für Zendure SolarFlow Systeme in Home Assistant**

---

## Inhaltsverzeichnis

* [Kapitel 1 – Was macht Battery SmartFlow AI?](#kapitel-1--was-macht-battery-smartflow-ai)
* [Kapitel 2 – Zwingende Voraussetzungen](#kapitel-2--zwingende-voraussetzungen)
* [Kapitel 3 – Installation](#kapitel-3--installation)
* [Kapitel 4 – Konfiguration der Integration](#kapitel-4--konfiguration-der-integration)
* [Kapitel 5 – Betriebsmodi & Arbeitsweise](#kapitel-5--betriebsmodi--arbeitsweise)
* [Kapitel 6 – Sensoren & Steuerelemente](#kapitel-6--sensoren--steuerelemente)
* [Kapitel 7 – Regelprofil bearbeiten](#kapitel-7--regelprofil-bearbeiten)
* [Kapitel 8 – Technischer Hintergrund](#kapitel-8--technischer-hintergrund)
* [Kapitel 9 – FAQ & typische Probleme](#kapitel-9--faq--typische-probleme)
* [Kapitel 10 – Best Practices](#kapitel-10--best-practices--empfohlene-einstellungen)
* [Anhang 1 – Geräteprofil-Parameter](#anhang-1--geräteprofil-parameter)
* [Anhang 2 – Wichtige Diagnosewerte für Support](#anhang-2--wichtige-diagnosewerte-für-support)

---

# Kapitel 1 – Was macht Battery SmartFlow AI?

**Battery SmartFlow AI** ist eine Home-Assistant-Integration zur intelligenten Steuerung von Zendure SolarFlow Batteriesystemen.

Sie verbindet Batterie, Photovoltaik, Hausverbrauch und – optional – dynamische Strompreise, PV-Prognosen, zusätzliche Akkusysteme und Off-Grid-Verbraucher zu einem gemeinsamen Gesamtsystem.

Auf Basis dieser Informationen entscheidet die Integration automatisch:

* wann geladen wird
* wann entladen wird
* wie stark geladen oder entladen wird
* wann Stillstand sinnvoller ist
* wann Schutzfunktionen Vorrang haben
* wann technische Haltezustände sinnvoll sind
* wann eine Off-Grid-/Inselsteckdose diagnostisch berücksichtigt werden muss

---

## 🎯 Ziel der Integration

Battery SmartFlow AI versucht nicht einfach nur, möglichst oft zu laden oder zu entladen.

Das Ziel ist ein ausgewogenes Zusammenspiel aus:

| Ziel                  | Bedeutung                                      |
| --------------------- | ---------------------------------------------- |
| 💶 Wirtschaftlichkeit | günstige Preise nutzen, teure Preise vermeiden |
| ☀️ PV-Nutzung         | PV-Überschuss sinnvoll speichern               |
| 🏠 Hauslastdeckung    | Netzbezug reduzieren                           |
| 🔋 Batterieschutz     | SoC- und Zellschutz beachten                   |
| ⚙️ Regelstabilität    | unnötiges INPUT-/OUTPUT-Flattern vermeiden     |
| 🔍 Transparenz        | Entscheidungen nachvollziehbar machen          |

> [!TIP]
> Das beste Ergebnis ist nicht immer jeder einzelne Messwert exakt bei `0 W`.
> V4.3.0 regelt nahe am wirtschaftlichen Zielpunkt; je nach Geräteprofil und
> Einspeisevergütung kann dieser leicht auf der Bezugs- oder Einspeiseseite liegen.

---

## 🧠 Grundprinzip

Battery SmartFlow AI trennt zwei Ebenen:

### 1. Strategische Entscheidung

Die strategische Ebene entscheidet:

> **Was soll grundsätzlich passieren?**

Beispiele:

* PV-Überschuss laden
* Hauslast decken
* günstiges Preisfenster zum Laden nutzen
* teures Preisfenster zum Entladen nutzen
* Notladung auslösen
* Off-Grid-Last getrennt vom Netzregelpfad beobachten
* wegen Schutzbedingungen nichts tun

### 2. Technische Leistungsregelung

Die technische Ebene entscheidet:

> **Wie wird diese Entscheidung stabil am Gerät umgesetzt?**

Beispiele:

* Darf jetzt wirklich von INPUT nach OUTPUT gewechselt werden?
* Ist der Export stabil genug für PV-Ladung?
* Muss OUTPUT nach einem Lastabfall langsam heruntergeregelt werden?
* Soll ein Befehl erneut geschrieben werden oder kann er übersprungen werden?
* Wie stark darf die Leistung pro Regelzyklus steigen oder fallen?

Diese Trennung bildet in V4.3.0 den verbindlichen Regelpfad für alle Installationen.

---

## ✨ Wichtigste Neuerungen in V4.3.0

Battery SmartFlow AI hat sich seit den frühen Versionen deutlich weiterentwickelt.

Wichtige Neuerungen gegenüber V4.2.8:

* 🧠 einheitliche, saisonunabhängige Automatik
* ☀️ eigener Autarkiemodus statt des bisherigen Sommermodus
* 🔒 AC-Ladebindung für geplante und wirtschaftlich gestartete Netzladungen
* 🎯 präzisere netzgeführte Lade- und Entladeregelung nahe 0 W
* ⚖️ wirtschaftlich begründete leichte Einspeisung statt unnötigem Netzbezug
* 💶 Einspeisevergütung als Kostenbasis bei PV-Ladung
* 🔀 gewichteter Mischpreis bei gleichzeitiger PV- und Netzladung
* 🔍 getrennte strategische, sichtbare und technische Diagnosezustände
* 🧩 neue Profile für SolarFlow 3000/4000 Mix AC+ und 4000 Mix Pro
* ⚡ Leistungsgrenzen bis 4000 W bei weiterhin gerätespezifischem Sicherheitsdeckel

---

## 🧭 Kurz gesagt

Battery SmartFlow AI soll nicht möglichst viel schalten, sondern:

> **Erst verstehen, dann entscheiden, dann technisch sauber regeln.**

---

# Kapitel 2 – Zwingende Voraussetzungen

Damit Battery SmartFlow AI korrekt und stabil arbeiten kann, müssen bestimmte Einstellungen zwingend beachtet werden.

Die Integration übernimmt die vollständige Steuerung des Zendure-Systems.
Parallele oder widersprüchliche Steuerungen führen zu Instabilität.

> [!IMPORTANT]
> Wenn das System nicht wie erwartet arbeitet, sollten zuerst die Voraussetzungen in diesem Kapitel geprüft werden.
> Viele Fehler entstehen durch parallele Regelungen außerhalb von Battery SmartFlow AI.

---

## 1️⃣ Zendure Original-App

In der offiziellen Zendure-App müssen folgende Punkte geprüft werden:

* Ladeleistung auf Maximum setzen
* Entladeleistung auf Maximum setzen
* HEMS deaktivieren
* keine zeitgesteuerten Lade-/Entladepläne aktivieren
* keine externe Leistungsbegrenzung aktivieren

---

### ⚠ Hardwareliste prüfen

In der Zendure-App sollte die Hardwarekonfiguration möglichst sauber sein.

Besonders kritisch sind zusätzliche Steuer- oder Messkomponenten, die selbst Einfluss auf das Regelverhalten nehmen können.

Problematisch können sein:

* Shelly Pro 3EM direkt in Zendure
* externe Smart Meter / Zähler
* Zendure eigene Messsensoren mit HEMS-Regelung
* sonstige Leistungs- oder Netzsensoren, die Zendure direkt steuern
* aktive App-Automationen

Battery SmartFlow AI benötigt eine möglichst saubere Hardwarekonfiguration ohne parallele Steuerinstanzen.

---

## 2️⃣ Zendure Home-Assistant Integration

Folgende Einstellungen sind erforderlich:

* Energie-Export: **Erlaubt**
* kein P1-Sensor in der Zendure-Integration auswählen
* Zendure Manager: **deaktiviert**
* keine parallelen Automationen, die AC-Modus oder Leistungsgrenzen verändern

Falsche Einstellungen können führen zu:

* Entladeabbrüchen
* blockierten AC-Modi
* Wechsel zwischen INPUT/OUTPUT
* falschen Zuständen
* Fehlinterpretationen
* stark erhöhter Schaltzahl

---

## 3️⃣ Strompreis-Integration

Eine Strompreis-Integration ist optional, aber für wirtschaftliche Preislogik erforderlich.

Unterstützt werden grundsätzlich alle Sensoren, die einen aktuellen Strompreis und optional Preisprognosedaten liefern.

Typische Quellen:

* Tibber
* EPEX
* Octopus Energy
* Octopus Energy Forecast API
* eigene Template-Sensoren

Ohne Strompreis bleibt weiterhin möglich:

* PV-Überschussladung
* Hauslastdeckung im Autarkiemodus
* manuelle Steuerung
* Schutzlogik
* Off-Grid-Erkennung
* Diagnose

Ohne Strompreis stehen preisbasierte Lade- und Entladeentscheidungen nicht oder nur eingeschränkt zur Verfügung.

---

## 4️⃣ PV-Prognose

PV-Prognosen sind optional.

Wenn passende Prognosesensoren vorhanden sind, kann Battery SmartFlow AI sie für bessere Ladeplanung nutzen.

Typische Sensoren:

* PV-Prognose heute
* PV-Prognose morgen

Die Prognose wird nicht als alleinige Wahrheit behandelt. Sie ist ein zusätzlicher Planungs-Input.

Battery SmartFlow AI berücksichtigt weiterhin:

* reale aktuelle PV-Leistung
* Netzbezug
* Netzeinspeisung
* Hauslast
* SoC
* Preisfenster
* gelernte Verbrauchsdaten

Wenn keine Prognose konfiguriert ist, funktioniert die Integration weiterhin.

---

## 🛡️ Wichtig

Battery SmartFlow AI ist kein Ersatz für die Schutzfunktionen des Herstellers.

Die Integration setzt Entscheidungen in Home Assistant um. Die eigentliche Hardware, das BMS und die Zendure-Firmware behalten ihre eigenen Schutzmechanismen.

Trotzdem sollten alle Grenzwerte sinnvoll gesetzt werden.

---

# Kapitel 3 – Installation

Battery SmartFlow AI wird über HACS installiert.

---

## 🚀 Schnellinstallation über HACS

Über folgenden Button kann das Repository direkt in HACS geöffnet werden:

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=PalmManiac&repository=battery-smartflow-ai&category=integration)

Danach:

1. Repository hinzufügen
2. Integration installieren
3. Home Assistant neu starten
4. Integration über Geräte & Dienste hinzufügen

---

## 🔧 Manuelle Installation über HACS

Falls der Direktlink nicht genutzt wird:

1. HACS öffnen
2. ⋮ → **Benutzerdefinierte Repositories**
3. Repository-URL einfügen:

```text
https://github.com/PalmManiac/battery-smartflow-ai
```

4. Typ: **Integration** auswählen
5. Hinzufügen bestätigen
6. In HACS nach **Battery SmartFlow AI** suchen
7. Installieren

---

## 🔄 Neustart erforderlich

Nach der Installation muss Home Assistant neu gestartet werden.

Erst nach dem Neustart steht die Integration unter:

```text
Einstellungen → Geräte & Dienste → Integration hinzufügen
```

zur Verfügung.

---

## Hinweis zum alten Namen

Battery SmartFlow AI hieß früher **Zendure SmartFlow AI**.

Wenn eine sehr alte Version installiert war, kann es sein, dass in Home Assistant noch alte Namen oder alte Integrationseinträge sichtbar sind.

Wichtig ist:

* der neue Repository-Name lautet `battery-smartflow-ai`
* die Domain lautet `battery_smartflow_ai`
* alte manuelle Installationen sollten sauber entfernt werden
* nach Umbenennungen ist ein Neustart sinnvoll

Falls Home Assistant noch einen alten Anzeigenamen zeigt, obwohl die neue Integration korrekt geladen ist, kann das an alten gespeicherten Integrationseinträgen liegen.

---

# Kapitel 4 – Konfiguration der Integration

Nach der Installation wird Battery SmartFlow AI über Home Assistant eingerichtet:

```text
Einstellungen → Geräte & Dienste → Integration hinzufügen → Battery SmartFlow AI
```

Ein Beispiel für den Integrationseintrag:

![Integrationseintrag](images/config_00_config.png)

> [!NOTE]
> Dieser Screenshot zeigt den Integrationseintrag in Home Assistant.
> Die eigentliche Konfiguration erfolgt über den Einrichtungsdialog und den späteren Optionen-/Profilbereich.

---

## 4.1 Geräteprofil & Basisdaten

![Basis-Konfiguration](images/config_01_basic.png)

---

### Geräteprofil

Hier wird das passende Profil für das verwendete Zendure-Modell gewählt.

Das Profil definiert:

* Dynamik der Leistungsregelung
* Sicherheitsgrenzen
* Regelparameter
* Hardware-Limits
* Low-SoC-Verhalten
* Off-Grid-Fähigkeiten
* Mode-Switch-Verhalten

Aktuell unterstützte bzw. vorgesehene Profile:

| Profil                    | Typischer Einsatz                                      |
| ------------------------- | ------------------------------------------------------ |
| SolarFlow 800 Pro         | 800-W-System mit eigenem Stabilitätsprofil             |
| SolarFlow 800 Pro 2       | 800-W-System mit besonders konservativer Abstimmung    |
| SolarFlow 1600 AC+        | 1600-W-AC-System                                       |
| SolarFlow 2400 AC         | reiner AC-gekoppelter Speicher der 2400-W-Klasse       |
| SolarFlow 2400 AC+        | AC+-Variante der 2400-W-Klasse                         |
| SolarFlow 2400 Pro        | 2400-Pro-System                                        |
| SolarFlow 3000 Mix AC+    | AC-gekoppelter Speicher, 3000 W AC / 3680 W Off-Grid  |
| SolarFlow 4000 Mix AC+    | AC-gekoppelter Speicher, 4000 W AC / 3680 W Off-Grid  |
| SolarFlow 4000 Mix Pro    | AC-gekoppelter Speicher, 4000 W AC / 3680 W Off-Grid  |
| Hyper 2000                | Hyper-System                                           |
| HUB 2000                  | HUB-System                                             |

> [!IMPORTANT]
> Wähle immer das Profil, das deinem System am nächsten kommt.
> Ein falsches Profil kann zu zu aggressiver oder zu träger Regelung führen.

Die drei Mix-Modelle sind reine AC-gekoppelte Batteriespeicher ohne direkten
PV-Anschluss. Sie verwenden deshalb die neutrale Regelabstimmung des
SF2400AC, jeweils mit ihren bestätigten eigenen Leistungsgrenzen.

> [!WARNING]
> Bei den neuen 3000er- und 4000er-Modellen kann die praktische Nutzung derzeit
> noch durch ein Firmwareproblem eingeschränkt sein. Eine Token-Verbindung zu
> Z-HA kann zustande kommen, ohne dass das Gerät anschließend aktuelle Daten
> liefert. Über MQTT angelegte Entitäten sind keine verlässliche Alternative,
> da dieser Weg von Zendure nicht mehr unterstützt und nicht zuverlässig
> aktualisiert wird.

---

### Batterie-SoC Sensor

Sensor mit dem aktuellen Ladezustand der Batterie in Prozent.

* Einheit: %
* Pflichtfeld
* Grundlage aller Entscheidungen

Ohne gültigen SoC ist keine Steuerung möglich.

Der SoC wird genutzt für:

* SoC-Minimum
* SoC-Maximum
* Notladung
* Entladefreigabe
* Lernplanung
* Schutzentscheidungen
* verfügbare Batterieenergie

---

### SoC-Limit Status

Optionaler Sensor aus der Zendure-Integration.

Er meldet aktive BMS-Grenzen wie:

* Ladesperre
* Entladesperre

Battery SmartFlow AI respektiert diese Hardware-Grenzen.

Typische Zustände:

| Zustand             | Bedeutung                                |
| ------------------- | ---------------------------------------- |
| kein Limit aktiv    | Laden und Entladen grundsätzlich möglich |
| oberes Limit aktiv  | Laden wird blockiert                     |
| unteres Limit aktiv | Entladen wird blockiert                  |
| nicht konfiguriert  | Sensor wurde nicht ausgewählt            |

---

### Kapazität pro Akku-Pack

Angabe der nutzbaren Kapazität eines einzelnen Akku-Packs in kWh.

Dieser Wert ist entscheidend für:

* kWh-Delta-Berechnung
* Ladezeitabschätzung
* Profit-Berechnung
* Lernplanung
* Planung vor Preisspitzen
* verfügbare Batterieenergie

Bei mehreren installierten Akku-Packs wird dieser Wert mit der Pack-Anzahl multipliziert.

Beispiel:

```text
2 Akkupacks × 2,88 kWh = 5,76 kWh
```

> [!WARNING]
> Eine falsche Kapazitätsangabe führt zu falschen wirtschaftlichen Ergebnissen und ungenauer Ladeplanung.

---

### Batterie-Leistungssensor

Der Batterie-Leistungssensor ist wichtig für die Bilanzierung.

Empfohlenes Vorzeichen:

| Zustand          | Wert    |
| ---------------- | ------- |
| Batterie entlädt | positiv |
| Batterie lädt    | negativ |

Dieser Sensor wird genutzt für:

* Erkennung realer Ladung
* Erkennung realer Entladung
* Hauslastberechnung
* Lernplanung
* Ladepreisberechnung
* Profit-/Ersparnisberechnung

Wenn das Vorzeichen falsch ist, können Berechnungen und Diagnosen unplausibel werden.

---

### Installierte PV-Leistung

Hier wird die theoretisch installierte Modulleistung der Anlage in Wp angegeben.

Der Wert unterstützt die relative Einordnung der aktuellen PV-Leistung und den
Automatikkontext. Er schaltet keine getrennte Sommer- oder Winterstrategie um.

---

### PV-Leistung Sensor

Sensor mit aktueller PV-Leistung in Watt.

Wird genutzt für:

* Überschusserkennung
* dynamische Regelung
* PV-Gewichtung der Automatik
* Lernplanungskontext
* PV-Hauslastdeckung
* Off-Grid-Kontext
* Prognosevergleich

---

### Nutzung ohne PV-Anlage

Wenn keine PV-Anlage vorhanden ist, kann ein einfacher Template-Sensor verwendet werden, der dauerhaft **0 W** liefert.

```yaml
template:
  - sensor:
      - name: "Dummy PV Power"
        unit_of_measurement: "W"
        state: "0"
```

---

## 4.2 Preis & AC

![Preis & AC](images/config_02_price_ac.png)

---

### Preisverlauf

Der Preisverlauf ist optional, aber für Planung und dynamische Preislogik sehr wichtig.

Er enthält künftige Preiswerte, z. B. für die nächsten Stunden oder den nächsten Tag.

Battery SmartFlow AI nutzt diese Daten für:

* Tal-Erkennung
* Peak-Erkennung
* geplante Ladung
* Lernplanung
* wirtschaftliche Entladung
* Preisfensterbewertung

---

### Aktueller Strompreis

Der aktuelle Strompreis wird für Entscheidungen im aktuellen Moment genutzt.

Beispiele:

* Ist der aktuelle Preis sehr günstig?
* Ist der aktuelle Preis hoch genug zum Entladen?
* Lohnt sich eine Entladung gegenüber dem gespeicherten Ladepreis?
* Ist eine Notladung oder geplante Ladung wirtschaftlich sinnvoll?

---

### Einspeisevergütung

Die optionale Einspeisevergütung wird in ganzer Währung pro kWh eingetragen.

Beispiel:

```text
0,122 €/kWh = 12,2 ct/kWh
```

Sie wird für zwei wirtschaftliche Bewertungen genutzt:

* Eine optionale Netzladung soll vorhandene PV-Ladung nur verdrängen, wenn der
  Netzstrom günstiger als die entgangene Einspeisevergütung ist.
* Bei PV-Ladung wird die Vergütung als entgangener Erlös in den durchschnittlichen
  Ladepreis des Akkus eingerechnet.

Ohne eingetragene Einspeisevergütung wird PV-Ladung weiterhin mit `0,00 €/kWh`
bewertet.

---

### Zendure AC-Betriebsmodus

Der AC-Modus ist die zentrale Umschaltung des Zendure-Systems.

Typischerweise gibt es:

* INPUT
* OUTPUT

INPUT bedeutet in der Regel:

* Batterie laden
* AC-Ladepfad aktiv

OUTPUT bedeutet in der Regel:

* Batterie entladen
* Hauslastdeckung
* technischer Versorgungspfad

Battery SmartFlow AI setzt diesen Modus automatisch.

---

### Zendure Ladeleistung

Die Ladeleistungs-Entität ist eine Number-Entität.

Battery SmartFlow AI setzt hier die gewünschte Ladeleistung in Watt.

---

### Zendure Entladeleistung

Die Entladeleistungs-Entität ist ebenfalls eine Number-Entität.

Battery SmartFlow AI setzt hier die gewünschte Entladeleistung in Watt.

---

## 4.3 Netzmessung

![Netzmessung – Modus](images/config_03_grid_mode.png)

Die Netzmessung ist entscheidend für eine gute Regelung.

Battery SmartFlow AI unterstützt drei Varianten.

---

### Kein Netzsensor

In diesem Modus kann Battery SmartFlow AI nur eingeschränkt arbeiten.

Möglich sind dann vor allem:

* SoC-basierte Entscheidungen
* Preislogik
* Notladung
* manuelle Steuerung

Nicht optimal möglich sind:

* genaue Hauslastdeckung
* genaue PV-Überschusserkennung
* stabile 0-W-Regelung
* präzise netzgeführte Leistungsregelung

---

### Ein Sensor (+ / −)

Ein kombinierter Netzsensor liefert:

| Wert    | Bedeutung   |
| ------- | ----------- |
| positiv | Netzbezug   |
| negativ | Einspeisung |

Beispiel:

```text
+250 W = Netzbezug
-400 W = Netzeinspeisung
```

Battery SmartFlow AI rechnet daraus intern Bezug und Einspeisung.

---

### Zwei Sensoren

Empfohlen ist der Split-Modus mit zwei getrennten Sensoren:

* Netzbezug
* Netzeinspeisung

Beide Sensoren liefern positive Werte.

Beispiel:

```text
Netzbezug: 250 W
Netzeinspeisung: 0 W
```

oder:

```text
Netzbezug: 0 W
Netzeinspeisung: 400 W
```

Diese Variante ist am eindeutigsten und für die Regelung besonders gut geeignet.

---

## 4.4 Netzsensoren im Split-Modus

![Netzsensorauswahl](images/config_04_grid_split.png)

Im Split-Modus müssen zwei Sensoren ausgewählt werden:

* Netzbezug
* Netzeinspeisung

> [!WARNING]
> Achte darauf, dass die Sensoren nicht vertauscht werden.
> Vertauschte Sensoren führen zu falschen Entscheidungen.

Typische Folgen vertauschter Sensoren:

* Laden bei Netzbezug
* Entladen bei Einspeisung
* falsche Hauslast
* unplausible Diagnosewerte
* instabile Regelung

---

## 4.5 Zusatzakku-Erkennung

Battery SmartFlow AI kann optional ein weiteres Akkusystem beobachten.

Dafür gibt es zwei optionale Sensoren:

* Zusatzakku Ladeleistung
* Zusatzakku Entladeleistung

Diese Funktion ist wichtig, wenn mehrere Batteriesysteme im Haus vorhanden sind, die aber noch nicht koordiniert gemeinsam gesteuert werden.

---

### Zusatzakku lädt

Wenn ein anderer Akku gerade lädt, kann Battery SmartFlow AI die eigene Entladung blockieren.

Grund:

> Ein Akku soll nicht indirekt den anderen Akku laden.

Beispiel:

```text
Zusatzakku lädt mit 500 W
Battery SmartFlow AI würde eigentlich entladen
→ Entladung wird blockiert
```

---

### Zusatzakku entlädt

Wenn ein anderer Akku gerade entlädt, kann Battery SmartFlow AI das eigene Laden blockieren.

Grund:

> Die Entladung des anderen Akkus darf nicht fälschlich als PV-Überschuss interpretiert werden.

Beispiel:

```text
Zusatzakku entlädt mit 400 W
Netzsensor zeigt dadurch scheinbar weniger Bezug
Battery SmartFlow AI könnte sonst PV-Laden starten
→ Laden wird blockiert
```

---

### Ziel der Zusatzakku-Erkennung

Die Funktion verhindert:

* Akku-zu-Akku-Laden
* falsche PV-Überschusserkennung
* unnötige Lade-/Entladezyklen
* Konflikte zwischen getrennten Batteriesystemen

> [!NOTE]
> Eine echte koordinierte Multi-Battery-Steuerung ist damit noch nicht gemeint.
> Diese ist für eine spätere größere Version vorgesehen.

---

## 4.6 Off-Grid-/Inselsteckdose

Einige Zendure-Systeme besitzen eine Off-Grid- bzw. Inselsteckdose.

Battery SmartFlow AI kann diese optional auswerten.

Dazu gibt es zwei optionale Konfigurationsfelder:

* Off-Grid-Leistung / Inselsteckdose
* Off-Grid-Modus

![Off-Grid-Konfiguration](images/conf_06_offgrid.png)

---

### Off-Grid-Leistung

Der Off-Grid-Leistungssensor meldet die Leistung an der Inselsteckdose.

Für bestätigte 2400er-Zendure-Systeme gilt:

* positive Werte bedeuten aktive Last an der Inselsteckdose

Beispiel:

```text
Off-Grid-Leistung: 520 W
→ an der Inselsteckdose hängt eine Last von ca. 520 W
```

Battery SmartFlow AI nutzt diese Information für eine getrennte Diagnose.
Eine erkannte Off-Grid-Last blockiert eine ansonsten gültige Lade- oder
Entladestrategie nicht pauschal.

---

### Off-Grid-Modus

Der Off-Grid-Modus ist ein optionaler Select-Sensor.

Typische interne Zustände:

| Zustand  | Bedeutung                   |
| -------- | --------------------------- |
| `off`    | Off-Grid aus                |
| `normal` | Normalbetrieb               |
| `eco`    | ökonomischer Off-Grid-Modus |

Battery SmartFlow AI liest diesen Modus nur.

> [!IMPORTANT]
> Battery SmartFlow AI setzt oder verändert den Off-Grid-Modus nicht.
> Die Steuerung bleibt bei Zendure App, ZHA oder der verwendeten Zendure-Integration.

---

### Verhalten bei aktiver Off-Grid-Last

Eine aktive Off-Grid-Last wird unabhängig von der AC-Strategie beobachtet:

```text
offgrid_load_observed
```

Das bedeutet:

* Off-Grid-Last erkannt
* die gültige Lade- oder Entladestrategie bleibt bestehen
* kleine und dauerhafte Insel-Lasten blockieren AC-Ladung nicht pauschal
* SoC- und Zellschutz bleiben aktiv
* Notladung und manuelle Vorgaben behalten ihre Priorität

---

### Was beeinflusst Off-Grid?

Off-Grid-Leistung wird als eigener Gerätepfad diagnostisch erfasst. Sie wird
nicht als zusätzliche Hauslast in den Netzregelpfad eingerechnet und überstimmt
keine gültigen Kandidaten für:

* Preisladung
* Tal-Ladung
* Lernplanung
* geplante Netzladung
* sehr-billig-Ladung

---

### Einschränkung

Battery SmartFlow AI verändert den Off-Grid-Modus des Geräts nicht. Welche
Leistung die Inselsteckdose tatsächlich bereitstellt, bleibt von Zendure-
Firmware, Gerätegrenzen und Gerätekonfiguration abhängig.

---

## Wichtiger Hinweis zur Zendure-App

Damit Battery SmartFlow AI zuverlässig arbeiten kann, sollten in der Zendure-App keine parallelen Automationen aktiv sein.

Besonders kritisch sind:

* automatische HEMS-Regelung
* eigene Lade-/Entladepläne
* dynamische Leistungsregelung außerhalb von BSFAI
* P1-Regelung innerhalb der Zendure-Integration
* parallele Home-Assistant-Automationen auf denselben Entitäten

---

# Kapitel 5 – Betriebsmodi & Arbeitsweise

Battery SmartFlow AI bietet mehrere Betriebsmodi.

Die Modi bestimmen, welche strategischen Entscheidungen bevorzugt werden.

---

## 5.1 Betriebsmodi

---

## 🔹 Automatik

Der Automatikmodus ist der empfohlene Standardmodus.

Er kombiniert:

* PV-Leistung
* Hauslast
* SoC
* dynamische Preise
* PV-Prognose
* Lernplanung
* aktueller PV-, Preis-, Reserve- und Prognosekontext
* Schutzlogik

Die Automatik arbeitet ganzjährig mit einer gemeinsamen Strategie. Sie schaltet
nicht mehr zwischen einer Sommer- und einer Winterlogik um. Stattdessen bewertet
sie, ob die aktuelle Situation eher PV-, preis-, reserve- oder ausgewogen
orientiert ist. Die eigentliche Lade- oder Entladeentscheidung bleibt bei der
Decision Engine.

Typische Entscheidungen:

* PV-Überschuss laden
* bei hoher Last entladen
* bei günstigen Preisen laden
* bei hohen Preisen entladen
* bei schwacher PV-Prognose rechtzeitig nachladen
* bei ausreichender Batterie nichts tun
* Schutzbedingungen respektieren

Strategische Netzladung durch Planung, Lernplanung, Talpreise, sehr günstige
Preise oder Reservebedarf ist ausschließlich in der Automatik erlaubt.

---

## 🔹 Autarkiemodus

Der Autarkiemodus ist auf Autarkie und Hauslastdeckung ausgelegt.

Typische Ziele:

* vorhandene PV optimal nutzen
* Hauslast decken
* unnötigen Netzbezug reduzieren
* PV-Überschuss laden
* Akku nicht unnötig aus dem Netz laden

Im Autarkiemodus ist Entladung zur Hauslastdeckung besonders wichtig.

Normale strategische Netzladungen werden in diesem Modus nicht gestartet. Beim
Wechsel aus der Automatik in den Autarkiemodus wird eine aktive AC-Ladebindung
beendet. PV-Überschussladung, Hauslastdeckung und Schutzfunktionen bleiben aktiv.

Wenn SoC-Minimum oder Entlade-Wiederfreigabe aktiv ist, kann Entladung blockiert werden. In solchen Fällen hat die Schutzlogik Vorrang.

---

## 🔹 Manuell

Im manuellen Modus greift Battery SmartFlow AI nicht strategisch ein.

Der Nutzer kann wählen:

* Standby
* Laden
* Entladen
* konstante Entladung

Der manuelle Modus ist nützlich für:

* Tests
* Diagnose
* Sonderfälle
* manuelle Eingriffe
* Vergleich mit automatischer Regelung

Schutzmechanismen bleiben dennoch wirksam.

---

## 5.2 Adaptive Peak-Erkennung

Die adaptive Peak-Erkennung erkennt teure Preisfenster.

Dabei wird nicht nur ein fixer Preis betrachtet, sondern das Preisniveau des Tages.

Der Peak-Faktor bestimmt, ab wann ein Preis als Peak gilt.

Formel:

```text
Peak-Schwelle = max(
  Durchschnittspreis × Peak-Faktor,
  Durchschnittspreis + 0,03 €
)
```

Standardwert:

```text
1.35
```

| Peak-Faktor | Wirkung                         |
| ----------- | ------------------------------- |
| niedriger   | erkennt mehr Peaks              |
| höher       | erkennt nur starke Preisspitzen |

---

## 5.3 Entscheidungsgrund

Der Sensor **Entscheidungsgrund** erklärt, warum Battery SmartFlow AI gerade eine Entscheidung getroffen hat.

Beispiele:

```text
pv_surplus_charge
summer_cover_deficit
charge_commit_active
price_based_discharge
adaptive_peak_discharge
planning_forecast_poor
learned_charge_window_wait
soc_min_resume_block
cell_voltage_cutoff_block
```

> [!TIP]
> Wenn das System nicht das tut, was erwartet wird, sollte zuerst der Entscheidungsgrund geprüft werden.
> Für die Trennung von Strategie und technischer Umsetzung sind zusätzlich
> **Sichtbarer Zustand**, **Strategischer Grund** und **Technischer Grund** hilfreich.

---

## 5.4 Sehr-teuer- und Sehr-billig-Schwellen

Battery SmartFlow AI kann mit benutzerdefinierten Preisgrenzen arbeiten.

### Sehr-teuer-Schwelle

Diese Schwelle kann genutzt werden, um besonders teure Preisfenster zu markieren.

Sie kann Entladeentscheidungen beeinflussen.

### Sehr-billig-Schwelle

Diese Schwelle kann genutzt werden, um sehr günstige oder sogar negative Strompreise zu erkennen.

Bei sehr billigen Preisen kann eine Maximalladung sinnvoll sein.

Die Schwelle kann auch negative Werte annehmen, wenn der Tarif negative Preise liefert.

---

## 5.5 AC-Ladebindung

Eine geplante oder wirtschaftlich gestartete Netzladung erhält eine
**AC-Ladebindung**. Sie speichert unter anderem:

* Auslöser und Art der Ladung
* Ziel-SoC
* angeforderte Ladeleistung
* Start, Gültigkeit und gegebenenfalls Deadline
* zulässigen Preisbereich bei Lernplanung

Die Ladebindung verhindert, dass eine sinnvolle Ladung wegen kurzer Änderungen
von Preis, PV oder Netzleistung sofort wieder abgebrochen wird. Sie kann je nach
Plan zunächst warten, aktiv laden oder spätestens zum notwendigen Zeitpunkt
erzwingen, damit die benötigte Energie bis zur Deadline verfügbar ist.

Eine wartende Ladebindung reserviert das System nicht vollständig: PV-Ladung,
wirtschaftliche Entladung, technische Hauslastdurchleitung und Notladung können
weiterhin Vorrang erhalten.

Typische Beendigungsgründe sind:

* Ziel-SoC oder maximaler SoC erreicht
* Planungsdeadline abgelaufen
* Batterie nimmt nahe dem Ziel länger keine relevante Ladeleistung mehr an
* wirtschaftlicher Konflikt bei einer Reserve-Ladung
* Schutz- oder Sensordatenfehler
* Wechsel in Autarkie oder Manuell

PV-Leistung während einer aktiven Netzladung beendet die Ladebindung nicht. Sie
reduziert den benötigten Netzanteil und verbessert dadurch den Mischpreis.

---

## 5.6 Netzgeführte Leistungsregelung

Battery SmartFlow AI versucht nicht einfach nur, mit voller Leistung zu laden oder zu entladen.

Stattdessen wird die Leistung an der Netzsituation ausgerichtet.

Beispiele:

* bei Netzbezug kann Entladung erhöht werden
* bei Einspeisung kann Ladeleistung erhöht werden
* bei Lastabfall wird OUTPUT nicht sofort hart beendet
* bei Wolken wird INPUT nicht sofort hektisch gewechselt
* kleine Abweichungen innerhalb einer Totzone werden zunächst beruhigt
* verbleibender Netzbezug wird bei aktiver Entladung fein nachgeregelt
* PV-Ladung reduziert frühzeitig, bevor unnötiger Netzbezug entsteht

Die Regelung verbindet Totzone, Schrittbegrenzung, Netzverlauf und Haltezustände.
Dadurch kann sie näher am Zielpunkt arbeiten, ohne INPUT/OUTPUT-Flattern zu
erzeugen.

---

## 5.7 Einheitlicher V4.3-Regelpfad

Seit V4.3.0 ist die technische Regelkette für alle Installationen verbindlich:

```text
AutomaticStrategy-Kontext
→ Decision Engine
→ StrategyDecision
→ sichtbarer Zustand
→ StrategyIntent
→ ModeArbiter
→ RegulationPowerController
→ DeviceCommand
→ Home Assistant / Zendure
```

Die Automatik erzeugt dabei keine zweite Decision Engine. Sie bewertet den
Kontext und erteilt strategische Freigaben; die Decision Engine sammelt die
zulässigen Kandidaten und wählt anhand der Priorität die tatsächliche Aktion.

### Decision Engine

Entscheidet strategisch, was passieren soll.

Beispiele:

* Laden
* Entladen
* Warten
* Notladen
* Off-Grid-Kontext berücksichtigen

### StrategyDecision und sichtbarer Zustand

Das strategische Ergebnis erhält einen eindeutigen Zustand, eine Priorität und
einen ruhigen, nutzerverständlichen sichtbaren Zustand. Der ursprüngliche
Entscheidungsgrund bleibt separat als Quellgrund erhalten.

### StrategyIntent

Übersetzt die strategische Entscheidung in eine technische Absicht.

Beispiele:

```text
pv_charge
planned_charge
cover_deficit
peak_discharge
arbitrage_discharge
emergency_charge
manual_charge
passthrough
```

### ModeArbiter

Entscheidet, ob der gewünschte Modus jetzt technisch erlaubt ist.

Er berücksichtigt:

* aktuelle Netz-Historie
* stabile Import- und Exportzyklen
* Moduswechsel-Sperrzeiten
* aktive Haltezustände
* Zusatzakku-Ladung oder -Entladung
* SoC- und Zellschutz

### RegulationPowerController

Berechnet die konkrete Leistung.

Er berücksichtigt:

* Ziel-Netzbezug
* Totzone
* Regelverstärkung
* maximale Schrittweite
* vorherige Leistung
* Profilgrenzen
* kurzfristigen und mittleren Netzverlauf
* wirtschaftliches Ziel für leichten Bezug oder leichte Einspeisung

### DeviceCommand

Erzeugt den endgültigen Befehl.

Er entscheidet:

* AC-Modus
* Input-Limit
* Output-Limit
* ob ein Wert geschrieben werden muss
* ob ein Schreibvorgang übersprungen werden kann

---

## 5.8 Wirtschaftlichkeitsberechnung

Battery SmartFlow AI kann berechnen, ob eine Entladung wirtschaftlich sinnvoll ist.

Dazu wird ein gewichteter durchschnittlicher Ladepreis ermittelt.

Beispiel:

```text
Akku wurde günstig mit 0,18 €/kWh geladen
aktueller Preis liegt bei 0,32 €/kWh
→ Entladung kann wirtschaftlich sinnvoll sein
```

Die Gewinnmarge bestimmt, wie groß der Preisabstand mindestens sein sollte.

---

### Wichtig bei PV-Ladung

PV-Ladung ist wirtschaftlich nicht automatisch kostenlos. Wenn eine
Einspeisevergütung konfiguriert ist, entspricht der Ladepreis des PV-Anteils dem
entgangenen Einspeiseerlös.

Beispiel:

```text
Einspeisevergütung: 0,122 €/kWh
reine PV-Ladung:    0,122 €/kWh Speicherkosten
```

Bei gleichzeitiger PV- und Netzladung werden beide Anteile mit ihren jeweiligen
Preisen gewichtet. Negative Netzpreise bleiben dabei erhalten. Die Ladeherkunft
wird während der realen Ladung zwischengespeichert, sodass auch ein verzögert
gemeldeter SoC-Anstieg noch der richtigen Kostenbasis zugeordnet werden kann.

Ohne konfigurierte Einspeisevergütung bleibt der PV-Anteil bei `0,00 €/kWh`.

### Wirtschaftlicher Zielpunkt der Regelung

Bei PV-Ladung mit hinterlegter Einspeisevergütung bevorzugt die Regelung eine
kleine Einspeisung gegenüber unbeabsichtigtem Netzbezug. Bei Entladung ist diese
leichte Einspeiseausrichtung nur wirtschaftlich zulässig, wenn der Wert der
gespeicherten Energie einschließlich Sicherheitsabstand unter der
Einspeisevergütung liegt. Strategische Netz-, Not- und manuelle Ladungen werden
davon nicht beeinflusst.

---

### Technische Unterstützungsmodi

Einige Zustände sind technisch sinnvoll, aber keine wirtschaftliche Entladung.

Beispiel:

* PV-Hauslast-Passthrough

Diese werden nicht als wirtschaftliche Preisentladung gezählt.

---

## 5.9 Transparenz-Sensoren

Battery SmartFlow AI stellt viele Sensoren bereit, um Entscheidungen nachvollziehbar zu machen.

Besonders hilfreich sind:

* Entscheidungsgrund
* KI-Status
* KI-Empfehlung
* Engine-Status
* effektive Entladeschwelle
* ökonomische Entladeschwelle
* Lernplanungsstatus
* Automatik-Gewichtung
* Strategiezustand und sichtbarer Zustand
* strategischer und technischer Grund
* Status, Art und Ziel der AC-Ladebindung
* Ladequelle, angerechneter Ladepreis und PV-/Netzanteil
* Off-Grid-Regelgrund
* Regelgrund des ModeArbiters
* final gesetzte Leistung

---

# Kapitel 6 – Sensoren & Steuerelemente

Dieses Kapitel erklärt die wichtigsten Sensoren und Bedienelemente.

---

# 6.1 Status- & Wirtschaftssensoren

![Status & Wirtschaft](images/sensors_01_status.png)

---

## Systemstatus

Zeigt den allgemeinen Zustand der Integration.

Typische Werte:

| Zustand              | Bedeutung                                      |
| -------------------- | ---------------------------------------------- |
| OK                   | Integration arbeitet normal                    |
| Initialisierung      | System startet                                 |
| Sensordaten ungültig | ein Pflichtsensor liefert keinen gültigen Wert |
| Preisdaten ungültig  | Preisquelle unbrauchbar                        |

---

## KI-Status

Zeigt den aktuellen Hauptzustand.

Beispiele:

* Bereitschaft
* Laden
* Entladen
* Notladung
* Manueller Modus

---

## KI-Empfehlung

Zeigt die aktuelle Empfehlung der Integration.

Beispiele:

* Laden
* Entladen
* Keine Aktion
* Notladung

---

## Hauslast

Die Hauslast wird aus Netz, PV und Batterie berechnet.

Sie ist die geschätzte reale Last des Haushalts.

Eine korrekte Hauslast ist wichtig für:

* Autarkiemodus
* Entladung
* Lernplanung
* Diagnose
* Profilanalyse

---

## Ø Ladepreis Akku

Der durchschnittliche Ladepreis ist ein gewichteter Wert.

Er beschreibt, zu welchem Preis die aktuell gespeicherte Energie ungefähr geladen wurde.

Er wird genutzt für:

* wirtschaftliche Entladung
* Profitberechnung
* Preisvergleich

Bei Netzladung fließt der aktuelle Netzpreis ein. Bei PV-Ladung wird eine
konfigurierte Einspeisevergütung als entgangener Erlös verwendet. Bei gemischter
Ladung entsteht ein gewichteter Mischpreis. Der Durchschnittswert wird mit dem
nächsten erkannten Energiezuwachs fortgeschrieben.

---

## Ladequelle und angerechneter Ladepreis

Diese Sensoren zeigen die aktuelle wirtschaftliche Zuordnung einer Ladung:

| Sensor                    | Bedeutung                                             |
| ------------------------- | ----------------------------------------------------- |
| Ladequelle                | PV-, Netz- oder gemischte Ladung                      |
| Angerechneter Ladepreis   | Preis, der für den aktuellen Ladeanteil verwendet wird |
| Ladeanteil Netz           | geschätzter Netzanteil der Ladeleistung               |
| Ladeanteil PV             | geschätzter PV-Anteil der Ladeleistung                |
| Mischpreis aktiv          | zeigt eine gleichzeitige PV-/Netzladung               |

Der **angerechnete Ladepreis** kann bereits während der Ladung sichtbar sein.
Der **Ø Ladepreis Akku** wird dagegen erst mit einem erkannten SoC- bzw.
Energiezuwachs dauerhaft gewichtet.

---

## Ø Tagespreis

Der durchschnittliche Tagespreis wird aus den verfügbaren Preisprognosedaten berechnet.

Er dient als Grundlage für:

* Peak-Erkennung
* Tal-Erkennung
* relative Preisbewertung

---

# 6.2 Peak- & Transparenzsensoren

![Peak & Transparenz](images/sensors_02_peak.png)

---

## Adaptiver Peak erkannt

Zeigt an, ob aktuell ein dynamisch erkannter Preispeak aktiv ist.

---

## Aktuelle Peak-Schwelle

Zeigt den Preiswert, ab dem der aktuelle Zeitraum als Peak gilt.

---

## Aktuelle Tal-Schwelle

Zeigt den Preiswert, unterhalb dessen ein Preisfenster als günstig gilt.

---

## Aktueller Strompreis

Zeigt den aktuell gültigen Strompreis.

---

## Engine-Status

Zeigt, ob die Entscheidungslogik vollständig arbeiten kann.

Beispiele:

* System normal
* Keine Preisdaten verfügbar
* Kein aktueller Strompreis
* Ungültige Sensordaten

---

## Entscheidungsgrund

Der wichtigste Erklärungssensor.

Er zeigt den genauen Grund für die aktuelle Entscheidung.

Beispiele:

* PV-Überschuss laden
* Hauslast decken
* AC-Ladebindung aktiv
* Preisbasierte Entladung
* Zusatzakku lädt: Entladung blockiert
* Inselsteckdose aktiv: Last beobachtet
* Zellspannungs-Schutz aktiv

---

## Strategiezustand und sichtbarer Zustand

Der **Strategiezustand** beschreibt die intern ausgewählte Strategie, zum
Beispiel PV-Ladung, gebundene AC-Ladung, Hauslastdeckung, wirtschaftliche
Entladung oder Schutz.

Der **sichtbare Zustand** fasst diese Details bewusst ruhiger und verständlicher
zusammen. Kurzlebige technische Korrekturen müssen dadurch nicht den sichtbaren
Hauptstatus wechseln lassen.

---

## Strategischer und technischer Grund

Der **strategische Grund** erklärt, warum eine Strategie ausgewählt wurde. Der
**technische Grund** beschreibt, wie der ModeArbiter oder Leistungsregler diese
Strategie gerade umsetzt, begrenzt oder hält.

Zusammen mit **Quellgrund**, **Quellaktion** und **Quell-AC-Modus** lässt sich der
gesamte Weg von der ursprünglichen Regelentscheidung bis zum Gerätebefehl
nachvollziehen. Die Quellwerte sind standardmäßig deaktivierte
Diagnoseentitäten und können bei Bedarf in Home Assistant aktiviert werden.

---

## Automatik-Gewichtung

Zeigt den dominanten Kontext der einheitlichen Automatik:

* PV-orientiert
* ausgewogen
* preisorientiert
* reserveorientiert

Die Gewichtung ist keine eigene Betriebsart. Sie erklärt nur, welche Faktoren
im aktuellen Automatikkontext besonders relevant sind.

---

## AC-Ladebindung

Die Ladebindungs-Sensoren zeigen unter anderem:

* ob eine Bindung aktiv ist
* Art und ursprünglichen Auslöser
* Ziel-SoC und angeforderte Leistung
* Start- und Gültigkeitszeit
* Abbruch- oder Abschlussgrund
* ob ein PV-Anteil zugemischt werden darf
* die berechnete Ladequellen-Aufteilung

Einige Detailwerte sind standardmäßig deaktivierte Diagnoseentitäten.

---

## Aktives Geräteprofil

Zeigt das verwendete Geräteprofil.

Dieser Wert ist bei Support-Anfragen sehr wichtig.

---

## Erkannter Betriebsmodus

Zeigt den internen Kontextwert `summer`, `winter` oder `manual`.

> [!NOTE]
> Dieser Sensor ist kein auswählbarer Betriebsmodus. In der Automatik dienen
> `summer` und `winter` nur noch als weicher Diagnosekontext; sie schalten keine
> getrennten Strategien um. Die auswählbaren Modi sind Automatik, Autarkie und
> Manuell.

---

## Ersparnis / Gewinn

Zeigt die berechnete Ersparnis bzw. den berechneten Gewinn durch Preisarbitrage.

---

# 6.3 Lernplanungssensoren

Die Lernplanung erzeugt mehrere Diagnosewerte.

![Diagnosewerte](images/sensors_03_diagnose.png)

---

## Ladeplanung: Lernstatus

Zeigt, ob genügend Lerndaten vorhanden sind.

Typische Werte:

| Zustand                  | Bedeutung                                   |
| ------------------------ | ------------------------------------------- |
| Noch nicht gestartet     | es wurden noch keine Daten gesammelt        |
| Daten werden gesammelt   | Lernmodell baut Historie auf                |
| Nicht genügend Lerndaten | Bedingungen noch nicht erfüllt              |
| Bereit                   | Lernplanung kann verwendet werden           |
| Aktiv                    | Lernplanung steuert aktuell ein Ladefenster |

---

## Ladeplanung: Modus

Zeigt den aktuellen Modus der Lernplanung.

Beispiele:

* Deaktiviert
* Daten werden gesammelt
* Klassische Planung
* Lernplanung bereit
* Lernplanung wartet auf Ladefenster
* Lernplanung aktiv

---

## Ladeplanung: Geplanter Ladestart

Zeigt den optimal berechneten Startzeitpunkt für die geplante Ladung.

---

## Ladeplanung: Deadline

Zeigt den Zeitpunkt, bis zu dem die Batterie ausreichend geladen sein sollte.

---

## Ladeplanung: Nachladeenergie

Zeigt, wie viel Energie voraussichtlich nachgeladen werden muss.

---

## Ladeplanung: Fenstergröße

Zeigt die Länge des geplanten Ladefensters.

---

## Diagnose: Lernplanung Blockierungsgrund

Erklärt, warum Lernplanung noch nicht aktiv ist oder warum gerade keine Ladung geplant wird.

Beispiele:

* Kein Blocker
* Nicht genügend Historientage
* Datenqualität zu niedrig
* Keine Preisdaten verfügbar
* Keine Nachladung erforderlich
* Deadline zu nah

---

## Datenabdeckung

Zeigt, wie gut das gelernte Lastprofil bereits mit Daten gefüllt ist.

Eine hohe Datenabdeckung verbessert die Planung.

---

## Nutzbare Tage

Zeigt, wie viele Tage für das Lernmodell verwendet werden können.

---

## Erwarteter Verbrauch

Zeigt den erwarteten Verbrauch bis zur Planungsdeadline.

---

## Verfügbare Akkuenergie

Zeigt, wie viel Energie oberhalb des SoC-Minimums verfügbar ist.

Die Berechnung basiert auf:

```text
Gesamtkapazität × max(0, (aktueller SoC - SoC-Minimum) / 100)
```

---

## Reserve

Zeigt die eingeplante Sicherheitsreserve.

---

## Prognose-Zuschlag

Zeigt, wie die PV-Prognose die Ladeplanung beeinflusst.

---

# 6.4 Off-Grid-Sensoren

---

## Off-Grid-Leistung

Zeigt die gemessene Leistung an der Off-Grid-/Inselsteckdose.

Positive Werte werden als Last interpretiert.

---

## Off-Grid-Modus

Zeigt den gelesenen Off-Grid-Modus.

Mögliche normalisierte Werte:

* nicht konfiguriert
* unbekannt
* aus
* normal
* ökonomisch

---

## Off-Grid-Last aktiv

Zeigt, ob eine relevante Last an der Inselsteckdose erkannt wurde.

---

## Off-Grid-Quelle aktiv

Diagnosewert für mögliche Off-Grid-Eingangsleistung.

Dieser Bereich ist aktuell vorsichtig zu interpretieren, da nicht alle Geräte die Richtung gleich melden.

---

## Regelgrund Off-Grid

Zeigt, was die Off-Grid-Logik aktuell macht.

Mögliche Gründe:

```text
none
offgrid_load_observed
```

| Regelgrund                | Bedeutung                                      |
| ------------------------- | ---------------------------------------------- |
| `none`                    | Keine Off-Grid-Last erkannt                    |
| `offgrid_load_observed`   | Off-Grid-Last erkannt und diagnostisch erfasst |

---

# 6.5 Zellspannungs-Sensoren

Der Zellspannungs-Schutz ist optional und gehört zum Expertenbereich.

Er kann verwendet werden, wenn passende Sensoren für die niedrigste Zellspannung je Akkupack vorhanden sind.

---

## Globale niedrigste Zellspannung

Zeigt die niedrigste Zellspannung über alle konfigurierten Packs.

---

## Zellspannungs-Status

Mögliche Zustände:

* Deaktiviert
* Normal
* Warnbereich aktiv
* Entladesperre aktiv
* Sensordaten ungültig

---

## Zellspannungs-Notladung aktiv

Zeigt, ob wegen kritischer Zellspannung eine Notladung aktiv ist.

---

## Entladung durch Zellspannungs-Schutz blockiert

Zeigt, ob die Entladung wegen Zellspannung blockiert ist.

---

## Plausibilität SoC / Zellspannung

Dieser Diagnosewert hilft zu erkennen, ob SoC und Zellspannung zusammen plausibel wirken.

Beispiele:

* plausibel
* auffällig
* kritisch unplausibel
* nicht verfügbar

---

# 6.6 Steuerelemente

![Leistungs- & Schutzparameter](images/controls_01_limits.png)

---

## Max. Entladeleistung

Begrenzt die maximale Entladeleistung.

Dieser Wert wird zusätzlich durch das Geräteprofil begrenzt.

Die Oberfläche erlaubt Werte bis 4000 W, damit auch die neuen Mix-Modelle
vollständig eingestellt werden können. Kleinere Profile bleiben an ihrem
jeweiligen `MAX_OUTPUT_W` begrenzt.

---

## Max. Ladeleistung

Begrenzt die maximale Ladeleistung.

Dieser Wert wird zusätzlich durch das Geräteprofil begrenzt.

Die Oberfläche erlaubt Werte bis 4000 W. Das aktive Profil begrenzt den
tatsächlichen Befehl weiterhin über `MAX_INPUT_W`.

---

## Notladeleistung

Leistung, mit der bei Notladung geladen wird.

Auch dieser Wert kann bis 4000 W eingestellt werden und unterliegt dem
Eingangslimit des aktiven Geräteprofils.

---

## Notladung ab SoC

SoC-Schwelle, ab der eine Notladung ausgelöst werden kann.

---

## Peak-Faktor

Bestimmt, wie empfindlich adaptive Preispeaks erkannt werden.

---

## Tal-Faktor

Bestimmt, wie günstig ein Preis relativ zum Tagesniveau sein muss, damit er als
Talpreis bewertet wird. Ein niedrigerer Wert verlangt ein deutlicheres Preistal.

---

## PV-Ladestart ab Einspeisung

Mindestwert realer Netzeinspeisung für den Start einer neuen
PV-Überschussladung. Die aktuelle PV-Leistung allein reicht nicht als
Startsignal.

---

## Prognose-Grundlast

Annahme für die durchschnittliche Hauslast bei prognosebasierten
Planungsberechnungen. Der Wert beeinflusst die erwartete verfügbare PV-Energie,
nicht die aktuelle netzgeführte Leistungsregelung.

---

## Sehr-teuer-Schwelle

Benutzerdefinierte Schwelle für sehr teure Preise.

---

## Sehr-billig-Schwelle

Benutzerdefinierte Schwelle für sehr günstige Preise.

Kann auch negativ sein, wenn der Tarif negative Preise liefert.

---

## SoC Maximum

Oberes Ladeziel.

---

## SoC Minimum

Untere Schutzgrenze.

---

## Anzahl Akku-Packs

Wird zusammen mit der Packkapazität für die Gesamtkapazität verwendet.

---

## Modus & Wirtschaft

![Modus & Wirtschaft](images/controls_02_mode.png)

---

## Betriebsmodus

Auswahl zwischen:

* Automatik
* Autarkie
* Manuell

---

## Gewinnmarge

Bestimmt, wie groß der Preisabstand zwischen Ladepreis und Entladepreis mindestens sein soll.

---

## Manuelle Aktion

Im manuellen Modus kann gewählt werden:

* Standby
* Laden
* Entladen
* konstante Entladung

---

# Kapitel 7 – Regelprofil bearbeiten

Battery SmartFlow AI besitzt einen Profil-Editor.

Damit können wichtige Regelparameter direkt über Home Assistant angepasst werden.

![Regelprofil bearbeiten](images/config_05_profil_expert.png)

---

## 7.1 Bereiche im Profil-Editor

Der Profil-Editor ist in Bereiche aufgeteilt:

| Bereich       | Zweck                                      |
| ------------- | ------------------------------------------ |
| Allgemein     | gemeinsame Profilwerte                     |
| Laden         | Regelwerte für INPUT/Ladeleistung          |
| Entladen      | Regelwerte für OUTPUT/Entladeleistung      |
| Expertenmodus | Lernplanung und optionaler Zellschutz      |

---

## 7.2 Allgemein

Im Bereich **Allgemein** befinden sich gemeinsame Profilparameter.

Typische Werte:

* installierte PV-Leistung
* Ziel-Netzbezug
* Entladen Ziel-Netzbezug
* Export-Schutz
* Keepalive Mindestdefizit
* Keepalive Mindestleistung
* Entlade-Wiederfreigabe oberhalb SoC-Minimum

---

### Ziel-Netzbezug

Ein kleiner gewollter Netzbezug kann die Regelung beruhigen.

Beispiel:

```text
Ziel-Netzbezug: 10 W
```

Das bedeutet:

Battery SmartFlow AI versucht nicht exakt 0 W zu treffen, sondern lässt einen kleinen Bezug zu.

Das kann unnötige Einspeisung und Regelzacken reduzieren. Bei wirtschaftlich
bewerteter PV-Ladung kann der Regler diesen Grundwert gezielt in Richtung einer
kleinen Einspeisung verschieben.

---

### Entladen Ziel-Netzbezug

Dieser Wert legt den technischen Grundzielpunkt während aktiver Entladung fest.

* positiver Wert: kleiner Netzbezug
* `0 W`: neutraler Zielpunkt
* negativer Wert: kleine Netzeinspeisung

Das Geräteprofil enthält einen erprobten Standardwert. Zusätzlich kann die
Wirtschaftlichkeitslogik eine leichte Einspeisung freigeben, wenn die gespeicherte
Energie deutlich günstiger als die Einspeisevergütung ist.

---

### Export-Schutz

Der Export-Schutz ist eine zusätzliche Sicherheitsreserve gegen ungewollte Einspeisung.

Ein höherer Wert macht die Regelung vorsichtiger.

---

### Keepalive Mindestleistung

Dieser Wert hält eine Entladung ab einer Mindestleistung aktiv.

Zu niedrige Werte können zu Ein-/Aus-Flattern führen.

Zu hohe Werte können unnötigen Bezug oder Export verursachen.

---

## 7.3 Laden

Im Bereich **Laden** befinden sich die Regelparameter für INPUT/PV-Ladung.

Wichtige Werte:

* Laden Deadband
* Laden KP Hochregeln
* Laden KP Runterregeln
* Laden Max. Schritt Hochregeln
* Laden Max. Schritt Runterregeln

---

### Laden Deadband

Die Deadband ist ein Toleranzbereich.

Innerhalb dieses Bereichs wird nicht nachgeregelt.

| Einstellung         | Wirkung                                 |
| ------------------- | --------------------------------------- |
| höhere Deadband     | ruhiger, weniger kleine Korrekturen     |
| niedrigere Deadband | genauer, schneller, potenziell nervöser |

---

### Laden KP

KP bestimmt, wie stark auf Abweichungen reagiert wird.

| Einstellung    | Wirkung                                      |
| -------------- | -------------------------------------------- |
| höherer KP     | schnellere Reaktion, mehr Risiko für Sprünge |
| niedrigerer KP | ruhigere Reaktion, langsamere Anpassung      |

---

### Laden Max. Schritt

Begrenzt, wie stark die Ladeleistung pro Regelzyklus geändert werden darf.

Kleinere Schritte machen die Regelung ruhiger.

---

## 7.4 Entladen

Im Bereich **Entladen** befinden sich die Regelparameter für OUTPUT.

Wichtige Werte:

* Entladen Deadband
* Entladen KP Hochregeln
* Entladen KP Runterregeln
* Entladen Max. Schritt Hochregeln
* Entladen Max. Schritt Runterregeln

---

### Entladen Deadband

Toleranzbereich für die Entladung.

Ein höherer Wert kann bei nervösen Systemen helfen.

---

### Entladen KP

Bestimmt, wie stark die Entladeleistung angepasst wird.

Wenn die Entladekurve stark zackt, können niedrigere KP-Werte helfen.

---

### Entladen Max. Schritt

Begrenzt die Änderung pro Regelzyklus.

Für empfindliche Systeme sind kleinere Schritte oft besser.

---

## 7.5 Expertenmodus

Im Expertenmodus können erweiterte Funktionen aktiviert werden:

* Expertenmodus selbst
* lernbasierte Ladefenster-Planung
* Zellspannungs-Schutz

Die einheitliche Leistungsregelung ist in V4.3.0 für alle Installationen
verbindlich aktiv und keine einstellbare Expertenoption.

---

### Expertenmodus aktivieren

Aktiviert den erweiterten Bereich für zusätzliche Schutz- und Diagnosefunktionen.

---

### Lernbasierte Ladefenster-Planung verwenden

Wenn aktiviert, nutzt Battery SmartFlow AI die Lernplanung automatisch, sobald genug Daten vorhanden sind.

Bis dahin bleibt klassische Planung aktiv.

---

### Zellspannungs-Schutz aktivieren

Aktiviert die Möglichkeit, Zellspannungssensoren zu konfigurieren.

Der Schutz kann Entladung sperren oder Notladung auslösen.

---

# Kapitel 8 – Technischer Hintergrund

Dieses Kapitel richtet sich an Power-User.

---

# 8.1 Architekturüberblick

Battery SmartFlow AI arbeitet mit mehreren Ebenen.

```text
Sensoren
→ Mess- und Planungskontext
→ AutomaticStrategy-Kontext
→ Decision Engine
→ StrategyDecision / sichtbarer Zustand
→ StrategyIntent
→ ModeArbiter
→ RegulationPowerController
→ DeviceCommand
→ Home Assistant Service Calls
```

---

## Mess- und Planungskontext

Der Kontext enthält alle aktuellen Eingangsdaten:

* SoC
* PV-Leistung
* Hauslast
* Netzbezug
* Einspeisung
* Preis
* Preisprognose
* PV-Prognose
* Lernplanung
* Zellspannung
* Zusatzakku
* Off-Grid
* Geräteprofil

---

## AutomaticStrategy-Kontext

Dieser Baustein ist ausschließlich in der Automatik aktiv. Er bewertet die
aktuelle Relevanz von:

* PV und Hauslast
* Preisniveau
* verfügbarer Batteriereserve
* PV-Prognose

Das Ergebnis ist eine Gewichtung und eine Reihe strategischer Freigaben, zum
Beispiel ob wirtschaftliche Entladung, Tal-Ladung oder Reserve-Ladung überhaupt
geprüft werden darf. Die interne Sommer-/Wintererkennung ist nur noch ein
weicher Zusatzkontext und kein Umschalter für getrennte Strategien.

> [!IMPORTANT]
> AutomaticStrategy entscheidet nicht selbst über Laden oder Entladen. Die
> endgültige strategische Auswahl bleibt bei der Decision Engine.

---

## Decision Engine

Die Decision Engine erzeugt alle im aktuellen Kontext zulässigen Kandidaten.
Die Reihenfolge der Regeln ist nur noch der Gleichstandsentscheid; grundsätzlich
gewinnt der Kandidat mit der höchsten strategischen Priorität.

Sie fragt:

* Muss geladen werden?
* Darf entladen werden?
* Gibt es PV-Überschuss?
* Ist der Preis günstig?
* Ist der Preis teuer?
* Gibt es eine Notladung?
* Ist eine Schutzfunktion aktiv?
* Gibt es eine aktive Off-Grid-Last?

Zu den Kandidaten gehören unter anderem Notladung, manuelle Vorgaben,
PV-Überschussladung, geplante und gelernte Ladefenster, Preisladung,
wirtschaftliche Entladung sowie Hauslastdeckung im Autarkiemodus.

Ungültige Pflichtdaten oder richtungsabhängige Konflikte können einen Kandidaten
verwerfen, ohne automatisch jede andere zulässige Strategie zu blockieren.

---

## StrategyDecision und sichtbarer Zustand

Der ausgewählte Kandidat wird in ein einheitliches strategisches Modell
überführt. Es enthält:

* Strategiezustand
* sichtbaren Zustand
* gewünschten AC-Modus und Leistung
* strategischen Grund und Quellgrund
* Priorität
* Ziel-SoC und Zusatzinformationen

Der sichtbare Zustand ist bewusst nutzerorientiert und stabiler als ein
kurzlebiger technischer Reglergrund.

---

## StrategyIntent

Der StrategyIntent beschreibt die technische Absicht.

Beispiele:

```text
pv_charge
planned_charge
cover_deficit
peak_discharge
arbitrage_discharge
manual_charge
emergency_charge
passthrough
```

---

## ModeArbiter

Der ModeArbiter entscheidet, ob der Moduswechsel technisch erlaubt ist.

Er verhindert unter anderem:

* zu frühes INPUT bei instabilem Export
* OUTPUT während SoC-/Zellschutz
* INPUT während Zusatzakku-Entladung
* schnelles Hin und Her nach Lastwechseln

Eine erkannte Off-Grid-Dauerlast wird diagnostisch berücksichtigt, blockiert
eine ansonsten gültige AC-Ladung aber nicht pauschal.

---

## RegulationPowerController

Der RegulationPowerController berechnet die konkrete Leistung.

Er nutzt:

* Netz-Historie
* Ziel-Netzbezug
* Deadband
* KP-Werte
* Schrittbegrenzung
* Profilgrenzen
* vorherige Leistung
* schnelle Lastanstiege und Lastabfälle
* Near-Zero-Feinregelung bei aktivem OUTPUT
* wirtschaftliche Exportgewichtung

---

## DeviceCommand

DeviceCommand erzeugt aus strategischer Absicht, technischer Modusfreigabe und
berechneter Leistung den endgültigen Gerätebefehl.

Er entscheidet:

* AC-Modus
* Input-Limit
* Output-Limit
* ob ein Wert geschrieben werden muss
* ob ein Schreibvorgang übersprungen werden kann

---

# 8.2 Prioritätenhierarchie

Battery SmartFlow AI sammelt zunächst strategische Kandidaten und bewertet sie
anschließend nach Priorität. Dadurch beendet nicht mehr die erste passende
Regel automatisch die gesamte Auswertung.

| Rang        | Beispiele                                                        |
| ----------- | ---------------------------------------------------------------- |
| Schutz      | ungültige Sicherheitsgrenzen, SoC-/Zellschutz, Notladung        |
| Manuell     | manuelles Laden, Entladen, konstante Entladung oder Standby      |
| gebunden    | bereits aktive AC-Ladebindung                                   |
| strategisch | PV-Ladung, Planung, Lernplanung, Preis- und Reserve-Ladung       |
| Entladung   | adaptive Peak- und wirtschaftliche Entladung                    |
| Versorgung  | Autarkie-Hauslastdeckung und PV-Hauslast-Passthrough             |
| Leerlauf    | bereit, sicherer Leerlauf oder technischer Haltezustand          |

Richtungsblocker werden differenziert behandelt. Lädt beispielsweise ein
Zusatzakku, kann eine eigene Entladung unzulässig sein, während ein anderer
sicherer Kandidat weiterhin gewählt werden darf. Bei ungültigem Netzsensor gilt
grundsätzlich sicherer Leerlauf; Notladung und ausdrücklich manuelle Aktionen
bleiben gesondert priorisiert.

> [!IMPORTANT]
> Schutzfunktionen dürfen nicht von technischen Haltezuständen überstimmt werden.

---

# 8.3 Planungssystem

Battery SmartFlow AI kann Ladefenster planen.

Es berücksichtigt:

* zukünftige Preise
* aktuellen SoC
* SoC-Ziel
* PV-Prognose
* erwarteten Verbrauch
* Lernprofil
* Ladeleistung
* Deadline

Ziel ist nicht immer sofortiges Laden, sondern ein sinnvoller Zeitpunkt. Eine
strategische Netzladung darf nur in der Automatik entstehen. Autarkie und
Manuell starten keine normale Preis- oder Planladung.

Wird eine geplante, gelernte, sehr günstige, Tal- oder Reserve-Ladung
ausgewählt, erzeugt die Steuerung eine persistente AC-Ladebindung. Diese
übersteht kurze Zustandswechsel und einen Home-Assistant-Neustart. Sie bewahrt
den ursprünglichen Auslöser, Ziel-SoC, Leistungswunsch und – bei Lernplanung –
den geplanten Start, spätesten Start, die Deadline und den zulässigen Preis.

Die Laufzeit kennt drei wesentliche Phasen:

| Phase      | Verhalten                                                        |
| ---------- | ---------------------------------------------------------------- |
| wartend    | Plan bleibt gültig, Netzladung wartet auf Preis oder Startzeit   |
| aktiv      | Ladung ist aktuell zulässig und wird technisch geregelt           |
| erzwungen  | spätester Start ist erreicht; Zielenergie muss bis Deadline bereitstehen |

Abgeschlossen oder abgebrochen wird die Bindung unter anderem bei erreichtem
Ziel, abgelaufener Deadline, dauerhaft fehlender Ladeannahme nahe dem Ziel,
einem wirtschaftlichen Konflikt der Reserve-Ladung, Schutzfehlern oder Wechsel
der Betriebsart.

PV-Überschuss während einer aktiven Bindung wird nicht zum Abbruchgrund. Der
PV-Anteil reduziert stattdessen den Netzanteil der Gesamtladung.

---

# 8.4 Lernplanung

Die Lernplanung nutzt 15-Minuten-Zeitslots.

Sie sammelt historische Hauslastdaten und erstellt daraus ein typisches Verbrauchsprofil.

Aktivierung erst bei ausreichender Datenbasis.

Typische Bereitschaftskriterien:

* genügend Historientage
* genügend nutzbare Tage
* ausreichende Kernzeit-Abdeckung
* hohe Datenabdeckung

Bis dahin bleibt klassische Planung aktiv. Sobald eine gelernte Planung eine
Ladung anstößt, gelten dieselben Phasen und Abbruchbedingungen der
AC-Ladebindung wie bei der klassischen Planung.

---

# 8.5 Stabilitätsmechanismen

Wichtige Stabilitätsmechanismen:

* Mindesthaltezeiten für PV-Ladung, Entladung und Passthrough
* Sperrzeiten zwischen INPUT und OUTPUT
* stabile Importzyklen
* stabile Exportzyklen
* Haltezustände nach Lastabfall oder OUTPUT-Überschwingen
* Schrittbegrenzung
* getrennte Verstärkung beim Hoch- und Herunterregeln
* Totzonen mit zusätzlicher Near-Zero-Feinregelung
* Schreibvermeidung bei unveränderten Befehlen
* Erkennung, ob ein ausgeführter Befehl am Netzpunkt wirksam war

## Near-Zero-Regelung

Der Regler verwendet nicht nur den aktuellen Netzwert, sondern auch kurze und
mittlere Mittelwerte sowie die erkannte Änderungsrichtung. Bei aktivem OUTPUT
kann eine kleine zusätzliche Korrektur verbleibenden, dauerhaft bestätigten
Netzbezug abbauen. Bei Export oder instabilen Messwerten wird diese
Feinregelung begrenzt, damit keine Schwingung entsteht.

Bei PV-Ladung wird die Eingangsleistung schneller reduziert, sobald die
Einspeisereserve schrumpft. Dadurch soll die Ladung nahe am Netznullpunkt bleiben,
ohne in Netzbezug zu kippen.

## Wirtschaftliche Exportgewichtung

Ein konfigurierter Einspeisetarif kann den technischen Zielpunkt leicht in
Richtung Einspeisung verschieben:

* bei reiner PV-Überschussladung, um bezahlte Einspeisung nicht durch Netzbezug
  zu ersetzen
* bei Entladung nur dann, wenn die gespeicherte Energie zuzüglich Sicherheitsmarge
  günstiger als die Einspeisevergütung ist

Geplante, manuelle und Notladungen behalten ihren strategischen Leistungswunsch
und werden nicht durch diese Exportgewichtung verändert.

## Ladepreis-Zwischenspeicher

SoC-Werte werden häufig langsamer aktualisiert als Leistungs- und Netzsensoren.
Deshalb sammelt V4.3.0 während realer Ladung zeitlich begrenzt gewichtete
Nachweise zu PV-/Netzanteil und Preis. Ein nachlaufender SoC-Anstieg kann diese
Kostenbasis noch übernehmen, auch wenn INPUT bereits beendet wurde. Bei
Entladung oder am Mindest-SoC wird der Zwischenspeicher verworfen; veraltete
Nachweise werden nicht weiterverwendet.

---

# 8.6 Geräteprofile

Geräteprofile enthalten nicht nur Leistungsgrenzen, sondern auch technische Fähigkeiten.

Beispiele:

* maximale INPUT-Leistung
* maximale OUTPUT-Leistung
* Reaktionsgeschwindigkeit
* Schrittweiten
* Cooldowns
* Off-Grid-Erkennung und gerätespezifische Grenzwerte
* INPUT-Keepalive-Sicherheit
* Fast-Mode-Switch-Fähigkeit
* Low-SoC-Verhalten
* Zellschutzverhalten
* Passthrough-Fähigkeit

Benutzerwerte wie maximale Lade-, Entlade- oder Notladeleistung werden immer
noch einmal durch `MAX_INPUT_W` und `MAX_OUTPUT_W` des aktiven Profils begrenzt.
Die in Home Assistant einstellbare Obergrenze von 4000 W hebt daher keine
Gerätesicherheitsgrenze auf.

Im Code sind folgende Sicherheitsgrenzen hinterlegt:

| Profil                 | AC-Eingang | AC-Ausgang | Off-Grid-Grenze |
| ---------------------- | ----------:| ----------:| ---------------:|
| SF800Pro               | 1000 W     | 800 W      | –                |
| SF800Pro2              | 1000 W     | 800 W      | –                |
| SF1600AC+              | 1600 W     | 1600 W     | –                |
| SF2400AC               | 2400 W     | 2400 W     | 2400 W           |
| SF2400AC+              | 2400 W     | 2400 W     | 2400 W           |
| SF2400Pro              | 2400 W     | 2400 W     | 2400 W           |
| SolarFlow 3000 Mix AC+ | 3000 W     | 3000 W     | 3680 W           |
| SolarFlow 4000 Mix AC+ | 4000 W     | 4000 W     | 3680 W           |
| SolarFlow 4000 Mix Pro | 4000 W     | 4000 W     | 3680 W           |
| Hyper 2000             | 1200 W     | 1200 W     | –                |
| HUB 2000               | 1800 W     | 1200 W     | –                |

Die drei Mix-Profile verwenden bewusst keine Pro-Sonderlogik. Sie erben die
neutrale AC-gekoppelte Regelbasis des SF2400AC und überschreiben nur die vom
Nutzer bestätigten AC- und Off-Grid-Grenzen.

Die gemeldete Speicherkapazität wird nicht im Geräteprofil hinterlegt. Sie
entsteht weiterhin aus Kapazität pro Akkupack und Anzahl der Packs bzw. aus
einem optionalen Kapazitätssensor.

---

# 8.7 SF800Pro / SF800Pro2 Hinweise

Kleinere Systeme der 800-W-Klasse können empfindlicher auf schnelle Regeländerungen reagieren.

Daher können eigene Profile sinnvoll sein.

Typische Optimierungen:

* kleinerer Max-Schritt
* höhere Deadband
* etwas Ziel-Netzbezug statt 0 W
* längere Haltezeiten
* langsamere INPUT-/OUTPUT-Wechsel
* konservativeres Low-SoC-Verhalten

> [!TIP]
> Ziel ist ein möglichst kleiner und stabiler Netzfehler – nicht ein nervös
> erzwungener Einzelmesswert von exakt 0 W.

---

# 8.8 Hinweise zu SolarFlow 3000/4000 Mix

Die Profile der neuen Mix-Geräte sind in V4.3.0 vollständig auswählbar und ihre
bestätigten AC-/Off-Grid-Grenzen werden technisch berücksichtigt. Die
Datenbereitstellung liegt jedoch außerhalb von Battery SmartFlow AI.

Derzeit kann eine Token-Verbindung der Geräte zu Z-HA erfolgreich erscheinen,
obwohl wegen eines Firmwareproblems keine aktuellen Mess- und Steuerdaten
geliefert werden. In diesem Fall kann Battery SmartFlow AI trotz korrektem Profil
nicht arbeiten.

Bei einer Support-Anfrage zu diesen Modellen sollten deshalb zuerst geprüft
werden:

* genaue Modellbezeichnung
* installierte Firmware-Version
* ob die Z-HA-Entitäten tatsächlich laufend neue Werte liefern
* ob SoC, Batterieleistung, AC-Modus sowie Lade- und Entladegrenze verfügbar sind

MQTT-Entitäten allein gelten nicht als zuverlässiger Nachweis, weil dieser Weg
von Zendure nicht mehr unterstützt und nicht verlässlich aktualisiert wird.

---

# Kapitel 9 – FAQ & typische Probleme

---

## 9.1 Es wird kein adaptiver Peak erkannt

Mögliche Ursachen:

* keine Preisprognose vorhanden
* aktueller Preis fehlt
* Peak-Faktor zu hoch
* Tagespreise sind sehr gleichmäßig
* Preis liegt nicht weit genug über dem Tagesdurchschnitt

Prüfe:

* Engine-Status
* aktueller Strompreis
* Ø Tagespreis
* aktuelle Peak-Schwelle
* Preisverlauf

---

## 9.2 Engine-Status zeigt „Keine Preisdaten“

Dann fehlen Preisprognosedaten.

Mögliche Ursachen:

* Preisverlauf-Sensor nicht konfiguriert
* Sensor liefert keine Attribute
* Forecast-Format wird nicht erkannt
* Integration des Stromanbieters liefert gerade keine Daten

Ohne Preisprognose funktionieren PV- und Lastlogik weiterhin, aber Preisplanung ist eingeschränkt.

---

## 9.3 Gewinn bleibt 0 €

Mögliche Ursachen:

* keine reale Entladung erkannt
* kein gültiger Ladepreis gespeichert
* PV-Ladung wurde ohne konfigurierte Einspeisevergütung mit 0,00 €/kWh bewertet
* Preisunterschied zu klein
* technische Entladung wird nicht als Preisentladung gezählt
* Batterie-Leistungssensor hat falsches Vorzeichen

Prüfe:

* Ø Ladepreis Akku
* aktueller Strompreis
* Entscheidungsgrund
* Batterie-Leistung
* delta_kwh
* charge_source
* Angerechneter Ladepreis
* Einspeisevergütung in der Integrationskonfiguration

---

## 9.4 Regelung wirkt instabil

Mögliche Ursachen:

* Netzsensor liefert sprunghafte Werte
* falsches Geräteprofil
* zu aggressive Profilwerte
* parallele Automationen
* Zendure-App regelt mit
* P1-Regelung in Zendure-Integration aktiv
* Deadband zu klein
* Max-Schritte zu groß

Maßnahmen:

* ein passendes Geräteprofil verwenden
* korrektes Geräteprofil wählen
* Deadband erhöhen
* Schrittweiten reduzieren
* Ziel-Netzbezug leicht erhöhen
* parallele Automationen deaktivieren
* Netzsensor prüfen

---

## 9.5 Netzbezug oder Einspeisung bleibt oberhalb des Zielbereichs

Kurze Abweichungen bei Lastwechseln sind normal. V4.3.0 regelt im stabilen
Betrieb jedoch deutlich näher am jeweiligen Zielwert als frühere Versionen.

Der genaue Zielpunkt hängt vom Geräteprofil und von der Wirtschaftlichkeit ab:

* ein Profil kann einen kleinen Netzbezug vorsehen
* PV-Ladung mit Einspeisevergütung kann leichte Einspeisung bevorzugen
* Entladung kann leichte Einspeisung bevorzugen, wenn die gespeicherte Energie
  günstiger als die Vergütung ist
* 800-W-Profile arbeiten bewusst konservativer

Bleiben 30–100 W oder mehr dauerhaft stehen, prüfe:

* Ziel-Netzbezug und Entladen Ziel-Netzbezug
* Netzsensor-Aktualisierung und Vorzeichen
* aktives Geräteprofil
* technische Gründe und final gesetzte Leistung
* parallele Zendure- oder Home-Assistant-Regelungen

---

## 9.6 PV-Ladung startet nicht

Mögliche Ursachen:

* keine stabile Einspeisung
* PV-Ladestart-Schwelle nicht erreicht
* Zusatzakku entlädt
* SoC-Maximum erreicht
* SoC-Limit aktiv
* Zellschutz aktiv
* ModeArbiter wartet auf stabile Exportzyklen
* post-output-hold aktiv

Prüfe:

* PV-Leistung
* Netzeinspeisung
* PV-Ladestart ab Einspeisung
* Entscheidungsgrund
* regulation_mode_arbiter_reason
* pv_charge_latched
* additional_battery_discharge_active

Eine neue PV-Ladung startet anhand real gemessener Netzeinspeisung, nicht allein
aufgrund einer hohen PV-Leistung. Während einer bereits aktiven Ladung wird die
Leistung dagegen kontinuierlich geregelt.

---

## 9.7 Entladung startet nicht

Mögliche Ursachen:

* SoC-Minimum erreicht
* Entlade-Wiederfreigabe noch nicht erreicht
* Zellspannung blockiert
* unteres SoC-Limit aktiv
* Preis nicht hoch genug
* Automatik-Kontext erlaubt aktuell keine wirtschaftliche Entladung
* Autarkiemodus wartet noch auf eine technisch stabile Hauslastdeckung
* ModeArbiter wartet auf stabile Importzyklen
* Zusatzakku lädt

Prüfe:

* SoC
* SoC-Minimum
* discharge_resume_soc
* discharge_blocked_by_soc_min
* cell_voltage_discharge_blocked
* soc_limit_status
* Entscheidungsgrund
* effective_discharge_threshold
* regulation_mode_arbiter_reason

---

## 9.8 Off-Grid-Diagnose funktioniert nicht wie erwartet

Prüfe:

* Off-Grid-Leistung konfiguriert?
* Off-Grid-Modus konfiguriert?
* Off-Grid-Modus nicht `off`?
* Off-Grid-Leistung positiv?
* Off-Grid-Last aktiv?
* Off-Grid-Regelgrund?

> [!NOTE]
> Battery SmartFlow AI liest den Off-Grid-Modus nur und steuert die
> Inselsteckdose nicht direkt. `offgrid_load_observed` bedeutet, dass die Last
> erkannt und diagnostisch berücksichtigt wurde. Die tatsächlich bereitgestellte
> Off-Grid-Leistung bleibt Aufgabe von Zendure-Firmware und Gerätekonfiguration.

---

## 9.9 AC-Ladung bei aktiver Off-Grid-Last

Eine erkannte Off-Grid-Dauerlast wird diagnostisch angezeigt, blockiert eine
ansonsten gültige automatische AC-Ladung aber nicht mehr pauschal. Schutz,
Notladung, manuelle Vorgaben und die normale strategische Kandidatenauswahl
bleiben maßgeblich.

---

## 9.10 SolarFlow 3000/4000 Mix liefert keine Daten

Wenn die Token-Verbindung zu Z-HA gelingt, die Entitäten aber keine aktuellen
Werte liefern, liegt derzeit wahrscheinlich das bekannte Firmwareproblem dieser
Modelle vor. Das Geräteprofil in Battery SmartFlow AI kann fehlende Quelldaten
nicht ersetzen.

Prüfe Modell, Firmware-Version und die Zeitstempel bzw. Zustandsänderungen der
Z-HA-Entitäten. MQTT ist keine zuverlässig unterstützte Ausweichlösung.

---

## 9.11 PV-Ladung wird mit 0,00 €/kWh angerechnet

Prüfe zuerst die **Einspeisevergütung** in der Integrationskonfiguration. Der
Wert muss in ganzer Währung pro kWh eingegeben werden, beispielsweise `0,122`
für 12,2 ct/kWh.

Der Sensor **Angerechneter Ladepreis** zeigt den aktuellen Wert bereits während
der Ladung. Der **Ø Ladepreis Akku** wird erst mit dem nächsten erkannten
Energie- bzw. SoC-Anstieg gewichtet. Ohne konfigurierte Vergütung ist
`0,00 €/kWh` das vorgesehene Verhalten.

---

## 9.12 Update von „Zendure SmartFlow AI“

Wenn du von einer alten Version mit altem Namen kommst:

* alte Integration prüfen
* ggf. alte Custom Component entfernen
* neue Integration installieren
* Home Assistant neu starten
* Konfiguration prüfen
* Geräteprofil neu wählen
* optionale neue Sensoren ergänzen

---

# Kapitel 10 – Best Practices & empfohlene Einstellungen

---

## 10.1 Standard-Haushalt mit PV & dynamischem Tarif

Empfohlen:

* Automatikmodus
* korrekter Netzsensor
* Preisverlauf
* aktueller Strompreis
* Einspeisevergütung, falls vorhanden
* PV-Prognose optional
* Lernplanung aktiviert
* passendes Geräteprofil

---

## 10.2 Haushalt ohne PV

Empfohlen:

* Automatikmodus
* Preisverlauf
* aktueller Preis
* Netzsensor
* SoC-Minimum sinnvoll setzen
* Gewinnmarge nicht zu niedrig
* sehr-billig-Schwelle konfigurieren, wenn Tarif negative Preise liefert

---

## 10.3 Maximale Autarkie

Empfohlen:

* Autarkiemodus für konsequente PV-/Hauslastpriorität
* alternativ Automatik, wenn zusätzlich Preisladung und Arbitrage gewünscht sind
* PV-Leistungssensor
* Netzsensor
* PV-Ladestart-Schwelle passend setzen
* SoC-Minimum nicht zu hoch
* SoC-Maximum passend setzen

---

## 10.4 Volatile Strommärkte

Empfohlen:

* Automatikmodus
* Preisverlauf vollständig prüfen
* Peak-Faktor passend wählen
* Gewinnmarge nicht zu niedrig setzen
* sehr-billig-Schwelle nutzen
* Lernplanung aktivieren
* Diagnosewerte beobachten

---

## 10.5 Stabilität vor Aggressivität

Eine stabile Regelung ist wichtiger als ein einzelner exakt ausgeregelter
0-W-Messwert. Im eingeschwungenen Betrieb sollte V4.3.0 dennoch nur eine kleine
Abweichung vom wirtschaftlich gewählten Zielpunkt zeigen.

Bei nervösem Verhalten:

* zunächst Geräteprofil und Netzsensor prüfen
* Deadband erhöhen
* Max-Schritte reduzieren
* Ziel-Netzbezug leicht erhöhen
* Cooldowns verlängern
* passendes Geräteprofil wählen
* ein konservatives Geräteprofil verwenden

---

## 10.6 Kleine 800-W-Systeme

Bei kleineren Systemen wie SF800Pro oder SF800Pro2 können konservativere Werte sinnvoll sein.

Empfohlen:

* etwas Ziel-Netzbezug zulassen
* kleinere Schrittweiten
* höhere Deadband
* längere Haltezeiten
* keine aggressive 0-W-Jagd

---

## 10.7 Off-Grid-Nutzung

Empfohlen:

* Off-Grid-Leistung konfigurieren
* Off-Grid-Modus konfigurieren
* ein passendes Geräteprofil verwenden
* Diagnosewerte prüfen
* Verhalten mit und ohne AC testen
* gerätespezifische Grenzen beachten

---

## 10.8 SolarFlow 3000/4000 Mix

Empfohlen:

* exaktes Mix-Profil auswählen
* Lade-, Entlade- und Notladegrenze passend zur Anlage setzen
* Z-HA-Entitäten vor dem ersten Regeltest auf laufende Aktualisierung prüfen
* Firmware-Version bei Support-Anfragen immer mit angeben
* erst nach bestätigter Datenaktualisierung die Leistungsregelung beurteilen

---

# Anhang 1 – Geräteprofil-Parameter

Die folgenden Parameter sind typische Profilwerte.

Nicht jedes Profil verwendet alle Werte gleich.

---

## Allgemeine Werte

| Parameter                     | Bedeutung                                            |
| ----------------------------- | ---------------------------------------------------- |
| `TARGET_IMPORT_W`             | Zielwert für kleinen gewollten Netzbezug             |
| `DEADBAND_W`                  | allgemeine Totzone                                   |
| `EXPORT_GUARD_W`              | Schutzreserve gegen Einspeisung                      |
| `KEEPALIVE_MIN_DEFICIT_W`     | Mindestdefizit, ab dem Entladung aktiv gehalten wird |
| `KEEPALIVE_MIN_OUTPUT_W`      | Mindestleistung für stabile Entladung                |
| `SOC_DISCHARGE_RESUME_MARGIN` | SoC-Abstand oberhalb SoC-Minimum für Entladefreigabe |

---

## Lade-Regelung

| Parameter              | Bedeutung                                    |
| ---------------------- | -------------------------------------------- |
| `CHARGE_DEADBAND_W`    | Totzone für Ladeleistung                     |
| `CHARGE_KP_UP`         | Verstärkung beim Erhöhen der Ladeleistung    |
| `CHARGE_KP_DOWN`       | Verstärkung beim Reduzieren der Ladeleistung |
| `CHARGE_MAX_STEP_UP`   | maximaler Schritt beim Erhöhen               |
| `CHARGE_MAX_STEP_DOWN` | maximaler Schritt beim Reduzieren            |

---

## Entlade-Regelung

| Parameter                   | Bedeutung                                       |
| --------------------------- | ----------------------------------------------- |
| `DISCHARGE_TARGET_IMPORT_W` | Ziel-Netzbezug speziell für Entladung           |
| `DISCHARGE_DEADBAND_W`      | Totzone für Entladung                           |
| `DISCHARGE_KP_UP`           | Verstärkung beim Erhöhen der Entladeleistung    |
| `DISCHARGE_KP_DOWN`         | Verstärkung beim Reduzieren der Entladeleistung |
| `DISCHARGE_MAX_STEP_UP`     | maximaler Schritt beim Erhöhen der Entladung    |
| `DISCHARGE_MAX_STEP_DOWN`   | maximaler Schritt beim Reduzieren der Entladung |

---

## Zentrale Near-Zero- und Wirtschaftsparameter

Diese Werte besitzen zentrale V4.3-Standardwerte und sind derzeit keine
normalen Felder des Profil-Editors. Ein Geräteprofil kann sie technisch
überschreiben.

| Parameter                              | Bedeutung                                           |
| -------------------------------------- | --------------------------------------------------- |
| `DISCHARGE_NEAR_ZERO_DEADBAND_W`       | enger Bereich für die OUTPUT-Feinregelung           |
| `DISCHARGE_NEAR_ZERO_MIN_IMPORT_W`     | bestätigter Mindestbezug für eine Zusatzkorrektur   |
| `DISCHARGE_NEAR_ZERO_TRIM_STEP_W`      | Schrittweite der Zusatzkorrektur                    |
| `DISCHARGE_NEAR_ZERO_MAX_TRIM_W`       | maximale zusätzliche OUTPUT-Korrektur               |
| `ECONOMIC_EXPORT_TARGET_W`             | wirtschaftliches Ziel für eine kleine Einspeisung   |
| `ECONOMIC_EXPORT_MARGIN_EUR_KWH`       | Preisabstand vor wirtschaftlicher Exportfreigabe    |
| `ECONOMIC_TARGET_DEADBAND_W`           | enger Toleranzbereich bei aktivem Wirtschaftsziel   |

---

## Regelparameter der einheitlichen Regelkette

| Parameter                            | Bedeutung                                   |
| ------------------------------------ | ------------------------------------------- |
| `MODE_SWITCH_COOLDOWN_S`             | allgemeine Wartezeit zwischen Moduswechseln |
| `INPUT_AFTER_OUTPUT_BLOCK_S`         | Sperrzeit für INPUT nach OUTPUT             |
| `OUTPUT_AFTER_INPUT_BLOCK_S`         | Sperrzeit für OUTPUT nach INPUT             |
| `STABLE_EXPORT_CYCLES_FOR_PV_CHARGE` | stabile Exportzyklen für PV-Ladestart       |
| `STABLE_IMPORT_CYCLES_FOR_DISCHARGE` | stabile Importzyklen für Entladestart       |
| `PV_CHARGE_LATCH_MIN_HOLD_S`         | Mindesthaltezeit für aktive PV-Ladung       |
| `DISCHARGE_LATCH_MIN_HOLD_S`         | Mindesthaltezeit für aktive Entladung       |
| `PASSTHROUGH_LATCH_MIN_HOLD_S`       | Mindesthaltezeit für Passthrough-Zustände   |

---

## Off-Grid-Parameter

| Parameter                              | Bedeutung                                                    |
| -------------------------------------- | ------------------------------------------------------------ |
| `SUPPORTS_OFFGRID_SOCKET`              | Profil unterstützt Off-Grid-/Inselsteckdose                  |
| `SUPPORTS_OFFGRID_INPUT`               | Off-Grid kann auch als Eingangs-/Quellpfad betrachtet werden |
| `OFFGRID_MAX_INTERNAL_SUPPLY_W`        | maximal angenommene interne Versorgung der Off-Grid-Last     |
| `OFFGRID_LOAD_ACTIVE_W`                | Schwelle für aktive Off-Grid-Last                            |
| `OFFGRID_LOAD_BLOCKS_AC_CHARGE`        | Profilfähigkeit für eine AC-Ladesperre; aktuell deaktiviert  |
| `OFFGRID_INPUT_AFFECTS_ENERGY_BALANCE` | reservierter Wert für künftige Off-Grid-Quellenbehandlung    |

---

# Anhang 2 – Wichtige Diagnosewerte für Support

Bei Support-Anfragen sind folgende Werte besonders hilfreich:

```text
device_profile
ai_mode
season_mode
automatic_weighting
strategy_state
visible_state
strategic_reason
technical_reason
strategy_priority
source_reason
source_action
source_ac_mode
soc
soc_min
soc_max
soc_limit_status
pv_w
house_load
deficit
surplus
price_now
avg_charge_price
charge_source
charge_price_applied
charge_grid_part_w
charge_pv_part_w
charge_mixed_price_active
charge_commit_active
charge_commit_type
charge_commit_reason
charge_commit_source_reason
charge_commit_target_soc
charge_commit_abort_reason
charge_commit_requested_power_w
current_peak_threshold
economic_discharge_threshold
effective_discharge_threshold
decision_reason
set_mode
set_input_w
set_output_w
discharge_blocked_by_soc_min
discharge_resume_soc
cell_voltage_status
cell_voltage_discharge_blocked
additional_battery_charge_w
additional_battery_discharge_w
offgrid_power_w
offgrid_mode
offgrid_load_active
offgrid_rule_reason
regulation_command_path
regulation_strategy_intent
regulation_requested_mode
regulation_resolved_mode
regulation_mode_arbiter_reason
regulation_raw_target_w
regulation_limited_target_w
regulation_final_power_w
regulation_command_reason
regulation_target_import_w
regulation_effective_deadband_w
regulation_near_zero_active
regulation_near_zero_reason
regulation_near_zero_trim_w
regulation_economic_target_active
regulation_economic_target_reason
regulation_economic_effective_target_import_w
```

Zusätzlich hilfreich:

* Screenshot des Verlaufs
* verwendetes Geräteprofil
* Betriebsmodus
* Version von Battery SmartFlow AI
* Diagnosewert `regulation_command_path`
* Attribute des Sensors **Automatik-Gewichtung**
* Status und Auslöser einer eventuell aktiven AC-Ladebindung
* ob Off-Grid konfiguriert ist
* ob Zusatzakku-Sensoren konfiguriert sind

---

# Schlusswort

Battery SmartFlow AI soll nicht einfach „möglichst viel schalten“, sondern intelligent, stabil und nachvollziehbar regeln.

Die wichtigste Idee bleibt:

> Erst verstehen, dann entscheiden, dann technisch sauber regeln.

Mit V4.3.0 wurde diese technische Grundlage zu einem einheitlichen Gesamtsystem
weiterentwickelt:

* saisonunabhängige Automatik mit klarer Verantwortung
* priorisierte Strategieauswahl und persistente AC-Ladebindung
* präzise Near-Zero-Regelung mit wirtschaftlichem Zielpunkt
* realistische PV- und Mischkosten
* getrennte strategische, sichtbare und technische Diagnose
* profilabhängige Leistungsgrenzen und Stabilitätsmechanismen

Damit ist Battery SmartFlow AI nicht nur eine Preisautomation, sondern eine umfassende Steuerlogik für Zendure-Systeme in Home Assistant.
