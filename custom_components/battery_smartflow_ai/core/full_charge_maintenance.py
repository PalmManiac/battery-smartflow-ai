"""Transport-neutral full-charge maintenance planning.

This module deliberately does not claim to trigger BMS calibration.  It only
plans and confirms a user-authorized, protective full charge when no verified
native calibration capability exists.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Any, Mapping


DEFAULT_INTERVAL_DAYS = 30
DEFAULT_DUE_SOON_DAYS = 3
DEFAULT_MAX_POSTPONE_DAYS = 7
DEFAULT_FULL_CONFIRM_SECONDS = 300
FULL_SOC_PCT = 100.0
FULL_POWER_THRESHOLD_W = 50.0


class MaintenanceState(StrEnum):
    UNKNOWN = "unknown"
    NOT_DUE = "not_due"
    DUE_SOON = "due_soon"
    DUE = "due"
    WAITING_FOR_FAVORABLE_WINDOW = "waiting_for_favorable_window"
    CHARGING_TO_FULL = "charging_to_full"
    CONFIRMING_FULL = "confirming_full"
    COMPLETED = "completed"
    BLOCKED = "blocked"


class MaintenanceBlockReason(StrEnum):
    NONE = "none"
    NOT_ENABLED = "not_enabled"
    HEMS_ACTIVE = "hems_active"
    DEVICE_NOT_READY = "device_not_ready"
    TRANSPORT_UNAVAILABLE = "transport_unavailable"
    SOC_INVALID_OR_STALE = "soc_invalid_or_stale"
    PROTECTION_ACTIVE = "protection_active"
    PACK_DATA_CONFLICT = "pack_data_conflict"
    MANUAL_MODE = "manual_mode"


class MaintenanceWindow(StrEnum):
    NONE = "none"
    PV_SURPLUS = "pv_surplus"
    LOW_PRICE = "low_price"
    EXISTING_STRATEGIC_CHARGE = "existing_strategic_charge"
    OVERDUE_DEADLINE = "overdue_deadline"


class CalibrationInformationSource(StrEnum):
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"
    VERIFIED_NATIVE = "verified_native"
    BSFAI_DERIVED = "bsfai_derived"


@dataclass(frozen=True, slots=True)
class NativeCalibrationInformation:
    """Calibration information exposed only after semantic verification."""

    source: CalibrationInformationSource = CalibrationInformationSource.UNKNOWN
    status: str | None = None
    last_calibration_at: datetime | None = None
    next_calibration_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.source is not CalibrationInformationSource.VERIFIED_NATIVE and any(
            (self.status, self.last_calibration_at, self.next_calibration_at)
        ):
            raise ValueError("unverified values must not be exposed as native calibration")


@dataclass(frozen=True, slots=True)
class FullChargeMaintenanceRecord:
    """Persistable per-device maintenance state, never a low-level command."""

    device_id: str
    interval_days: int = DEFAULT_INTERVAL_DAYS
    last_confirmed_full_at: datetime | None = None
    last_completed_maintenance_at: datetime | None = None
    active: bool = False
    full_candidate_since: datetime | None = None

    def __post_init__(self) -> None:
        if not self.device_id.strip():
            raise ValueError("device_id is required")
        if self.interval_days < 1:
            raise ValueError("interval_days must be positive")

    @property
    def next_recommended_full_at(self) -> datetime | None:
        if self.last_confirmed_full_at is None:
            return None
        return self.last_confirmed_full_at + timedelta(days=self.interval_days)

    def as_dict(self) -> dict[str, Any]:
        return {
            "device_id": self.device_id,
            "interval_days": self.interval_days,
            "last_confirmed_full_at": _format_time(self.last_confirmed_full_at),
            "last_completed_maintenance_at": _format_time(
                self.last_completed_maintenance_at
            ),
            "active": self.active,
            "full_candidate_since": _format_time(self.full_candidate_since),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> FullChargeMaintenanceRecord:
        return cls(
            device_id=str(value["device_id"]),
            interval_days=int(value.get("interval_days", DEFAULT_INTERVAL_DAYS)),
            last_confirmed_full_at=_parse_time(value.get("last_confirmed_full_at")),
            last_completed_maintenance_at=_parse_time(
                value.get("last_completed_maintenance_at")
            ),
            active=bool(value.get("active", False)),
            full_candidate_since=_parse_time(value.get("full_candidate_since")),
        )


@dataclass(frozen=True, slots=True)
class FullChargeMaintenanceInput:
    now: datetime
    enabled: bool
    soc_pct: float | None
    soc_fresh: bool
    charge_power_w: float | None = None
    device_ready: bool = True
    transport_available: bool = True
    hems_active: bool = False
    protection_active: bool = False
    pack_data_conflict: bool = False
    pv_window_favorable: bool = False
    price_window_favorable: bool = False
    strategic_charge_active: bool = False
    native_full_state_confirmed: bool = False
    automation_allowed: bool = True

    def __post_init__(self) -> None:
        if self.now.tzinfo is None:
            raise ValueError("now must be timezone-aware")


@dataclass(frozen=True, slots=True)
class FullChargeMaintenanceDecision:
    record: FullChargeMaintenanceRecord
    state: MaintenanceState
    block_reason: MaintenanceBlockReason = MaintenanceBlockReason.NONE
    selected_window: MaintenanceWindow = MaintenanceWindow.NONE
    request_full_charge: bool = False
    target_soc_pct: float | None = None
    temporary_user_limit_override: bool = False


class FullChargeMaintenancePlanner:
    """Evaluate one device without transport or Home Assistant dependencies."""

    def __init__(
        self,
        *,
        due_soon_days: int = DEFAULT_DUE_SOON_DAYS,
        max_postpone_days: int = DEFAULT_MAX_POSTPONE_DAYS,
        full_confirm_seconds: int = DEFAULT_FULL_CONFIRM_SECONDS,
    ) -> None:
        if min(due_soon_days, max_postpone_days, full_confirm_seconds) < 0:
            raise ValueError("maintenance timing values must not be negative")
        self._due_soon = timedelta(days=due_soon_days)
        self._max_postpone = timedelta(days=max_postpone_days)
        self._full_confirm = timedelta(seconds=full_confirm_seconds)

    def evaluate(
        self,
        record: FullChargeMaintenanceRecord,
        data: FullChargeMaintenanceInput,
    ) -> FullChargeMaintenanceDecision:
        now = data.now.astimezone(timezone.utc)
        if not data.enabled:
            record = replace(record, active=False)
        next_due = record.next_recommended_full_at
        base_state = _schedule_state(next_due, now, self._due_soon)

        invalid_reason = _block_reason(data)
        if invalid_reason is not MaintenanceBlockReason.NONE:
            return FullChargeMaintenanceDecision(
                replace(record, full_candidate_since=None),
                MaintenanceState.BLOCKED,
                block_reason=invalid_reason,
            )

        at_full = data.soc_pct is not None and data.soc_pct >= FULL_SOC_PCT
        if at_full:
            if (record.full_candidate_since is not None
                and record.last_confirmed_full_at is not None
                and record.last_confirmed_full_at >= record.full_candidate_since):
                return FullChargeMaintenanceDecision(record, base_state)
            candidate_since = record.full_candidate_since or now
            confirming = replace(record, full_candidate_since=candidate_since)
            full_is_plausible = (
                data.native_full_state_confirmed
                or data.charge_power_w is not None
                and abs(data.charge_power_w) <= FULL_POWER_THRESHOLD_W
            )
            if now - candidate_since >= self._full_confirm and full_is_plausible:
                completed = replace(
                    confirming,
                    last_confirmed_full_at=now,
                    last_completed_maintenance_at=now if record.active else (
                        record.last_completed_maintenance_at
                    ),
                    active=False,
                    full_candidate_since=candidate_since,
                )
                return FullChargeMaintenanceDecision(
                    completed, MaintenanceState.COMPLETED
                )
            return FullChargeMaintenanceDecision(
                confirming,
                MaintenanceState.CONFIRMING_FULL,
                selected_window=_select_window(data),
                request_full_charge=record.active and _select_window(data) is not MaintenanceWindow.NONE,
                target_soc_pct=FULL_SOC_PCT if record.active and _select_window(data) is not MaintenanceWindow.NONE else None,
                temporary_user_limit_override=record.active and _select_window(data) is not MaintenanceWindow.NONE,
            )

        record = replace(record, full_candidate_since=None)
        if not record.active and base_state in {MaintenanceState.NOT_DUE, MaintenanceState.DUE_SOON}:
            return FullChargeMaintenanceDecision(record, base_state)
        if not data.enabled:
            return FullChargeMaintenanceDecision(
                record,
                MaintenanceState.BLOCKED,
                block_reason=MaintenanceBlockReason.NOT_ENABLED,
            )
        window = _select_window(data)
        if window is MaintenanceWindow.NONE and next_due is not None:
            if now >= next_due + self._max_postpone:
                window = MaintenanceWindow.OVERDUE_DEADLINE
        if window is MaintenanceWindow.NONE:
            return FullChargeMaintenanceDecision(
                record, MaintenanceState.WAITING_FOR_FAVORABLE_WINDOW
            )
        return _charging_decision(replace(record, active=True), window)


def _charging_decision(
    record: FullChargeMaintenanceRecord, window: MaintenanceWindow
) -> FullChargeMaintenanceDecision:
    return FullChargeMaintenanceDecision(
        record,
        MaintenanceState.CHARGING_TO_FULL,
        selected_window=window,
        request_full_charge=True,
        target_soc_pct=FULL_SOC_PCT,
        temporary_user_limit_override=True,
    )


def _schedule_state(
    next_due: datetime | None, now: datetime, due_soon: timedelta
) -> MaintenanceState:
    if next_due is None:
        return MaintenanceState.DUE
    due = next_due.astimezone(timezone.utc)
    if now >= due:
        return MaintenanceState.DUE
    if now >= due - due_soon:
        return MaintenanceState.DUE_SOON
    return MaintenanceState.NOT_DUE


def _block_reason(data: FullChargeMaintenanceInput) -> MaintenanceBlockReason:
    if not data.automation_allowed:
        return MaintenanceBlockReason.MANUAL_MODE
    if data.hems_active:
        return MaintenanceBlockReason.HEMS_ACTIVE
    if data.protection_active:
        return MaintenanceBlockReason.PROTECTION_ACTIVE
    if data.pack_data_conflict:
        return MaintenanceBlockReason.PACK_DATA_CONFLICT
    if not data.device_ready:
        return MaintenanceBlockReason.DEVICE_NOT_READY
    if not data.transport_available:
        return MaintenanceBlockReason.TRANSPORT_UNAVAILABLE
    if not data.soc_fresh or data.soc_pct is None:
        return MaintenanceBlockReason.SOC_INVALID_OR_STALE
    return MaintenanceBlockReason.NONE


def _select_window(data: FullChargeMaintenanceInput) -> MaintenanceWindow:
    if data.pv_window_favorable:
        return MaintenanceWindow.PV_SURPLUS
    if data.price_window_favorable:
        return MaintenanceWindow.LOW_PRICE
    if data.strategic_charge_active:
        return MaintenanceWindow.EXISTING_STRATEGIC_CHARGE
    return MaintenanceWindow.NONE


def _format_time(value: datetime | None) -> str | None:
    return value.astimezone(timezone.utc).isoformat() if value is not None else None


def _parse_time(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        raise ValueError("persisted maintenance timestamps must be timezone-aware")
    return parsed.astimezone(timezone.utc)
