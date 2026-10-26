# BSFAI- und Zendure-Sensorkatalog

Dieser Anhang listet die von der Integration erzeugten Sensoren. BSFAI-Berechnungs- und Statussensoren stehen getrennt von den Zendure-Hardwarewerten.

## Haus & Netz

| Sensor | Bedeutung | `key` |
|---|---|---|
| Netzleistung | Netzleistung des konfigurierten Messsystems. | `grid_power` |
| Shelly-Netzleistung Phase A | Netzleistung auf Phase A laut Shelly Pro 3EM. | `grid_phase_a_power` |
| Shelly-Netzleistung Phase B | Netzleistung auf Phase B laut Shelly Pro 3EM. | `grid_phase_b_power` |
| Shelly-Netzleistung Phase C | Netzleistung auf Phase C laut Shelly Pro 3EM. | `grid_phase_c_power` |
| Hauslast | Berechnete Hauslast am gemeinsamen Netzanschluss. | `house_load` |

## Status & Steuerung

| Sensor | Bedeutung | `key` |
|---|---|---|
| Status nativer Zendure-Test | Status der nativen Zendure-Beobachtung. | `native_zendure_status` |
| Native Zendure-Steuerung | Aktiver nativer Kommunikations- und Steuerungsweg. | `native_zendure_control` |
| Gefundene native Zendure-Geräte | Anzahl erkannter nativer Zendure-Geräte. | `native_zendure_device_count` |
| Empfangene native Zendure-Nachrichten | Anzahl empfangener nativer Zendure-Nachrichten. | `native_zendure_message_count` |
| Letzte native Zendure-Nachricht | Zeitpunkt der letzten nativen Zendure-Nachricht. | `native_zendure_last_message` |
| Paket des nativen Zendure-Erstabgleichs | Name des gespeicherten Erstabgleich-Pakets. | `native_zendure_last_capture` |
| Fehler nativer Zendure-Test | Letzter gemeldeter Fehler des nativen Zendure-Tests. | `native_zendure_error` |
| Zendure-Hardwareverbindung | Erreichbarkeit der Zendure-Hardwareverbindung. | `native_zendure_watchdog` |
| Aktives Geräteprofil | Für das System verwendetes Geräteprofil. | `device_profile` |
| Adaptiver Peak erkannt | Zeigt, ob ein adaptiver Preishöchststand erkannt wurde. | `adaptive_peak_active` |
| Ladestrategie | Aktuell angewendete Ladstrategie. | `charge_strategy` |
| Volladungswartung | Status der geplanten Volladungspflege. | `full_charge_maintenance_state` |
| Volladungswartung aktiv | Zeigt, ob Volladungspflege derzeit aktiv ist. | `full_charge_maintenance_active` |
| Nächste empfohlene Volladung | Zeitpunkt der nächsten empfohlenen Volladung. | `full_charge_maintenance_next_recommended` |
| Engine-Status | Betriebsbereitschaft und erkannte Eingabefehler. | `engine_health` |
| Regelungskontext | Aktueller Regelungskontext (Preis, PV oder manuell). | `season_mode` |
| Hardware-SoC-Begrenzungsstatus | Erkannter SoC-Begrenzungsstatus der Hardware. | `soc_limit_status` |
| Fehlerstatus | Zusammenfassende Einstufung erkannter Fehler. | `fault_level_status` |
| Systemstatus | Aktueller Gesamtstatus der BSFAI-Regelung. | `status` |
| KI-Status | Status der KI-gestützten Regelung. | `ai_status` |
| KI-Empfehlung | Aktuelle Empfehlung der Regelung. | `recommendation` |
| Entscheidungsgrund | Grund für die aktuelle Regelentscheidung. | `decision_reason` |
| Nächste Aktion | Geplante nächste Aktion und ihr Status. | `next_action_state` |
| Startzeit nächste Aktion | Geplanter Zeitpunkt der nächsten Aktion. | `next_action_time` |

## PV-Prognose

| Sensor | Bedeutung | `key` |
|---|---|---|
| Prognose-Status | Status der verfügbaren PV-Prognosedaten. | `forecast_status` |
| PV-Ausblick | Zusammenfassung des erwarteten PV-Verlaufs. | `pv_outlook` |
| Nutzbare PV-Prognose – Rest heute | Nutzbare PV-Energie für den angegebenen Zeitraum. | `forecast_remaining_today_kwh` |
| Nutzbare PV-Prognose – morgen | Nutzbare PV-Energie für den angegebenen Zeitraum. | `forecast_tomorrow_kwh` |
| Nutzbare PV-Prognose – nächste 3 Stunden | Nutzbare PV-Energie für den angegebenen Zeitraum. | `forecast_next_3h_kwh` |
| Nutzbare PV-Prognose – nächste 6 Stunden | Nutzbare PV-Energie für den angegebenen Zeitraum. | `forecast_next_6h_kwh` |
| PV-Prognose brutto – Rest heute | Brutto-PV-Prognose vor BSFAI-Anpassungen für den Zeitraum. | `forecast_gross_remaining_today_kwh` |
| PV-Prognose brutto – morgen | Brutto-PV-Prognose vor BSFAI-Anpassungen für den Zeitraum. | `forecast_gross_tomorrow_kwh` |
| PV-Prognose brutto – nächste 3 Stunden | Brutto-PV-Prognose vor BSFAI-Anpassungen für den Zeitraum. | `forecast_gross_next_3h_kwh` |
| PV-Prognose brutto – nächste 6 Stunden | Brutto-PV-Prognose vor BSFAI-Anpassungen für den Zeitraum. | `forecast_gross_next_6h_kwh` |

## Lernbasierte Ladeplanung

| Sensor | Bedeutung | `key` |
|---|---|---|
| Ladeplanung: Lernstatus | Vom Lernmodell ermittelte Ladeplanung und deren Zeit- oder Energiewerte. | `learned_planning_status` |
| Ladeplanung: Modus | Vom Lernmodell ermittelte Ladeplanung und deren Zeit- oder Energiewerte. | `learned_planning_mode` |
| Ladeplanung: Geplanter Ladestart | Vom Lernmodell ermittelte Ladeplanung und deren Zeit- oder Energiewerte. | `learned_planning_optimal_charge_start` |
| Ladeplanung: Deadline | Vom Lernmodell ermittelte Ladeplanung und deren Zeit- oder Energiewerte. | `learned_planning_deadline` |
| Ladeplanung: Nachladeenergie | Vom Lernmodell ermittelte Ladeplanung und deren Zeit- oder Energiewerte. | `learned_planning_required_charge_energy_kwh` |
| Ladeplanung: Fenstergröße | Vom Lernmodell ermittelte Ladeplanung und deren Zeit- oder Energiewerte. | `learned_planning_effective_window_minutes` |

## Preise & Wirtschaftlichkeit

| Sensor | Bedeutung | `key` |
|---|---|---|
| Preise – Ø dynamischer Tagespreis | Zeigt den aktuellen Wert für „Preise – Ø dynamischer Tagespreis“. | `price_daily_average` |
| Preise – Aktuelle Peak-Schwelle | Preisgrenze, die BSFAI aktuell für die Regelung verwendet. | `current_peak_threshold` |
| Preise – Aktuelle Valley-Schwelle | Preisgrenze, die BSFAI aktuell für die Regelung verwendet. | `current_valley_threshold` |
| Preise – Ökonomische Entladeschwelle | Preisgrenze, die BSFAI aktuell für die Regelung verwendet. | `economic_discharge_threshold` |
| Preise – Effektive Entladeschwelle | Preisgrenze, die BSFAI aktuell für die Regelung verwendet. | `effective_discharge_threshold` |
| Aktuell – Bezugspreis | Aktueller Netzbezugspreis. | `price_now` |
| Aktuell – Einspeisevergütung | Aktuell verwendete Einspeisevergütung. | `feed_in_tariff` |
| Aktuell – Angerechneter Akku-Ladepreis | Ladepreis, den BSFAI für aktuelle Ladung ansetzt. | `charge_price_applied` |
| Preise – Ø Ladepreis aktuell (geschätzt) | Geschätzter durchschnittlicher Ladepreis des aktuellen SoC-Zyklus. | `avg_charge_price` |
| Preise – Ø Netzladepreis | Gewichteter Durchschnittswert der erfassten Energiemengen und Preise. | `economics_average_grid_charge_price` |
| Preise – Ø PV-Opportunitätswert | Gewichteter Durchschnittswert der erfassten Energiemengen und Preise. | `economics_average_pv_opportunity_value` |
| Preise – Ø Ladepreis gesamt (Netz + PV) | Gesamtbilanz: gewichteter durchschnittlicher Ladepreis aus Netz- und PV-Ladung. | `economics_average_battery_charge_price` |
| Preise – Ø Einspeisevergütung | Gewichteter Durchschnittswert der erfassten Energiemengen und Preise. | `economics_average_export_price` |
| Preise – Ø Wert der Batterieentladung | Gewichteter Durchschnittswert der erfassten Energiemengen und Preise. | `economics_average_battery_discharge_value` |
| Preise – Ø Wert Native PV direkt ins Haus | Gewichteter Durchschnittswert der erfassten Energiemengen und Preise. | `economics_average_native_pv_to_home_return` |

## Zellspannungs-Schutz

| Sensor | Bedeutung | `key` |
|---|---|---|
| Globale niedrigste Zellspannung | Niedrigste erkannte Zellspannung über die überwachten Packs. | `global_lowest_cell_voltage` |
| Zellspannungs-Notladung aktiv | Zeigt, ob Zellspannungs-Schutz eine Notladung anfordert. | `cell_voltage_emergency_active` |
| Entladung durch Zellspannungs-Schutz blockiert | Zeigt, ob Zellspannungs-Schutz die Entladung sperrt. | `cell_voltage_discharge_blocked` |
| Plausibilität SoC / Zellspannung | Plausibilitätsbewertung von SoC und Zellspannung. | `cell_voltage_soc_plausibility` |
| Zellspannungs-Status | Status des Zellspannungs-Schutzes. | `cell_voltage_status` |

## Debug-Aufzeichnung

| Sensor | Bedeutung | `key` |
|---|---|---|
| Debug-Aufzeichnung aktiv | Statusinformation zur zeitlich begrenzten Debug-Aufzeichnung. | `debug_recording_active` |
| Debug-Aufzeichnung endet um | Statusinformation zur zeitlich begrenzten Debug-Aufzeichnung. | `debug_recording_ends_at` |
| Erfasste Debug-Datensätze | Statusinformation zur zeitlich begrenzten Debug-Aufzeichnung. | `debug_sample_count` |
| Letztes Debug-Paket | Statusinformation zur zeitlich begrenzten Debug-Aufzeichnung. | `debug_last_package` |
| Letzter Debug-Fehler | Statusinformation zur zeitlich begrenzten Debug-Aufzeichnung. | `debug_last_error` |

## Regelungstraining

| Sensor | Bedeutung | `key` |
|---|---|---|
| Regelungstraining aktiv | Zeigt, ob Regelungstraining läuft. | `regulation_training_active` |
| Regelungstrainings-Datensätze | Anzahl erfasster Trainingsdatensätze. | `regulation_training_sample_count` |
| Gespeicherte Trainingssitzungen | Anzahl gespeicherter Trainingssitzungen. | `regulation_training_saved_sessions` |
| Ergebnis des Regelungstrainings | Letztes Ergebnis des Regelungstrainings. | `regulation_training_result` |

## Energie & Bilanz

| Sensor | Bedeutung | `key` |
|---|---|---|
| Bilanz seit Start – Bisheriger Handelsgewinn | Zeigt den aktuellen Wert für „Bilanz seit Start – Bisheriger Handelsgewinn“. | `profit_eur` |
| Bilanz heute – Netzladekosten | Erfasste Energiemenge oder wirtschaftliche Bilanz für den angegebenen Zeitraum. | `economics_daily_grid_charge_cost` |
| Bilanz heute – PV-Opportunitätskosten | Erfasste Energiemenge oder wirtschaftliche Bilanz für den angegebenen Zeitraum. | `economics_daily_pv_opportunity_cost` |
| Bilanz heute – Einspeiseertrag | Erfasste Energiemenge oder wirtschaftliche Bilanz für den angegebenen Zeitraum. | `economics_daily_export_revenue` |
| Bilanz heute – Vermiedene Netzbezugskosten | Erfasste Energiemenge oder wirtschaftliche Bilanz für den angegebenen Zeitraum. | `economics_daily_avoided_grid_import_cost` |
| Bilanz heute – Batterienutzen | Erfasste Energiemenge oder wirtschaftliche Bilanz für den angegebenen Zeitraum. | `economics_daily_battery_benefit` |
| Bilanz heute – Wert des direkten PV-Eigenverbrauchs | Erfasste Energiemenge oder wirtschaftliche Bilanz für den angegebenen Zeitraum. | `economics_daily_native_pv_self_consumption_value` |
| Bilanz seit Start – Netzladekosten | Erfasste Energiemenge oder wirtschaftliche Bilanz für den angegebenen Zeitraum. | `economics_total_grid_charge_cost` |
| Bilanz seit Start – PV-Opportunitätskosten | Erfasste Energiemenge oder wirtschaftliche Bilanz für den angegebenen Zeitraum. | `economics_total_pv_opportunity_cost` |
| Bilanz seit Start – Einspeiseertrag | Erfasste Energiemenge oder wirtschaftliche Bilanz für den angegebenen Zeitraum. | `economics_total_export_revenue` |
| Bilanz seit Start – Vermiedene Netzbezugskosten | Erfasste Energiemenge oder wirtschaftliche Bilanz für den angegebenen Zeitraum. | `economics_total_avoided_grid_import_cost` |
| Bilanz seit Start – Batterienutzen | Erfasste Energiemenge oder wirtschaftliche Bilanz für den angegebenen Zeitraum. | `economics_total_battery_benefit` |
| Bilanz seit Start – Wert des direkten PV-Eigenverbrauchs | Erfasste Energiemenge oder wirtschaftliche Bilanz für den angegebenen Zeitraum. | `economics_total_native_pv_self_consumption_value` |
| Bilanz seit Start – Wirtschaftlicher Wirkungsgrad | Erfasste Energiemenge oder wirtschaftliche Bilanz für den angegebenen Zeitraum. | `economics_total_economic_efficiency_pct` |
| Energie heute – Netz zu Akku | Erfasste Energiemenge oder wirtschaftliche Bilanz für den angegebenen Zeitraum. | `economics_daily_grid_to_battery_kwh` |
| Energie heute – PV zu Akku | Erfasste Energiemenge oder wirtschaftliche Bilanz für den angegebenen Zeitraum. | `economics_daily_pv_to_battery_kwh` |
| Energie heute – Netzeinspeisung | Erfasste Energiemenge oder wirtschaftliche Bilanz für den angegebenen Zeitraum. | `economics_daily_grid_export_kwh` |
| Energie heute – Akku zu Haus | Erfasste Energiemenge oder wirtschaftliche Bilanz für den angegebenen Zeitraum. | `economics_daily_battery_to_home_kwh` |
| Energie heute – Akku zu Netz | Erfasste Energiemenge oder wirtschaftliche Bilanz für den angegebenen Zeitraum. | `economics_daily_battery_to_grid_kwh` |
| Energie heute – Native PV direkt ins Haus | Erfasste Energiemenge oder wirtschaftliche Bilanz für den angegebenen Zeitraum. | `economics_daily_native_pv_to_home_kwh` |
| Energie seit Start – Netz zu Akku | Erfasste Energiemenge oder wirtschaftliche Bilanz für den angegebenen Zeitraum. | `economics_total_grid_to_battery_kwh` |
| Energie seit Start – PV zu Akku | Erfasste Energiemenge oder wirtschaftliche Bilanz für den angegebenen Zeitraum. | `economics_total_pv_to_battery_kwh` |
| Energie seit Start – Netzeinspeisung | Erfasste Energiemenge oder wirtschaftliche Bilanz für den angegebenen Zeitraum. | `economics_total_grid_export_kwh` |
| Energie seit Start – Akku zu Haus | Erfasste Energiemenge oder wirtschaftliche Bilanz für den angegebenen Zeitraum. | `economics_total_battery_to_home_kwh` |
| Energie seit Start – Akku zu Netz | Erfasste Energiemenge oder wirtschaftliche Bilanz für den angegebenen Zeitraum. | `economics_total_battery_to_grid_kwh` |
| Energie seit Start – Native PV direkt ins Haus | Erfasste Energiemenge oder wirtschaftliche Bilanz für den angegebenen Zeitraum. | `economics_total_native_pv_to_home_kwh` |

## Zendure-Hardware-Sensoren

**Hauptgerät**

| Sensor | Bedeutung | Schlüssel |
|---|---|---|
| Batterieanzahl | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `pack_count` |
| Nennkapazität | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `capacity_kwh` |
| Batterieleistung | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `power_w` |
| Off-Grid-Leistung | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `offgrid_power_w` |
| Zellspannungsdifferenz | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `cell_delta_v` |
| WLAN-Signalstärke | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `rssi` |
| Geschätzte Restlaufzeit bis leer | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `remaining_output_time` |
| Verfügbare Energie | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `available_energy` |
| Wirkungsgrad (Roundtrip) | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `roundtrip_efficiency` |
| Gesamtenergie Laden | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `charged_energy` |
| Gesamtenergie Entladen | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `discharged_energy` |
| Gesamte PV-Energie | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `pv_energy` |
| Schaltvorgänge | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `switching_count` |
| Hardware-SoC-Minimum | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `soc_min` |
| Hardware-SoC-Maximum | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `soc_max` |
| Batterieheizung | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `heating` |
| Sollwert-Speicherung | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `setpoint_storage` |
| Gerätedaten | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `data_ready` |
| Netzverbindung | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `grid_connection` |
| PV-Status | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `pv_status` |
| SoC-Kalibrierung | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `soc_calibration` |
| Durchleitung | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `passthrough` |
| Rückfluss | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `reverse_flow` |
| Off-Grid-Modus | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `offgrid_mode` |
| Fehlerstatus | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `error_status` |
| Online-Status | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `online` |
| Ladezustand | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `soc_pct` |
| Ladeleistung | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `charge_power_w` |
| Entladeleistung | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `discharge_power_w` |
| AC-Eingangsleistung | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `ac_input_power_w` |
| AC-Ausgangsleistung | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `ac_output_power_w` |
| PV-Leistung | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `pv_power_w` |
| Betriebsmodus | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `mode` |
| Temperatur | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `temperature_c` |
| Maximale Zelltemperatur | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `cell_temperature_c` |
| Batteriespannung | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `battery_voltage_v` |
| Spannung | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `voltage_v` |
| Strom | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `current_a` |
| Niedrigste Zellspannung | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `cell_min_v` |
| Höchste Zellspannung | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `cell_max_v` |
| Statuscode | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `state_code` |
| Pack-Typ | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `pack_type` |
| Fehlercode | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `fault_code` |
| Schutz aktiv | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `protection_active` |
| Firmware | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `firmware` |
| Produkt-ID | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `product_id` |
| Geräteprofil | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `profile` |
| Kommunikationsweg | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `transport` |
| Steuerungsstatus | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `control_state` |
| Zendure HEMS | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `hems` |
| Letzter Datenempfang | Vom Zendure-Hauptgerät gemeldeter aktueller Mess- oder Statuswert. Verfügbarkeit modellabhängig. | `last_message` |

**Akku-Packs**

| Diese Werte erscheinen je erkanntem Pack als eigene Sensoren.

| Sensor | Bedeutung | Schlüssel |
|---|---|---|
| Status | Messwert oder Status, den das jeweilige Zendure-Akku-Pack meldet. Manche Diagnosewerte sind standardmäßig deaktiviert. | `status` |
| Zellspannungsdifferenz | Messwert oder Status, den das jeweilige Zendure-Akku-Pack meldet. Manche Diagnosewerte sind standardmäßig deaktiviert. | `cell_delta_v` |
| Nennkapazität | Messwert oder Status, den das jeweilige Zendure-Akku-Pack meldet. Manche Diagnosewerte sind standardmäßig deaktiviert. | `capacity_kwh` |
| Batterieleistung | Messwert oder Status, den das jeweilige Zendure-Akku-Pack meldet. Manche Diagnosewerte sind standardmäßig deaktiviert. | `power_w` |
| Batterieheizung | Messwert oder Status, den das jeweilige Zendure-Akku-Pack meldet. Manche Diagnosewerte sind standardmäßig deaktiviert. | `heating_active` |
| Ladezustand | Messwert oder Status, den das jeweilige Zendure-Akku-Pack meldet. Manche Diagnosewerte sind standardmäßig deaktiviert. | `soc_pct` |
| Ladeleistung | Messwert oder Status, den das jeweilige Zendure-Akku-Pack meldet. Manche Diagnosewerte sind standardmäßig deaktiviert. | `charge_power_w` |
| Entladeleistung | Messwert oder Status, den das jeweilige Zendure-Akku-Pack meldet. Manche Diagnosewerte sind standardmäßig deaktiviert. | `discharge_power_w` |
| Spannung | Messwert oder Status, den das jeweilige Zendure-Akku-Pack meldet. Manche Diagnosewerte sind standardmäßig deaktiviert. | `voltage_v` |
| Strom | Messwert oder Status, den das jeweilige Zendure-Akku-Pack meldet. Manche Diagnosewerte sind standardmäßig deaktiviert. | `current_a` |
| Niedrigste Zellspannung | Messwert oder Status, den das jeweilige Zendure-Akku-Pack meldet. Manche Diagnosewerte sind standardmäßig deaktiviert. | `cell_min_v` |
| Höchste Zellspannung | Messwert oder Status, den das jeweilige Zendure-Akku-Pack meldet. Manche Diagnosewerte sind standardmäßig deaktiviert. | `cell_max_v` |
| Maximale Zelltemperatur | Messwert oder Status, den das jeweilige Zendure-Akku-Pack meldet. Manche Diagnosewerte sind standardmäßig deaktiviert. | `temperature_c` |
| Statuscode | Messwert oder Status, den das jeweilige Zendure-Akku-Pack meldet. Manche Diagnosewerte sind standardmäßig deaktiviert. | `state_code` |
| Pack-Typ | Messwert oder Status, den das jeweilige Zendure-Akku-Pack meldet. Manche Diagnosewerte sind standardmäßig deaktiviert. | `pack_type` |
| Fehlercode | Messwert oder Status, den das jeweilige Zendure-Akku-Pack meldet. Manche Diagnosewerte sind standardmäßig deaktiviert. | `fault_code` |
| Schutz aktiv | Messwert oder Status, den das jeweilige Zendure-Akku-Pack meldet. Manche Diagnosewerte sind standardmäßig deaktiviert. | `protection_active` |
| Firmware | Messwert oder Status, den das jeweilige Zendure-Akku-Pack meldet. Manche Diagnosewerte sind standardmäßig deaktiviert. | `firmware` |
| Letzter Datenempfang | Messwert oder Status, den das jeweilige Zendure-Akku-Pack meldet. Manche Diagnosewerte sind standardmäßig deaktiviert. | `last_message` |

**Optionale Rohdiagnose des Hauptgeräts**

| Feld | Beschreibung |
|---|---|
| `acStatus` | Rohwert `acStatus` direkt aus Zendure; Bedeutung modell- und firmwareabhängig. |
| `aiState` | Rohwert `aiState` direkt aus Zendure; Bedeutung modell- und firmwareabhängig. |
| `batCalTime` | Rohwert `batCalTime` direkt aus Zendure; Bedeutung modell- und firmwareabhängig. |
| `bindstate` | Rohwert `bindstate` direkt aus Zendure; Bedeutung modell- und firmwareabhängig. |
| `dcStatus` | Rohwert `dcStatus` direkt aus Zendure; Bedeutung modell- und firmwareabhängig. |
| `factoryModeState` | Rohwert `factoryModeState` direkt aus Zendure; Bedeutung modell- und firmwareabhängig. |
| `gridStandard` | Rohwert `gridStandard` direkt aus Zendure; Bedeutung modell- und firmwareabhängig. |
| `IOTState` | Rohwert `IOTState` direkt aus Zendure; Bedeutung modell- und firmwareabhängig. |
| `LCNState` | Rohwert `LCNState` direkt aus Zendure; Bedeutung modell- und firmwareabhängig. |
| `localAPIEnable` | Rohwert `localAPIEnable` direkt aus Zendure; Bedeutung modell- und firmwareabhängig. |
| `net` | Rohwert `net` direkt aus Zendure; Bedeutung modell- und firmwareabhängig. |
| `oldMode` | Rohwert `oldMode` direkt aus Zendure; Bedeutung modell- und firmwareabhängig. |
| `OTAState` | Rohwert `OTAState` direkt aus Zendure; Bedeutung modell- und firmwareabhängig. |
| `phaseSwitch` | Rohwert `phaseSwitch` direkt aus Zendure; Bedeutung modell- und firmwareabhängig. |
| `socLimit` | Rohwert `socLimit` direkt aus Zendure; Bedeutung modell- und firmwareabhängig. |
| `socCompSwitch` | Rohwert `socCompSwitch` direkt aus Zendure; Bedeutung modell- und firmwareabhängig. |
| `writeRsp` | Rohwert `writeRsp` direkt aus Zendure; Bedeutung modell- und firmwareabhängig. |
| `packNum` | Rohwert `packNum` direkt aus Zendure; Bedeutung modell- und firmwareabhängig. |
| `PowerCycle` | Rohwert `PowerCycle` direkt aus Zendure; Bedeutung modell- und firmwareabhängig. |
| `solarPower1` | Leistung des jeweiligen MPPT-Eingangs, sofern geliefert. |
| `solarPower2` | Leistung des jeweiligen MPPT-Eingangs, sofern geliefert. |
| `solarPower3` | Leistung des jeweiligen MPPT-Eingangs, sofern geliefert. |
| `solarPower4` | Leistung des jeweiligen MPPT-Eingangs, sofern geliefert. |
| `solarPower5` | Leistung des jeweiligen MPPT-Eingangs, sofern geliefert. |
| `solarPower6` | Leistung des jeweiligen MPPT-Eingangs, sofern geliefert. |

Die internen Schlüssel dienen der Suche in Entwicklerwerkzeugen. Anzeigenamen können durch Home Assistant oder den Nutzer angepasst werden.
