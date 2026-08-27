from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import (
    FORECAST_STATUS_AVAILABLE,
    FORECAST_STATUS_NOT_CONFIGURED,
    FORECAST_STATUS_UNAVAILABLE,
    PV_OUTLOOK_GOOD,
    PV_OUTLOOK_MIXED,
    PV_OUTLOOK_POOR,
    PV_OUTLOOK_UNKNOWN,
)
from .core.clock import SystemClock
from .core.ports import Clock


@dataclass
class ForecastSummary:
    status: str = FORECAST_STATUS_NOT_CONFIGURED
    source_name: str | None = None

    remaining_today_kwh: float = 0.0
    tomorrow_kwh: float = 0.0

    next_3h_kwh: float = 0.0
    next_6h_kwh: float = 0.0

    peak_today_w: float = 0.0
    peak_tomorrow_w: float = 0.0

    pv_outlook: str = PV_OUTLOOK_UNKNOWN


def _to_float(v: Any, default: float | None = None) -> float | None:
    try:
        if v is None:
            return default
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip()
        if s == "" or s.lower() in ("unknown", "unavailable", "none"):
            return default
        return float(s)
    except Exception:
        return default


def _normalize_dt(value: Any) -> datetime | None:
    if value is None:
        return None

    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = dt_util.parse_datetime(str(value))
        except Exception:
            return None

    if dt is None:
        return None

    return dt_util.as_local(dt)


def _classify_pv_outlook(
    remaining_today_kwh: float,
    next_6h_kwh: float,
    tomorrow_kwh: float,
    installed_pv_wp: float,
) -> str:
    installed_wp = max(0.0, float(installed_pv_wp or 0.0))

    if installed_wp <= 0:
        if next_6h_kwh <= 0.05 and remaining_today_kwh <= 0.10 and tomorrow_kwh <= 0.10:
            return PV_OUTLOOK_POOR
        if next_6h_kwh >= 2.5 or remaining_today_kwh >= 4.0 or tomorrow_kwh >= 5.0:
            return PV_OUTLOOK_GOOD
        if next_6h_kwh > 0.10 or remaining_today_kwh > 0.20 or tomorrow_kwh > 0.20:
            return PV_OUTLOOK_MIXED
        return PV_OUTLOOK_UNKNOWN

    reference_day_kwh = installed_wp / 1000.0 * 3.0
    reference_6h_kwh = installed_wp / 1000.0 * 1.5

    good_now = (
        next_6h_kwh >= reference_6h_kwh * 0.55
        or remaining_today_kwh >= reference_day_kwh * 0.55
        or tomorrow_kwh >= reference_day_kwh * 0.70
    )

    poor_now = (
        next_6h_kwh <= max(0.15, reference_6h_kwh * 0.08)
        and remaining_today_kwh <= max(0.20, reference_day_kwh * 0.10)
        and tomorrow_kwh <= max(0.30, reference_day_kwh * 0.12)
    )

    if good_now:
        return PV_OUTLOOK_GOOD
    if poor_now:
        return PV_OUTLOOK_POOR

    return PV_OUTLOOK_MIXED


def _read_sensor_kwh(
    hass: HomeAssistant,
    entity_id: str | None,
) -> tuple[float | None, bool]:
    if not entity_id:
        return None, False

    st = hass.states.get(entity_id)
    if st is None:
        return None, False

    return _to_float(st.state, None), True


def _read_sensor_attrs(
    hass: HomeAssistant,
    entity_id: str | None,
) -> tuple[dict[str, Any], bool]:
    if not entity_id:
        return {}, False

    st = hass.states.get(entity_id)
    if st is None:
        return {}, False

    attrs = st.attributes or {}
    if not isinstance(attrs, dict):
        return {}, False

    return attrs, True


def _iter_hourly_intervals(attrs: dict[str, Any]) -> list[dict[str, Any]]:
    raw = attrs.get("detailedHourly")
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    return []


def _iter_halfhour_intervals(attrs: dict[str, Any]) -> list[dict[str, Any]]:
    raw = attrs.get("detailedForecast")
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    return []


def _get_interval_power_kw(item: dict[str, Any]) -> float | None:
    return _to_float(item.get("pv_estimate"), None)


def _net_interval_energy_kwh(
    energy_kwh: float,
    duration_h: float,
    base_load_w: float,
) -> float:
    base_kwh = (max(0.0, float(base_load_w or 0.0)) / 1000.0) * max(0.0, float(duration_h or 0.0))
    return max(0.0, float(energy_kwh or 0.0) - base_kwh)


def _compute_window_energy_from_intervals(
    intervals: list[dict[str, Any]],
    now_local: datetime,
    hours_ahead: float,
    slot_minutes: int,
    forecast_base_load_w: float,
) -> float:
    if not intervals:
        return 0.0

    window_end = now_local + timedelta(hours=float(hours_ahead))
    total_kwh = 0.0
    slot_td = timedelta(minutes=slot_minutes)

    for item in intervals:
        start = _normalize_dt(item.get("period_start"))
        if start is None:
            continue

        end = start + slot_td
        if end <= now_local or start >= window_end:
            continue

        power_kw = _get_interval_power_kw(item)
        if power_kw is None or power_kw <= 0:
            continue

        overlap_start = max(start, now_local)
        overlap_end = min(end, window_end)
        overlap_h = max(0.0, (overlap_end - overlap_start).total_seconds() / 3600.0)
        if overlap_h <= 0:
            continue

        gross_kwh = float(power_kw) * overlap_h
        net_kwh = _net_interval_energy_kwh(
            energy_kwh=gross_kwh,
            duration_h=overlap_h,
            base_load_w=forecast_base_load_w,
        )
        total_kwh += net_kwh

    return total_kwh


def _compute_peak_kw_for_date(
    intervals: list[dict[str, Any]],
    target_date,
) -> float:
    peak_kw = 0.0

    for item in intervals:
        start = _normalize_dt(item.get("period_start"))
        if start is None or start.date() != target_date:
            continue

        power_kw = _get_interval_power_kw(item)
        if power_kw is None:
            continue

        peak_kw = max(peak_kw, float(power_kw))

    return peak_kw


def _compute_peaks_for_sensor(
    hass: HomeAssistant,
    entity_id: str | None,
    now_local: datetime,
) -> tuple[float, float]:
    """
    Returns:
        peak_today_w, peak_tomorrow_w
    """
    attrs, found = _read_sensor_attrs(hass, entity_id)
    if not found:
        return 0.0, 0.0

    today = now_local.date()
    tomorrow = (now_local + timedelta(days=1)).date()

    hourly = _iter_hourly_intervals(attrs)
    if hourly:
        peak_today_w = _compute_peak_kw_for_date(hourly, today) * 1000.0
        peak_tomorrow_w = _compute_peak_kw_for_date(hourly, tomorrow) * 1000.0
        return peak_today_w, peak_tomorrow_w

    halfhour = _iter_halfhour_intervals(attrs)
    if halfhour:
        peak_today_w = _compute_peak_kw_for_date(halfhour, today) * 1000.0
        peak_tomorrow_w = _compute_peak_kw_for_date(halfhour, tomorrow) * 1000.0
        return peak_today_w, peak_tomorrow_w

    return 0.0, 0.0


def _compute_daily_net_energy_for_sensor(
    hass: HomeAssistant,
    entity_id: str | None,
    fallback_state_kwh: float | None,
    target_date,
    forecast_base_load_w: float,
) -> float:
    attrs, found = _read_sensor_attrs(hass, entity_id)
    if not found:
        return max(0.0, float(fallback_state_kwh or 0.0))

    hourly = _iter_hourly_intervals(attrs)
    if hourly:
        total_kwh = 0.0
        for item in hourly:
            start = _normalize_dt(item.get("period_start"))
            if start is None or start.date() != target_date:
                continue

            power_kw = _get_interval_power_kw(item)
            if power_kw is None or power_kw <= 0:
                continue

            gross_kwh = float(power_kw) * 1.0
            total_kwh += _net_interval_energy_kwh(
                energy_kwh=gross_kwh,
                duration_h=1.0,
                base_load_w=forecast_base_load_w,
            )
        return total_kwh

    halfhour = _iter_halfhour_intervals(attrs)
    if halfhour:
        total_kwh = 0.0
        for item in halfhour:
            start = _normalize_dt(item.get("period_start"))
            if start is None or start.date() != target_date:
                continue

            power_kw = _get_interval_power_kw(item)
            if power_kw is None or power_kw <= 0:
                continue

            gross_kwh = float(power_kw) * 0.5
            total_kwh += _net_interval_energy_kwh(
                energy_kwh=gross_kwh,
                duration_h=0.5,
                base_load_w=forecast_base_load_w,
            )
        return total_kwh

    return max(0.0, float(fallback_state_kwh or 0.0))


def _compute_subday_metrics(
    hass: HomeAssistant,
    today_entity_id: str | None,
    tomorrow_entity_id: str | None,
    forecast_base_load_w: float,
    now_local: datetime,
) -> tuple[float, float, float, float]:
    """
    Returns:
        next_3h_kwh, next_6h_kwh, peak_today_w, peak_tomorrow_w

    - next_3h / next_6h are NET after base load
    - peaks remain gross W
    """
    attrs, found = _read_sensor_attrs(hass, today_entity_id)
    if not found:
        _, peak_tomorrow_w = _compute_peaks_for_sensor(
            hass, tomorrow_entity_id, now_local
        )
        return 0.0, 0.0, 0.0, peak_tomorrow_w

    hourly = _iter_hourly_intervals(attrs)
    if hourly:
        next_3h_kwh = _compute_window_energy_from_intervals(
            hourly,
            now_local=now_local,
            hours_ahead=3.0,
            slot_minutes=60,
            forecast_base_load_w=forecast_base_load_w,
        )
        next_6h_kwh = _compute_window_energy_from_intervals(
            hourly,
            now_local=now_local,
            hours_ahead=6.0,
            slot_minutes=60,
            forecast_base_load_w=forecast_base_load_w,
        )
        peak_today_w, _ = _compute_peaks_for_sensor(
            hass, today_entity_id, now_local
        )
        _, peak_tomorrow_w = _compute_peaks_for_sensor(
            hass, tomorrow_entity_id, now_local
        )
        return next_3h_kwh, next_6h_kwh, peak_today_w, peak_tomorrow_w

    halfhour = _iter_halfhour_intervals(attrs)
    if halfhour:
        next_3h_kwh = _compute_window_energy_from_intervals(
            halfhour,
            now_local=now_local,
            hours_ahead=3.0,
            slot_minutes=30,
            forecast_base_load_w=forecast_base_load_w,
        )
        next_6h_kwh = _compute_window_energy_from_intervals(
            halfhour,
            now_local=now_local,
            hours_ahead=6.0,
            slot_minutes=30,
            forecast_base_load_w=forecast_base_load_w,
        )
        peak_today_w, _ = _compute_peaks_for_sensor(
            hass, today_entity_id, now_local
        )
        _, peak_tomorrow_w = _compute_peaks_for_sensor(
            hass, tomorrow_entity_id, now_local
        )
        return next_3h_kwh, next_6h_kwh, peak_today_w, peak_tomorrow_w

    _, peak_tomorrow_w = _compute_peaks_for_sensor(
        hass, tomorrow_entity_id, now_local
    )
    return 0.0, 0.0, 0.0, peak_tomorrow_w


def build_forecast_summary(
    hass: HomeAssistant,
    today_entity_id: str | None,
    tomorrow_entity_id: str | None,
    installed_pv_wp: float = 0.0,
    forecast_base_load_w: float = 300.0,
    *,
    clock: Clock | None = None,
) -> ForecastSummary:
    """
    Build a normalized optional forecast summary from two daily forecast sensors.

    - today/tomorrow totals are NET after base load where interval data is available
    - next_3h / next_6h are NET after base load
    - peaks remain gross W
    - forecast remains optional
    """
    if not today_entity_id and not tomorrow_entity_id:
        return ForecastSummary(
            status=FORECAST_STATUS_NOT_CONFIGURED,
            source_name=None,
            pv_outlook=PV_OUTLOOK_UNKNOWN,
        )

    today_kwh_raw, today_found = _read_sensor_kwh(hass, today_entity_id)
    tomorrow_kwh_raw, tomorrow_found = _read_sensor_kwh(hass, tomorrow_entity_id)

    any_configured = bool(today_entity_id or tomorrow_entity_id)
    any_found = bool(today_found or tomorrow_found)
    any_valid = today_kwh_raw is not None or tomorrow_kwh_raw is not None

    if any_configured and (not any_found or not any_valid):
        return ForecastSummary(
            status=FORECAST_STATUS_UNAVAILABLE,
            source_name="Solcast",
            pv_outlook=PV_OUTLOOK_UNKNOWN,
        )

    now_local = (clock or SystemClock()).local_now()
    today = now_local.date()
    tomorrow = (now_local + timedelta(days=1)).date()

    remaining_today_kwh = _compute_daily_net_energy_for_sensor(
        hass=hass,
        entity_id=today_entity_id,
        fallback_state_kwh=today_kwh_raw,
        target_date=today,
        forecast_base_load_w=forecast_base_load_w,
    )

    tomorrow_kwh_val = _compute_daily_net_energy_for_sensor(
        hass=hass,
        entity_id=tomorrow_entity_id,
        fallback_state_kwh=tomorrow_kwh_raw,
        target_date=tomorrow,
        forecast_base_load_w=forecast_base_load_w,
    )

    next_3h_kwh, next_6h_kwh, peak_today_w, peak_tomorrow_w = _compute_subday_metrics(
        hass=hass,
        today_entity_id=today_entity_id,
        tomorrow_entity_id=tomorrow_entity_id,
        forecast_base_load_w=forecast_base_load_w,
        now_local=now_local,
    )

    pv_outlook = _classify_pv_outlook(
        remaining_today_kwh=remaining_today_kwh,
        next_6h_kwh=next_6h_kwh,
        tomorrow_kwh=tomorrow_kwh_val,
        installed_pv_wp=float(installed_pv_wp or 0.0),
    )

    return ForecastSummary(
        status=FORECAST_STATUS_AVAILABLE,
        source_name="Solcast",
        remaining_today_kwh=round(float(remaining_today_kwh), 3),
        tomorrow_kwh=round(float(tomorrow_kwh_val), 3),
        next_3h_kwh=round(float(next_3h_kwh), 3),
        next_6h_kwh=round(float(next_6h_kwh), 3),
        peak_today_w=round(float(peak_today_w), 1),
        peak_tomorrow_w=round(float(peak_tomorrow_w), 1),
        pv_outlook=pv_outlook,
    )
