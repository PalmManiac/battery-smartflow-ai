# Dashboard-Vorlage „Wirtschaft & Preise“

Battery SmartFlow AI erstellt und verändert **kein Dashboard automatisch**. Die
Datei [`dashboard-wirtschaft-preise.yaml`](dashboard-wirtschaft-preise.yaml) ist
ausschließlich eine freiwillige Vorlage mit Home-Assistant-Standardkarten.

## Verwendung

1. Öffne das Gerät **Battery SmartFlow AI – Wirtschaft & Preise**.
2. Notiere die tatsächlichen Entity-IDs der dort angezeigten Sensoren.
3. Öffne eine Dashboard-Ansicht im Rohkonfigurationseditor.
4. Kopiere die gesamte Vorlage oder nur gewünschte Karten.
5. Ersetze alle `sensor.bsfai_...`-Beispiel-IDs durch die IDs deiner Installation.
6. Speichere die Ansicht und prüfe die verfügbaren Statistikdaten.

Die Ersetzung ist notwendig, weil Home Assistant Entity-IDs abhängig von
Sprache, Entity Registry und früheren Installationen vergibt. BSFAI ändert
bestehende Entity-IDs nicht.

Die Vorlage verwendet nur Markdown, Entities, Glance, History Graph und
Statistics Graph. Es werden keine Custom Cards benötigt. Der Sensor „Aktuell –
Einspeisevergütung“ zeigt den dynamischen Exportpreis, wenn eine gültige Quelle
konfiguriert ist, sonst den statischen Rückfalltarif. Statistikdiagramme können
direkt nach dem Update noch leer sein, bis Recorder-Daten vorliegen.
