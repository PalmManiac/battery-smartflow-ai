"""Single native Zendure model/capability authority for V5."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re
from types import MappingProxyType
from typing import Mapping

from .core.models import DeviceProfile, NativeDeviceIdentity, ZendureTransport
from .device_profiles import DEVICE_PROFILE_MODELS


class VerificationLevel(StrEnum):
    """Evidence level; only VERIFIED may later participate in a write gate."""

    VERIFIED = "verified"
    REFERENCE_ONLY = "reference_only"
    UNKNOWN = "unknown"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class TransportCapability:
    transport: ZendureTransport
    read: VerificationLevel
    write: VerificationLevel
    discovery: VerificationLevel
    notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CalibrationCapability:
    raw_status: VerificationLevel
    next_due_from_device: VerificationLevel
    notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ZendureDeviceMatrixEntry:
    """One exact native-model mapping without duplicating profile limits."""

    profile_key: str
    canonical_model: str
    model_aliases: frozenset[str]
    confirmed_product_ids: frozenset[str]
    transports: Mapping[ZendureTransport, TransportCapability]
    readable_main_properties: frozenset[str]
    readable_pack_properties: frozenset[str]
    writable_main_properties: Mapping[str, VerificationLevel]
    writable_main_properties_by_transport: Mapping[
        ZendureTransport, Mapping[str, VerificationLevel]
    ]
    neutral_device_targets: frozenset[str]
    neutral_pack_targets: frozenset[str]
    hems_status: VerificationLevel
    calibration: CalibrationCapability
    native_control_approved: bool = False

    def __post_init__(self) -> None:
        if self.profile_key not in DEVICE_PROFILE_MODELS:
            raise ValueError("Native matrix references an unknown device profile")
        object.__setattr__(self, "transports", MappingProxyType(dict(self.transports)))
        object.__setattr__(
            self,
            "writable_main_properties",
            MappingProxyType(dict(self.writable_main_properties)),
        )
        object.__setattr__(
            self,
            "writable_main_properties_by_transport",
            MappingProxyType(
                {
                    transport: MappingProxyType(dict(properties))
                    for transport, properties in self.writable_main_properties_by_transport.items()
                }
            ),
        )

    @property
    def profile(self) -> DeviceProfile:
        """Use the established profile as the sole hardware-limit authority."""

        return DEVICE_PROFILE_MODELS[self.profile_key]

    def transport(self, value: ZendureTransport) -> TransportCapability:
        return self.transports.get(
            value,
            TransportCapability(
                value,
                VerificationLevel.UNSUPPORTED,
                VerificationLevel.UNSUPPORTED,
                VerificationLevel.UNSUPPORTED,
            ),
        )

    def property_write_level(
        self, transport: ZendureTransport, property_name: str
    ) -> VerificationLevel:
        """Return evidence for one property on one exact transport."""

        return self.writable_main_properties_by_transport.get(transport, {}).get(
            property_name, VerificationLevel.UNSUPPORTED
        )


_COMMON_MAIN_READS = frozenset(
    {
        "electricLevel",
        "outputPackPower",
        "packInputPower",
        "gridInputPower",
        "outputHomePower",
        "solarInputPower",
        "acMode",
        "inputLimit",
        "outputLimit",
        "chargeMaxLimit",
        "inverseMaxPower",
        "minSoc",
        "socSet",
        "smartMode",
        "hemsState",
        "faultLevel",
        "heatState",
        "hyperTmp",
        "BatVolt",
        "masterSoftVersion",
    }
)
_COMMON_PACK_READS = frozenset(
    {
        "packType",
        "softVersion",
        "socLevel",
        "power",
        "totalVol",
        "batcur",
        "minVol",
        "maxVol",
        "maxTemp",
        "state",
        "faultLevel",
        "heatState",
    }
)
_REFERENCE_WRITES = {
    "smartMode": VerificationLevel.REFERENCE_ONLY,
    "acMode": VerificationLevel.REFERENCE_ONLY,
    "inputLimit": VerificationLevel.REFERENCE_ONLY,
    "outputLimit": VerificationLevel.REFERENCE_ONLY,
    "minSoc": VerificationLevel.REFERENCE_ONLY,
    "socSet": VerificationLevel.REFERENCE_ONLY,
}
_COMMON_DEVICE_TARGETS = frozenset(
    {
        "soc_pct",
        "charge_power_w",
        "discharge_power_w",
        "ac_input_power_w",
        "ac_output_power_w",
        "pv_power_w",
        "mode",
        "input_limit_w",
        "output_limit_w",
        "configured_charge_limit_w",
        "configured_discharge_limit_w",
        "min_soc_pct",
        "max_soc_pct",
        "hems_active",
        "fault_code",
        "protection_active",
        "temperature_c",
        "battery_voltage_v",
        "firmware",
    }
)
_COMMON_PACK_TARGETS = frozenset(
    {
        "pack_type",
        "firmware",
        "soc_pct",
        "charge_power_w",
        "discharge_power_w",
        "voltage_v",
        "current_a",
        "cell_min_v",
        "cell_max_v",
        "temperature_c",
        "state_code",
        "fault_code",
        "protection_active",
    }
)


def _normalize_model(value: str) -> str:
    return re.sub(r"[^a-z0-9+]", "", value.casefold())


def _transport_matrix() -> Mapping[ZendureTransport, TransportCapability]:
    """Return evidence for the four initial current-generation models."""

    return {
        ZendureTransport.CLOUD_MQTT: TransportCapability(
            ZendureTransport.CLOUD_MQTT,
            VerificationLevel.VERIFIED,
            VerificationLevel.VERIFIED,
            VerificationLevel.VERIFIED,
            ("Typed properties/write mapping implemented in issue #335",),
        ),
        ZendureTransport.ZENSDK: TransportCapability(
            ZendureTransport.ZENSDK,
            VerificationLevel.REFERENCE_ONLY,
            VerificationLevel.REFERENCE_ONLY,
            VerificationLevel.REFERENCE_ONLY,
            ("Implementation and real-device verification follow in #340-#342",),
        ),
        ZendureTransport.LOCAL_MQTT: TransportCapability(
            ZendureTransport.LOCAL_MQTT,
            VerificationLevel.UNKNOWN,
            VerificationLevel.UNKNOWN,
            VerificationLevel.UNKNOWN,
            ("Do not infer Local MQTT support from Cloud MQTT compatibility",),
        ),
    }


def _entry(
    profile_key: str,
    canonical_model: str,
    *aliases: str,
    product_ids: tuple[str, ...] = (),
) -> ZendureDeviceMatrixEntry:
    first_write_model = profile_key == "SF2400AC"
    transports = dict(_transport_matrix())
    writes = dict(_REFERENCE_WRITES)
    transport_writes = {
        ZendureTransport.CLOUD_MQTT: {
            property_name: VerificationLevel.VERIFIED
            for property_name in writes
        },
        ZendureTransport.ZENSDK: dict(_REFERENCE_WRITES),
        ZendureTransport.LOCAL_MQTT: {
            property_name: VerificationLevel.UNKNOWN for property_name in writes
        },
    }
    if first_write_model:
        transports[ZendureTransport.ZENSDK] = TransportCapability(
            ZendureTransport.ZENSDK,
            VerificationLevel.VERIFIED,
            VerificationLevel.VERIFIED,
            VerificationLevel.REFERENCE_ONLY,
            ("Only explicit reversible outputLimit verification is approved",),
        )
        writes["outputLimit"] = VerificationLevel.VERIFIED
        transport_writes[ZendureTransport.ZENSDK]["outputLimit"] = VerificationLevel.VERIFIED
    return ZendureDeviceMatrixEntry(
        profile_key=profile_key,
        canonical_model=canonical_model,
        model_aliases=frozenset(
            _normalize_model(value) for value in (canonical_model, *aliases)
        ),
        confirmed_product_ids=frozenset(product_ids),
        transports=transports,
        readable_main_properties=_COMMON_MAIN_READS,
        readable_pack_properties=_COMMON_PACK_READS,
        writable_main_properties=writes,
        writable_main_properties_by_transport=transport_writes,
        neutral_device_targets=_COMMON_DEVICE_TARGETS,
        neutral_pack_targets=_COMMON_PACK_TARGETS,
        hems_status=VerificationLevel.REFERENCE_ONLY,
        calibration=CalibrationCapability(
            raw_status=VerificationLevel.REFERENCE_ONLY,
            next_due_from_device=VerificationLevel.UNKNOWN,
            notes=(
                "socStatus/batCalTime require field interpretation",
                "Zendure-HA nextCalibration is derived, not a device due date",
            ),
        ),
        native_control_approved=True,
    )


ZENDURE_DEVICE_MATRIX: Mapping[str, ZendureDeviceMatrixEntry] = MappingProxyType(
    {
        entry.profile_key: entry
        for entry in (
            _entry(
                "SF2400AC",
                "SolarFlow 2400 AC",
                "solarFlow2400AC",
                "SF2400AC",
                product_ids=("BC8B7F",),
            ),
            _entry(
                "SF2400Pro",
                "SolarFlow 2400 Pro",
                "solarFlow2400Pro",
                "SF2400Pro",
            ),
            _entry(
                "SF2400AC+",
                "SolarFlow 2400 AC+",
                "solarFlow2400AC+",
                "SF2400AC+",
            ),
            _entry(
                "SF800Pro",
                "SolarFlow 800 Pro",
                "solarFlow800Pro",
                "SF800Pro",
                product_ids=("R3mn8U",),
            ),
        )
    }
)

_BY_MODEL = {
    alias: entry
    for entry in ZENDURE_DEVICE_MATRIX.values()
    for alias in entry.model_aliases
}
_BY_PRODUCT_ID = {
    product_id: entry
    for entry in ZENDURE_DEVICE_MATRIX.values()
    for product_id in entry.confirmed_product_ids
}


def resolve_zendure_device(
    identity: NativeDeviceIdentity,
) -> ZendureDeviceMatrixEntry | None:
    """Resolve only exact evidence; conflicting identity remains unsupported."""

    by_model = (
        _BY_MODEL.get(_normalize_model(identity.product_model))
        if identity.product_model
        else None
    )
    by_product = (
        _BY_PRODUCT_ID.get(identity.product_id)
        if identity.product_id
        else None
    )
    if by_model is not None and by_product is not None and by_model is not by_product:
        return None
    return by_product or by_model


def preferred_local_transport(
    identity: NativeDeviceIdentity,
) -> ZendureTransport | None:
    """Return the model family's local path without user transport choice."""

    entry = resolve_zendure_device(identity)
    if entry is None:
        return None
    for transport in (ZendureTransport.ZENSDK, ZendureTransport.LOCAL_MQTT):
        capability = entry.transport(transport)
        if capability.read in {
            VerificationLevel.VERIFIED,
            VerificationLevel.REFERENCE_ONLY,
        }:
            return transport
    return None
