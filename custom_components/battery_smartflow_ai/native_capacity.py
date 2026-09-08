"""Conservative pack profiles and inventory-derived nominal capacity.

Serial families follow Zendure-HA's battery profiles (device.py).
Unknown families never inherit the main device's or another pack's capacity.
"""

from dataclasses import dataclass

from .core.models import NeutralDeviceState


@dataclass(frozen=True)
class NativeCapacity:
    pack_count: int | None
    capacity_kwh: float | None
    reason: str


def pack_capacity_kwh(serial: str | None, pack_type: str | None) -> float | None:
    if not serial or len(serial) < 4:
        return None
    if serial[0] == "A":
        return 2.4 if serial[3] == "3" else 0.96
    if serial[0] == "B":
        return 8.0 if str(pack_type) == "70" else 0.96
    return {"C": 1.92, "F": 2.88, "G": 2.88, "J": 2.4}.get(serial[0])


def native_capacity(state: NeutralDeviceState | None, expected_count: int | None = None) -> NativeCapacity:
    if state is None or not state.packs:
        return NativeCapacity(expected_count, None, "inventory_pending")
    packs = {pack.pack_id: pack for pack in state.packs}
    if expected_count is not None and expected_count != len(packs):
        return NativeCapacity(expected_count, None, "inventory_incomplete")
    total = 0.0
    for pack in packs.values():
        if not pack.soc_pct.valid:
            return NativeCapacity(len(packs), None, "pack_data_unavailable")
        capacity = pack_capacity_kwh(
            pack.serial_number, pack.pack_type.value if pack.pack_type.valid else None,
        )
        if capacity is None:
            return NativeCapacity(len(packs), None, "unknown_pack_profile")
        total += capacity
    return NativeCapacity(len(packs), round(total, 3), "pack_profiles")
