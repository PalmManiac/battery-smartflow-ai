"""Provider-independent economic accounting for normalized energy flows."""

from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import date, datetime, time
from math import isfinite
from typing import Any, Mapping

from .market_price.models import MarketPrice, MarketPriceDirection
from .economic_efficiency import economic_efficiency_pct


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

    def as_dict(self) -> dict[str, float]:
        """Return persistence-safe numeric values."""

        return {field.name: getattr(self, field.name) for field in fields(self)}


@dataclass(frozen=True, slots=True)
class PriceableEnergyFlows:
    """Energy flows that can be valued with the currently available prices."""

    flows: EconomicEnergyFlows
    status: str


def priceable_energy_flows(
    flows: EconomicEnergyFlows,
    *,
    import_price: MarketPrice,
    export_price: MarketPrice,
) -> PriceableEnergyFlows:
    """Exclude only flows whose historical interval price is unavailable.

    Physical energy remains in ``EnergyAccumulator``. This projection prevents
    an unavailable price from stopping the coordinator without inventing a zero
    price or valuing the interval later with a different price.
    """

    import_available = import_price.valid
    export_available = export_price.valid
    if import_available and export_available:
        status = "accounted"
    elif not import_available and not export_available:
        status = "import_and_export_price_missing"
    elif not import_available:
        status = "import_price_missing"
    else:
        status = "export_price_missing"

    return PriceableEnergyFlows(
        flows=EconomicEnergyFlows(
            grid_to_battery_kwh=(
                flows.grid_to_battery_kwh if import_available else 0.0
            ),
            pv_to_battery_kwh=(
                flows.pv_to_battery_kwh if export_available else 0.0
            ),
            grid_export_kwh=(
                flows.grid_export_kwh if export_available else 0.0
            ),
            battery_to_home_kwh=(
                flows.battery_to_home_kwh if import_available else 0.0
            ),
            battery_to_grid_kwh=(
                flows.battery_to_grid_kwh if export_available else 0.0
            ),
        ),
        status=status,
    )


@dataclass(frozen=True, slots=True)
class EconomicPowerFlows:
    """Power attributed to economic flow directions, in watts."""

    grid_to_battery_w: float = 0.0
    pv_to_battery_w: float = 0.0
    grid_export_w: float = 0.0
    battery_to_home_w: float = 0.0
    battery_to_grid_w: float = 0.0

    def __post_init__(self) -> None:
        for field in fields(self):
            value = float(getattr(self, field.name))
            if not isfinite(value) or value < 0.0:
                raise ValueError(f"{field.name} must be a finite non-negative value")
            object.__setattr__(self, field.name, value)

    def to_energy(self, duration_seconds: float) -> EconomicEnergyFlows:
        """Convert this sample with E = P * t / 3,600,000."""

        factor = float(duration_seconds) / 3_600_000.0
        return EconomicEnergyFlows(
            grid_to_battery_kwh=self.grid_to_battery_w * factor,
            pv_to_battery_kwh=self.pv_to_battery_w * factor,
            grid_export_kwh=self.grid_export_w * factor,
            battery_to_home_kwh=self.battery_to_home_w * factor,
            battery_to_grid_kwh=self.battery_to_grid_w * factor,
        )


@dataclass(frozen=True, slots=True)
class EnergyAccumulatorSnapshot:
    """Persistent daily and lifetime energy-flow totals."""

    day: date
    daily: EconomicEnergyFlows
    total: EconomicEnergyFlows


@dataclass(frozen=True, slots=True)
class EnergyAccumulationResult:
    """Outcome of one sample, including gap-handling diagnostics."""

    energy: EconomicEnergyFlows
    daily_energy: EconomicEnergyFlows
    elapsed_seconds: float
    accounted_seconds: float
    status: str


class EnergyAccumulator:
    """Accumulate real-time power samples without restart double counting."""

    STATE_VERSION = 1

    def __init__(self, *, max_interval_seconds: float = 300.0) -> None:
        maximum = float(max_interval_seconds)
        if not isfinite(maximum) or maximum <= 0.0:
            raise ValueError("max_interval_seconds must be finite and positive")
        self._max_interval_seconds = maximum
        self._last_sample_at: datetime | None = None
        self._day: date | None = None
        self._daily = EconomicEnergyFlows()
        self._total = EconomicEnergyFlows()

    def add_sample(
        self,
        *,
        sampled_at: datetime,
        power: EconomicPowerFlows,
    ) -> EnergyAccumulationResult:
        """Add one power sample using its real interval from the prior sample."""

        if sampled_at.tzinfo is None or sampled_at.utcoffset() is None:
            raise ValueError("sampled_at must be timezone-aware")

        if self._last_sample_at is None:
            self._last_sample_at = sampled_at
            self._ensure_day(sampled_at.date())
            return self._result(status="baseline")

        elapsed = (sampled_at - self._last_sample_at).total_seconds()
        if elapsed <= 0.0:
            return self._result(elapsed=elapsed, status="duplicate_or_out_of_order")

        previous = self._last_sample_at
        self._last_sample_at = sampled_at
        accounted = min(elapsed, self._max_interval_seconds)
        status = "gap_limited" if accounted < elapsed else "accounted"

        # A normal coordinator interval that crosses midnight is divided so
        # the lifetime value keeps the full interval while the new daily bucket
        # receives only the part after midnight. A limited long gap is assigned
        # only to the current day and never backfilled across downtime.
        if previous.date() != sampled_at.date() and accounted == elapsed:
            midnight = datetime.combine(
                sampled_at.date(), time.min, tzinfo=sampled_at.tzinfo
            )
            previous_day_seconds = max(
                0.0, (midnight - previous).total_seconds()
            )
            current_day_seconds = max(
                0.0, (sampled_at - midnight).total_seconds()
            )
            previous_energy = power.to_energy(previous_day_seconds)
            current_energy = power.to_energy(current_day_seconds)
            self._ensure_day(previous.date())
            self._daily = self._add_flows(self._daily, previous_energy)
            self._total = self._add_flows(self._total, previous_energy)
            self._ensure_day(sampled_at.date())
            self._daily = self._add_flows(self._daily, current_energy)
            self._total = self._add_flows(self._total, current_energy)
            energy = self._add_flows(previous_energy, current_energy)
        else:
            self._ensure_day(sampled_at.date())
            energy = power.to_energy(accounted)
            self._daily = self._add_flows(self._daily, energy)
            self._total = self._add_flows(self._total, energy)

        return EnergyAccumulationResult(
            energy=energy,
            daily_energy=(
                current_energy
                if previous.date() != sampled_at.date() and accounted == elapsed
                else energy
            ),
            elapsed_seconds=elapsed,
            accounted_seconds=accounted,
            status=status,
        )

    def snapshot(self) -> EnergyAccumulatorSnapshot:
        """Return the current daily and lifetime energy totals."""

        day = self._day
        if day is None:
            raise RuntimeError("accumulator has not received a sample")
        return EnergyAccumulatorSnapshot(day=day, daily=self._daily, total=self._total)

    def to_state(self) -> dict[str, Any]:
        """Serialize totals as plain state for any StateStore adapter."""

        return {
            "version": self.STATE_VERSION,
            "day": self._day.isoformat() if self._day is not None else None,
            "daily": self._daily.as_dict(),
            "total": self._total.as_dict(),
            "last_sample_at": (
                self._last_sample_at.isoformat()
                if self._last_sample_at is not None
                else None
            ),
        }

    @classmethod
    def from_state(
        cls,
        raw: Mapping[str, Any] | None,
        *,
        max_interval_seconds: float = 300.0,
    ) -> EnergyAccumulator:
        """Restore totals but require a fresh post-restart time baseline."""

        accumulator = cls(max_interval_seconds=max_interval_seconds)
        if not isinstance(raw, Mapping) or raw.get("version") != cls.STATE_VERSION:
            return accumulator
        try:
            raw_day = raw.get("day")
            accumulator._day = date.fromisoformat(str(raw_day)) if raw_day else None
            accumulator._daily = cls._flows_from_state(raw.get("daily"))
            accumulator._total = cls._flows_from_state(raw.get("total"))
        except (TypeError, ValueError):
            return cls(max_interval_seconds=max_interval_seconds)

        # Deliberately ignore persisted last_sample_at. Accounting the gap from
        # shutdown until the first new reading would invent energy after restart.
        accumulator._last_sample_at = None
        return accumulator

    def _ensure_day(self, current_day: date) -> None:
        if self._day != current_day:
            self._day = current_day
            self._daily = EconomicEnergyFlows()

    def _result(
        self,
        *,
        elapsed: float = 0.0,
        status: str,
    ) -> EnergyAccumulationResult:
        return EnergyAccumulationResult(
            energy=EconomicEnergyFlows(),
            daily_energy=EconomicEnergyFlows(),
            elapsed_seconds=elapsed,
            accounted_seconds=0.0,
            status=status,
        )

    @staticmethod
    def _add_flows(
        left: EconomicEnergyFlows,
        right: EconomicEnergyFlows,
    ) -> EconomicEnergyFlows:
        return EconomicEnergyFlows(
            **{
                field.name: getattr(left, field.name) + getattr(right, field.name)
                for field in fields(EconomicEnergyFlows)
            }
        )

    @staticmethod
    def _flows_from_state(raw: Any) -> EconomicEnergyFlows:
        if not isinstance(raw, Mapping):
            raise ValueError("energy flow state must be a mapping")
        return EconomicEnergyFlows(
            **{
                field.name: raw.get(field.name, 0.0)
                for field in fields(EconomicEnergyFlows)
            }
        )


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

    def record_grid_flows(
        self,
        *,
        flows: EconomicEnergyFlows,
        import_price: MarketPrice,
        export_price: MarketPrice,
        daily_flows: EconomicEnergyFlows | None = None,
    ) -> None:
        """Record the grid-related monetary flows defined by issue #248."""

        daily = daily_flows if daily_flows is not None else flows
        self._record_grid_totals(
            self._daily,
            daily,
            import_price=import_price,
            export_price=export_price,
        )
        self._record_grid_totals(
            self._total,
            flows,
            import_price=import_price,
            export_price=export_price,
        )

    def record_battery_value_flows(
        self,
        *,
        flows: EconomicEnergyFlows,
        import_price: MarketPrice,
        export_price: MarketPrice,
        daily_flows: EconomicEnergyFlows | None = None,
    ) -> None:
        """Record PV opportunity cost and attributable battery benefit.

        Battery benefit is defined as avoided grid-import cost minus grid
        charging cost minus PV opportunity cost plus only the export revenue
        attributable to battery discharge. Total export revenue is deliberately
        not added here because ``record_grid_flows`` already records it and it
        may contain ordinary PV export that is not a battery benefit.
        """

        daily = daily_flows if daily_flows is not None else flows
        self._record_battery_value_totals(
            self._daily,
            daily,
            import_price=import_price,
            export_price=export_price,
        )
        self._record_battery_value_totals(
            self._total,
            flows,
            import_price=import_price,
            export_price=export_price,
        )

    def to_state(self) -> dict[str, Any]:
        """Serialize daily and lifetime monetary totals."""

        return {
            "version": 1,
            "currency": self._currency,
            "daily": self._totals_to_state(self._daily),
            "total": self._totals_to_state(self._total),
        }

    @classmethod
    def from_state(
        cls,
        raw: Mapping[str, Any] | None,
        *,
        currency: str,
    ) -> EconomicsEngine:
        """Restore persisted monetary totals for the active currency."""

        engine = cls(currency=currency)
        if (
            not isinstance(raw, Mapping)
            or raw.get("version") != 1
            or str(raw.get("currency", "")).strip().upper() != engine.currency
        ):
            return engine
        try:
            engine._daily = cls._totals_from_state(raw.get("daily"))
            engine._total = cls._totals_from_state(raw.get("total"))
        except (TypeError, ValueError):
            return cls(currency=currency)
        return engine

    def daily_snapshot(self) -> EconomicsSnapshot:
        return self._snapshot(self._daily)

    def total_snapshot(self) -> EconomicsSnapshot:
        return self._snapshot(self._total)

    def total_economic_efficiency_pct(self) -> float | None:
        """Return the since-start cost-recovery ratio from valued flows."""
        return economic_efficiency_pct(
            grid_charge_cost=self._total.grid_charge_cost,
            pv_opportunity_cost=self._total.pv_opportunity_cost,
            battery_benefit=self._total.battery_benefit,
            charged_energy_kwh=(
                self._total.grid_charge_kwh + self._total.pv_charge_kwh
            ),
            discharged_energy_kwh=self._total.battery_discharge_kwh,
        )

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

    def _record_grid_totals(
        self,
        totals: _EconomicsTotals,
        flows: EconomicEnergyFlows,
        *,
        import_price: MarketPrice,
        export_price: MarketPrice,
    ) -> None:
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
            required=bool(flows.grid_export_kwh),
        )
        totals.grid_charge_kwh += flows.grid_to_battery_kwh
        totals.grid_charge_cost += flows.grid_to_battery_kwh * import_value
        totals.export_kwh += flows.grid_export_kwh
        totals.export_revenue += flows.grid_export_kwh * export_value
        totals.battery_discharge_kwh += flows.battery_to_home_kwh
        avoided_cost = flows.battery_to_home_kwh * import_value
        totals.battery_discharge_value += avoided_cost
        totals.avoided_grid_import_cost += avoided_cost

    def _record_battery_value_totals(
        self,
        totals: _EconomicsTotals,
        flows: EconomicEnergyFlows,
        *,
        import_price: MarketPrice,
        export_price: MarketPrice,
    ) -> None:
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
                flows.pv_to_battery_kwh or flows.battery_to_grid_kwh
            ),
        )
        grid_charge_cost = flows.grid_to_battery_kwh * import_value
        pv_opportunity_cost = flows.pv_to_battery_kwh * export_value
        avoided_cost = flows.battery_to_home_kwh * import_value
        battery_export_value = flows.battery_to_grid_kwh * export_value

        totals.pv_charge_kwh += flows.pv_to_battery_kwh
        totals.pv_opportunity_cost += pv_opportunity_cost
        totals.battery_discharge_kwh += flows.battery_to_grid_kwh
        totals.battery_discharge_value += battery_export_value
        totals.battery_benefit += (
            avoided_cost
            - grid_charge_cost
            - pv_opportunity_cost
            + battery_export_value
        )

    @staticmethod
    def _totals_to_state(totals: _EconomicsTotals) -> dict[str, float]:
        return {
            field.name: float(getattr(totals, field.name))
            for field in fields(_EconomicsTotals)
        }

    @staticmethod
    def _totals_from_state(raw: Any) -> _EconomicsTotals:
        if not isinstance(raw, Mapping):
            raise ValueError("economics totals must be a mapping")
        values: dict[str, float] = {}
        for field in fields(_EconomicsTotals):
            value = float(raw.get(field.name, 0.0))
            if not isfinite(value):
                raise ValueError("economics totals must be finite")
            values[field.name] = value
        return _EconomicsTotals(**values)
