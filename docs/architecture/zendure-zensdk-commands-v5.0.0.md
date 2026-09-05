# ZenSDK command adapter contract for V5.0.0

The ZenSDK write path follows this boundary:

`DeviceCommand -> NativeDeviceCommandGate -> AuthorizedNativeCommand -> ZenSDK adapter`

The adapter cannot accept an unaddressed property/value pair. It accepts only
the gate-issued envelope for one exact logical main device, resolves that device
through the Cloud bootstrap identity, and checks the per-transport property
evidence in the device matrix again before sending any HTTP request.

## Initial allow-list

The initial field-verified scope is deliberately limited to `outputLimit` on
the SolarFlow 2400 AC. `acMode`, `smartMode`, `inputLimit`, `minSoc`, and
`socSet` remain reference-only and therefore cannot produce a POST. Other
models remain blocked until the same property-level evidence exists for them.

The mapping retains whole watts for `outputLimit`. SoC fields are prepared as
tenths of a percent, but remain unreachable until their individual matrix
capabilities are verified.

## Delivery and verification

Each approved property is posted at most once to `/properties/write`. There is
no retry after a timeout, no alternate-address write, no command replay after
rediscovery, and no fallback to Cloud or Local MQTT. A 2xx result records only
HTTP transport acceptance. It does not mark the command as applied.

Every write prepares a transport-neutral readback record before it is sent.
Only a later ZenSDK report for the same logical device, same property, and a
timestamp newer than the send timestamp can confirm it. Superseded-command and
bounded-history behavior stays in the shared verification manager.

Issue #342 connects this adapter to the productive neutral command path when
the verified model family identifies ZenSDK as its local transport. Users do
not choose a transport. Normal scheduled ZenSDK reports feed the same
verification manager, so command confirmation adds no second polling loop. An
unavailable or stale ZenSDK path blocks writes without Cloud, Local MQTT, or
Z-HA fallback.
