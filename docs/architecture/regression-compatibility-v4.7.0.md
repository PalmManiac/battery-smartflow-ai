# Refactoring-Regression und Rückwärtskompatibilität (V4.7.0)

Issue #280 bildet den Abschluss der Core-/Adapter-Umstellung. Die Absicherung
verbindet eingefrorene V4.6.0-Verträge mit den bereits vorhandenen fachlichen
Szenariotests. V4.7.0 führt dadurch keinen parallelen Verhaltenspfad ein und
ändert keine Reglerparameter.

## Ausführbare V4.6-Verträge

`tests/test_v470_backward_compatibility.py` sichert drei Update-Grenzen ab:

1. Ein bestehender Config Entry wird unter derselben Entry-ID eingerichtet,
   an Sensor, Number und Select weitergereicht, migriert und entladen. Alte
   Daten und Optionen bleiben erhalten; nur die bestehenden Migrationen
   ergänzen `pack_capacity_kwh` und entfernen den obsoleten
   `regulation_v42_enabled`-Schalter.
2. Die vollständigen Sensor-, Number- und Select-Beschreibungen werden als
   kanonisierte AST-Verträge gegen den Stand des Tags `4.6.0` geprüft. Damit
   bleiben Keys, Übersetzungsschlüssel, Einheiten, Grenzen und Icons stabil.
   Zusätzlich werden Unique-ID- und Device-Registry-Formeln explizit geprüft.
3. SF2400AC, SF2400Pro, SF2400AC+ und SF800Pro behalten Leistungsgrenzen,
   Passthrough-/Off-grid-/Keepalive-Fähigkeiten und die relevanten
   Near-zero-Zielwerte. Die neuen typisierten Profile müssen weiterhin exakt
   die kompatible V4.6-Darstellung erzeugen.

Battery SmartFlow AI besitzt in V4.6.0 keine Button-Plattform. Die nicht
persistenten Debug-Start-/Stop-Aktionen bleiben deshalb wie bisher im
Options-Flow und als Services; es wird für V4.7 kein neues Button-Entity
erfunden.

## Abdeckungsmatrix

| Risiko | Ausführbarer Nachweis |
| --- | --- |
| Config Entry, Migration, Setup und Unload | `test_v470_backward_compatibility.py` |
| Entity-/Device-Registry und Übersetzungen | `test_v470_backward_compatibility.py`, `test_translations.py`, `test_sensor_diagnostics_v470.py` |
| Geräteprofile und Grenzwerte | `test_v470_backward_compatibility.py`, `test_device_profiles.py` |
| RuntimeSnapshot bis DeviceCommand | `test_core_without_home_assistant.py`, `test_dev9_scenarios.py`, `test_technical_regulation_core.py`, `test_maintenance_431.py` |
| Sommer/Winter/Automatik, PV, Planung und Lernplanung | `test_dev9_scenarios.py`, `test_maintenance_431.py`, `test_rc2_charge_window_regressions.py`, `test_rc6_night_planning_regressions.py` |
| ChargeCommit und Schutzlogik | `test_maintenance_431.py`, `test_dev9_scenarios.py` |
| Cooldown, Holds, Latches, Ramp-down und Near-zero | `test_technical_regulation_core.py`, `test_maintenance_431.py`, `test_rc4_pv_grid_regressions.py`, `test_rc5_discharge_feedback_regressions.py` |
| Off-grid und Zusatzakku | `test_dev9_scenarios.py`, `test_maintenance_431.py` |
| Import-/Exportpreise, Null, negativ und unavailable | `test_market_price_models.py`, `test_market_price_sources.py`, `test_export_market_price.py`, `test_market_economics_core_contract.py` |
| Economics, Tageswechsel und Neustart | `test_v460_economics_scenarios.py`, `test_economics.py`, `test_energy_accumulator.py`, `test_state_store.py` |
| Debug-Aufzeichnung und Datenschutz | `test_debug_pipeline.py`, `test_debug_recorder.py`, `test_debug_exporter.py`, `test_sensor_diagnostics_v470.py` |

## Breaking Changes

Für den Architekturumbau von V4.7.0 sind keine zwingenden Breaking Changes an
Config Entries, Entity IDs, Device IDs, Optionen oder persistenten
Zustandsformaten bekannt. Der interne Austausch von Modellen und Ports bleibt
hinter den vorhandenen HA-Verträgen. Ein später entdeckter Bruch muss vor dem
finalen Release entweder behoben oder mit Migration und Release-Note
dokumentiert werden.

Diese Absicherung bewertet die Beta als testbare Vorabversion; sie ersetzt
nicht die reale Geräteerprobung während der Beta-Phase.
