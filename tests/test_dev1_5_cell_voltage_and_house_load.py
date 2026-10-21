from __future__ import annotations

from types import SimpleNamespace

from custom_components.battery_smartflow_ai.const import (
    CONF_CELL_VOLTAGE_PROTECTION_ENABLED,
    CONF_EXPERT_MODE_ENABLED,
)
from custom_components.battery_smartflow_ai.coordinator import (
    ZendureSmartFlowCoordinator,
    _native_battery_power_totals,
)
from custom_components.battery_smartflow_ai.core.models.states import (
    MeasuredValue,
    ValueValidity,
)


def _device_state(charge: float | None, discharge: float | None):
    def measured(value):
        return (
            MeasuredValue.available(value)
            if value is not None
            else MeasuredValue.absent(ValueValidity.MISSING)
        )

    return SimpleNamespace(
        charge_power_w=measured(charge),
        discharge_power_w=measured(discharge),
    )


def test_native_battery_power_totals_sum_all_systems() -> None:
    states = (
        _device_state(2400.0, 0.0),
        _device_state(2399.0, 0.0),
        _device_state(2399.0, 0.0),
    )

    totals = _native_battery_power_totals(states)
    assert totals is not None
    assert totals == (7198.0, 0.0)
    assert round(max(0.0, 7545.9 + 364.8 + totals[1] - totals[0]), 0) == 713


def test_native_battery_power_totals_require_complete_system_readings() -> None:
    states = (
        _device_state(2400.0, 0.0),
        _device_state(2399.0, 0.0),
        _device_state(None, None),
    )

    assert _native_battery_power_totals(states) is None


def test_read_only_native_cell_voltage_protection_uses_native_pack_values() -> None:
    coordinator = ZendureSmartFlowCoordinator.__new__(ZendureSmartFlowCoordinator)
    cell_voltage = MeasuredValue.available(3.09)
    state = SimpleNamespace(
        packs=(SimpleNamespace(cell_min_v=cell_voltage),)
    )
    coordinator.entry = SimpleNamespace(
        options={
            CONF_EXPERT_MODE_ENABLED: True,
            CONF_CELL_VOLTAGE_PROTECTION_ENABLED: True,
        },
        data={"connection_type": "native"},
    )
    coordinator.entities = SimpleNamespace(lowest_cell_voltage_entities=())
    coordinator.native_zendure = SimpleNamespace(
        control_enabled=False,
        selected_device_state=lambda: state,
    )

    assert coordinator._get_lowest_cell_voltage_values() == [3.09]
