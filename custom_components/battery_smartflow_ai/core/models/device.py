"""Neutral device capability models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping


CAPABILITY_PROFILE_KEYS = frozenset(
    {
        "MAX_INPUT_W",
        "MAX_OUTPUT_W",
        "SUPPORTS_PASSTHROUGH",
        "PV_HOUSELOAD_PASSTHROUGH",
        "OUTPUT_ZERO_IS_NEUTRAL",
        "INPUT_KEEPALIVE_SAFE",
        "REQUIRES_STABLE_EXPORT_FOR_INPUT",
        "SUPPORTS_FAST_MODE_SWITCH",
        "SUPPORTS_OFFGRID_SOCKET",
        "SUPPORTS_OFFGRID_INPUT",
        "OFFGRID_MAX_INTERNAL_SUPPLY_W",
        "MPPT_CLIPS_WITHOUT_OUTPUT",
    }
)


@dataclass(frozen=True, slots=True)
class DeviceCapabilities:
    """Capabilities consumed by the core without identifying a manufacturer."""

    max_input_w: float
    max_output_w: float
    supports_passthrough: bool = False
    supports_pv_house_load_passthrough: bool = False
    supports_fast_mode_switch: bool = False
    supports_offgrid_socket: bool = False
    supports_offgrid_input: bool = False
    offgrid_max_internal_supply_w: float = 0.0
    output_zero_is_neutral: bool = True
    input_keepalive_safe: bool = True
    requires_stable_export_for_input: bool = False
    mppt_clips_without_output: bool = False
    supports_charge: bool = True
    supports_discharge: bool = True
    supports_ac_charge: bool = True
    supports_power_limits: bool = True

    @classmethod
    def from_profile(cls, profile: Mapping[str, Any]) -> DeviceCapabilities:
        """Adapt the existing V4.6 profile mapping without changing its schema."""

        return cls(
            max_input_w=float(profile.get("MAX_INPUT_W", 0.0) or 0.0),
            max_output_w=float(profile.get("MAX_OUTPUT_W", 0.0) or 0.0),
            supports_passthrough=bool(profile.get("SUPPORTS_PASSTHROUGH", False)),
            supports_pv_house_load_passthrough=bool(
                profile.get(
                    "PV_HOUSELOAD_PASSTHROUGH",
                    profile.get("SUPPORTS_PASSTHROUGH", False),
                )
            ),
            supports_fast_mode_switch=bool(
                profile.get("SUPPORTS_FAST_MODE_SWITCH", False)
            ),
            supports_offgrid_socket=bool(
                profile.get("SUPPORTS_OFFGRID_SOCKET", False)
            ),
            supports_offgrid_input=bool(
                profile.get("SUPPORTS_OFFGRID_INPUT", False)
            ),
            offgrid_max_internal_supply_w=float(
                profile.get("OFFGRID_MAX_INTERNAL_SUPPLY_W", 0.0) or 0.0
            ),
            output_zero_is_neutral=bool(
                profile.get("OUTPUT_ZERO_IS_NEUTRAL", True)
            ),
            input_keepalive_safe=bool(
                profile.get("INPUT_KEEPALIVE_SAFE", True)
            ),
            requires_stable_export_for_input=bool(
                profile.get("REQUIRES_STABLE_EXPORT_FOR_INPUT", False)
            ),
            mppt_clips_without_output=bool(
                profile.get("MPPT_CLIPS_WITHOUT_OUTPUT", False)
            ),
        )

    def as_legacy_mapping(self) -> dict[str, Any]:
        """Return the unchanged V4.6 capability-key representation."""

        return {
            "MAX_INPUT_W": self.max_input_w,
            "MAX_OUTPUT_W": self.max_output_w,
            "SUPPORTS_PASSTHROUGH": self.supports_passthrough,
            "PV_HOUSELOAD_PASSTHROUGH": (
                self.supports_pv_house_load_passthrough
            ),
            "SUPPORTS_FAST_MODE_SWITCH": self.supports_fast_mode_switch,
            "SUPPORTS_OFFGRID_SOCKET": self.supports_offgrid_socket,
            "SUPPORTS_OFFGRID_INPUT": self.supports_offgrid_input,
            "OFFGRID_MAX_INTERNAL_SUPPLY_W": self.offgrid_max_internal_supply_w,
            "OUTPUT_ZERO_IS_NEUTRAL": self.output_zero_is_neutral,
            "INPUT_KEEPALIVE_SAFE": self.input_keepalive_safe,
            "REQUIRES_STABLE_EXPORT_FOR_INPUT": (
                self.requires_stable_export_for_input
            ),
            "MPPT_CLIPS_WITHOUT_OUTPUT": self.mppt_clips_without_output,
        }


@dataclass(frozen=True, slots=True)
class DeviceProfile:
    """Manufacturer-neutral capabilities plus behavior-preserving tuning.

    ``settings`` deliberately retains the established uppercase tuning keys.
    Those keys remain the options/migration contract while capabilities and
    hardware limits have one typed owner for core consumers.
    """

    key: str
    label: str
    capabilities: DeviceCapabilities
    settings: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "settings", MappingProxyType(dict(self.settings)))

    @classmethod
    def from_legacy_mapping(
        cls,
        key: str,
        profile: Mapping[str, Any],
    ) -> DeviceProfile:
        """Split the compatible V4.6 mapping without changing any value."""

        settings = {
            setting_key: value
            for setting_key, value in profile.items()
            if setting_key != "label" and setting_key not in CAPABILITY_PROFILE_KEYS
        }
        return cls(
            key=str(key),
            label=str(profile.get("label", key)),
            capabilities=DeviceCapabilities.from_profile(profile),
            settings=settings,
        )

    def as_legacy_mapping(self) -> dict[str, Any]:
        """Rebuild the exact dictionary shape used by existing integrations."""

        return {
            "label": self.label,
            **dict(self.settings),
            **self.capabilities.as_legacy_mapping(),
        }


class CommandExecutionStatus(StrEnum):
    """Platform-neutral result status of one backend execution attempt."""

    APPLIED = "applied"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class CommandExecutionResult:
    """Neutral feedback from a platform adapter after command execution."""

    status: CommandExecutionStatus
    reason: str
    mode_written: bool = False
    input_written: bool = False
    output_written: bool = False
    error: str | None = None
