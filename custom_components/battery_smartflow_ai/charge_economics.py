"""Economic attribution of battery charging energy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping


@dataclass(frozen=True)
class ChargePricing:
    """Economic source and price of an active battery charge sample."""

    active: bool
    is_grid_charge: bool
    price_eur_kwh: float
    source: str
    grid_part_w: float
    pv_part_w: float

    @property
    def total_power_w(self) -> float:
        return max(0.0, float(self.grid_part_w) + float(self.pv_part_w))


def inactive_charge_pricing(source: str = "no_charge_command") -> ChargePricing:
    """Return a stable inactive pricing result."""

    return ChargePricing(
        active=False,
        is_grid_charge=False,
        price_eur_kwh=0.0,
        source=str(source),
        grid_part_w=0.0,
        pv_part_w=0.0,
    )


def classify_charge_pricing(
    *,
    grid_import_w: float,
    grid_export_w: float,
    decision_charge_w: float,
    decision_ac_mode: str,
    price_now: float | None,
    feed_in_tariff: float,
    battery_charge_w: float,
    decision_reason: str | None = None,
) -> ChargePricing:
    """Classify one active charge sample and its opportunity cost.

    Measured battery charging is authoritative even if a delayed SoC update
    arrives in the cycle in which the newly calculated decision has already
    left INPUT mode. This keeps the preceding PV charge economically visible.
    """

    charge_cmd_w = max(0.0, float(decision_charge_w or 0.0))
    measured_charge_w = max(0.0, float(battery_charge_w or 0.0))

    if str(decision_ac_mode) != "input" and measured_charge_w <= 30.0:
        return inactive_charge_pricing("not_in_input_mode")

    charge_w = measured_charge_w if measured_charge_w > 30.0 else charge_cmd_w
    if charge_w <= 0.0:
        return inactive_charge_pricing("no_charge_command")

    import_w = max(0.0, float(grid_import_w or 0.0))
    export_w = max(0.0, float(grid_export_w or 0.0))
    pv_price = max(0.0, float(feed_in_tariff or 0.0))

    price_driven_charge_reasons = {
        "very_cheap_force_charge",
        "valley_boost_charge",
        "valley_boost_charge_mixed_forecast",
        "planning_latest_start",
        "planning_forecast_poor",
        "planning_forecast_mixed",
        "planning_forecast_reality_override",
        "valley_opportunity_charge",
        "valley_opportunity_charge_mixed_forecast",
        "summer_peak_reserve_charge",
    }

    if export_w >= 40.0:
        return ChargePricing(
            active=True,
            is_grid_charge=False,
            price_eur_kwh=pv_price,
            source="pv_surplus_export",
            grid_part_w=0.0,
            pv_part_w=charge_w,
        )

    if import_w <= 60.0:
        return ChargePricing(
            active=True,
            is_grid_charge=False,
            price_eur_kwh=pv_price,
            source="pv_or_free_low_import",
            grid_part_w=0.0,
            pv_part_w=charge_w,
        )

    if price_now is None:
        return ChargePricing(
            active=True,
            is_grid_charge=False,
            price_eur_kwh=pv_price,
            source="price_missing_assume_pv_opportunity",
            grid_part_w=0.0,
            pv_part_w=charge_w,
        )

    grid_part_w = min(import_w, charge_w)
    pv_part_w = max(0.0, charge_w - grid_part_w)
    mixed_price = (
        (grid_part_w * float(price_now)) + (pv_part_w * pv_price)
    ) / charge_w

    if grid_part_w > 0.0 and pv_part_w > 0.0:
        source = "mixed_grid_pv_charge"
    elif grid_part_w > 0.0:
        source = (
            str(decision_reason)
            if decision_reason in price_driven_charge_reasons
            else "grid_charge"
        )
    else:
        source = "pv_opportunity_charge"

    return ChargePricing(
        active=True,
        is_grid_charge=grid_part_w > max(60.0, charge_w * 0.10),
        price_eur_kwh=float(mixed_price),
        source=str(source),
        grid_part_w=float(grid_part_w),
        pv_part_w=float(pv_part_w),
    )


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def recent_charge_evidence(
    raw: Any,
    *,
    now: datetime,
    max_age_seconds: float = 900.0,
) -> dict[str, Any] | None:
    """Return valid pending charge evidence or ``None`` when it is stale."""

    if not isinstance(raw, Mapping):
        return None

    updated_at = _parse_datetime(raw.get("updated_at"))
    if updated_at is None:
        return None

    try:
        age_seconds = (now - updated_at).total_seconds()
        energy_wh = max(0.0, float(raw.get("energy_wh", 0.0) or 0.0))
        cost_eur = float(raw.get("cost_eur", 0.0) or 0.0)
        grid_energy_wh = max(
            0.0,
            float(raw.get("grid_energy_wh", 0.0) or 0.0),
        )
        pv_energy_wh = max(
            0.0,
            float(raw.get("pv_energy_wh", 0.0) or 0.0),
        )
        duration_seconds = max(
            0.0,
            float(raw.get("duration_seconds", 0.0) or 0.0),
        )
    except (TypeError, ValueError):
        return None

    if age_seconds < -30.0 or age_seconds > float(max_age_seconds):
        return None
    if energy_wh <= 0.0 or duration_seconds <= 0.0:
        return None

    return {
        "energy_wh": energy_wh,
        "cost_eur": cost_eur,
        "grid_energy_wh": min(grid_energy_wh, energy_wh),
        "pv_energy_wh": min(pv_energy_wh, energy_wh),
        "duration_seconds": duration_seconds,
        "source": str(raw.get("source", "charge_evidence") or "charge_evidence"),
        "updated_at": updated_at.isoformat(),
    }


def add_charge_evidence(
    raw: Any,
    *,
    pricing: ChargePricing,
    duration_seconds: float,
    now: datetime,
) -> dict[str, Any] | None:
    """Add a power-weighted charge sample to the pending evidence ledger."""

    if not pricing.active or pricing.total_power_w <= 0.0:
        return recent_charge_evidence(raw, now=now)

    duration_seconds = max(1.0, min(float(duration_seconds), 30.0))
    existing = recent_charge_evidence(raw, now=now) or {
        "energy_wh": 0.0,
        "cost_eur": 0.0,
        "grid_energy_wh": 0.0,
        "pv_energy_wh": 0.0,
        "duration_seconds": 0.0,
        "source": pricing.source,
    }

    duration_hours = duration_seconds / 3600.0
    energy_wh = pricing.total_power_w * duration_hours
    grid_energy_wh = max(0.0, pricing.grid_part_w) * duration_hours
    pv_energy_wh = max(0.0, pricing.pv_part_w) * duration_hours

    return {
        "energy_wh": float(existing["energy_wh"]) + energy_wh,
        "cost_eur": float(existing["cost_eur"])
        + (energy_wh / 1000.0) * float(pricing.price_eur_kwh),
        "grid_energy_wh": float(existing["grid_energy_wh"]) + grid_energy_wh,
        "pv_energy_wh": float(existing["pv_energy_wh"]) + pv_energy_wh,
        "duration_seconds": float(existing["duration_seconds"]) + duration_seconds,
        "source": str(pricing.source),
        "updated_at": now.isoformat(),
    }


def pricing_from_charge_evidence(
    raw: Any,
    *,
    now: datetime,
) -> ChargePricing | None:
    """Convert pending evidence into the price used for a delayed SoC delta."""

    evidence = recent_charge_evidence(raw, now=now)
    if evidence is None:
        return None

    energy_wh = float(evidence["energy_wh"])
    duration_hours = float(evidence["duration_seconds"]) / 3600.0
    grid_energy_wh = float(evidence["grid_energy_wh"])
    pv_energy_wh = float(evidence["pv_energy_wh"])

    price = float(evidence["cost_eur"]) / (energy_wh / 1000.0)
    grid_part_w = grid_energy_wh / duration_hours
    pv_part_w = pv_energy_wh / duration_hours
    total_power_w = grid_part_w + pv_part_w

    if grid_energy_wh > 0.0 and pv_energy_wh > 0.0:
        source = "mixed_grid_pv_charge"
    else:
        source = str(evidence["source"])

    return ChargePricing(
        active=True,
        is_grid_charge=grid_part_w > max(60.0, total_power_w * 0.10),
        price_eur_kwh=float(price),
        source=source,
        grid_part_w=float(grid_part_w),
        pv_part_w=float(pv_part_w),
    )
