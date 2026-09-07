"""Deterministic source selection for native Zendure telemetry."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Generic, Mapping, TypeVar

from .core.models import MeasuredValue, ValueValidity, ZendureTransport


ValueT = TypeVar("ValueT")


class ReadSourceStatus(StrEnum):
    """Quality of one selected property across all observed transports."""

    CONSISTENT = "sources_consistent"
    SINGLE = "single_source"
    FALLBACK = "source_fallback"
    CONFLICT = "source_conflict"
    UNAVAILABLE = "source_unavailable"


@dataclass(frozen=True, slots=True)
class SourceMeasurement(Generic[ValueT]):
    """One normalized value retaining its transport provenance."""

    transport: ZendureTransport
    measurement: MeasuredValue[ValueT]
    retained: bool = False


@dataclass(frozen=True, slots=True)
class SelectedMeasurement(Generic[ValueT]):
    """Deterministic winning value plus a privacy-safe selection trace."""

    measurement: MeasuredValue[ValueT]
    transport: ZendureTransport | None
    status: ReadSourceStatus
    reason: str
    alternatives: tuple[ZendureTransport, ...]


_VALIDITY_RANK = {
    ValueValidity.VALID: 0,
    ValueValidity.STALE: 1,
    ValueValidity.OFFLINE: 2,
    ValueValidity.INVALID: 3,
    ValueValidity.UNAVAILABLE: 4,
    ValueValidity.UNKNOWN: 5,
    ValueValidity.NEVER_RECEIVED: 6,
    ValueValidity.MISSING: 7,
    ValueValidity.UNSUPPORTED: 8,
}


class NativeReadSourceArbiter:
    """Select one value without depending on callback arrival order."""

    def __init__(
        self,
        priorities: Mapping[str, tuple[ZendureTransport, ...]] | None = None,
    ) -> None:
        self._priorities = dict(priorities or {})

    def select(
        self,
        property_name: str,
        candidates: tuple[SourceMeasurement[ValueT], ...],
        *,
        safety_critical: bool = False,
    ) -> SelectedMeasurement[ValueT]:
        """Return a stable property winner with conservative conflict handling."""

        if not candidates:
            return SelectedMeasurement(
                MeasuredValue.absent(ValueValidity.NEVER_RECEIVED),
                None,
                ReadSourceStatus.UNAVAILABLE,
                "no_source_reported_property",
                (),
            )

        priority = self._priorities.get(
            property_name,
            (
                ZendureTransport.ZENSDK,
                ZendureTransport.LOCAL_MQTT,
                ZendureTransport.CLOUD_MQTT,
                ZendureTransport.HOME_ASSISTANT,
            ),
        )
        order = {transport: index for index, transport in enumerate(priority)}
        ranked = sorted(
            candidates,
            key=lambda item: (
                _VALIDITY_RANK.get(item.measurement.validity, 99),
                item.retained,
                order.get(item.transport, len(order)),
                item.transport.value,
            ),
        )
        usable = tuple(item for item in ranked if item.measurement.valid)
        if not usable:
            winner = ranked[0]
            return SelectedMeasurement(
                winner.measurement,
                winner.transport,
                ReadSourceStatus.UNAVAILABLE,
                f"best_available_validity:{winner.measurement.validity.value}",
                tuple(item.transport for item in ranked[1:]),
            )

        fresh = tuple(item for item in usable if not item.retained)
        pool = fresh or usable
        distinct = {_comparable(item.measurement.value) for item in pool}
        if safety_critical and len(distinct) > 1:
            return SelectedMeasurement(
                MeasuredValue.absent(ValueValidity.INVALID),
                None,
                ReadSourceStatus.CONFLICT,
                "fresh_safety_sources_disagree",
                tuple(item.transport for item in pool),
            )

        winner = pool[0]
        if len(pool) == 1:
            status = (
                ReadSourceStatus.FALLBACK
                if len(candidates) > 1
                else ReadSourceStatus.SINGLE
            )
            reason = (
                "preferred_sources_not_usable"
                if status is ReadSourceStatus.FALLBACK
                else "only_valid_source"
            )
        elif len(distinct) == 1:
            status = ReadSourceStatus.CONSISTENT
            reason = "equivalent_sources_priority_selected"
        else:
            status = ReadSourceStatus.FALLBACK
            reason = "noncritical_sources_differ_priority_selected"
        return SelectedMeasurement(
            winner.measurement,
            winner.transport,
            status,
            reason,
            tuple(item.transport for item in pool[1:]),
        )


def _comparable(value: object) -> object:
    """Make common numeric values stable for cross-transport comparisons."""

    if isinstance(value, float):
        return round(value, 6)
    return value
