"""V4.5 compatibility contracts for the extracted import-price parser."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.market_price import (  # noqa: E402
    LegacyImportForecastAdapter,
    MarketPriceDirection,
)


UTC = timezone.utc
BERLIN = timezone(timedelta(hours=2), name="Europe/Berlin")
NOW = datetime(2026, 8, 22, 10, 0, tzinfo=UTC)


def parse_datetime(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def adapter(
    *,
    now: datetime = NOW,
    default_timezone=UTC,
) -> LegacyImportForecastAdapter:
    return LegacyImportForecastAdapter(
        now=now,
        default_timezone=default_timezone,
        parse_datetime=parse_datetime,
    )


def normalize(attributes: dict[str, object], **kwargs):
    return adapter(**kwargs).normalize(
        attributes,
        direction=MarketPriceDirection.IMPORT,
        active_currency="EUR",
    )


class LegacyImportForecastAdapterTests(unittest.TestCase):
    def test_recognizes_all_v45_top_level_containers(self) -> None:
        instance = adapter()

        for key in (
            "rates",
            "data",
            "unit_rate_forecast",
            "timeslots",
            "today",
            "tomorrow",
            "raw_today",
            "raw_tomorrow",
        ):
            with self.subTest(key=key):
                self.assertTrue(instance.supports({key: []}))
        self.assertFalse(instance.supports({"forecast": []}))

    def test_parses_tariff_cents_and_converts_to_currency_per_kwh(self) -> None:
        forecast = normalize(
            {
                "rates": [
                    {
                        "validFrom": "2026-08-22T11:00:00+00:00",
                        "validTo": "2026-08-22T12:00:00+00:00",
                        "unitRateInformation": {
                            "rates": [
                                {"latestGrossUnitRateCentsPerKwh": -3.0}
                            ]
                        },
                    }
                ]
            }
        )

        self.assertEqual(len(forecast.points), 1)
        self.assertEqual(forecast.points[0].price, -0.03)

    def test_tariff_shape_does_not_fall_back_to_generic_fields(self) -> None:
        forecast = normalize(
            {
                "rates": [
                    {
                        "validFrom": "2026-08-22T11:00:00+00:00",
                        "validTo": "2026-08-22T12:00:00+00:00",
                        "price": 0.25,
                    }
                ]
            }
        )

        self.assertEqual(forecast.points, ())

    def test_parses_generic_container_and_field_aliases(self) -> None:
        cases = (
            (
                "data",
                {"start_time": "2026-08-22T11:00:00+00:00", "price_per_kwh": 0.1},
            ),
            (
                "unit_rate_forecast",
                {"starts_at": "2026-08-22T11:15:00+00:00", "value_inc_vat": 0.2},
            ),
            (
                "rates",
                {"start": "2026-08-22T11:30:00+00:00", "unit_rate": -0.04},
            ),
        )

        for container, point in cases:
            with self.subTest(container=container):
                forecast = normalize({container: [point]})
                self.assertEqual(len(forecast.points), 1)

    def test_parses_nested_timeslots_container(self) -> None:
        forecast = normalize(
            {
                "data": {
                    "timeslots": [
                        {
                            "time": "2026-08-22T11:00:00+00:00",
                            "price": 0.17,
                        }
                    ]
                }
            }
        )

        self.assertEqual(len(forecast.points), 1)
        self.assertEqual(forecast.points[0].price, 0.17)

    def test_missing_end_keeps_v45_fifteen_minute_default(self) -> None:
        forecast = normalize(
            {
                "rates": [
                    {
                        "start": "2026-08-22T11:00:00+00:00",
                        "price": 0.22,
                    }
                ]
            }
        )

        point = forecast.points[0]
        self.assertEqual(point.end - point.start, timedelta(minutes=15))

    def test_merges_today_and_tomorrow_forecast_lists(self) -> None:
        forecast = normalize(
            {
                "today": [
                    {"starts_at": "2026-08-22T23:00:00+00:00", "total": 0.12}
                ],
                "tomorrow": [
                    {"starts_at": "2026-08-23T00:00:00+00:00", "total": 0.08}
                ],
            }
        )

        self.assertEqual([point.price for point in forecast.points], [0.12, 0.08])
        self.assertEqual(
            forecast.points[0].end - forecast.points[0].start,
            timedelta(hours=1),
        )
        self.assertEqual(
            forecast.points[1].end - forecast.points[1].start,
            timedelta(hours=1),
        )

    def test_merges_nested_today_and_tomorrow_provider_payload(self) -> None:
        forecast = normalize(
            {
                "data": {
                    "today": [
                        {"start": "2026-08-22T11:00:00+00:00", "price": 0.2}
                    ],
                    "tomorrow": [
                        {"start": "2026-08-23T00:00:00+00:00", "price": 0.1}
                    ],
                }
            }
        )

        self.assertEqual(len(forecast.points), 2)
        self.assertEqual(
            forecast.points[0].end - forecast.points[0].start,
            timedelta(minutes=15),
        )
        self.assertLess(forecast.points[0].end, forecast.points[1].start)

    def test_infers_quarter_hour_and_hour_slots_from_adjacent_starts(self) -> None:
        quarter_hour = normalize(
            {
                "rates": [
                    {"start": "2026-08-22T11:00:00+00:00", "price": 0.1},
                    {"start": "2026-08-22T11:15:00+00:00", "price": 0.2},
                ]
            }
        )
        hourly = normalize(
            {
                "rates": [
                    {"start": "2026-08-22T11:00:00+00:00", "price": 0.1},
                    {"start": "2026-08-22T12:00:00+00:00", "price": 0.2},
                ]
            }
        )

        self.assertTrue(
            all(
                point.end - point.start == timedelta(minutes=15)
                for point in quarter_hour.points
            )
        )
        self.assertTrue(
            all(
                point.end - point.start == timedelta(hours=1)
                for point in hourly.points
            )
        )

    def test_zero_and_negative_prices_are_preserved(self) -> None:
        forecast = normalize(
            {
                "rates": [
                    {"start": "2026-08-22T11:00:00+00:00", "price": 0.0},
                    {"start": "2026-08-22T12:00:00+00:00", "price": -0.05},
                ]
            }
        )

        self.assertEqual([point.price for point in forecast.points], [0.0, -0.05])

    def test_forecast_unit_is_normalized_to_currency_per_kwh(self) -> None:
        forecast = normalize(
            {
                "unit_of_measurement": "EUR/MWh",
                "currency": "EUR",
                "rates": [
                    {"start": "2026-08-22T11:00:00+00:00", "price": 122.0}
                ],
            }
        )

        self.assertEqual(forecast.points[0].price, 0.122)

    def test_epex_euro_symbol_forecast_is_preserved(self) -> None:
        forecast = normalize(
            {
                "unit_of_measurement": "€/kWh",
                "data": [
                    {
                        "start_time": "2026-08-22T11:00:00+00:00",
                        "end_time": "2026-08-22T12:00:00+00:00",
                        "price_per_kwh": -0.04,
                    },
                    {
                        "start_time": "2026-08-22T12:00:00+00:00",
                        "end_time": "2026-08-22T13:00:00+00:00",
                        "price_per_kwh": 0.22,
                    },
                ],
            }
        )

        self.assertEqual([point.price for point in forecast.points], [-0.04, 0.22])

    def test_forecast_with_different_currency_is_rejected(self) -> None:
        forecast = normalize(
            {
                "unit_of_measurement": "DKK/kWh",
                "currency": "DKK",
                "rates": [
                    {"start": "2026-08-22T11:00:00+00:00", "price": 1.5}
                ],
            }
        )

        self.assertEqual(forecast.points, ())

    def test_gap_is_preserved_instead_of_inventing_missing_slots(self) -> None:
        forecast = normalize(
            {
                "rates": [
                    {
                        "start": "2026-08-22T11:00:00+00:00",
                        "end": "2026-08-22T12:00:00+00:00",
                        "price": 0.1,
                    },
                    {
                        "start": "2026-08-22T13:00:00+00:00",
                        "end": "2026-08-22T14:00:00+00:00",
                        "price": 0.2,
                    },
                ]
            }
        )

        self.assertEqual(forecast.points[0].end, datetime(2026, 8, 22, 12, tzinfo=UTC))
        self.assertEqual(forecast.points[1].start, datetime(2026, 8, 22, 13, tzinfo=UTC))

    def test_expired_invalid_and_non_mapping_points_are_discarded(self) -> None:
        forecast = normalize(
            {
                "rates": [
                    "invalid",
                    {"start": "invalid", "price": 0.1},
                    {
                        "start": "2026-08-22T08:00:00+00:00",
                        "end": "2026-08-22T09:00:00+00:00",
                        "price": 0.2,
                    },
                    {
                        "start": "2026-08-22T12:00:00+00:00",
                        "end": "2026-08-22T11:00:00+00:00",
                        "price": 0.3,
                    },
                ]
            }
        )

        self.assertEqual(forecast.points, ())

    def test_points_are_sorted_and_aware_timestamps_are_localized(self) -> None:
        forecast = normalize(
            {
                "rates": [
                    {"start": "2026-08-22T12:00:00+00:00", "price": 0.3},
                    {"start": "2026-08-22T11:00:00+00:00", "price": 0.1},
                ]
            },
            default_timezone=BERLIN,
        )

        self.assertLess(forecast.points[0].start, forecast.points[1].start)
        self.assertEqual(forecast.points[0].start.tzinfo, BERLIN)

    def test_naive_timestamps_use_the_home_assistant_timezone(self) -> None:
        local_now = datetime(2026, 8, 22, 10, 0, tzinfo=BERLIN)
        forecast = normalize(
            {
                "rates": [
                    {"start": "2026-08-22T11:00:00", "price": 0.1}
                ]
            },
            now=local_now,
            default_timezone=BERLIN,
        )

        self.assertEqual(forecast.points[0].start.tzinfo, BERLIN)

    def test_unknown_or_empty_container_returns_explicit_empty_forecast(self) -> None:
        self.assertEqual(normalize({"forecast": []}).points, ())
        self.assertEqual(normalize({"rates": []}).points, ())
        self.assertEqual(normalize({"rates": "invalid"}).points, ())

    def test_provider_field_heuristics_no_longer_live_in_coordinator(self) -> None:
        coordinator_source = (
            Path(__file__).resolve().parents[1]
            / "custom_components"
            / "battery_smartflow_ai"
            / "coordinator.py"
        ).read_text(encoding="utf-8")

        self.assertIn("_get_import_market_price", coordinator_source)
        for provider_field in (
            "validFrom",
            "validTo",
            "unitRateInformation",
            "latestGrossUnitRateCentsPerKwh",
            "unit_rate_forecast",
        ):
            with self.subTest(provider_field=provider_field):
                self.assertNotIn(provider_field, coordinator_source)


if __name__ == "__main__":
    unittest.main()
