"""Transport-neutral layered limits and explicit native-control blockers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import math

from .states import MeasuredValue, ValueValidity


class PowerDirection(StrEnum):
    """A direction with an independent power-limit calculation."""

    CHARGE = "charge"
    DISCHARGE = "discharge"


class LimitLayer(StrEnum):
    """Semantic owner of a limit value."""

    PROFILE = "profile"
    DEVICE = "device"
    DYNAMIC = "dynamic"
    STRATEGY = "strategy"


class ControlBlocker(StrEnum):
    """Non-numeric reason why a command must not be sent."""

    PROFILE_NOT_APPROVED = "profile_not_approved"
    TRANSPORT_UNAVAILABLE = "transport_unavailable"
    HEMS_ACTIVE = "hems_active"
    HEMS_UNKNOWN = "hems_unknown"
    DEVICE_OFFLINE = "device_offline"
    DEVICE_ONLINE_UNKNOWN = "device_online_unknown"
    PROTECTION_ACTIVE = "protection_active"
    PROTECTION_UNKNOWN = "protection_unknown"
    REQUIRED_LIMIT_UNAVAILABLE = "required_limit_unavailable"


@dataclass(frozen=True, slots=True)
class NamedLimit:
    """One runtime limit whose validity must survive calculation."""

    name: str
    value: MeasuredValue[float]
    required: bool = False


@dataclass(frozen=True, slots=True)
class LimitDiagnostic:
    """One evaluated input for transparent diagnostics."""

    layer: LimitLayer
    name: str
    value_w: float | None
    validity: ValueValidity
    applied: bool


@dataclass(frozen=True, slots=True)
class DirectionLimitRequest:
    """All independent inputs for one power direction."""

    direction: PowerDirection
    profile_limit_w: float
    strategy_target_w: float
    device_limits: tuple[NamedLimit, ...] = ()
    dynamic_limits: tuple[NamedLimit, ...] = ()


@dataclass(frozen=True, slots=True)
class EffectivePowerLimit:
    """Clamped target plus the exact layer which constrained it."""

    direction: PowerDirection
    requested_w: float
    profile_limit_w: float
    effective_limit_w: float
    clamped_target_w: float
    limiting_layer: LimitLayer
    limiting_name: str
    required_limit_unavailable: bool
    diagnostics: tuple[LimitDiagnostic, ...]

    @property
    def clamped(self) -> bool:
        return self.clamped_target_w < self.requested_w


@dataclass(frozen=True, slots=True)
class NativeControlGate:
    """Explicit prerequisites which must never be hidden as zero power."""

    profile_approved: bool
    transport_available: bool
    online: MeasuredValue[bool]
    hems_active: MeasuredValue[bool]
    protection_active: MeasuredValue[bool]


@dataclass(frozen=True, slots=True)
class NativeCommandLimits:
    """Independent charge/discharge limits and command blockers."""

    charge: EffectivePowerLimit
    discharge: EffectivePowerLimit
    blockers: tuple[ControlBlocker, ...]

    @property
    def command_allowed(self) -> bool:
        return not self.blockers


@dataclass(frozen=True, slots=True)
class SocLimitRequest:
    """Separate hard, device, dynamic, and strategy SoC boundaries."""

    profile_min_pct: float
    profile_max_pct: float
    strategy_min_pct: float
    strategy_max_pct: float
    device_min_pct: MeasuredValue[float]
    device_max_pct: MeasuredValue[float]
    dynamic_min_pct: MeasuredValue[float]
    dynamic_max_pct: MeasuredValue[float]


@dataclass(frozen=True, slots=True)
class EffectiveSocLimits:
    """Effective SoC interval without conflating it with power limits."""

    min_pct: float
    max_pct: float
    min_layer: LimitLayer
    max_layer: LimitLayer
    valid: bool


def resolve_power_limit(request: DirectionLimitRequest) -> EffectivePowerLimit:
    """Clamp one direction without treating absent runtime values as zero."""

    _validate_non_negative("profile_limit_w", request.profile_limit_w)
    _validate_non_negative("strategy_target_w", request.strategy_target_w)
    operational_candidates = [
        (request.profile_limit_w, LimitLayer.PROFILE, "hardware_maximum"),
    ]
    diagnostics = [
        LimitDiagnostic(
            layer=LimitLayer.PROFILE,
            name="hardware_maximum",
            value_w=request.profile_limit_w,
            validity=ValueValidity.VALID,
            applied=True,
        )
    ]
    required_unavailable = False
    for layer, limits in (
        (LimitLayer.DEVICE, request.device_limits),
        (LimitLayer.DYNAMIC, request.dynamic_limits),
    ):
        for item in limits:
            applied = item.value.valid
            numeric = float(item.value.value) if applied else None
            if numeric is not None:
                _validate_non_negative(item.name, numeric)
                operational_candidates.append((numeric, layer, item.name))
            elif item.required:
                required_unavailable = True
            diagnostics.append(
                LimitDiagnostic(
                    layer=layer,
                    name=item.name,
                    value_w=numeric,
                    validity=item.value.validity,
                    applied=applied,
                )
            )
    effective, effective_layer, effective_name = min(
        operational_candidates, key=lambda item: item[0]
    )
    if request.strategy_target_w <= effective:
        clamped = request.strategy_target_w
        layer = LimitLayer.STRATEGY
        name = "strategy_target"
    else:
        clamped = effective
        layer = effective_layer
        name = effective_name
    diagnostics.append(
        LimitDiagnostic(
            layer=LimitLayer.STRATEGY,
            name="strategy_target",
            value_w=request.strategy_target_w,
            validity=ValueValidity.VALID,
            applied=True,
        )
    )
    return EffectivePowerLimit(
        direction=request.direction,
        requested_w=request.strategy_target_w,
        profile_limit_w=request.profile_limit_w,
        effective_limit_w=effective,
        clamped_target_w=clamped,
        limiting_layer=layer,
        limiting_name=name,
        required_limit_unavailable=required_unavailable,
        diagnostics=tuple(diagnostics),
    )


def resolve_native_command_limits(
    charge: DirectionLimitRequest,
    discharge: DirectionLimitRequest,
    gate: NativeControlGate,
) -> NativeCommandLimits:
    """Resolve both directions and preserve every hard blocker explicitly."""

    if charge.direction is not PowerDirection.CHARGE:
        raise ValueError("charge request must use the charge direction")
    if discharge.direction is not PowerDirection.DISCHARGE:
        raise ValueError("discharge request must use the discharge direction")
    charge_result = resolve_power_limit(charge)
    discharge_result = resolve_power_limit(discharge)
    blockers: list[ControlBlocker] = []
    if not gate.profile_approved:
        blockers.append(ControlBlocker.PROFILE_NOT_APPROVED)
    if not gate.transport_available:
        blockers.append(ControlBlocker.TRANSPORT_UNAVAILABLE)
    if gate.online.valid:
        if not gate.online.value:
            blockers.append(ControlBlocker.DEVICE_OFFLINE)
    elif gate.online.validity is ValueValidity.OFFLINE:
        blockers.append(ControlBlocker.DEVICE_OFFLINE)
    else:
        blockers.append(ControlBlocker.DEVICE_ONLINE_UNKNOWN)
    _append_boolean_blocker(
        blockers,
        gate.hems_active,
        true=ControlBlocker.HEMS_ACTIVE,
        unknown=ControlBlocker.HEMS_UNKNOWN,
    )
    _append_boolean_blocker(
        blockers,
        gate.protection_active,
        true=ControlBlocker.PROTECTION_ACTIVE,
        unknown=ControlBlocker.PROTECTION_UNKNOWN,
    )
    if (
        charge_result.required_limit_unavailable
        or discharge_result.required_limit_unavailable
    ):
        blockers.append(ControlBlocker.REQUIRED_LIMIT_UNAVAILABLE)
    return NativeCommandLimits(
        charge=charge_result,
        discharge=discharge_result,
        blockers=tuple(blockers),
    )


def resolve_soc_limits(request: SocLimitRequest) -> EffectiveSocLimits:
    """Combine SoC floors with max and ceilings with min semantics."""

    for name, value in (
        ("profile_min_pct", request.profile_min_pct),
        ("profile_max_pct", request.profile_max_pct),
        ("strategy_min_pct", request.strategy_min_pct),
        ("strategy_max_pct", request.strategy_max_pct),
    ):
        _validate_soc(name, value)
    minimums = [
        (request.profile_min_pct, LimitLayer.PROFILE),
        (request.strategy_min_pct, LimitLayer.STRATEGY),
    ]
    maximums = [
        (request.profile_max_pct, LimitLayer.PROFILE),
        (request.strategy_max_pct, LimitLayer.STRATEGY),
    ]
    if request.device_min_pct.valid:
        minimums.append((float(request.device_min_pct.value), LimitLayer.DEVICE))
    if request.device_max_pct.valid:
        maximums.append((float(request.device_max_pct.value), LimitLayer.DEVICE))
    if request.dynamic_min_pct.valid:
        minimums.append((float(request.dynamic_min_pct.value), LimitLayer.DYNAMIC))
    if request.dynamic_max_pct.valid:
        maximums.append((float(request.dynamic_max_pct.value), LimitLayer.DYNAMIC))
    for value, _layer in (*minimums, *maximums):
        _validate_soc("runtime_soc_limit", value)
    minimum, min_layer = max(minimums, key=lambda item: item[0])
    maximum, max_layer = min(maximums, key=lambda item: item[0])
    return EffectiveSocLimits(
        min_pct=minimum,
        max_pct=maximum,
        min_layer=min_layer,
        max_layer=max_layer,
        valid=minimum <= maximum,
    )


def _append_boolean_blocker(
    blockers: list[ControlBlocker],
    measurement: MeasuredValue[bool],
    *,
    true: ControlBlocker | None = None,
    false: ControlBlocker | None = None,
    unknown: ControlBlocker,
) -> None:
    if not measurement.valid:
        blockers.append(unknown)
    elif measurement.value and true is not None:
        blockers.append(true)
    elif not measurement.value and false is not None:
        blockers.append(false)


def _validate_non_negative(name: str, value: float) -> None:
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be finite and non-negative")


def _validate_soc(name: str, value: float) -> None:
    if not math.isfinite(value) or not 0 <= value <= 100:
        raise ValueError(f"{name} must be between 0 and 100")
