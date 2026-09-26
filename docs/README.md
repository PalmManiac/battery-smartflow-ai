# Battery SmartFlow AI – Dokumentation

Battery SmartFlow AI steuert unterstützte Zendure-Batteriesysteme in Home
Assistant anhand von PV-Erzeugung, Hausverbrauch, Ladezustand und optionalen
Strompreisen sowie PV-Prognosen.

## Battery SmartFlow AI wird unabhängig

Seit V5 kann BSFAI ein Zendure-System direkt erkennen und steuern. Hauptgerät
und Akku-Packs erscheinen als eigene Home-Assistant-Geräte; Z-HA ist für diesen
Weg nicht mehr erforderlich. Der bisherige Weg über vorhandene HA-Entitäten
bleibt verfügbar. Aktuell wird ein Hauptsystem zur Steuerung ausgewählt.

Die konkrete Daten- und Steuerverbindung hängt vom Modell ab: ZenSDK,
lokales MQTT oder Cloud MQTT. Bei allen Wegen gilt: Nur ein Regler darf
gleichzeitig Befehle an dasselbe Gerät senden.

## Einstieg

- [Installation über HACS](installation.md)
- [Deutsche Anleitung mit bebildertem V5-Schnellstart](anleitung.md#v5-schnellstart-zendure-direkt-verbinden)
- [English user guide with illustrated V5 quick start](user-guide.md#v5-quick-start-connect-zendure-directly)
- [V5.1.0 HEMS Portal overview (German)](anleitung.md#v510-das-bsfai-portal)
- [V5.1.0 HEMS Portal overview (English)](user-guide.md#v510-the-bsfai-portal)
- [Wirtschaft & Preise im Dashboard](dashboard-wirtschaft-preise.md)

V5 ist jetzt die aktuelle stabile Version. Bei einer bestehenden V4-Installation
solltest du vor dem Umstieg ein Home-Assistant-Backup erstellen und die
Ersteinrichtung mit einem eindeutigen Steuerungsweg durchführen. Fehlen
aktuelle Akku-Daten, bleibt BSFAI aus Sicherheitsgründen im Leerlauf.

## Support und Mitwirkung

Fehler und Funktionswünsche gehören in die
[GitHub-Issues](https://github.com/PalmManiac/battery-smartflow-ai/issues);
Erfahrungen mit noch wenig getesteten Modellen helfen besonders. Teile
Debug-Dateien erst nach einer Prüfung auf persönliche Informationen.
