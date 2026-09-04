# V5.0.0: Zendure Cloud MQTT command mapping

Issue #335 adds the typed write boundary for Zendure Cloud MQTT. It does not
connect the productive `PowerController`; that remains the responsibility of
the following integration step.

## Boundary

```text
DeviceCommand
  -> NativeDeviceCommandGate
  -> AuthorizedNativeCommand
  -> ZendureCloudCommandAdapter
  -> typed properties/write publish
  -> fresh properties/report readback
  -> NativeCommandVerificationManager
```

There is no public arbitrary topic/property publish method. The adapter accepts
only a gate-issued envelope, resolves the exact Cloud identity from the
bootstrap inventory, and rejects unknown devices, packs, models, transports,
and unmapped properties. It never retries an ambiguous publish, changes the
target, or falls back to another transport.

## Confirmed mapping

The Zendure reference implementation confirms the topic
`iot/<productKey>/<deviceKey>/properties/write` and the envelope fields
`properties`, `messageId`, `deviceId`, and Unix `timestamp`. Writes use QoS 0
and are not retained.

| Neutral target | Cloud property | Raw value | Readback |
|---|---|---:|---|
| input mode | `acMode` | `1` | `acMode` |
| output mode | `acMode` | `2` | `acMode` |
| input limit | `inputLimit` | whole watts, including `0` | `inputLimit` |
| output limit | `outputLimit` | whole watts, including `0` | `outputLimit` |
| minimum SoC | `minSoc` | percent multiplied by 10 | `minSoc` |
| maximum SoC | `socSet` | percent multiplied by 10 | `socSet` |

Enabled properties are emitted in the stable order mode, input, output,
minimum SoC, maximum SoC. Each property gets a separate, small payload and a
separate message and verification identity. Hardware power ceilings are still
owned by `DeviceProfile` and applied by the central gate before mapping.

## Verification and concurrency

MQTT publish acceptance produces only `transport_ok` and
`awaiting_readback`. Device success requires a newer report for the exact
device and property with the expected raw value. A newer command for the same
device/property supersedes the prior active verification, so delayed reports
cannot complete the older command. The adapter sends at most once per mapped
property and stops the sequence at the first publish failure.

The capability matrix now records property-write evidence per transport.
Therefore Cloud MQTT support cannot accidentally authorize the same property
on ZenSDK or Local MQTT. The separately field-proven ZenSDK scope remains
SF2400AC `outputLimit` only.

## Safety and privacy

- HEMS, writer-conflict, migration, selected-device, online/protection, and
  capability checks remain in `NativeDeviceCommandGate`.
- Credentials remain in the MQTT session and never enter commands,
  verification history, or diagnostics.
- Verification diagnostics pseudonymize the logical device key and omit native
  IDs, product keys, serial numbers, topics, and payloads.
- Productive use is intentionally absent until the PowerController integration
  is implemented and tested.
