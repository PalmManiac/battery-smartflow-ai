"""Privacy-safe hierarchical projection for the native device overview."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
from types import MappingProxyType
from typing import Mapping

from .core.models import (
    DeviceControlState,
    DeviceInventory,
    HemsStatus,
    MeasuredValue,
    NeutralDeviceState,
    ValueValidity,
    ZendureTransport,
)


@dataclass(frozen=True, slots=True)
class PackOverview:
    public_id: str
    parent_public_id: str
    pack_model: str | None
    firmware: MeasuredValue[str]
    measurements: Mapping[str, MeasuredValue]
    last_message_at: datetime | None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "measurements", MappingProxyType(dict(self.measurements))
        )


@dataclass(frozen=True, slots=True)
class MainSystemOverview:
    public_id: str
    display_name: str
    model: str | None
    firmware: MeasuredValue[str]
    measurements: Mapping[str, MeasuredValue]
    product_id: str | None
    profile_key: str | None
    control_state: DeviceControlState
    control_enabled: bool
    actively_controlled: bool
    status_text: str
    selected_transport: ZendureTransport
    available_transports: tuple[ZendureTransport, ...]
    online: bool
    hems_active: bool
    hems_status: HemsStatus
    hems_observed_at: datetime | None
    control_block_reason: str | None
    last_message_at: datetime | None
    packs: tuple[PackOverview, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "measurements", MappingProxyType(dict(self.measurements))
        )


def build_native_device_overview(
    inventory: DeviceInventory,
    states: Mapping[str, NeutralDeviceState],
) -> tuple[MainSystemOverview, ...]:
    """Build an unbounded hierarchy without exposing stable source identities."""

    result = []
    for system_id, device in sorted(inventory.devices.items()):
        state = states.get(system_id)
        public_id = _public_id("DEVICE", system_id)
        identity = device.native_identities[0] if device.native_identities else None
        packs = []
        state_packs = {item.pack_id: item for item in state.packs} if state else {}
        for pack_id, pack_identity in sorted(inventory.packs.items()):
            if pack_identity.parent_system_id != system_id:
                continue
            observed = state_packs.get(pack_id)
            if observed is None:
                continue
            packs.append(
                PackOverview(
                    public_id=_public_id("PACK", pack_id),
                    parent_public_id=public_id,
                    pack_model=pack_identity.pack_type,
                    firmware=observed.firmware,
                    measurements=MappingProxyType(
                        {
                            "soc_pct": observed.soc_pct,
                            "charge_power_w": observed.charge_power_w,
                            "discharge_power_w": observed.discharge_power_w,
                            "voltage_v": observed.voltage_v,
                            "current_a": observed.current_a,
                            "cell_min_v": observed.cell_min_v,
                            "cell_max_v": observed.cell_max_v,
                            "temperature_c": observed.temperature_c,
                            "state_code": observed.state_code,
                            "fault_code": observed.fault_code,
                            "protection_active": observed.protection_active,
                        }
                    ),
                    last_message_at=observed.last_message_at,
                )
            )
        result.append(
            MainSystemOverview(
                public_id=public_id,
                display_name=device.display_name,
                model=device.model,
                firmware=_measurement(state, "firmware"),
                measurements=MappingProxyType(
                    {
                        key: _measurement(state, key)
                        for key in (
                            "soc_pct",
                            "charge_power_w",
                            "discharge_power_w",
                            "ac_input_power_w",
                            "ac_output_power_w",
                            "pv_power_w",
                            "mode",
                            "fault_code",
                            "protection_active",
                            "temperature_c",
                            "battery_voltage_v",
                        )
                    }
                    if state
                    else {}
                ),
                product_id=identity.product_id if identity else None,
                profile_key=device.profile_key,
                control_state=device.control_state,
                control_enabled=device.control_state in {
                    DeviceControlState.ENABLED,
                    DeviceControlState.ACTIVE,
                },
                actively_controlled=(
                    device.control_state is DeviceControlState.ACTIVE
                ),
                status_text=_status_text(device.control_state, device.hems_status),
                selected_transport=device.selected_transport,
                available_transports=tuple(
                    sorted(device.available_transports, key=lambda item: item.value)
                ),
                online=device.online,
                hems_active=device.hems_active,
                hems_status=device.hems_status,
                hems_observed_at=device.hems_observed_at,
                control_block_reason=(
                    f"zendure_hems_{device.hems_status.value}"
                    if device.control_state is DeviceControlState.HEMS_BLOCKED
                    else None
                ),
                last_message_at=state.last_message_at if state else None,
                packs=tuple(packs),
            )
        )
    return tuple(result)


def _measurement(state: object | None, key: str) -> MeasuredValue:
    if state is None:
        return MeasuredValue.absent(ValueValidity.MISSING)
    return getattr(state, key, MeasuredValue.absent(ValueValidity.MISSING))


def _public_id(kind: str, value: str) -> str:
    digest = hashlib.sha256(f"bsfai:{kind}:{value}".encode()).hexdigest()[:12]
    return f"ZD_{kind}_{digest}"


def _status_text(state: DeviceControlState, hems_status: HemsStatus) -> str:
    if state is DeviceControlState.HEMS_BLOCKED:
        return {
            HemsStatus.ACTIVE: "Observation mode - Zendure HEMS active",
            HemsStatus.STALE: "Observation mode - Zendure HEMS status stale",
            HemsStatus.INVALID: "Observation mode - Zendure HEMS status invalid",
            HemsStatus.UNKNOWN: "Observation mode - Zendure HEMS status unknown",
        }.get(hems_status, "Observation mode - Zendure HEMS blocks control")
    return {
        DeviceControlState.OBSERVATION: "Observation mode",
        DeviceControlState.ELIGIBLE: "Eligible for control",
        DeviceControlState.ENABLED: "Control enabled",
        DeviceControlState.ACTIVE: "Actively controlled",
        DeviceControlState.UNSUPPORTED: (
            "Observation mode - device profile not supported"
        ),
        DeviceControlState.OFFLINE: "Observation mode - device offline",
    }[state]
