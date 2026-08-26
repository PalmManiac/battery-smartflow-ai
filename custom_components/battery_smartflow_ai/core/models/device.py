"""Neutral device capability models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class DeviceCapabilities:
    """Capabilities consumed by the core without identifying a manufacturer."""

    max_input_w: float
    max_output_w: float
    supports_passthrough: bool = False
    supports_fast_mode_switch: bool = False
    supports_offgrid_socket: bool = False
    supports_offgrid_input: bool = False
    offgrid_max_internal_supply_w: float = 0.0

    @classmethod
    def from_profile(cls, profile: Mapping[str, Any]) -> DeviceCapabilities:
        """Adapt the existing V4.6 profile mapping without changing its schema."""

        return cls(
            max_input_w=float(profile.get("MAX_INPUT_W", 0.0) or 0.0),
            max_output_w=float(profile.get("MAX_OUTPUT_W", 0.0) or 0.0),
            supports_passthrough=bool(profile.get("SUPPORTS_PASSTHROUGH", False)),
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
        )
