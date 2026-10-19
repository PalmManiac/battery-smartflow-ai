"""Persistent, per-device native setup configuration.

The discovery inventory is live and may be incomplete while a device is
offline.  This small options payload keeps a device's setup choice stable
across discovery runs without implying that discovery activates control.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .core.models import ZendureTransport
from .hardware.zendure.device_matrix import preferred_local_transport

SETUP_SCHEMA_VERSION = 1
SETUP_REQUIRED = "setup_required"
SETUP_COMPLETE = "configured"
SETUP_UNSUPPORTED = "unsupported_read_only"


def reconcile_device_setups(
    discovered: Sequence[Any],
    existing: Any = None,
    *,
    legacy_selected_device: str | None = None,
    legacy_transport: str | None = None,
) -> dict[str, Any]:
    """Merge current discovery metadata with durable per-device choices.

    Devices absent from a discovery response are deliberately retained.  A
    pre-V6 single-device selection is migrated once into the matching record;
    the old selected-device option remains the separate active-control choice.
    """

    records: dict[str, dict[str, Any]] = {}
    raw_records = existing.get("devices") if isinstance(existing, Mapping) else None
    if isinstance(raw_records, Mapping):
        for device_id, raw in raw_records.items():
            if (
                not isinstance(device_id, str)
                or not device_id
                or not isinstance(raw, Mapping)
            ):
                continue
            record = dict(raw)
            transport = record.get("transport")
            if transport not in {item.value for item in ZendureTransport}:
                record.pop("transport", None)
                if record.get("setup_status") == SETUP_COMPLETE:
                    record["setup_status"] = SETUP_REQUIRED
            records[device_id] = record

    for item in discovered:
        candidate = getattr(item, "candidate", None)
        identity = getattr(candidate, "identity", None)
        device_id = getattr(candidate, "candidate_id", None)
        if not isinstance(device_id, str) or not device_id:
            continue
        record = records.setdefault(device_id, {"setup_status": SETUP_REQUIRED})
        supported = bool(getattr(candidate, "supported", False))
        if not supported:
            record["setup_status"] = SETUP_UNSUPPORTED
            record.pop("transport", None)
        elif record.get("setup_status") == SETUP_UNSUPPORTED:
            record["setup_status"] = SETUP_REQUIRED
        record["model"] = getattr(identity, "product_model", None)
        record["pack_count"] = getattr(item, "pack_count", None)
        record["online"] = bool(getattr(item, "online", False))
        local = preferred_local_transport(identity) if supported else None
        transports = (
            {ZendureTransport.CLOUD_MQTT.value}
            if supported
            else set()
        )
        if local is not None:
            transports.add(local.value)
        record["available_transports"] = sorted(transports)
        if (
            record.get("setup_status") == SETUP_COMPLETE
            and record.get("transport") not in record["available_transports"]
        ):
            record["setup_status"] = SETUP_REQUIRED
            record.pop("transport", None)

    if legacy_selected_device and legacy_selected_device in records:
        record = records[legacy_selected_device]
        if record.get("setup_status") == SETUP_REQUIRED:
            try:
                transport = ZendureTransport(str(legacy_transport))
            except (TypeError, ValueError):
                transport = None
            if transport is not None:
                available = record.get("available_transports", ())
                if not available or transport.value in available:
                    record["transport"] = transport.value
                    record["setup_status"] = SETUP_COMPLETE

    return {"version": SETUP_SCHEMA_VERSION, "devices": records}


def save_device_setup(
    setup_map: Mapping[str, Any], device_id: str, transport: str
) -> dict[str, Any]:
    """Return an updated map after validating one discovered device choice."""

    result = reconcile_device_setups((), setup_map)
    records = result["devices"]
    record = records.get(device_id)
    if record is None:
        raise ValueError("native_device_not_discovered")
    if record.get("setup_status") == SETUP_UNSUPPORTED:
        raise ValueError("native_device_unsupported")
    available = record.get("available_transports", ())
    if transport not in available:
        raise ValueError("native_transport_unsupported")
    record["transport"] = transport
    record["setup_status"] = SETUP_COMPLETE
    return result


def setup_is_complete(setup_map: Mapping[str, Any]) -> bool:
    """Whether every supported device known to this map has been handled."""

    devices = setup_map.get("devices", {})
    return isinstance(devices, Mapping) and all(
        isinstance(record, Mapping)
        and record.get("setup_status") in {SETUP_COMPLETE, SETUP_UNSUPPORTED}
        for record in devices.values()
    )
