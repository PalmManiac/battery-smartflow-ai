# V5.0.0 Zendure device, pack and upgrade identity model

Status: binding foundation for issue #321  
Runtime baseline: V4.7.3  
Scope: logical systems, native identities, packs, discovery and V4-to-V5 binding

## 1. Identity rule

A BSFAI system and a Zendure hardware identity are not the same object.

- The **logical BSFAI system ID** owns configuration, entity registry identity,
  history, learned state and the selected control target.
- A **native hardware identity** describes how Cloud MQTT, Local MQTT or ZenSDK
  recognizes the physical Zendure system.
- One logical system may accumulate multiple transport-specific identities
  after explicit matching.
- A diagnostic alias from issue #320 is never an internal or registry ID.

For an upgraded V4 installation the logical identity is derived from the
existing Home Assistant ConfigEntry ID. Existing entity unique IDs and device
registry identifiers remain anchored to that ConfigEntry. Native discovery must
not replace this owner.

## 2. Existing V4 installations

Updating the integration does not enable native communication and does not
create a second device. The existing Home Assistant entity backend remains the
selected transport until a separate migration flow completes.

The flow is:

1. load the existing ConfigEntry, settings and state unchanged;
2. represent it as one active logical system;
3. collect native discovery results as read-only candidates;
4. show model, safe display name, shortened identity, pack count and transports;
5. let the user identify which candidate is the existing physical system;
6. attach the confirmed native identity to the same logical system;
7. validate native readings before offering a backend switch;
8. retain the old Home Assistant entity configuration as a rollback source;
9. switch transport only in a later explicit step.

Even an exact stable-identifier match is a suggestion, not authorization to
bind or control hardware. Model and friendly name alone never establish an
identity. An ambiguous or absent match leaves the V4 system untouched.

## 3. Fresh installations

On a fresh installation a confirmed discovery candidate may create a logical
system. It starts in observation mode. A supported model is not automatically
controlled; an unknown model starts unsupported/read-only.

Discovery itself never creates Home Assistant entities and never selects an
active system.

## 4. Main systems and packs

`DeviceInventory` is collection-based and has no fixed device count:

```text
devices[logical_system_id]
packs[pack_id] -> parent logical_system_id
candidates[transport_scoped_native_id]
```

Packs are hierarchical observations. They cannot become an active control
target independently from their parent main system. A pack without a known
parent is rejected rather than guessed into place.

## 5. V5 control invariant

The inventory may contain any number of observed systems, but V5 permits at
most one `ACTIVE` main system. Newly discovered systems are `OBSERVATION` or
`UNSUPPORTED`. If the active system disappears, it becomes `OFFLINE`; no other
system is promoted automatically.

HEMS remains a blocker state. Detection, support, enablement and active control
are separate decisions:

```text
discovered != supported != enabled != active
```

## 6. Persistence boundary

The inventory schema persists only identity and management metadata:

- logical main systems and confirmed transport identities;
- parent/pack relationships;
- available and selected transport;
- profile/support/control state;
- online and HEMS flags.

Discovery candidates are transient and deliberately not serialized. Tokens,
MQTT credentials and signing material remain outside the inventory as required
by issue #320.

The serialized inventory is versioned and validates after loading: no native
identity may belong to two systems, no pack may have an unknown parent, only one
V5 system may be active, and the selected transport must be available.

## 7. Home Assistant registry migration contract

Later config-flow and registry work must update an existing installation in
place:

- keep the existing ConfigEntry;
- keep published entity unique IDs where their meaning is unchanged;
- keep entity IDs, custom names, areas and enabled/disabled state;
- preserve recorder/statistic IDs and learned BSFAI state;
- do not delete and recreate the V4 BSFAI device to attach native hardware;
- use explicit registry migration only if a future entity must change owner;
- provide cancellation and rollback before removing legacy source references.

Issue #321 defines the neutral identity model only. It does not perform native
discovery, modify ConfigEntry data, touch registries or switch a backend.

## 8. Handoff

- #322–#324 create credentials, transports and discovery candidates without
  creating active systems.
- A later config-flow step presents and confirms V4-to-native bindings.
- Native observation validates the selected candidate before backend cutover.
- V6 reuses the same collection and identity model when multiple active systems
  are eventually allowed.
