# V5.0.0 Zendure secrets and diagnostic privacy model

Status: binding foundation for issues #320 and #322–#324  
Runtime baseline: V4.7.3  
Scope: Cloud bootstrap, Cloud MQTT, Local MQTT, ZenSDK and all diagnostic output

## 1. Trust boundaries

Native Zendure communication is split into three layers:

1. **Credential and transport adapters** may temporarily hold the exact values
   required for authentication, signing and connection setup.
2. **Native device adapters** receive authenticated messages and convert them
   into identity-aware raw device observations.
3. **Neutral device state, RuntimeSnapshot, Strategy and PowerController** must
   never receive tokens, MQTT credentials, signing material or raw connection
   endpoints.

Credentials are not device state. A transport adapter may reference a stable
internal device identity, but a neutral device model must not reference the
credential object that made a message available.

## 2. Classification

### Secrets: always remove

- complete App/Home-Assistant token and decoded token text;
- `appKey`, API keys, access/refresh tokens and private keys;
- Authorization, Bearer and Basic headers;
- request signatures, signing material, cookies and session credentials;
- Cloud- and Local-MQTT client ID, username and password;
- Wi-Fi SSID/password and other provisioning credentials;
- values in future fields whose names identify them as credentials or secrets.

Secret values become `[REDACTED]`. They never become hashes or aliases because
diagnostic equality for credentials is not a supported use case.

### Sensitive identities: package-local pseudonyms

- `deviceKey`, device IDs and device-map keys;
- main-device and pack serials (`serial`, `sn`, `snNumber`);
- pack IDs/keys and pack-map keys;
- `productKey` where it participates in routing or account identity;
- occurrences of the same identifiers inside MQTT topics, URLs and error text.

Examples:

- `ZD_DEVICE_A1`
- `ZD_SERIAL_A1`
- `ZD_PACK_A1`
- `ZD_PRODUCT_A1`

Equal source identities receive the same alias everywhere in one export. Alias
namespaces restart for every export. They are deliberately unsuitable for
cross-export or cross-installation tracking and are not internal device IDs.

### Network and user identifiers: remove

- complete API endpoints and broker URLs;
- IP addresses and full `.local` hostnames;
- user-defined names when a capture path enables name anonymization;
- any network identifier that embeds a serial or device ID.

Transport class (`cloud_mqtt`, `local_mqtt`, `zensdk`), normalized region/host
class and connection state may be exposed separately when later adapters can
derive them without retaining the original endpoint.

### Safe technical data

After sanitizing identities and credentials, diagnostics may contain:

- verified model, firmware and capability labels;
- transport class, lifecycle phase and timing;
- numeric power, energy, voltage, temperature and SoC measurements;
- valid zero, missing, null, stale and invalid as distinct states;
- payload key/schema inventories;
- MQTT QoS/retained flags and request/response status classes;
- configured/available/fresh/readback-match booleans.

## 3. Central sanitizing boundary

`zendure_privacy.ZendureDiagnosticSanitizer` is the shared implementation for
native Zendure payloads and the existing BSFAI debug pipeline. Supported output
paths must pass through this boundary before serialization, logging or entity
attribute creation.

The sanitizer:

1. creates a detached JSON-safe copy;
2. performs a complete discovery pass for secrets and identities;
3. assigns package-local typed aliases;
4. recursively sanitizes mapping values, mapping keys and sequences;
5. replaces discovered identities inside MQTT topics and free text;
6. removes inline Authorization/Bearer credentials and assignments;
7. preserves numeric zero, null and boolean values exactly.

The discovery pass is required because an MQTT topic can occur before the
`deviceKey` field that explains the identity embedded in that topic.

Unknown nested properties are not exempt. Every mapping and sequence passes
through the same recursive boundary, and future credential-looking field names
are conservatively redacted.

## 4. Exception and logging policy

Never log raw HTTP responses, MQTT payloads, connection objects or `repr()` of
requests/exceptions that may carry credentials.

A transport operation creates one sanitizer context, registers its credential
and identity inputs by sanitizing the structured context, and uses
`sanitize_exception()` for any externally supplied exception text.

Allowed:

```text
Zendure Cloud MQTT authentication failed for ZD_DEVICE_A1
```

Forbidden:

```text
MQTT login failed username=<full> password=<full> device=<full deviceKey>
```

Operational logs should prefer controlled reason enums over remote free text.
Sanitized remote detail belongs in diagnostics only when it materially helps
support.

## 5. Home Assistant persistence and reauthentication

Issues #322 and later must follow these rules:

- persist only credentials actually required to reconnect;
- use the integration ConfigEntry data/options mechanisms;
- do not create a separate plaintext credential file;
- do not copy secrets into coordinator persistence, learned state or debug
  configuration;
- pass credentials directly from the HA adapter to the owning transport;
- token replacement updates the owning ConfigEntry value and recreates the
  affected transport context;
- reauthentication UI and errors expose only controlled reason/status values;
- unload/reload drops in-memory connection credentials with the transport.

Home Assistant ConfigEntry storage is not presented as encrypted secret
storage. The safety objective is least duplication, platform-owned persistence
and zero diagnostic/log/entity exposure.

## 6. Home Assistant entity contract

Entities and attributes may expose model, product family, transport class,
online state, capabilities and package-local diagnostic aliases where useful.

They must never expose:

- credentials or signature material;
- full device, pack or serial identities;
- full API/broker endpoints, IP addresses or hostnames;
- raw unfiltered request, response or MQTT payloads.

Internal stable device identity for the registry is owned by issue #321. The
diagnostic aliases in this document must not be used as registry identifiers.

## 7. Initial-sync capture contract

Issue #324 may retain a near-complete ordered initial-sync capture only after
the complete capture object has passed through one sanitizer instance.

The capture writer must:

- sanitize before writing, not after reopening a raw file;
- never create a temporary unredacted capture;
- run a second sanitizing pass at the serialization edge as defence in depth;
- use one alias namespace for HTTP bootstrap, topics, payloads and pack data;
- fail closed when serialization or sanitizing cannot complete;
- report controlled errors without including the rejected raw value.

Captures may preserve unknown property names and safe values. A property name
that looks like a secret, credential, identity or network address is sanitized
even when the firmware field was not known when BSFAI was released.

## 8. Test contract

Automated tests cover:

- App token, `appKey`, client ID, username and password removal;
- nested and unknown credential fields;
- Authorization/Bearer and inline assignment removal;
- device, pack, serial and product aliases;
- consistent aliases across fields, mapping keys, topics and free text;
- IDs encountered after the topic in the original payload;
- endpoint, broker, IP and hostname removal;
- exception text containing discovered secret/identity values;
- source immutability and JSON-safe timestamps;
- preservation of zero, null and boolean distinctions;
- package-local alias namespace reset;
- compatibility of the existing V4 debug-package pipeline.

## 9. Handoff to later V5 issues

- **#321** defines real internal device/pack identities. Diagnostic aliases are
  not candidates for that model.
- **#322** stores the App token minimally and keeps decoding/signing inside the
  Cloud transport adapter.
- **#323** owns Cloud-MQTT credentials and must never add them to device state.
- **#324** uses one sanitizer context for the complete initial-sync capture.
- **#325+** receive only sanitized diagnostics and credential-free normalized
  observations.

No native network request or device write is introduced by issue #320.

