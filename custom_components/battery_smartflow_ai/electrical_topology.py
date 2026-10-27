"""Persistent physical electrical topology for V6.

This configuration describes wiring and limits only. It is deliberately
independent of battery groups and EnergyScopes and is not consumed by a
productive allocator in this development stage.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

ELECTRICAL_TOPOLOGY_SCHEMA_VERSION = 1
PHASES = {"l1", "l2", "l3", "unknown"}
DOMAIN_KINDS = {"grid", "off_grid"}
OUTPUT_KINDS = {"grid", "off_grid"}


def empty_electrical_topology() -> dict[str, Any]:
    """Return a new empty versioned topology."""

    return {
        "version": ELECTRICAL_TOPOLOGY_SCHEMA_VERSION,
        "circuits": {},
        "load_domains": {},
        "connections": [],
    }


def _records(value: Any, *, label: str) -> Mapping:
    if not isinstance(value, Mapping):
        raise TypeError(f"{label} must be a mapping")
    return value


def _optional_limit(value: Any, *, label: str) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        raise TypeError(f"{label} must be a positive number")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise TypeError(f"{label} must be a positive number") from error
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{label} must be a positive finite number")
    return number


def normalize_electrical_topology(value: Any = None) -> dict[str, Any]:
    """Validate and normalize circuits, load domains and device outputs.

    IDs for disconnected or offline devices are retained. No model-specific
    current or power limit is supplied implicitly.
    """

    if value is None:
        return empty_electrical_topology()
    if not isinstance(value, Mapping):
        raise TypeError("Electrical topology must be a mapping")
    version = value.get("version")
    if version is not None and version != ELECTRICAL_TOPOLOGY_SCHEMA_VERSION:
        raise ValueError(f"Unsupported electrical topology schema version: {version}")

    raw_circuits = _records(value.get("circuits", {}), label="circuits")
    circuits: dict[str, dict[str, Any]] = {}
    for raw_id, raw in raw_circuits.items():
        if not isinstance(raw_id, str) or not raw_id.strip():
            continue
        if not isinstance(raw, Mapping):
            raise TypeError("Each circuit must be a mapping")
        circuit_id = raw_id.strip()
        name = str(raw.get("name") or "").strip()
        phase = str(raw.get("phase", "unknown")).strip().lower()
        if not name:
            raise ValueError("Circuit name is required")
        if phase not in PHASES:
            raise ValueError(f"Unsupported circuit phase: {phase}")
        parent_id = str(raw.get("parent_circuit_id") or "").strip() or None
        circuits[circuit_id] = {
            "name": name,
            "phase": phase,
            "max_current_a": _optional_limit(
                raw.get("max_current_a"), label="max_current_a"
            ),
            "max_power_w": _optional_limit(raw.get("max_power_w"), label="max_power_w"),
            "parent_circuit_id": parent_id,
        }

    for circuit_id, circuit in circuits.items():
        parent_id = circuit["parent_circuit_id"]
        if parent_id is not None and parent_id not in circuits:
            raise ValueError(f"Unknown parent circuit: {parent_id}")
        if parent_id == circuit_id:
            raise ValueError("A circuit cannot be its own upstream circuit")
        seen = {circuit_id}
        ancestor_id = parent_id
        while ancestor_id is not None:
            if ancestor_id in seen:
                raise ValueError("Circuit hierarchy cannot contain a cycle")
            seen.add(ancestor_id)
            ancestor_id = circuits[ancestor_id]["parent_circuit_id"]

    raw_domains = _records(value.get("load_domains", {}), label="load_domains")
    domains: dict[str, dict[str, str]] = {}
    for raw_id, raw in raw_domains.items():
        if not isinstance(raw_id, str) or not raw_id.strip():
            continue
        if not isinstance(raw, Mapping):
            raise TypeError("Each load domain must be a mapping")
        domain_id = raw_id.strip()
        name = str(raw.get("name") or "").strip()
        kind = str(raw.get("kind") or "").strip().lower()
        if not name:
            raise ValueError("Load domain name is required")
        if kind not in DOMAIN_KINDS:
            raise ValueError(f"Unsupported load domain kind: {kind}")
        domains[domain_id] = {"name": name, "kind": kind}

    raw_connections = value.get("connections", ())
    if not isinstance(raw_connections, Sequence) or isinstance(
        raw_connections, (str, bytes)
    ):
        raise TypeError("connections must be a list")
    connections: list[dict[str, Any]] = []
    connection_ids: set[str] = set()
    output_keys: set[tuple[str, str]] = set()
    for raw in raw_connections:
        if not isinstance(raw, Mapping):
            raise TypeError("Each device output connection must be a mapping")
        connection_id = str(raw.get("id") or "").strip()
        device_id = str(raw.get("device_id") or "").strip()
        output_id = str(raw.get("output_id") or "").strip()
        kind = str(raw.get("kind") or "").strip().lower()
        circuit_id = str(raw.get("circuit_id") or "").strip() or None
        load_domain_id = str(raw.get("load_domain_id") or "").strip() or None
        if not connection_id or not device_id or not output_id:
            raise ValueError("Each connection needs an ID, device and output")
        if connection_id in connection_ids:
            raise ValueError("Connection IDs must be unique")
        if kind not in OUTPUT_KINDS:
            raise ValueError(f"Unsupported output kind: {kind}")
        key = (device_id, output_id)
        if key in output_keys:
            raise ValueError("A device output may be connected only once")
        if circuit_id is None:
            raise ValueError("Each device output must be assigned to a circuit")
        if circuit_id not in circuits:
            raise ValueError(f"Unknown circuit: {circuit_id}")
        if load_domain_id is not None and load_domain_id not in domains:
            raise ValueError(f"Unknown load domain: {load_domain_id}")
        if kind == "off_grid":
            if load_domain_id is None or domains[load_domain_id]["kind"] != "off_grid":
                raise ValueError("An off-grid output needs an off-grid load domain")
        elif load_domain_id is not None and domains[load_domain_id]["kind"] != "grid":
            raise ValueError("A grid output can only use a grid load domain")
        connection_ids.add(connection_id)
        output_keys.add(key)
        connections.append(
            {
                "id": connection_id,
                "device_id": device_id,
                "output_id": output_id,
                "kind": kind,
                "circuit_id": circuit_id,
                "load_domain_id": load_domain_id,
            }
        )

    return {
        "version": ELECTRICAL_TOPOLOGY_SCHEMA_VERSION,
        "circuits": circuits,
        "load_domains": domains,
        "connections": connections,
    }


def save_electrical_topology(config: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize a complete topology before it is persisted atomically."""

    return normalize_electrical_topology(config)
