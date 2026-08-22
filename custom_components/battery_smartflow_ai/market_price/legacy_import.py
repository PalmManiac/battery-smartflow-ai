"""Compatibility adapter for V4.5 import-price forecast attributes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, tzinfo
from typing import Callable, Mapping

from .models import (
    MarketPriceDirection,
    MarketPriceForecast,
    MarketPricePoint,
)


DatetimeParser = Callable[[str], datetime | None]


def _to_float(value: object, default: float | None = None) -> float | None:
    """Preserve the permissive numeric conversion used by V4.5."""

    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True, slots=True)
class LegacyImportForecastAdapter:
    """Normalize the import forecast attribute families supported by V4.5."""

    now: datetime
    default_timezone: tzinfo
    parse_datetime: DatetimeParser

    @property
    def name(self) -> str:
        """Return a stable diagnostic name."""

        return "legacy_import_forecast"

    def supports(self, attributes: Mapping[str, object]) -> bool:
        """Return whether a known V4.5 forecast container is present."""

        return any(
            key in attributes
            for key in ("rates", "data", "unit_rate_forecast")
        )

    def normalize(
        self,
        attributes: Mapping[str, object],
        *,
        direction: MarketPriceDirection,
        active_currency: str,
    ) -> MarketPriceForecast:
        """Return the same future price intervals produced by V4.5.

        ``direction`` and ``active_currency`` establish the common adapter
        contract. This compatibility parser intentionally performs only the
        historic cents conversion; central unit handling follows in issue
        #243.
        """

        del direction, active_currency

        raw = (
            attributes.get("rates")
            or attributes.get("data")
            or attributes.get("unit_rate_forecast")
        )
        if not raw:
            return MarketPriceForecast.empty(timestamp=self.now)

        if isinstance(raw, dict):
            raw = raw.get("rates") or raw.get("data") or raw.get("timeslots")

        if not isinstance(raw, list):
            return MarketPriceForecast.empty(timestamp=self.now)

        now = self._normalize_datetime(self.now)
        points: list[MarketPricePoint] = []

        for item in raw:
            if not isinstance(item, dict):
                continue

            if "validFrom" in item and "validTo" in item:
                tariff_point = self._parse_tariff_point(item, now)
                if tariff_point is not None:
                    points.append(tariff_point)
                continue

            generic_point = self._parse_generic_point(item, now)
            if generic_point is not None:
                points.append(generic_point)

        points.sort(key=lambda point: point.start)
        return MarketPriceForecast(points=tuple(points), timestamp=now)

    def _parse_tariff_point(
        self,
        item: Mapping[str, object],
        now: datetime,
    ) -> MarketPricePoint | None:
        """Parse the historic validFrom/unitRateInformation structure."""

        start = item.get("validFrom")
        end = item.get("validTo")
        cents = None
        unit_information = item.get("unitRateInformation") or {}
        if isinstance(unit_information, Mapping):
            rates = unit_information.get("rates") or []
            if (
                isinstance(rates, (list, tuple))
                and rates
                and isinstance(rates[0], dict)
            ):
                cents = _to_float(
                    rates[0].get("latestGrossUnitRateCentsPerKwh"),
                    None,
                )

        if not start or not end or cents is None:
            return None

        point_start = self._parse_and_normalize(start)
        point_end = self._parse_and_normalize(end)
        if not self._valid_future_interval(point_start, point_end, now):
            return None

        return MarketPricePoint(
            start=point_start,
            end=point_end,
            price=float(cents) / 100.0,
        )

    def _parse_generic_point(
        self,
        item: Mapping[str, object],
        now: datetime,
    ) -> MarketPricePoint | None:
        """Parse the generic field aliases accepted by V4.5."""

        start = (
            item.get("start_time")
            or item.get("starts_at")
            or item.get("start")
            or item.get("time")
        )
        end = item.get("end_time") or item.get("ends_at") or item.get("end")
        price = _to_float(
            item.get("price_per_kwh")
            or item.get("value_inc_vat")
            or item.get("value")
            or item.get("unit_rate")
            or item.get("price"),
            None,
        )
        if not start or price is None:
            return None

        point_start = self._parse_and_normalize(start)
        if point_start is None:
            return None

        if end:
            point_end = self._parse_and_normalize(end)
            if point_end is None:
                return None
        else:
            point_end = point_start + timedelta(minutes=15)

        if not self._valid_future_interval(point_start, point_end, now):
            return None

        return MarketPricePoint(
            start=point_start,
            end=point_end,
            price=float(price),
        )

    def _parse_and_normalize(self, value: object) -> datetime | None:
        parsed = self.parse_datetime(str(value))
        return self._normalize_datetime(parsed)

    def _normalize_datetime(self, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=self.default_timezone)
        return value.astimezone(self.default_timezone)

    @staticmethod
    def _valid_future_interval(
        start: datetime | None,
        end: datetime | None,
        now: datetime,
    ) -> bool:
        return bool(start and end and end > start and end > now)
