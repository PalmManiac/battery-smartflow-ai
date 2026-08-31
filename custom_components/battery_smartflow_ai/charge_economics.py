"""Economic attribution of battery charging energy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping


TRADE_SOC_MIN_RESET_CONFIRM_CYCLES = 3


def trade_soc_min_reset_state(
    *,
    soc: float,
    soc_min: float,
    previous_count: int,
    previously_confirmed: bool,
    required_cycles: int = TRADE_SOC_MIN_RESET_CONFIRM_CYCLES,
) -> tuple[int, bool]:
    """Confirm a real SoC-min event without trusting one transient sample.

    Some battery integrations briefly expose 0 percent while their entities
    refresh. Clearing the economic charge ledger on that single sample loses
    the average charge price permanently. A real low-SoC condition remains
    eligible after a short sequence of consecutive update cycles.
    """

    if float(soc) > float(soc_min):
        return 0, False

    required = max(1, int(required_cycles))
    if previously_confirmed:
        return required, True

    count = min(required, max(0, int(previous_count)) + 1)
    return count, count >= required


def resolve_feed_in_tariff(
    *,
    data: Mapping[str, Any],
    options: Mapping[str, Any],
    default: float = 0.0,
) -> float:
    """Resolve the tariff without allowing stale options to shadow config data."""

    if "feed_in_tariff" in data:
        value = data.get("feed_in_tariff")
    elif "feed_in_tariff" in options:
        value = options.get("feed_in_tariff")
    else:
        value = default

    try:
        return max(0.0, float(value if value is not None else default))
    except (TypeError, ValueError):
        return max(0.0, float(default))


@dataclass(frozen=True)
class ChargePricing:
    """Economic source and price of an active battery charge sample."""

    active: bool
    is_grid_charge: bool
    price_per_kwh: float
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
        price_per_kwh=0.0,
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
    native_pv_w: float = 0.0,
    native_pv_valid: bool = False,
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
            price_per_kwh=pv_price,
            source="pv_surplus_export",
            grid_part_w=0.0,
            pv_part_w=charge_w,
        )

    # During active PV-surplus charging, short control/sensor delays can create
    # a small import pulse even though nearly all battery power still comes
    # from PV. Do not let those insignificant pulses make the applied price
    # jump between the feed-in tariff and a mixed grid/PV price. A material
    # grid share is still priced normally below.
    pv_surplus_import_tolerance_w = max(
        60.0,
        min(100.0, charge_w * 0.10),
    )
    pv_surplus_dominant = bool(
        decision_reason == "pv_surplus_charge"
        and import_w <= pv_surplus_import_tolerance_w
    )

    if import_w <= 60.0 or pv_surplus_dominant:
        return ChargePricing(
            active=True,
            is_grid_charge=False,
            price_per_kwh=pv_price,
            source="pv_or_free_low_import",
            grid_part_w=0.0,
            pv_part_w=charge_w,
        )

    if price_now is None:
        return ChargePricing(
            active=True,
            is_grid_charge=False,
            price_per_kwh=pv_price,
            source="price_missing_assume_pv_opportunity",
            grid_part_w=0.0,
            pv_part_w=charge_w,
        )

    native_pv_part_w = (
        min(charge_w, max(0.0, float(native_pv_w or 0.0)))
        if bool(native_pv_valid)
        else 0.0
    )
    grid_part_w = min(import_w, max(0.0, charge_w - native_pv_part_w))
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
        price_per_kwh=float(mixed_price),
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
        # V4.5.0 reads the former EUR-named field so pending evidence created
        # before the update remains usable. Numeric values are preserved as-is;
        # there is no exchange-rate conversion.
        cost = float(raw.get("cost", raw.get("cost_eur", 0.0)) or 0.0)
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
        "cost": cost,
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
        "cost": 0.0,
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
        "cost": float(existing["cost"])
        + (energy_wh / 1000.0) * float(pricing.price_per_kwh),
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

    price = float(evidence["cost"]) / (energy_wh / 1000.0)
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
        price_per_kwh=float(price),
        source=source,
        grid_part_w=float(grid_part_w),
        pv_part_w=float(pv_part_w),
    )
