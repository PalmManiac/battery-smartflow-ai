# BSFAI- und Zendure-Sensorkatalog

Dieser Anhang listet die von der Integration erzeugten Sensoren. BSFAI-Berechnungs- und Statussensoren stehen getrennt von den Zendure-Hardwarewerten.

## Haus & Netz

| Sensor | Bedeutung | `key` |
|---|---|---|
| Netzleistung | Netzleistung des konfigurierten Messsystems. | `grid_power` |
| Shelly-Netzleistung Phase A | Netzleistung auf Phase A laut Shelly Pro 3EM. | `grid_phase_a_power` |
| Shelly-Netzleistung Phase B | Netzleistung auf Phase B laut Shelly Pro 3EM. | `grid_phase_b_power` |
| Shelly-Netzleistung Phase C | Netzleistung auf Phase C laut Shelly Pro 3EM. | `grid_phase_c_power` |
| Hauslast | Zeigt den aus Netzleistung, PV-Leistung und Batteriefluss berechneten Verbrauch des Hauses. | `house_load` |

## Status & Steuerung

| Sensor | Bedeutung | `key` |
|---|---|---|
| Status nativer Zendure-Test | Zeigt „Status nativer Zendure-Test“ für die native Zendure-Beobachtung bzw. -Steuerung.<br>Zustände: Nicht eingerichtet — Funktion deaktiviert; Geräte werden gesucht; Verbindung wird hergestellt; Erstdaten werden erfasst; Beobachtung aktiv; Fehler — Fehler erkannt. | `native_zendure_status` |
| Native Zendure-Steuerung | Zeigt „Native Zendure-Steuerung“ für die native Zendure-Beobachtung bzw. -Steuerung.<br>Zustände: Deaktiviert; Keine Daten; Cloud; Cloud; ZenSDK; Lokal; Nicht unterstützt. | `native_zendure_control` |
| Gefundene native Zendure-Geräte | Zeigt „Gefundene native Zendure-Geräte“ für die native Zendure-Beobachtung bzw. -Steuerung. | `native_zendure_device_count` |
| Empfangene native Zendure-Nachrichten | Zeigt „Empfangene native Zendure-Nachrichten“ für die native Zendure-Beobachtung bzw. -Steuerung. | `native_zendure_message_count` |
| Letzte native Zendure-Nachricht | Zeigt „Letzte native Zendure-Nachricht“ für die native Zendure-Beobachtung bzw. -Steuerung. | `native_zendure_last_message` |
| Paket des nativen Zendure-Erstabgleichs | Zeigt „Paket des nativen Zendure-Erstabgleichs“ für die native Zendure-Beobachtung bzw. -Steuerung. | `native_zendure_last_capture` |
| Fehler nativer Zendure-Test | Zeigt „Fehler nativer Zendure-Test“ für die native Zendure-Beobachtung bzw. -Steuerung. | `native_zendure_error` |
| Zendure-Hardwareverbindung | Zeigt „Zendure-Hardwareverbindung“ für die native Zendure-Beobachtung bzw. -Steuerung.<br>Zustände: Erreichbar — Gerät erreichbar; Verbindung instabil; Nicht erreichbar — Gerät nicht erreichbar; Direktprüfung nicht verfügbar; Unbekannt — Status nicht bekannt. | `native_zendure_watchdog` |
| Aktives Geräteprofil | Für das System verwendetes Geräteprofil. | `device_profile` |
| Adaptiver Peak erkannt | Zeigt, ob ein adaptiver Preishöchststand erkannt wurde.<br>Zustände: Nein — inaktiv; Ja — aktiv. | `adaptive_peak_active` |
| Ladestrategie | Aktuell angewendete Ladstrategie.<br>Zustände: Keine spezielle Ladestrategie aktiv — keine Strategie aktiv; PV-Überschussladung — Laden mit PV-Überschuss; Preisladung am spätesten Startzeitpunkt; Preisladung wegen schwacher PV-Prognose; Preisladung bei gemischter PV-Prognose; Preisladung wegen schwacher Live-PV trotz guter Prognose; Sehr-billig-Schwelle: Maximalladung; Preis-Tal-Ladung; Preis-Tal-Ladung, wegen Prognose abgeschwächt; Notladung; Manuelle Ladestrategie — manuelle Vorgabe; Opportunistische Tal-Ladung; Opportunistische Tal-Ladung bei gemischter Prognose; Lernbasierte Ladefenster-Planung; Strategische Peakreserve. | `charge_strategy` |
| Volladungswartung | Status der geplanten Volladungspflege.<br>Zustände: Unbekannt — Status nicht bekannt; Noch nicht fällig; Bald fällig — Wartung wird bald fällig; Fällig — Wartung ist fällig; Wartet auf günstiges Ladefenster; Lädt vollständig; Bestätigt Volladung; Abgeschlossen — Wartung abgeschlossen; Blockiert — Wartung kann aktuell nicht laufen. | `full_charge_maintenance_state` |
| Volladungswartung aktiv | Zeigt, ob Volladungspflege derzeit aktiv ist.<br>Zustände: Ja — aktiv; Nein — inaktiv. | `full_charge_maintenance_active` |
| Nächste empfohlene Volladung | Zeitpunkt der nächsten empfohlenen Volladung. | `full_charge_maintenance_next_recommended` |
| Engine-Status | Betriebsbereitschaft und erkannte Eingabefehler.<br>Zustände: System normal; Keine Preisdaten verfügbar; Kein aktueller Strompreis; Ungültige Sensordaten. | `engine_health` |
| Regelungskontext | Aktueller Regelungskontext (Preis, PV oder manuell).<br>Zustände: Preis; PV; Manuell — manuelle Vorgabe. | `season_mode` |
| Hardware-SoC-Begrenzungsstatus | Erkannter SoC-Begrenzungsstatus der Hardware.<br>Zustände: Hardware-SoC-Begrenzung nicht verfügbar — Funktion nicht eingerichtet; Kein Limit aktiv; Oberes SoC-Limit aktiv (Laden gesperrt); Unteres SoC-Limit aktiv (Entladen gesperrt). | `soc_limit_status` |
| Fehlerstatus | Zusammenfassende Einstufung erkannter Fehler.<br>Zustände: Kein Fehler / alles normal — Normalbetrieb; Warnung (Gerät läuft weiter); Fehler / Schutz aktiv — Fehler erkannt. | `fault_level_status` |
| Systemstatus | Aktueller Gesamtstatus der BSFAI-Regelung.<br>Zustände: Initialisierung; OK; Sensordaten ungültig; Preisdaten ungültig. | `status` |
| KI-Status | Status der KI-gestützten Regelung.<br>Zustände: Bereitschaft; Laden (PV-Überschuss); Laden (Preisvorteil); Entladen (Hauslast decken); Entladen (hoher Strompreis); Zwangsentladung (extreme Preise); Notladung aktiv; Manueller Modus — manuelle Vorgabe. | `ai_status` |
| KI-Empfehlung | Aktuelle Empfehlung der Regelung.<br>Zustände: Keine Aktion; Laden — Batterie lädt; Entladen — Batterie entlädt; Notladung. | `recommendation` |
| Entscheidungsgrund | Grund für die aktuelle Regelentscheidung.<br>Zustände: Bereitschaft; Kein Bedarf erkannt; Entladen gestartet (Bedarf erkannt); Entladen aktiv (Hauslastdeckung); Laden gestartet (Überschuss erkannt); Laden aktiv; Entladen wegen hohem Strompreis; Zwangsentladung wegen extremer Preisspitze; Notladung aktiv (verriegelt); Autarkie: Hauslast decken; PV-Überschuss laden; Entladung gestoppt (SoC-Minimum erreicht); SF800Pro: PV-Hauslast-Passthrough aktiv; Laden blockiert (oberes SoC-Limit aktiv); Entladen blockiert (unteres SoC-Limit aktiv); Manueller Modus aktiv; Manueller Standby; Manuelles Laden; Manuelles Entladen; Konstante Entladung aktiv; Manuelle Bereitschaft; Bereit — keine Lade- oder Entladeaktivität; Entladen wegen Preisspitze; Preisbasierte Entladung; Preis-Tal erkannt. Maximalladung; Preisladung gestartet (spätester sinnvoller Startzeitpunkt erreicht); Preisladung wegen schwacher PV-Prognose; Preisladung bei gemischter PV-Prognose; Lernbasierte Ladeplanung noch nicht bereit; Lernbasierte Ladeplanung wartet auf optimales Ladefenster; Lernbasiertes Ladefenster aktiv; AC-Ladebindung aktiv; AC-Ladebindung wartet auf Preisfenster; Lernplanung: spätester Startzeitpunkt erreicht; Lernplanung: keine Nachladung erforderlich; Preis-Tal genutzt, da real kaum PV verfügbar ist; Preis-Tal genutzt bei gemischter Prognose und schwacher realer PV; Preis-Tal erkannt, aber wegen gemischter PV-Prognose abgeschwächt; Preisladung gestartet: reale PV zu schwach trotz guter Prognose; Sehr-billig-Schwelle erreicht: Maximalladung aktiv; Zusatzakku lädt: Entladung blockiert; Zusatzakku entlädt: Laden blockiert; Inselsteckdose aktiv: automatische Netzladung blockiert; Inselsteckdose aktiv: Versorgung über Akku/PV; Entladung blockiert (Wiederfreigabe-Schwelle noch nicht erreicht); Entladung blockiert (Zellspannungs-Schutz aktiv); Notladung aktiv (Zellspannung kritisch); PV-Ladung blockiert, da Entladung noch durch SoC-/Zellschutz gesperrt ist; Lernplanung: Deadline zu nah, Start jetzt; Sicherer Leerlauf: Akku-SoC ungültig; Sicherer Leerlauf: native Akkukapazität nicht verfügbar; Sicherer Leerlauf: Netzsensordaten fehlen; Entladung bei Netzsensor-Aussetzer vorübergehend gehalten; Sicherer Leerlauf: konfigurierte SoC-Grenzen ungültig; Sicherer Leerlauf: konfigurierte Leistungsgrenzen ungültig; Entladung blockiert: Zellspannungssensor nicht verfügbar; Automatik: Hochpreisfenster absichern; Automatik: Akku-Reserve für spätere Preisspitze halten. | `decision_reason` |
| Nächste Aktion | Geplante nächste Aktion und ihr Status.<br>Zustände: Keine Aktion geplant — keine Strategie aktiv; Geplantes Laden; Geplante Entladung; Ladevorgang aktiv; Entladevorgang aktiv; Entladung freigegeben – wartet auf Netzbezug; Manuelles Laden; Manuelle Entladung; Konstante Entladung aktiv; Notladung; SF800Pro: PV-Hauslast-Passthrough aktiv. | `next_action_state` |
| Startzeit nächste Aktion | Geplanter Zeitpunkt der nächsten Aktion. | `next_action_time` |

## PV-Prognose

| Sensor | Bedeutung | `key` |
|---|---|---|
| Prognose-Status | Zeigt die nach Verbrauch und Systemverlusten nutzbare PV-Energie für Prognose-Status.<br>Zustände: Nicht konfiguriert — Funktion nicht eingerichtet; Keine Prognosedaten verfügbar — keine Daten verfügbar; Prognosedaten verfügbar — Daten verfügbar. | `forecast_status` |
| PV-Ausblick | Zusammenfassung des erwarteten PV-Verlaufs.<br>Zustände: Unbekannt — Status nicht bekannt; Schwach — ungünstiger PV-Ausblick; Gemischt — uneinheitlicher PV-Ausblick; Gut — günstiger PV-Ausblick. | `pv_outlook` |
| Nutzbare PV-Prognose – Rest heute | Zeigt die nach Verbrauch und Systemverlusten nutzbare PV-Energie für Rest heute. | `forecast_remaining_today_kwh` |
| Nutzbare PV-Prognose – morgen | Zeigt die nach Verbrauch und Systemverlusten nutzbare PV-Energie für morgen. | `forecast_tomorrow_kwh` |
| Nutzbare PV-Prognose – nächste 3 Stunden | Zeigt die nach Verbrauch und Systemverlusten nutzbare PV-Energie für nächste 3 Stunden. | `forecast_next_3h_kwh` |
| Nutzbare PV-Prognose – nächste 6 Stunden | Zeigt die nach Verbrauch und Systemverlusten nutzbare PV-Energie für nächste 6 Stunden. | `forecast_next_6h_kwh` |
| PV-Prognose brutto – Rest heute | Zeigt die Brutto-PV-Prognose vor der BSFAI-Bewertung für Rest heute. | `forecast_gross_remaining_today_kwh` |
| PV-Prognose brutto – morgen | Zeigt die Brutto-PV-Prognose vor der BSFAI-Bewertung für morgen. | `forecast_gross_tomorrow_kwh` |
| PV-Prognose brutto – nächste 3 Stunden | Zeigt die Brutto-PV-Prognose vor der BSFAI-Bewertung für nächste 3 Stunden. | `forecast_gross_next_3h_kwh` |
| PV-Prognose brutto – nächste 6 Stunden | Zeigt die Brutto-PV-Prognose vor der BSFAI-Bewertung für nächste 6 Stunden. | `forecast_gross_next_6h_kwh` |

## Lernbasierte Ladeplanung

| Sensor | Bedeutung | `key` |
|---|---|---|
| Ladeplanung: Lernstatus | Zeigt den vom Lernmodell ermittelten Wert für „Ladeplanung: Lernstatus“.<br>Zustände: Noch nicht gestartet; Daten werden gesammelt; Nicht genügend Lerndaten; Bereit — Betriebsdaten liegen vor; Aktiv — Funktion ist aktiv. | `learned_planning_status` |
| Ladeplanung: Modus | Zeigt den vom Lernmodell ermittelten Wert für „Ladeplanung: Modus“.<br>Zustände: Deaktiviert — Funktion deaktiviert; Daten werden gesammelt; Klassische Planung; Lernplanung bereit — Betriebsdaten liegen vor; Lernplanung wartet auf Ladefenster; Lernplanung aktiv — Batterie lädt; Klassische Planung; Lernplanung wartet auf Ladefenster; Lernplanung aktiv. | `learned_planning_mode` |
| Ladeplanung: Geplanter Ladestart | Zeigt den vom Lernmodell ermittelten Wert für „Ladeplanung: Geplanter Ladestart“. | `learned_planning_optimal_charge_start` |
| Ladeplanung: Deadline | Zeigt den vom Lernmodell ermittelten Wert für „Ladeplanung: Deadline“. | `learned_planning_deadline` |
| Ladeplanung: Nachladeenergie | Zeigt den vom Lernmodell ermittelten Wert für „Ladeplanung: Nachladeenergie“. | `learned_planning_required_charge_energy_kwh` |
| Ladeplanung: Fenstergröße | Zeigt den vom Lernmodell ermittelten Wert für „Ladeplanung: Fenstergröße“. | `learned_planning_effective_window_minutes` |

## Preise & Wirtschaftlichkeit

| Sensor | Bedeutung | `key` |
|---|---|---|
| Preise – Ø dynamischer Tagespreis | Zeigt den von BSFAI berechneten Preiswert bzw. die Preisgrenze „Preise – Ø dynamischer Tagespreis“. | `price_daily_average` |
| Preise – Aktuelle Peak-Schwelle | Zeigt den von BSFAI berechneten Preiswert bzw. die Preisgrenze „Preise – Aktuelle Peak-Schwelle“. | `current_peak_threshold` |
| Preise – Aktuelle Valley-Schwelle | Zeigt den von BSFAI berechneten Preiswert bzw. die Preisgrenze „Preise – Aktuelle Valley-Schwelle“. | `current_valley_threshold` |
| Preise – Ökonomische Entladeschwelle | Zeigt den von BSFAI berechneten Preiswert bzw. die Preisgrenze „Preise – Ökonomische Entladeschwelle“. | `economic_discharge_threshold` |
| Preise – Effektive Entladeschwelle | Zeigt den von BSFAI berechneten Preiswert bzw. die Preisgrenze „Preise – Effektive Entladeschwelle“. | `effective_discharge_threshold` |
| Aktuell – Bezugspreis | Aktueller Netzbezugspreis. | `price_now` |
| Aktuell – Einspeisevergütung | Aktuell verwendete Einspeisevergütung. | `feed_in_tariff` |
| Aktuell – Angerechneter Akku-Ladepreis | Zeigt den Preis, den BSFAI der aktuellen Ladung für die laufende Berechnung ansetzt. | `charge_price_applied` |
| Preise – Ø Ladepreis aktuell (geschätzt) | Zeigt die geschätzten durchschnittlichen Kosten der Ladung im aktuellen SoC-Zyklus. | `avg_charge_price` |
| Preise – Ø Netzladepreis | Zeigt den mengen- bzw. energiemengengewichteten Durchschnitt für „Preise – Ø Netzladepreis“. | `economics_average_grid_charge_price` |
| Preise – Ø PV-Opportunitätswert | Zeigt den mengen- bzw. energiemengengewichteten Durchschnitt für „Preise – Ø PV-Opportunitätswert“. | `economics_average_pv_opportunity_value` |
| Preise – Ø Ladepreis gesamt (Netz + PV) | Zeigt den mengen- bzw. energiemengengewichteten Durchschnitt für „Preise – Ø Ladepreis gesamt (Netz + PV)“. | `economics_average_battery_charge_price` |
| Preise – Ø Einspeisevergütung | Zeigt den mengen- bzw. energiemengengewichteten Durchschnitt für „Preise – Ø Einspeisevergütung“. | `economics_average_export_price` |
| Preise – Ø Wert der Batterieentladung | Zeigt den mengen- bzw. energiemengengewichteten Durchschnitt für „Preise – Ø Wert der Batterieentladung“. | `economics_average_battery_discharge_value` |
| Preise – Ø Wert Native PV direkt ins Haus | Zeigt den mengen- bzw. energiemengengewichteten Durchschnitt für „Preise – Ø Wert Native PV direkt ins Haus“. | `economics_average_native_pv_to_home_return` |

## Zellspannungs-Schutz

| Sensor | Bedeutung | `key` |
|---|---|---|
| Globale niedrigste Zellspannung | Niedrigste erkannte Zellspannung über die überwachten Packs. | `global_lowest_cell_voltage` |
| Zellspannungs-Notladung aktiv | Zeigt, ob Zellspannungs-Schutz eine Notladung anfordert.<br>Zustände: Nein — inaktiv; Ja — aktiv. | `cell_voltage_emergency_active` |
| Entladung durch Zellspannungs-Schutz blockiert | Zeigt, ob Zellspannungs-Schutz die Entladung sperrt.<br>Zustände: Nein — inaktiv; Ja — aktiv. | `cell_voltage_discharge_blocked` |
| Plausibilität SoC / Zellspannung | Plausibilitätsbewertung von SoC und Zellspannung.<br>Zustände: Plausibel — Normalbetrieb; Auffällig; Kritisch unplausibel; Nicht verfügbar. | `cell_voltage_soc_plausibility` |
| Zellspannungs-Status | Status des Zellspannungs-Schutzes.<br>Zustände: Deaktiviert — Funktion deaktiviert; Normal — Normalbetrieb; Warnbereich aktiv; Entladesperre aktiv; Sensordaten ungültig. | `cell_voltage_status` |

## Debug-Aufzeichnung

| Sensor | Bedeutung | `key` |
|---|---|---|
| Debug-Aufzeichnung aktiv | Zeigt den Status oder das Ergebnis der zeitlich begrenzten Debug-Aufzeichnung.<br>Zustände: Nein — inaktiv; Ja — aktiv. | `debug_recording_active` |
| Debug-Aufzeichnung endet um | Zeigt den Status oder das Ergebnis der zeitlich begrenzten Debug-Aufzeichnung. | `debug_recording_ends_at` |
| Erfasste Debug-Datensätze | Zeigt den Status oder das Ergebnis der zeitlich begrenzten Debug-Aufzeichnung. | `debug_sample_count` |
| Letztes Debug-Paket | Zeigt den Status oder das Ergebnis der zeitlich begrenzten Debug-Aufzeichnung. | `debug_last_package` |
| Letzter Debug-Fehler | Zeigt den Status oder das Ergebnis der zeitlich begrenzten Debug-Aufzeichnung. | `debug_last_error` |

## Regelungstraining

| Sensor | Bedeutung | `key` |
|---|---|---|
| Regelungstraining aktiv | Zeigt den Status, Umfang oder das Ergebnis der optionalen Regelungstrainingsdaten.<br>Zustände: Nein — inaktiv; Ja — aktiv. | `regulation_training_active` |
| Regelungstrainings-Datensätze | Zeigt den Status, Umfang oder das Ergebnis der optionalen Regelungstrainingsdaten. | `regulation_training_sample_count` |
| Gespeicherte Trainingssitzungen | Zeigt den Status, Umfang oder das Ergebnis der optionalen Regelungstrainingsdaten. | `regulation_training_saved_sessions` |
| Ergebnis des Regelungstrainings | Zeigt den Status, Umfang oder das Ergebnis der optionalen Regelungstrainingsdaten.<br>Zustände: Noch nicht trainiert; Training läuft; Shadow-Kandidat verfügbar; Keine sichere Verbesserung gefunden; Weitere Trainingsdaten erforderlich; Unterbrochen – Teildaten gesichert. | `regulation_training_result` |

## Energie & Bilanz

| Sensor | Bedeutung | `key` |
|---|---|---|
| Bilanz seit Start – Bisheriger Handelsgewinn | Zeigt den bisher errechneten wirtschaftlichen Überschuss seit Beginn der Bilanz. | `profit_eur` |
| Bilanz heute – Netzladekosten | Zeigt den berechneten Geldbetrag für „Bilanz heute – Netzladekosten“. | `economics_daily_grid_charge_cost` |
| Bilanz heute – PV-Opportunitätskosten | Zeigt den berechneten Geldbetrag für „Bilanz heute – PV-Opportunitätskosten“. | `economics_daily_pv_opportunity_cost` |
| Bilanz heute – Einspeiseertrag | Zeigt den berechneten Geldbetrag für „Bilanz heute – Einspeiseertrag“. | `economics_daily_export_revenue` |
| Bilanz heute – Vermiedene Netzbezugskosten | Zeigt den berechneten Geldbetrag für „Bilanz heute – Vermiedene Netzbezugskosten“. | `economics_daily_avoided_grid_import_cost` |
| Bilanz heute – Batterienutzen | Zeigt den berechneten Geldbetrag für „Bilanz heute – Batterienutzen“. | `economics_daily_battery_benefit` |
| Bilanz heute – Wert des direkten PV-Eigenverbrauchs | Zeigt den berechneten Geldbetrag für „Bilanz heute – Wert des direkten PV-Eigenverbrauchs“. | `economics_daily_native_pv_self_consumption_value` |
| Bilanz seit Start – Netzladekosten | Zeigt den berechneten Geldbetrag für „Bilanz seit Start – Netzladekosten“. | `economics_total_grid_charge_cost` |
| Bilanz seit Start – PV-Opportunitätskosten | Zeigt den berechneten Geldbetrag für „Bilanz seit Start – PV-Opportunitätskosten“. | `economics_total_pv_opportunity_cost` |
| Bilanz seit Start – Einspeiseertrag | Zeigt den berechneten Geldbetrag für „Bilanz seit Start – Einspeiseertrag“. | `economics_total_export_revenue` |
| Bilanz seit Start – Vermiedene Netzbezugskosten | Zeigt den berechneten Geldbetrag für „Bilanz seit Start – Vermiedene Netzbezugskosten“. | `economics_total_avoided_grid_import_cost` |
| Bilanz seit Start – Batterienutzen | Zeigt den berechneten Geldbetrag für „Bilanz seit Start – Batterienutzen“. | `economics_total_battery_benefit` |
| Bilanz seit Start – Wert des direkten PV-Eigenverbrauchs | Zeigt den berechneten Geldbetrag für „Bilanz seit Start – Wert des direkten PV-Eigenverbrauchs“. | `economics_total_native_pv_self_consumption_value` |
| Bilanz seit Start – Wirtschaftlicher Wirkungsgrad | Zeigt den berechneten Geldbetrag für „Bilanz seit Start – Wirtschaftlicher Wirkungsgrad“. | `economics_total_economic_efficiency_pct` |
| Energie heute – Netz zu Akku | Zeigt die erfasste Energiemenge für „Energie heute – Netz zu Akku“. | `economics_daily_grid_to_battery_kwh` |
| Energie heute – PV zu Akku | Zeigt die erfasste Energiemenge für „Energie heute – PV zu Akku“. | `economics_daily_pv_to_battery_kwh` |
| Energie heute – Netzeinspeisung | Zeigt die erfasste Energiemenge für „Energie heute – Netzeinspeisung“. | `economics_daily_grid_export_kwh` |
| Energie heute – Akku zu Haus | Zeigt die erfasste Energiemenge für „Energie heute – Akku zu Haus“. | `economics_daily_battery_to_home_kwh` |
| Energie heute – Akku zu Netz | Zeigt die erfasste Energiemenge für „Energie heute – Akku zu Netz“. | `economics_daily_battery_to_grid_kwh` |
| Energie heute – Native PV direkt ins Haus | Zeigt die erfasste Energiemenge für „Energie heute – Native PV direkt ins Haus“. | `economics_daily_native_pv_to_home_kwh` |
| Energie seit Start – Netz zu Akku | Zeigt die erfasste Energiemenge für „Energie seit Start – Netz zu Akku“. | `economics_total_grid_to_battery_kwh` |
| Energie seit Start – PV zu Akku | Zeigt die erfasste Energiemenge für „Energie seit Start – PV zu Akku“. | `economics_total_pv_to_battery_kwh` |
| Energie seit Start – Netzeinspeisung | Zeigt die erfasste Energiemenge für „Energie seit Start – Netzeinspeisung“. | `economics_total_grid_export_kwh` |
| Energie seit Start – Akku zu Haus | Zeigt die erfasste Energiemenge für „Energie seit Start – Akku zu Haus“. | `economics_total_battery_to_home_kwh` |
| Energie seit Start – Akku zu Netz | Zeigt die erfasste Energiemenge für „Energie seit Start – Akku zu Netz“. | `economics_total_battery_to_grid_kwh` |
| Energie seit Start – Native PV direkt ins Haus | Zeigt die erfasste Energiemenge für „Energie seit Start – Native PV direkt ins Haus“. | `economics_total_native_pv_to_home_kwh` |

## Zendure-Hardware-Sensoren

**Hauptgerät**

| Sensor | Bedeutung | Schlüssel |
|---|---|---|
| Batterieanzahl | Zeigt, wie viele Akku-Packs das Hauptgerät aktuell erkennt. | `pack_count` |
| Nennkapazität | Zeigt die gesamte im Hauptgerät konfigurierte Nennkapazität der angeschlossenen Batterie-Packs in kWh. | `capacity_kwh` |
| Batterieleistung | Zeigt die vom Hauptgerät gemeldete Gesamtleistung der Batterie. | `power_w` |
| Off-Grid-Leistung | Zeigt die Leistung am Off-Grid-Ausgang. | `offgrid_power_w` |
| WLAN-Signalstärke | Zeigt die Stärke des WLAN-Funksignals in dBm. | `rssi` |
| Geschätzte Restlaufzeit bis leer | Schätzt, wie lange die Batterie bei der aktuellen Entladung noch Energie liefern kann. | `remaining_output_time` |
| Verfügbare Energie | Zeigt die aktuell verfügbare Batterieenergie in kWh. | `available_energy_kwh` |
| Wirkungsgrad (Roundtrip) | Zeigt den geschätzten Wirkungsgrad über Laden und anschließendes Entladen in Prozent. | `roundtrip_efficiency_pct` |
| Gesamtenergie Laden | Zeigt die vom Gerät aufsummierte geladene Energie in kWh. | `charged_energy_kwh` |
| Gesamtenergie Entladen | Zeigt die vom Gerät aufsummierte abgegebene Energie in kWh. | `discharged_energy_kwh` |
| Gesamte PV-Energie | Zeigt die vom Gerät aufsummierte, über PV erzeugte Energie in kWh. | `pv_energy_kwh` |
| Schaltvorgänge | Zeigt den vom Gerät erfassten Zählerstand der Schaltvorgänge. | `switching_count` |
| Hardware-SoC-Minimum | Zeigt das in der Hardware eingestellte untere SoC-Limit. | `hardware_soc_min` |
| Hardware-SoC-Maximum | Zeigt das in der Hardware eingestellte obere SoC-Limit. | `hardware_soc_max` |
| Batterieheizung | Zeigt an, ob die Batterieheizung eingeschaltet oder ausgeschaltet ist.<br>Zustände: Ein — Heizung eingeschaltet; Aus — Heizung ausgeschaltet. | `heating_active` |
| Sollwert-Speicherung | Zeigt, ob Leistungsvorgaben dauerhaft oder nur vorübergehend gespeichert werden.<br>Zustände: Dauerhafte Speicherung — Vorgabe dauerhaft gespeichert; Temporäre Regelung — Vorgabe nur vorübergehend aktiv; Unbekannt — Status nicht bekannt. | `setpoint_storage` |
| Gerätedaten | Zeigt, ob das Gerät die erforderlichen Betriebsdaten bereitstellt.<br>Zustände: Noch nicht bereit — Betriebsdaten noch nicht bereit; Bereit — Betriebsdaten liegen vor; Unbekannt — Status nicht bekannt. | `dataReady` |
| Netzverbindung | Zeigt, ob das Gerät mit dem Stromnetz verbunden ist.<br>Zustände: Getrennt — keine Netzverbindung; Verbunden — Netzverbindung besteht; Unbekannt — Status nicht bekannt. | `gridState` |
| PV-Status | Zeigt, ob das Gerät PV-Eingang als aktiv meldet.<br>Zustände: Inaktiv — Funktion ist inaktiv; Aktiv — Funktion ist aktiv; Unbekannt — Status nicht bekannt. | `pvStatus` |
| SoC-Kalibrierung | Zeigt, ob der SoC normal ist oder gerade kalibriert wird.<br>Zustände: Normal — Normalbetrieb; Kalibrierung läuft — SoC-Kalibrierung läuft; Unbekannt — Status nicht bekannt. | `socStatus` |
| Durchleitung | Zeigt, ob die Durchleitung zwischen Netz-Eingang und Ausgang aktiv ist.<br>Zustände: Inaktiv — Funktion ist inaktiv; Aktiv — Funktion ist aktiv; Unbekannt — Status nicht bekannt. | `pass` |
| Rückfluss | Zeigt, ob ein Rückfluss am Gerät erkannt bzw. freigegeben ist.<br>Zustände: Inaktiv — Funktion ist inaktiv; Aktiv — Funktion ist aktiv; Unbekannt — Status nicht bekannt. | `reverseState` |
| Off-Grid-Modus | Zeigt den eingestellten Betriebsmodus für den netzunabhängigen Betrieb.<br>Zustände: Standard; Wirtschaftlich; Deaktiviert — Funktion deaktiviert; Unbekannt — Status nicht bekannt. | `gridOffMode` |
| Fehlerstatus | Zeigt, ob das Gerät einen Fehlerzustand meldet.<br>Zustände: Kein Fehler — kein Fehler gemeldet; Fehler — Fehler erkannt; Unbekannt — Status nicht bekannt. | `is_error` |
| Online-Status | Zeigt, ob das Gerät aktuell als online oder offline erkannt wird.<br>Zustände: Online — Gerät erreichbar; Offline — Gerät nicht erreichbar. | `online` |
| Ladezustand | Zeigt den Ladezustand der Batterie in Prozent. | `soc_pct` |
| Ladeleistung | Zeigt die aktuelle Ladeleistung dieses Akku-Packs in Watt. | `charge_power_w` |
| Entladeleistung | Zeigt die aktuelle Entladeleistung dieses Akku-Packs in Watt. | `discharge_power_w` |
| AC-Eingangsleistung | Zeigt die elektrische Leistung am AC-Eingang in Watt. | `ac_input_power_w` |
| AC-Ausgangsleistung | Zeigt die elektrische Leistung am AC-Ausgang in Watt. | `ac_output_power_w` |
| PV-Leistung | Zeigt die aktuelle Eingangsleistung der PV-Anlage in Watt. | `pv_power_w` |
| Betriebsmodus | Zeigt, ob das Gerät bereitsteht, lädt oder entlädt.<br>Zustände: Bereitschaft — keine Lade- oder Entladeaktivität; Laden — Batterie lädt; Entladen — Batterie entlädt; Unbekannt — Status nicht bekannt. | `mode` |
| Temperatur | Zeigt die Temperatur des Hauptgeräts in °C. | `temperature_c` |
| Batteriespannung | Zeigt die Batteriespannung am Hauptgerät in Volt. | `battery_voltage_v` |
| Firmware | Zeigt die Firmware-Version des Geräts. | `firmware` |
| Produkt-ID | Zeigt die Produktkennung des Geräts. | `product_id` |
| Geräteprofil | Zeigt das erkannte Geräteprofil bzw. Modellprofil. | `profile` |
| Kommunikationsweg | Zeigt den verwendeten Kommunikationsweg zum Gerät.<br>Zustände: Home Assistant / Z-HA; Cloud; Lokal; ZenSDK. | `transport` |
| Steuerungsstatus | Zeigt, ob das Gerät beobachtet, zur Steuerung bereit, freigegeben, aktiv gesteuert oder blockiert ist.<br>Zustände: Beobachtung — nur Beobachtung, keine aktive Steuerung; Steuerbar — Gerät kann gesteuert werden; Freigegeben — Steuerung wurde freigegeben; Aktiv gesteuert — Funktion ist aktiv; Durch HEMS blockiert — Zendure HEMS verhindert die Steuerung; Nicht unterstützt — Funktion oder Gerät nicht unterstützt; Offline — Gerät nicht erreichbar. | `control_state` |
| Zendure HEMS | Zeigt den Zustand der Zendure-HEMS-Steuerung.<br>Zustände: Aktiv — Funktion ist aktiv; Inaktiv — Funktion ist inaktiv; Unbekannt — Status nicht bekannt; Veraltet — Statusmeldung ist veraltet; Ungültig — Statusmeldung ist ungültig; Nicht unterstützt — Funktion oder Gerät nicht unterstützt. | `hems` |
| Letzter Datenempfang | Zeigt Zeitpunkt und damit Aktualität des letzten empfangenen Gerätedatensatzes. | `last_message` |


**Akku-Packs**

Diese Werte erscheinen je erkanntem Pack als eigene Sensoren.

| Sensor | Bedeutung | Schlüssel |
|---|---|---|
| Status | Zeigt den Betriebszustand dieses einzelnen Akku-Packs.<br>Zustände: Ruhezustand — keine Lade- oder Entladeaktivität; Laden — Batterie lädt; Entladen — Batterie entlädt. | `status` |
| Zellspannungsdifferenz | Zeigt den Spannungsunterschied zwischen höchster und niedrigster Zelle des Packs. | `cell_delta_v` |
| Nennkapazität | Zeigt die Nennkapazität dieses Akku-Packs in kWh. | `capacity_kwh` |
| Batterieleistung | Zeigt die vom Pack gemeldete aktuelle Batterieleistung. | `power_w` |
| Batterieheizung | Zeigt den Betriebszustand der Heizung in diesem Akku-Pack an.<br>Zustände: Ein — Heizung eingeschaltet; Aus — Heizung ausgeschaltet. | `heating_active` |
| Ladezustand | Zeigt den Ladezustand der Batterie in Prozent. | `soc_pct` |
| Ladeleistung | Zeigt die aktuelle Ladeleistung dieses Akku-Packs in Watt. | `charge_power_w` |
| Entladeleistung | Zeigt die aktuelle Entladeleistung dieses Akku-Packs in Watt. | `discharge_power_w` |
| Spannung | Zeigt die Spannung des Akku-Packs in Volt. | `voltage_v` |
| Strom | Zeigt den Strom des Akku-Packs in Ampere. | `current_a` |
| Niedrigste Zellspannung | Zeigt die niedrigste Zellspannung innerhalb dieses Packs. | `cell_min_v` |
| Höchste Zellspannung | Zeigt die höchste Zellspannung innerhalb dieses Packs. | `cell_max_v` |
| Maximale Zelltemperatur | Zeigt die höchste vom Pack gemeldete Zelltemperatur in °C. | `temperature_c` |
| Statuscode | Zeigt den vom Pack gemeldeten numerischen Statuscode. Die genaue Codetabelle ist Zendure- und firmwareabhängig. | `state_code` |
| Pack-Typ | Zeigt die von Zendure gemeldete Typkennung dieses Akku-Packs. | `pack_type` |
| Fehlercode | Zeigt den vom Pack gemeldeten Fehlercode; 0 bedeutet üblicherweise, dass kein Fehlercode gesetzt ist. | `fault_code` |
| Schutz aktiv | Zeigt, ob der Batterieschutz dieses Packs aktiv ist. | `protection_active` |
| Firmware | Zeigt die Firmware-Version des Geräts. | `firmware` |
| Letzter Datenempfang | Zeigt Zeitpunkt und damit Aktualität des letzten empfangenen Gerätedatensatzes. | `last_message` |

**Optionale Rohdiagnose des Hauptgeräts**
