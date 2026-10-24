"""Persistent configuration contract for V6 battery groups.

Groups describe ownership only.  They do not enable device control or imply
that members share an electrical circuit or energy measurement scope.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

GROUPS_SCHEMA_VERSION = 1


def empty_group_config() -> dict[str, Any]:
    """Return an empty, versioned group configuration."""

    return {"version": GROUPS_SCHEMA_VERSION, "groups": {}}


def migrate_single_device_group(
    value: Any,
    *,
    setup_map: Any,
    selected_device_id: Any,
) -> dict[str, Any]:
    """Map the pre-groups selected system to one group, once, without discovery.

    This migration is intentionally limited to the already selected and fully
    configured legacy system. Other discovered devices remain ungrouped.
    """

    result = reconcile_group_config(value)
    if (
        result["groups"]
        or (isinstance(value, Mapping) and value.get("version") is not None)
        or not isinstance(selected_device_id, str)
    ):
        return result
    records = setup_map.get("devices") if isinstance(setup_map, Mapping) else None
    record = records.get(selected_device_id) if isinstance(records, Mapping) else None
    if not isinstance(record, Mapping) or record.get("setup_status") != "configured":
        return result
    name = str(record.get("display_name") or record.get("model") or "System").strip()
    result["groups"]["default"] = {"name": name, "members": [selected_device_id]}
    return result


def reconcile_group_config(value: Any = None) -> dict[str, Any]:
    """Normalize stored groups while retaining offline and not-yet-seen IDs.

    Device discovery is allowed to be incomplete.  Membership is therefore
    never pruned merely because a device is missing from the latest scan.
    Invalid group records are ignored, but duplicate ownership is rejected so
    ambiguous configuration cannot silently become active later.
    """

    if isinstance(value, Mapping):
        stored_version = value.get("version")
        if stored_version is not None and stored_version != GROUPS_SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported battery group schema version: {stored_version}"
            )
    raw_groups = value.get("groups") if isinstance(value, Mapping) else None
    if not isinstance(raw_groups, Mapping):
        return empty_group_config()

    groups: dict[str, dict[str, Any]] = {}
    claimed_devices: set[str] = set()
    for raw_group_id, raw_group in raw_groups.items():
        if not isinstance(raw_group_id, str) or not raw_group_id.strip():
            continue
        if not isinstance(raw_group, Mapping):
            continue
        name = str(raw_group.get("name", "")).strip()
        raw_members = raw_group.get("members", ())
        if not name or not isinstance(raw_members, Sequence) or isinstance(
            raw_members, (str, bytes)
        ):
            continue
        members = sorted(
            {
                member.strip()
                for member in raw_members
                if isinstance(member, str) and member.strip()
            }
        )
        duplicates = claimed_devices.intersection(members)
        if duplicates:
            raise ValueError("A device may belong to only one battery group")
        claimed_devices.update(members)
        groups[raw_group_id.strip()] = {"name": name, "members": members}

    return {"version": GROUPS_SCHEMA_VERSION, "groups": groups}


def save_group(
    config: Mapping[str, Any],
    *,
    group_id: str,
    name: str,
    members: Sequence[str],
    move_members: bool = False,
) -> dict[str, Any]:
    """Add or update one group without changing any other membership."""

    normalized_id = str(group_id).strip()
    normalized_name = str(name).strip()
    if not normalized_id or not normalized_name:
        raise ValueError("Battery group ID and name are required")
    if isinstance(members, (str, bytes)):
        raise TypeError("Battery group members must be a sequence of device IDs")
    if any(not isinstance(member, str) for member in members):
        raise TypeError("Battery group members must be device IDs")
    normalized_members = sorted({member.strip() for member in members if member.strip()})

    result = reconcile_group_config(config)
    groups = result["groups"]
    for existing_id, existing in tuple(groups.items()):
        if existing_id == normalized_id:
            continue
        moved = set(existing["members"]).intersection(normalized_members)
        if moved and not move_members:
            raise ValueError("A device may belong to only one battery group")
        if moved:
            groups[existing_id] = {
                **existing,
                "members": sorted(set(existing["members"]) - moved),
            }
    groups[normalized_id] = {"name": normalized_name, "members": normalized_members}
    return result


def remove_group(config: Mapping[str, Any], group_id: str) -> dict[str, Any]:
    """Remove a group while leaving its devices known and ungrouped."""

    result = reconcile_group_config(config)
    result["groups"].pop(str(group_id), None)
    return result
