"""Transport-neutral native device and battery-pack runtime states."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from .inventory import ZendureTransport
from .states import MeasuredValue


class DeviceOperatingMode(StrEnum):
    """Observed physical direction, independent of a vendor mode number."""

    IDLE = "idle"
    CHARGE = "charge"
    DISCHARGE = "discharge"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ReportedDeviceSetpoints:
    """Mutable device settings reported at runtime, never hardware maxima."""

    input_limit_w: MeasuredValue[float]
    output_limit_w: MeasuredValue[float]
    configured_charge_limit_w: MeasuredValue[float]
    configured_discharge_limit_w: MeasuredValue[float]
    min_soc_pct: MeasuredValue[float]
    max_soc_pct: MeasuredValue[float]


@dataclass(frozen=True, slots=True)
class NeutralPackState:
    """Observed battery pack below one main system; never independently controlled."""

    pack_id: str
    parent_system_id: str
    pack_type: MeasuredValue[str]
    firmware: MeasuredValue[str]
    soc_pct: MeasuredValue[float]
    charge_power_w: MeasuredValue[float]
    discharge_power_w: MeasuredValue[float]
    voltage_v: MeasuredValue[float]
    current_a: MeasuredValue[float]
    cell_min_v: MeasuredValue[float]
    cell_max_v: MeasuredValue[float]
    temperature_c: MeasuredValue[float]
    state_code: MeasuredValue[int]
    fault_code: MeasuredValue[int]
    protection_active: MeasuredValue[bool]
    last_message_at: datetime | None


@dataclass(frozen=True, slots=True)
class NeutralDeviceState:
    """One main system snapshot consumable without Zendure property knowledge."""

    system_id: str
    observed_transport: ZendureTransport
    model: str | None
    firmware: MeasuredValue[str]
    online: MeasuredValue[bool]
    soc_pct: MeasuredValue[float]
    charge_power_w: MeasuredValue[float]
    discharge_power_w: MeasuredValue[float]
    ac_input_power_w: MeasuredValue[float]
    ac_output_power_w: MeasuredValue[float]
    pv_power_w: MeasuredValue[float]
    mode: MeasuredValue[DeviceOperatingMode]
    setpoints: ReportedDeviceSetpoints
    hems_active: MeasuredValue[bool]
    fault_code: MeasuredValue[int]
    protection_active: MeasuredValue[bool]
    temperature_c: MeasuredValue[float]
    battery_voltage_v: MeasuredValue[float]
    last_message_at: datetime | None
    packs: tuple[NeutralPackState, ...]
