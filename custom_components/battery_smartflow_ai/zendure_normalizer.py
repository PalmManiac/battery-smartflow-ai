"""Map verified Zendure reports into transport-neutral V5 runtime states."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
import math
from typing import Any, Callable, Mapping

from .core.models import (
    DeviceOperatingMode,
    MeasuredValue,
    NeutralDeviceState,
    NeutralPackState,
    ReportedDeviceSetpoints,
    ValueValidity,
    ZendureTransport,
)
from .zendure_cloud import ZendureCloudBootstrap
from .zendure_cloud_mqtt import CloudMqttMessage
from .zendure_device_matrix import resolve_zendure_device
from .zendure_hems_activity import HemsActivityDiagnostic, HemsActivityTracker


DEFAULT_STALE_AFTER_SECONDS = 30.0


class MappingScope(StrEnum):
    MAIN = "main"
    PACK = "pack"


@dataclass(frozen=True, slots=True)
class PropertyMapping:
    """Auditable raw-to-neutral conversion contract."""

    raw_name: str
    target: str
    scope: MappingScope
    raw_types: tuple[type, ...]
    raw_unit: str | None
    target_unit: str | None
    scale: float = 1.0
    sign: str = "positive_magnitude"
    minimum: float | None = None
    maximum: float | None = None
    converter: Callable[[Any], Any] | None = None


def _mode(value: Any) -> DeviceOperatingMode:
    return {
        0: DeviceOperatingMode.IDLE,
        1: DeviceOperatingMode.CHARGE,
        2: DeviceOperatingMode.DISCHARGE,
    }.get(value, DeviceOperatingMode.UNKNOWN)


def _binary(value: Any) -> bool:
    if value in (0, False):
        return False
    if value in (1, True):
        return True
    raise ValueError("not_binary")


def _kelvin_tenths_to_celsius(value: Any) -> float:
    return round(float(value) / 10.0 - 273.15, 2)


def _signed_16_tenths(value: Any) -> float:
    number = int(value)
    if number > 32767:
        number -= 65536
    return number / 10.0


def _mapping(
    raw_name: str,
    target: str,
    scope: MappingScope,
    raw_types: tuple[type, ...],
    raw_unit: str | None = None,
    target_unit: str | None = None,
    **kwargs: Any,
) -> PropertyMapping:
    return PropertyMapping(
        raw_name,
        target,
        scope,
        raw_types,
        raw_unit,
        target_unit,
        **kwargs,
    )


MAIN_PROPERTY_MAPPINGS = {
    item.raw_name: item
    for item in (
        _mapping(
            "electricLevel", "soc_pct", MappingScope.MAIN,
            (int, float), "%", "%", minimum=0, maximum=100,
        ),
        _mapping(
            "outputPackPower", "charge_power_w", MappingScope.MAIN,
            (int, float), "W", "W", minimum=0,
        ),
        _mapping(
            "packInputPower", "discharge_power_w", MappingScope.MAIN,
            (int, float), "W", "W", minimum=0,
        ),
        _mapping(
            "gridInputPower", "ac_input_power_w", MappingScope.MAIN,
            (int, float), "W", "W", minimum=0,
        ),
        _mapping(
            "outputHomePower", "ac_output_power_w", MappingScope.MAIN,
            (int, float), "W", "W", minimum=0,
        ),
        _mapping(
            "solarInputPower", "pv_power_w", MappingScope.MAIN,
            (int, float), "W", "W", minimum=0,
        ),
        _mapping(
            "gridOffPower", "offgrid_power_w", MappingScope.MAIN,
            (int, float), "W", "W", minimum=0,
        ),
        _mapping("acMode", "mode", MappingScope.MAIN, (int,), converter=_mode),
        _mapping(
            "inputLimit", "input_limit_w", MappingScope.MAIN,
            (int, float), "W", "W", minimum=0,
        ),
        _mapping(
            "outputLimit", "output_limit_w", MappingScope.MAIN,
            (int, float), "W", "W", minimum=0,
        ),
        _mapping(
            "chargeMaxLimit", "configured_charge_limit_w", MappingScope.MAIN,
            (int, float), "W", "W", minimum=0,
        ),
        _mapping(
            "inverseMaxPower", "configured_discharge_limit_w",
            MappingScope.MAIN, (int, float), "W", "W", minimum=0,
        ),
        _mapping(
            "minSoc", "min_soc_pct", MappingScope.MAIN,
            (int, float), "0.1 %", "%", scale=0.1, minimum=0, maximum=100,
        ),
        _mapping(
            "socSet", "max_soc_pct", MappingScope.MAIN,
            (int, float), "0.1 %", "%", scale=0.1, minimum=0, maximum=100,
        ),
        _mapping(
            "hemsState", "hems_active", MappingScope.MAIN,
            (bool, int), converter=_binary,
        ),
        _mapping("faultLevel", "fault_code", MappingScope.MAIN, (int,)),
        _mapping(
            "heatState", "protection_active", MappingScope.MAIN,
            (bool, int), converter=_binary,
        ),
        _mapping(
            "hyperTmp", "temperature_c", MappingScope.MAIN,
            (int, float), "0.1 K", "°C",
            converter=_kelvin_tenths_to_celsius,
        ),
        _mapping(
            "BatVolt", "battery_voltage_v", MappingScope.MAIN,
            (int, float), "0.01 V", "V", scale=0.01, minimum=0,
        ),
        _mapping(
            "masterSoftVersion", "firmware", MappingScope.MAIN,
            (str, int), converter=str,
        ),
    )
}


PACK_PROPERTY_MAPPINGS = {
    item.raw_name: item
    for item in (
        _mapping(
            "packType", "pack_type", MappingScope.PACK,
            (str, int), converter=str,
        ),
        _mapping(
            "softVersion", "firmware", MappingScope.PACK,
            (str, int), converter=str,
        ),
        _mapping(
            "socLevel", "soc_pct", MappingScope.PACK,
            (int, float), "%", "%", minimum=0, maximum=100,
        ),
        _mapping(
            "totalVol", "voltage_v", MappingScope.PACK,
            (int, float), "0.01 V", "V", scale=0.01, minimum=0,
        ),
        _mapping(
            "batcur", "current_a", MappingScope.PACK,
            (int,), "0.1 A signed16", "A", sign="signed",
            converter=_signed_16_tenths,
        ),
        _mapping(
            "minVol", "cell_min_v", MappingScope.PACK,
            (int, float), "0.01 V", "V", scale=0.01, minimum=0,
        ),
        _mapping(
            "maxVol", "cell_max_v", MappingScope.PACK,
            (int, float), "0.01 V", "V", scale=0.01, minimum=0,
        ),
        _mapping(
            "maxTemp", "temperature_c", MappingScope.PACK,
            (int, float), "0.1 K", "°C",
            converter=_kelvin_tenths_to_celsius,
        ),
        _mapping("state", "state_code", MappingScope.PACK, (int,)),
        _mapping("faultLevel", "fault_code", MappingScope.PACK, (int,)),
        _mapping(
            "heatState", "protection_active", MappingScope.PACK,
            (bool, int), converter=_binary,
        ),
    )
}


@dataclass(frozen=True, slots=True)
class NormalizationResult:
    state: NeutralDeviceState
    unknown_main_properties: tuple[str, ...]
    unknown_pack_properties: tuple[str, ...]


@dataclass(slots=True)
class _Observed:
    value: Any
    validity: ValueValidity
    observed_at: datetime


@dataclass(slots=True)
class _PackAccumulator:
    values: dict[str, _Observed]
    serial_number: str | None = None
    last_message_at: datetime | None = None


class ZendureCloudNormalizer:
    """Incrementally normalize Cloud reports without strategy decisions."""

    def __init__(
        self,
        bootstrap: ZendureCloudBootstrap,
        *,
        stale_after_seconds: float = DEFAULT_STALE_AFTER_SECONDS,
        supported_device_targets: Mapping[str, frozenset[str]] | None = None,
        supported_pack_targets: Mapping[str, frozenset[str]] | None = None,
    ) -> None:
        if stale_after_seconds <= 0:
            raise ValueError("stale_after_seconds must be positive")
        self._stale_after = stale_after_seconds
        self._models = {
            item.candidate.candidate_id: item.candidate.identity.product_model
            for item in bootstrap.devices
        }
        self._online = {
            item.candidate.candidate_id: item.online
            for item in bootstrap.devices
        }
        self._device_values: dict[str, dict[str, _Observed]] = {
            candidate_id: {} for candidate_id in self._models
        }
        self._pack_values: dict[str, dict[str, _PackAccumulator]] = {
            candidate_id: {} for candidate_id in self._models
        }
        self._last_message: dict[str, datetime | None] = {
            candidate_id: None for candidate_id in self._models
        }
        self._hems_activity = {
            candidate_id: HemsActivityTracker() for candidate_id in self._models
        }
        self._observed_transport: dict[str, ZendureTransport] = {
            candidate_id: ZendureTransport.CLOUD_MQTT
            for candidate_id in self._models
        }
        self._unknown_main = {
            candidate_id: set() for candidate_id in self._models
        }
        self._unknown_pack = {
            candidate_id: set() for candidate_id in self._models
        }
        matrix_device_targets: dict[str, frozenset[str]] = {}
        matrix_pack_targets: dict[str, frozenset[str]] = {}
        for item in bootstrap.devices:
            entry = resolve_zendure_device(item.candidate.identity)
            candidate_id = item.candidate.candidate_id
            matrix_device_targets[candidate_id] = (
                entry.neutral_device_targets if entry is not None else frozenset()
            )
            if entry is not None:
                matrix_pack_targets[candidate_id] = entry.neutral_pack_targets
        self._supported_device_targets = (
            dict(supported_device_targets)
            if supported_device_targets is not None
            else matrix_device_targets
        )
        self._supported_pack_targets = (
            dict(supported_pack_targets)
            if supported_pack_targets is not None
            else matrix_pack_targets
        )

    def apply(
        self,
        message: CloudMqttMessage,
        *,
        now: datetime | None = None,
    ) -> NormalizationResult | None:
        system_id = message.device_candidate_id
        if system_id is None or system_id not in self._models:
            return None
        observed_at = message.received_at
        self._last_message[system_id] = observed_at
        self._observed_transport[system_id] = (
            ZendureTransport.ZENSDK
            if message.transport == "zensdk"
            else (
                ZendureTransport.LOCAL_MQTT
                if message.transport == "local_mqtt"
                else ZendureTransport.CLOUD_MQTT
            )
        )
        payload = message.parsed_payload
        if isinstance(payload, Mapping):
            properties = payload.get("properties")
            if isinstance(properties, Mapping):
                self._apply_properties(
                    self._device_values[system_id],
                    properties,
                    MAIN_PROPERTY_MAPPINGS,
                    self._unknown_main[system_id],
                    observed_at,
                )
            self._apply_packs(system_id, payload.get("packData"), observed_at)
        if message.topic.endswith("/properties/energy"):
            self._hems_activity[system_id].observe_energy(observed_at=observed_at)
        return self.snapshot(system_id, now=now or observed_at)

    def set_hems_monitoring(
        self,
        system_id: str,
        available: bool,
        *,
        observed_at: datetime,
    ) -> None:
        """Tell the tracker whether Cloud MQTT is currently subscribed."""

        if system_id not in self._models:
            raise KeyError(system_id)
        self._hems_activity[system_id].set_monitoring(
            available,
            observed_at=observed_at,
        )

    def hems_diagnostics(
        self,
        system_id: str,
        *,
        now: datetime,
    ) -> HemsActivityDiagnostic:
        if system_id not in self._models:
            raise KeyError(system_id)
        return self._hems_activity[system_id].diagnostics(now=now)

    def set_online(self, system_id: str, online: bool) -> None:
        if system_id not in self._models:
            raise KeyError(system_id)
        self._online[system_id] = online

    def snapshot(
        self,
        system_id: str,
        *,
        now: datetime | None = None,
    ) -> NormalizationResult:
        if system_id not in self._models:
            raise KeyError(system_id)
        current = now or datetime.now(timezone.utc)
        online = self._online[system_id]
        values = self._device_values[system_id]
        supported = self._supported_device_targets.get(system_id, frozenset())

        def device_value(target: str) -> MeasuredValue[Any]:
            return self._value(values, target, supported, online, current)

        direct_hems = device_value("hems_active")
        hems_active = (
            direct_hems
            if direct_hems.validity
            not in {ValueValidity.NEVER_RECEIVED, ValueValidity.MISSING}
            else self._hems_activity[system_id].measurement(now=current)
        )

        packs = tuple(
            self._pack_snapshot(system_id, pack_id, accumulator, current, online)
            for pack_id, accumulator in sorted(
                self._pack_values[system_id].items()
            )
        )
        state = NeutralDeviceState(
            system_id=system_id,
            observed_transport=self._observed_transport[system_id],
            model=self._models[system_id],
            firmware=device_value("firmware"),
            online=MeasuredValue(
                value=online,
                validity=(
                    ValueValidity.UNKNOWN
                    if online is None
                    else ValueValidity.VALID
                ),
                observed_at=self._last_message[system_id],
            ),
            soc_pct=device_value("soc_pct"),
            charge_power_w=device_value("charge_power_w"),
            discharge_power_w=device_value("discharge_power_w"),
            ac_input_power_w=device_value("ac_input_power_w"),
            ac_output_power_w=device_value("ac_output_power_w"),
            pv_power_w=device_value("pv_power_w"),
            mode=device_value("mode"),
            setpoints=ReportedDeviceSetpoints(
                input_limit_w=device_value("input_limit_w"),
                output_limit_w=device_value("output_limit_w"),
                configured_charge_limit_w=device_value(
                    "configured_charge_limit_w"
                ),
                configured_discharge_limit_w=device_value(
                    "configured_discharge_limit_w"
                ),
                min_soc_pct=device_value("min_soc_pct"),
                max_soc_pct=device_value("max_soc_pct"),
            ),
            hems_active=hems_active,
            fault_code=device_value("fault_code"),
            protection_active=device_value("protection_active"),
            temperature_c=device_value("temperature_c"),
            battery_voltage_v=device_value("battery_voltage_v"),
            last_message_at=self._last_message[system_id],
            packs=packs,
            offgrid_power_w=device_value("offgrid_power_w"),
        )
        return NormalizationResult(
            state,
            tuple(sorted(self._unknown_main[system_id])),
            tuple(sorted(self._unknown_pack[system_id])),
        )

    def _apply_properties(
        self,
        destination: dict[str, _Observed],
        properties: Mapping[str, Any],
        mappings: Mapping[str, PropertyMapping],
        unknown: set[str],
        observed_at: datetime,
    ) -> None:
        for raw_name, raw_value in properties.items():
            mapping = mappings.get(str(raw_name))
            if mapping is None:
                unknown.add(str(raw_name))
                continue
            destination[mapping.target] = _normalize(
                mapping, raw_value, observed_at
            )

    def _apply_packs(
        self,
        system_id: str,
        raw_packs: Any,
        observed_at: datetime,
    ) -> None:
        if not isinstance(raw_packs, list):
            return
        for raw_pack in raw_packs:
            if not isinstance(raw_pack, Mapping):
                continue
            pack_id = _pack_id(raw_pack)
            if pack_id is None:
                self._unknown_pack[system_id].add("pack_without_identity")
                continue
            accumulator = self._pack_values[system_id].setdefault(
                pack_id, _PackAccumulator({})
            )
            serial_number = raw_pack.get("sn")
            if isinstance(serial_number, (str, int)) and not isinstance(
                serial_number, bool
            ):
                serial_text = str(serial_number).strip()
                if serial_text:
                    accumulator.serial_number = serial_text
            accumulator.last_message_at = observed_at
            self._apply_properties(
                accumulator.values,
                {
                    key: value
                    for key, value in raw_pack.items()
                    if key not in {"sn", "packId", "packKey", "power"}
                },
                PACK_PROPERTY_MAPPINGS,
                self._unknown_pack[system_id],
                observed_at,
            )
            self._apply_pack_power(accumulator, raw_pack, observed_at)

    def _apply_pack_power(
        self,
        accumulator: _PackAccumulator,
        raw_pack: Mapping[str, Any],
        observed_at: datetime,
    ) -> None:
        power = raw_pack.get("power")
        state = raw_pack.get("state")
        if _is_number(power) and state in (0, 1, 2):
            accumulator.values["charge_power_w"] = _Observed(
                float(power) if state == 1 else 0.0,
                ValueValidity.VALID,
                observed_at,
            )
            accumulator.values["discharge_power_w"] = _Observed(
                float(power) if state == 2 else 0.0,
                ValueValidity.VALID,
                observed_at,
            )
        elif power is not None:
            for target in ("charge_power_w", "discharge_power_w"):
                accumulator.values[target] = _Observed(
                    None, ValueValidity.INVALID, observed_at
                )

    def _pack_snapshot(
        self,
        system_id: str,
        pack_id: str,
        accumulator: _PackAccumulator,
        now: datetime,
        online: bool | None,
    ) -> NeutralPackState:
        supported = self._supported_pack_targets.get(system_id, frozenset())

        def value(target: str) -> MeasuredValue[Any]:
            return self._value(
                accumulator.values, target, supported, online, now
            )

        return NeutralPackState(
            pack_id=pack_id,
            parent_system_id=system_id,
            serial_number=accumulator.serial_number,
            pack_type=value("pack_type"),
            firmware=value("firmware"),
            soc_pct=value("soc_pct"),
            charge_power_w=value("charge_power_w"),
            discharge_power_w=value("discharge_power_w"),
            voltage_v=value("voltage_v"),
            current_a=value("current_a"),
            cell_min_v=value("cell_min_v"),
            cell_max_v=value("cell_max_v"),
            temperature_c=value("temperature_c"),
            state_code=value("state_code"),
            fault_code=value("fault_code"),
            protection_active=value("protection_active"),
            last_message_at=accumulator.last_message_at,
        )

    def _value(
        self,
        values: Mapping[str, _Observed],
        target: str,
        supported: frozenset[str],
        online: bool | None,
        now: datetime,
    ) -> MeasuredValue[Any]:
        if target not in supported:
            return MeasuredValue.absent(ValueValidity.UNSUPPORTED)
        observed = values.get(target)
        if observed is None:
            validity = (
                ValueValidity.OFFLINE
                if online is False
                else ValueValidity.NEVER_RECEIVED
            )
            return MeasuredValue.absent(validity)
        validity = observed.validity
        if online is False:
            validity = ValueValidity.OFFLINE
        elif (
            validity is ValueValidity.VALID
            and (now - observed.observed_at).total_seconds() > self._stale_after
        ):
            validity = ValueValidity.STALE
        return MeasuredValue(observed.value, validity, observed.observed_at)


def _normalize(
    mapping: PropertyMapping,
    raw_value: Any,
    observed_at: datetime,
) -> _Observed:
    if isinstance(raw_value, bool) and bool not in mapping.raw_types:
        return _Observed(None, ValueValidity.INVALID, observed_at)
    if not isinstance(raw_value, mapping.raw_types):
        return _Observed(None, ValueValidity.INVALID, observed_at)
    try:
        if mapping.converter is not None:
            value = mapping.converter(raw_value)
        else:
            value = round(float(raw_value) * mapping.scale, 9)
            if mapping.raw_types == (int,) and mapping.scale == 1:
                value = int(raw_value)
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("non_finite")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if mapping.minimum is not None and value < mapping.minimum:
                raise ValueError("below_range")
            if mapping.maximum is not None and value > mapping.maximum:
                raise ValueError("above_range")
    except (TypeError, ValueError, OverflowError):
        return _Observed(None, ValueValidity.INVALID, observed_at)
    return _Observed(value, ValueValidity.VALID, observed_at)


def _pack_id(raw_pack: Mapping[str, Any]) -> str | None:
    for key in ("sn", "packId", "packKey"):
        value = raw_pack.get(key)
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            text = str(value).strip()
            if text:
                return text
    return None


def _is_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )
