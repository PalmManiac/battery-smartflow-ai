"""Provider-independent economic accounting for normalized energy flows."""

from __future__ import annotations

from dataclasses import dataclass, fields
from math import isfinite
from typing import Any

from .market_price.models import MarketPrice, MarketPriceDirection


@dataclass(frozen=True, slots=True)
class EconomicEnergyFlows:
    """Energy deltas attributed during one accounting interval, in kWh."""

    grid_to_battery_kwh: float = 0.0
    pv_to_battery_kwh: float = 0.0
    grid_export_kwh: float = 0.0
    battery_to_home_kwh: float = 0.0
    battery_to_grid_kwh: float = 0.0

    def __post_init__(self) -> None:
        for field in fields(self):
            value = float(getattr(self, field.name))
            if not isfinite(value) or value < 0.0:
                raise ValueError(f"{field.name} must be a finite non-negative value")
            object.__setattr__(self, field.name, value)


@dataclass(frozen=True, slots=True)
class EconomicsSnapshot:
    """Calculated economic totals exposed to consumers such as sensors."""

    currency: str
    grid_charge_cost: float
    pv_opportunity_cost: float
    export_revenue: float
    avoided_grid_import_cost: float
    battery_benefit: float
    average_grid_charge_price: float | None
    average_pv_opportunity_value: float | None
    average_export_price: float | None
    average_battery_discharge_value: float | None

    def as_dict(self) -> dict[str, Any]:
        """Return stable result data without adding calculation logic to sensors."""

        return {field.name: getattr(self, field.name) for field in fields(self)}


@dataclass(slots=True)
class _EconomicsTotals:
    grid_charge_kwh: float = 0.0
    grid_charge_cost: float = 0.0
    pv_charge_kwh: float = 0.0
    pv_opportunity_cost: float = 0.0
    export_kwh: float = 0.0
    export_revenue: float = 0.0
    battery_discharge_kwh: float = 0.0
    battery_discharge_value: float = 0.0
    avoided_grid_import_cost: float = 0.0
    battery_benefit: float = 0.0


class EconomicsEngine:
    """Central calculator for daily and lifetime economic values.

    The caller supplies already normalized prices and energy deltas. Provider
    parsing, time integration, persistence and day-boundary detection remain
    outside this deliberately deterministic accounting core.
    """

    def __init__(self, *, currency: str) -> None:
        normalized_currency = str(currency).strip().upper()
        if not normalized_currency:
            raise ValueError("currency must not be empty")
        self._currency = normalized_currency
        self._daily = _EconomicsTotals()
        self._total = _EconomicsTotals()

    @property
    def currency(self) -> str:
        return self._currency

    def record(
        self,
        *,
        flows: EconomicEnergyFlows,
        import_price: MarketPrice,
        export_price: MarketPrice,
    ) -> None:
        """Calculate and add one interval to daily and lifetime totals."""

        import_value = self._price(
            import_price,
            MarketPriceDirection.IMPORT,
            required=bool(
                flows.grid_to_battery_kwh or flows.battery_to_home_kwh
            ),
        )
        export_value = self._price(
            export_price,
            MarketPriceDirection.EXPORT,
            required=bool(
                flows.pv_to_battery_kwh
                or flows.grid_export_kwh
                or flows.battery_to_grid_kwh
            ),
        )

        grid_charge_cost = flows.grid_to_battery_kwh * import_value
        pv_opportunity_cost = flows.pv_to_battery_kwh * export_value
        export_revenue = flows.grid_export_kwh * export_value
        avoided_cost = flows.battery_to_home_kwh * import_value
        battery_export_value = flows.battery_to_grid_kwh * export_value
        battery_discharge_kwh = (
            flows.battery_to_home_kwh + flows.battery_to_grid_kwh
        )
        battery_discharge_value = avoided_cost + battery_export_value
        battery_benefit = (
            battery_discharge_value - grid_charge_cost - pv_opportunity_cost
        )

        for totals in (self._daily, self._total):
            totals.grid_charge_kwh += flows.grid_to_battery_kwh
            totals.grid_charge_cost += grid_charge_cost
            totals.pv_charge_kwh += flows.pv_to_battery_kwh
            totals.pv_opportunity_cost += pv_opportunity_cost
            totals.export_kwh += flows.grid_export_kwh
            totals.export_revenue += export_revenue
            totals.battery_discharge_kwh += battery_discharge_kwh
            totals.battery_discharge_value += battery_discharge_value
            totals.avoided_grid_import_cost += avoided_cost
            totals.battery_benefit += battery_benefit

    def daily_snapshot(self) -> EconomicsSnapshot:
        return self._snapshot(self._daily)

    def total_snapshot(self) -> EconomicsSnapshot:
        return self._snapshot(self._total)

    def reset_daily(self) -> None:
        """Start a fresh daily bucket without changing lifetime totals."""

        self._daily = _EconomicsTotals()

    def _price(
        self,
        price: MarketPrice,
        direction: MarketPriceDirection,
        *,
        required: bool,
    ) -> float:
        if price.direction is not direction:
            raise ValueError(f"expected {direction.value} market price")
        if not required:
            return 0.0
        if not price.valid:
            raise ValueError(f"{direction.value} market price is not valid")
        if price.currency.strip().upper() != self._currency:
            raise ValueError("market price currency does not match engine currency")
        if price.unit != f"{self._currency}/kWh":
            raise ValueError("market price is not normalized to currency per kWh")
        value = float(price.current_price)
        if not isfinite(value):
            raise ValueError("market price must be finite")
        return value

    def _snapshot(self, totals: _EconomicsTotals) -> EconomicsSnapshot:
        return EconomicsSnapshot(
            currency=self._currency,
            grid_charge_cost=totals.grid_charge_cost,
            pv_opportunity_cost=totals.pv_opportunity_cost,
            export_revenue=totals.export_revenue,
            avoided_grid_import_cost=totals.avoided_grid_import_cost,
            battery_benefit=totals.battery_benefit,
            average_grid_charge_price=self._average(
                totals.grid_charge_cost, totals.grid_charge_kwh
            ),
            average_pv_opportunity_value=self._average(
                totals.pv_opportunity_cost, totals.pv_charge_kwh
            ),
            average_export_price=self._average(
                totals.export_revenue, totals.export_kwh
            ),
            average_battery_discharge_value=self._average(
                totals.battery_discharge_value, totals.battery_discharge_kwh
            ),
        )

    @staticmethod
    def _average(value: float, energy_kwh: float) -> float | None:
        return value / energy_kwh if energy_kwh > 0.0 else None
