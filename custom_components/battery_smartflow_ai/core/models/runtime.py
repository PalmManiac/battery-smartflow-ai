"""Central normalized runtime input for BSFAI core decisions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from .device import DeviceCapabilities
from .market import MarketPrice
from .regulation import AutomaticStrategyResult
from .states import (
    AdditionalBatteryState,
    BatteryState,
    GridState,
    MeasuredValue,
    OffGridState,
    PVState,
    ValueValidity,
)


AiMode = Literal["automatic", "summer", "manual"]


@dataclass
class RuntimeSnapshot:
    """One platform-neutral, normalized input for a core decision cycle.

    The flat fields preserve the established Decision Engine contract while
    typed views expose the shared models introduced by Issue #267. This avoids
    a second aggregate context during the incremental V4.7 migration.
    """

    now: datetime

    soc: float
    soc_min: float
    soc_max: float

    emergency_soc: float
    emergency_charge_w: float

    max_charge_w: float
    max_discharge_w: float

    grid_import_w: float
    grid_export_w: float
    pv_w: float
    house_load_w: float

    avg_charge_price: float | None
    expensive_threshold: float
    very_expensive_threshold: float
    profit_margin_pct: float

    ai_mode: AiMode
    manual_action: str | None
    season: Literal["winter", "summer"]

    profile: dict[str, Any]
    prev_discharge_w: float
    prev_charge_w: float

    battery_capacity_kwh: float
    battery_discharge_w: float = 0.0
    last_output_w: float = 0.0

    additional_battery_charge_w: float = 0.0
    additional_battery_discharge_w: float = 0.0
    pv_charge_start_export_w: float = 80.0

    peak_factor: float = 1.35
    valley_factor: float = 0.85
    very_cheap_price: float | None = None

    cell_voltage_emergency_active: bool = False
    forecast: Any | None = None
    learned_charge_plan: Any | None = None
    learned_planning_enabled: bool = False
    import_market_price: MarketPrice | None = None
    export_market_price: MarketPrice | None = None

    pv_charge_start_counter: int = 0
    pv_charge_stop_counter: int = 0
    forecast_wait_block_counter: int = 0
    pv_charge_latched: bool = False

    discharge_blocked_by_soc_min: bool = False
    cell_voltage_discharge_blocked: bool = False

    pv_houseload_passthrough_active: bool = False
    pv_houseload_passthrough_target_w: float = 0.0
    pv_houseload_passthrough_stop_reason: str = "none"

    offgrid_power_w: float = 0.0
    offgrid_mode: str = "not_configured"
    offgrid_available: bool = False
    offgrid_active: bool = False
    offgrid_load_active: bool = False
    offgrid_source_active: bool = False

    automatic_strategy_active: bool = False
    automatic_weighting: str = "inactive"
    automatic_pv_weight: float = 0.0
    automatic_price_weight: float = 0.0
    automatic_reserve_weight: float = 0.0
    automatic_forecast_weight: float = 0.0
    automatic_discharge_allowed: bool = False
    automatic_discharge_reason: str = "not_evaluated"
    automatic_peak_reserve_allowed: bool = False
    automatic_peak_reserve_reason: str = "not_evaluated"
    automatic_valley_charge_allowed: bool = False
    automatic_valley_charge_reason: str = "not_evaluated"
    automatic_planning_allowed: bool = False
    automatic_planning_reason: str = "not_evaluated"

    grid_sensor_configured: bool = True
    grid_sensor_valid: bool = True
    pv_sensor_valid: bool = True
    soc_limits_valid: bool = True
    power_limits_valid: bool = True

    @staticmethod
    def _measured(
        value: float,
        *,
        valid: bool,
        observed_at: datetime,
        invalid_status: ValueValidity = ValueValidity.INVALID,
    ) -> MeasuredValue[float]:
        if valid:
            return MeasuredValue.available(float(value), observed_at=observed_at)
        return MeasuredValue.absent(invalid_status, observed_at=observed_at)

    @property
    def battery(self) -> BatteryState:
        """Return the normalized battery view for this cycle."""

        return BatteryState(
            soc_pct=self._measured(
                self.soc,
                valid=self.soc_limits_valid,
                observed_at=self.now,
            ),
            charge_power_w=MeasuredValue.available(
                max(0.0, self.prev_charge_w),
                observed_at=self.now,
            ),
            discharge_power_w=MeasuredValue.available(
                max(0.0, self.battery_discharge_w),
                observed_at=self.now,
            ),
        )

    @property
    def grid(self) -> GridState:
        """Return normalized grid flows with explicit sensor validity."""

        invalid_status = (
            ValueValidity.INVALID
            if self.grid_sensor_configured
            else ValueValidity.MISSING
        )
        return GridState(
            import_power_w=self._measured(
                self.grid_import_w,
                valid=self.grid_sensor_valid,
                observed_at=self.now,
                invalid_status=invalid_status,
            ),
            export_power_w=self._measured(
                self.grid_export_w,
                valid=self.grid_sensor_valid,
                observed_at=self.now,
                invalid_status=invalid_status,
            ),
        )

    @property
    def pv(self) -> PVState:
        """Return normalized PV and derived house-load measurements."""

        return PVState(
            production_power_w=self._measured(
                self.pv_w,
                valid=self.pv_sensor_valid,
                observed_at=self.now,
            ),
            house_load_power_w=MeasuredValue.available(
                max(0.0, self.house_load_w),
                observed_at=self.now,
            ),
        )

    @property
    def offgrid(self) -> OffGridState:
        """Return optional off-grid state without exposing entity metadata."""

        if not self.offgrid_available:
            return OffGridState(
                active=MeasuredValue.absent(
                    ValueValidity.MISSING,
                    observed_at=self.now,
                ),
                output_power_w=MeasuredValue.absent(
                    ValueValidity.MISSING,
                    observed_at=self.now,
                ),
            )
        return OffGridState(
            active=MeasuredValue.available(self.offgrid_active, observed_at=self.now),
            output_power_w=MeasuredValue.available(
                max(0.0, self.offgrid_power_w),
                observed_at=self.now,
            ),
        )

    @property
    def additional_battery(self) -> AdditionalBatteryState:
        """Return normalized additional-battery flows."""

        return AdditionalBatteryState(
            charge_power_w=MeasuredValue.available(
                max(0.0, self.additional_battery_charge_w),
                observed_at=self.now,
            ),
            discharge_power_w=MeasuredValue.available(
                max(0.0, self.additional_battery_discharge_w),
                observed_at=self.now,
            ),
        )

    @property
    def capabilities(self) -> DeviceCapabilities:
        """Return the manufacturer-neutral capability subset of the profile."""

        return DeviceCapabilities.from_profile(self.profile)

    @property
    def automatic_strategy(self) -> AutomaticStrategyResult:
        """Return the typed AutomaticStrategy result carried by the snapshot."""

        return AutomaticStrategyResult(
            active=self.automatic_strategy_active,
            weighting=self.automatic_weighting,  # type: ignore[arg-type]
            pv_weight=self.automatic_pv_weight,
            price_weight=self.automatic_price_weight,
            reserve_weight=self.automatic_reserve_weight,
            forecast_weight=self.automatic_forecast_weight,
            reason=self.automatic_discharge_reason,
            metadata={
                "automatic_discharge_allowed": self.automatic_discharge_allowed,
                "automatic_peak_reserve_allowed": self.automatic_peak_reserve_allowed,
                "automatic_valley_charge_allowed": self.automatic_valley_charge_allowed,
                "automatic_planning_allowed": self.automatic_planning_allowed,
            },
        )


# Compatibility name for existing Decision Engine tests and callers.
DecisionContext = RuntimeSnapshot
