# V4.7.0: Sensor-, Übersetzungs- und Diagnose-Struktur

- Status: Konsolidierung für Issue #278
- Scope: Home-Assistant-Oberfläche, keine Core- oder Strategieänderung

## Sensoroberfläche

Die Sensoren folgen sechs fachlichen Bereichen:

1. Geräte- und Batteriezustand,
2. Strategie und technische Regelung,
3. Planung und Forecast,
4. Marktpreise und Wirtschaft,
5. zeitbegrenztes Debug und Diagnose,
6. Konfiguration und Profilstatus.

Wirtschafts-, Energie- und Preissensoren verwenden weiterhin das virtuelle Gerät
`Wirtschaft & Preise`. Die übrigen nutzerrelevanten Zustände verbleiben am
BSFAI-Hauptgerät. Keys und Unique IDs werden nicht umbenannt; bestehende
Dashboards, Registry-Einträge und Automationen behalten damit ihre Identität.

## Dauerdiagnose und Debug-Paket

Umfangreiche Strategie-, Regelungs-, Planungs- und Rohwertdiagnosen gehören in
das begrenzte JSON-Debug-Paket. Von dieser Diagnoseoberfläche bleiben nur fünf
schlanke Statussensoren dauerhaft Recorder-sichtbar:

- Debug-Aufzeichnung aktiv,
- Ende der Aufzeichnung,
- Anzahl erfasster Datensätze,
- Name des letzten Pakets,
- letzter Fehler.

Der Paketsensor veröffentlicht ausschließlich den Dateinamen. Der vollständige
lokale Pfad bleibt intern beim Coordinator und wird nur zum kontrollierten
Diagnostics-Download verwendet. Freier Fehlertext wird vor der Veröffentlichung
mit demselben Secret-Filter wie das JSON-Paket bereinigt.

## Datenschutz

Debug-Paket und permanente Diagnosewerte filtern unter anderem Tokens,
Authorization-Header, Passwörter, API-Schlüssel, Client-Secrets und freie
Credential-Zuweisungen. Die Diagnostics-Funktion akzeptiert ausschließlich eine
Datei unmittelbar im integrationsspezifischen Debug-Verzeichnis. Persönliche
Pfade werden nicht als Sensorzustand gespeichert.

## Übersetzungen und Einheiten

`strings.json` bleibt die vollständige englische Quelle; Deutsch, Englisch,
Französisch und Niederländisch besitzen dieselben Schlüssel und Enum-Zustände.
Deutsche Begriffe verwenden weiterhin nutzernahe Bezeichnungen wie Netz,
Ladebindung und Regelungsgrund. Geld- und Preissensoren beziehen ihre Einheit
dynamisch aus der aktiven Home-Assistant-Währung; die bestehende Entity-ID
`profit_eur` bleibt nur aus Kompatibilitätsgründen erhalten und zeigt keine fest
verdrahtete EUR-Einheit an.

## Core-Grenze

Sensorbeschreibungen, Translation Keys, Device Classes, State Classes,
Entity Categories und Gerätezuordnungen verbleiben ausschließlich in der
Home-Assistant-Plattform. Die Core-Module kennen diese Oberfläche nicht.
