"""Compatibility adapter for V4.5 import-price forecast attributes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, tzinfo
from typing import Callable, Iterable, Mapping

from .models import (
    MarketPriceDirection,
    MarketPriceForecast,
    MarketPricePoint,
    MarketPriceValidity,
)
from .adapters import normalize_price_value


DatetimeParser = Callable[[str], datetime | None]


_FORECAST_CONTAINER_KEYS = (
    "rates",
    "data",
    "unit_rate_forecast",
    "timeslots",
    "today",
    "tomorrow",
    "raw_today",
    "raw_tomorrow",
)

_START_KEYS = ("start_time", "starts_at", "start", "time")
_END_KEYS = ("end_time", "ends_at", "end")
_PRICE_KEYS = (
    "price_per_kwh",
    "value_inc_vat",
    "total",
    "value",
    "unit_rate",
    "price",
)
_DEFAULT_SLOT_DURATION = timedelta(minutes=15)
_MAX_INFERRED_SLOT_DURATION = timedelta(hours=2)


def _to_float(value: object, default: float | None = None) -> float | None:
    """Preserve the permissive numeric conversion used by V4.5."""

    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _first_present(
    values: Mapping[str, object],
    keys: Iterable[str],
) -> object | None:
    """Return the first present non-None value without discarding numeric zero."""

    for key in keys:
        if key in values and values[key] is not None:
            return values[key]
    return None


@dataclass(frozen=True, slots=True)
class _PendingPoint:
    """Parsed point whose missing end can be inferred from adjacent slots."""

    start: datetime
    end: datetime | None
    price: object
    unit: object | None = None
    currency: object | None = None


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

        return any(key in attributes for key in _FORECAST_CONTAINER_KEYS)

    def normalize(
        self,
        attributes: Mapping[str, object],
        *,
        direction: MarketPriceDirection,
        active_currency: str,
    ) -> MarketPriceForecast:
        """Return the same future price intervals produced by V4.5.

        ``direction`` and ``active_currency`` establish the common adapter
        contract. Values and units are normalized centrally after the legacy
        provider fields have been extracted.
        """

        del direction

        raw_items = self._extract_items(attributes)
        if not raw_items:
            return MarketPriceForecast.empty(timestamp=self.now)

        now = self._normalize_datetime(self.now)
        source_unit = _first_present(
            attributes,
            ("unit_of_measurement", "unit"),
        )
        source_currency = attributes.get("currency")
        pending: list[_PendingPoint] = []

        for item in raw_items:
            if "validFrom" in item and "validTo" in item:
                tariff_point = self._parse_tariff_point(
                    item,
                    now,
                    source_currency=source_currency,
                )
                if tariff_point is not None:
                    pending.append(tariff_point)
                continue

            generic_point = self._parse_generic_point(
                item,
                now,
                source_unit=source_unit,
                source_currency=source_currency,
            )
            if generic_point is not None:
                pending.append(generic_point)

        pending.sort(key=lambda point: point.start)
        points = self._finalize_points(
            pending,
            now,
            active_currency=active_currency,
        )
        return MarketPriceForecast(points=tuple(points), timestamp=now)

    def _extract_items(
        self,
        attributes: Mapping[str, object],
    ) -> list[Mapping[str, object]]:
        """Flatten supported provider containers, including today/tomorrow pairs."""

        items: list[Mapping[str, object]] = []
        visited: set[int] = set()

        def visit(value: object) -> None:
            if isinstance(value, (list, tuple)):
                for entry in value:
                    if isinstance(entry, Mapping):
                        items.append(entry)
                return

            if not isinstance(value, Mapping) or id(value) in visited:
                return
            visited.add(id(value))
            for key in _FORECAST_CONTAINER_KEYS:
                if key in value:
                    visit(value[key])

        for key in _FORECAST_CONTAINER_KEYS:
            if key in attributes:
                visit(attributes[key])
        return items

    def _parse_tariff_point(
        self,
        item: Mapping[str, object],
        now: datetime,
        *,
        source_currency: object | None,
    ) -> _PendingPoint | None:
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

        return _PendingPoint(
            start=point_start,
            end=point_end,
            price=cents,
            unit="ct/kWh",
            currency=item.get("currency", source_currency),
        )

    def _parse_generic_point(
        self,
        item: Mapping[str, object],
        now: datetime,
        *,
        source_unit: object | None,
        source_currency: object | None,
    ) -> _PendingPoint | None:
        """Parse the generic field aliases accepted by V4.5."""

        start = _first_present(item, _START_KEYS)
        end = _first_present(item, _END_KEYS)
        price = _to_float(_first_present(item, _PRICE_KEYS), None)
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
            point_end = None

        if point_end is not None and point_end <= point_start:
            return None

        return _PendingPoint(
            start=point_start,
            end=point_end,
            price=float(price),
            unit=_first_present(
                item,
                ("unit_of_measurement", "unit"),
            )
            or source_unit,
            currency=item.get("currency", source_currency),
        )

    def _finalize_points(
        self,
        pending: list[_PendingPoint],
        now: datetime,
        *,
        active_currency: str,
    ) -> list[MarketPricePoint]:
        """Infer missing ends from adjacent starts and retain real slot lengths."""

        if not pending:
            return []

        known_durations = [
            point.end - point.start
            for point in pending
            if point.end is not None
            and _DEFAULT_SLOT_DURATION
            <= point.end - point.start
            <= _MAX_INFERRED_SLOT_DURATION
        ]
        adjacent_durations = [
            following.start - point.start
            for point, following in zip(pending, pending[1:])
            if _DEFAULT_SLOT_DURATION
            <= following.start - point.start
            <= _MAX_INFERRED_SLOT_DURATION
        ]
        fallback_duration = (
            known_durations[-1]
            if known_durations
            else adjacent_durations[-1]
            if adjacent_durations
            else _DEFAULT_SLOT_DURATION
        )

        points: list[MarketPricePoint] = []
        seen: set[tuple[datetime, datetime]] = set()
        for index, point in enumerate(pending):
            point_end = point.end
            if point_end is None:
                next_start = next(
                    (
                        candidate.start
                        for candidate in pending[index + 1 :]
                        if candidate.start > point.start
                    ),
                    None,
                )
                if (
                    next_start is not None
                    and next_start - point.start <= _MAX_INFERRED_SLOT_DURATION
                ):
                    point_end = next_start
                else:
                    point_end = point.start + fallback_duration

            if not self._valid_future_interval(point.start, point_end, now):
                continue

            interval = (point.start, point_end)
            if interval in seen:
                continue
            normalized = normalize_price_value(
                point.price,
                unit=point.unit,
                currency=point.currency,
                active_currency=active_currency,
            )
            if not normalized.validity is MarketPriceValidity.VALID:
                continue
            if normalized.value is None:
                continue
            seen.add(interval)
            points.append(
                MarketPricePoint(
                    start=point.start,
                    end=point_end,
                    price=float(normalized.value),
                )
            )
        return points

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
