"""Pure mapping from strategy decisions to the visible AI status."""

from __future__ import annotations

from .const import (
    AI_MODE_MANUAL,
    AI_STATUS_CHARGE_SURPLUS,
    AI_STATUS_COVER_DEFICIT,
    AI_STATUS_EMERGENCY_CHARGE,
    AI_STATUS_EXPENSIVE_DISCHARGE,
    AI_STATUS_MANUAL,
    AI_STATUS_PRICE_CHARGE,
    AI_STATUS_STANDBY,
    AI_STATUS_VERY_EXPENSIVE_FORCE,
)


def map_ai_status(ai_mode: str, action: str, reason: str) -> str:
    """Return the translated status key for one strategy decision."""

    if ai_mode == AI_MODE_MANUAL:
        return AI_STATUS_MANUAL
    if action == "passthrough" or reason == "pv_house_load_passthrough":
        return AI_STATUS_STANDBY
    if action == "emergency":
        return AI_STATUS_EMERGENCY_CHARGE
    if action == "charge":
        if reason == "pv_surplus_charge":
            return AI_STATUS_CHARGE_SURPLUS
        if (
            "valley" in reason
            or "planning" in reason
            or "price" in reason
            or reason.startswith("learned_charge_window_")
            or reason == "summer_peak_reserve_charge"
        ):
            return AI_STATUS_PRICE_CHARGE
        return AI_STATUS_CHARGE_SURPLUS
    if action == "discharge":
        if "very_expensive" in reason or "adaptive_peak" in reason:
            return AI_STATUS_VERY_EXPENSIVE_FORCE
        if "price" in reason:
            return AI_STATUS_EXPENSIVE_DISCHARGE
        return AI_STATUS_COVER_DEFICIT
    return AI_STATUS_STANDBY
