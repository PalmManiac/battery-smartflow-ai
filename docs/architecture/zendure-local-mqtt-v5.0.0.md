# ZendureLegacy Local MQTT path for V5.0.0

Issues #337, #338 and #339 form one implementation block:

`Local MQTT report -> neutral state -> PowerController -> DeviceCommandGate -> Local MQTT command -> fresh report`

## Automatic model path

The user selects one main system and explicitly enables native control, but
does not choose a technical transport. A model classified as `ZendureLegacy`
uses Local MQTT; a `ZendureZenSdk` model continues to use ZenSDK. An unknown
model receives no native write path. Loss of the selected local transport
pauses commands and never falls back to Cloud MQTT, ZenSDK or Z-HA.

The first allow-list covers Hyper 2000 and SolarFlow Hub 2000, for which the
Zendure-HA reference provides concrete Legacy inheritance and command payloads.
Other apparent Legacy devices remain unapproved until their BSFAI device
profiles and exact behavior are available.

## Broker prerequisite

Legacy hardware publishes to a user-controlled MQTT broker only after its
broker target has been provisioned. V5.0.0-dev24 connects to an already
provisioned broker using private options for server, port, username and
password. The password is displayed only as the fixed stored-secret mask and
is excluded from states and diagnostics.

Provisioning the hardware over Bluetooth is deliberately not hidden inside the
transport: it requires Wi-Fi credentials, a reachable Bluetooth adapter and a
separate user-visible operation. Until that onboarding operation exists, a
Legacy tester must have configured the device for the chosen broker already.

## Read path

Only verified Legacy devices are included in Local MQTT subscriptions. Both
`/{product}/{device}/#` and `iot/{product}/{device}/#` are observed because the
reference implementation uses both topic families. `getAll` is the only
outbound operation on startup. Reports keep the stable Cloud-discovered logical
device identity, are tagged `local_mqtt`, and enter the existing neutral
device/pack normalizer. Unknown topics remain bounded diagnostic evidence.

A connected broker alone is not control readiness. The selected device must
have supplied a fresh local message within 30 seconds. Disconnect, stale data,
ambiguous identity, HEMS, protection, disabled control and an unsupported
profile all fail closed.

## Write path

There is no arbitrary Local MQTT publish API. A gate-authorized neutral command
can produce exactly one allow-listed `deviceAutomation` invocation:

- Hyper 2000: AC charge, discharge and stop payloads from the Legacy reference;
- SolarFlow Hub 2000: discharge and stop only; AC charge is rejected.

The adapter publishes to the exact discovered product/device
`function/invoke` topic. It records transport acceptance separately from later
property readback. A newer target supersedes an older pending verification;
commands are not retried or replayed after reconnect.

## Single-writer authority

Transport selection inspects every known identity of the logical main device.
All identities must resolve to the same verified local model family; unknown
or conflicting results remain read-only. The selected writer receives a
generation-bound authority only after current telemetry confirms that the
transport is ready.

Startup, disconnect and stale data revoke synchronization. Recovery requires
a fresh validation and starts a new authority generation, so an old or pending
command cannot be replayed after reconnect or moved to another transport.
Cloud MQTT and the Z-HA entity backend are never automatic write fallbacks.

## Field boundary

Automated tests prove filtering, identity, normalization provenance, payload
shape, exactly-once routing, no alternate-transport write, stale blocking,
secret redaction and all existing ZenSDK regressions. Completion of the three
issues still requires a real Legacy device to confirm report properties,
INPUT/OUTPUT where supported, stop and reconnect behavior.
