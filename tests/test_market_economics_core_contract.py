"""Issue #276 contracts for platform-neutral market and economics code."""

from __future__ import annotations

import ast
from datetime import datetime, timezone
from types import SimpleNamespace
import unittest

from support import PACKAGE_ROOT, bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.core.clock import TestClock  # noqa: E402
from custom_components.battery_smartflow_ai.core.models import (  # noqa: E402
    MarketPrice as CoreMarketPrice,
)
from custom_components.battery_smartflow_ai.economics import (  # noqa: E402
    EconomicPowerFlows,
    EnergyAccumulator,
)
from custom_components.battery_smartflow_ai.market_price import (  # noqa: E402
    MarketPrice as PublicMarketPrice,
    MarketPriceDirection,
    MarketPriceSourceAdapter,
    MarketPriceValidity,
    NumericPriceNormalizer,
)
from custom_components.battery_smartflow_ai.market_price.sources import (  # noqa: E402
    GenericStatePriceSource,
)


class MarketEconomicsCoreContractTests(unittest.TestCase):
    def test_market_and_economics_core_have_no_platform_imports(self) -> None:
        paths = [PACKAGE_ROOT / "economics.py"]
        paths.extend((PACKAGE_ROOT / "market_price").glob("*.py"))
        for path in paths:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            modules = {
                node.module or ""
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom)
            }
            modules.update(
                alias.name
                for node in ast.walk(tree)
                if isinstance(node, ast.Import)
                for alias in node.names
            )
            self.assertFalse(
                any(
                    module == "homeassistant"
                    or module.startswith("homeassistant.")
                    for module in modules
                ),
                str(path),
            )

    def test_public_market_model_is_the_canonical_core_model(self) -> None:
        self.assertIs(PublicMarketPrice, CoreMarketPrice)

    def test_boundary_preserves_zero_negative_and_unavailable(self) -> None:
        now = datetime(2026, 8, 28, 13, 0, tzinfo=timezone.utc)

        def adapt(value: object) -> CoreMarketPrice:
            state = SimpleNamespace(
                state=value,
                attributes={"unit_of_measurement": "EUR/kWh"},
                last_updated=now,
            )
            return MarketPriceSourceAdapter(
                source=GenericStatePriceSource("sensor.price", lambda _: state),
                normalizer=NumericPriceNormalizer(now=now),
                direction=MarketPriceDirection.IMPORT,
                active_currency="EUR",
            ).read()

        self.assertEqual(adapt(0).current_price, 0.0)
        self.assertEqual(adapt(-0.05).current_price, -0.05)
        unavailable = adapt("unavailable")
        self.assertIsNone(unavailable.current_price)
        self.assertIs(unavailable.validity, MarketPriceValidity.UNAVAILABLE)

    def test_energy_time_is_supplied_by_clock_and_state_is_plain_data(self) -> None:
        clock = TestClock(datetime(2026, 8, 28, 13, 0, tzinfo=timezone.utc))
        accumulator = EnergyAccumulator()
        accumulator.add_sample(
            sampled_at=clock.utc_now(),
            power=EconomicPowerFlows(grid_to_battery_w=1000.0),
        )
        state = accumulator.to_state()

        self.assertIsInstance(state, dict)
        self.assertEqual(state["version"], EnergyAccumulator.STATE_VERSION)
        self.assertNotIn("entity_id", state)
        self.assertNotIn("store_path", state)


if __name__ == "__main__":
    unittest.main()
