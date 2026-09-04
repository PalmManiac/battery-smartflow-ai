# V5.0.0: Productive native PowerController path

Issue #336 connects the unchanged neutral regulation output to the native
Zendure Cloud MQTT stack:

```text
DecisionEngine -> StrategyIntent -> ModeArbiter -> RegulationPowerController
  -> DeviceCommand -> NativeDeviceCommandGate -> Cloud MQTT mapping
  -> publish acceptance -> fresh readback -> optional physical effect
```

The PowerController still knows no Zendure property, MQTT topic, credential, or
transport rule. The Coordinator selects the output backend only from the
explicit `native_zendure_control_enabled` option. With the option disabled,
the established Home Assistant/Z-HA backend remains unchanged. With it
enabled, that backend is not called, preventing competing writes.

## Fail-closed activation

Native output additionally requires exactly one selected main system, an
observing runtime after initial synchronization, a connected Cloud MQTT
session, fresh online/protection/HEMS observations, a unique Cloud identity,
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
inside the Cloud adapter implemented by issue #335.

## Feedback and diagnostics

MQTT publish acceptance is reported as `awaiting_readback`, not device success.
Every property has a bounded 15-second readback window. A fresh exact readback
confirms it; a newer same-target command supersedes it; otherwise it becomes a
readback timeout. Diagnostics keep transport and readback status separate and
omit credentials and native identities.
