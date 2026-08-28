# V4.7.0: Nachgewiesener Legacy-Cleanup

- Status: Umsetzung für Issue #277
- Scope: nur nachweislich ungenutzte oder vollständig ersetzte Laufzeitpfade

## Entfernt

- zwei private Decision-Engine-Prüfungen ohne Aufrufer,
- `get_profile_defaults()` ohne Aufrufer,
- die Rückübersetzung moderner `CHARGE_*`- und `DISCHARGE_*`-Parameter auf
  generische V2-Reglerschlüssel,
- generische Regler-Fallbacks in Decision Engine, GridHistory und dem aktuellen
  RegulationPowerController.

`PowerContext` trägt die benötigten technischen Werte nun ausdrücklich und
richtungsbezogen. Der alte Delta-Regler erhält damit keine vollständige
Profil-Map mehr und kann weder Profilannahmen treffen noch versehentlich auf den
parallelen generischen Parametersatz zurückfallen.

## Bewusst erhaltene Migration

Die alten Override-Namen `DEADBAND_W`, `KP_UP`, `KP_DOWN`, `MAX_STEP_UP` und
`MAX_STEP_DOWN` werden beim Laden bestehender Benutzeroptionen weiterhin
akzeptiert. Das ist ein Upgrade-Vertrag, kein aktiver Reglerpfad. Die Werte
können außerdem aus Kompatibilitätsgründen noch in Profil-/Diagnoseausgaben
erscheinen, steuern aber nicht mehr die aktuelle richtungsbezogene Regelung.

Ebenso bleiben bestehende Entity IDs, gespeicherte Economics-Felder,
Winter-Modus-Normalisierung und Preisfeldmigrationen erhalten. Diese Elemente
haben nachgewiesene Upgrade- oder Registry-Verantwortung und sind daher kein
toter Code.

## Nachweis

Alle ausgelieferten Profile enthalten einen vollständigen Satz aus
`CHARGE_DEADBAND_W`, `CHARGE_KP_*`, `CHARGE_MAX_STEP_*`,
`DISCHARGE_DEADBAND_W`, `DISCHARGE_KP_*` und `DISCHARGE_MAX_STEP_*`.
Architekturtests sichern ab, dass die entfernten Helfer nicht zurückkehren und
dass die alten Namen ausschließlich im dokumentierten Migrationsvertrag
zulässig bleiben.
