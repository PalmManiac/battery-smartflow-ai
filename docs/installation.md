## Installation

### Über HACS (empfohlen)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=PalmManiac&repository=battery-smartflow-ai&category=integration)

1. HACS muss in Home Assistant installiert sein.
2. Suche in HACS nach **Battery SmartFlow AI** und installiere die Integration.
   Falls sie nicht gefunden wird, füge
   `https://github.com/PalmManiac/battery-smartflow-ai` als benutzerdefiniertes
   Repository vom Typ **Integration** hinzu.
3. Solange V5 noch als Vorabversion veröffentlicht wird, wähle in HACS
   gegebenenfalls ausdrücklich den aktuellen Release Candidate aus;
   Vorabversionen werden nicht immer automatisch angeboten.
4. Starte Home Assistant neu und öffne **Einstellungen → Geräte & Dienste →
   Integration hinzufügen → Battery SmartFlow AI**.
5. Wähle **Zendure direkt verbinden** oder **Vorhandene HA-Entitäten verwenden**.
   Der [bebilderte V5-Schnellstart](anleitung.md#v5-schnellstart-zendure-direkt-verbinden)
   erklärt den direkten Weg.

Bei einem Upgrade von V4: Erstelle vorher ein Home-Assistant-Backup. Betreibe
Z-HA und die native BSFAI-Steuerung nicht gleichzeitig als Regler für dasselbe
Zendure-Gerät. Der bestehende Entitäten-Weg bleibt nach dem Update zunächst
erhalten; die direkte Zendure-Steuerung wird nicht automatisch aktiviert.
