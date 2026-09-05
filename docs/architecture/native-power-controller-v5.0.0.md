# V5.0.0: Productive native PowerController path

Issue #336 connects the unchanged neutral regulation output to the native
Zendure native stack. Issue #336 introduced Cloud MQTT; issue #342 adds the
same gated path for ZenSDK:

```text
DecisionEngine -> StrategyIntent -> ModeArbiter -> RegulationPowerController
  -> DeviceCommand -> NativeDeviceCommandGate -> selected transport adapter
  -> transport acceptance -> fresh readback -> optional physical effect
```

The PowerController still knows no Zendure property, MQTT topic, credential, or
transport rule. The Coordinator selects the output backend only from the
explicit `native_zendure_control_enabled` option and native transport choice.
With the option disabled,
the established Home Assistant/Z-HA backend remains unchanged. With it
enabled, that backend is not called, preventing competing writes.

## Fail-closed activation

Native output additionally requires exactly one selected main system, an
observing runtime after initial synchronization, a ready explicitly selected
transport, fresh online/protection/HEMS observations, a unique device identity,
an approved model/profile and transport, inactive HEMS, and a gate-approved
command. Packs are never command targets. There is no device or transport
fallback.

During startup, initial capture, disconnect, reconnect, stale state, or HEMS
uncertainty, the command is skipped. No command from before a restart or
disconnect is persisted or replayed. The MQTT reconnect requests a fresh
`getAll` report before subsequent state-based command execution.

## Preserved regulation behavior

The existing `DeviceCommandBuilder`, deadbands, no-change flags, step limits,
holds, latches, mode cooldowns, keepalive behavior and profile clamping remain
the only regulation source. The native backend removes individual writes whose
fresh readback already equals the requested mode or limit. A remaining command
is sent through the same central gate used by the development write test.

INPUT, OUTPUT and a zero-watt stop retain their neutral DeviceCommand meaning.
Zendure-specific mode values, SoC scaling, property ordering and payloads stay
inside the selected transport adapter.

## Explicit ZenSDK ownership

Existing entries without a saved transport remain on Cloud MQTT for upgrade
compatibility. Choosing ZenSDK is explicit and never inferred from reachability.
When selected, a command can run only while the per-device ZenSDK health is
fresh and available. The Cloud publisher and Home Assistant/Z-HA backend are
not called. Loss of local reachability blocks the command without fallback.

The first productive ZenSDK allow-list remains limited to the field-verified
SF2400AC `outputLimit`. Commands requiring reference-only properties such as
`acMode` or `inputLimit` fail at the central gate before reaching the adapter.
This permits isolated regulation tests without silently treating an incomplete
start or direction-change sequence as successful.

## Feedback and diagnostics

MQTT publish acceptance is reported as `awaiting_readback`, not device success.
Every property has a bounded 15-second readback window. A fresh exact readback
confirms it; a newer same-target command supersedes it; otherwise it becomes a
readback timeout. Diagnostics keep transport and readback status separate and
omit credentials and native identities.
