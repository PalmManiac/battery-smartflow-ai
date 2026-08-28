"""Canonical platform-independent models shared across the BSFAI core."""

from .device import (
    CommandExecutionResult,
    CommandExecutionStatus,
    DeviceCapabilities,
    DeviceProfile,
)
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
from .runtime import AiMode, DecisionContext, RuntimeSnapshot
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
    "AiMode",
    "AutomaticStrategyResult",
    "BatteryState",
    "ChargeCommitState",
    "ChargeSourceAllocation",
    "CommandExecutionResult",
    "CommandExecutionStatus",
    "DeviceCapabilities",
    "DeviceProfile",
    "DeviceCommand",
    "DecisionContext",
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
    "RuntimeSnapshot",
    "StrategicState",
    "StrategyContext",
    "StrategyDecision",
    "StrategyIntent",
    "ValueValidity",
    "VisibleState",
]
