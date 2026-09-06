# Native transport measurements for V5.0.0

Issue #344 measures whether each automatically selected local transport carries
neutral BSFAI commands and telemetry reliably. Measurements never select a
write transport and never enable fallback.

## Metrics schema

The privacy-safe native diagnostics include
`battery_smartflow_ai.native_transport_metrics` schema version 1. Command
samples are grouped by pseudonymized physical device, model, firmware,
transport and command type. They expose separate statistics for:

- gate to send;
- send to transport response;
- send to fresh readback;
- send to physical effect, where observable;
- neutral status/effect counts plus timeout, mismatch, transport-error and
  superseded counts and rates.

Telemetry samples are grouped by device, model, firmware and transport. They
expose update-interval statistics plus disconnect and reconnect counts. Only a
bounded in-memory sample is retained. Median, minimum and maximum remain useful
for small field samples; p90 and p95 are deliberately omitted until at least 20
samples exist.

The export contains no serial number, device key, broker address, IP address,
token, username, password or command payload. Device identity is represented by
a one-way truncated hash that is stable only for grouping the same installation.

## Controlled SF2400AC baseline

The first controlled measurement used one SF2400AC with V5 development build
5.0.0.dev15 and five reversible 0 -> 1 -> 0 W output-limit cycles under the
same Home Assistant installation and network conditions.

- direct ZenSDK confirmed readback median: 1.528 seconds;
- Z-HA end-to-end entity-state median: 2.994 seconds;
- observed reduction under this setup: approximately 49 percent.

The Z-HA number measures from the Home Assistant service request to the
confirmed Z-HA entity state, so it is not a pure network-latency comparison.
This is first-device evidence, not a performance guarantee for another model,
firmware, network or installation. It does not validate Cloud MQTT or Legacy
Local MQTT.

## Outstanding field measurements

Longer runs must still cover command types, restarts, reconnects, idle and
active regulation, Near-Zero behavior and physical effect. Hyper 2000 and
SolarFlow Hub 2000 require separate Local MQTT versus Z-HA measurements on real
already-provisioned Legacy hardware. Results remain attached to their exact
model, firmware, transport and test conditions.
