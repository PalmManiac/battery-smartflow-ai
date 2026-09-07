"""Restart-safe runtime ownership for per-device full-charge maintenance."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .core.full_charge_maintenance import (
    FullChargeMaintenanceDecision,
    FullChargeMaintenanceInput,
    FullChargeMaintenancePlanner,
    FullChargeMaintenanceRecord,
    MaintenanceBlockReason,
    MaintenanceState,
    MaintenanceWindow,
)


class FullChargeMaintenanceRuntime:
    """Own maintenance records without owning transports or device commands."""

    def __init__(self, planner: FullChargeMaintenancePlanner | None = None) -> None:
        self._planner = planner or FullChargeMaintenancePlanner()
        self._records: dict[str, FullChargeMaintenanceRecord] = {}
        self._last_decision: FullChargeMaintenanceDecision | None = None

    def restore(self, payload: Mapping[str, Any] | None) -> tuple[str, ...]:
        """Restore valid records independently and report invalid opaque keys."""

        self._records.clear()
        invalid: list[str] = []
        if not isinstance(payload, Mapping):
            return () if payload is None else ("invalid_document",)
        raw_records = payload.get("records", {})
        if not isinstance(raw_records, Mapping):
            return ("invalid_records",)
        for opaque_key, raw in raw_records.items():
            try:
                if not isinstance(raw, Mapping):
                    raise ValueError("record must be a mapping")
                record = FullChargeMaintenanceRecord.from_dict(raw)
                self._records[record.device_id] = record
            except (KeyError, TypeError, ValueError):
                invalid.append(str(opaque_key))
        return tuple(sorted(invalid))

    def evaluate(
        self,
        device_id: str,
        data: FullChargeMaintenanceInput,
        *,
        interval_days: int = 30,
    ) -> FullChargeMaintenanceDecision:
        """Evaluate and retain one selected device only."""

        record = self._records.get(device_id)
        if record is None:
            record = FullChargeMaintenanceRecord(
                device_id=device_id,
                interval_days=interval_days,
            )
        elif record.interval_days != interval_days and not record.active:
            record = FullChargeMaintenanceRecord(
                device_id=record.device_id,
                interval_days=interval_days,
                last_confirmed_full_at=record.last_confirmed_full_at,
                last_completed_maintenance_at=record.last_completed_maintenance_at,
                active=record.active,
                full_candidate_since=record.full_candidate_since,
            )
        decision = self._planner.evaluate(record, data)
        self._records[device_id] = decision.record
        self._last_decision = decision
        return decision

    def persisted_state(self) -> dict[str, Any]:
        """Return detached semantic state without queued commands."""

        return deepcopy({
            "schema_version": 1,
            "records": {
                device_id: record.as_dict()
                for device_id, record in sorted(self._records.items())
            },
        })

    def sensor_data(self) -> dict[str, Any]:
        """Expose the latest selected-device decision without physical identity."""

        decision = self._last_decision
        if decision is None:
            return {
                "full_charge_maintenance_state": MaintenanceState.UNKNOWN.value,
                "full_charge_maintenance_block_reason": (
                    MaintenanceBlockReason.NONE.value
                ),
                "full_charge_maintenance_window": MaintenanceWindow.NONE.value,
                "full_charge_maintenance_last_confirmed": None,
                "full_charge_maintenance_next_recommended": None,
                "full_charge_maintenance_active": False,
            }
        record = decision.record
        return {
            "full_charge_maintenance_state": decision.state.value,
            "full_charge_maintenance_block_reason": decision.block_reason.value,
            "full_charge_maintenance_window": decision.selected_window.value,
            "full_charge_maintenance_last_confirmed": record.last_confirmed_full_at,
            "full_charge_maintenance_next_recommended": (
                record.next_recommended_full_at
            ),
            "full_charge_maintenance_active": record.active,
        }
