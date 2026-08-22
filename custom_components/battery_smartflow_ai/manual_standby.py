"""One-shot handover helpers for manual standby."""

from __future__ import annotations


def active_power_direction(
    *,
    current_ac_mode: str | None,
    last_ac_mode: str | None,
    current_input_limit_w: float | None,
    current_output_limit_w: float | None,
    last_input_limit_w: float | None,
    last_output_limit_w: float | None,
    measured_charge_w: float = 0.0,
    measured_discharge_w: float = 0.0,
) -> str | None:
    """Return the active side that must be stopped on standby entry.

    Live entity values take precedence over the coordinator cache. Measured
    battery power is a final fallback when a Zendure Number entity has not yet
    refreshed. Merely being in OUTPUT mode is not enough to issue a stop: that
    is the neutral display mode and may legitimately carry 0 W.
    """

    current_mode = str(current_ac_mode or "").lower()
    last_mode = str(last_ac_mode or "").lower()
    current_input = max(0.0, float(current_input_limit_w or 0.0))
    current_output = max(0.0, float(current_output_limit_w or 0.0))
    last_input = max(0.0, float(last_input_limit_w or 0.0))
    last_output = max(0.0, float(last_output_limit_w or 0.0))
    measured_charge = max(0.0, float(measured_charge_w or 0.0))
    measured_discharge = max(0.0, float(measured_discharge_w or 0.0))

    if current_mode == "input":
        return "input"
    if current_mode == "output" and (
        current_output > 0.0 or last_output > 0.0 or measured_discharge > 30.0
    ):
        return "output"
    if current_input > 0.0 or last_input > 0.0 or measured_charge > 30.0:
        return "input"
    if current_output > 0.0 or last_output > 0.0:
        return "output"
    if last_mode == "input":
        return "input"
    if last_mode == "output" and measured_discharge > 30.0:
        return "output"
    return None
