"""Static contracts for the V4.6 economics virtual device and sensors."""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "battery_smartflow_ai"
SENSOR_PATH = COMPONENT / "sensor.py"

MONEY_VALUES = {
    "grid_charge_cost",
    "pv_opportunity_cost",
    "export_revenue",
    "avoided_grid_import_cost",
    "battery_benefit",
}
ENERGY_VALUES = {
    "grid_to_battery_kwh",
    "pv_to_battery_kwh",
    "grid_export_kwh",
    "battery_to_home_kwh",
    "battery_to_grid_kwh",
}
PRICE_KEYS = {
    "economics_average_grid_charge_price",
    "economics_average_pv_opportunity_value",
    "economics_average_export_price",
    "economics_average_battery_discharge_value",
}
EFFICIENCY_KEYS = {"economics_total_economic_efficiency_pct"}
MIGRATED_KEYS = {
    "price_daily_average",
    "current_peak_threshold",
    "current_valley_threshold",
    "economic_discharge_threshold",
    "effective_discharge_threshold",
    "price_now",
    "feed_in_tariff",
    "charge_price_applied",
    "avg_charge_price",
    "profit_eur",
}


def _descriptions() -> dict[str, dict[str, ast.expr]]:
    tree = ast.parse(SENSOR_PATH.read_text(encoding="utf-8"))
    result: dict[str, dict[str, ast.expr]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name):
            continue
        if node.func.id != "ZendureSensorEntityDescription":
            continue
        keywords = {item.arg: item.value for item in node.keywords if item.arg}
        key_node = keywords.get("key")
        if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
            result[key_node.value] = keywords
    return result


def _source(value: ast.expr) -> str:
    return ast.unparse(value)


def test_all_new_economics_sensors_use_the_virtual_device() -> None:
    descriptions = _descriptions()
    expected = {
        *(f"economics_{period}_{value}" for period in ("daily", "total") for value in MONEY_VALUES),
        *(f"economics_{period}_{value}" for period in ("daily", "total") for value in ENERGY_VALUES),
        *PRICE_KEYS,
        *EFFICIENCY_KEYS,
    }

    assert len(expected) == 25
    for key in expected:
        assert key in descriptions
        assert _source(descriptions[key]["economics_device"]) == "True"

    source = SENSOR_PATH.read_text(encoding="utf-8")
    assert 'translation_key="economics_and_prices"' in source
    assert "model=virtual_device_model(coordinator.hass.config.language)" in source
    assert 'via_device=(DOMAIN, entry.entry_id)' in source
    assert 'identifiers={(DOMAIN, f"{entry.entry_id}_economics")}' in source


def test_money_and_energy_statistics_use_safe_state_classes() -> None:
    descriptions = _descriptions()
    for period in ("daily", "total"):
        for value in MONEY_VALUES:
            item = descriptions[f"economics_{period}_{value}"]
            assert _source(item["device_class"]) == "SensorDeviceClass.MONETARY"
            assert _source(item["state_class"]) == "SensorStateClass.TOTAL"
        for value in ENERGY_VALUES:
            item = descriptions[f"economics_{period}_{value}"]
            assert _source(item["device_class"]) == "SensorDeviceClass.ENERGY"
            assert _source(item["state_class"]) == "SensorStateClass.TOTAL_INCREASING"
            assert _source(item["native_unit_of_measurement"]) == (
                "UnitOfEnergy.KILO_WATT_HOUR"
            )

    for key, item in descriptions.items():
        device_class = item.get("device_class")
        if device_class is not None and _source(device_class) == (
            "SensorDeviceClass.MONETARY"
        ):
            assert _source(item["state_class"]) == "SensorStateClass.TOTAL", key

    efficiency = descriptions["economics_total_economic_efficiency_pct"]
    assert _source(efficiency["native_unit_of_measurement"]) == repr("%")
    assert _source(efficiency["state_class"]) == "SensorStateClass.MEASUREMENT"


def test_translated_names_form_alphabetical_groups() -> None:
    expected_prefixes = (
        "Balance today – ",
        "Balance since start – ",
        "Energy today – ",
        "Energy since start – ",
        "Prices – ",
    )
    strings = json.loads((COMPONENT / "strings.json").read_text(encoding="utf-8"))
    sensors = strings["entity"]["sensor"]

    for key in _descriptions():
        if key.startswith("economics_"):
            assert sensors[key]["name"].startswith(expected_prefixes)


def test_coordinator_exposes_flat_runtime_values_for_sensor_readers() -> None:
    source = (COMPONENT / "coordinator.py").read_text(encoding="utf-8")
    assert "economics_runtime_values" in source
    assert 'f"economics_daily_{key}"' in source
    assert 'f"economics_total_{key}"' in source
    for key in PRICE_KEYS:
        assert f'"{key}"' in source


def test_existing_price_entities_migrate_without_changing_unique_ids() -> None:
    descriptions = _descriptions()
    for key in MIGRATED_KEYS:
        assert key in descriptions
        assert _source(descriptions[key]["economics_device"]) == "True"
        assert _source(descriptions[key]["runtime_key"]) == repr(key)

    source = SENSOR_PATH.read_text(encoding="utf-8")
    assert 'f"{DOMAIN}_{entry.entry_id}_{description.key}"' in source
    # The formerly disabled applied-charge-price entity keeps its existing key
    # but is no longer removed as a retired diagnostic entity.
    charge_price = descriptions["charge_price_applied"]
    assert "entity_category" not in charge_price
    assert "entity_registry_enabled_default" not in charge_price


def test_migrated_visible_names_use_economics_group_prefixes() -> None:
    strings = json.loads((COMPONENT / "strings.json").read_text(encoding="utf-8"))
    sensors = strings["entity"]["sensor"]
    prefixes = ("Current – ", "Prices – ", "Balance since start – ")
    for key in MIGRATED_KEYS:
        assert sensors[key]["name"].startswith(prefixes)
