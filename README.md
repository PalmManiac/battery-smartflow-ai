# Battery SmartFlow AI

---

![GitHub Release](https://img.shields.io/github/v/release/PalmManiac/battery-smartflow-ai?style=for-the-badge)
![Maintained](https://img.shields.io/badge/Maintained-Yes-green?style=for-the-badge)
![GitHub Repo Size](https://img.shields.io/github/repo-size/PalmManiac/battery-smartflow-ai?style=for-the-badge)
[![Active installs](https://badge.t-haber.de/badge/battery_smartflow_ai?kill_cache=1)](https://github.com/PalmManiac/battery-smartflow-ai/)
![GitHub Stars](https://img.shields.io/github/stars/PalmManiac/battery-smartflow-ai?style=for-the-badge)
![License](https://img.shields.io/github/license/PalmManiac/battery-smartflow-ai?style=for-the-badge)
![HACS](https://img.shields.io/badge/HACS-Default-blue?style=for-the-badge)

---

<img src="docs/images/infografik.png" width="900">

**Intelligent, economic and stable control for Zendure SolarFlow systems in Home Assistant**


---

# 🌍 Language

- 🇬🇧 English
- 🇩🇪 Deutsch
- FR French
- NL Dutch

---


## What does this integration do?

**Battery SmartFlow AI** automatically controls your Zendure SolarFlow system – based on:

- ☀️ PV generation
- 🏠 Real household load
- 🔋 Battery SoC
- 💶 Dynamic electricity prices (optional)
- ⚙️ Device-specific control profiles

The integration combines this data into a **physically stable and economically optimized charging and discharging strategy**.

Goal:

> Minimal grid import.  
> Maximum economic efficiency.  
> No hectic direction changes.

---

# 🧠 Core functions (V2 architecture)

- Adaptive peak detection (individually configurable)
- Price pre-planning with valley detection
- Dynamic grid regulation (regulation instead of full power)
- Device profiles per model
- Hard-sync with real AC mode
- Transparency sensors for price logic
- Profit / savings calculation
- Seasonal logic (summer/winter)

---

# ⚠️ Mandatory prerequisites

For the integration to work correctly, the following points **must** be fulfilled:

---

## 1️⃣ Zendure original app

In the Zendure app:

- Charge power → Maximum
- Discharge power → Maximum
- HEMS → disabled
- No parallel automations

⚠️ Control takes place exclusively via Home Assistant.

---

## 2️⃣ Zendure Home Assistant integration

The following settings are mandatory:

- Do not select a P1 sensor
- Energy export: **Allowed**
- Zendure Manager → Operating mode **OFF**

Incorrect settings lead to:

- Blocked AC modes
- Discharge interruptions
- Unstable regulation

---

## 3️⃣ Configure grid sensor correctly

Recommended:

- Split mode with separate import & export  
  (e.g. Shelly Pro 3EM)

---

## 4️⃣ Electricity price integration (optional)

Supported:

- Tibber
- EPEX
- Octopus (including German Forecast API)

Without an electricity price, PV- and load-based control still works.

---

# 🛠 Installation (HACS)

[![HACS Repository](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=PalmManiac&repository=battery-smartflow-ai&category=integration)

1. Open HACS  
2. search for 'Battery SmartFlow AI'
3. download it
4. restart Home Assistant

---

# ⚙️ Configuration

After installation:

**Settings → Devices & Services → Add Integration → Battery SmartFlow AI**

---

## 1️⃣ Main configuration

<img width="635" height="1186" alt="Screenshot 2026-02-19 134834" src="https://github.com/user-attachments/assets/541d5438-d41f-4595-8456-b93a5f5f41b7" /><img width="633" height="1228" alt="Screenshot 2026-02-25 141115" src="https://github.com/user-attachments/assets/23c3cc0b-938d-44b7-800a-7ad5fdc11711" />

Here you select:

- Device profile
- Battery SoC sensor
- PV power
- Electricity price (optional)
- Price history (optional)
- Zendure AC mode
- Charge & discharge entities
- Grid mode

📖 Detailed explanations can be found in the **manual (V2)**.

---

## 2️⃣ Grid measurement

<img width="631" height="708" alt="Screenshot 2026-02-25 141200" src="https://github.com/user-attachments/assets/c86a8dce-c792-426a-8b33-9b01ffbba776" />

You can choose between:

- No grid sensor
- One combined sensor (+/-)
- Two sensors (import & export)

Recommended: **Two sensors**.

---

## 3️⃣ Split sensor selection

<img width="421" height="475" alt="Screenshot 2026-02-25 141224" src="https://github.com/user-attachments/assets/d0dc939a-be84-4b70-8053-29207e3612ba" />

Here you select:

- Grid import
- Grid export

separately.

---

# ⚙️ Device profiles

The integration uses model-dependent control parameters.

Currently supported:

- SolarFlow 800 Pro (SF800Pro)
- SolarFlow 1600 AC+ (SF1600AC+)
- SolarFlow 2400 AC (SF2400AC)
- SolarFlow 2400 Pro (SF2400PRO)
- Hyper 2000
- Hub 2000

The profile influences, among other things:

- Target grid import
- Regulation speed
- Export tolerance
- Hardware limits

---

# 🧠 Peak factor (Adaptive Peak)

The peak factor can be adjusted via the GUI and influences the detection of price peaks.

Formula:

Peak threshold = max(
Average price × Peak factor,
Average price + €0.03
)

Default: **1.35**

- Lower → detects more peaks (more sensitive)
- Higher → detects only strong price peaks (more conservative)

---

# 📊 Transparency sensors (V2)

V2 makes the price logic visible, e.g.:

- Ø daily price
- Current peak threshold
- Engine status
- Adaptive peak active

---

# 💶 Profit / savings

The integration can show:

- Ø charging price (weighted average)
- Discharged energy
- Price difference
- Total profit in €

Note: Details about the calculation are in the **manual (V2)**.

---

# 🔄 Operating modes

## Automatic (recommended)

Price + PV + load combined.

## Summer

Focus on autonomy, without price planning.

## Winter

Focus on economic efficiency, with price planning.

## Manual

No AI interventions, charging/discharging/standby manually.

---

# 🛡 Safety mechanisms

- SoC minimum / SoC maximum
- BMS limit detection (SoC limit status)
- Emergency charging function
- Hard-sync with real Zendure AC mode

---

# 📖 Documentation

This README provides an overview.

For details (including screenshots, examples, FAQ) see:

- **Manual (V2)**

---

# Support & Contribution

- GitHub Issues for bugs & feature requests
- Pull Requests welcome

---

**Battery SmartFlow AI – understandable, stable, economical.**

---

**Deutsche Version**

# Battery SmartFlow AI

**Intelligente, wirtschaftliche und stabile Steuerung für Zendure SolarFlow Systeme in Home Assistant**

---

## Was macht diese Integration?

**Battery SmartFlow AI** steuert dein Zendure SolarFlow System automatisch – basierend auf:

- ☀️ PV-Erzeugung
- 🏠 Realer Hauslast
- 🔋 Batterie-SoC
- 💶 Dynamischen Strompreisen (optional)
- ⚙️ Gerätespezifischen Regelprofilen

Die Integration kombiniert diese Daten zu einer **physikalisch stabilen und wirtschaftlich optimierten Lade- und Entladestrategie**.

Ziel:

> Minimaler Netzbezug.  
> Maximale Wirtschaftlichkeit.  
> Keine hektischen Richtungswechsel.

---

# 🧠 Kernfunktionen (V2 Architektur)

- Adaptive Peak-Erkennung (individuell einstellbar)
- Preis-Vorplanung mit Valley-Erkennung
- Dynamische Netzregelung (Regelung statt Vollgas)
- Geräteprofile pro Modell
- Hard-Sync mit realem AC-Modus
- Transparenz-Sensoren für Preislogik
- Gewinn-/Ersparnis-Berechnung
- Saisonale Logik (Sommer/Winter)

---

# ⚠️ Zwingende Voraussetzungen

Damit die Integration korrekt arbeitet, **müssen** folgende Punkte erfüllt sein:

---

## 1️⃣ Zendure Original-App

In der Zendure App:

- Ladeleistung → Maximum
- Entladeleistung → Maximum
- HEMS → deaktivieren
- Keine parallelen Automationen

⚠️ Die Steuerung erfolgt ausschließlich über Home Assistant.

---

## 2️⃣ Zendure Home Assistant Integration

Folgende Einstellungen sind zwingend erforderlich:

- Kein P1-Sensor auswählen
- Energie-Export: **Erlaubt**
- Zendure Manager → Betriebsmodus **AUS**

Falsche Einstellungen führen zu:

- Blockierten AC-Modi
- Entladeabbrüchen
- Instabiler Regelung

---

## 3️⃣ Netzsensor korrekt konfigurieren

Empfohlen:

- Split-Modus mit separatem Bezug & Einspeisung  
  (z. B. Shelly Pro 3EM)

---

## 4️⃣ Strompreis-Integration (optional)

Unterstützt:

- Tibber
- EPEX
- Octopus (inkl. deutscher Forecast API)

Ohne Strompreis funktioniert PV- und lastbasierte Steuerung weiterhin.

---

# 🛠 Installation (HACS)

[![HACS Repository](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=PalmManiac&repository=battery-smartflow-ai&category=integration)

1. HACS öffnen  
2. suche nach 'Battery SmartFlow AI'  
3. Herunterladen 
4. Home Assistant neu starten

---

# ⚙️ Konfiguration

Nach der Installation:

**Einstellungen → Geräte & Dienste → Integration hinzufügen → Battery SmartFlow AI**

---

## 1️⃣ Hauptkonfiguration

<img width="635" height="1186" alt="Screenshot 2026-02-19 134834" src="https://github.com/user-attachments/assets/541d5438-d41f-4595-8456-b93a5f5f41b7" /><img width="633" height="1228" alt="Screenshot 2026-02-25 141115" src="https://github.com/user-attachments/assets/23c3cc0b-938d-44b7-800a-7ad5fdc11711" />

Hier werden ausgewählt:

- Geräteprofil
- Batterie-SoC Sensor
- PV-Leistung
- Strompreis (optional)
- Preisverlauf (optional)
- Zendure AC-Modus
- Lade- & Entlade-Entitäten
- Netzmodus

📖 Detaillierte Erklärungen findest du in der **Anleitung (V2)**.

---

## 2️⃣ Netzmessung

<img width="631" height="708" alt="Screenshot 2026-02-25 141200" src="https://github.com/user-attachments/assets/c86a8dce-c792-426a-8b33-9b01ffbba776" />

Du kannst wählen zwischen:

- Kein Netzsensor
- Ein kombinierter Sensor (+/-)
- Zwei Sensoren (Bezug & Einspeisung)

Empfohlen: **Zwei Sensoren**.

---

## 3️⃣ Split-Sensor Auswahl

<img width="421" height="475" alt="Screenshot 2026-02-25 141224" src="https://github.com/user-attachments/assets/d0dc939a-be84-4b70-8053-29207e3612ba" />

Hier werden:

- Netzbezug
- Netzeinspeisung

separat ausgewählt.

---

# ⚙️ Geräteprofile

Die Integration nutzt modellabhängige Regelparameter.

Aktuell unterstützt:

- SolarFlow 800 Pro (SF800Pro)
- SolarFlow 1600 AC+ (SF1600AC+)
- SolarFlow 2400 AC (SF2400AC)
- SolarFlow 2400 Pro (SF2400PRO)
- Hyper 2000
- Hub 2000

Das Profil beeinflusst u. a.:

- Ziel-Netzbezug
- Regelgeschwindigkeit
- Export-Toleranz
- Hardware-Grenzen

---

# 🧠 Peak-Faktor (Adaptive Peak)

Der Peak-Faktor ist über die GUI einstellbar und beeinflusst die Erkennung von Preisspitzen.

Formel:

Peak-Schwelle = max(
Durchschnittspreis × Peak-Faktor,
Durchschnittspreis + 0,03 €
)

Standard: **1.35**

- Niedriger → erkennt mehr Peaks (sensitiver)
- Höher → erkennt nur starke Preisspitzen (konservativer)

---

# 📊 Transparenz-Sensoren (V2)

V2 macht die Preislogik sichtbar, z. B.:

- Ø Tagespreis
- Aktuelle Peak-Schwelle
- Engine-Status
- Adaptive Peak aktiv

---

# 💶 Gewinn / Ersparnis

Die Integration kann:

- Ø Ladepreis (gewichteter Durchschnitt)
- Entladene Energie
- Preis-Differenz
- Gesamtgewinn in €

sichtbar machen.

Hinweis: Details zur Berechnung stehen in der **Anleitung (V2)**.

---

# 🔄 Betriebsmodi

## Automatik (empfohlen)
Preis + PV + Last kombiniert.

## Sommer
Autarkie-Fokus, ohne Preisplanung.

## Winter
Wirtschaftlichkeits-Fokus, mit Preisplanung.

## Manuell
Keine KI-Eingriffe, Laden/Entladen/Standby manuell.

---

# 🛡 Sicherheitsmechanismen

- SoC-Minimum / SoC-Maximum
- BMS-Limit-Erkennung (SoC-Limit Status)
- Notladefunktion (Emergency)
- Hard-Sync mit realem Zendure AC-Modus

---

# 📖 Dokumentation

Diese README bietet eine Übersicht.

Für Details (inkl. Screenshots, Beispiele, FAQ) siehe:

- **Anleitung (V2)**

---

# Support & Mitwirkung

- GitHub Issues für Bugs & Feature-Wünsche
- Pull Requests willkommen

---

**Battery SmartFlow AI – erklärbar, stabil, wirtschaftlich.**
