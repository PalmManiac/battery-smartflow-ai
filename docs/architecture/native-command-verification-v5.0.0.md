# V5 native command verification

Issue #334 generalizes the first verified ZenSDK write from #333 into a
transport-neutral lifecycle below the PowerController and above every native
transport adapter.

## Boundary

The execution chain is:

`PowerController -> DeviceCommand -> DeviceCommandGate -> Transport -> CommandVerification`

The PowerController owns the requested physical outcome. The gate owns current
write authority and safety. A transport owns only sending and its technical
acknowledgement. `NativeCommandVerificationManager` owns correlation of fresh
readback and optional physical effect.

A transport acknowledgement can never complete a command. Completion requires
a fresh, correctly addressed readback. Effect verification is a separate,
command-specific decision and may legitimately be `not_applicable` or
`not_observable`.

## Correlation and concurrency

Each command has a random command ID and an exact `(device_id, target_key)`
ownership key. A newer command for the same device and target supersedes the
older command. Other targets and other devices remain independent. Late
readback for a superseded command is ignored.

Readback is accepted only when the device, property and timestamp match the
command. The timestamp must be later than the send timestamp. A per-command
tolerance represents verified device quantization or clamping; it is never a
global guessed tolerance.

## Result states

The lifecycle distinguishes preparation, gate acceptance, sending, transport
acceptance, readback confirmation and effect confirmation. Blocked, transport
error, readback timeout/mismatch, contradictory response, effect
timeout/mismatch, superseded and cancelled are separate outcomes.

An ambiguous transport error followed by the expected device value is recorded
as a contradictory response rather than silently converted to success.

Retry permission is explicit per command through `max_attempts`. The default is
one attempt. The manager never schedules retries itself.

## Diagnostics

Diagnostics expose requested/final values, transport status, readback,
effect status and the following measured intervals:

- gate to send
- send to transport result
- send to readback
- send to physical effect

Device identifiers are pseudonymized. Command metadata, payloads, credentials,
tokens and serial numbers are not part of the diagnostic model. History is
bounded, and repeated ineffective commands are counted per pseudonymous device.

The Dev14 reversible SF2400AC test is the first consumer of this generalized
layer. Normal PowerController writes remain on the Home Assistant/Z-HA backend;
this issue enables no additional native command or transport.
