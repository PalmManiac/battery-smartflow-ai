# V5.0.0-dev1: Zendure communication research

Status: research baseline for issue #319

BSFAI baseline: V4.7.1 (`92c87d4`)

Research date: 2026-08-31

## Scope and safety boundary

This document records the protocol facts that can be established from current
reference implementations without connecting to a user's Zendure account or
sending a command to a physical device.

It is deliberately not an implementation specification for native writes.
Cloud MQTT, local MQTT, and ZenSDK remain separate transports. Any field or
behaviour not confirmed by source plus a real capture is marked as open.

No native control path is introduced by issue #319.

## Sources and evidence level

Primary reference implementations inspected at fixed revisions:

- [Zendure/Zendure-HA `e71b0b8`](https://github.com/Zendure/Zendure-HA/tree/e71b0b83be2e5909fbaf1cd931ad6a530a2be234)
- [Zendure-HA cloud/local API implementation](https://github.com/Zendure/Zendure-HA/blob/e71b0b83be2e5909fbaf1cd931ad6a530a2be234/custom_components/zendure_ha/api.py)
- [Zendure-HA device and ZenSDK implementation](https://github.com/Zendure/Zendure-HA/blob/e71b0b83be2e5909fbaf1cd931ad6a530a2be234/custom_components/zendure_ha/device.py)
- [Zendure-HA model registry](https://github.com/Zendure/Zendure-HA/blob/e71b0b83be2e5909fbaf1cd931ad6a530a2be234/custom_components/zendure_ha/api.py#L66-L90)
- [Zendure-HA legacy local-MQTT documentation](https://github.com/Zendure/Zendure-HA/wiki/Local-Mqtt-%28Legacy-Devices%29)
- [Zendure-HA SF800 property documentation](https://github.com/Zendure/Zendure-HA/wiki/SolarFlow-800)
- [Gielz1986/Zendure-HA-zenSDK `1c92733`](https://github.com/Gielz1986/Zendure-HA-zenSDK/tree/1c927332849b30a79f8e8e6cfdfb9fcde582210c)
- [ZenSDK REST polling and write commands](https://github.com/Gielz1986/Zendure-HA-zenSDK/blob/1c927332849b30a79f8e8e6cfdfb9fcde582210c/Global%20%28EN%29%20Integration/packages/zendure_gielz1986_global.yaml)

Evidence labels used below:

- **confirmed in reference code**: directly visible in the pinned source;
- **documented by reference project**: stated in its documentation but still
  requires BSFAI field validation;
- **capture required**: shape, timing, or model coverage cannot safely be
  established without real device traffic.

Reference code is evidence of observed interoperability, not an official,
stable Zendure protocol contract. BSFAI must remain defensive against firmware,
region, account, and model differences.

## Transport separation

| Transport | Network path | Discovery/bootstrap | Read path | Write path | Issue #319 conclusion |
|---|---|---|---|---|---|
| Zendure Cloud MQTT | Internet API plus MQTT broker returned by the API | App token -> `/api/ha/deviceList` | MQTT reports and replies | MQTT property/function topics | Structurally understood; real initial-sync and TLS captures still required |
| Local MQTT | Device is reconfigured to a user-controlled LAN broker | Cloud device list plus Bluetooth/Wi-Fi broker provisioning in Z-HA | Same broad MQTT topic families, received on local broker | MQTT property/function topics on local broker | Legacy-device path; provisioning and firmware coverage require real devices |
| ZenSDK | Direct HTTP to device on LAN | IP/name resolution; Z-HA derives a `.local` host if no IP is supplied | `GET /properties/report` | `POST /properties/write` | Local REST path confirmed; discovery, response semantics, and model matrix need field proof |

Cloud MQTT is not "local MQTT over the Internet". Local MQTT changes the
device's broker target. ZenSDK does not use MQTT at all.

## 1. Zendure App token and Cloud bootstrap

### Token structure

The current Zendure-HA implementation treats the App token as Base64-encoded
UTF-8 text. After decoding, it splits at the final dot into:

```text
<Zendure API base URL>.<appKey>
```

Both parts are credentials/bootstrap material:

- the full token is secret;
- `appKey` is secret;
- the decoded API base can reveal account region/routing and should not be
  emitted in normal diagnostics;
- malformed Base64, missing separator, or empty components must fail closed.

BSFAI must never log the original token or the decoded text. Parsing should
return a redacted result containing at most a normalized region/host class,
never the complete URL or key.

### `/api/ha/deviceList` request

Zendure-HA sends an HTTPS POST to:

```text
<decoded API base>/api/ha/deviceList
```

The JSON body contains `appKey`. Request headers include a timestamp, a random
nonce, a fixed client identifier, and an uppercase SHA-1 signature built from
sorted request parameters and the reference client's signing material.

The signing material is intentionally not copied into this document. It is
credential-like implementation detail and must be isolated in the future cloud
auth adapter. It must never reach sensors, debug exports, or normal logs.

Zendure-HA accepts the response only when the top-level response reports
success and code 200. The useful result is the response `data` object. At least
these containers are required by the reference implementation:

- `deviceList`: one or more device definitions;
- `mqtt`: Cloud-MQTT connection data.

### Cloud-MQTT bootstrap fields

The reference code consumes these fields from `data.mqtt`:

- `clientId`
- `url` (host or `host:port`)
- `username`
- `password`

All four are secrets or connection-sensitive values. The broker URL may be
shown only in redacted host-class form. Username, password, and client ID must
not appear in diagnostics.

The reference code uses MQTT 3.1 and defaults to port 1883 when the returned URL
contains no port. It does not configure TLS in the inspected connection path.
This is not sufficient evidence that every region or future endpoint is plain
MQTT. A real capture must record returned port, TLS requirement, certificate
behaviour, MQTT protocol version, session flags, and broker disconnect reason
without recording credentials.

## 2. Device list and stable identity

The current reference path consumes the following per-main-device fields:

| Field | Role | Sensitivity | Proposed BSFAI treatment |
|---|---|---|---|
| `deviceKey` | MQTT routing and current dictionary key | persistent device identity | secret/pseudonymous; store securely, expose only a fingerprint |
| `productKey` | MQTT topic routing and product family | device/product identity | internal adapter metadata; redacted in exported diagnostics |
| `productModel` | exact model registry lookup | low-to-medium | normalized model candidate, never fuzzy-matched |
| `snNumber` | serial and ZenSDK write field | persistent serial | secret/pseudonymous; never export in full |
| `deviceName` | user-editable display label | personal/free text | display only; never identity or profile evidence |
| `ip` | optional ZenSDK address in reference code | network identity | secret; redact or omit from diagnostics |

### Proposed identity model

For V5, a main system should be represented conceptually as:

```text
devices[device_id]
```

where `device_id` is a BSFAI-stable opaque identifier derived from a confirmed
Zendure identity, not the display name. The raw `deviceKey` is the strongest
current main-device candidate because it is also used for MQTT routing. Before
it is adopted as the durable key, captures must verify stability across:

- integration reload;
- Home Assistant restart;
- device rename;
- firmware update;
- Cloud/ZenSDK transport change;
- token regeneration;
- account region changes where applicable.

`productModel` selects only an exact, verified model mapping. Unknown models
remain visible and read-only. Similar spelling or a matching display name is
not enough to assign a `DeviceProfile`.

### Main systems versus packs

Packs are not returned as independently controllable main systems in the
inspected processing path. They arrive inside device telemetry as `packData`.
Each pack record is expected to contain `sn`; the reference code uses that
serial as the pack dictionary key and creates a child device with the main
system serial as parent metadata.

Conceptually V5 therefore needs:

```text
pack_id            = opaque fingerprint of confirmed pack identity
parent_device_id   = owning main-system device_id
pack_model         = exact confirmed pack model, or unknown
```

`packType` is useful model evidence for at least some packs, but the reference
also infers models and capacities from serial prefixes. Serial-prefix inference
is not strong enough to become a universal BSFAI truth. It may be retained as
unverified evidence, but `pack_model = unknown` and unknown capacity are valid
states until a model/pack capture proves a mapping.

Pack order in `packData` must not be treated as stable identity. A pack serial
or another proven device-supplied pack identifier is required.

## 3. Cloud MQTT

### Topics observed in the reference implementation

The reference subscribes per device to both topic roots:

```text
/<productKey>/<deviceKey>/#
iot/<productKey>/<deviceKey>/#
```

Known topic suffixes include:

| Suffix | Direction/meaning in reference |
|---|---|
| `properties/report` | device property report; main read source |
| `properties/energy` | HEMS-related activity signal in Z-HA |
| `properties/read` | request topic, including `getAll` |
| `properties/read/reply` | reply topic, currently ignored by general handler |
| `properties/write` | property write topic |
| `function/invoke` | function command topic |
| `function/invoke/reply` | function reply |
| `register/replay` | registration/replay handshake |
| `time-sync` | time-sync traffic |
| `event/device` | device event |
| `event/error` | error event |
| `config`, `log` | observed but not used for state mapping |

MQTT payloads are JSON. Property updates use a `properties` mapping. Pack data
uses a `packData` list. Commands in the reference add `deviceId`, `messageId`,
and Unix `timestamp` around a property mapping.

The existence of a publish call or broker acknowledgement is not proof that a
device accepted or applied a command. Issue #334 must define verification using
reply/readback and, where possible, physical effect.

### Initial synchronization

For legacy devices Z-HA requests:

```json
{"properties":["getAll"]}
```

on the per-device `properties/read` topic. On first refresh it sends this to
both configured cloud and local clients; subsequent reads use the selected
client.

This establishes that `getAll` is used by the reference, but not that one
response is complete for every model. Issue #324 must capture:

- messages arriving immediately on broker subscription;
- retained flags and QoS;
- response(s) caused by `getAll`;
- whether `properties/report`, `properties/read/reply`, or multiple topics form
  the initial state;
- missing/default properties;
- time until the first complete usable snapshot;
- follow-up incremental reports and their cadence;
- online/offline and reconnect traffic.

No implementation may mark an initial snapshot complete merely because the
first JSON object arrived.

## 4. Local MQTT

Zendure-HA documents local MQTT as necessary only for legacy families:

- Hyper 2000
- Hub 2000
- Hub 1200
- ACE 1500

The same documentation says newer SF800/SF800Pro/SF2400 families can use
ZenSDK instead. This is a reference-project support statement, not yet a full
Zendure capability matrix.

The local path requires a user-controlled MQTT broker, broker host/port,
username/password, Wi-Fi SSID/password, and Bluetooth visibility. Z-HA uses
Bluetooth to change the device's MQTT target and the device reboots during the
operation. This provisioning action is state-changing and is out of scope for
issue #319.

The inspected runtime subscribes to the same two broad topic roots on the local
broker. It can also relay selected local traffic to Zendure Cloud so that the
app and firmware functions continue to work. BSFAI must not copy this relay
behaviour implicitly: it creates a second connection, a second trust boundary,
and potential competing authority.

Open local-MQTT questions for real captures:

- exact Bluetooth provisioning protocol and failure modes;
- whether every listed legacy model uses identical topics and JSON shapes;
- retained-message behaviour after broker change;
- authentication requirements and username case rules;
- reconnection after broker/Home Assistant restart;
- whether app/firmware use truly requires relaying for each firmware;
- whether Cloud and local messages can race or duplicate energy samples;
- online/offline semantics when the LAN broker is reachable but the device is
  not publishing;
- safe recovery procedure if provisioning is interrupted.

## 5. ZenSDK

### Addressing and discovery

ZenSDK is a local HTTP/REST transport. The current Z-HA implementation uses an
explicit IP from device metadata when available. Otherwise it constructs a
hostname conceptually like:

```text
zendure-<productModel-without-spaces>-<serial>.local
```

This demonstrates `.local` name use, but not the authoritative mDNS service
type or TXT-record schema. Issue #319 cannot claim true automatic mDNS
discovery until a packet/service capture provides:

- service type;
- instance name;
- A/AAAA records;
- TXT fields;
- relationship to serial, device key, and product model;
- behaviour with multiple identical devices and multiple network interfaces.

Until then, IP input and derived `.local` names are fallback addressing, not a
proven discovery contract.

### Read endpoint

The confirmed local read endpoint is:

```text
GET http://<device>/properties/report
```

The independent ZenSDK Home Assistant package polls it once per second. Z-HA
polls it according to its coordinator/selected-transport logic and feeds the
returned JSON through the same property mapper as MQTT.

The observed response shape is conceptually:

```json
{
  "product": "<model/product value>",
  "properties": {
    "electricLevel": 0,
    "acMode": 0
  },
  "packData": [
    {
      "sn": "<pack serial>",
      "packType": 0,
      "socLevel": 0
    }
  ]
}
```

This is illustrative and deliberately incomplete. Absence of a field must be
represented as missing/unsupported, never as numeric zero.

### Write endpoint (analysis only)

The confirmed local write endpoint is:

```text
POST http://<device>/properties/write
```

Reference requests contain the main-system serial plus a `properties` mapping.
Z-HA also adds a monotonically increasing in-memory `id`. Examples in the
reference projects write `smartMode`, `acMode`, `inputLimit`, `outputLimit`,
`minSoc`, and `socSet`.

Issue #319 does not authorize calling this endpoint. The reference returns
success after the HTTP request is sent and does not establish that the property
was applied. Native BSFAI must later require:

1. HTTP transport result;
2. parsed response/acknowledgement where available;
3. property readback from `properties/report`;
4. optional physical-effect confirmation;
5. bounded timeout/retry policy;
6. no replay after restart or transport change.

### ZenSDK model evidence

The current Zendure-HA registry implements the following as `ZendureZenSdk`
families:

- SolarFlow 800
- SolarFlow 800 Pro / Pro 2
- SolarFlow 800 Plus
- SolarFlow 1600 AC+
- SolarFlow 2400 AC
- SolarFlow 2400 AC+
- SolarFlow 2400 Pro
- SolarFlow 4000 AC+

The independent ZenSDK project additionally claims support for 3000 Mix AC+
and 4000 Mix variants. These lists are project support claims, not proof that
every firmware exposes every property. The V5 capability matrix must be
property- and firmware-aware. No model is write-enabled solely because its
name occurs in this list.

## 6. Raw properties versus derived Z-HA values

### Direct device fields relevant to BSFAI

The following fields are read directly from `properties` or `packData` in the
inspected references and are candidates for native mapping:

| Domain | Raw candidate fields | BSFAI use |
|---|---|---|
| Main SoC/status | `electricLevel`, `socLimit`, `socStatus`, `packState`, `packNum` | SoC, limit status, calibration/status evidence, charge state |
| AC control/readback | `acMode`, `inputLimit`, `outputLimit`, `smartMode` | command readback and current mode/limits |
| Power | `gridInputPower`, `outputHomePower`, `solarInputPower`, `outputPackPower`, `packInputPower`, `gridOffPower` | measured charge/discharge, PV, home/off-grid context |
| Limits/config | `chargeMaxLimit` or `chargeLimit`, `inverseMaxPower`, `minSoc`, `socSet`, `gridReverse`, `gridOffMode` | hardware/runtime limits and settings |
| Protection/error | `heatState`, `is_error`, `hyperTmp`, `connectionStatus`, device/error events | blocker/health evidence |
| Pack identity/state | `sn`, `packType`, `socLevel`, `state`, `power`, `softVersion` | pack membership and telemetry |
| Pack electrical/thermal | `maxTemp`, `totalVol`, `batcur`, `maxVol`, `minVol` | cell/temperature protection evidence |

Property names, scales, sign conventions, and availability are not assumed
universal. For example, the SF800 reference documents encoded temperature,
current, and voltage units, while `minSoc`/`socSet` may be tenths of a percent
in ZenSDK payloads. The mapper must be model/capability aware and retain raw
evidence for redacted diagnostics.

### Values computed by Z-HA or the independent package

These must not be described as direct Zendure API fields merely because they
appear as Home Assistant entities:

- total capacity in kWh (summed from inferred pack models/capacities);
- available kWh (capacity multiplied by usable SoC range);
- combined signed battery power (`packInputPower - outputPackPower` in Z-HA's
  convention);
- remaining charge/discharge time;
- aggregated charged, discharged, solar, grid-input, home-output, and off-grid
  energy;
- round-trip efficiency;
- relay/switch counts;
- cell-balance labels derived from max/min cell voltage difference;
- PV-to-home and PV-to-battery splits calculated from several raw powers;
- calibration due date/last-calibration bookkeeping;
- HEMS connection/status classifications synthesized by Z-HA;
- manager/global SoC and multi-device power allocation;
- charge/discharge limits hard-coded by Z-HA model classes.

BSFAI may later calculate equivalent concepts, but their provenance must say
`derived` and identify their raw inputs. They must not overwrite a direct
device property with the same display meaning.

### HEMS and calibration caution

Z-HA sets its `hemsState` when it sees `properties/energy` traffic and ages that
state using its own timeout. This is evidence of HEMS activity, not yet proof of
a canonical boolean property delivered by every device. V5's hard HEMS blocker
needs a per-model, per-transport truth table proven by captures.

`socStatus` is labelled as calibrating by the references, while other
calibration dates are inferred from observing full SoC or status transitions.
BSFAI must distinguish:

- a direct current calibration/status property;
- a confirmed completed full charge;
- a locally calculated maintenance due date;
- an actual device command for calibration, which is not established here.

## 7. Minimum native data needed by current BSFAI

To preserve V4.7.1 behaviour, a selected device's native snapshot eventually
needs, with validity and freshness attached:

- main-system identity and exact verified profile/capabilities;
- total SoC;
- measured battery AC charge/discharge power or an equally reliable native
  directional pair;
- current AC mode;
- current input and output limits;
- hardware/runtime maximum input and output evidence without replacing profile
  maxima;
- SoC limit status where supported;
- per-pack lowest cell-voltage evidence where supported;
- pack membership and stable pack identity;
- off-grid power and off-grid mode where supported;
- HEMS blocker state;
- online/freshness/error state;
- readback properties required to verify future commands.

House-grid power, general house PV, market prices, feed-in tariff, and forecasts
remain Home Assistant/HEMS inputs. They are not replaced by the Zendure device
transport merely because a device exposes related local measurements.

## 8. Secret and privacy classification

Never emit unredacted values for:

- App token;
- decoded token text;
- `appKey`;
- request signing material or signatures;
- Cloud-MQTT client ID, username, or password;
- local-MQTT username/password;
- Wi-Fi SSID/password;
- complete `deviceKey`/device ID;
- complete main-device or pack serial number;
- device IP address or full `.local` hostname;
- Authorization headers or future session cookies/tokens;
- user-defined device names when diagnostics are anonymized.

Safe diagnostic substitutes:

- per-export salted fingerprints, not stable global hashes;
- model/capability labels only when verified;
- redacted host class/region rather than full endpoint;
- boolean `configured`, `available`, `fresh`, and `matches_readback` flags;
- payload schema/key inventory with values removed;
- numeric technical measurements only after identity fields are stripped.

MD5-derived local broker credentials used by the reference are not a suitable
new BSFAI credential design. Issue #320 owns secure storage, redaction, and
credential lifecycle.

## 9. Required initial-sync capture matrix

Issue #324 should collect redacted captures for each available combination:

| Dimension | Required variants |
|---|---|
| Transport | Cloud MQTT, Local MQTT, ZenSDK |
| Lifecycle | cold start, HA reload, reconnect, device reboot, firmware update where safe |
| Device state | idle, charging, discharging, PV passthrough, SoC limit, offline/recovery |
| Packs | no external pack where valid, one pack, multiple packs, mixed pack models |
| Control context | Zendure HEMS off/on, Z-HA manager off, no concurrent writer |

Each capture should record, after redaction:

- verified model and firmware;
- transport and connection timing;
- ordered message/request timeline;
- topic/path and payload key inventory;
- retained/QoS information for MQTT;
- HTTP status and response-key inventory for ZenSDK;
- first-seen and last-seen time per property;
- which properties are initial-only, periodic, incremental, or event-only;
- missing/null/zero distinctions;
- pack order and identity stability;
- online/offline and HEMS transitions;
- discrepancies against Z-HA entities;
- no secrets and no full identity values.

Captures for issue #324 remain read-only. No `properties/write`, function
invoke, broker reprovisioning, or BLE configuration is needed to establish the
initial read model.

## 10. Decisions established by issue #319

1. Cloud bootstrap is App token -> decoded API base/appKey -> signed
   `/api/ha/deviceList` -> device list plus Cloud-MQTT credentials.
2. `deviceKey` is the strongest current main-device identity candidate, but its
   lifecycle stability still requires capture proof.
3. Packs are child records from `packData`; order is not identity.
4. Cloud MQTT and Local MQTT share topic families but are separate authority
   and trust domains.
5. ZenSDK is local HTTP/REST with `GET /properties/report` and
   `POST /properties/write`.
6. A transport acknowledgement is not device success.
7. Direct properties and locally derived values must retain different
   provenance.
8. Unknown model, unknown pack model, missing property, stale property, and
   valid numeric zero are distinct states.
9. Z-HA's current model classes are evidence for a candidate capability matrix,
   not permission to write to all listed models.
10. HEMS status and calibration semantics still require explicit real-device
    proof.
11. No runtime auto-switch between transports is designed or implied.
12. No native write implementation is part of this research issue.

## 11. Open questions handed to later V5 issues

### Issue #320: secrets and privacy

- Binding model: `zendure-secrets-privacy-v5.0.0.md`.
- secure token/MQTT credential storage and reauth;
- salted diagnostic identity fingerprints;
- signing implementation isolation;
- endpoint/IP/serial redaction tests.

### Issue #321: identity

- Binding model: `zendure-device-identity-v5.0.0.md`.
- prove `deviceKey` stability;
- exact device/pack identity schema;
- duplicate/moved pack behaviour;
- exact versus unknown model mapping.

### Issues #322 and #323: Cloud discovery/read-only

- regional API and broker differences;
- TLS/MQTT session facts;
- resilient device-list and broker error handling;
- read-only subscriptions with no command topics published.

### Issue #324: initial sync

- completeness criteria;
- incremental/event-only property inventory;
- retained/stale message handling;
- per-model/firmware capture matrix.

### Issues #337 and #340: local read transports

- safe Local-MQTT provisioning boundary and model coverage;
- authoritative ZenSDK mDNS discovery;
- polling interval, rate limits, timeouts, and concurrency;
- per-property transport parity.

### Issues #331-#335 and #343: future write safety

- HEMS truth source;
- central command gate;
- single explicit write authority;
- response/readback/effect verification;
- bounded retries and no replay.

## Acceptance-criteria check

- [x] Cloud, Local MQTT, and ZenSDK are separated.
- [x] App-token to device-list and Cloud-MQTT bootstrap is documented.
- [x] Known topic and payload families are identified.
- [x] Main systems and packs are conceptually separated.
- [x] Candidate stable identifiers and their unresolved risks are documented.
- [x] Known reference-project model differences are recorded without granting
      write support.
- [x] Direct and derived values are separated.
- [x] Secret and identity fields are classified.
- [x] Initial-sync capture gaps are explicit.
- [x] No active native control was introduced.
