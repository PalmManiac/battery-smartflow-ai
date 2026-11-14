"""V5 legacy Energy settings are copied into V6 EnergyScopes safely."""

from __future__ import annotations

from support import bootstrap

bootstrap()

from custom_components.battery_smartflow_ai.v6_migration import (  # noqa: E402
    migrate_legacy_energy_scope,
)


def test_migrates_legacy_energy_sources_and_preserves_old_values() -> None:
    options = {
        "native_zendure_selected_device": "cloud:device-1",
        "battery_groups": {
            "version": 1,
            "groups": {
                "home": {"name": "Home", "members": ["cloud:device-1"]}
            },
        },
    }
    data = {
        "grid_mode": "single",
        "grid_power_entity": "sensor.grid_power",
        "pv_entity": "sensor.pv_power",
        "pv_forecast_config_entries": ["solcast-home"],
        "installed_pv_wp": 6200,
        "price_now_entity": "sensor.price_now",
        "price_export_entity": "sensor.price_export",
        "additional_battery_charge_entity": "sensor.extra_charge",
    }

    result = migrate_legacy_energy_scope(options=options, data=data)

    scope = result["scopes"]["legacy-default"]
    assert scope["group_ids"] == ["home"]
    assert scope["grid_mode"] == "signed"
    assert scope["grid_power_entities"] == ["sensor.grid_power"]
    assert scope["price_entity"] == "sensor.price_now"
    assert scope["export_price_entity"] == "sensor.price_export"
    assert scope["pv_sources"] == [
        {
            "id": "legacy-pv",
            "name": "PV",
            "mode": "aggregate",
            "power_entities": ["sensor.pv_power"],
            "forecast_entry_ids": ["solcast-home"],
            "installed_power_wp": 6200.0,
        }
    ]
    # Migration is additive so rollback and unsupported legacy roles retain data.
    assert data["grid_power_entity"] == "sensor.grid_power"
    assert data["additional_battery_charge_entity"] == "sensor.extra_charge"


def test_does_not_overwrite_existing_scope_or_guess_a_group() -> None:
    existing = {
        "version": 1,
        "scopes": {
            "configured": {
                "name": "Existing",
                "group_ids": ["home"],
                "grid_mode": "none",
                "pv_sources": [],
            }
        },
    }
    options = {
        "battery_groups": {
            "version": 1,
            "groups": {"home": {"name": "Home", "members": ["cloud:d1"]}},
        },
        "energy_scopes": existing,
        "native_zendure_selected_device": "cloud:d1",
    }
    preserved = migrate_legacy_energy_scope(
        options=options, data={"price_now_entity": "sensor.price"}
    )
    assert "legacy-default" not in preserved["scopes"]
    assert preserved["scopes"]["configured"]["group_ids"] == ["home"]

    assert migrate_legacy_energy_scope(
        options={"native_zendure_selected_device": "cloud:d1"},
        data={"price_now_entity": "sensor.price"},
    ) == {"version": 1, "scopes": {}}
