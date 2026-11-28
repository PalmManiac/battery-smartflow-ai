"""Narrow, evidence-based cold-protection wakeup for the SF2400Pro."""

from __future__ import annotations

from datetime import datetime
from typing import Any


MAX_DATA_AGE_SECONDS = 30.0
MAX_COLD_PACK_TEMPERATURE_C = 2.0


def cold_wakeup_evidence(state: Any, *, now: datetime) -> bool:
    """Require fresh cold-protection telemetry before changing AC direction."""

    def value(measured: Any) -> Any | None:
        observed = getattr(measured, "observed_at", None)
        if not getattr(measured, "valid", False) or observed is None:
            return None
        age = (now - observed).total_seconds()
        if age < 0 or age > MAX_DATA_AGE_SECONDS:
            return None
        return measured.value

    if value(getattr(state, "protection_active", None)) is not True:
        return False
    if value(getattr(state, "heating_active", None)) is not False:
        return False
    if value(getattr(state, "mode", None)) != "discharge":
        return False
    pv_w = value(getattr(state, "pv_power_w", None))
    if pv_w is None or not 0 <= float(pv_w) <= 5:
        return False
    is_error = value(getattr(state, "diagnostics", {}).get("is_error"))
    if is_error != 1:
        return False
    packs = tuple(getattr(state, "packs", ()) or ())
    temperatures = [value(getattr(pack, "temperature_c", None)) for pack in packs]
    return bool(
        temperatures
        and all(temperature is not None for temperature in temperatures)
        and max(float(temperature) for temperature in temperatures)
        <= MAX_COLD_PACK_TEMPERATURE_C
    )


def cold_wakeup_command(command: Any) -> bool:
    """Only a mode switch with zero AC input and output may bypass protection."""

    return bool(
        command.reason == "cold_protection_wakeup"
        and command.ac_mode == "input"
        and command.input_limit_w == 0
        and command.output_limit_w == 0
        and command.should_write_mode
        and not command.should_write_input
        and not command.should_write_output
        and not command.should_write_min_soc
        and not command.should_write_max_soc
        and not command.should_write_offgrid_mode
    )


def cold_wakeup_stop_command(command: Any) -> bool:
    """A zero-power return to output mode may always stop a wakeup attempt."""

    return bool(
        command.reason == "cold_protection_wakeup_stop"
        and command.ac_mode == "output"
        and command.input_limit_w == 0
        and command.output_limit_w == 0
        and command.should_write_mode
        and not command.should_write_min_soc
        and not command.should_write_max_soc
        and not command.should_write_offgrid_mode
    )
