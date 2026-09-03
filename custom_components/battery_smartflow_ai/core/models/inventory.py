"""Neutral multi-device identity and V4-to-V5 binding models."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Iterable, Mapping


class ZendureTransport(StrEnum):
    """Communication paths that may identify the same physical system."""

    HOME_ASSISTANT = "home_assistant"
    CLOUD_MQTT = "cloud_mqtt"
    LOCAL_MQTT = "local_mqtt"
    ZENSDK = "zensdk"


class DeviceControlState(StrEnum):
    """Explicit management state of one discovered main system."""

    OBSERVATION = "observation"
    ELIGIBLE = "eligible"
    ENABLED = "enabled"
    ACTIVE = "active"
    HEMS_BLOCKED = "hems_blocked"
    UNSUPPORTED = "unsupported"
    OFFLINE = "offline"


class BindingState(StrEnum):
    """User-decision state for a discovered/native identity binding."""

    UNMATCHED = "unmatched"
    SUGGESTED = "suggested"
    CONFIRMED = "confirmed"


@dataclass(frozen=True, slots=True)
class NativeDeviceIdentity:
    """Transport-owned identity observed for one Zendure main system.

    Values are intentionally retained only as internal identity data.  UI,
    logs and diagnostics must use the privacy boundary from issue #320.
    """

    transport: ZendureTransport
    device_id: str | None = None
    serial_number: str | None = None
    product_id: str | None = None
    product_model: str | None = None

    def __post_init__(self) -> None:
        if not any((self.device_id, self.serial_number)):
            raise ValueError(
                "A native device identity needs a stable device or serial ID"
            )

    @property
    def key(self) -> str:
        """Return a stable transport-scoped discovery key."""

        stable = self.device_id or self.serial_number
        return f"{self.transport.value}:{stable}"

    def exact_match_keys(self) -> frozenset[tuple[str, str]]:
        """Return only identifiers strong enough for an equality suggestion."""

        keys: set[tuple[str, str]] = set()
        if self.serial_number:
            keys.add(("serial", self.serial_number))
        if self.device_id:
            keys.add((f"device:{self.transport.value}", self.device_id))
        return frozenset(keys)

    def as_dict(self) -> dict[str, str | None]:
        return {
            "transport": self.transport.value,
            "device_id": self.device_id,
            "serial_number": self.serial_number,
            "product_id": self.product_id,
            "product_model": self.product_model,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> NativeDeviceIdentity:
        return cls(
            transport=ZendureTransport(str(value["transport"])),
            device_id=_optional_text(value.get("device_id")),
            serial_number=_optional_text(value.get("serial_number")),
            product_id=_optional_text(value.get("product_id")),
            product_model=_optional_text(value.get("product_model")),
        )


@dataclass(frozen=True, slots=True)
class BatteryPackIdentity:
    """One non-independent battery/extension pack below a main system."""

    pack_id: str
    parent_system_id: str
    serial_number: str | None = None
    product_id: str | None = None
    pack_type: str | None = None
    firmware: str | None = None

    def __post_init__(self) -> None:
        if not self.pack_id or not self.parent_system_id:
            raise ValueError("Pack and parent system IDs must not be empty")

    def as_dict(self) -> dict[str, str | None]:
        return {
            "pack_id": self.pack_id,
            "parent_system_id": self.parent_system_id,
            "serial_number": self.serial_number,
            "product_id": self.product_id,
            "pack_type": self.pack_type,
            "firmware": self.firmware,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> BatteryPackIdentity:
        return cls(
            pack_id=str(value["pack_id"]),
            parent_system_id=str(value["parent_system_id"]),
            serial_number=_optional_text(value.get("serial_number")),
            product_id=_optional_text(value.get("product_id")),
            pack_type=_optional_text(value.get("pack_type")),
            firmware=_optional_text(value.get("firmware")),
        )


@dataclass(frozen=True, slots=True)
class MainDevice:
    """Persistent logical BSFAI system, independent of its current backend."""

    system_id: str
    display_name: str
    model: str | None = None
    profile_key: str | None = None
    control_state: DeviceControlState = DeviceControlState.OBSERVATION
    selected_transport: ZendureTransport = ZendureTransport.HOME_ASSISTANT
    available_transports: frozenset[ZendureTransport] = field(
        default_factory=lambda: frozenset({ZendureTransport.HOME_ASSISTANT})
    )
    native_identities: tuple[NativeDeviceIdentity, ...] = ()
    online: bool = True
    hems_active: bool = False
    supported: bool = True

    def __post_init__(self) -> None:
        if not self.system_id:
            raise ValueError("Logical system ID must not be empty")
        if self.selected_transport not in self.available_transports:
            raise ValueError("Selected transport must be available")
        identity_keys = [identity.key for identity in self.native_identities]
        if len(identity_keys) != len(set(identity_keys)):
            raise ValueError("Native identities must be unique per main system")

    @classmethod
    def from_v4_config_entry(
        cls,
        entry_id: str,
        *,
        display_name: str = "Battery SmartFlow AI",
        model: str | None = None,
        profile_key: str | None = None,
    ) -> MainDevice:
        """Create the stable logical owner for an existing V4 installation."""

        if not entry_id:
            raise ValueError("V4 ConfigEntry ID must not be empty")
        return cls(
            system_id=f"config_entry:{entry_id}",
            display_name=display_name,
            model=model,
            profile_key=profile_key,
            control_state=DeviceControlState.ACTIVE,
        )

    def bind(self, identity: NativeDeviceIdentity) -> MainDevice:
        """Return the same logical system enriched with one native identity."""

        identities = {item.key: item for item in self.native_identities}
        identities[identity.key] = identity
        transports = set(self.available_transports)
        transports.add(identity.transport)
        return replace(
            self,
            native_identities=tuple(identities[key] for key in sorted(identities)),
            available_transports=frozenset(transports),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "system_id": self.system_id,
            "display_name": self.display_name,
            "model": self.model,
            "profile_key": self.profile_key,
            "control_state": self.control_state.value,
            "selected_transport": self.selected_transport.value,
            "available_transports": sorted(
                item.value for item in self.available_transports
            ),
            "native_identities": [item.as_dict() for item in self.native_identities],
            "online": self.online,
            "hems_active": self.hems_active,
            "supported": self.supported,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> MainDevice:
        return cls(
            system_id=str(value["system_id"]),
            display_name=str(value["display_name"]),
            model=_optional_text(value.get("model")),
            profile_key=_optional_text(value.get("profile_key")),
            control_state=DeviceControlState(str(value["control_state"])),
            selected_transport=ZendureTransport(str(value["selected_transport"])),
            available_transports=frozenset(
                ZendureTransport(str(item))
                for item in value.get("available_transports", ())
            ),
            native_identities=tuple(
                NativeDeviceIdentity.from_dict(item)
                for item in value.get("native_identities", ())
            ),
            online=bool(value.get("online", True)),
            hems_active=bool(value.get("hems_active", False)),
            supported=bool(value.get("supported", True)),
        )


@dataclass(frozen=True, slots=True)
class DiscoveryCandidate:
    """Read-only discovery result that is not yet a BSFAI system."""

    identity: NativeDeviceIdentity
    display_name: str
    supported: bool
    pack_count: int = 0

    @property
    def candidate_id(self) -> str:
        return self.identity.key


@dataclass(frozen=True, slots=True)
class DeviceBindingProposal:
    """Explicit migration decision; suggestions never perform a binding."""

    system_id: str
    candidate_id: str
    state: BindingState
    reasons: tuple[str, ...] = ()


class DeviceInventory:
    """Unbounded collection of logical systems, packs and discovery candidates."""

    def __init__(
        self,
        *,
        devices: Iterable[MainDevice] = (),
        packs: Iterable[BatteryPackIdentity] = (),
    ) -> None:
        device_items = tuple(devices)
        pack_items = tuple(packs)
        self._devices = {device.system_id: device for device in device_items}
        self._packs = {pack.pack_id: pack for pack in pack_items}
        if len(self._devices) != len(device_items):
            raise ValueError("Logical system IDs must be unique")
        if len(self._packs) != len(pack_items):
            raise ValueError("Pack IDs must be unique")
        self._candidates: dict[str, DiscoveryCandidate] = {}
        self._validate()

    @property
    def devices(self) -> Mapping[str, MainDevice]:
        return MappingProxyType(self._devices)

    @property
    def packs(self) -> Mapping[str, BatteryPackIdentity]:
        return MappingProxyType(self._packs)

    @property
    def candidates(self) -> Mapping[str, DiscoveryCandidate]:
        return MappingProxyType(self._candidates)

    def discover(self, candidate: DiscoveryCandidate) -> None:
        """Remember a candidate without creating or activating a system."""

        self._candidates[candidate.candidate_id] = candidate

    def suggest_bindings(self, system_id: str) -> tuple[DeviceBindingProposal, ...]:
        """Suggest exact-identity matches while requiring user confirmation."""

        device = self._devices[system_id]
        known_keys = set().union(
            *(identity.exact_match_keys() for identity in device.native_identities)
        ) if device.native_identities else set()
        proposals: list[DeviceBindingProposal] = []
        for candidate in self._candidates.values():
            reasons: list[str] = []
            shared = known_keys & candidate.identity.exact_match_keys()
            if shared:
                reasons.extend(sorted(kind for kind, _ in shared))
            if device.model and candidate.identity.product_model == device.model:
                reasons.append("model")
            state = BindingState.SUGGESTED if shared else BindingState.UNMATCHED
            proposals.append(
                DeviceBindingProposal(
                    system_id=system_id,
                    candidate_id=candidate.candidate_id,
                    state=state,
                    reasons=tuple(reasons),
                )
            )
        return tuple(sorted(proposals, key=lambda item: item.candidate_id))

    def confirm_binding(self, system_id: str, candidate_id: str) -> MainDevice:
        """Attach a candidate only after the caller records explicit consent."""

        candidate = self._candidates[candidate_id]
        for other_id, device in self._devices.items():
            if other_id != system_id and any(
                identity.key == candidate_id for identity in device.native_identities
            ):
                raise ValueError("Native device is already bound to another system")
        bound = self._devices[system_id].bind(candidate.identity)
        self._devices[system_id] = bound
        del self._candidates[candidate_id]
        return bound

    def add_observed_system(
        self,
        candidate_id: str,
        *,
        system_id: str,
    ) -> MainDevice:
        """Create a fresh-install system in observation mode only."""

        if system_id in self._devices:
            raise ValueError("Logical system ID already exists")
        candidate = self._candidates[candidate_id]
        device = MainDevice(
            system_id=system_id,
            display_name=candidate.display_name,
            model=candidate.identity.product_model,
            control_state=(
                DeviceControlState.OBSERVATION
                if candidate.supported
                else DeviceControlState.UNSUPPORTED
            ),
            selected_transport=candidate.identity.transport,
            available_transports=frozenset({candidate.identity.transport}),
            native_identities=(candidate.identity,),
            supported=candidate.supported,
        )
        self._devices[system_id] = device
        del self._candidates[candidate_id]
        return device

    def add_pack(self, pack: BatteryPackIdentity) -> None:
        if pack.parent_system_id not in self._devices:
            raise ValueError("Pack parent system is unknown")
        self._packs[pack.pack_id] = pack

    def reconcile_packs(
        self,
        parent_system_id: str,
        observed: Iterable[BatteryPackIdentity],
    ) -> None:
        """Replace one parent's pack membership from a complete observation."""

        if parent_system_id not in self._devices:
            raise ValueError("Pack parent system is unknown")
        incoming = tuple(observed)
        if any(pack.parent_system_id != parent_system_id for pack in incoming):
            raise ValueError("Observed pack belongs to a different parent system")
        if len({pack.pack_id for pack in incoming}) != len(incoming):
            raise ValueError("Observed pack IDs must be unique")
        retained = {
            pack_id: pack
            for pack_id, pack in self._packs.items()
            if pack.parent_system_id != parent_system_id
        }
        retained.update({pack.pack_id: pack for pack in incoming})
        self._packs = retained

    def set_control_state(
        self,
        system_id: str,
        state: DeviceControlState,
    ) -> MainDevice:
        """Apply a validated management state without implicit failover."""

        device = self._devices[system_id]
        if state in {DeviceControlState.ENABLED, DeviceControlState.ACTIVE}:
            if not device.supported:
                raise ValueError("Unsupported device cannot be enabled")
            if not device.online:
                raise ValueError("Offline device cannot be enabled")
            if device.hems_active:
                raise ValueError("HEMS-blocked device cannot be enabled")
        if state is DeviceControlState.ACTIVE and any(
            other_id != system_id
            and other.control_state is DeviceControlState.ACTIVE
            for other_id, other in self._devices.items()
        ):
            raise ValueError("V5 permits exactly one active main system")
        updated = replace(device, control_state=state)
        self._devices[system_id] = updated
        return updated

    def set_hems_active(self, system_id: str, active: bool) -> MainDevice:
        """Treat Zendure HEMS solely as a control blocker."""

        device = self._devices[system_id]
        if active:
            state = DeviceControlState.HEMS_BLOCKED
        elif not device.supported:
            state = DeviceControlState.UNSUPPORTED
        elif not device.online:
            state = DeviceControlState.OFFLINE
        else:
            state = DeviceControlState.OBSERVATION
        updated = replace(device, hems_active=active, control_state=state)
        self._devices[system_id] = updated
        return updated

    def mark_unavailable(self, system_id: str) -> None:
        """Pause a missing selected system without activating another one."""

        device = self._devices[system_id]
        self._devices[system_id] = replace(
            device,
            online=False,
            control_state=DeviceControlState.OFFLINE,
        )

    def mark_available(self, system_id: str) -> None:
        """Restore observation after fresh data without re-enabling control."""

        device = self._devices[system_id]
        if device.online:
            return
        state = (
            DeviceControlState.HEMS_BLOCKED
            if device.hems_active
            else DeviceControlState.OBSERVATION
            if device.supported
            else DeviceControlState.UNSUPPORTED
        )
        self._devices[system_id] = replace(
            device,
            online=True,
            control_state=state,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "devices": {
                key: self._devices[key].as_dict() for key in sorted(self._devices)
            },
            "packs": {key: self._packs[key].as_dict() for key in sorted(self._packs)},
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> DeviceInventory:
        if int(value.get("schema_version", 0)) != 1:
            raise ValueError("Unsupported device inventory schema")
        return cls(
            devices=(
                MainDevice.from_dict(item)
                for item in value.get("devices", {}).values()
            ),
            packs=(
                BatteryPackIdentity.from_dict(item)
                for item in value.get("packs", {}).values()
            ),
        )

    def _validate(self) -> None:
        active = [
            device for device in self._devices.values()
            if device.control_state is DeviceControlState.ACTIVE
        ]
        if len(active) > 1:
            raise ValueError("V5 permits exactly one active main system")
        for pack in self._packs.values():
            if pack.parent_system_id not in self._devices:
                raise ValueError("Pack parent system is unknown")
        native_keys = [
            identity.key
            for device in self._devices.values()
            for identity in device.native_identities
        ]
        if len(native_keys) != len(set(native_keys)):
            raise ValueError("A native identity cannot belong to multiple systems")


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None
