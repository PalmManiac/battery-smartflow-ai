"""Build V4.4.0 debug samples from existing coordinator diagnostics."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from .debug_package import DebugSample, redact_secrets


_RAW_VALUE_KEYS = (
    "soc",
    "pv_w",
    "pv_sensor_valid",
    "deficit",
    "surplus",
    "grid_sensor_configured",
    "grid_sensor_valid",
    "house_load",
    "battery_ac_power_raw",
    "battery_ac_power_sensor_valid",
    "battery_charge_w_est",
    "battery_discharge_w_est",
    "max_charge",
    "max_discharge",
    "soc_limit",
    "soc_limits_valid",
    "power_limits_valid",
    "additional_battery_charge_w",
    "additional_battery_discharge_w",
    "additional_battery_discharge_active",
    "offgrid_power_w",
    "offgrid_power_raw_w",
    "offgrid_mode",
    "offgrid_mode_raw",
    "cell_voltage_protection_enabled",
    "configured_lowest_cell_voltage_sensor_count",
    "global_lowest_cell_voltage",
    "cell_voltage_status",
    "cell_voltage_discharge_blocked",
    "cell_voltage_emergency_active",
)

_PRICE_KEYS = (
    "price_now",
    "feed_in_tariff",
    "pv_opportunity_price",
    "avg_charge_price",
    "economic_discharge_threshold",
    "effective_discharge_threshold",
    "current_peak_threshold",
    "current_valley_threshold",
    "charge_price_applied",
    "charge_source",
    "charge_grid_part_w",
    "charge_pv_part_w",
)

_STRATEGY_KEYS = (
    "ai_mode",
    "season_mode",
    "manual_action",
    "decision_action",
    "decision_reason",
    "charge_strategy",
    "strategy_state",
)


def _selected(source: Mapping[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    """Copy only keys that are actually present in the source mapping."""

    return {key: source[key] for key in keys if key in source}


def _prefixed(
    source: Mapping[str, Any],
    prefix: str,
    *,
    exclude_prefixes: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Copy a diagnostic namespace and remove its redundant prefix."""

    return {
        key.removeprefix(prefix): value
        for key, value in source.items()
        if key.startswith(prefix)
        and not any(key.startswith(excluded) for excluded in exclude_prefixes)
    }


def build_entity_diagnostics(
    configured_entities: Mapping[str, str | None] | None,
    entity_availability: Mapping[str, bool | None] | None,
    *,
    compact: bool = False,
) -> dict[str, dict[str, Any]]:
    """Describe configured, optional and unavailable entities explicitly."""

    configured_entities = configured_entities or {}
    entity_availability = entity_availability or {}
    result: dict[str, dict[str, Any]] = {}
    for role, entity_id in configured_entities.items():
        configured = bool(entity_id)
        available = entity_availability.get(role) if configured else None
        if not configured:
            status = "not_configured"
        elif available is True:
            status = "available"
        elif available is False:
            status = "unavailable"
        else:
            status = "unknown"
        diagnostic = {
            "configured": configured,
            "available": available,
            "status": status,
        }
        if not compact:
            diagnostic["entity_id"] = entity_id
        # Configured and available is the normal case and already documented
        # once in config.configured_entities. Per-sample data only needs to
        # retain exceptions and transitions away from that state.
        if not compact or status in {"unavailable", "unknown"}:
            result[str(role)] = diagnostic
    return redact_secrets(result)


def build_debug_sample(
    *,
    timestamp: datetime,
    details: Mapping[str, Any],
    configured_entities: Mapping[str, str | None] | None = None,
    entity_availability: Mapping[str, bool | None] | None = None,
) -> DebugSample:
    """Group existing coordinator diagnostics into one schema-v1 sample.

    Missing values remain missing instead of receiving invented defaults.  This
    preserves the distinction between a measured zero and unavailable data.
    """

    raw_values = _selected(details, _RAW_VALUE_KEYS)
    raw_values["entities"] = build_entity_diagnostics(
        configured_entities,
        entity_availability,
        compact=True,
    )

    strategy = _selected(details, _STRATEGY_KEYS)
    strategy["automatic"] = _prefixed(details, "automatic_")
    strategy["intent"] = _prefixed(details, "regulation_strategy_")
    strategy["charge_source_allocation"] = {
        **_prefixed(details, "charge_source_allocation_"),
        **_selected(
            details,
            (
                "charge_total_target_w",
                "charge_pv_available_w",
                "charge_pv_allocated_w",
                "charge_grid_requested_w",
                "charge_device_input_w",
                "charge_unfilled_w",
                "charge_pv_share_pct",
                "charge_grid_share_pct",
            ),
        ),
    }

    regulation = _prefixed(
        details,
        "regulation_",
        exclude_prefixes=(
            "regulation_command_",
            "regulation_strategy_",
            "regulation_profile_",
        ),
    )

    planning = {
        "learned": _prefixed(details, "learned_planning_"),
        "forecast": _prefixed(details, "forecast_"),
        "charge_commit": _prefixed(details, "charge_commit_"),
    }
    if "pv_outlook" in details:
        planning["forecast"]["pv_outlook"] = details["pv_outlook"]

    command = {
        "requested": _selected(details, ("set_mode", "set_input_w", "set_output_w")),
        "regulation": _prefixed(details, "regulation_command_"),
        "mode_write": _prefixed(details, "mode_write_"),
        "input_write": _prefixed(details, "input_write_"),
        "output_write": _prefixed(details, "output_write_"),
        "effectiveness": _prefixed(details, "command_effectiveness_"),
    }

    return DebugSample(
        timestamp=timestamp,
        strategy=strategy,
        regulation=regulation,
        raw_values=raw_values,
        prices=_selected(details, _PRICE_KEYS),
        planning=planning,
        command=command,
    ).redacted_copy()
