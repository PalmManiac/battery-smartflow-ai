"""Prove that representative core behavior runs without Home Assistant."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CoreWithoutHomeAssistantTests(unittest.TestCase):
    def test_core_imports_and_test_doubles_need_no_home_assistant(self) -> None:
        script = f"import sys; sys.path.insert(0, {str(ROOT)!r})\n" + textwrap.dedent(
            """
            import asyncio
            from datetime import datetime, timedelta, timezone
            import importlib.util
            import sys

            assert importlib.util.find_spec("homeassistant") is None

            from custom_components.battery_smartflow_ai.core.clock import TestClock
            from custom_components.battery_smartflow_ai.core.models import (
                ChargeCommitState,
                DeviceCapabilities,
                DeviceCommand,
                GridHistoryState,
                MarketPrice,
                MarketPriceDirection,
                MarketPriceValidity,
                RegulationRuntimeState,
                RuntimeSnapshot,
                StrategyIntent,
                ValueValidity,
            )
            from custom_components.battery_smartflow_ai.core.testing import (
                FakeDeviceBackend,
                MemoryStateStore,
            )
            from custom_components.battery_smartflow_ai.automatic_strategy import AutomaticStrategy
            from custom_components.battery_smartflow_ai.decision_engine import DecisionEngine
            from custom_components.battery_smartflow_ai.economics import EconomicsEngine
            from custom_components.battery_smartflow_ai.mode_arbiter import ModeArbiter
            from custom_components.battery_smartflow_ai.regulation_power_controller import RegulationPowerController

            assert "homeassistant" not in sys.modules
            now = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)
            clock = TestClock(now)
            clock.advance(timedelta(seconds=30))
            assert clock.utc_now() == now + timedelta(seconds=30)

            snapshot = RuntimeSnapshot(
                now=clock.utc_now(), soc=50.0, soc_min=10.0, soc_max=90.0,
                emergency_soc=5.0, emergency_charge_w=500.0,
                max_charge_w=1000.0, max_discharge_w=800.0,
                grid_import_w=300.0, grid_export_w=0.0,
                pv_w=100.0, house_load_w=400.0,
                avg_charge_price=None, expensive_threshold=0.30,
                very_expensive_threshold=0.40, profit_margin_pct=5.0,
                ai_mode="automatic", manual_action=None, season="summer",
                profile={"MAX_INPUT_W": 1000.0, "MAX_OUTPUT_W": 800.0},
                prev_discharge_w=0.0, prev_charge_w=0.0,
                battery_capacity_kwh=2.0,
            )
            result = DecisionEngine().evaluate(snapshot)
            assert result is not None
            assert snapshot.grid.import_power_w.value == 300.0
            assert AutomaticStrategy() is not None
            assert ChargeCommitState().phase == "waiting"
            assert EconomicsEngine(currency="EUR").currency == "EUR"

            intent = StrategyIntent(
                "cover_deficit", "output", 300.0, "standalone_test"
            )
            arbiter = ModeArbiter().evaluate(
                now=clock.utc_now(), intent=intent,
                grid=GridHistoryState(
                    grid_now_w=300.0, grid_avg_short_w=300.0,
                    stable_import_cycles=3,
                ),
                runtime=RegulationRuntimeState(), current_ac_mode="output",
            )
            power = RegulationPowerController().calculate(
                intent=intent, arbiter=arbiter,
                grid=GridHistoryState(grid_now_w=300.0),
                max_output_w=800.0,
            )
            assert power.final_power_w >= 0.0

            zero_price = MarketPrice(
                direction=MarketPriceDirection.IMPORT, current_price=0.0,
                currency="EUR", unit="EUR/kWh", timestamp=clock.utc_now(),
                source="test", validity=MarketPriceValidity.VALID,
                is_dynamic=True, is_fallback=False,
            )
            assert zero_price.valid and zero_price.current_price == 0.0
            assert ValueValidity.UNAVAILABLE != ValueValidity.VALID

            capabilities = DeviceCapabilities.from_profile(snapshot.profile)
            backend = FakeDeviceBackend(capabilities)
            command = DeviceCommand("output", output_limit_w=300.0, reason="test")
            store = MemoryStateStore()

            async def exercise_ports():
                assert (await store.load()).status.value == "empty"
                assert (await store.save({"day": "2026-08-28"})).saved
                loaded = await store.load()
                loaded.data["day"] = "changed-only-in-copy"
                assert (await store.load()).data["day"] == "2026-08-28"
                execution = await backend.execute(command)
                assert execution.status.value == "applied"
                assert backend.commands == [command]

            asyncio.run(exercise_ports())
            assert "homeassistant" not in sys.modules
            print("CORE_WITHOUT_HOME_ASSISTANT_OK")
            """
        )
        completed = subprocess.run(
            [sys.executable, "-I", "-c", script],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("CORE_WITHOUT_HOME_ASSISTANT_OK", completed.stdout)


if __name__ == "__main__":
    unittest.main()
