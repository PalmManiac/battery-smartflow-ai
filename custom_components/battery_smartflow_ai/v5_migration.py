"""Idempotent V4.7-to-V5 migration without native control activation."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping

from .core.models import BindingState, DiscoveryCandidate
from .zendure_device_matrix import resolve_zendure_device

V5_MIGRATION_SCHEMA = 1


class MigrationPhase(StrEnum):
    ZHA_TRANSITION = "zha_transition"
    NATIVE_MATCH_REQUIRED = "native_match_required"
    SHADOW_READY = "shadow_ready"


@dataclass(frozen=True, slots=True)
class V5MigrationState:
    schema_version: int
    phase: MigrationPhase
    legacy_system_id: str
    binding_state: BindingState
    native_candidate_id: str | None
    native_control_enabled: bool
    legacy_zha_enabled: bool

    def __post_init__(self) -> None:
        if self.native_control_enabled:
            raise ValueError("config migration must not activate native control")
        if not self.legacy_zha_enabled:
            raise ValueError("config migration must retain the Z-HA path")

    def as_dict(self) -> Mapping[str, Any]:
        return MappingProxyType({
            "schema_version": self.schema_version,
            "phase": self.phase.value,
            "legacy_system_id": self.legacy_system_id,
            "binding_state": self.binding_state.value,
            "native_candidate_id": self.native_candidate_id,
            "native_control_enabled": self.native_control_enabled,
            "legacy_zha_enabled": self.legacy_zha_enabled,
        })


def initial_v5_migration_state(entry_id: str) -> V5MigrationState:
    if not entry_id:
        raise ValueError("entry_id is required")
    return V5MigrationState(
        V5_MIGRATION_SCHEMA,
        MigrationPhase.ZHA_TRANSITION,
        f"config_entry:{entry_id}",
        BindingState.UNMATCHED,
        None,
        False,
        True,
    )


def match_v4_device(
    *, legacy_profile: str | None,
    candidates: tuple[DiscoveryCandidate, ...],
) -> tuple[DiscoveryCandidate, ...]:
    """Return candidates for confirmation; never match names or order."""

    if legacy_profile is None:
        return ()
    return tuple(
        candidate for candidate in candidates
        if candidate.supported
        and (entry := resolve_zendure_device(candidate.identity)) is not None
        and entry.profile_key == legacy_profile
    )


def migrate_persisted_v47_state(
    state: Mapping[str, Any], *, legacy_system_id: str,
) -> dict[str, Any]:
    """Preserve the flat V4 document and add restart-safe ownership metadata."""

    migrated = deepcopy(dict(state))
    migrated.setdefault("v5_migration_schema", V5_MIGRATION_SCHEMA)
    migrated.setdefault("v5_legacy_system_id", legacy_system_id)
    migrated["v5_native_control_enabled"] = False
    migrated.setdefault("v5_native_candidate_id", None)
    migrated.setdefault("v5_binding_state", BindingState.UNMATCHED.value)
    migrated["v5_legacy_zha_enabled"] = True
    migrated.setdefault("v5_economics_owner", legacy_system_id)
    if migrated.get("charge_commit_active"):
        migrated.setdefault("v5_charge_commit_owner", legacy_system_id)
    return migrated
