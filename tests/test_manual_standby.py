"""Regression tests for the one-shot manual-standby handover."""

from __future__ import annotations

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.manual_standby import (  # noqa: E402
    active_power_direction,
)


def _direction(**overrides: object) -> str | None:
    values = {
        "current_ac_mode": "output",
        "last_ac_mode": "output",
        "current_input_limit_w": 0.0,
        "current_output_limit_w": 0.0,
        "last_input_limit_w": 0.0,
        "last_output_limit_w": 0.0,
        "measured_charge_w": 0.0,
        "measured_discharge_w": 0.0,
    }
    values.update(overrides)
    return active_power_direction(**values)


def test_standby_stops_live_output_limit_from_issue_254() -> None:
    assert _direction(current_output_limit_w=170.0) == "output"
    assert _direction(current_output_limit_w=600.0) == "output"


def test_standby_stops_cached_or_measured_discharge() -> None:
    assert _direction(last_output_limit_w=167.0) == "output"
    assert _direction(measured_discharge_w=167.0) == "output"


def test_standby_still_stops_active_input_charge() -> None:
    assert _direction(current_ac_mode="input") == "input"
    assert _direction(
        current_ac_mode="unknown",
        last_ac_mode="input",
        last_input_limit_w=700.0,
    ) == "input"


def test_neutral_output_mode_needs_no_stop_command() -> None:
    assert _direction() is None


def test_live_mode_wins_over_stale_opposite_cache() -> None:
    assert _direction(
        current_ac_mode="output",
        current_output_limit_w=600.0,
        last_ac_mode="input",
        last_input_limit_w=700.0,
    ) == "output"
