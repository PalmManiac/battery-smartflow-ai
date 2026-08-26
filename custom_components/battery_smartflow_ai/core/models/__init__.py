"""Canonical platform-independent models shared across the BSFAI core."""

from .device import DeviceCapabilities
from .market import (
    MarketPrice,
    MarketPriceDirection,
    MarketPriceForecast,
    MarketPricePoint,
    MarketPriceValidity,
)
from .regulation import (
    AutomaticStrategyResult,
    ChargeSourceAllocation,
    DeviceCommand,
    GridHistoryState,
    ModeArbiterResult,
    PowerControllerResult,
    RegulationRuntimeState,
    StrategyContext,
    StrategyIntent,
)
from .states import (
    AdditionalBatteryState,
    BatteryState,
    GridState,
    MeasuredValue,
    OffGridState,
    PVState,
    ValueValidity,
)
from .strategy import (
    ChargeCommitState,
    StrategicState,
    StrategyDecision,
    VisibleState,
)

__all__ = [
    "AdditionalBatteryState",
    "AutomaticStrategyResult",
    "BatteryState",
    "ChargeCommitState",
    "ChargeSourceAllocation",
    "DeviceCapabilities",
    "DeviceCommand",
    "GridHistoryState",
    "GridState",
    "MarketPrice",
    "MarketPriceDirection",
    "MarketPriceForecast",
    "MarketPricePoint",
    "MarketPriceValidity",
    "MeasuredValue",
    "ModeArbiterResult",
    "OffGridState",
    "PVState",
    "PowerControllerResult",
    "RegulationRuntimeState",
    "StrategicState",
    "StrategyContext",
    "StrategyDecision",
    "StrategyIntent",
    "ValueValidity",
    "VisibleState",
]
