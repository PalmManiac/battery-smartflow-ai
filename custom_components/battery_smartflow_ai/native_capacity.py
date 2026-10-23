"""Conservative pack profiles and inventory-derived nominal capacity.

Serial families follow Zendure-HA's battery profiles (device.py).
Unknown families never inherit the main device's or another pack's capacity.
"""

from dataclasses import dataclass

from .core.models import NeutralDeviceState
from .hardware.zendure.pack_inventory import normalize_pack_count


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
) -> NativePackProfile | None:
    """Resolve the confirmed type-5 model before serial and other type evidence."""

    normalized_serial = str(serial or "").strip().upper()
    normalized_type = str(pack_type).strip() if pack_type is not None else ""
    # Type 5 identifies AB3000X. Prefer this confirmed telemetry over the older
    # generic F-serial mapping (AB3000), which does not distinguish the X variant.
    if normalized_type == "5":
        return NativePackProfile("AB3000X", 2.88, "pack_type")

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

    type_profiles = {
        "70": ("I8000", 8.0),
        "250": ("AB1000", 0.96),
        "300": ("AB2000S / AB2000X", 1.92),
        "500": ("I2400", 2.4),
    }
    if normalized_type in type_profiles:
        model, capacity = type_profiles[normalized_type]
        return NativePackProfile(model, capacity, "pack_type")
    return None


def pack_capacity_kwh(serial: str | None, pack_type: str | None) -> float | None:
    profile = resolve_pack_profile(serial, pack_type)
    return profile.capacity_kwh if profile is not None else None


def native_capacity(
    state: NeutralDeviceState | None,
    expected_count: int | None = None,
    *,
    require_fresh_pack_soc: bool = True,
) -> NativeCapacity:
    """Calculate capacity from confirmed pack profiles and inventory.

    Control callers may waive per-pack SoC freshness only when they separately
    require a fresh aggregate system SoC. Pack SoC is not needed to identify a
    pack's nominal capacity.
    """
    if state is None:
        return NativeCapacity(expected_count, None, "inventory_pending")
    diagnostics = getattr(state, "diagnostics", {})
    reported_count = diagnostics.get("packNum") if hasattr(diagnostics, "get") else None
    if reported_count is not None and getattr(reported_count, "valid", False):
        count = normalize_pack_count(getattr(reported_count, "value", None))
        if count is not None:
            # A live device report supersedes the count captured at bootstrap;
            # this matters when a pack is added after the initial discovery.
            expected_count = count
    if not state.packs:
        return NativeCapacity(expected_count, None, "inventory_pending")
    packs = {pack.pack_id: pack for pack in state.packs}
    if expected_count is not None and expected_count != len(packs):
        return NativeCapacity(expected_count, None, "inventory_incomplete")
    total = 0.0
    for pack in packs.values():
        if require_fresh_pack_soc and not pack.soc_pct.valid:
            return NativeCapacity(len(packs), None, "pack_data_unavailable")
        capacity = pack_capacity_kwh(
            pack.serial_number, pack.pack_type.value if pack.pack_type.valid else None,
        )
        if capacity is None:
            return NativeCapacity(len(packs), None, "unknown_pack_profile")
        total += capacity
    return NativeCapacity(len(packs), round(total, 3), "pack_profiles")


def native_inventory_capacity(state: NeutralDeviceState | None) -> NativeCapacity:
    """Return only a confirmed nominal pack inventory for presentation.

    Legacy Cloud devices publish pack SoC in sparse groups.  Their previously
    confirmed serial inventory remains useful to display nominal capacity even
    while the next grouped pack report is pending.  This intentionally does
    not replace :func:`native_capacity`, whose fresh SoC requirement remains
    the safety boundary for control calculations.
    """

    if state is None or not state.packs:
        return NativeCapacity(None, None, "inventory_pending")
    total = 0.0
    for pack in state.packs:
        capacity = pack_capacity_kwh(
            pack.serial_number,
            pack.pack_type.value if pack.pack_type.valid else None,
        )
        if capacity is None:
            return NativeCapacity(len(state.packs), None, "unknown_pack_profile")
        total += capacity
    return NativeCapacity(len(state.packs), round(total, 3), "pack_inventory")
