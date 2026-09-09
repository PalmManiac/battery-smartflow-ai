"""Tests for Home Assistant Energy solar forecast normalization."""

from datetime import datetime, timezone
from types import ModuleType, SimpleNamespace
import sys
import unittest

from support import bootstrap

bootstrap()

from custom_components.battery_smartflow_ai.const import (  # noqa: E402
    FORECAST_STATUS_AVAILABLE,
    FORECAST_STATUS_UNAVAILABLE,
)
from custom_components.battery_smartflow_ai.forecast import (  # noqa: E402
    async_build_forecast_summary,
    async_energy_forecast_sources,
    build_energy_forecast_summary,
)


class FixedClock:
    def local_now(self):
        return datetime(2026, 9, 9, 10, 0, tzinfo=timezone.utc)


class EnergyForecastTests(unittest.TestCase):
    def test_multiple_energy_forecasts_are_aggregated_and_windowed(self):
        now = datetime(2026, 9, 9, 10, 30, tzinfo=timezone.utc)
        first = {
            "wh_hours": {
                "2026-09-09T10:00:00+00:00": 600,
                "2026-09-09T11:00:00+00:00": 1200,
                "2026-09-09T12:00:00+00:00": 600,
                "2026-09-10T10:00:00+00:00": 600,
            }
        }
        second = {
            "wh_hours": {
                "2026-09-09T10:00:00+00:00": 400,
                "2026-09-09T11:00:00+00:00": 800,
                "2026-09-09T12:00:00+00:00": 400,
                "2026-09-10T10:00:00+00:00": 400,
            }
        }

        result = build_energy_forecast_summary(
            [first, second],
            now_local=now,
            forecast_base_load_w=300,
            source_name="East, West",
        )

        self.assertEqual(result.status, FORECAST_STATUS_AVAILABLE)
        self.assertEqual(result.source_name, "East, West")
        self.assertEqual(result.next_3h_kwh, 2.75)
        self.assertEqual(result.next_6h_kwh, 2.75)
        self.assertEqual(result.tomorrow_kwh, 0.7)
        self.assertEqual(result.peak_today_w, 2000.0)

    def test_empty_or_invalid_energy_forecast_is_unavailable(self):
        result = build_energy_forecast_summary(
            [{"wh_hours": {"invalid": "unknown"}}],
            now_local=datetime(2026, 9, 9, tzinfo=timezone.utc),
            source_name="Forecast",
        )
        self.assertEqual(result.status, FORECAST_STATUS_UNAVAILABLE)
        self.assertEqual(result.source_name, "Forecast")


class EnergyForecastApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        components = ModuleType("homeassistant.components")
        components.__path__ = []
        energy = ModuleType("homeassistant.components.energy")
        energy.__path__ = []
        websocket = ModuleType("homeassistant.components.energy.websocket_api")

        async def get_platforms(_hass):
            async def forecast(_hass, entry_id):
                if entry_id == "broken":
                    raise RuntimeError("provider failed")
                return {
                    "wh_hours": {"2026-09-09T10:00:00+00:00": 1000}
                }

            return {"forecast_solar": forecast}

        websocket.async_get_energy_platforms = get_platforms
        sys.modules["homeassistant.components"] = components
        sys.modules["homeassistant.components.energy"] = energy
        sys.modules["homeassistant.components.energy.websocket_api"] = websocket

        entries = {
            "east": SimpleNamespace(
                entry_id="east", title="East roof", domain="forecast_solar"
            ),
            "broken": SimpleNamespace(
                entry_id="broken", title="Broken roof", domain="forecast_solar"
            ),
            "other": SimpleNamespace(
                entry_id="other", title="Weather", domain="weather"
            ),
        }
        self.hass = SimpleNamespace(
            config_entries=SimpleNamespace(
                async_entries=lambda: list(entries.values()),
                async_get_entry=entries.get,
            )
        )

    async def test_lists_only_energy_forecast_config_entries(self):
        options = await async_energy_forecast_sources(self.hass)
        self.assertEqual(
            [item["value"] for item in options], ["broken", "east"]
        )

    async def test_one_failed_source_does_not_discard_available_forecast(self):
        result = await async_build_forecast_summary(
            self.hass,
            ("broken", "east"),
            None,
            None,
            forecast_base_load_w=0,
            clock=FixedClock(),
        )
        self.assertEqual(result.status, FORECAST_STATUS_AVAILABLE)
        self.assertEqual(result.remaining_today_kwh, 1.0)
        self.assertEqual(result.source_name, "Broken roof, East roof")


if __name__ == "__main__":
    unittest.main()
