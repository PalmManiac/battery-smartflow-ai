"""Contracts for the platform-independent V4.7 core models."""

from __future__ import annotations

import ast
from datetime import datetime, timezone
from pathlib import Path
import unittest

from support import PACKAGE_ROOT, bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.core.models import (  # noqa: E402
    AdditionalBatteryState,
    AutomaticStrategyResult,
    BatteryState,
    DeviceCapabilities,
    DeviceCommand,
    DecisionContext,
    GridState,
    MarketPrice,
    MarketPriceDirection,
    MarketPriceValidity,
    MeasuredValue,
    OffGridState,
    PVState,
    RuntimeSnapshot,
    StrategyContext,
    StrategyIntent,
    ValueValidity,
)
from custom_components.battery_smartflow_ai.market_price.models import (  # noqa: E402
    MarketPrice as LegacyMarketPrice,
)
from custom_components.battery_smartflow_ai.regulation_models import (  # noqa: E402
    DeviceCommand as LegacyDeviceCommand,
    StrategyIntent as LegacyStrategyIntent,
)
from custom_components.battery_smartflow_ai.decision_engine import (  # noqa: E402
    DecisionEngine,
)


NOW = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)


class CoreModelTests(unittest.TestCase):
    @staticmethod
    def runtime_snapshot(**overrides: object) -> RuntimeSnapshot:
        values: dict[str, object] = {
            "now": NOW,
            "soc": 50.0,
            "soc_min": 10.0,
            "soc_max": 90.0,
            "emergency_soc": 5.0,
            "emergency_charge_w": 500.0,
            "max_charge_w": 1000.0,
            "max_discharge_w": 800.0,
            "grid_import_w": 100.0,
            "grid_export_w": 0.0,
            "pv_w": 200.0,
            "house_load_w": 300.0,
            "avg_charge_price": None,
            "expensive_threshold": 0.30,
            "very_expensive_threshold": 0.40,
            "profit_margin_pct": 5.0,
            "ai_mode": "automatic",
            "manual_action": None,
            "season": "summer",
            "profile": {"MAX_INPUT_W": 1000.0, "MAX_OUTPUT_W": 800.0},
            "prev_discharge_w": 0.0,
            "prev_charge_w": 0.0,
            "battery_capacity_kwh": 2.0,
        }
        values.update(overrides)
        return RuntimeSnapshot(**values)  # type: ignore[arg-type]

    def test_measurement_keeps_absence_distinct_from_zero(self) -> None:
        zero = MeasuredValue.available(0.0, observed_at=NOW)
        unavailable = MeasuredValue[float].absent(
            ValueValidity.UNAVAILABLE,
            observed_at=NOW,
        )

        self.assertTrue(zero.valid)
        self.assertEqual(zero.value, 0.0)
        self.assertFalse(unavailable.valid)
        self.assertIsNone(unavailable.value)

    def test_absent_measurement_rejects_valid_status(self) -> None:
        with self.assertRaises(ValueError):
            MeasuredValue[float].absent(ValueValidity.VALID)

    def test_central_states_are_constructible_without_ha_objects(self) -> None:
        number = MeasuredValue.available(100.0)
        missing_number = MeasuredValue[float].absent(ValueValidity.MISSING)
        active = MeasuredValue.available(True)

        battery = BatteryState(number, number, missing_number)
        grid = GridState(number, missing_number)
        pv = PVState(number, number)
        offgrid = OffGridState(active, missing_number)
        additional = AdditionalBatteryState(missing_number, missing_number)

        self.assertTrue(battery.soc_pct.valid)
        self.assertEqual(grid.import_power_w.value, 100.0)
        self.assertEqual(pv.house_load_power_w.value, 100.0)
        self.assertTrue(offgrid.active.value)
        self.assertFalse(additional.charge_power_w.valid)

    def test_device_capabilities_adapt_existing_profile_mapping(self) -> None:
        capabilities = DeviceCapabilities.from_profile(
            {
                "label": "vendor-specific display name is adapter data",
                "MAX_INPUT_W": 2400.0,
                "MAX_OUTPUT_W": 800.0,
                "SUPPORTS_PASSTHROUGH": True,
                "SUPPORTS_FAST_MODE_SWITCH": True,
                "SUPPORTS_OFFGRID_SOCKET": False,
            }
        )

        self.assertEqual(capabilities.max_input_w, 2400.0)
        self.assertEqual(capabilities.max_output_w, 800.0)
        self.assertTrue(capabilities.supports_passthrough)
        self.assertFalse(capabilities.supports_offgrid_socket)
        self.assertFalse(hasattr(capabilities, "manufacturer"))

    def test_strategy_and_command_legacy_paths_export_canonical_types(self) -> None:
        self.assertIs(LegacyStrategyIntent, StrategyIntent)
        self.assertIs(LegacyDeviceCommand, DeviceCommand)
        self.assertIs(StrategyContext, AutomaticStrategyResult)

    def test_decision_context_is_the_runtime_snapshot_not_a_second_model(self) -> None:
        self.assertIs(DecisionContext, RuntimeSnapshot)

    def test_decision_engine_evaluates_a_prepared_runtime_snapshot(self) -> None:
        snapshot = self.runtime_snapshot(soc=4.0)

        decision = DecisionEngine().evaluate(snapshot)

        self.assertEqual(decision.action, "emergency")
        self.assertEqual(decision.charge_w, 500.0)

    def test_runtime_snapshot_exposes_typed_states_and_validity(self) -> None:
        snapshot = self.runtime_snapshot(
            grid_sensor_configured=True,
            grid_sensor_valid=False,
            pv_sensor_valid=True,
        )

        self.assertFalse(snapshot.grid.import_power_w.valid)
        self.assertEqual(
            snapshot.grid.import_power_w.validity,
            ValueValidity.INVALID,
        )
        self.assertTrue(snapshot.pv.production_power_w.valid)
        self.assertEqual(snapshot.capabilities.max_output_w, 800.0)
        self.assertFalse(hasattr(snapshot, "entity_id"))

    def test_market_price_legacy_path_exports_canonical_type(self) -> None:
        price = MarketPrice(
            direction=MarketPriceDirection.IMPORT,
            current_price=0.0,
            currency="EUR",
            unit="EUR/kWh",
            timestamp=NOW,
            source="normalized",
            validity=MarketPriceValidity.VALID,
            is_dynamic=True,
            is_fallback=False,
        )

        self.assertIs(LegacyMarketPrice, MarketPrice)
        self.assertTrue(price.valid)
        self.assertEqual(price.current_price, 0.0)

    def test_core_model_files_do_not_import_home_assistant(self) -> None:
        model_root = PACKAGE_ROOT / "core" / "models"
        violations: list[str] = []

        for path in sorted(model_root.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""]
                else:
                    continue
                if any(name == "homeassistant" or name.startswith("homeassistant.") for name in names):
                    violations.append(str(path.relative_to(PACKAGE_ROOT)))

        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
