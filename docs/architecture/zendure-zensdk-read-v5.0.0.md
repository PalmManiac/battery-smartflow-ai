# ZenSDK read identity: issue #340

Status: first hardening step, not completion of #340 or productive ZenSDK control.

The current reader uses the Cloud-discovered main-device serial and local address
to request `GET /properties/report`. A response must contain the same top-level
`sn` and a `properties` object. Optional `packData` must be a list of objects.
Pack serials never establish the identity of the main device.

The SF2400AC field report from 2026-09-04 contains this top-level serial and
report structure. The pinned Zendure-HA reference at
`e71b0b83be2e5909fbaf1cd931ad6a530a2be234`, `device.py`, documents the existing
derived hostname and `/properties/report` request. Hardware/model coverage
beyond that capture still needs verification.

If an address now belongs to another device, the response is discarded and the
reader may try the serial-derived local hostname. Missing identity, mismatched
identity and malformed reports cannot refresh normalized state or mark the device
recovered. HTTP redirects are not followed. Diagnostic attempts retain only the
candidate identifier (redacted on export), address-source label, status and safe
reason; they do not include the received serial or address.

The same candidate ID is retained across Cloud discovery and ZenSDK reports.
Multiple devices, including identical models in reversed discovery order, are
resolved independently. Zero remains a valid measurement. Unknown fields and
pack metadata inside valid reports remain available to the existing normalizer
and privacy-filtered capture.

## Remaining work

Local transport diagnostics now derive availability exclusively from ZenSDK
reports and local failures, independently of merged device telemetry. They expose
the report receive timestamp, its age, a 30-second freshness ceiling and the
states `unknown`, `available`, `degraded`, `stale`, and `offline`. A failed read
makes availability false immediately (`degraded` with still-recent data); three
consecutive failures mean `offline`. Without new reports, even a previously
successful reader becomes `stale`. Future timestamps fail closed. Recovery
requires a new identity-validated local report. Cloud messages cannot refresh
this timestamp. The existing combined device state and productive Cloud writer
are unchanged; #341/#342 must consume this separate health state for local writes.

- Complete transport-specific mapping, availability, timing and reconnect/backoff
  coverage for #340, including model evidence for the requested ZenSDK family.
- Verify exact API model names/profile mappings for 800 Pro and Pro 2 separately.
- Keep ZenSDK read, write and readback together when explicitly selected in
  #341/#342; implement the complete authorized command adapter and selection.
- Preserve one selected control owner and the existing per-device HEMS blocker.
  The current activity-based HEMS evidence is separate from local telemetry.
- Keep #408 open until real start, regulation and stop are confirmed on hardware.

This change does not expand the existing reversible `outputLimit` write probe,
enable productive ZenSDK writes, change transport selection or create a release.

## Dev19 evidence limits

The recorded Cloud commands timed out without readback. A later command failed
with `invalid_power_value`; the current mapping rejects fractional watt values.
These are separate observations requiring follow-up. MQTT publish acceptance is
not device confirmation. The `enable: false` field and missing readback alone do
not prove Cloud control is unsupported. Identity correlation in verification
must also be checked before treating missing readback as a transport diagnosis.
