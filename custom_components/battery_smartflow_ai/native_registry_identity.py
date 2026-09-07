"""Stable Home Assistant registry identities for native Zendure hardware."""

from __future__ import annotations

from .const import DOMAIN


def native_hardware_unique_id(
    entry_id: str,
    kind: str,
    public_id: str,
    entity_key: str,
) -> str:
    """Return the established native entity identity without raw device IDs."""

    if kind not in {"main", "pack"}:
        raise ValueError("unsupported native hardware kind")
    if not all((entry_id, public_id, entity_key)):
        raise ValueError("native registry identity parts must not be empty")
    return f"{DOMAIN}_{entry_id}_native_{kind}_{public_id}_{entity_key}"


def native_main_device_identifier(public_id: str) -> tuple[str, str]:
    if not public_id:
        raise ValueError("public_id must not be empty")
    return DOMAIN, f"native_zendure_{public_id}"


def native_pack_device_identifier(public_id: str) -> tuple[str, str]:
    if not public_id:
        raise ValueError("public_id must not be empty")
    return DOMAIN, f"native_zendure_pack_{public_id}"
