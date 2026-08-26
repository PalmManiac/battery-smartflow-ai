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
    GridState,
    MarketPrice,
    MarketPriceDirection,
    MarketPriceValidity,
    MeasuredValue,
    OffGridState,
    PVState,
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


NOW = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)


class CoreModelTests(unittest.TestCase):
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
