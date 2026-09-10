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


@dataclass(frozen=True, slots=True)
class NativePackProfile:
    """One conservatively resolved battery model and nominal capacity."""

    model: str
    capacity_kwh: float
    source: str


def resolve_pack_profile(
    serial: str | None,
    pack_type: str | int | None,
    parent_model: str | None = None,
) -> NativePackProfile | None:
    """Resolve serial evidence first, then field-confirmed pack-type fallback."""

    normalized_serial = str(serial or "").strip().upper()
    normalized_type = str(pack_type).strip() if pack_type is not None else ""
    if len(normalized_serial) >= 4:
        prefix = normalized_serial[0]
        if prefix == "A":
            return NativePackProfile(
                "AIO2400" if normalized_serial[3] == "3" else "AB1000",
                2.4 if normalized_serial[3] == "3" else 0.96,
                "serial",
            )
        if prefix == "B":
            return NativePackProfile(
                "I8000" if normalized_type == "70" else "AB1000S",
                8.0 if normalized_type == "70" else 0.96,
                "serial_and_pack_type" if normalized_type == "70" else "serial",
            )
        if prefix == "C":
            suffix = {"F": "S", "E": "X"}.get(normalized_serial[3], "")
            return NativePackProfile(f"AB2000{suffix}", 1.92, "serial")
        serial_profiles = {
            "F": ("AB3000", 2.88),
            "G": ("AB3000L", 2.88),
            "J": ("I2400", 2.4),
        }
        if prefix in serial_profiles:
            model, capacity = serial_profiles[prefix]
            return NativePackProfile(model, capacity, "serial")

    normalized_parent = "".join(
        character for character in (parent_model or "").casefold()
        if character.isalnum()
    )
    type_profiles = {
        "70": ("I8000", 8.0),
        "250": ("AB1000", 0.96),
        "300": ("AB2000S / AB2000X", 1.92),
        "500": ("I2400", 2.4),
    }
    if normalized_type == "5" and normalized_parent == "solarflow2400ac":
        return NativePackProfile("AB3000X", 2.88, "pack_type_and_parent")
    if normalized_type in type_profiles:
        model, capacity = type_profiles[normalized_type]
        return NativePackProfile(model, capacity, "pack_type")
    return None


def pack_capacity_kwh(serial: str | None, pack_type: str | None) -> float | None:
    profile = resolve_pack_profile(serial, pack_type)
    return profile.capacity_kwh if profile is not None else None


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
