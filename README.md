# Battery SmartFlow AI

---

![GitHub Release](https://img.shields.io/github/v/release/PalmManiac/battery-smartflow-ai?style=for-the-badge)
![Maintained](https://img.shields.io/badge/Maintained-Yes-green?style=for-the-badge)
![GitHub Repo Size](https://img.shields.io/github/repo-size/PalmManiac/battery-smartflow-ai?style=for-the-badge)
[![Active installs](https://badge.t-haber.de/badge/battery_smartflow_ai?kill_cache=1)](https://github.com/PalmManiac/battery-smartflow-ai/)
![GitHub Stars](https://img.shields.io/github/stars/PalmManiac/battery-smartflow-ai?style=for-the-badge)
![License](https://img.shields.io/github/license/PalmManiac/battery-smartflow-ai?style=for-the-badge)
![HACS](https://img.shields.io/badge/HACS-Default-blue?style=for-the-badge)

## Unterstützung

Battery SmartFlow AI ist ein privates Freizeitprojekt. Wenn dir die Integration hilft und du die weitere Entwicklung unterstützen möchtest, freue ich mich über eine kleine Unterstützung:

<a href="https://www.buymeacoffee.com/palm_maniac">
  <img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me a Coffee" width="217" height="42">
</a>
<a href="https://www.paypal.com/donate/?hosted_button_id=PYBRJ6T7S4T5U">
  <img src="https://pics.paypal.com/00/s/NmUyYjVhZTItYTRkZi00ZTkwLThjMDAtODMwMjk3NTY5Yzdl/file.PNG" alt="Spenden mit PayPal" width="217">
</a>

---

<img src="docs/images/infografik.png" width="900">

**Intelligent, economic and stable control for Zendure SolarFlow systems in Home Assistant**

*Note: Currently, only a single battery system is supported. Support for coordinated multi-battery systems is planned for a later major version.*

---

# 🌍 Language

* 🇬🇧 English
* 🇩🇪 Deutsch
* 🇫🇷 French
* 🇳🇱 Dutch

---

## What does this integration do?

**Battery SmartFlow AI** automatically controls your Zendure SolarFlow system – based on:

* ☀️ PV generation
* 🏠 Real household load
* 🔋 Battery SoC
* 💶 Dynamic electricity prices (optional)
* 🌦️ PV forecast data (optional)
* 🧠 Learned consumption and charge-window planning
* ⚙️ Device-specific control profiles
* 🧩 Optional additional battery and off-grid socket detection

The integration combines this data into a **physically stable and economically optimized charging and discharging strategy**.

Goal:

> Minimal grid import.
> Maximum economic efficiency.
> Stable charging and discharging.
> No hectic INPUT/OUTPUT direction changes.

---

# 🧠 Core functions / unified architecture

* Adaptive peak detection for expensive price windows
* Price pre-planning with valley detection
* Learned charge-window planning based on historic household consumption
* Optional PV forecast integration
* Dynamic grid regulation instead of simple full-power switching
* Unified power regulation with grid history, mode arbitration and smoothed power control
* Device profiles per Zendure model
* Profile editor for charge/discharge tuning
* Hard-sync with real Zendure AC mode
* Transparency and diagnostic sensors
* Profit / savings calculation
* Season-neutral automatic strategy with seasonal context
* Optional additional battery detection
* Optional off-grid / island socket support
* Optional cell-voltage protection

---

# ⚠️ Mandatory prerequisites

For the integration to work correctly, the following points **must** be fulfilled:

---

## 1️⃣ Zendure original app

In the Zendure app:

* Charge power → Maximum
* Discharge power → Maximum
* HEMS → disabled
* No parallel automations

⚠️ Control takes place exclusively via Home Assistant.

---

## 2️⃣ Zendure Home Assistant integration

The following settings are mandatory:

* Do not select a P1 sensor in the Zendure integration
* Energy export: **Allowed**
* Zendure Manager → Operating mode **OFF**

Incorrect settings may lead to:

* Blocked AC modes
* Discharge interruptions
* Unstable regulation
* Unexpected INPUT/OUTPUT behavior

---

## 3️⃣ Configure grid sensor correctly

Recommended:

* Split mode with separate import & export
  (for example Shelly Pro 3EM)

Supported:

* No grid sensor
* One combined sensor with positive import / negative export
* Two separate sensors for import and export

For best regulation quality, a stable local grid power source is recommended.

---

## 4️⃣ Electricity price integration (optional)

Supported price sources include:

* Tibber
* EPEX
* Octopus Energy, including German Forecast API

Without an electricity price, PV- and load-based control still works.

---

## 5️⃣ PV forecast integration (optional)

PV forecast sensors are optional.

They can improve charge planning, but Battery SmartFlow AI can also run without forecast data.

Supported forecast sources depend on the sensors you provide, for example:

* Solcast PV Forecast
* Other Home Assistant sensors exposing today's and tomorrow's PV forecast

---

# 🛠 Installation (HACS)

[![HACS Repository](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=PalmManiac&repository=battery-smartflow-ai&category=integration)

1. Open HACS
2. Search for `Battery SmartFlow AI`
3. Download it
4. Restart Home Assistant

---

# ⚙️ Configuration

After installation:

**Settings → Devices & Services → Add Integration → Battery SmartFlow AI**

---

## 1️⃣ Main configuration

<img src="docs/images/config_00_config.png" width="750">

Here you select:

* Device profile
* Battery SoC sensor
* Battery AC power sensor
* PV power sensor
* Electricity price (optional)
* Price history / forecast (optional)
* PV forecast today / tomorrow (optional)
* Zendure AC mode
* Charge & discharge entities
* Grid mode
* Additional battery charge/discharge sensors (optional)
* Off-grid / island socket sensors (optional)
* SoC limit status sensor (optional)

📖 Detailed explanations can be found in the **manual**.

---

## 2️⃣ Grid measurement

You can choose between:

* No grid sensor
* One combined sensor (+/-)
* Two sensors (import & export)

Recommended: **two separate sensors**.

---

## 3️⃣ Split sensor selection

When using split mode, select:

* Grid import
* Grid export

separately.

---

## 4️⃣ Expert mode

The expert menu provides access to:

* Learned charge-window planning
* Cell-voltage protection
* Advanced diagnostics

The unified power regulation is the mandatory command path for all installations.

---

## 5️⃣ Off-grid / island socket configuration

<img src="docs/images/conf_06_offgrid.png" width="700">

For Zendure systems with an off-grid / island socket, optional sensors can be configured:

* Off-grid power
* Off-grid mode

The off-grid mode is only read by Battery SmartFlow AI. It is **never** controlled or changed by the integration.

Positive off-grid power values are interpreted as an active load at the island socket.

---

# ⚙️ Device profiles

The integration uses model-dependent control parameters.

Currently supported profiles include:

* SolarFlow 800 Pro
* SolarFlow 800 Pro 2
* SolarFlow 1600 AC
* SolarFlow 2400 AC
* SolarFlow 2400 AC+
* SolarFlow 2400 Pro
* Hyper 2000
* HUB 2000

The profile influences, among other things:

* Hardware input/output limits
* Target grid import
* Regulation speed
* Export guard
* Charge and discharge step limits
* Stable import/export cycle thresholds
* Mode-switch cooldowns
* Low-SoC behavior
* Off-grid capability
* Device-specific safety behavior

The profile editor allows advanced users to tune selected parameters directly from Home Assistant.

---

# 🔁 Unified power regulation

Battery SmartFlow AI uses one authoritative technical regulation chain:

**Decision Engine → StrategyIntent → ModeArbiter → PowerController → DeviceCommand**

The Decision Engine remains the strategic layer. It decides **what** should happen.

The new technical regulation layer decides:

* whether a mode change is technically allowed now
* how quickly power should be changed
* whether INPUT or OUTPUT should be held briefly
* whether a command should be written or skipped
* how to reduce mode flapping and unnecessary service calls

This improves behavior during:

* fast load changes
* cloudy PV conditions
* PV charge start/stop transitions
* output overshoot situations
* low-power regulation near 0 W
* sensitive smaller systems such as 800 W class devices

The improved regulation is optional and can be enabled in the expert menu.

---

# 🧠 Learned charge-window planning

Battery SmartFlow AI can learn the typical household consumption profile.

The learned planning uses:

* historic load data
* 15-minute slots
* daily usage patterns
* current battery SoC
* SoC minimum / maximum
* PV forecast adjustment
* price forecast data
* realistic effective charge power

It only becomes active once enough training data is available.

Until then, classic planning remains active.

Diagnostic sensors show:

* learning status
* data coverage
* usable history days
* expected consumption
* required charge energy
* planned charge start
* planning deadline
* selected charge window
* blocking reason

---

# 🔌 Off-grid / island socket support

Battery SmartFlow AI supports optional evaluation of Zendure off-grid / island socket sensors.

If configured, the integration can detect active off-grid loads and prevent automatic AC/grid charging from overriding the island socket behavior.

Supported off-grid mode values:

* `off`
* `normal`
* `eco`

When off-grid load is active, Battery SmartFlow AI can use a technical support mode:

`offgrid_load_support`

This means:

* the island socket is actively supplied via battery/PV where possible
* automatic price/planning/grid charging is blocked during active off-grid load
* emergency charging, cell-voltage emergency charging and manual charging remain allowed
* SoC minimum, SoC limits and cell-voltage protection are still respected
* this technical support is not counted as economic price discharge

Note: The exact behavior above device or national limits depends on Zendure firmware and regional settings.

---

# 🔋 Additional battery detection

Battery SmartFlow AI can optionally monitor another battery system.

Supported optional sensors:

* Additional battery charge power
* Additional battery discharge power

This helps avoid unwanted battery-to-battery behavior:

* if another battery is charging, BSFAI can block discharge
* if another battery is discharging, BSFAI can block charging

This prevents false PV surplus detection and unwanted energy transfer between battery systems.

---

# 🛡 Safety mechanisms

Battery SmartFlow AI includes multiple safety mechanisms:

* SoC minimum / SoC maximum
* SoC limit status from Zendure/BMS
* Emergency charging
* Cell-voltage protection
* Cell-voltage emergency charging
* Discharge resume hysteresis
* Hard-sync with real Zendure AC mode
* Protection against unwanted discharge during low SoC
* Protection against unwanted charging during additional battery discharge

Technical regulation holds are not allowed to override SoC or cell-voltage protection.

---

# 🧠 Peak factor (Adaptive Peak)

The peak factor can be adjusted via the GUI and influences the detection of price peaks.

Formula:

Peak threshold = max(
Average price × Peak factor,
Average price + €0.03
)

Default: **1.35**

* Lower → detects more peaks (more sensitive)
* Higher → detects only strong price peaks (more conservative)

---

# 📊 Diagnostics and transparency sensors

Battery SmartFlow AI provides detailed diagnostic and transparency sensors, for example:

* Ø daily price
* Current peak threshold
* Current valley threshold
* Economic discharge threshold
* Effective discharge threshold
* Engine status
* Adaptive peak active
* Forecast status
* PV outlook
* Learned planning status
* Learned planning blocking reason
* Learned profile diagnostics
* Grid history diagnostics
* Regulation mode arbiter reason
* Regulation target and final power
* Device command diagnostics
* Off-grid mode
* Off-grid load active
* Off-grid rule reason
* Cell-voltage status
* SoC limit status

<img src="docs/images/sensors_03_diagnose.png" width="350">

---

# 💶 Profit / savings

The integration can show:

* Ø charging price (weighted average)
* Charged energy
* Discharged energy
* Price difference
* Total profit / savings in €

Technical support modes such as off-grid support or PV house-load passthrough are not counted as economic price discharge.

Note: Details about the calculation are in the **manual**.

---

# 🔄 Operating modes

## Automatic (recommended)

Combines price, PV, forecast, learned planning and load data.

## Autarky

Focus on autonomy and covering household load.

## Manual

No AI interventions. Charging, discharging, constant discharge and standby can be selected manually.

---

# 📖 Documentation

This README provides an overview.

For detailed setup, screenshots, examples, FAQ and troubleshooting, see:

* **Manual**

---

# Support & Contribution

* GitHub Issues for bugs & feature requests
* Pull Requests welcome

---

**Battery SmartFlow AI – understandable, stable, economical.**

---

**Deutsche Version**

# Battery SmartFlow AI

**Intelligente, wirtschaftliche und stabile Steuerung für Zendure SolarFlow Systeme in Home Assistant**

*Achtung: Aktuell wird nur ein einzelnes Batteriesystem unterstützt. Die koordinierte Unterstützung mehrerer Batteriesysteme ist für eine spätere Hauptversion geplant.*

---

## Was macht diese Integration?

**Battery SmartFlow AI** steuert dein Zendure SolarFlow System automatisch – basierend auf:

* ☀️ PV-Erzeugung
* 🏠 Realer Hauslast
* 🔋 Batterie-SoC
* 💶 Dynamischen Strompreisen (optional)
* 🌦️ PV-Prognosedaten (optional)
* 🧠 Gelernter Verbrauchs- und Ladefenster-Planung
* ⚙️ Gerätespezifischen Regelprofilen
* 🧩 Optionaler Zusatzakku- und Off-Grid-Erkennung

Die Integration kombiniert diese Daten zu einer **physikalisch stabilen und wirtschaftlich optimierten Lade- und Entladestrategie**.

Ziel:

> Minimaler Netzbezug.
> Maximale Wirtschaftlichkeit.
> Stabiles Laden und Entladen.
> Keine hektischen INPUT-/OUTPUT-Richtungswechsel.

---

# 🧠 Kernfunktionen / einheitliche Architektur

* Adaptive Peak-Erkennung für teure Preisfenster
* Preis-Vorplanung mit Tal-Erkennung
* Lernbasierte Ladefenster-Planung anhand historischer Hauslast
* Optionale PV-Prognoseintegration
* Dynamische Netzregelung statt einfacher Vollgas-Schaltung
* Einheitliche Leistungsregelung mit Netz-Historie, stabilerer Modusfreigabe und geglätteter Leistungssteuerung
* Geräteprofile pro Zendure-Modell
* Profil-Editor für Lade-/Entlade-Tuning
* Hard-Sync mit realem Zendure AC-Modus
* Transparenz- und Diagnose-Sensoren
* Gewinn-/Ersparnis-Berechnung
* Saisonneutrale Automatik mit saisonalem Kontext
* Optionale Zusatzakku-Erkennung
* Optionale Off-Grid-/Inselsteckdosen-Unterstützung
* Optionaler Zellspannungs-Schutz

---

# ⚠️ Zwingende Voraussetzungen

Damit die Integration korrekt arbeitet, **müssen** folgende Punkte erfüllt sein:

---

## 1️⃣ Zendure Original-App

In der Zendure App:

* Ladeleistung → Maximum
* Entladeleistung → Maximum
* HEMS → deaktivieren
* Keine parallelen Automationen

⚠️ Die Steuerung erfolgt ausschließlich über Home Assistant.

---

## 2️⃣ Zendure Home Assistant Integration

Folgende Einstellungen sind zwingend erforderlich:

* Kein P1-Sensor in der Zendure-Integration auswählen
* Energie-Export: **Erlaubt**
* Zendure Manager → Betriebsmodus **AUS**

Falsche Einstellungen können führen zu:

* Blockierten AC-Modi
* Entladeabbrüchen
* Instabiler Regelung
* Unerwartetem INPUT-/OUTPUT-Verhalten

---

## 3️⃣ Netzsensor korrekt konfigurieren

Empfohlen:

* Split-Modus mit separatem Bezug & Einspeisung
  (z. B. Shelly Pro 3EM)

Unterstützt werden:

* Kein Netzsensor
* Ein kombinierter Sensor mit positivem Bezug / negativer Einspeisung
* Zwei separate Sensoren für Bezug und Einspeisung

Für die beste Regelqualität wird eine stabile lokale Netzleistungsquelle empfohlen.

---

## 4️⃣ Strompreis-Integration (optional)

Unterstützte Preisquellen sind unter anderem:

* Tibber
* EPEX
* Octopus Energy, inklusive deutscher Forecast API

Ohne Strompreis funktioniert PV- und lastbasierte Steuerung weiterhin.

---

## 5️⃣ PV-Prognoseintegration (optional)

PV-Prognosesensoren sind optional.

Sie können die Ladeplanung verbessern, Battery SmartFlow AI funktioniert aber auch ohne Prognosedaten.

Unterstützt werden passende Home-Assistant-Sensoren, z. B.:

* Solcast PV Forecast
* andere Sensoren für PV-Prognose heute und morgen

---

# 🛠 Installation (HACS)

[![HACS Repository](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=PalmManiac&repository=battery-smartflow-ai&category=integration)

1. HACS öffnen
2. nach `Battery SmartFlow AI` suchen
3. herunterladen
4. Home Assistant neu starten

---

# ⚙️ Konfiguration

Nach der Installation:

**Einstellungen → Geräte & Dienste → Integration hinzufügen → Battery SmartFlow AI**

---

## 1️⃣ Hauptkonfiguration

<img src="docs/images/config_00_config.png" width="750">

Hier werden ausgewählt:

* Geräteprofil
* Batterie-SoC Sensor
* Batterie-AC-Leistungssensor
* PV-Leistungssensor
* Strompreis (optional)
* Preisverlauf / Preisprognose (optional)
* PV-Prognose heute / morgen (optional)
* Zendure AC-Modus
* Lade- & Entlade-Entitäten
* Netzmodus
* Zusatzakku Lade-/Entladesensoren (optional)
* Off-Grid-/Inselsteckdosen-Sensoren (optional)
* SoC-Limit Statussensor (optional)

📖 Detaillierte Erklärungen findest du in der **Anleitung**.

---

## 2️⃣ Netzmessung

Du kannst wählen zwischen:

* Kein Netzsensor
* Ein kombinierter Sensor (+/-)
* Zwei Sensoren (Bezug & Einspeisung)

Empfohlen: **zwei separate Sensoren**.

---

## 3️⃣ Split-Sensor Auswahl

Im Split-Modus werden:

* Netzbezug
* Netzeinspeisung

separat ausgewählt.

---

## 4️⃣ Expertenmodus

Im Expertenmenü findest du:

* Lernbasierte Ladefenster-Planung
* Zellspannungs-Schutz
* Erweiterte Diagnosen

Die verbesserte Leistungsregelung ist ab V4.3.0-Dev8.1 für alle Installationen
verbindlich aktiv und muss nicht mehr gesondert eingeschaltet werden.

---

## 5️⃣ Off-Grid-/Inselsteckdosen-Konfiguration

<img src="docs/images/conf_06_offgrid.png" width="700">

Für Zendure-Systeme mit Off-Grid-/Inselsteckdose können optionale Sensoren konfiguriert werden:

* Off-Grid-Leistung
* Off-Grid-Modus

Der Off-Grid-Modus wird von Battery SmartFlow AI nur gelesen. Er wird **niemals** durch die Integration gesetzt oder verändert.

Positive Off-Grid-Leistungswerte werden als aktive Last an der Inselsteckdose interpretiert.

---

# ⚙️ Geräteprofile

Die Integration nutzt modellabhängige Regelparameter.

Aktuell unterstützte Profile:

* SolarFlow 800 Pro
* SolarFlow 800 Pro 2
* SolarFlow 1600 AC
* SolarFlow 2400 AC
* SolarFlow 2400 AC+
* SolarFlow 2400 Pro
* Hyper 2000
* HUB 2000

Das Profil beeinflusst u. a.:

* Hardware-Grenzen für INPUT/OUTPUT
* Ziel-Netzbezug
* Regelgeschwindigkeit
* Export-Schutz
* Lade- und Entlade-Schrittweiten
* stabile Import-/Export-Zyklen
* Moduswechsel-Cooldowns
* Low-SoC-Verhalten
* Off-Grid-Fähigkeiten
* gerätespezifisches Schutzverhalten

Der Profil-Editor erlaubt fortgeschrittenen Nutzern, ausgewählte Parameter direkt in Home Assistant feinzujustieren.

---

# 🔁 Einheitliche Leistungsregelung

Die verbesserte technische Regelkette ist ab V4.3.0-Dev8.1 der verbindliche
Befehlsweg:

**Decision Engine → StrategyIntent → ModeArbiter → PowerController → DeviceCommand**

Die Decision Engine bleibt die strategische Ebene. Sie entscheidet, **was** passieren soll.

Die neue technische Regelung entscheidet danach:

* ob ein Moduswechsel jetzt technisch erlaubt ist
* wie schnell Leistung verändert werden soll
* ob INPUT oder OUTPUT kurz gehalten werden soll
* ob ein Befehl geschrieben oder übersprungen werden kann
* wie Flattern und unnötige Service Calls reduziert werden

Das verbessert das Verhalten bei:

* schnellen Lastwechseln
* wechselnder Bewölkung
* PV-Ladestart und PV-Ladestopp
* OUTPUT-Überschwingen
* Regelung nahe 0 W
* empfindlicheren kleineren Systemen wie 800-W-Klassen

---

# 🧠 Lernbasierte Ladefenster-Planung

Battery SmartFlow AI kann das typische Verbrauchsprofil des Haushalts lernen.

Die Lernplanung nutzt:

* historische Hauslastdaten
* 15-Minuten-Slots
* typische Tagesverläufe
* aktuellen Batterie-SoC
* SoC-Minimum / SoC-Maximum
* PV-Prognose-Zuschlag
* Preisprognosedaten
* realistische effektive Ladeleistung

Sie wird erst aktiv, sobald genügend Lerndaten vorhanden sind.

Bis dahin bleibt automatisch die klassische Planung aktiv.

Diagnosesensoren zeigen:

* Lernstatus
* Datenabdeckung
* nutzbare Historientage
* erwarteten Verbrauch
* benötigte Nachladeenergie
* geplanten Ladestart
* Planungs-Deadline
* gewähltes Ladefenster
* Blockierungsgrund

---

# 🔌 Off-Grid-/Inselsteckdosen-Unterstützung

Battery SmartFlow AI unterstützt optional die Auswertung von Zendure Off-Grid-/Inselsteckdosen-Sensoren.

Wenn diese konfiguriert sind, kann die Integration aktive Off-Grid-Lasten erkennen und verhindern, dass automatische AC-/Netzladung das Verhalten der Inselsteckdose überstimmt.

Unterstützte Off-Grid-Moduswerte:

* `off`
* `normal`
* `eco`

Bei aktiver Off-Grid-Last kann Battery SmartFlow AI einen technischen Unterstützungsmodus verwenden:

`offgrid_load_support`

Das bedeutet:

* die Inselsteckdose wird soweit möglich über Akku/PV unterstützt
* automatische Preis-, Planungs- oder Netzladung wird während aktiver Off-Grid-Last blockiert
* Notladung, Zellspannungs-Notladung und manuelles Laden bleiben erlaubt
* SoC-Minimum, SoC-Limits und Zellspannungs-Schutz werden weiter respektiert
* diese technische Unterstützung wird nicht als wirtschaftliche Preisentladung gezählt

Hinweis: Das genaue Verhalten oberhalb geräte- oder länderspezifischer Grenzen hängt von Zendure-Firmware und regionalen Einstellungen ab.

---

# 🔋 Zusatzakku-Erkennung

Battery SmartFlow AI kann optional ein weiteres Akkusystem beobachten.

Optionale Sensoren:

* Zusatzakku Ladeleistung
* Zusatzakku Entladeleistung

Damit wird unerwünschtes Akku-zu-Akku-Verhalten vermieden:

* wenn ein anderer Akku lädt, kann BSFAI die Entladung blockieren
* wenn ein anderer Akku entlädt, kann BSFAI das Laden blockieren

Dadurch werden falsche PV-Überschusserkennung und ungewollte Energieverschiebung zwischen Akkusystemen vermieden.

---

# 🛡 Sicherheitsmechanismen

Battery SmartFlow AI enthält mehrere Schutzmechanismen:

* SoC-Minimum / SoC-Maximum
* SoC-Limit Status von Zendure/BMS
* Notladung
* Zellspannungs-Schutz
* Zellspannungs-Notladung
* Entlade-Wiederfreigabe-Hysterese
* Hard-Sync mit realem Zendure AC-Modus
* Schutz gegen unerwünschte Entladung bei niedrigem SoC
* Schutz gegen unerwünschtes Laden bei entladendem Zusatzakku

Technische Haltezustände dürfen SoC- oder Zellspannungs-Schutz nicht überstimmen.

---

# 🧠 Peak-Faktor (Adaptive Peak)

Der Peak-Faktor ist über die GUI einstellbar und beeinflusst die Erkennung von Preisspitzen.

Formel:

Peak-Schwelle = max(
Durchschnittspreis × Peak-Faktor,
Durchschnittspreis + 0,03 €
)

Standard: **1.35**

* Niedriger → erkennt mehr Peaks (sensitiver)
* Höher → erkennt nur starke Preisspitzen (konservativer)

---

# 📊 Diagnose- und Transparenzsensoren

Battery SmartFlow AI stellt umfangreiche Diagnose- und Transparenzsensoren bereit, z. B.:

* Ø Tagespreis
* aktuelle Peak-Schwelle
* aktuelle Tal-Schwelle
* ökonomische Entladeschwelle
* effektive Entladeschwelle
* Engine-Status
* Adaptive Peak aktiv
* Prognose-Status
* PV-Ausblick
* Lernplanungsstatus
* Lernplanung Blockierungsgrund
* gelernte Profil-Diagnosen
* Netz-Historie-Diagnosen
* Regelgrund des ModeArbiters
* Ziel- und Endleistung der Regelung
* DeviceCommand-Diagnosen
* Off-Grid-Modus
* Off-Grid-Last aktiv
* Regelgrund Off-Grid
* Zellspannungs-Status
* SoC-Limit Status

<img src="docs/images/sensors_03_diagnose.png" width="350">

---

# 💶 Gewinn / Ersparnis

Die Integration kann sichtbar machen:

* Ø Ladepreis (gewichteter Durchschnitt)
* geladene Energie
* entladene Energie
* Preis-Differenz
* Gesamtgewinn / Gesamtersparnis in €

Technische Unterstützungsmodi wie Off-Grid-Support oder PV-Hauslast-Passthrough werden nicht als wirtschaftliche Preisentladung gezählt.

Hinweis: Details zur Berechnung stehen in der **Anleitung**.

---

# 🔄 Betriebsmodi

## Automatik (empfohlen)

Kombiniert Preis, PV, Prognose, Lernplanung und Lastdaten.

## Autarkie

Autarkie-Fokus und Hauslastdeckung.

## Manuell

Keine KI-Eingriffe. Laden, Entladen, konstante Entladung und Standby können manuell gewählt werden.

---

# 📖 Dokumentation

Diese README bietet eine Übersicht.

Für detaillierte Einrichtung, Screenshots, Beispiele, FAQ und Troubleshooting siehe:

* **Anleitung**

---

# Support & Mitwirkung

* GitHub Issues für Bugs & Feature-Wünsche
* Pull Requests willkommen

---

**Battery SmartFlow AI – erklärbar, stabil, wirtschaftlich.**
