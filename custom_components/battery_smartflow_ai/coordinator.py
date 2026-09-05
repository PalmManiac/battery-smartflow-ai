from __future__ import annotations

import logging
from functools import partial
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .ai_status import map_ai_status
from .const import (
    DOMAIN,
    UPDATE_INTERVAL,
    INTEGRATION_VERSION,
    # config keys
    CONF_SOC_ENTITY,
    CONF_PV_ENTITY,
    CONF_NATIVE_PV_ENTITY,
    CONF_PV_FORECAST_TODAY_ENTITY,
    CONF_PV_FORECAST_TOMORROW_ENTITY,
    CONF_PRICE_EXPORT_ENTITY,
    CONF_PRICE_NOW_ENTITY,
    CONF_DYNAMIC_FEED_IN_PRICE_ENTITY,
    CONF_AC_MODE_ENTITY,
    CONF_INPUT_LIMIT_ENTITY,
    CONF_OUTPUT_LIMIT_ENTITY,
    CONF_GRID_MODE,
    CONF_GRID_POWER_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_GRID_EXPORT_ENTITY,
    CONF_SOC_LIMIT_ENTITY,
    CONF_PACK_CAPACITY_KWH,
    CONF_BATTERY_AC_POWER_ENTITY,
    CONF_ADDITIONAL_BATTERY_CHARGE_ENTITY,
    CONF_ADDITIONAL_BATTERY_DISCHARGE_ENTITY,
    CONF_DEVICE_PROFILE,
    CONF_PROFILE_OVERRIDES,
    CONF_INSTALLED_PV_WP,
    CONF_EXPERT_MODE_ENABLED,
    CONF_FEED_IN_TARIFF,
    CONF_CELL_VOLTAGE_PROTECTION_ENABLED,
    CONF_OFFGRID_POWER_ENTITY,
    CONF_OFFGRID_MODE_ENTITY,
    LOWEST_CELL_VOLTAGE_CONFIG_KEYS,
    GRID_MODE_NONE,
    GRID_MODE_SINGLE,
    GRID_MODE_SPLIT,
    # settings keys (entry.options)
    SETTING_SOC_MIN,
    SETTING_SOC_MAX,
    SETTING_MAX_CHARGE,
    SETTING_MAX_DISCHARGE,
    SETTING_PRICE_THRESHOLD,
    SETTING_VERY_EXPENSIVE_THRESHOLD,
    SETTING_EMERGENCY_SOC,
    SETTING_EMERGENCY_CHARGE,
    SETTING_PROFIT_MARGIN_PCT,
    SETTING_BATTERY_PACKS,
    SETTING_PEAK_FACTOR,
    SETTING_VALLEY_FACTOR,
    SETTING_CELL_VOLTAGE_WARNING,
    SETTING_CELL_VOLTAGE_CUTOFF,
    SETTING_CELL_VOLTAGE_RESUME,
    SETTING_PV_CHARGE_START_EXPORT_W,
    SETTING_FORECAST_BASE_LOAD,
    SETTING_LEARNED_PLANNING_ENABLED,
    # defaults
    DEFAULT_SOC_MIN,
    DEFAULT_SOC_MAX,
    DEFAULT_MAX_CHARGE,
    DEFAULT_MAX_DISCHARGE,
    DEFAULT_EMERGENCY_SOC,
    DEFAULT_EMERGENCY_CHARGE,
    DEFAULT_PROFIT_MARGIN_PCT,
    DEFAULT_BATTERY_PACKS,
    DEFAULT_PEAK_FACTOR,
    DEFAULT_VALLEY_FACTOR,
    DEFAULT_DEVICE_PROFILE,
    DEFAULT_INSTALLED_PV_WP,
    DEFAULT_EXPERT_MODE_ENABLED,
    DEFAULT_FEED_IN_TARIFF,
    DEFAULT_CELL_VOLTAGE_PROTECTION_ENABLED,
    DEFAULT_CELL_VOLTAGE_WARNING,
    DEFAULT_CELL_VOLTAGE_CUTOFF,
    DEFAULT_CELL_VOLTAGE_RESUME,
    DEFAULT_PV_CHARGE_START_EXPORT_W,
    DEFAULT_FORECAST_BASE_LOAD,
    DEFAULT_LEARNED_PLANNING_ENABLED,
    # modes
    AI_MODE_AUTOMATIC,
    AI_MODE_SUMMER,
    AI_MODE_MANUAL,
    normalize_ai_mode,
    MANUAL_STANDBY,
    # statuses
    STATUS_OK,
    STATUS_SENSOR_INVALID,
    AI_STATUS_STANDBY,
    RECO_STANDBY,
    RECO_CHARGE,
    RECO_DISCHARGE,
    RECO_EMERGENCY,
    ZENDURE_MODE_INPUT,
    ZENDURE_MODE_OUTPUT,
)
from .device_profiles import get_device_profile, merge_profile_with_overrides
from .decision_engine import (
    advance_pv_charge_hysteresis,
    compute_pv_attributable_export_w,
    DecisionEngine,
    DecisionResult,
)
from .core.models.runtime import RuntimeSnapshot
from .forecast import build_forecast_summary
from .learned_planning import (
    LearningSample,
    LearningChargePowerSample,
    MIN_LEARNED_CHARGE_POWER_SAMPLE_W,
    ROLLING_DAYS,
    build_learned_charge_plan,
    build_profile_diagnostics,
    build_slot_model,
    evaluate_readiness,
    learned_typical_charge_power_w,
)
from .grid_history import GridHistory, build_grid_history_config
from .charge_source_allocator import ChargeSourceAllocator
from .charge_commit_policy import (
    current_inactive_commit_abort_reason,
    learned_commit_is_forced,
    learned_commit_price_phase,
    learned_commit_should_yield_to_discharge,
    learned_plan_may_complete_active_commit,
    preserved_learned_commit_power,
)
from .battery_protection import (
    cell_voltage_emergency_minimum_elapsed,
    next_cell_voltage_discharge_lock_state,
    next_cell_voltage_emergency_state,
)
from .charge_economics import (
    add_charge_evidence,
    classify_charge_pricing,
    pricing_from_charge_evidence,
    recent_charge_evidence,
    resolve_feed_in_tariff,
    trade_soc_min_reset_state,
)
from .economics import (
    EconomicPowerFlows,
    EconomicsEngine,
    EnergyAccumulator,
    priceable_energy_flows,
)
from .automatic_strategy import (
    AutomaticStrategy,
    economic_discharge_continuation_reason,
    forecast_supports_early_pv_passthrough,
    maintain_active_economic_discharge,
)
from .strategy_adapter import decision_to_strategy_intent
from .strategy_state import ChargeCommitState
from .mode_arbiter import ModeArbiter, build_mode_arbiter_config
from .regulation_models import RegulationRuntimeState
from .core.models import CommandExecutionResult, DeviceCapabilities, DeviceCommand
from .core.ports import Clock, DeviceBackend, DeviceBackendExecutionError
from .regulation_power_controller import (
    RegulationPowerController,
    build_regulation_power_config,
)
from .device_command import DeviceCommandBuilder, clamp_number_power_request
from .command_execution_state import confirmed_command_state_updates
from .adapters.home_assistant.device_backend import (
    HomeAssistantEntityBackend,
)
from .adapters.home_assistant.clock import HomeAssistantClock
from .adapters.home_assistant.state_store import HomeAssistantStateStore
from .v5_migration import migrate_persisted_v47_state
from .command_effectiveness import (
    CommandEffectivenessConfig,
    CommandEffectivenessState,
    evaluate_command_effectiveness,
    record_effectiveness_retry,
)
from .debug_recorder import DebugRecorder
from .debug_exporter import DebugExportError, export_debug_package
from .debug_sample_builder import build_debug_sample
from .price_currency import (
    PriceCurrency,
    migrate_legacy_price_fields,
    price_input_profile,
    resolve_price_currency,
)
from .price_math import comparison_tolerance
from .market_price import (
    ExportMarketPriceResolver,
    GenericStatePriceSource,
    LegacyImportForecastAdapter,
    MarketPrice,
    MarketPriceDirection,
    MarketPriceSourceAdapter,
    NumericPriceNormalizer,
)
from .manual_standby import active_power_direction

_LOGGER = logging.getLogger(__name__)

STORE_VERSION = 1
ACTIVE_STATUS_DISPLAY_HOLD_S = 60

CHARGE_COMMIT_PRICE_VALID_MINUTES = 20

# V4.3.0-dev5.8.3:
# Treat a strategic AC charge target as practically reached when the battery
# is close to the target but has continuously stopped accepting charge.
CHARGE_COMMIT_BMS_STALL_TARGET_GAP_PCT = 3.0
CHARGE_COMMIT_BMS_STALL_MAX_CHARGE_W = 25.0
CHARGE_COMMIT_BMS_STALL_SECONDS = 300.0

# V4.3.0-dev5.8.4:
# An active strategic charge may be considered economically complete when
# the battery is already very close to its near-full target and the current
# electricity price has entered the profitable discharge range.
CHARGE_COMMIT_DISCHARGE_WINDOW_TARGET_GAP_PCT = 3.0

CHARGE_COMMIT_PLANNING_REASONS = {
    "planning_latest_start",
    "planning_forecast_poor",
    "planning_forecast_mixed",
    "planning_forecast_reality_override",
}

CHARGE_COMMIT_LEARNED_REASONS = {
    "learned_charge_window_active",
    "learned_charge_window_latest_start_reached",
    "learned_charge_window_deadline_too_close_start_now",
}

CHARGE_COMMIT_PRICE_REASONS = {
    "very_cheap_force_charge",
    "valley_boost_charge",
    "valley_boost_charge_mixed_forecast",
    "valley_opportunity_charge",
    "valley_opportunity_charge_mixed_forecast",
}

CHARGE_COMMIT_RESERVE_REASONS = {
    "summer_peak_reserve_charge",
}

CHARGE_COMMIT_SOURCE_REASONS = (
    CHARGE_COMMIT_PLANNING_REASONS
    | CHARGE_COMMIT_LEARNED_REASONS
    | CHARGE_COMMIT_PRICE_REASONS
    | CHARGE_COMMIT_RESERVE_REASONS
)

SEASON_COUNTER_MIN = -100
SEASON_COUNTER_MAX = 100

# V4.2.3-Beta6:
# Do not evaluate winter signals in the evening/night.
# Low PV and low export after sunset must not count as "winter".
SEASON_WINTER_EVALUATION_START_HOUR = 10.0
SEASON_WINTER_EVALUATION_END_HOUR = 16.0


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
        
def _clamp_season_counter(value: Any) -> int:
    """Limit the season hysteresis counter to a sane range.

    The counter is only used as hysteresis for the seasonal diagnostic context.
    It must not grow indefinitely after months of operation.
    """
    try:
        counter = int(value or 0)
    except Exception:
        counter = 0

    return max(SEASON_COUNTER_MIN, min(SEASON_COUNTER_MAX, counter))


@dataclass
class SelectedEntities:
    soc: str
    pv: str
    native_pv: str | None
    pv_forecast_today: str | None
    pv_forecast_tomorrow: str | None
    price_export: str | None
    price_now: str | None
    dynamic_feed_in_price: str | None
    ac_mode: str
    input_limit: str
    output_limit: str
    battery_ac_power: str
    additional_battery_charge: str | None
    additional_battery_discharge: str | None
    soc_limit: str | None
    grid_mode: str
    grid_power: str | None
    grid_import: str | None
    grid_export: str | None
    lowest_cell_voltage_entities: tuple[str | None, ...]
    offgrid_power: str | None
    offgrid_mode: str | None


class ZendureSmartFlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.price_currency: PriceCurrency = resolve_price_currency(
            getattr(hass.config, "currency", None)
        )

        if self.price_currency.used_fallback:
            _LOGGER.warning(
                "Home Assistant has no valid system currency; using %s for "
                "Battery SmartFlow AI price units",
                self.price_currency.code,
            )
        self.price_comparison_tolerance = comparison_tolerance(
            price_input_profile(self.price_currency).step
        )

        self.device_profile_key = (
            entry.options.get(CONF_DEVICE_PROFILE)
            or entry.data.get(CONF_DEVICE_PROFILE)
            or DEFAULT_DEVICE_PROFILE
        )

        self._device_profile = get_device_profile(self.device_profile_key)
        self._device_profile_cfg = self._device_profile.as_legacy_mapping()

        self.runtime_settings: dict[str, float] = dict(entry.options)

        self.entities = SelectedEntities(
            soc=str(entry.data[CONF_SOC_ENTITY]),
            pv=str(entry.data[CONF_PV_ENTITY]),
            native_pv=entry.data.get(CONF_NATIVE_PV_ENTITY),
            pv_forecast_today=entry.data.get(CONF_PV_FORECAST_TODAY_ENTITY),
            pv_forecast_tomorrow=entry.data.get(CONF_PV_FORECAST_TOMORROW_ENTITY),
            battery_ac_power=str(
                entry.options.get(CONF_BATTERY_AC_POWER_ENTITY)
                or entry.data.get(CONF_BATTERY_AC_POWER_ENTITY, "")
            ),
            additional_battery_charge=entry.data.get(CONF_ADDITIONAL_BATTERY_CHARGE_ENTITY),
            additional_battery_discharge=entry.data.get(CONF_ADDITIONAL_BATTERY_DISCHARGE_ENTITY),
            price_export=entry.data.get(CONF_PRICE_EXPORT_ENTITY),
            price_now=entry.data.get(CONF_PRICE_NOW_ENTITY),
            dynamic_feed_in_price=entry.data.get(
                CONF_DYNAMIC_FEED_IN_PRICE_ENTITY
            ),
            ac_mode=str(entry.data[CONF_AC_MODE_ENTITY]),
            input_limit=str(entry.data[CONF_INPUT_LIMIT_ENTITY]),
            output_limit=str(entry.data[CONF_OUTPUT_LIMIT_ENTITY]),
            soc_limit=entry.data.get(CONF_SOC_LIMIT_ENTITY),
            grid_mode=str(entry.data.get(CONF_GRID_MODE, GRID_MODE_NONE)),
            grid_power=entry.data.get(CONF_GRID_POWER_ENTITY),
            grid_import=entry.data.get(CONF_GRID_IMPORT_ENTITY),
            grid_export=entry.data.get(CONF_GRID_EXPORT_ENTITY),
            offgrid_power=entry.data.get(CONF_OFFGRID_POWER_ENTITY),
            offgrid_mode=entry.data.get(CONF_OFFGRID_MODE_ENTITY),
            lowest_cell_voltage_entities=tuple(
                entry.options.get(key) for key in LOWEST_CELL_VOLTAGE_CONFIG_KEYS
            ),
        )

        self.runtime_mode: dict[str, Any] = {
            "ai_mode": AI_MODE_AUTOMATIC,
            "manual_action": MANUAL_STANDBY,
        }

        self._engine = DecisionEngine()
        self._debug_recorder = DebugRecorder(integration_version=INTEGRATION_VERSION)
        self._debug_last_package: str | None = None
        self._debug_last_error: str | None = None
        self._automatic_strategy = AutomaticStrategy()
        self._charge_source_allocator = ChargeSourceAllocator()
        self._energy_accumulator = EnergyAccumulator()
        self._economics_engine = EconomicsEngine(
            currency=self.price_currency.code
        )
        
        self._grid_history = GridHistory(
            build_grid_history_config(self._get_active_profile())
        )
        
        self._mode_arbiter = ModeArbiter(
            build_mode_arbiter_config(
                self._get_active_profile(),
                self._device_profile.capabilities,
            )
        )
        
        self._regulation_power_controller = RegulationPowerController(
            build_regulation_power_config(
                self._get_active_profile(),
                capabilities=self._device_profile.capabilities,
                price_step=price_input_profile(self.price_currency).step,
            )
        )
        
        self._device_command_builder = DeviceCommandBuilder()
        self._device_backend: DeviceBackend = HomeAssistantEntityBackend(
            capabilities=self._device_profile.capabilities,
            set_ac_mode=self._set_ac_mode,
            set_input_limit=self._set_input_limit,
            set_output_limit=self._set_output_limit,
        )
        self._command_effectiveness_config = CommandEffectivenessConfig()
        self._clock = clock or HomeAssistantClock()

        self._state_store = HomeAssistantStateStore(
            hass,
            version=STORE_VERSION,
            key=f"{DOMAIN}.{entry.entry_id}",
        )
        self._persist: dict[str, Any] = {
            "runtime_mode": dict(self.runtime_mode),

            # last applied setpoints
            "last_set_mode": None,
            "last_set_input_w": None,
            "last_set_output_w": None,
            "prev_discharge_w": 0.0,
            "prev_charge_w": 0.0,

            # basic state
            "power_state": "idle",  # idle|charging|discharging|discharge_waiting_for_import|passthrough
            "emergency_active": False,
            "discharge_blocked_by_soc_min": False,
            "discharge_resume_soc": None,

            # analytics
            "trade_avg_charge_price": None,
            "trade_charged_kwh": 0.0,
            "trade_cycle_below_soc_min": False,
            "trade_soc_min_reset_count": 0,
            "prev_soc": None,
            "pending_charge_price_evidence": None,

            "avg_charge_price": None,
            "charged_kwh": 0.0,
            "discharged_kwh": 0.0,
            "profit": 0.0,
            "last_ts": None,
            "economics_energy_state": None,
            "economics_money_state": None,
            "economics_money_day": None,

            # season detection
            "season_mode": "winter",
            "season_counter": 0,

            # cell voltage
            "global_lowest_cell_voltage": None,
            "cell_voltage_status": "disabled",
            "cell_voltage_emergency_active": False,
            "cell_voltage_emergency_started_at": None,
            "cell_voltage_discharge_blocked": False,
            "cell_voltage_resume_threshold": None,
            "cell_voltage_post_emergency_discharge_locked": False,
            "cell_voltage_normal_charge_observed": False,
            "cell_voltage_soc_plausibility": "not_available",

            # PV charge debounce / hysteresis
            "pv_charge_start_counter": 0,
            "pv_charge_stop_counter": 0,
            "pv_charge_latched": False,
            
            # Unified display-only status hysteresis.
            "active_status_display_hold_until": None,
            "active_status_display_action": "",
            "active_status_display_mode": "",
            "active_status_display_reason": "",
            "active_status_display_hold_reason": "none",

            # Forecast / reality override
            "forecast_wait_block_counter": 0,

            # V4.1.0 learned charge-window planning
            "learned_load_slots": {},
            "learned_load_last_ts": None,
            "learned_charge_power_samples": [],

            # SF800Pro PV house-load passthrough hysteresis
            "pv_houseload_passthrough_active": False,
            "pv_houseload_passthrough_started_ts": None,
            "pv_houseload_passthrough_export_counter": 0,
            "pv_houseload_passthrough_target_w": 0.0,
            "pv_houseload_passthrough_stop_reason": "none",

            # SF800Pro passthrough output smoothing
            "sf800_passthrough_prev_output_w": 0.0,
            "sf800_passthrough_smoothed_target_w": 0.0,
            
            # V4.2.0 regulation runtime state
            "regulation_last_resolved_mode": "idle",
            "regulation_last_requested_mode": "idle",
            "regulation_last_mode_change_ts": None,
            "regulation_last_command_ts": None,
            "regulation_active_state": "none",
            "regulation_active_state_started_ts": None,
            "regulation_post_load_drop_hold_until": None,
            "regulation_post_output_overshoot_hold_until": None,
            "regulation_pv_charge_latch_started_ts": None,
            "regulation_discharge_latch_started_ts": None,
            "automatic_economic_discharge_source_reason": "",
            "regulation_passthrough_latch_started_ts": None,
            "regulation_skipped_write_reason": "none",

            # V4.3.0-dev6.2:
            # Bounded recovery when the active Number value still looks correct
            # but the battery no longer applies the INPUT/OUTPUT command.
            "command_effectiveness_direction": "none",
            "command_effectiveness_mismatch_cycles": 0,
            "command_effectiveness_retry_count": 0,
            "command_effectiveness_last_retry_at": None,
            "command_effectiveness_status": "inactive",
            "command_effectiveness_reason": "not_evaluated",
            "command_effectiveness_target_w": 0.0,
            "command_effectiveness_measured_w": 0.0,
            "command_effectiveness_retry_forced": False,
            
            # V4.3.0-dev5.6:
            # Strategic AC charge binding with explicit runtime phase.
            "charge_commit_active": False,
            "charge_commit_phase": "waiting",
            "charge_commit_type": "none",
            "charge_commit_source_state": "",
            "charge_commit_reason": "",
            "charge_commit_source_reason": "",
            "charge_commit_target_soc": None,
            "charge_commit_started_at": None,
            "charge_commit_updated_at": None,
            "charge_commit_valid_until": None,

            # Learned/planned charge-window context.
            "charge_commit_optimal_start": None,
            "charge_commit_latest_start": None,
            "charge_commit_deadline": None,
            "charge_commit_acceptable_price_per_kwh": None,

            "charge_commit_requested_power_w": 0.0,
            "charge_commit_allow_pv_blend": True,
            "charge_commit_abort_reason": "none",
            "charge_commit_price_per_kwh": None,

            # V4.3.0-dev5.8.3:
            # Start time of a continuously detected BMS/full-charge stall.
            "charge_commit_bms_stall_started_at": None,

            # debug
            "debug": "init",
        }

        super().__init__(
            hass,
            _LOGGER,
            name="Battery SmartFlow AI",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    async def _load(self) -> None:
        load_result = await self._state_store.load()
        if load_result.usable:
            loaded_data = migrate_persisted_v47_state(
                load_result.data,
                legacy_system_id=f"config_entry:{self.entry.entry_id}",
            )
            migrate_legacy_price_fields(loaded_data)
            self._persist.update(loaded_data)

            # V4.2.2:
            # Normalize old persisted extreme values. Previous versions could let
            # season_counter grow indefinitely, e.g. -167000, effectively pinning
            # Automatic mode to winter for a very long time.
            self._persist["season_counter"] = _clamp_season_counter(
                self._persist.get("season_counter", 0)
            )

            if "runtime_mode" in loaded_data and isinstance(
                loaded_data["runtime_mode"], dict
            ):
                self.runtime_mode.update(loaded_data["runtime_mode"])
                
            self.runtime_mode["ai_mode"] = normalize_ai_mode(
                self.runtime_mode.get("ai_mode")
            )

            for legacy_key in (
                "pv_surplus_display_hold_until",
                "pv_surplus_display_hold_reason",
                "sf800_pv_charge_latched",
                "sf800_pv_charge_started_ts",
                "sf800_pv_charge_stop_counter",
                "sf800_mode_arbiter_state",
                "sf800_mode_arbiter_reason",
            ):
                self._persist.pop(legacy_key, None)

            self._energy_accumulator = EnergyAccumulator.from_state(
                self._persist.get("economics_energy_state")
            )
            self._economics_engine = EconomicsEngine.from_state(
                self._persist.get("economics_money_state"),
                currency=self.price_currency.code,
            )
        elif load_result.error:
            _LOGGER.warning(
                "Persistent state load skipped (%s): %s",
                load_result.status,
                load_result.error,
            )

    async def _save(self) -> None:
        self._persist["runtime_mode"] = dict(self.runtime_mode)
        save_result = await self._state_store.save(self._persist)
        if not save_result.saved:
            _LOGGER.warning(
                "Persistent state save failed (%s): %s",
                save_result.status,
                save_result.error or "unknown error",
            )
        
    def _charge_pricing_reason(self, decision_reason: str | None) -> str:
        """Return the reason that should be used for charge price attribution.

        During an active AC-Ladebindung the public decision reason becomes
        charge_commit_active. For price/source attribution we still need the
        original AC charge reason, e.g. valley_opportunity_charge.
        """
        reason = str(decision_reason or "idle")

        if reason == "charge_commit_active":
            source_reason = str(
                self._persist.get("charge_commit_source_reason", "") or ""
            )
            if source_reason:
                return source_reason

        return reason
        
    def _charge_commit_type_for_reason(self, reason: str) -> str:
        """Return the V4.3 charge commit type for a DecisionResult reason."""
        if reason in CHARGE_COMMIT_PLANNING_REASONS:
            return "planning"
        if reason in CHARGE_COMMIT_LEARNED_REASONS:
            return "learned"
        if reason == "very_cheap_force_charge":
            return "very_cheap"
        if reason in {
            "valley_boost_charge",
            "valley_boost_charge_mixed_forecast",
        }:
            return "valley"
        if reason in {
            "valley_opportunity_charge",
            "valley_opportunity_charge_mixed_forecast",
        }:
            return "opportunity"
        if reason in CHARGE_COMMIT_RESERVE_REASONS:
            return "reserve"
        return "none"


    def _charge_commit_source_state_for_type(self, commit_type: str) -> str:
        if commit_type == "planning":
            return "ac_charge_planned"
        if commit_type == "learned":
            return "ac_charge_learned"
        if commit_type in ("very_cheap", "valley", "opportunity"):
            return "ac_charge_price"
        if commit_type == "reserve":
            return "ac_charge_reserve"
        return ""


    def _parse_commit_dt(self, value: Any) -> datetime | None:
        if not value:
            return None
        try:
            parsed = dt_util.parse_datetime(str(value))
            if parsed is None:
                return None
            return dt_util.as_utc(parsed)
        except Exception:
            return None


    def _commit_dt_to_store(self, value: datetime | None) -> str | None:
        """Store charge commit timestamps in local HA time for diagnostics.

        Internally parsed values are normalized back to UTC when needed.
        The stored string is primarily shown in diagnostic sensors, so local
        Home Assistant time is easier to read than raw UTC.
        """
        if value is None:
            return None
        try:
            local_value = dt_util.as_local(value)
            return local_value.replace(microsecond=0).isoformat(timespec="seconds")
        except Exception:
            return None


    def _get_charge_commit(self) -> ChargeCommitState:
        return ChargeCommitState(
            active=bool(
                self._persist.get(
                    "charge_commit_active",
                    False,
                )
            ),
            phase=str(
                self._persist.get(
                    "charge_commit_phase",
                    "waiting",
                )
                or "waiting"
            ),
            commit_type=str(
                self._persist.get(
                    "charge_commit_type",
                    "none",
                )
                or "none"
            ),
            source_state=str(
                self._persist.get(
                    "charge_commit_source_state",
                    "",
                )
                or ""
            ),
            source_reason=str(
                self._persist.get(
                    "charge_commit_source_reason",
                    "",
                )
                or ""
            ),
            strategic_reason=str(
                self._persist.get(
                    "charge_commit_reason",
                    "",
                )
                or ""
            ),
            target_soc=_to_float(
                self._persist.get(
                    "charge_commit_target_soc",
                ),
                None,
            ),
            started_at=self._parse_commit_dt(
                self._persist.get(
                    "charge_commit_started_at",
                )
            ),
            updated_at=self._parse_commit_dt(
                self._persist.get(
                    "charge_commit_updated_at",
                )
            ),
            valid_until=self._parse_commit_dt(
                self._persist.get(
                    "charge_commit_valid_until",
                )
            ),
            optimal_start=self._parse_commit_dt(
                self._persist.get(
                    "charge_commit_optimal_start",
                )
            ),
            latest_start=self._parse_commit_dt(
                self._persist.get(
                    "charge_commit_latest_start",
                )
            ),
            deadline=self._parse_commit_dt(
                self._persist.get(
                    "charge_commit_deadline",
                )
            ),
            acceptable_price_per_kwh=_to_float(
                self._persist.get(
                    "charge_commit_acceptable_price_per_kwh",
                ),
                None,
            ),
            requested_power_w=_to_float(
                self._persist.get(
                    "charge_commit_requested_power_w",
                ),
                0.0,
            ),
            allow_pv_blend=bool(
                self._persist.get(
                    "charge_commit_allow_pv_blend",
                    True,
                )
            ),
            abort_reason=str(
                self._persist.get(
                    "charge_commit_abort_reason",
                    "none",
                )
                or "none"
            ),
        )


    def _store_charge_commit(
        self,
        commit: ChargeCommitState,
    ) -> None:
        self._persist["charge_commit_active"] = bool(
            commit.active
        )
        self._persist["charge_commit_phase"] = str(
            commit.phase or "waiting"
        )
        self._persist["charge_commit_type"] = str(
            commit.commit_type or "none"
        )
        self._persist["charge_commit_source_state"] = str(
            commit.source_state or ""
        )
        self._persist["charge_commit_reason"] = str(
            commit.strategic_reason or ""
        )
        self._persist["charge_commit_source_reason"] = str(
            commit.source_reason or ""
        )
        self._persist["charge_commit_target_soc"] = (
            commit.target_soc
        )

        self._persist["charge_commit_started_at"] = (
            self._commit_dt_to_store(
                commit.started_at
            )
        )
        self._persist["charge_commit_updated_at"] = (
            self._commit_dt_to_store(
                commit.updated_at
            )
        )
        self._persist["charge_commit_valid_until"] = (
            self._commit_dt_to_store(
                commit.valid_until
            )
        )

        self._persist["charge_commit_optimal_start"] = (
            self._commit_dt_to_store(
                commit.optimal_start
            )
        )
        self._persist["charge_commit_latest_start"] = (
            self._commit_dt_to_store(
                commit.latest_start
            )
        )
        self._persist["charge_commit_deadline"] = (
            self._commit_dt_to_store(
                commit.deadline
            )
        )

        self._persist[
            "charge_commit_acceptable_price_per_kwh"
        ] = commit.acceptable_price_per_kwh

        self._persist["charge_commit_requested_power_w"] = float(
            commit.requested_power_w or 0.0
        )
        self._persist["charge_commit_allow_pv_blend"] = bool(
            commit.allow_pv_blend
        )
        self._persist["charge_commit_abort_reason"] = str(
            commit.abort_reason or "none"
        )


    def _clear_charge_commit(
        self,
        abort_reason: str = "none",
        *,
        completed: bool = False,
    ) -> None:
        self._persist["charge_commit_active"] = False
        self._persist["charge_commit_phase"] = (
            "completed"
            if completed
            else "aborted"
            if abort_reason != "none"
            else "waiting"
        )

        self._persist["charge_commit_type"] = "none"
        self._persist["charge_commit_source_state"] = ""
        self._persist["charge_commit_reason"] = ""
        self._persist["charge_commit_source_reason"] = ""
        self._persist["charge_commit_target_soc"] = None
        self._persist["charge_commit_started_at"] = None
        self._persist["charge_commit_updated_at"] = None
        self._persist["charge_commit_valid_until"] = None

        self._persist["charge_commit_optimal_start"] = None
        self._persist["charge_commit_latest_start"] = None
        self._persist["charge_commit_deadline"] = None
        self._persist[
            "charge_commit_acceptable_price_per_kwh"
        ] = None

        self._persist["charge_commit_requested_power_w"] = 0.0
        self._persist["charge_commit_allow_pv_blend"] = True
        self._persist["charge_commit_abort_reason"] = str(
            abort_reason or "none"
        )
        self._persist["charge_commit_price_per_kwh"] = None
        self._persist["charge_commit_bms_stall_started_at"] = None


    def _price_commit_valid_until(
        self,
        now: datetime,
        commit_type: str,
    ) -> datetime | None:
        """Return optional validity timeout for AC-Ladebindungen.

        V4.3.0-dev2.2:
        Do not end price/opportunity charge bindings by a fixed timeout.

        A fixed 20-minute timeout can wrongly cancel an active AC-Ladebindung even
        when the current price is still good or even lower than at start. Until a
        real price-condition check is implemented, price-based AC-Ladebindungen are
        held until target SoC, protection, blocker or manual abort.
        """
        return None


    def _strategic_ac_charge_price_conflict(
        self,
        *,
        reason: str,
        price_now: float | None,
        effective_discharge_threshold: float | None,
    ) -> bool:
        """Return whether an optional reserve charge conflicts with discharge economics.

        Planned and learned charge windows have already evaluated the complete
        future price curve, required energy, deadline and available charging slots.
        Their decisions must therefore not be overridden afterwards by the simpler
        effective-discharge-threshold check.

        The guard remains active for optional peak-reserve charging so that reserve
        charging cannot start or continue inside an economic discharge window.
        """

        if reason not in CHARGE_COMMIT_RESERVE_REASONS:
            return False

        current_price = _to_float(price_now, None)
        discharge_threshold = _to_float(
            effective_discharge_threshold,
            None,
        )

        if current_price is None or discharge_threshold is None:
            return False

        if discharge_threshold <= 0.0:
            return False

        margin = max(
            0.0,
            float(self.price_comparison_tolerance),
        )

        return float(current_price) >= (
            float(discharge_threshold) + margin
        )


    def _charge_commit_abort_reason(
        self,
        *,
        commit: ChargeCommitState,
        now: datetime,
        soc: float,
        soc_max: float,
        ai_mode: str,
        manual_action: str,
        additional_battery_discharge_w: float,
        offgrid_load_active: bool,
        cell_voltage_emergency_active: bool,
        price_now: float | None,
        effective_discharge_threshold: float | None,
        automatic_peak_reserve_allowed: bool,
        battery_charge_w: float,
        learned_charge_plan: Any | None,
    ) -> str:
        if not commit.active:
            return "none"

        if ai_mode == AI_MODE_SUMMER:
            return "autarky_mode_selected"

        if ai_mode == AI_MODE_MANUAL:
            return "manual_mode_selected"

        if bool(cell_voltage_emergency_active):
            return "protection_cutoff"

        if float(additional_battery_discharge_w or 0.0) > 50.0:
            return "additional_battery_discharging_blocks_charge"

        # A falling live need must not replace an active binding's target SoC.
        # Only legacy targetless bindings retain the zero-need fail-safe.
        if learned_plan_may_complete_active_commit(
            commit=commit,
            learned_charge_plan=learned_charge_plan,
        ):
            return "learned_charge_no_longer_needed"

        # V4.3.0-dev8:
        # A continuously used island socket is an independent device path.
        # Its load must neither abort nor pause a valid AC charge binding.

        if self._strategic_ac_charge_price_conflict(
            reason=str(commit.source_reason or ""),
            price_now=price_now,
            effective_discharge_threshold=effective_discharge_threshold,
        ):
            return "price_condition_lost"

        target_soc = commit.target_soc
        if target_soc is None:
            target_soc = float(soc_max)

        effective_target_soc = min(float(target_soc), float(soc_max))

        # Small tolerance avoids a commit flickering at exact target.
        if float(soc) >= effective_target_soc - 0.2:
            if effective_target_soc >= float(soc_max) - 0.2:
                return "max_soc_reached"
            return "target_soc_reached"
            
        # V4.3.0-dev5.8.4:
        # Once an active charge is practically complete, do not keep buying expensive
        # grid energy while the same energy could already be discharged profitably.
        #
        # This is deliberately narrow:
        # - waiting bindings are harmless since Dev5.8.1 and remain alive
        # - forced bindings must still reach their required energy target
        # - only near-full targets participate, so lower learned targets cannot
        #   repeatedly complete and immediately recreate themselves
        current_price = _to_float(price_now, None)
        discharge_threshold = _to_float(
            effective_discharge_threshold,
            None,
        )

        target_gap = max(
            0.0,
            float(effective_target_soc) - float(soc),
        )

        target_is_near_max = bool(
            float(effective_target_soc)
            >= (
                float(soc_max)
                - CHARGE_COMMIT_DISCHARGE_WINDOW_TARGET_GAP_PCT
            )
        )

        profitable_discharge_window = bool(
            current_price is not None
            and discharge_threshold is not None
            and float(discharge_threshold) > 0.0
            and float(current_price) >= float(discharge_threshold)
        )

        if (
            str(commit.phase or "") == "active"
            and target_is_near_max
            and target_gap
            <= CHARGE_COMMIT_DISCHARGE_WINDOW_TARGET_GAP_PCT
            and profitable_discharge_window
        ):
            return "target_nearly_reached_discharge_window"
            
        # V4.3.0-dev5.8.3:
        # Some batteries stop accepting AC charge shortly before the reported SoC
        # reaches the requested target. Without an escape hatch the charge binding
        # would keep INPUT active indefinitely.
        #
        # Only treat this as an effectively completed target when:
        # - the binding is really active/forced, never while merely waiting
        # - less than 3 percentage points remain
        # - the binding is still requesting meaningful charge power
        # - the configured battery AC-power sensor is valid
        # - measured battery charge stays <= 25 W continuously for 5 minutes
        target_gap = max(
            0.0,
            float(effective_target_soc) - float(soc),
        )

        battery_power_sensor_valid = (
            _to_float(
                self._state(self.entities.battery_ac_power),
                None,
            )
            is not None
        )

        bms_stall_candidate = bool(
            str(commit.phase or "") in ("active", "forced")
            and float(effective_target_soc) >= (
                float(soc_max) - CHARGE_COMMIT_BMS_STALL_TARGET_GAP_PCT
            )
            and target_gap <= CHARGE_COMMIT_BMS_STALL_TARGET_GAP_PCT
            and float(commit.requested_power_w or 0.0) > 50.0
            and battery_power_sensor_valid
            and float(battery_charge_w or 0.0)
            <= CHARGE_COMMIT_BMS_STALL_MAX_CHARGE_W
        )

        if bms_stall_candidate:
            stall_started_at = self._parse_commit_dt(
                self._persist.get(
                    "charge_commit_bms_stall_started_at"
                )
            )

            if stall_started_at is None:
                self._persist[
                    "charge_commit_bms_stall_started_at"
                ] = dt_util.as_utc(now).isoformat()

            else:
                stall_seconds = max(
                    0.0,
                    (
                        dt_util.as_utc(now)
                        - dt_util.as_utc(stall_started_at)
                    ).total_seconds(),
                )

                if stall_seconds >= CHARGE_COMMIT_BMS_STALL_SECONDS:
                    return "target_unreachable_battery_full"

        else:
            # Any meaningful charge recovery, larger target gap, waiting phase or
            # invalid sensor immediately cancels the pending full-BMS detection.
            self._persist["charge_commit_bms_stall_started_at"] = None

        # V4.3.0-dev5.8.5:
        # A learned charge binding exists to provide the required energy by its
        # planning deadline. Once that deadline has passed, the old binding no
        # longer has a valid strategic purpose and must not keep INPUT active.
        #
        # The stored deadline belongs to the original binding snapshot and is not
        # refreshed by later learned-plan recalculations.
        if (
            commit.deadline is not None
            and dt_util.as_utc(now) >= dt_util.as_utc(commit.deadline)
        ):
            return "deadline_passed"

        return "none"


    def _committed_charge_decision(
        self,
        *,
        base_decision: DecisionResult,
        commit: ChargeCommitState,
        max_charge_w: float,
    ) -> DecisionResult:
        requested_power = float(commit.requested_power_w or 0.0)
        if requested_power <= 0.0:
            requested_power = float(base_decision.charge_w or 0.0)
        if requested_power <= 0.0:
            requested_power = float(max_charge_w)

        requested_power = max(0.0, min(float(requested_power), float(max_charge_w)))

        return DecisionResult(
            action="charge",
            ac_mode="input",
            charge_w=requested_power,
            discharge_w=0.0,
            reason="charge_commit_active",
            target_soc=commit.target_soc,
            current_peak_threshold=base_decision.current_peak_threshold,
            current_valley_threshold=base_decision.current_valley_threshold,
            economic_discharge_threshold=base_decision.economic_discharge_threshold,
            effective_discharge_threshold=base_decision.effective_discharge_threshold,
        )
        
        
    def _waiting_charge_commit_decision(
        self,
        *,
        base_decision: DecisionResult,
        commit: ChargeCommitState,
    ) -> DecisionResult:
        """Keep a charge binding alive without reserving the whole system.

        V4.3.0-dev5.8.1:
        A waiting AC charge binding only postpones its own grid charging.
        It must not suppress profitable discharge, PV passthrough or a real
        emergency charge.

        The binding itself remains active and may start later when its original
        learned price condition is reached.
        """

        action = str(base_decision.action or "")
        reason = str(base_decision.reason or "")

        # Real PV surplus may continue charging while the learned AC part waits.
        if (
            reason == "pv_surplus_charge"
            and action == "charge"
            and str(base_decision.ac_mode or "") == "input"
            and float(base_decision.charge_w or 0.0) > 0.0
        ):
            return base_decision

        # A waiting future charge must never suppress an emergency charge.
        if action == "emergency":
            return base_decision

        # Economic discharge and technical passthrough remain independent from
        # the waiting AC charge binding.
        if (
            action in ("discharge", "passthrough")
            and str(base_decision.ac_mode or "") == "output"
            and float(base_decision.discharge_w or 0.0) > 0.0
        ):
            return base_decision

        # Other AC/grid charge decisions stay postponed while the learned binding
        # is explicitly waiting for its original price condition.
        return DecisionResult(
            action="idle",
            ac_mode="output",
            charge_w=0.0,
            discharge_w=0.0,
            reason="charge_commit_waiting_price",
            target_soc=commit.target_soc,
            current_peak_threshold=(
                base_decision.current_peak_threshold
            ),
            current_valley_threshold=(
                base_decision.current_valley_threshold
            ),
            economic_discharge_threshold=(
                base_decision.economic_discharge_threshold
            ),
            effective_discharge_threshold=(
                base_decision.effective_discharge_threshold
            ),
        )
        
        
    def _learned_commit_plan_values(
        self,
        learned_charge_plan: Any | None,
    ) -> tuple[
        datetime | None,
        datetime | None,
        datetime | None,
        float | None,
    ]:
        """Extract learned planning data for an AC charge binding."""

        if learned_charge_plan is None:
            return None, None, None, None

        optimal_start = getattr(
            learned_charge_plan,
            "optimal_charge_start",
            None,
        )
        latest_start = getattr(
            learned_charge_plan,
            "latest_charge_start",
            None,
        )
        deadline = getattr(
            learned_charge_plan,
            "planning_deadline",
            None,
        )
        acceptable_price = _to_float(
            getattr(
                learned_charge_plan,
                "acceptable_charge_price_per_kwh",
                None,
            ),
            None,
        )

        try:
            optimal_start = (
                dt_util.as_utc(optimal_start)
                if optimal_start is not None
                else None
            )
        except Exception:
            optimal_start = None

        try:
            latest_start = (
                dt_util.as_utc(latest_start)
                if latest_start is not None
                else None
            )
        except Exception:
            latest_start = None

        try:
            deadline = (
                dt_util.as_utc(deadline)
                if deadline is not None
                else None
            )
        except Exception:
            deadline = None

        return (
            optimal_start,
            latest_start,
            deadline,
            acceptable_price,
        )


    def _apply_charge_commit(
        self,
        *,
        now: datetime,
        decision: DecisionResult,
        learned_charge_plan: Any | None,
        soc: float,
        soc_max: float,
        max_charge_w: float,
        ai_mode: str,
        manual_action: str,
        additional_battery_discharge_w: float,
        offgrid_load_active: bool,
        cell_voltage_emergency_active: bool,
        price_now: float | None,
        effective_discharge_threshold: float | None,
        automatic_peak_reserve_allowed: bool,
        battery_charge_w: float,
    ) -> DecisionResult:
        """Start, hold or stop a strategic AC charge binding."""
        reason = str(decision.reason or "idle")
        now_utc = dt_util.as_utc(now)

        commit = self._get_charge_commit()
        
        (
            learned_optimal_start,
            learned_latest_start,
            learned_deadline,
            learned_acceptable_price,
        ) = self._learned_commit_plan_values(
            learned_charge_plan
        )

        # Active commit: check whether it must stop.
        if commit.active:
            abort_reason = self._charge_commit_abort_reason(
                commit=commit,
                now=now_utc,
                soc=float(soc),
                soc_max=float(soc_max),
                ai_mode=str(ai_mode),
                manual_action=str(manual_action),
                additional_battery_discharge_w=float(
                    additional_battery_discharge_w or 0.0
                ),
                offgrid_load_active=bool(offgrid_load_active),
                cell_voltage_emergency_active=bool(
                    cell_voltage_emergency_active
                ),
                price_now=price_now,
                effective_discharge_threshold=(
                    effective_discharge_threshold
                ),
                automatic_peak_reserve_allowed=bool(
                    automatic_peak_reserve_allowed
                ),
                battery_charge_w=float(battery_charge_w or 0.0),
                learned_charge_plan=learned_charge_plan,
            )

            if abort_reason != "none":
                completed = abort_reason in {
                    "max_soc_reached",
                    "target_soc_reached",
                    "target_unreachable_battery_full",
                    "target_nearly_reached_discharge_window",
                    "learned_charge_no_longer_needed",
                }

                self._clear_charge_commit(
                    abort_reason,
                    completed=completed,
                )
                return decision
                
            # V4.3.0-dev5.8:
            # Learned charge bindings are snapshots of the planning decision
            # that created them.
            #
            # Do not overwrite optimal_start, latest_start, deadline or the
            # acceptable price with a newly calculated LearnedChargePlan.
            #
            # Phase transitions are monotonic:
            #
            #   waiting -> active -> forced
            #          \-> forced
            #
            # Once AC charging has actually become active, a later price
            # recalculation must not send the same charge binding back to
            # waiting. The binding then continues until target SoC or a real
            # abort condition is reached.
            if str(commit.commit_type or "") == "learned":
                current_phase = str(
                    commit.phase or "waiting"
                )

                forced = learned_commit_is_forced(
                    commit=commit,
                    now=now_utc,
                )

                if forced:
                    commit.phase = "forced"

                else:
                    acceptable_price = _to_float(
                        commit.acceptable_price_per_kwh,
                        None,
                    )
                    current_price = _to_float(
                        price_now,
                        None,
                    )

                    price_too_high = bool(
                        acceptable_price is not None
                        and current_price is not None
                        and float(current_price)
                        > (
                            float(acceptable_price)
                            + float(
                                self.price_comparison_tolerance
                            )
                        )
                    )

                    commit.phase = learned_commit_price_phase(
                        current_phase=current_phase,
                        price_too_high=price_too_high,
                    )

                # The Decision Engine has already verified that economic
                # discharge is genuinely possible (SoC, protection, data and
                # Automatic permissions included). A non-forced learned binding
                # must yield instead of overriding that selected OUTPUT action.
                if learned_commit_should_yield_to_discharge(
                    commit=commit,
                    now=now_utc,
                    selected_reason=str(decision.reason or ""),
                ):
                    commit.phase = "waiting"

                commit.updated_at = now_utc
                self._store_charge_commit(commit)

                if commit.phase == "waiting":
                    return self._waiting_charge_commit_decision(
                        base_decision=decision,
                        commit=commit,
                    )

                # The target, timing and power form one planning snapshot. A
                # shrinking live need must not taper the stored 800 W request to
                # the planner's 100 W minimum while the old target SoC remains.
                commit.requested_power_w = preserved_learned_commit_power(
                    requested_power_w=float(commit.requested_power_w or 0.0),
                    max_charge_w=float(max_charge_w),
                )
                commit.updated_at = now_utc
                self._store_charge_commit(commit)

            # If the same charge reason is still present, refresh power and
            # price-window timeout for optional price commits.
            if reason in CHARGE_COMMIT_SOURCE_REASONS:
                commit.requested_power_w = max(
                    0.0,
                    min(float(decision.charge_w or 0.0), float(max_charge_w)),
                )
                if commit.requested_power_w <= 0.0:
                    commit.requested_power_w = float(max_charge_w)
                commit.updated_at = now_utc
                refreshed_until = self._price_commit_valid_until(
                    now_utc,
                    str(commit.commit_type or "none"),
                )
                if refreshed_until is not None:
                    commit.valid_until = refreshed_until
                if price_now is not None:
                    self._persist["charge_commit_price_per_kwh"] = float(price_now)
                self._store_charge_commit(commit)
                
            return self._committed_charge_decision(
                base_decision=decision,
                commit=commit,
                max_charge_w=float(max_charge_w),
            )
            
        # V4.3.0-dev5.0.1:
        # Do not start a learned/planned AC-Ladebindung when the current price
        # is already in the effective discharge range.
        if self._strategic_ac_charge_price_conflict(
            reason=reason,
            price_now=price_now,
            effective_discharge_threshold=effective_discharge_threshold,
        ):
            self._persist["charge_commit_abort_reason"] = (
                "price_condition_lost"
            )

            return DecisionResult(
                action="idle",
                ac_mode="output",
                charge_w=0.0,
                discharge_w=0.0,
                reason="strategic_ac_charge_blocked_price_conflict",
                target_soc=decision.target_soc,
                current_peak_threshold=decision.current_peak_threshold,
                current_valley_threshold=decision.current_valley_threshold,
                economic_discharge_threshold=(
                    decision.economic_discharge_threshold
                ),
                effective_discharge_threshold=(
                    decision.effective_discharge_threshold
                ),
            )

        # No active commit: start one for strategic AC charge decisions.
        if (
            reason in CHARGE_COMMIT_SOURCE_REASONS
            and str(decision.action or "") == "charge"
            and str(decision.ac_mode or "") == "input"
            and float(decision.charge_w or 0.0) > 0.0
            and float(soc) < float(soc_max)
        ):
            commit_type = self._charge_commit_type_for_reason(reason)
            target_soc = decision.target_soc
            if target_soc is None:
                target_soc = float(soc_max)

            initial_phase = "active"

            if commit_type == "learned":
                latest_start_reached = bool(
                    learned_latest_start is not None
                    and now_utc >= learned_latest_start
                )

                forced_reason = reason in {
                    "learned_charge_window_latest_start_reached",
                    "learned_charge_window_deadline_too_close_start_now",
                }

                if latest_start_reached or forced_reason:
                    initial_phase = "forced"
                else:
                    acceptable_price = _to_float(
                        learned_acceptable_price,
                        None,
                    )
                    current_price = _to_float(
                        price_now,
                        None,
                    )

                    if (
                        acceptable_price is not None
                        and current_price is not None
                        and float(current_price)
                        > (
                            float(acceptable_price)
                            + float(
                                self.price_comparison_tolerance
                            )
                        )
                    ):
                        initial_phase = "waiting"

            new_commit = ChargeCommitState(
                active=True,
                phase=initial_phase,
                commit_type=commit_type,
                source_state=(
                    self._charge_commit_source_state_for_type(
                        commit_type
                    )
                ),
                source_reason=reason,
                strategic_reason=reason,
                target_soc=float(target_soc),
                max_soc=float(soc_max),
                started_at=now_utc,
                updated_at=now_utc,
                valid_until=self._price_commit_valid_until(
                    now_utc,
                    commit_type,
                ),
                optimal_start=(
                    learned_optimal_start
                    if commit_type == "learned"
                    else None
                ),
                latest_start=(
                    learned_latest_start
                    if commit_type == "learned"
                    else None
                ),
                deadline=(
                    learned_deadline
                    if commit_type == "learned"
                    else None
                ),
                acceptable_price_per_kwh=(
                    learned_acceptable_price
                    if commit_type == "learned"
                    else None
                ),
                requested_power_w=min(
                    float(decision.charge_w or 0.0),
                    float(max_charge_w),
                ),
                allow_pv_blend=True,
                abort_reason="none",
            )
            self._store_charge_commit(new_commit)
            
            if price_now is not None:
                self._persist["charge_commit_price_per_kwh"] = float(price_now)
            else:
                self._persist["charge_commit_price_per_kwh"] = None
                
            if new_commit.phase == "waiting":
                return self._waiting_charge_commit_decision(
                    base_decision=decision,
                    commit=new_commit,
                )

            return self._committed_charge_decision(
                base_decision=decision,
                commit=new_commit,
                max_charge_w=float(max_charge_w),
            )

        self._persist["charge_commit_abort_reason"] = (
            current_inactive_commit_abort_reason(
                stored_abort_reason=str(
                    self._persist.get("charge_commit_abort_reason", "none") or "none"
                ),
                learned_charge_plan=learned_charge_plan,
            )
        )
        return decision

    def _state(self, entity_id: str | None) -> Any:
        if not entity_id:
            return None
        st = self.hass.states.get(entity_id)
        return st.state if st else None

    def _debug_status_data(self) -> dict[str, Any]:
        """Return the small V4.4.0 debug status surface for Home Assistant."""

        status = self._debug_recorder.status
        return {
            "debug_recording_active": status.active,
            "debug_recording_ends_at": status.recording_end,
            "debug_sample_count": status.sample_count,
            "debug_last_package": self._debug_last_package,
            "debug_last_error": self._debug_last_error,
        }

    @property
    def debug_last_package_path(self) -> str | None:
        """Return the latest package path for Home Assistant diagnostics."""

        return self._debug_last_package

    @property
    def debug_recording_status(self):
        """Return the sparse recording status for the options flow."""

        return self._debug_recorder.status

    def _debug_configured_entities(self) -> dict[str, str | None]:
        """Return entity ids by diagnostic role without reading their contents."""

        return {
            "soc": self.entities.soc,
            "pv": self.entities.pv,
            "native_pv": self.entities.native_pv,
            "pv_forecast_today": self.entities.pv_forecast_today,
            "pv_forecast_tomorrow": self.entities.pv_forecast_tomorrow,
            "price_now": self.entities.price_now,
            "price_export": self.entities.price_export,
            "dynamic_feed_in_price": self.entities.dynamic_feed_in_price,
            "ac_mode": self.entities.ac_mode,
            "input_limit": self.entities.input_limit,
            "output_limit": self.entities.output_limit,
            "battery_ac_power": self.entities.battery_ac_power,
            "additional_battery_charge": self.entities.additional_battery_charge,
            "additional_battery_discharge": self.entities.additional_battery_discharge,
            "soc_limit": self.entities.soc_limit,
            "grid_power": self.entities.grid_power,
            "grid_import": self.entities.grid_import,
            "grid_export": self.entities.grid_export,
            "offgrid_power": self.entities.offgrid_power,
            "offgrid_mode": self.entities.offgrid_mode,
        }

    def _debug_entity_availability(self) -> dict[str, bool | None]:
        """Return availability for configured diagnostic entities."""

        return {
            role: (
                self.hass.states.get(entity_id) is not None
                if entity_id
                else None
            )
            for role, entity_id in self._debug_configured_entities().items()
        }

    async def _async_export_debug_package(self, package) -> None:
        """Write a completed package outside the event loop and retain its path."""

        try:
            result = await self.hass.async_add_executor_job(
                partial(
                    export_debug_package,
                    package,
                    config_directory=self.hass.config.config_dir,
                )
            )
        except DebugExportError as err:
            self._debug_last_error = str(err)
            _LOGGER.warning("Debug package export failed: %s", err)
            return
        self._debug_last_package = str(result.path)
        self._debug_last_error = None

    async def async_start_debug_recording(self, *, duration_minutes: int) -> None:
        """Start a user-requested bounded debug recording."""

        self._debug_recorder.start(
            duration_minutes=duration_minutes,
            now=self._clock.utc_now(),
            device_profile=self.device_profile_key,
            ai_mode=str(self.runtime_mode.get("ai_mode") or AI_MODE_AUTOMATIC),
            season_mode=str(self._persist.get("season_mode", "winter")),
            config={
                "configured_entities": self._debug_configured_entities(),
                # Options may change without recreating the coordinator. Keep
                # the debug package aligned with the live control settings.
                "runtime_settings": {
                    **self.runtime_settings,
                    **dict(self.entry.options),
                },
            },
            profile=self._get_active_profile(),
        )
        self._debug_last_error = None
        await self.async_request_refresh()

    async def async_stop_debug_recording(self) -> None:
        """Stop the active debug recording and write its JSON package."""

        package = self._debug_recorder.stop(now=self._clock.utc_now())
        if package is not None:
            await self._async_export_debug_package(package)
        await self.async_request_refresh()

    async def _async_capture_debug_sample(
        self,
        *,
        now: datetime,
        details: dict[str, Any],
    ) -> None:
        """Capture one cycle only while a recording is active."""

        if not self._debug_recorder.is_active:
            return
        package = self._debug_recorder.record(
            build_debug_sample(
                timestamp=now,
                details=details,
                configured_entities=self._debug_configured_entities(),
                entity_availability=self._debug_entity_availability(),
            ),
            now=now,
        )
        if package is not None:
            await self._async_export_debug_package(package)
            # Queue one follow-up refresh after an automatic completion so HA
            # publishes the inactive state and exported path immediately.
            self.hass.async_create_task(self.async_request_refresh())

    def _attr(self, entity_id: str | None, attr: str) -> Any:
        if not entity_id:
            return None
        st = self.hass.states.get(entity_id)
        if not st:
            return None
        return st.attributes.get(attr)

    def _get_active_profile(self) -> dict[str, Any]:
        overrides = self.entry.options.get(CONF_PROFILE_OVERRIDES, {})
        if not isinstance(overrides, dict):
            overrides = {}
        return merge_profile_with_overrides(self.device_profile_key, overrides)

    def _get_installed_pv_wp(self) -> float:
        try:
            value = self.entry.options.get(
                CONF_INSTALLED_PV_WP,
                self.entry.data.get(CONF_INSTALLED_PV_WP, DEFAULT_INSTALLED_PV_WP),
            )
            return float(value)
        except Exception:
            return float(DEFAULT_INSTALLED_PV_WP)
            
    def _get_feed_in_tariff(self) -> float:
        price = self._get_export_market_price()
        return float(price.current_price) if price.valid else 0.0

    def _get_export_market_price(
        self,
        now: datetime | None = None,
    ) -> MarketPrice:
        """Return dynamic export price, static fallback, or explicit missing."""

        static_configured = bool(
            CONF_FEED_IN_TARIFF in self.entry.data
            or CONF_FEED_IN_TARIFF in self.entry.options
        )
        static_value = resolve_feed_in_tariff(
            data=self.entry.data,
            options=self.entry.options,
            default=DEFAULT_FEED_IN_TARIFF,
        )
        return ExportMarketPriceResolver(
            state_getter=self.hass.states.get,
            active_currency=self.price_currency.code,
            dynamic_entity_id=self.entities.dynamic_feed_in_price,
            static_value=static_value,
            static_configured=static_configured,
            now=now,
        ).resolve()

    def _expert_mode_enabled(self) -> bool:
        return bool(
            self.entry.options.get(
                CONF_EXPERT_MODE_ENABLED,
                DEFAULT_EXPERT_MODE_ENABLED,
            )
        )

    def _cell_voltage_protection_enabled(self) -> bool:
        if not self._expert_mode_enabled():
            return False
        return bool(
            self.entry.options.get(
                CONF_CELL_VOLTAGE_PROTECTION_ENABLED,
                DEFAULT_CELL_VOLTAGE_PROTECTION_ENABLED,
            )
        )

    def _get_lowest_cell_voltage_values(self) -> list[float]:
        values: list[float] = []

        if not self._cell_voltage_protection_enabled():
            return values

        for entity_id in self.entities.lowest_cell_voltage_entities:
            val = _to_float(self._state(entity_id), None)
            if val is not None:
                values.append(float(val))

        return values

    def _get_global_lowest_cell_voltage(self) -> float | None:
        values = self._get_lowest_cell_voltage_values()
        if not values:
            return None
        return min(values)

    def _get_cell_voltage_status(
        self,
        global_lowest_cell_voltage: float | None,
    ) -> str:
        if not self._cell_voltage_protection_enabled():
            return "disabled"

        if global_lowest_cell_voltage is None:
            return "sensor_invalid"

        cutoff = self._get_setting(
            SETTING_CELL_VOLTAGE_CUTOFF,
            DEFAULT_CELL_VOLTAGE_CUTOFF,
        )
        warning = self._get_setting(
            SETTING_CELL_VOLTAGE_WARNING,
            DEFAULT_CELL_VOLTAGE_WARNING,
        )

        if global_lowest_cell_voltage <= float(cutoff):
            return "cutoff_active"
        if global_lowest_cell_voltage <= float(warning):
            return "warning"
        return "normal"

    def _get_cell_voltage_soc_plausibility(
        self,
        soc: float,
        soc_min: float,
        global_lowest_cell_voltage: float | None,
    ) -> str:
        """Diagnose whether SoC and cell voltage still look plausible together.

        This is a transparency-only signal. It does not change control behavior.
        """
        if not self._cell_voltage_protection_enabled():
            return "not_available"

        if global_lowest_cell_voltage is None:
            return "not_available"

        warning_v = self._get_setting(
            SETTING_CELL_VOLTAGE_WARNING,
            DEFAULT_CELL_VOLTAGE_WARNING,
        )
        cutoff_v = self._get_setting(
            SETTING_CELL_VOLTAGE_CUTOFF,
            DEFAULT_CELL_VOLTAGE_CUTOFF,
        )

        warning_soc_threshold = max(float(soc_min) + 10.0, 20.0)
        critical_soc_threshold = max(float(soc_min) + 15.0, 30.0)

        cell_v = float(global_lowest_cell_voltage)
        soc_val = float(soc)

        if cell_v <= float(cutoff_v) and soc_val >= critical_soc_threshold:
            return "critical"

        if cell_v <= float(warning_v) and soc_val >= warning_soc_threshold:
            return "warning"

        return "normal"

    def set_ai_mode(self, mode: str) -> None:
        self.runtime_mode["ai_mode"] = normalize_ai_mode(mode)

    def set_manual_action(self, action: str) -> None:
        self.runtime_mode["manual_action"] = action
        
    def _prepare_number_write(
        self,
        *,
        entity_id: str,
        requested_w: float,
        diagnostic_prefix: str,
    ) -> int:
        """Clamp a power request to the Number entity's live limits.

        V4.3.0-dev5.7:
        Some devices may narrow their Number entity range dynamically.
        Sending a value above that live range can be rejected by Home Assistant
        or ignored by the device.

        Store both the original request and the effective value for diagnostics.
        """

        requested = max(0.0, float(requested_w or 0.0))
        min_value = _to_float(
            self._attr(entity_id, "min"),
            None,
        )
        max_value = _to_float(
            self._attr(entity_id, "max"),
            None,
        )

        effective_int = clamp_number_power_request(
            requested,
            min_value=min_value,
            max_value=max_value,
        )
        requested_int = int(round(requested, 0))

        self._persist[
            f"{diagnostic_prefix}_requested_w"
        ] = requested_int

        self._persist[
            f"{diagnostic_prefix}_effective_w"
        ] = effective_int

        self._persist[
            f"{diagnostic_prefix}_entity_min_w"
        ] = min_value

        self._persist[
            f"{diagnostic_prefix}_entity_max_w"
        ] = max_value

        self._persist[
            f"{diagnostic_prefix}_clamped"
        ] = effective_int != requested_int

        return effective_int

    def _store_command_execution_result(
        self,
        result: CommandExecutionResult,
    ) -> None:
        """Expose neutral backend feedback without leaking HA details to core."""

        self._persist["command_execution_status"] = str(result.status)
        self._persist["command_execution_reason"] = str(result.reason)
        self._persist["command_execution_mode_written"] = bool(
            result.mode_written
        )
        self._persist["command_execution_input_written"] = bool(
            result.input_written
        )
        self._persist["command_execution_output_written"] = bool(
            result.output_written
        )
        self._persist["command_execution_error"] = result.error

    async def _execute_device_command(
        self,
        command: DeviceCommand,
        *,
        force_power: bool = True,
        power_before_mode: bool = False,
    ) -> CommandExecutionResult:
        """Execute one neutral command through the configured backend."""

        try:
            native_runtime = getattr(self, "native_zendure", None)
            if native_runtime is not None and native_runtime.control_enabled:
                result = await native_runtime.async_execute_device_command(command)
                self._persist.update(
                    confirmed_command_state_updates(command, result)
                )
            else:
                result = await self._device_backend.execute(
                    command,
                    force_power=force_power,
                    power_before_mode=power_before_mode,
                )
        except DeviceBackendExecutionError as err:
            self._store_command_execution_result(err.result)
            raise

        self._store_command_execution_result(result)
        return result

    async def _set_ac_mode(self, mode: str) -> None:
        """Write the AC mode reliably.

        V4.3.0-dev5.7:
        - compare against the real Select entity
        - do not trust the internal cache alone
        - wait for Home Assistant to accept the service call
        - update the cache only after a successful call
        """

        requested_mode = str(mode or "")
        current_mode = str(
            self._state(self.entities.ac_mode) or ""
        )

        cached_mode = str(
            self._persist.get("last_set_mode") or ""
        )

        self._persist["mode_write_requested"] = requested_mode
        self._persist["mode_write_entity_state"] = current_mode

        cache_matches = (
            cached_mode == requested_mode
        )

        entity_matches = (
            current_mode == requested_mode
        )

        # Skip only when both our internal cache and the real Select entity agree.
        if cache_matches and entity_matches:
            self._persist["mode_write_skipped"] = True
            self._persist["mode_write_skip_reason"] = (
                "cache_and_entity_match"
            )
            return

        # The real entity is already correct, but our cache is stale.
        # Synchronize the cache without sending another device command.
        if entity_matches:
            self._persist["last_set_mode"] = requested_mode
            self._persist["mode_write_skipped"] = True
            self._persist["mode_write_skip_reason"] = (
                "entity_match_cache_resynced"
            )
            return

        self._persist["mode_write_skipped"] = False
        self._persist["mode_write_skip_reason"] = "none"

        await self.hass.services.async_call(
            "select",
            "select_option",
            {
                "entity_id": self.entities.ac_mode,
                "option": requested_mode,
            },
            blocking=True,
        )

        # Update our internal cache only after Home Assistant accepted the call.
        self._persist["last_set_mode"] = requested_mode
        self._persist["mode_write_last_success"] = requested_mode

    async def _set_input_limit(
        self,
        watts: float,
        *,
        force: bool = False,
    ) -> None:
        """Write the effective INPUT limit reliably.

        V4.3.0-dev5.7:
        - respect dynamic Number entity limits
        - compare against the real entity state
        - do not trust the internal cache alone
        - update the cache only after a successful service call
        """

        val = self._prepare_number_write(
            entity_id=self.entities.input_limit,
            requested_w=float(watts),
            diagnostic_prefix="input_write",
        )

        cached_value = _to_float(
            self._persist.get("last_set_input_w"),
            None,
        )

        entity_value = _to_float(
            self._state(self.entities.input_limit),
            None,
        )

        cache_matches = bool(
            cached_value is not None
            and int(round(cached_value, 0)) == val
        )

        entity_matches = bool(
            entity_value is not None
            and abs(float(entity_value) - float(val)) < 1.0
        )

        self._persist["input_write_entity_state_w"] = entity_value

        # Skip only when both our cache and the real Number entity agree.
        if cache_matches and entity_matches and not force:
            self._persist["input_write_skipped"] = True
            self._persist["input_write_skip_reason"] = (
                "cache_and_entity_match"
            )
            return

        self._persist["input_write_skipped"] = False
        self._persist["input_write_skip_reason"] = "none"

        await self.hass.services.async_call(
            "number",
            "set_value",
            {
                "entity_id": self.entities.input_limit,
                "value": val,
            },
            blocking=True,
        )

        # Update only after Home Assistant accepted the service call.
        self._persist["last_set_input_w"] = val
        # Zendure-HA handles an inputLimit write as a complete INPUT command and
        # includes outputLimit=0. Keep the local regulation cache aligned
        # without issuing a second, relay-triggering outputLimit=0 command.
        self._persist["last_set_output_w"] = 0
        self._persist["input_write_last_success_w"] = val

    async def _set_output_limit(
        self,
        watts: float,
        *,
        force: bool = False,
    ) -> None:
        """Write the effective OUTPUT limit reliably.

        V4.3.0-dev5.7:
        Uses the same live-limit and Soll-/Ist synchronization as INPUT.
        """

        val = self._prepare_number_write(
            entity_id=self.entities.output_limit,
            requested_w=float(watts),
            diagnostic_prefix="output_write",
        )

        cached_value = _to_float(
            self._persist.get("last_set_output_w"),
            None,
        )

        entity_value = _to_float(
            self._state(self.entities.output_limit),
            None,
        )

        cache_matches = bool(
            cached_value is not None
            and int(round(cached_value, 0)) == val
        )

        entity_matches = bool(
            entity_value is not None
            and abs(float(entity_value) - float(val)) < 1.0
        )

        self._persist["output_write_entity_state_w"] = entity_value

        if cache_matches and entity_matches and not force:
            self._persist["output_write_skipped"] = True
            self._persist["output_write_skip_reason"] = (
                "cache_and_entity_match"
            )
            return

        self._persist["output_write_skipped"] = False
        self._persist["output_write_skip_reason"] = "none"

        await self.hass.services.async_call(
            "number",
            "set_value",
            {
                "entity_id": self.entities.output_limit,
                "value": val,
            },
            blocking=True,
        )

        self._persist["last_set_output_w"] = val
        # Zendure-HA handles an outputLimit write as a complete OUTPUT command
        # and includes inputLimit=0.
        self._persist["last_set_input_w"] = 0
        self._persist["output_write_last_success_w"] = val

    def _get_setting(self, key: str, default: float) -> float:
        try:
            val = self.entry.options.get(key, default)
            return float(val)
        except Exception:
            return float(default)

    def _get_grid(self) -> tuple[float | None, float | None]:
        """
        Returns (import_w, export_w).
        import_w > 0 means importing from grid
        export_w > 0 means exporting to grid
        """
        mode = self.entities.grid_mode

        if mode == GRID_MODE_NONE:
            return None, None

        if mode == GRID_MODE_SINGLE and self.entities.grid_power:
            gp = _to_float(self._state(self.entities.grid_power), None)
            if gp is None:
                return None, None
            gp = float(gp)
            if gp >= 0:
                return gp, 0.0
            return 0.0, abs(gp)

        if mode == GRID_MODE_SPLIT and self.entities.grid_import and self.entities.grid_export:
            gi = _to_float(self._state(self.entities.grid_import), None)
            ge = _to_float(self._state(self.entities.grid_export), None)
            if gi is None or ge is None:
                return None, None
            return float(gi), float(ge)

        return None, None

    def _get_import_market_price(self, now: datetime) -> MarketPrice:
        """Build the canonical import price from the configured V4.5 sources."""

        source = GenericStatePriceSource(
            entity_id=self.entities.price_now or "not_configured",
            state_getter=self.hass.states.get,
        )
        current_price = MarketPriceSourceAdapter(
            source=source,
            normalizer=NumericPriceNormalizer(now=now),
            direction=MarketPriceDirection.IMPORT,
            active_currency=self.price_currency.code,
        ).read()

        forecast = None
        if self.entities.price_export:
            forecast_state = self.hass.states.get(self.entities.price_export)
            if forecast_state is not None:
                adapter = LegacyImportForecastAdapter(
                    now=now,
                    default_timezone=dt_util.get_default_time_zone(),
                    parse_datetime=dt_util.parse_datetime,
                )
                forecast = adapter.normalize(
                    forecast_state.attributes or {},
                    direction=MarketPriceDirection.IMPORT,
                    active_currency=self.price_currency.code,
                )

        return replace(current_price, forecast=forecast)

    def _normalize_offgrid_mode(self, raw: Any) -> str:
        if raw is None:
            return "not_configured"

        value = str(raw).strip().lower()

        if value in ("off", "aus", "0", "disabled"):
            return "off"

        if value in ("normal", "on"):
            return "normal"

        if value in ("eco", "economic", "ökonomisch", "oekonomisch"):
            return "eco"

        if value in ("unknown", "unavailable", "none", ""):
            return "unknown"

        return "unknown"

    def _get_soc_limit(self) -> int | None:
        if not self.entities.soc_limit:
            return None
        raw = self._state(self.entities.soc_limit)
        val = _to_float(raw, None)
        if val is None:
            return None
        try:
            return int(val)
        except Exception:
            return None

    def _get_battery_capacity(self) -> float:
        pack_capacity = float(self.entry.data.get(CONF_PACK_CAPACITY_KWH, 0))

        packs = self._get_setting(
            SETTING_BATTERY_PACKS,
            DEFAULT_BATTERY_PACKS,
        )

        try:
            packs = int(packs)
        except Exception:
            packs = DEFAULT_BATTERY_PACKS

        if pack_capacity <= 0 or packs <= 0:
            return 0.0

        return pack_capacity * packs

    def _stable_iso_minute(self, value: datetime | None) -> str | None:
        """Return a stable ISO timestamp rounded to full minutes.

        This avoids Recorder churn from second/microsecond jitter in timestamp
        sensors. Learned planning works in 15-minute slots, so second-level
        precision is not useful for Home Assistant states.
        """
        if value is None:
            return None

        try:
            dt = dt_util.as_local(value)
            dt = dt.replace(second=0, microsecond=0)
            return dt.isoformat()
        except Exception:
            return None

    def _learning_slot_start(self, ts: datetime) -> datetime:
        """Return the local 15-minute slot start for a timestamp."""
        local = dt_util.as_local(ts)

        minute = (local.minute // 15) * 15

        slot_local = local.replace(
            minute=minute,
            second=0,
            microsecond=0,
        )

        return dt_util.as_utc(slot_local)

    def _update_learned_load_history(
        self,
        now: datetime,
        house_load_w: float,
    ) -> None:
        """Accumulate learned house-load energy into 15-minute slots.

        Stored format:
            learned_load_slots = {
                "<slot_start_utc_iso>": energy_kwh
            }

        We store already aggregated 15-minute slot energy, not every 10-second
        sample, so the Store remains small enough for long-term use.
        """
        now_utc = dt_util.as_utc(now)

        slots_raw = self._persist.get("learned_load_slots", {})
        if not isinstance(slots_raw, dict):
            slots_raw = {}

        last_raw = self._persist.get("learned_load_last_ts")
        if not last_raw:
            self._persist["learned_load_last_ts"] = now_utc.isoformat()
            self._persist["learned_load_slots"] = slots_raw
            return

        try:
            last_dt = dt_util.parse_datetime(str(last_raw))
            if last_dt is None:
                raise ValueError("invalid learned_load_last_ts")
            last_utc = dt_util.as_utc(last_dt)
        except Exception:
            self._persist["learned_load_last_ts"] = now_utc.isoformat()
            self._persist["learned_load_slots"] = slots_raw
            return

        delta_seconds = (now_utc - last_utc).total_seconds()

        if delta_seconds <= 0:
            self._persist["learned_load_last_ts"] = now_utc.isoformat()
            self._persist["learned_load_slots"] = slots_raw
            return

        max_gap_seconds = max(60.0, float(UPDATE_INTERVAL) * 3.0)
        usable_seconds = min(delta_seconds, max_gap_seconds)

        load_w = max(0.0, min(float(house_load_w or 0.0), 20000.0))
        energy_kwh = load_w * (usable_seconds / 3600.0) / 1000.0

        if energy_kwh > 0.0:
            midpoint = last_utc + timedelta(seconds=usable_seconds / 2.0)
            slot_start = self._learning_slot_start(midpoint)
            key = slot_start.isoformat()

            old = 0.0
            try:
                old = float(slots_raw.get(key, 0.0) or 0.0)
            except Exception:
                old = 0.0

            slots_raw[key] = round(old + energy_kwh, 6)

        cutoff = now_utc - timedelta(days=15)
        cleaned: dict[str, float] = {}

        for key, value in slots_raw.items():
            try:
                slot_dt = dt_util.parse_datetime(str(key))
                if slot_dt is None:
                    continue

                slot_utc = dt_util.as_utc(slot_dt)
                if slot_utc < cutoff:
                    continue

                val = float(value or 0.0)
                if val <= 0.0:
                    continue

                cleaned[slot_utc.isoformat()] = round(val, 6)
            except Exception:
                continue

        self._persist["learned_load_slots"] = cleaned
        self._persist["learned_load_last_ts"] = now_utc.isoformat()

    def _get_learned_load_samples(self) -> list[LearningSample]:
        """Convert persisted 15-minute slot energy into LearningSample objects."""
        slots_raw = self._persist.get("learned_load_slots", {})
        if not isinstance(slots_raw, dict):
            return []

        samples: list[LearningSample] = []

        for key, value in slots_raw.items():
            try:
                start = dt_util.parse_datetime(str(key))
                if start is None:
                    continue

                start = dt_util.as_utc(start)
                energy_kwh = float(value or 0.0)

                if energy_kwh <= 0.0:
                    continue

                samples.append(
                    LearningSample(
                        start=start,
                        end=start + timedelta(minutes=15),
                        energy_kwh=energy_kwh,
                    )
                )
            except Exception:
                continue

        samples.sort(key=lambda s: s.start)
        return samples
        
    def _cleanup_learned_charge_power_samples(self, now: datetime) -> None:
        """Keep only recent, technically unthrottled charge-power samples."""

        cutoff = dt_util.as_utc(now) - timedelta(days=ROLLING_DAYS)

        cleaned: list[dict[str, object]] = []

        for item in self._persist.get("learned_charge_power_samples", []):
            if not isinstance(item, dict):
                continue

            try:
                ts_raw = item.get("ts")
                ts = dt_util.parse_datetime(str(ts_raw)) if ts_raw else None
                if ts is None:
                    continue

                ts_utc = dt_util.as_utc(ts)

                if ts_utc < cutoff:
                    continue

                power_w = float(item.get("power_w") or 0.0)
                if power_w < MIN_LEARNED_CHARGE_POWER_SAMPLE_W:
                    continue

                commanded_power_w = float(
                    item.get("commanded_power_w") or 0.0
                )
                charge_cap_w = float(item.get("charge_cap_w") or 0.0)

                # Drop legacy/self-throttled samples. They cannot prove the
                # maximum charge power the battery would have accepted.
                if (
                    charge_cap_w <= 0.0
                    or commanded_power_w < charge_cap_w * 0.90
                ):
                    continue

                cleaned.append(
                    {
                        "ts": ts_utc.isoformat(),
                        "power_w": round(power_w, 1),
                        "commanded_power_w": round(commanded_power_w, 1),
                        "charge_cap_w": round(charge_cap_w, 1),
                    }
                )
            except Exception:
                continue

        self._persist["learned_charge_power_samples"] = cleaned

    def _remember_learned_charge_power_sample(
        self,
        now: datetime,
        *,
        decision: DecisionResult,
        battery_charge_w: float,
        max_charge_w: float,
    ) -> None:
        """Store a charge-power sample from real charging phases.

        Use the final decision after all blockers/limit checks, so only the
        actually intended charging state is learned.
        """

        if decision.ac_mode != "input":
            return

        if float(decision.charge_w or 0.0) <= 0.0:
            return

        measured_charge_w = max(0.0, float(battery_charge_w or 0.0))
        commanded_charge_w = max(0.0, float(decision.charge_w or 0.0))
        charge_cap_w = max(0.0, float(max_charge_w or 0.0))

        # Only a practically unthrottled request can reveal the technically
        # reachable charge speed. This breaks the former 1161 W feedback loop.
        if charge_cap_w <= 0.0 or commanded_charge_w < charge_cap_w * 0.90:
            return

        # Prefer real measured AC charge power. If the battery power sensor does
        # not provide a negative charging value, fall back to the command.
        charge_power_w = measured_charge_w if measured_charge_w > 0.0 else commanded_charge_w

        if charge_power_w < MIN_LEARNED_CHARGE_POWER_SAMPLE_W:
            return

        self._persist.setdefault("learned_charge_power_samples", []).append(
            {
                "ts": dt_util.as_utc(now).isoformat(),
                "power_w": round(charge_power_w, 1),
                "commanded_power_w": round(commanded_charge_w, 1),
                "charge_cap_w": round(charge_cap_w, 1),
            }
        )

        self._cleanup_learned_charge_power_samples(now)

    def _get_learned_charge_power_samples(self) -> list[LearningChargePowerSample]:
        """Convert persisted charge-power samples into LearningChargePowerSample objects."""

        raw = self._persist.get("learned_charge_power_samples", [])
        if not isinstance(raw, list):
            return []

        samples: list[LearningChargePowerSample] = []

        for item in raw:
            if not isinstance(item, dict):
                continue

            try:
                ts_raw = item.get("ts")
                ts = dt_util.parse_datetime(str(ts_raw)) if ts_raw else None
                if ts is None:
                    continue

                power_w = float(item.get("power_w") or 0.0)
                if power_w < MIN_LEARNED_CHARGE_POWER_SAMPLE_W:
                    continue

                commanded_power_w = _to_float(
                    item.get("commanded_power_w"),
                    None,
                )
                charge_cap_w = _to_float(
                    item.get("charge_cap_w"),
                    None,
                )

                samples.append(
                    LearningChargePowerSample(
                        ts=dt_util.as_utc(ts),
                        power_w=power_w,
                        commanded_power_w=commanded_power_w,
                        charge_cap_w=charge_cap_w,
                    )
                )
            except Exception:
                continue

        samples.sort(key=lambda s: s.ts)
        return samples
        
    def _get_regulation_runtime_state(self) -> RegulationRuntimeState:
        """Build the authoritative regulation runtime state."""

        def _parse_dt(value):
            if not value:
                return None
            try:
                return dt_util.parse_datetime(str(value))
            except Exception:
                return None

        return RegulationRuntimeState(
            last_resolved_mode=str(
                self._persist.get("regulation_last_resolved_mode", "idle")
                or "idle"
            ),
            last_requested_mode=str(
                self._persist.get("regulation_last_requested_mode", "idle")
                or "idle"
            ),
            last_ac_mode=self._persist.get("last_set_mode"),
            last_input_limit_w=float(
                self._persist.get("last_set_input_w", 0.0) or 0.0
            ),
            last_output_limit_w=float(
                self._persist.get("last_set_output_w", 0.0) or 0.0
            ),
            last_mode_change_ts=_parse_dt(
                self._persist.get("regulation_last_mode_change_ts")
            ),
            last_command_ts=_parse_dt(
                self._persist.get("regulation_last_command_ts")
            ),
            active_regulation_state=str(
                self._persist.get("regulation_active_state", "none")
                or "none"
            ),
            active_state_started_ts=_parse_dt(
                self._persist.get("regulation_active_state_started_ts")
            ),
            post_load_drop_hold_until=_parse_dt(
                self._persist.get("regulation_post_load_drop_hold_until")
            ),
            post_output_overshoot_hold_until=_parse_dt(
                self._persist.get("regulation_post_output_overshoot_hold_until")
            ),
            pv_charge_latch_started_ts=_parse_dt(
                self._persist.get("regulation_pv_charge_latch_started_ts")
            ),
            discharge_latch_started_ts=_parse_dt(
                self._persist.get("regulation_discharge_latch_started_ts")
            ),
            passthrough_latch_started_ts=_parse_dt(
                self._persist.get("regulation_passthrough_latch_started_ts")
            ),
            skipped_write_reason=str(
                self._persist.get("regulation_skipped_write_reason", "none")
                or "none"
            ),
        )

    def _get_command_effectiveness_state(self) -> CommandEffectivenessState:
        """Build the bounded command-recovery state from persisted values."""

        last_retry_at = None
        last_retry_raw = self._persist.get(
            "command_effectiveness_last_retry_at"
        )
        if last_retry_raw:
            try:
                last_retry_at = dt_util.parse_datetime(str(last_retry_raw))
            except Exception:
                last_retry_at = None

        direction = str(
            self._persist.get("command_effectiveness_direction", "none")
            or "none"
        )
        if direction not in ("input", "output"):
            direction = "none"

        return CommandEffectivenessState(
            direction=direction,
            mismatch_cycles=int(
                self._persist.get(
                    "command_effectiveness_mismatch_cycles",
                    0,
                )
                or 0
            ),
            retry_count=int(
                self._persist.get(
                    "command_effectiveness_retry_count",
                    0,
                )
                or 0
            ),
            last_retry_at=last_retry_at,
        )

    def _store_command_effectiveness_result(self, result: Any) -> None:
        """Persist command-effectiveness state and diagnostics."""

        state = result.state
        self._persist["command_effectiveness_direction"] = state.direction
        self._persist["command_effectiveness_mismatch_cycles"] = int(
            state.mismatch_cycles
        )
        self._persist["command_effectiveness_retry_count"] = int(
            state.retry_count
        )
        self._persist["command_effectiveness_last_retry_at"] = (
            state.last_retry_at.isoformat()
            if state.last_retry_at is not None
            else None
        )
        self._persist["command_effectiveness_status"] = str(result.status)
        self._persist["command_effectiveness_reason"] = str(result.reason)
        self._persist["command_effectiveness_target_w"] = float(
            result.target_w
        )
        self._persist["command_effectiveness_measured_w"] = float(
            result.measured_w
        )
        self._persist["command_effectiveness_retry_forced"] = bool(
            result.retry_direction is not None
        )

    def _record_command_effectiveness_retry(
        self,
        *,
        now: datetime,
        direction: str,
    ) -> None:
        """Record a recovery write after its service call succeeded."""

        state = record_effectiveness_retry(
            now=dt_util.as_utc(now),
            direction=direction,
            previous=self._get_command_effectiveness_state(),
        )

        self._persist["command_effectiveness_direction"] = state.direction
        self._persist["command_effectiveness_mismatch_cycles"] = 0
        self._persist["command_effectiveness_retry_count"] = int(
            state.retry_count
        )
        self._persist["command_effectiveness_last_retry_at"] = (
            state.last_retry_at.isoformat()
            if state.last_retry_at is not None
            else None
        )
        self._persist["command_effectiveness_status"] = "retry_sent"
        self._persist["command_effectiveness_reason"] = (
            "active_command_repeated"
        )
        self._persist["command_effectiveness_retry_forced"] = True
        
    def _update_regulation_runtime_state(
        self,
        *,
        now: datetime,
        requested_mode: str,
        resolved_mode: str,
        active_state: str,
        command_skipped: bool,
        command_skip_reason: str,
        current_ac_mode: str | None,
        command_ac_mode: str,
        profile: dict[str, Any],
        grid: Any,
    ) -> None:
        """Persist V4.2.0 regulation runtime diagnostics.

        During the transition this state is mostly diagnostic. Once the V4.2
        command path is enabled, the same state is used for cooldowns, holds and
        cleaner command decisions.
        """

        now_utc = dt_util.as_utc(now)
        
        post_load_drop_hold_s = float(profile.get("POST_LOAD_DROP_HOLD_S", 60.0) or 60.0)
        post_output_overshoot_hold_s = float(
            profile.get("POST_OUTPUT_OVERSHOOT_HOLD_S", 60.0) or 60.0
        )
        export_guard_w = float(profile.get("EXPORT_GUARD_W", 80.0) or 80.0)
        last_output_w = float(self._persist.get("last_set_output_w", 0.0) or 0.0)

        previous_resolved_mode = str(
            self._persist.get("regulation_last_resolved_mode", "idle") or "idle"
        )

        previous_ac_mode = str(self._persist.get("last_set_mode") or current_ac_mode or "")

        real_mode_changed = (
            command_ac_mode in ("input", "output")
            and previous_ac_mode in ("input", "output")
            and command_ac_mode != previous_ac_mode
        )

        resolved_mode_changed = (
            resolved_mode in ("input", "output")
            and previous_resolved_mode in ("input", "output")
            and resolved_mode != previous_resolved_mode
        )

        if real_mode_changed or resolved_mode_changed:
            self._persist["regulation_last_mode_change_ts"] = now_utc.isoformat()

        previous_active_state = str(
            self._persist.get("regulation_active_state", "none") or "none"
        )

        if active_state != previous_active_state:
            self._persist["regulation_active_state_started_ts"] = now_utc.isoformat()

        self._persist["regulation_last_requested_mode"] = str(requested_mode)
        self._persist["regulation_last_resolved_mode"] = str(resolved_mode)
        self._persist["regulation_active_state"] = str(active_state)
        self._persist["regulation_last_command_ts"] = now_utc.isoformat()
        self._persist["regulation_skipped_write_reason"] = (
            str(command_skip_reason) if command_skipped else "none"
        )

        if active_state == "pv_charge_active":
            if not self._persist.get("regulation_pv_charge_latch_started_ts"):
                self._persist["regulation_pv_charge_latch_started_ts"] = (
                    now_utc.isoformat()
                )
        else:
            self._persist["regulation_pv_charge_latch_started_ts"] = None

        if active_state == "discharge_active":
            if not self._persist.get("regulation_discharge_latch_started_ts"):
                self._persist["regulation_discharge_latch_started_ts"] = (
                    now_utc.isoformat()
                )
        else:
            self._persist["regulation_discharge_latch_started_ts"] = None

        if active_state == "passthrough_active":
            if not self._persist.get("regulation_passthrough_latch_started_ts"):
                self._persist["regulation_passthrough_latch_started_ts"] = (
                    now_utc.isoformat()
                )
        else:
            self._persist["regulation_passthrough_latch_started_ts"] = None
            
        # Post-output-overshoot hold:
        # If OUTPUT is really active and causes/keeps export beyond guard, block an
        # immediate INPUT handover. Do not extend this hold when output is already 0 W,
        # otherwise PV surplus charging can be blocked forever while stable export exists.
        grid_now_w = float(getattr(grid, "grid_now_w", 0.0) or 0.0)

        output_really_active = (
            last_output_w > 0.0
            and (
                previous_active_state == "discharge_active"
                or active_state == "discharge_active"
            )
        )

        if grid_now_w <= -abs(export_guard_w) and output_really_active:
            self._persist["regulation_post_output_overshoot_hold_until"] = (
                now_utc + timedelta(seconds=post_output_overshoot_hold_s)
            ).isoformat()

        # Cleanup expired post holds.
        for key in (
            "regulation_post_load_drop_hold_until",
            "regulation_post_output_overshoot_hold_until",
        ):
            raw = self._persist.get(key)
            if not raw:
                continue
            try:
                dt = dt_util.parse_datetime(str(raw))
                if dt is None or dt_util.as_utc(dt) <= now_utc:
                    self._persist[key] = None
            except Exception:
                self._persist[key] = None

    def _update_pv_charge_hysteresis(
        self,
        grid_import_w: float,
        grid_export_w: float,
        pv_w: float,
        pv_charge_start_export_w: float,
        battery_discharge_w: float = 0.0,
        previous_discharge_w: float = 0.0,
        last_output_w: float = 0.0,
        additional_battery_discharge_w: float = 0.0,
        mppt_clips_without_output: bool = False,
    ) -> tuple[int, int, bool]:
        start_counter = int(self._persist.get("pv_charge_start_counter", 0) or 0)
        stop_counter = int(self._persist.get("pv_charge_stop_counter", 0) or 0)
        latched = bool(self._persist.get("pv_charge_latched", False))

        start_counter, stop_counter, latched = advance_pv_charge_hysteresis(
            start_counter=start_counter,
            stop_counter=stop_counter,
            latched=latched,
            grid_import_w=grid_import_w,
            grid_export_w=grid_export_w,
            pv_w=pv_w,
            pv_charge_start_export_w=pv_charge_start_export_w,
            battery_discharge_w=battery_discharge_w,
            previous_discharge_w=previous_discharge_w,
            last_output_w=last_output_w,
            additional_battery_discharge_w=additional_battery_discharge_w,
            mppt_clips_without_output=mppt_clips_without_output,
        )

        self._persist["pv_charge_start_counter"] = start_counter
        self._persist["pv_charge_stop_counter"] = stop_counter
        self._persist["pv_charge_latched"] = latched

        return start_counter, stop_counter, latched

    def _sf800_compute_passthrough_output(
        self,
        profile: dict[str, Any],
        raw_target_w: float,
        max_output_w: float,
        latch_active: bool,
        force_zero: bool = False,
    ) -> float:
        """Smooth and rate-limit SF800Pro passthrough output."""
        if force_zero:
            self._persist["sf800_passthrough_prev_output_w"] = 0.0
            self._persist["sf800_passthrough_smoothed_target_w"] = 0.0
            return 0.0

        raw_target = max(
            0.0,
            min(float(raw_target_w or 0.0), float(max_output_w or 0.0)),
        )

        prev_output = float(
            self._persist.get("sf800_passthrough_prev_output_w", 0.0) or 0.0
        )
        prev_smoothed = float(
            self._persist.get("sf800_passthrough_smoothed_target_w", raw_target)
            or raw_target
        )

        min_output = float(
            profile.get("PV_HOUSELOAD_PASSTHROUGH_MIN_OUTPUT_W", 80.0) or 80.0
        )
        max_step_up = float(
            profile.get("PV_HOUSELOAD_PASSTHROUGH_MAX_STEP_UP_W", 100.0) or 100.0
        )
        max_step_down = float(
            profile.get("PV_HOUSELOAD_PASSTHROUGH_MAX_STEP_DOWN_W", 150.0) or 150.0
        )
        alpha = float(
            profile.get("PV_HOUSELOAD_PASSTHROUGH_SMOOTHING_ALPHA", 0.30) or 0.30
        )

        alpha = max(0.05, min(alpha, 1.0))

        smoothed_target = (prev_smoothed * (1.0 - alpha)) + (raw_target * alpha)

        if smoothed_target > prev_output:
            next_output = prev_output + min(smoothed_target - prev_output, max_step_up)
        else:
            next_output = prev_output - min(prev_output - smoothed_target, max_step_down)

        next_output = max(0.0, min(next_output, float(max_output_w or 0.0)))

        if latch_active and raw_target > 0.0:
            next_output = max(next_output, min_output)

        if not latch_active and next_output < min_output:
            next_output = 0.0

        self._persist["sf800_passthrough_prev_output_w"] = float(next_output)
        self._persist["sf800_passthrough_smoothed_target_w"] = float(smoothed_target)

        return float(next_output)

    def _update_pv_houseload_passthrough(
        self,
        now,
        profile: dict[str, Any],
        soc: float,
        soc_min: float,
        soc_max: float,
        pv_w: float,
        house_load_w: float,
        grid_import_w: float,
        grid_export_w: float,
        max_output_w: float,
        pv_charge_start_export_w: float,
        discharge_blocked_by_soc_min: bool,
        cell_voltage_discharge_blocked: bool,
        cell_voltage_emergency_active: bool,
        additional_battery_charge_w: float,
        pv_charge_latched: bool,
        forecast_status: str,
        pv_outlook: str,
        forecast_remaining_today_kwh: float,
        battery_capacity_kwh: float,
    ) -> tuple[bool, float, str]:
        capabilities = DeviceCapabilities.from_profile(profile)
        enabled = capabilities.supports_pv_house_load_passthrough

        active = bool(self._persist.get("pv_houseload_passthrough_active", False))
        started_ts_raw = self._persist.get("pv_houseload_passthrough_started_ts")
        export_counter = int(
            self._persist.get("pv_houseload_passthrough_export_counter", 0) or 0
        )

        hold_seconds = float(
            profile.get("PV_HOUSELOAD_PASSTHROUGH_HOLD_SECONDS", 300.0) or 300.0
        )
        min_pv_w = float(
            profile.get("PV_HOUSELOAD_PASSTHROUGH_MIN_PV_W", 120.0) or 120.0
        )
        min_house_load_w = float(
            profile.get("PV_HOUSELOAD_PASSTHROUGH_MIN_HOUSE_LOAD_W", 120.0) or 120.0
        )
        export_stop_cycles = int(
            profile.get("PV_HOUSELOAD_PASSTHROUGH_EXPORT_STOP_CYCLES", 18) or 18
        )

        stop_reason = "none"
        target_w = 0.0
        forced = False
        forced_prev = bool(
            self._persist.get(
                "pv_houseload_passthrough_forced",
                False,
            )
        )

        protection_active = bool(
            discharge_blocked_by_soc_min
            or cell_voltage_discharge_blocked
            or cell_voltage_emergency_active
        )

        if not enabled:
            active = False
            target_w = 0.0
            stop_reason = "disabled"

        elif protection_active:
            active = False
            target_w = 0.0
            stop_reason = "protection_active"

        elif float(additional_battery_charge_w or 0.0) > 0.0:
            active = False
            target_w = 0.0
            stop_reason = "additional_battery_charging"

        elif float(soc) <= float(soc_min):
            active = False
            target_w = 0.0
            stop_reason = "soc_min"

        else:
            pv_val = max(0.0, float(pv_w or 0.0))
            house_val = max(0.0, float(house_load_w or 0.0))
            export_val = max(0.0, float(grid_export_w or 0.0))
            import_val = max(0.0, float(grid_import_w or 0.0))
            min_output_w = max(
                60.0,
                float(
                    profile.get(
                        "PV_HOUSELOAD_PASSTHROUGH_MIN_OUTPUT_W",
                        80.0,
                    )
                    or 80.0
                ),
            )

            daylight_available = bool(
                pv_val >= max(20.0, min_pv_w * 0.25)
            )
            sun_state = self.hass.states.get("sun.sun")
            if sun_state is not None:
                daylight_available = bool(
                    str(sun_state.state or "") == "above_horizon"
                )
                if not daylight_available:
                    try:
                        daylight_available = bool(
                            float(
                                sun_state.attributes.get(
                                    "elevation",
                                    -90.0,
                                )
                            )
                            > 0.0
                        )
                    except (TypeError, ValueError):
                        daylight_available = False

            mppt_clips_without_output = capabilities.mppt_clips_without_output
            full_soc_threshold = max(
                float(soc_min),
                float(soc_max) - 1.0,
            )
            full_soc_release_threshold = max(
                float(soc_min),
                float(soc_max) - 2.0,
            )
            battery_near_full = bool(
                float(soc) >= full_soc_release_threshold
            )
            forecast_surplus_expected = forecast_supports_early_pv_passthrough(
                forecast_status=str(forecast_status),
                pv_outlook=str(pv_outlook),
                remaining_today_kwh=float(forecast_remaining_today_kwh or 0.0),
                battery_capacity_kwh=float(battery_capacity_kwh or 0.0),
                soc=float(soc),
                soc_max=float(soc_max),
            )
            forced = bool(
                mppt_clips_without_output
                and daylight_available
                and float(max_output_w or 0.0) >= 60.0
                and house_val >= 60.0
                and (
                    float(soc) >= full_soc_threshold
                    or (
                        forced_prev
                        and float(soc) >= full_soc_release_threshold
                    )
                )
            )

            raw_target_w = min(
                pv_val,
                house_val,
                float(max_output_w or 0.0),
            )

            target_w = raw_target_w

            enough_pv = pv_val >= min_pv_w
            enough_house_load = house_val >= min_house_load_w
            useful_target = raw_target_w >= 60.0

            stable_export_for_pv_charge = (
                export_val >= float(pv_charge_start_export_w or 0.0)
            )

            if stable_export_for_pv_charge:
                export_counter += 1
            else:
                export_counter = 0

            hold_active = False
            if active and started_ts_raw:
                try:
                    started = dt_util.parse_datetime(str(started_ts_raw))
                    if started is not None:
                        elapsed = (
                            dt_util.as_utc(now) - dt_util.as_utc(started)
                        ).total_seconds()
                        hold_active = elapsed < hold_seconds
                except Exception:
                    hold_active = False

            if forced:
                if not active:
                    self._persist[
                        "pv_houseload_passthrough_started_ts"
                    ] = dt_util.as_utc(now).isoformat()

                active = True
                export_counter = 0
                target_w = min(
                    house_val,
                    float(max_output_w or 0.0),
                    max(
                        pv_val + 20.0,
                        min_output_w,
                    ),
                )
                stop_reason = "full_battery_pv_passthrough"

            elif (
                mppt_clips_without_output
                and not battery_near_full
                and not forecast_surplus_expected
            ):
                active = False
                export_counter = 0
                target_w = 0.0
                stop_reason = "battery_not_near_full"

            elif active:
                if not enough_pv:
                    if hold_active:
                        stop_reason = "hold_pv_low"
                    else:
                        active = False
                        target_w = 0.0
                        stop_reason = "pv_low"

                elif not enough_house_load:
                    if hold_active:
                        stop_reason = "hold_house_load_low"
                    else:
                        active = False
                        target_w = 0.0
                        stop_reason = "house_load_low"

                elif export_counter >= export_stop_cycles and not hold_active:
                    active = False
                    target_w = 0.0
                    stop_reason = "stable_export_handover_to_pv_charge"

                elif not useful_target:
                    if hold_active:
                        stop_reason = "hold_target_low"
                    else:
                        active = False
                        target_w = 0.0
                        stop_reason = "target_low"

                else:
                    stop_reason = "active"

            else:
                export_counter = 0

                if (
                    not bool(pv_charge_latched)
                    and enough_pv
                    and enough_house_load
                    and useful_target
                    and export_val < float(pv_charge_start_export_w or 0.0)
                    and (
                        forecast_surplus_expected
                        or import_val <= max(250.0, house_val * 0.50)
                    )
                ):
                    active = True
                    self._persist["pv_houseload_passthrough_started_ts"] = (
                        dt_util.as_utc(now).isoformat()
                    )
                    stop_reason = "started"
                else:
                    target_w = 0.0
                    stop_reason = "conditions_not_met"

        if not active:
            self._persist["pv_houseload_passthrough_started_ts"] = None
            export_counter = 0

        if active:
            target_w = self._sf800_compute_passthrough_output(
                profile=profile,
                raw_target_w=float(target_w or 0.0),
                max_output_w=float(max_output_w or 0.0),
                latch_active=True,
                force_zero=False,
            )
        else:
            target_w = self._sf800_compute_passthrough_output(
                profile=profile,
                raw_target_w=0.0,
                max_output_w=float(max_output_w or 0.0),
                latch_active=False,
                force_zero=True,
            )

        self._persist["pv_houseload_passthrough_active"] = bool(active)
        self._persist["pv_houseload_passthrough_forced"] = bool(forced)
        self._persist["pv_houseload_passthrough_export_counter"] = int(export_counter)
        self._persist["pv_houseload_passthrough_target_w"] = float(target_w or 0.0)
        self._persist["pv_houseload_passthrough_stop_reason"] = str(stop_reason)

        return bool(active), float(target_w or 0.0), str(stop_reason)

    def _update_discharge_resume_hysteresis(
        self,
        soc: float,
        soc_min: float,
        resume_margin: float,
    ) -> bool:
        blocked = bool(self._persist.get("discharge_blocked_by_soc_min", False))
        effective_resume_soc = float(soc_min) + max(0.0, float(resume_margin))

        if float(soc) <= float(soc_min):
            blocked = True
        elif float(soc) >= effective_resume_soc:
            blocked = False

        self._persist["discharge_blocked_by_soc_min"] = blocked
        self._persist["discharge_resume_soc"] = effective_resume_soc

        return blocked

    def _update_cell_voltage_discharge_hysteresis(
        self,
        global_lowest_cell_voltage: float | None,
    ) -> bool:
        blocked = bool(self._persist.get("cell_voltage_discharge_blocked", False))

        if not self._cell_voltage_protection_enabled():
            self._persist["cell_voltage_discharge_blocked"] = False
            self._persist["cell_voltage_resume_threshold"] = None
            return False

        cutoff = self._get_setting(
            SETTING_CELL_VOLTAGE_CUTOFF,
            DEFAULT_CELL_VOLTAGE_CUTOFF,
        )
        resume = self._get_setting(
            SETTING_CELL_VOLTAGE_RESUME,
            DEFAULT_CELL_VOLTAGE_RESUME,
        )

        self._persist["cell_voltage_resume_threshold"] = float(resume)

        if global_lowest_cell_voltage is None:
            self._persist["cell_voltage_discharge_blocked"] = True
            return True

        cell_v = float(global_lowest_cell_voltage)

        if cell_v <= float(cutoff):
            blocked = True
        elif cell_v >= float(resume):
            blocked = False

        self._persist["cell_voltage_discharge_blocked"] = blocked
        return blocked

    def _update_cell_voltage_emergency_hysteresis(
        self,
        global_lowest_cell_voltage: float | None,
    ) -> bool:
        now_utc = self._clock.utc_now()
        previously_active = bool(
            self._persist.get("cell_voltage_emergency_active", False)
        )
        started_at = self._parse_commit_dt(
            self._persist.get("cell_voltage_emergency_started_at")
        )

        if previously_active and started_at is None:
            # Safe upgrade/restart fallback for an already active emergency
            # charge without a stored Beta4 start timestamp.
            started_at = now_utc

        minimum_charge_elapsed = cell_voltage_emergency_minimum_elapsed(
            started_at=started_at if previously_active else None,
            now=now_utc,
        )

        active = next_cell_voltage_emergency_state(
            previously_active=previously_active,
            protection_enabled=self._cell_voltage_protection_enabled(),
            lowest_cell_voltage=global_lowest_cell_voltage,
            warning_voltage=float(
                self._get_setting(
                    SETTING_CELL_VOLTAGE_WARNING,
                    DEFAULT_CELL_VOLTAGE_WARNING,
                )
            ),
            resume_voltage=float(
                self._get_setting(
                    SETTING_CELL_VOLTAGE_RESUME,
                    DEFAULT_CELL_VOLTAGE_RESUME,
                )
            ),
            minimum_charge_elapsed=minimum_charge_elapsed,
        )

        if active:
            if started_at is None:
                started_at = now_utc
            self._persist["cell_voltage_emergency_started_at"] = (
                started_at.isoformat()
            )
        else:
            self._persist["cell_voltage_emergency_started_at"] = None

        self._persist["cell_voltage_emergency_active"] = active
        return active

    def _update_cell_voltage_post_emergency_discharge_lock(
        self,
        *,
        cell_voltage_emergency_active: bool,
        decision_action: str,
        decision_reason: str,
        measured_charge_w: float,
        soc: float,
        resume_soc: float,
        global_lowest_cell_voltage: float | None,
    ) -> bool:
        """Keep discharge blocked after a pure cell-voltage emergency charge."""
        resume_voltage = float(
            self._get_setting(
                SETTING_CELL_VOLTAGE_RESUME,
                DEFAULT_CELL_VOLTAGE_RESUME,
            )
        )
        locked, normal_charge_observed = next_cell_voltage_discharge_lock_state(
            previously_locked=bool(
                self._persist.get(
                    "cell_voltage_post_emergency_discharge_locked", False
                )
            ),
            normal_charge_observed=bool(
                self._persist.get("cell_voltage_normal_charge_observed", False)
            ),
            cell_voltage_emergency_active=bool(cell_voltage_emergency_active),
            decision_action=str(decision_action or ""),
            decision_reason=str(decision_reason or ""),
            measured_charge_w=float(measured_charge_w or 0.0),
            soc=float(soc),
            resume_soc=float(resume_soc),
            lowest_cell_voltage=global_lowest_cell_voltage,
            resume_voltage=resume_voltage,
            protection_enabled=self._cell_voltage_protection_enabled(),
            battery_full=bool(self._get_soc_limit() == 1),
        )
        self._persist["cell_voltage_post_emergency_discharge_locked"] = locked
        self._persist["cell_voltage_normal_charge_observed"] = (
            normal_charge_observed
        )
        return locked

    def _season_detection(
        self,
        pv_w: float,
        export_w: float,
        now: datetime | None = None,
    ) -> str:
        season = self._persist.get("season_mode", "winter")
        counter = _clamp_season_counter(
            self._persist.get("season_counter", 0)
        )

        installed_pv_wp = self._get_installed_pv_wp()

        if installed_pv_wp <= 0:
            summer_pv_threshold = 1100.0
            summer_export_threshold = 350.0
            winter_pv_threshold = 500.0
            winter_export_threshold = 140.0
        else:
            summer_pv_threshold = max(900.0, installed_pv_wp * 0.46)
            summer_export_threshold = max(300.0, installed_pv_wp * 0.15)

            winter_pv_threshold = max(450.0, installed_pv_wp * 0.22)
            winter_export_threshold = max(120.0, installed_pv_wp * 0.06)

        summer_signal = (
            pv_w > summer_pv_threshold
            and export_w > summer_export_threshold
        )

        winter_signal = (
            pv_w < winter_pv_threshold
            and export_w < winter_export_threshold
        )
        
        try:
            local_now = dt_util.as_local(now or self._clock.utc_now())
            season_eval_hour = local_now.hour + (local_now.minute / 60.0)
        except Exception:
            season_eval_hour = 12.0

        winter_evaluation_active = (
            SEASON_WINTER_EVALUATION_START_HOUR
            <= season_eval_hour
            < SEASON_WINTER_EVALUATION_END_HOUR
        )

        if summer_signal:
            counter += 1

        elif winter_signal and winter_evaluation_active:
            counter -= 1

        elif winter_evaluation_active:
            # Only decay towards neutral during the daytime evaluation window.
            # Outside this window we keep the last season tendency stable, so
            # evening/night darkness does not undo a valid summer detection.
            if counter > 0:
                counter -= 1
            elif counter < 0:
                counter += 1

        counter = _clamp_season_counter(counter)

        thresh = 30
        if counter > thresh:
            season = "summer"
        elif counter < -thresh:
            season = "winter"

        self._persist["season_mode"] = season
        self._persist["season_counter"] = counter

        self._persist["season_thresholds"] = {
            "installed_pv_wp": installed_pv_wp,
            "summer_pv_threshold": summer_pv_threshold,
            "summer_export_threshold": summer_export_threshold,
            "winter_pv_threshold": winter_pv_threshold,
            "winter_export_threshold": winter_export_threshold,
            "counter": counter,
            "winter_evaluation_active": bool(winter_evaluation_active),
            "season_eval_hour": round(float(season_eval_hour), 2),
            "winter_evaluation_start_hour": float(
                SEASON_WINTER_EVALUATION_START_HOUR
            ),
            "winter_evaluation_end_hour": float(
                SEASON_WINTER_EVALUATION_END_HOUR
            ),
        }

        return season

    def _map_ai_status(self, ai_mode: str, action: str, reason: str) -> str:
        source_reason = None
        if reason == "charge_commit_active":
            source_reason = str(
                self._persist.get("charge_commit_source_reason", "") or ""
            )
        return map_ai_status(
            ai_mode,
            action,
            reason,
            source_reason=source_reason,
        )

    def _map_reco(self, action: str) -> str:
        if action == "passthrough":
            return RECO_STANDBY
        if action == "charge":
            return RECO_CHARGE
        if action == "discharge":
            return RECO_DISCHARGE
        if action == "emergency":
            return RECO_EMERGENCY
        return RECO_STANDBY

    def _map_charge_strategy(self, ai_mode: str, action: str, reason: str) -> str:
        if ai_mode == AI_MODE_MANUAL:
            return "manual"

        if action == "emergency":
            return "emergency"

        if reason == "pv_surplus_charge":
            return "pv_surplus"

        if reason == "planning_latest_start":
            return "planning_latest_start"

        if reason == "planning_forecast_poor":
            return "planning_forecast_poor"

        if reason == "planning_forecast_mixed":
            return "planning_forecast_mixed"

        if reason == "valley_boost_charge":
            return "valley_boost"

        if reason == "valley_boost_charge_mixed_forecast":
            return "valley_boost_mixed"

        if reason == "planning_forecast_reality_override":
            return "planning_reality_override"

        if reason == "very_cheap_force_charge":
            return "very_cheap"

        if reason == "valley_opportunity_charge":
            return "valley_opportunity"

        if reason == "valley_opportunity_charge_mixed_forecast":
            return "valley_opportunity_mixed"
            
        if reason == "summer_peak_reserve_charge":
            return "reserve"

        return "none"

    async def _enter_safe_idle(
        self,
        *,
        reason: str,
        raw_values: dict[str, Any],
    ) -> dict[str, Any]:
        """Stop the active command and expose a deterministic safe-idle state."""

        package = self._debug_recorder.tick(now=self._clock.utc_now())
        if package is not None:
            await self._async_export_debug_package(package)

        current_mode = str(
            self._state(self.entities.ac_mode)
            or self._persist.get("last_set_mode")
            or ""
        )
        last_input_w = float(
            self._persist.get("last_set_input_w", 0.0) or 0.0
        )
        last_output_w = float(
            self._persist.get("last_set_output_w", 0.0) or 0.0
        )

        stop_input = bool(
            current_mode == ZENDURE_MODE_INPUT or last_input_w > 0.0
        )
        stop_output = bool(
            not stop_input
            and (
                current_mode == ZENDURE_MODE_OUTPUT
                or last_output_w > 0.0
            )
        )
        safe_idle_command = DeviceCommand(
            ac_mode=("input" if stop_input else "output"),
            input_limit_w=0.0,
            output_limit_w=0.0,
            reason=reason,
            should_write_mode=False,
            should_write_input=stop_input,
            should_write_output=stop_output,
            skipped=not (stop_input or stop_output),
            skip_reason=("none" if stop_input or stop_output else "unchanged"),
            metadata={"command_path": "safe_idle"},
        )
        await self._execute_device_command(
            safe_idle_command,
            force_power=True,
        )

        self._persist["last_set_input_w"] = 0
        self._persist["last_set_output_w"] = 0
        self._persist["prev_charge_w"] = 0.0
        self._persist["prev_discharge_w"] = 0.0
        self._persist["power_state"] = "idle"
        self._persist["next_action_time"] = None
        self._persist["regulation_active_state"] = "none"
        self._persist["regulation_last_requested_mode"] = "idle"
        self._persist["regulation_last_resolved_mode"] = "idle"
        self._persist["regulation_skipped_write_reason"] = reason
        self._persist["debug"] = reason.upper()
        self._persist["last_ts"] = self._clock.utc_now().isoformat()
        await self._save()

        details = {
            **raw_values,
            "strategy_state": "idle_safe",
            "visible_state": "safe_idle",
            "strategic_reason": reason,
            "technical_reason": reason,
            "strategy_priority": 800,
            "regulation_command_path": "unified",
        }

        return {
            "status": STATUS_SENSOR_INVALID,
            "ai_status": AI_STATUS_STANDBY,
            "recommendation": RECO_STANDBY,
            "debug": reason.upper(),
            **self._debug_status_data(),
            "details": details,
            "decision_reason": reason,
            "next_action_time": None,
            "next_action_state": "none",
            "device_profile": self.device_profile_key,
            "season_mode": self._persist.get("season_mode", "winter"),
            "fault_level_status": "warning",
            "engine_health": reason,
            "strategy_state": "idle_safe",
            "visible_state": "safe_idle",
            "strategic_reason": reason,
            "technical_reason": reason,
            "strategy_priority": 800,
        }

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            if self._persist.get("last_ts") is None:
                await self._load()
                self._persist["last_ts"] = self._clock.utc_now().isoformat()

            now = self._clock.utc_now()

            native_runtime = getattr(self, "native_zendure", None)
            native_baseline = (
                native_runtime.consume_control_baseline()
                if native_runtime is not None
                and hasattr(native_runtime, "consume_control_baseline")
                else None
            )
            if native_baseline is not None:
                baseline_mode, baseline_input_w, baseline_output_w = native_baseline
                self._persist["last_set_mode"] = baseline_mode
                self._persist["last_set_input_w"] = baseline_input_w
                self._persist["last_set_output_w"] = baseline_output_w
                self._persist["prev_charge_w"] = baseline_input_w
                self._persist["prev_discharge_w"] = baseline_output_w
                self._persist["native_handover_baseline_mode"] = baseline_mode
                self._persist["native_handover_baseline_input_w"] = baseline_input_w
                self._persist["native_handover_baseline_output_w"] = baseline_output_w

            soc = _to_float(self._state(self.entities.soc), None)
            pv = _to_float(self._state(self.entities.pv), None)
            native_pv = _to_float(self._state(self.entities.native_pv), None)

            if soc is None or not 0.0 <= float(soc) <= 100.0:
                return await self._enter_safe_idle(
                    reason="soc_invalid",
                    raw_values={
                        "soc_raw": self._state(self.entities.soc),
                        "pv_raw": self._state(self.entities.pv),
                    },
                )

            soc = float(soc)
            pv_sensor_valid = pv is not None
            pv_w = float(pv or 0.0)
            native_pv_configured = bool(self.entities.native_pv)
            native_pv_sensor_valid = native_pv is not None
            native_pv_w = float(native_pv or 0.0)

            battery_capacity_kwh = self._get_battery_capacity()

            prev_soc = self._persist.get("prev_soc")
            delta_kwh = 0.0

            if prev_soc is not None and battery_capacity_kwh > 0:
                soc_delta_pct = soc - prev_soc
                delta_kwh = battery_capacity_kwh * (soc_delta_pct / 100.0)

            self._persist["prev_soc"] = soc

            profile = self._get_active_profile()
            device_capabilities = self._device_profile.capabilities
            
            export_market_price = self._get_export_market_price(now)
            feed_in_tariff = float(
                export_market_price.current_price
                if export_market_price.valid
                else 0.0
            )

            offgrid_raw = _to_float(
                self._state(self.entities.offgrid_power),
                None,
            )

            offgrid_mode_raw = self._state(self.entities.offgrid_mode)
            offgrid_mode = self._normalize_offgrid_mode(offgrid_mode_raw)

            supports_offgrid_socket = bool(
                device_capabilities.supports_offgrid_socket
            ) or bool(self.entities.offgrid_power)

            supports_offgrid_input = device_capabilities.supports_offgrid_input

            offgrid_load_active_w = float(
                profile.get("OFFGRID_LOAD_ACTIVE_W", 50.0) or 50.0
            )

            offgrid_available = bool(
                supports_offgrid_socket
                and self.entities.offgrid_power
                and offgrid_raw is not None
            )

            offgrid_power_raw_w = float(offgrid_raw or 0.0)

            # Confirmed for SF2400Pro/ZHA:
            # positive Off-Grid power means active load at the island socket.
            offgrid_power_w = max(0.0, offgrid_power_raw_w)

            offgrid_mode_allows_active = offgrid_mode not in ("off",)

            offgrid_load_active = bool(
                offgrid_available
                and offgrid_mode_allows_active
                and offgrid_power_w > offgrid_load_active_w
            )

            # Diagnostic only for now. Direction for Off-Grid input/source still
            # needs separate verification.
            offgrid_source_active = bool(
                supports_offgrid_input
                and offgrid_available
                and offgrid_power_raw_w < -offgrid_load_active_w
            )

            offgrid_active = bool(offgrid_load_active or offgrid_source_active)

            soc_min = self._get_setting(
                SETTING_SOC_MIN,
                profile.get("SOC_MIN", DEFAULT_SOC_MIN),
            )
            soc_max = self._get_setting(
                SETTING_SOC_MAX,
                profile.get("SOC_MAX", DEFAULT_SOC_MAX),
            )
            resume_margin = float(profile.get("SOC_DISCHARGE_RESUME_MARGIN", 3.0))

            max_charge = self._get_setting(
                SETTING_MAX_CHARGE,
                profile.get("MAX_CHARGE_W", DEFAULT_MAX_CHARGE),
            )
            max_discharge = self._get_setting(
                SETTING_MAX_DISCHARGE,
                profile.get("MAX_DISCHARGE_W", DEFAULT_MAX_DISCHARGE),
            )

            profile_max_in = float(profile.get("MAX_INPUT_W", max_charge))
            profile_max_out = float(profile.get("MAX_OUTPUT_W", max_discharge))
            max_charge = min(float(max_charge), profile_max_in)
            max_discharge = min(float(max_discharge), profile_max_out)

            soc_limits_valid = bool(
                0.0 <= float(soc_min) < float(soc_max) <= 100.0
            )
            power_limits_valid = bool(
                float(max_charge) >= 0.0
                and float(max_discharge) > 0.0
                and float(profile_max_in) > 0.0
                and float(profile_max_out) > 0.0
            )

            price_profile = price_input_profile(self.price_currency)
            expensive = self._get_setting(
                SETTING_PRICE_THRESHOLD,
                price_profile.default_expensive_threshold,
            )
            very_expensive = self._get_setting(
                SETTING_VERY_EXPENSIVE_THRESHOLD,
                price_profile.default_very_expensive_threshold,
            )
            emergency_soc = self._get_setting(SETTING_EMERGENCY_SOC, DEFAULT_EMERGENCY_SOC)
            emergency_w = self._get_setting(SETTING_EMERGENCY_CHARGE, DEFAULT_EMERGENCY_CHARGE)
            profit_margin_pct = self._get_setting(
                SETTING_PROFIT_MARGIN_PCT,
                DEFAULT_PROFIT_MARGIN_PCT,
            )
            forecast_base_load_w = self._get_setting(
                SETTING_FORECAST_BASE_LOAD,
                DEFAULT_FORECAST_BASE_LOAD,
            )
            learned_planning_enabled = bool(
                self.entry.options.get(
                    SETTING_LEARNED_PLANNING_ENABLED,
                    DEFAULT_LEARNED_PLANNING_ENABLED,
                )
            )

            ai_mode = normalize_ai_mode(
                self.runtime_mode.get("ai_mode", AI_MODE_AUTOMATIC)
            )
            self.runtime_mode["ai_mode"] = ai_mode
            manual_action = str(self.runtime_mode.get("manual_action", MANUAL_STANDBY))
            
            # V4.3.0-dev5.7:
            # Strategic PV handover policy.
            #
            # Automatic:
            #   React quickly to confirmed PV surplus. Short grid-import phases
            #   do not need to trigger immediate house-load coverage.
            #
            # Autarky (internal legacy key AI_MODE_SUMMER):
            #   Preserve stronger INPUT/OUTPUT hysteresis because continuous
            #   house-load coverage has priority and changing clouds must not
            #   cause rapid mode flapping.
            #
            # Manual:
            #   No automatic PV handover policy is required.
            if ai_mode == AI_MODE_AUTOMATIC:
                pv_handover_policy = "fast"
                load_coverage_priority = False

            elif ai_mode == AI_MODE_SUMMER:
                pv_handover_policy = "stable"
                load_coverage_priority = True

            else:
                pv_handover_policy = "default"
                load_coverage_priority = False

            grid_sensor_configured = self.entities.grid_mode != GRID_MODE_NONE
            grid_import_raw, grid_export_raw = self._get_grid()
            grid_sensor_valid = bool(
                grid_sensor_configured
                and grid_import_raw is not None
                and grid_export_raw is not None
            )
            grid_import = float(grid_import_raw or 0.0)
            grid_export = float(grid_export_raw or 0.0)
                
            grid_history_state = self._grid_history.update(
                grid_import_w=float(grid_import or 0.0),
                grid_export_w=float(grid_export or 0.0),
            )

            import_market_price = self._get_import_market_price(now)
            price_now = (
                import_market_price.current_price
                if import_market_price.valid
                else None
            )
            price_points = list(
                import_market_price.forecast.points
                if import_market_price.forecast is not None
                else ()
            )

            forecast_summary = build_forecast_summary(
                hass=self.hass,
                today_entity_id=self.entities.pv_forecast_today,
                tomorrow_entity_id=self.entities.pv_forecast_tomorrow,
                installed_pv_wp=self._get_installed_pv_wp(),
                forecast_base_load_w=float(forecast_base_load_w),
                clock=self._clock,
            )

            additional_battery_charge_w = _to_float(
                self._state(self.entities.additional_battery_charge),
                0.0,
            )
            additional_battery_charge_w = float(additional_battery_charge_w or 0.0)

            additional_battery_discharge_w = _to_float(
                self._state(self.entities.additional_battery_discharge),
                0.0,
            )
            additional_battery_discharge_w = float(additional_battery_discharge_w or 0.0)
            additional_battery_discharge_active = additional_battery_discharge_w > 50.0

            if additional_battery_discharge_active:
                self._persist["pv_charge_latched"] = False
                self._persist["pv_charge_start_counter"] = 0
                self._persist["pv_charge_stop_counter"] = 0

            daily_avg_price = None
            daily_min_price = None
            daily_max_price = None

            if price_points:
                prices = [float(p.price) for p in price_points]

                if prices:
                    daily_avg_price = sum(prices) / len(prices)
                    daily_min_price = min(prices)
                    daily_max_price = max(prices)

            peak_factor = float(
                self.runtime_settings.get(
                    SETTING_PEAK_FACTOR,
                    DEFAULT_PEAK_FACTOR,
                )
            )

            valley_factor = float(
                self.runtime_settings.get(
                    SETTING_VALLEY_FACTOR,
                    DEFAULT_VALLEY_FACTOR,
                ) or DEFAULT_VALLEY_FACTOR
            )

            pv_charge_start_export_w = self._get_setting(
                SETTING_PV_CHARGE_START_EXPORT_W,
                DEFAULT_PV_CHARGE_START_EXPORT_W,
            )

            battery_raw = self._state(self.entities.battery_ac_power)
            battery_power_value = _to_float(battery_raw, None)
            battery_ac_power_sensor_valid = battery_power_value is not None
            battery_power = (
                float(battery_power_value)
                if battery_power_value is not None
                else 0.0
            )
            battery_power = float(battery_power or 0.0)

            battery_discharge_w = max(0.0, battery_power)
            battery_charge_w = max(0.0, -battery_power)

            pv_attributable_export_w = compute_pv_attributable_export_w(
                grid_export_w=float(grid_export or 0.0),
                battery_discharge_w=float(battery_discharge_w),
                previous_discharge_w=float(
                    self._persist.get("prev_discharge_w", 0.0)
                    or 0.0
                ),
                last_output_w=float(
                    self._persist.get("last_set_output_w", 0.0)
                    or 0.0
                ),
                additional_battery_discharge_w=float(
                    additional_battery_discharge_w or 0.0
                ),
            )

            pv_charge_start_counter, pv_charge_stop_counter, pv_charge_latched = (
                self._update_pv_charge_hysteresis(
                    grid_import_w=float(grid_import or 0.0),
                    grid_export_w=float(grid_export or 0.0),
                    pv_w=float(pv_w or 0.0),
                    pv_charge_start_export_w=float(pv_charge_start_export_w),
                    battery_discharge_w=float(battery_discharge_w),
                    previous_discharge_w=float(
                        self._persist.get("prev_discharge_w", 0.0)
                        or 0.0
                    ),
                    last_output_w=float(
                        self._persist.get("last_set_output_w", 0.0)
                        or 0.0
                    ),
                    additional_battery_discharge_w=float(
                        additional_battery_discharge_w or 0.0
                    ),
                    mppt_clips_without_output=(
                        device_capabilities.mppt_clips_without_output
                    ),
                )
            )

            very_cheap_price = self.runtime_settings.get("very_cheap_price", None)
            if very_cheap_price is not None:
                try:
                    very_cheap_price = float(very_cheap_price)
                except Exception:
                    very_cheap_price = None

            engine_health = "ok"
            if not grid_sensor_valid:
                engine_health = "grid_sensor_invalid"
            elif not pv_sensor_valid:
                engine_health = "pv_sensor_invalid"
            elif not price_points:
                engine_health = "no_price_data"
            elif price_now is None:
                engine_health = "no_current_price"

            house_load = max(
                0.0,
                float(grid_import)
                + float(pv_w)
                + float(battery_discharge_w)
                - float(grid_export)
                - float(battery_charge_w)
            )

            # V4.1.0 learned charge-window planning:
            # Data collection and diagnostics only. No decision impact yet.
            self._update_learned_load_history(
                now=now,
                house_load_w=float(house_load),
            )

            learned_samples = self._get_learned_load_samples()

            learned_slot_model = build_slot_model(
                samples=learned_samples,
                now=now,
            )
            learned_profile_diagnostics = build_profile_diagnostics(
                model=learned_slot_model,
                now=now,
            )

            learned_readiness = evaluate_readiness(learned_slot_model)

            learned_charge_power_samples = self._get_learned_charge_power_samples()
            learned_charge_power = learned_typical_charge_power_w(
                samples=learned_charge_power_samples,
                now=now,
            )

            learned_charge_plan = build_learned_charge_plan(
                model=learned_slot_model,
                readiness=learned_readiness,
                now=now,
                market_price=import_market_price,
                forecast=forecast_summary,
                total_battery_capacity_kwh=float(battery_capacity_kwh),
                current_soc=float(soc),
                soc_min=float(soc_min),
                soc_max=float(soc_max),
                profile_charge_limit_w=float(max_charge),
                current_effective_charge_cap_w=float(max_charge),
                learned_typical_charge_power_w=learned_charge_power,
                force_active=False,
            )

            season = self._season_detection(
                pv_w=pv_w,
                export_w=float(grid_export),
                now=now,
            )
            
            # V4.3.0-dev5.0:
            # Build the new unified automatic-strategy context.
            #
            # Diagnostic only in dev5.0. DecisionEngine still uses the existing
            # strategy paths, so this must not change charging or discharging.
            automatic_season_context = (
                "summer_like"
                if str(season) == "summer"
                else "winter_like"
                if str(season) == "winter"
                else "neutral"
            )

            automatic_strategy_context = self._automatic_strategy.evaluate(
                automatic_mode_active=(
                    str(ai_mode) == AI_MODE_AUTOMATIC
                ),
                season_context=automatic_season_context,
                pv_w=float(pv_w or 0.0),
                house_load_w=float(house_load or 0.0),
                installed_pv_wp=float(
                    self._get_installed_pv_wp()
                ),
                soc=float(soc),
                soc_min=float(soc_min),
                soc_max=float(soc_max),
                price_now=price_now,
                price_min=daily_min_price,
                price_max=daily_max_price,
                price_average=daily_avg_price,
                forecast_status=str(
                    forecast_summary.status
                ),
                pv_outlook=str(
                    forecast_summary.pv_outlook
                ),
                forecast_remaining_today_kwh=float(
                    forecast_summary.remaining_today_kwh
                ),
                forecast_tomorrow_kwh=float(
                    forecast_summary.tomorrow_kwh
                ),
                grid_import_w=float(grid_import or 0.0),
                metadata={
                    "legacy_season_mode": str(season),
                    "grid_import_w": round(
                        float(grid_import or 0.0),
                        2,
                    ),
                    "grid_export_w": round(
                        float(grid_export or 0.0),
                        2,
                    ),
                    "daily_min_price": daily_min_price,
                    "daily_max_price": daily_max_price,
                    "daily_average_price": daily_avg_price,
                },
            )

            global_lowest_cell_voltage = self._get_global_lowest_cell_voltage()
            cell_voltage_status = self._get_cell_voltage_status(global_lowest_cell_voltage)
            cell_voltage_soc_plausibility = self._get_cell_voltage_soc_plausibility(
                soc=float(soc),
                soc_min=float(soc_min),
                global_lowest_cell_voltage=global_lowest_cell_voltage,
            )

            self._persist["global_lowest_cell_voltage"] = global_lowest_cell_voltage
            self._persist["cell_voltage_status"] = cell_voltage_status
            self._persist["cell_voltage_soc_plausibility"] = cell_voltage_soc_plausibility

            cell_voltage_discharge_blocked = self._update_cell_voltage_discharge_hysteresis(
                global_lowest_cell_voltage
            )
            cell_voltage_discharge_blocked = bool(
                cell_voltage_discharge_blocked
                or self._persist.get(
                    "cell_voltage_post_emergency_discharge_locked", False
                )
            )

            discharge_blocked_by_soc_min = self._update_discharge_resume_hysteresis(
                soc=float(soc),
                soc_min=float(soc_min),
                resume_margin=float(resume_margin),
            )

            (
                trade_soc_min_reset_count,
                trade_cycle_below_soc_min,
            ) = trade_soc_min_reset_state(
                soc=float(soc),
                soc_min=float(soc_min),
                previous_count=int(
                    self._persist.get("trade_soc_min_reset_count", 0) or 0
                ),
                previously_confirmed=bool(
                    self._persist.get("trade_cycle_below_soc_min", False)
                ),
            )
            self._persist["trade_soc_min_reset_count"] = (
                trade_soc_min_reset_count
            )

            if trade_cycle_below_soc_min:
                self._persist["trade_avg_charge_price"] = 0.0
                self._persist["trade_charged_kwh"] = 0.0
                self._persist["trade_cycle_below_soc_min"] = True
                self._persist["pending_charge_price_evidence"] = None
            elif float(soc) > float(soc_min):
                self._persist["trade_cycle_below_soc_min"] = False

            cell_voltage_emergency_active = (
                self._update_cell_voltage_emergency_hysteresis(
                    global_lowest_cell_voltage
                )
            )

            manual_mode_active = ai_mode == AI_MODE_MANUAL

            if manual_mode_active:
                sf800_stop_reason = "manual_mode"

                self._persist["pv_houseload_passthrough_active"] = False
                self._persist["pv_houseload_passthrough_forced"] = False
                self._persist["pv_houseload_passthrough_started_ts"] = None
                self._persist["pv_houseload_passthrough_export_counter"] = 0
                self._persist["pv_houseload_passthrough_target_w"] = 0.0
                self._persist["pv_houseload_passthrough_stop_reason"] = sf800_stop_reason

                pv_houseload_passthrough_active = False
                pv_houseload_passthrough_target_w = 0.0
                pv_houseload_passthrough_stop_reason = sf800_stop_reason
            else:
                pv_houseload_passthrough_active, pv_houseload_passthrough_target_w, pv_houseload_passthrough_stop_reason = (
                    self._update_pv_houseload_passthrough(
                        now=now,
                        profile=profile,
                        soc=float(soc),
                        soc_min=float(soc_min),
                        soc_max=float(soc_max),
                        pv_w=float(pv_w),
                        house_load_w=float(house_load),
                        grid_import_w=float(grid_import or 0.0),
                        grid_export_w=float(grid_export or 0.0),
                        max_output_w=float(max_discharge),
                        pv_charge_start_export_w=float(pv_charge_start_export_w),
                        discharge_blocked_by_soc_min=bool(discharge_blocked_by_soc_min),
                        cell_voltage_discharge_blocked=bool(cell_voltage_discharge_blocked),
                        cell_voltage_emergency_active=bool(cell_voltage_emergency_active),
                        additional_battery_charge_w=float(additional_battery_charge_w or 0.0),
                        pv_charge_latched=bool(pv_charge_latched),
                        forecast_status=str(forecast_summary.status),
                        pv_outlook=str(forecast_summary.pv_outlook),
                        forecast_remaining_today_kwh=float(
                            forecast_summary.remaining_today_kwh
                        ),
                        battery_capacity_kwh=float(battery_capacity_kwh),
                    )
                )

            ctx = RuntimeSnapshot(
                now=now,
                soc=soc,
                soc_min=float(soc_min),
                soc_max=float(soc_max),
                emergency_soc=float(emergency_soc),
                emergency_charge_w=float(emergency_w),
                max_charge_w=float(max_charge),
                max_discharge_w=float(max_discharge),
                grid_import_w=float(grid_import),
                grid_export_w=float(grid_export),
                pv_w=float(pv_w),
                house_load_w=float(house_load),
                battery_discharge_w=float(battery_discharge_w),
                last_output_w=float(
                    self._persist.get("last_set_output_w", 0.0)
                    or 0.0
                ),
                avg_charge_price=self._persist.get("trade_avg_charge_price"),
                expensive_threshold=float(expensive),
                very_expensive_threshold=float(very_expensive),
                profit_margin_pct=float(profit_margin_pct),
                import_market_price=import_market_price,
                export_market_price=export_market_price,
                ai_mode=ai_mode,
                manual_action=manual_action,
                season=season,
                profile=profile,
                prev_discharge_w=float(self._persist.get("prev_discharge_w", 0.0)),
                prev_charge_w=float(self._persist.get("prev_charge_w", 0.0)),
                battery_capacity_kwh=battery_capacity_kwh,
                peak_factor=peak_factor,
                valley_factor=valley_factor,
                very_cheap_price=very_cheap_price,
                additional_battery_charge_w=additional_battery_charge_w,
                additional_battery_discharge_w=additional_battery_discharge_w,
                pv_charge_start_export_w=float(pv_charge_start_export_w),
                cell_voltage_emergency_active=cell_voltage_emergency_active,
                forecast=forecast_summary,
                pv_charge_start_counter=int(pv_charge_start_counter),
                pv_charge_stop_counter=int(pv_charge_stop_counter),
                pv_charge_latched=bool(pv_charge_latched),
                forecast_wait_block_counter=int(self._persist.get("forecast_wait_block_counter", 0)),
                discharge_blocked_by_soc_min=bool(discharge_blocked_by_soc_min),
                cell_voltage_discharge_blocked=bool(cell_voltage_discharge_blocked),
                pv_houseload_passthrough_active=bool(pv_houseload_passthrough_active),
                pv_houseload_passthrough_target_w=float(pv_houseload_passthrough_target_w),
                pv_houseload_passthrough_stop_reason=str(pv_houseload_passthrough_stop_reason),
                learned_charge_plan=learned_charge_plan,
                learned_planning_enabled=bool(learned_planning_enabled),
                offgrid_power_w=float(offgrid_power_w),
                offgrid_mode=str(offgrid_mode),
                offgrid_available=bool(offgrid_available),
                offgrid_active=bool(offgrid_active),
                offgrid_load_active=bool(offgrid_load_active),
                offgrid_source_active=bool(offgrid_source_active),
                automatic_strategy_active=bool(
                    automatic_strategy_context.active
                ),
                automatic_weighting=str(
                    automatic_strategy_context.weighting
                ),
                automatic_pv_weight=float(
                    automatic_strategy_context.pv_weight
                ),
                automatic_price_weight=float(
                    automatic_strategy_context.price_weight
                ),
                automatic_reserve_weight=float(
                    automatic_strategy_context.reserve_weight
                ),
                automatic_forecast_weight=float(
                    automatic_strategy_context.forecast_weight
                ),
                automatic_discharge_allowed=bool(
                    automatic_strategy_context.metadata.get(
                        "automatic_discharge_allowed",
                        False,
                    )
                ),
                automatic_discharge_reason=str(
                    automatic_strategy_context.metadata.get(
                        "automatic_discharge_reason",
                        "not_evaluated",
                    )
                ),
                automatic_peak_reserve_allowed=bool(
                    automatic_strategy_context.metadata.get(
                        "automatic_peak_reserve_allowed",
                        False,
                    )
                ),
                automatic_peak_reserve_reason=str(
                    automatic_strategy_context.metadata.get(
                        "automatic_peak_reserve_reason",
                        "not_evaluated",
                    )
                ),
                automatic_valley_charge_allowed=bool(
                    automatic_strategy_context.metadata.get(
                        "automatic_valley_charge_allowed",
                        False,
                    )
                ),
                automatic_valley_charge_reason=str(
                    automatic_strategy_context.metadata.get(
                        "automatic_valley_charge_reason",
                        "not_evaluated",
                    )
                ),
                automatic_planning_allowed=bool(
                    automatic_strategy_context.metadata.get(
                        "automatic_planning_allowed",
                        False,
                    )
                ),
                automatic_planning_reason=str(
                    automatic_strategy_context.metadata.get(
                        "automatic_planning_reason",
                        "not_evaluated",
                    )
                ),
                grid_sensor_configured=bool(grid_sensor_configured),
                grid_sensor_valid=bool(grid_sensor_valid),
                pv_sensor_valid=bool(pv_sensor_valid),
                soc_limits_valid=bool(soc_limits_valid),
                power_limits_valid=bool(power_limits_valid),
            )

            base_required_kwh = (
                battery_capacity_kwh
                * max(0.0, float(soc_max) - float(soc))
                / 100.0
            )

            if (
                self._engine._forecast_supports_waiting(ctx, base_required_kwh)
                and self._engine._is_valley_price_now(ctx)
                and self._engine._is_real_pv_underperforming(ctx)
            ):
                self._persist["forecast_wait_block_counter"] = int(
                    self._persist.get("forecast_wait_block_counter", 0)
                ) + 1
            else:
                self._persist["forecast_wait_block_counter"] = 0

            ctx.forecast_wait_block_counter = int(
                self._persist.get("forecast_wait_block_counter", 0)
            )

            learned_planning_blocks_competing_grid_charge = bool(
                self._engine._learned_planning_waits_for_window(ctx)
            )

            decision = self._engine.evaluate(ctx)
            strategy_selection = self._engine.last_strategy_selection

            cell_voltage_post_emergency_discharge_locked = (
                self._update_cell_voltage_post_emergency_discharge_lock(
                    cell_voltage_emergency_active=bool(
                        cell_voltage_emergency_active
                    ),
                    decision_action=str(decision.action or ""),
                    decision_reason=str(decision.reason or ""),
                    measured_charge_w=float(battery_charge_w or 0.0),
                    soc=float(soc),
                    resume_soc=float(soc_min) + max(0.0, float(resume_margin)),
                    global_lowest_cell_voltage=global_lowest_cell_voltage,
                )
            )
            cell_voltage_discharge_blocked = bool(
                cell_voltage_discharge_blocked
                or cell_voltage_post_emergency_discharge_locked
            )

            strict_low_soc_protection = bool(profile.get("LOW_SOC_PROTECTION_STRICT", False))
            low_soc_pv_charge_requires_export = bool(
                profile.get("LOW_SOC_PV_CHARGE_REQUIRES_EXPORT", False)
            )
            protection_active = bool(
                discharge_blocked_by_soc_min or cell_voltage_discharge_blocked
            )

            if (
                strict_low_soc_protection
                and low_soc_pv_charge_requires_export
                and protection_active
                and decision.ac_mode == "input"
                and float(decision.charge_w or 0.0) > 0.0
                and decision.reason == "pv_surplus_charge"
            ):
                if (
                    float(grid_export or 0.0) < float(pv_charge_start_export_w)
                    or float(grid_import or 0.0) > 30.0
                ):
                    decision.charge_w = 0.0
                    decision.discharge_w = 0.0
                    decision.action = "idle"
                    decision.ac_mode = "output"
                    decision.reason = "pv_charge_blocked_by_discharge_protection"
                    
            soc_limit = self._get_soc_limit()

            # V4.3.0-dev8:
            # Off-Grid load remains visible in diagnostics but no longer
            # rewrites the selected INPUT/OUTPUT strategy. The device itself
            # supplies the island socket independently from the AC house path.

            if soc_limit == 1 and decision.ac_mode == "input" and float(decision.charge_w or 0.0) > 0:
                decision.charge_w = 0.0
                decision.action = "idle"
                decision.reason = "soc_limit_upper"
            elif soc_limit == 2 and decision.ac_mode == "output" and float(decision.discharge_w or 0.0) > 0:
                decision.discharge_w = 0.0
                decision.action = "idle"
                decision.reason = "soc_limit_lower"

            if (
                decision.ac_mode == "output"
                and float(decision.discharge_w or 0.0) > 0.0
                and discharge_blocked_by_soc_min
                and decision.reason != "pv_house_load_passthrough"
            ):
                decision.discharge_w = 0.0
                decision.action = "idle"
                decision.reason = "soc_min_resume_block"

            if (
                decision.ac_mode == "output"
                and float(decision.discharge_w or 0.0) > 0.0
                and cell_voltage_discharge_blocked
                and decision.reason != "pv_house_load_passthrough"
            ):
                decision.discharge_w = 0.0
                decision.action = "idle"
                decision.reason = (
                    "cell_voltage_sensor_invalid"
                    if cell_voltage_status == "sensor_invalid"
                    else "cell_voltage_cutoff_block"
                )

            # Keep active discharge stable without coupling Automatic mode to
            # the seasonal diagnostic context.
            #
            # - Explicit Autarkie mode keeps the existing house-load coverage.
            # - Automatic only keeps an already active economic discharge while
            #   AutomaticStrategy permits discharge and the effective price
            #   threshold remains reached.
            autarky_cover_mode_active = bool(
                ai_mode == AI_MODE_SUMMER
            )

            previous_regulation_state = str(
                self._persist.get("regulation_active_state", "none") or "none"
            )

            last_output_w = max(
                0.0,
                float(self._persist.get("last_set_output_w", 0.0) or 0.0),
            )

            automatic_economic_hold_active = maintain_active_economic_discharge(
                automatic_mode_active=(ai_mode == AI_MODE_AUTOMATIC),
                strategy_active=bool(automatic_strategy_context.active),
                strategy_allows_discharge=bool(
                    automatic_strategy_context.metadata.get(
                        "automatic_discharge_allowed",
                        False,
                    )
                ),
                effective_price_reached=(
                    self._engine._is_effective_discharge_price_reached(ctx)
                ),
                previous_regulation_state=previous_regulation_state,
                active_output_w=last_output_w,
            )

            discharge_hold_mode_active = bool(
                autarky_cover_mode_active
                or automatic_economic_hold_active
            )

            original_discharge_reason = str(decision.reason or "")

            previous_economic_discharge_source_reason = str(
                self._persist.get(
                    "automatic_economic_discharge_source_reason",
                    "",
                )
                or ""
            )

            economic_discharge_source_reason = (
                economic_discharge_continuation_reason(
                    hold_active=automatic_economic_hold_active,
                    decision_action=str(decision.action or ""),
                    decision_reason=original_discharge_reason,
                    previous_source_reason=(
                        previous_economic_discharge_source_reason
                    ),
                )
            )

            previous_discharge_w = max(
                0.0,
                float(
                    self._persist.get(
                        "prev_discharge_w",
                        0.0,
                    )
                    or 0.0
                ),
            )

            active_discharge_output_w = max(
                previous_discharge_w,
                last_output_w,
            )

            stable_export_cycles = int(
                getattr(
                    grid_history_state,
                    "stable_export_cycles",
                    0,
                )
                or 0
            )

            discharge_exit_cycles = int(
                profile.get(
                    "DISCHARGE_EXIT_EXPORT_CYCLES",
                    8,
                )
                or 8
            )

            discharge_exit_export_w = max(
                80.0,
                float(
                    profile.get(
                        "EXPORT_GUARD_W",
                        80.0,
                    )
                    or 80.0
                ),
            )

            grid_export_now_w = max(
                0.0,
                float(grid_export or 0.0),
            )

            discharge_exit_confirmed = bool(
                grid_export_now_w >= discharge_exit_export_w
                and stable_export_cycles >= discharge_exit_cycles
            )

            if (
                discharge_hold_mode_active
                and ai_mode != AI_MODE_MANUAL
                and decision.action == "idle"
                and (
                    (
                        autarky_cover_mode_active
                        and original_discharge_reason
                        in {"idle", "state_idle", "standby"}
                    )
                    or (
                        automatic_economic_hold_active
                        and economic_discharge_source_reason is not None
                    )
                )
                and active_discharge_output_w > 0.0
                and float(soc) > float(soc_min)
                and not bool(discharge_blocked_by_soc_min)
                and not bool(cell_voltage_discharge_blocked)
                and not bool(cell_voltage_emergency_active)
                and float(additional_battery_charge_w or 0.0) <= 50.0
                and soc_limit != 2
                and not discharge_exit_confirmed
            ):
                hold_discharge_w = max(
                    self._engine._discharge_keepalive_w(ctx),
                    min(
                        active_discharge_output_w,
                        float(max_discharge),
                    ),
                )

                hold_reason = (
                    "summer_cover_deficit"
                    if autarky_cover_mode_active
                    else economic_discharge_source_reason
                )

                decision = DecisionResult(
                    action="discharge",
                    ac_mode="output",
                    charge_w=0.0,
                    discharge_w=hold_discharge_w,
                    reason=hold_reason,
                    target_soc=decision.target_soc,
                    current_peak_threshold=(
                        decision.current_peak_threshold
                    ),
                    current_valley_threshold=(
                        decision.current_valley_threshold
                    ),
                    economic_discharge_threshold=(
                        decision.economic_discharge_threshold
                    ),
                    effective_discharge_threshold=(
                        decision.effective_discharge_threshold
                    ),
                )

                if autarky_cover_mode_active:
                    self._persist["summer_discharge_latch_reason"] = (
                        f"hold_{original_discharge_reason}"
                    )
                    self._persist[
                        "automatic_discharge_latch_reason"
                    ] = "none"
                else:
                    self._persist["summer_discharge_latch_reason"] = "none"
                    self._persist[
                        "automatic_discharge_latch_reason"
                    ] = f"hold_{original_discharge_reason}"

            else:
                self._persist["summer_discharge_latch_reason"] = "none"
                self._persist["automatic_discharge_latch_reason"] = "none"

            if (
                ai_mode == AI_MODE_AUTOMATIC
                and economic_discharge_source_reason is not None
                and str(decision.action or "") == "discharge"
            ):
                self._persist[
                    "automatic_economic_discharge_source_reason"
                ] = economic_discharge_source_reason
            else:
                self._persist[
                    "automatic_economic_discharge_source_reason"
                ] = ""
            
            regulation_runtime = self._get_regulation_runtime_state()

            # V4.2 PV charge latch continuation:
            # In the improved regulation path, do not let a short idle cycle from
            # the strategic DecisionEngine immediately stop an already active PV
            # charge. This can happen in the morning transition when charging
            # consumes the visible export for one or more cycles.
            #
            # The technical regulation should continue PV charging and let the
            # PowerController reduce input smoothly until stable grid import
            # confirms that PV charge should really exit.
            pv_charge_exit_import_cycles = int(
                profile.get("PV_CHARGE_EXIT_IMPORT_CYCLES", 3) or 3
            )

            original_decision_reason = str(decision.reason or "")

            if (
                ai_mode != AI_MODE_MANUAL
                and str(regulation_runtime.active_regulation_state)
                == "pv_charge_active"
                and bool(pv_charge_latched)
                and decision.action == "idle"
                and original_decision_reason in (
                    "idle",
                    "state_idle",
                    "standby",
                )
                and int(grid_history_state.stable_import_cycles or 0)
                < pv_charge_exit_import_cycles
                and soc_limit != 1
                and not additional_battery_discharge_active
                and not bool(cell_voltage_emergency_active)
                and float(soc) < float(soc_max)
            ):
                decision = DecisionResult(
                    action="charge",
                    ac_mode="input",
                    charge_w=max(
                        0.0,
                        float(self._persist.get("last_set_input_w", 0.0) or 0.0),
                    ),
                    discharge_w=0.0,
                    reason="pv_surplus_charge",
                    target_soc=decision.target_soc,
                )

                self._persist["regulation_pv_charge_latch_continue_reason"] = (
                    original_decision_reason
                )
            else:
                self._persist["regulation_pv_charge_latch_continue_reason"] = "none"

            critical_data_reason = str(decision.reason or "") in {
                "sensor_invalid",
                "soc_invalid",
                "grid_sensor_invalid",
                "soc_limits_invalid",
                "power_limits_invalid",
                "cell_voltage_sensor_invalid",
            }

            if critical_data_reason:
                if bool(self._persist.get("charge_commit_active", False)):
                    self._clear_charge_commit(
                        str(decision.reason or "sensor_invalid")
                    )

                return await self._enter_safe_idle(
                    reason=str(decision.reason or "sensor_invalid"),
                    raw_values={
                        "soc": float(soc),
                        "pv_w": float(pv_w),
                        "pv_sensor_valid": bool(pv_sensor_valid),
                        "deficit": float(grid_import),
                        "surplus": float(grid_export),
                        "grid_sensor_configured": bool(
                            grid_sensor_configured
                        ),
                        "grid_sensor_valid": bool(grid_sensor_valid),
                        "soc_limits_valid": bool(soc_limits_valid),
                        "power_limits_valid": bool(power_limits_valid),
                    },
                )
                
            # The strategic AC charge binding runs before power tracking and
            # StrategyIntent creation so the unified regulation sees it.
            decision = self._apply_charge_commit(
                now=now,
                decision=decision,
                learned_charge_plan=learned_charge_plan,
                soc=float(soc),
                soc_max=float(soc_max),
                max_charge_w=float(max_charge),
                ai_mode=str(ai_mode),
                manual_action=str(manual_action),
                additional_battery_discharge_w=float(
                    additional_battery_discharge_w or 0.0
                ),
                offgrid_load_active=bool(offgrid_load_active),
                cell_voltage_emergency_active=bool(
                    cell_voltage_emergency_active
                ),
                price_now=price_now,
                effective_discharge_threshold=(
                    decision.effective_discharge_threshold
                ),
                automatic_peak_reserve_allowed=bool(
                    automatic_strategy_context.metadata.get(
                        "automatic_peak_reserve_allowed",
                        False,
                    )
                ),
                battery_charge_w=float(battery_charge_w or 0.0),
            )

            # V4.3.0-dev5.6.3:
            # Charge source classification, economic accounting and diagnostics
            # must use the final decision after protection, technical holds and
            # strategic AC charge binding have been applied.            
            charge_price_applied = None
            charge_source = "no_charge_delta"
            charge_price_bootstrap_active = False
            is_grid_charge = False
            charge_grid_part_w = 0.0
            charge_pv_part_w = 0.0

            # V4.3.0-dev2.1:
            # Use the original AC charge reason for price/source attribution while an
            # AC-Ladebindung is active. The strategy reason itself remains
            # charge_commit_active, but the price logic needs e.g. valley_opportunity_charge.
            charge_pricing_reason = self._charge_pricing_reason(decision.reason)

            stored_commit_price = _to_float(
                self._persist.get("charge_commit_price_per_kwh"),
                None,
            )
            pricing_price_now = (
                float(price_now)
                if price_now is not None
                else stored_commit_price
            )

            current_charge_pricing = classify_charge_pricing(
                grid_import_w=float(grid_import or 0.0),
                grid_export_w=float(grid_export or 0.0),
                decision_charge_w=float(decision.charge_w or 0.0),
                decision_ac_mode=str(decision.ac_mode),
                price_now=pricing_price_now,
                feed_in_tariff=float(feed_in_tariff),
                battery_charge_w=float(battery_charge_w),
                decision_reason=charge_pricing_reason,
                native_pv_w=float(native_pv_w),
                native_pv_valid=bool(
                    native_pv_configured and native_pv_sensor_valid
                ),
            )

            # V4.6.0 economics energy accounting uses measured battery/grid
            # power and the already centralized charge-source attribution.
            # Each physical direction is represented once: total grid export
            # remains an export flow, while its battery-attributable subset is
            # tracked separately for later benefit calculations.
            battery_to_grid_w = min(
                float(battery_discharge_w), float(grid_export)
            )
            battery_to_home_w = max(
                0.0, float(battery_discharge_w) - battery_to_grid_w
            )
            economics_energy_result = self._energy_accumulator.add_sample(
                sampled_at=now,
                power=EconomicPowerFlows(
                    grid_to_battery_w=float(
                        current_charge_pricing.grid_part_w
                        if current_charge_pricing.active
                        else 0.0
                    ),
                    pv_to_battery_w=float(
                        current_charge_pricing.pv_part_w
                        if current_charge_pricing.active
                        else 0.0
                    ),
                    grid_export_w=float(grid_export),
                    battery_to_home_w=battery_to_home_w,
                    battery_to_grid_w=battery_to_grid_w,
                ),
            )
            economics_energy_snapshot = self._energy_accumulator.snapshot()
            self._persist[
                "economics_energy_state"
            ] = self._energy_accumulator.to_state()
            economics_day = economics_energy_snapshot.day.isoformat()
            if self._persist.get("economics_money_day") != economics_day:
                self._economics_engine.reset_daily()
            priceable_total = priceable_energy_flows(
                economics_energy_result.energy,
                import_price=import_market_price,
                export_price=export_market_price,
            )
            priceable_daily = priceable_energy_flows(
                economics_energy_result.daily_energy,
                import_price=import_market_price,
                export_price=export_market_price,
            )
            self._economics_engine.record_grid_flows(
                flows=priceable_total.flows,
                daily_flows=priceable_daily.flows,
                import_price=import_market_price,
                export_price=export_market_price,
            )
            self._economics_engine.record_battery_value_flows(
                flows=priceable_total.flows,
                daily_flows=priceable_daily.flows,
                import_price=import_market_price,
                export_price=export_market_price,
            )
            economics_daily_snapshot = self._economics_engine.daily_snapshot()
            economics_total_snapshot = self._economics_engine.total_snapshot()
            self._persist["economics_money_day"] = economics_day
            self._persist[
                "economics_money_state"
            ] = self._economics_engine.to_state()
            economics_runtime_values = {
                **{
                    f"economics_daily_{key}": value
                    for key, value in economics_daily_snapshot.as_dict().items()
                    if key != "currency"
                },
                **{
                    f"economics_total_{key}": value
                    for key, value in economics_total_snapshot.as_dict().items()
                    if key != "currency"
                },
                **{
                    f"economics_daily_{key}": value
                    for key, value in economics_energy_snapshot.daily.as_dict().items()
                },
                **{
                    f"economics_total_{key}": value
                    for key, value in economics_energy_snapshot.total.as_dict().items()
                },
                "economics_average_grid_charge_price": (
                    economics_total_snapshot.average_grid_charge_price
                ),
                "economics_average_pv_opportunity_value": (
                    economics_total_snapshot.average_pv_opportunity_value
                ),
                "economics_average_export_price": (
                    economics_total_snapshot.average_export_price
                ),
                "economics_average_battery_discharge_value": (
                    economics_total_snapshot.average_battery_discharge_value
                ),
                "economics_total_economic_efficiency_pct": (
                    self._economics_engine.total_economic_efficiency_pct()
                ),
            }

            sample_duration_seconds = float(UPDATE_INTERVAL)
            try:
                previous_update = dt_util.parse_datetime(
                    str(self._persist.get("last_ts") or "")
                )
                if previous_update is not None:
                    sample_duration_seconds = max(
                        1.0,
                        (now - dt_util.as_utc(previous_update)).total_seconds(),
                    )
            except Exception:
                sample_duration_seconds = float(UPDATE_INTERVAL)

            pending_charge_evidence = recent_charge_evidence(
                self._persist.get("pending_charge_price_evidence"),
                now=now,
            )

            if current_charge_pricing.active:
                pending_charge_evidence = add_charge_evidence(
                    pending_charge_evidence,
                    pricing=current_charge_pricing,
                    duration_seconds=sample_duration_seconds,
                    now=now,
                )

            if delta_kwh > 0:
                is_below_soc_min_cycle = bool(
                    self._persist.get("trade_cycle_below_soc_min", False)
                )
                delta_charge_pricing = pricing_from_charge_evidence(
                    pending_charge_evidence,
                    now=now,
                )
                if delta_charge_pricing is None:
                    delta_charge_pricing = current_charge_pricing

                if delta_charge_pricing.active:
                    is_grid_charge = bool(
                        delta_charge_pricing.is_grid_charge
                    )
                    charge_price_applied = float(
                        delta_charge_pricing.price_per_kwh
                    )
                    charge_source = str(delta_charge_pricing.source)
                    charge_grid_part_w = float(
                        delta_charge_pricing.grid_part_w
                    )
                    charge_pv_part_w = float(
                        delta_charge_pricing.pv_part_w
                    )

                    if not is_below_soc_min_cycle:
                        charged_kwh = float(
                            self._persist.get("trade_charged_kwh", 0.0)
                            or 0.0
                        )
                        avg_price = self._persist.get(
                            "trade_avg_charge_price"
                        )
                        applied_price = float(
                            delta_charge_pricing.price_per_kwh
                        )
                        new_total_kwh = charged_kwh + float(delta_kwh)

                        if new_total_kwh > 0:
                            if avg_price is None:
                                new_avg = applied_price
                            else:
                                new_avg = (
                                    float(avg_price) * charged_kwh
                                    + applied_price * float(delta_kwh)
                                ) / new_total_kwh
                        else:
                            new_avg = 0.0

                        self._persist["trade_charged_kwh"] = new_total_kwh
                        self._persist["trade_avg_charge_price"] = new_avg

                # The pending samples describe the energy represented by this
                # SoC increase. Begin a fresh evidence window afterwards.
                pending_charge_evidence = None

            elif delta_kwh < 0:
                # Never carry charge evidence across a discharge interval.
                pending_charge_evidence = None

            elif current_charge_pricing.active:
                # Show the opportunity/grid price immediately, while the
                # economic energy ledger still waits for a real SoC increase.
                is_grid_charge = bool(current_charge_pricing.is_grid_charge)
                charge_price_applied = float(
                    current_charge_pricing.price_per_kwh
                )
                charge_source = str(current_charge_pricing.source)
                charge_grid_part_w = float(current_charge_pricing.grid_part_w)
                charge_pv_part_w = float(current_charge_pricing.pv_part_w)

            self._persist[
                "pending_charge_price_evidence"
            ] = pending_charge_evidence
                    
            # V4.3.0-dev5.2.1:
            # Bootstrap the economic charge-price basis during a confirmed
            # strategic grid charge even when the SoC sensor has not yet
            # produced a positive delta_kwh.
            #
            # The real energy ledger is still updated only by delta_kwh > 0.
            # This fallback only prevents the average charge price from staying
            # at a zero price throughout a real AC charge because of coarse or
            # delayed SoC updates.
            current_trade_avg_price = _to_float(
                self._persist.get("trade_avg_charge_price"),
                None,
            )
            current_trade_charged_kwh = max(
                0.0,
                float(
                    self._persist.get(
                        "trade_charged_kwh",
                        0.0,
                    )
                    or 0.0
                ),
            )

            confirmed_grid_charge_reasons = (
                CHARGE_COMMIT_PLANNING_REASONS
                | CHARGE_COMMIT_LEARNED_REASONS
                | CHARGE_COMMIT_PRICE_REASONS
                | CHARGE_COMMIT_RESERVE_REASONS
            )

            bootstrap_pricing_reason = self._charge_pricing_reason(
                decision.reason
            )

            confirmed_strategic_grid_charge = bool(
                str(decision.ac_mode) == "input"
                and float(decision.charge_w or 0.0) > 0.0
                and str(bootstrap_pricing_reason)
                in confirmed_grid_charge_reasons
                and float(grid_import or 0.0) > 60.0
                and charge_price_applied is not None
            )

            if (
                confirmed_strategic_grid_charge
                and current_trade_charged_kwh <= 0.0
                and (
                    current_trade_avg_price is None
                    or current_trade_avg_price <= 0.0001
                )
            ):
                self._persist["trade_avg_charge_price"] = float(
                    charge_price_applied
                )

                charge_price_bootstrap_active = True                

            if (
                delta_kwh < 0
                and price_now is not None
                and decision.ac_mode == "output"
                and float(decision.discharge_w or 0.0) > 0.0
                and decision.reason
                not in {
                    "pv_house_load_passthrough",
                    "offgrid_load_support",
                }
            ):
                sold_kwh = abs(float(delta_kwh))
                avg_price = self._persist.get("trade_avg_charge_price")

                tracked_kwh = max(
                    0.0,
                    float(self._persist.get("trade_charged_kwh", 0.0) or 0.0),
                )

                # V4.2.5:
                # trade_charged_kwh is only the internally priced charge ledger,
                # not the physical battery energy. It can be depleted while the
                # battery still contains energy, e.g. after restarts, updates,
                # SoC jumps or incomplete historic charge tracking.
                #
                # Therefore only book profit for the part of the discharge that
                # is still covered by priced charge energy, but do not reset the
                # average charge price here.
                accounted_sold_kwh = min(float(sold_kwh), float(tracked_kwh))

                if avg_price is not None and accounted_sold_kwh > 0:
                    profit = (
                        float(price_now) - float(avg_price)
                    ) * float(accounted_sold_kwh)

                    self._persist["profit"] = (
                        float(self._persist.get("profit", 0.0))
                        + float(profit)
                    )

                remaining_kwh = max(
                    0.0,
                    float(tracked_kwh) - float(accounted_sold_kwh),
                )

                self._persist["trade_charged_kwh"] = remaining_kwh

                # Important:
                # Do not set trade_avg_charge_price to 0 here.
                # The real reset is handled above when SoC reaches SoC-Min.

            adaptive_peak_active = decision.reason == "adaptive_peak_discharge"
            
            # V4.3.1-dev9:
            # Calculate the PV/grid split for an active strategic AC charge binding.
            # The binding target is the TOTAL battery charge target. Usable PV
            # therefore reduces only the AC/grid share instead of being added on
            # top of the full binding target.
            charge_source_allocation = self._charge_source_allocator.allocate(
                charge_commit_active=bool(
                    self._persist.get("charge_commit_active", False)
                ),
                allow_pv_blend=bool(
                    self._persist.get("charge_commit_allow_pv_blend", True)
                ),
                total_target_w=float(
                    self._persist.get(
                        "charge_commit_requested_power_w",
                        decision.charge_w or 0.0,
                    )
                    or 0.0
                ),
                pv_w=float(pv_w or 0.0),
                house_load_w=float(house_load or 0.0),
                max_grid_input_w=float(max_charge),
                native_pv_w=float(native_pv_w),
                native_pv_valid=bool(
                    native_pv_configured and native_pv_sensor_valid
                ),
            )

            if (
                charge_source_allocation.active
                and bool(
                    self._persist.get(
                        "charge_commit_allow_pv_blend",
                        True,
                    )
                )
                and str(decision.action or "") == "charge"
                and str(decision.ac_mode or "") == "input"
                and (
                    str(decision.reason or "") == "charge_commit_active"
                    or str(decision.reason or "")
                    in CHARGE_COMMIT_SOURCE_REASONS
                )
            ):
                # Keep the binding active even when PV covers the complete
                # target. The SF AC input expects TOTAL charging power; using
                # only grid_requested_w here would turn a PV-covered target
                # into INPUT 0 W and export the available surplus.
                decision.charge_w = max(
                    0.0,
                    float(
                        charge_source_allocation.device_input_w
                        or 0.0
                    ),
                )
                
            # Store final effective previous power only after all protection and limit
            # blockers have modified the decision. Otherwise a blocked discharge can leave
            # a stale prev_discharge_w > 0 and suppress PV charging in the next cycle.
            if decision.reason == "pv_house_load_passthrough":
                self._persist["prev_discharge_w"] = 0.0
            else:
                self._persist["prev_discharge_w"] = float(decision.discharge_w or 0.0)

            if decision.ac_mode == "input" and float(decision.charge_w or 0.0) > 0.0:
                self._persist["prev_charge_w"] = float(decision.charge_w)
            else:
                self._persist["prev_charge_w"] = 0.0

            self._remember_learned_charge_power_sample(
                now,
                decision=decision,
                battery_charge_w=float(battery_charge_w),
                max_charge_w=float(max_charge),
            )
            
            strategy_intent = decision_to_strategy_intent(
                decision,
                pv_handover_policy=pv_handover_policy,
                load_coverage_priority=load_coverage_priority,
            )
            
            strategy_intent.metadata.update(
                {
                    # The technical layer must not keep a stale PV INPUT hold
                    # after the source-aware strategic latch has released.
                    "pv_charge_latched": bool(pv_charge_latched),
                    "pv_charge_stop_counter": int(pv_charge_stop_counter),
                    # V4.3.0-dev7:
                    # Keep the full strategic candidate selection internally
                    # visible even when a later safety, charge-binding or
                    # technical handover adjusts the selected DecisionResult.
                    "strategy_candidate_count": int(
                        strategy_selection.get(
                            "candidate_count",
                            0,
                        )
                    ),
                    "strategy_eligible_candidate_count": int(
                        strategy_selection.get(
                            "eligible_candidate_count",
                            0,
                        )
                    ),
                    "strategy_selected_rule": str(
                        strategy_selection.get(
                            "selected_rule",
                            "unknown",
                        )
                    ),
                    "strategy_selected_reason": str(
                        strategy_selection.get(
                            "selected_reason",
                            "idle",
                        )
                    ),
                    "strategy_selected_state": str(
                        strategy_selection.get(
                            "selected_state",
                            "idle_ready",
                        )
                    ),
                    "strategy_selected_priority": int(
                        strategy_selection.get(
                            "selected_priority",
                            0,
                        )
                    ),
                    "strategy_selection_override_reason": (
                        "none"
                        if str(
                            strategy_selection.get(
                                "selected_reason",
                                "idle",
                            )
                        )
                        == str(decision.reason or "idle")
                        else str(decision.reason or "idle")
                    ),
                    "strategy_candidates": list(
                        strategy_selection.get(
                            "candidates",
                            [],
                        )
                    ),
                    "pv_handover_policy": str(
                        strategy_intent.pv_handover_policy
                    ),
                    "load_coverage_priority": bool(
                        strategy_intent.load_coverage_priority
                    ),
                    "charge_source_allocation_active": bool(
                        charge_source_allocation.active
                    ),
                    "charge_total_target_w": float(
                        charge_source_allocation.total_target_w
                    ),
                    "charge_pv_available_w": float(
                        charge_source_allocation.pv_available_w
                    ),
                    "charge_pv_allocated_w": float(
                        charge_source_allocation.pv_allocated_w
                    ),
                    "charge_native_pv_available_w": float(
                        charge_source_allocation.native_pv_available_w
                    ),
                    "charge_native_pv_allocated_w": float(
                        charge_source_allocation.native_pv_allocated_w
                    ),
                    "charge_grid_requested_w": float(
                        charge_source_allocation.grid_requested_w
                    ),
                    "charge_device_input_w": float(
                        charge_source_allocation.device_input_w
                    ),
                    "charge_unfilled_w": float(
                        charge_source_allocation.unfilled_w
                    ),
                    "charge_pv_share_pct": float(
                        charge_source_allocation.pv_share_pct
                    ),
                    "charge_grid_share_pct": float(
                        charge_source_allocation.grid_share_pct
                    ),
                    "charge_source_allocation_reason": str(
                        charge_source_allocation.reason
                    ),
                    "automatic_strategy_active": bool(
                        automatic_strategy_context.active
                    ),
                    "automatic_weighting": str(
                        automatic_strategy_context.weighting
                    ),
                    "automatic_season_context": str(
                        automatic_strategy_context.season_context
                    ),
                    "automatic_pv_weight": float(
                        automatic_strategy_context.pv_weight
                    ),
                    "automatic_price_weight": float(
                        automatic_strategy_context.price_weight
                    ),
                    "automatic_reserve_weight": float(
                        automatic_strategy_context.reserve_weight
                    ),
                    "automatic_forecast_weight": float(
                        automatic_strategy_context.forecast_weight
                    ),
                    "automatic_strategy_reason": str(
                        automatic_strategy_context.reason
                    ),
                    "automatic_discharge_allowed": bool(
                        automatic_strategy_context.metadata.get(
                            "automatic_discharge_allowed",
                            False,
                        )
                    ),
                    "automatic_discharge_reason": str(
                        automatic_strategy_context.metadata.get(
                            "automatic_discharge_reason",
                            "not_evaluated",
                        )
                    ),
                    "automatic_peak_reserve_allowed": bool(
                        automatic_strategy_context.metadata.get(
                            "automatic_peak_reserve_allowed",
                            False,
                        )
                    ),
                    "automatic_peak_reserve_reason": str(
                        automatic_strategy_context.metadata.get(
                            "automatic_peak_reserve_reason",
                            "not_evaluated",
                        )
                    ),
                    "automatic_valley_charge_allowed": bool(
                        automatic_strategy_context.metadata.get(
                            "automatic_valley_charge_allowed",
                            False,
                        )
                    ),
                    "automatic_valley_charge_reason": str(
                        automatic_strategy_context.metadata.get(
                            "automatic_valley_charge_reason",
                            "not_evaluated",
                        )
                    ),
                    "automatic_planning_allowed": bool(
                        automatic_strategy_context.metadata.get(
                            "automatic_planning_allowed",
                            False,
                        )
                    ),
                    "automatic_planning_reason": str(
                        automatic_strategy_context.metadata.get(
                            "automatic_planning_reason",
                            "not_evaluated",
                        )
                    ),                    
                    "automatic_pv_weight_reason": str(
                        automatic_strategy_context.metadata.get(
                            "pv_weight_reason",
                            "unknown",
                        )
                    ),
                    "automatic_price_weight_reason": str(
                        automatic_strategy_context.metadata.get(
                            "price_weight_reason",
                            "unknown",
                        )
                    ),
                    "automatic_reserve_weight_reason": str(
                        automatic_strategy_context.metadata.get(
                            "reserve_weight_reason",
                            "unknown",
                        )
                    ),
                    "automatic_forecast_weight_reason": str(
                        automatic_strategy_context.metadata.get(
                            "forecast_weight_reason",
                            "unknown",
                        )
                    ),
                }
            )

            # V4.3.0-dev3.1:
            # Provide economic grid-target data to the technical PowerController.
            #
            # The PowerController does not decide whether charging or discharging
            # should start. It only uses these values to shift the small technical
            # target range toward slight export when that is economically preferable.
            feed_in_tariff_configured = bool(export_market_price.valid)

            battery_value_per_kwh = _to_float(
                self._persist.get("trade_avg_charge_price"),
                None,
            )

            # Compatibility fallback for older persisted installations.
            if battery_value_per_kwh is None:
                battery_value_per_kwh = _to_float(
                    self._persist.get("avg_charge_price"),
                    None,
                )

            strategy_intent.metadata.update(
                {
                    "feed_in_tariff_configured": bool(
                        feed_in_tariff_configured
                    ),
                    "feed_in_tariff_per_kwh": float(
                        feed_in_tariff or 0.0
                    ),
                    "battery_value_per_kwh": battery_value_per_kwh,
                }
            )

            strategy_meta = dict(strategy_intent.metadata or {})

            strategy_state = str(strategy_meta.get("strategy_state", "idle_ready"))
            visible_state = str(strategy_meta.get("visible_state", "ready"))
            strategic_reason = str(
                strategy_meta.get("strategic_reason", decision.reason or "idle")
            )
            technical_reason = str(strategy_meta.get("technical_reason", "none"))
            strategy_priority = int(strategy_meta.get("strategy_priority", strategy_intent.priority))
            source_reason = str(strategy_meta.get("source_reason", decision.reason or "idle"))
            source_action = str(strategy_meta.get("source_action", decision.action or "idle"))
            source_ac_mode = str(strategy_meta.get("source_ac_mode", decision.ac_mode or "output"))
            strategy_candidate_count = int(
                strategy_meta.get(
                    "strategy_candidate_count",
                    0,
                )
            )
            strategy_eligible_candidate_count = int(
                strategy_meta.get(
                    "strategy_eligible_candidate_count",
                    0,
                )
            )
            strategy_selected_rule = str(
                strategy_meta.get(
                    "strategy_selected_rule",
                    "unknown",
                )
            )
            strategy_selected_reason = str(
                strategy_meta.get(
                    "strategy_selected_reason",
                    "idle",
                )
            )
            strategy_selected_state = str(
                strategy_meta.get(
                    "strategy_selected_state",
                    "idle_ready",
                )
            )
            strategy_selected_priority = int(
                strategy_meta.get(
                    "strategy_selected_priority",
                    0,
                )
            )
            strategy_selection_override_reason = str(
                strategy_meta.get(
                    "strategy_selection_override_reason",
                    "none",
                )
            )
            strategy_candidates = list(
                strategy_meta.get(
                    "strategy_candidates",
                    [],
                )
            )
            
            charge_commit_active = bool(self._persist.get("charge_commit_active", False))
            charge_commit_type = str(self._persist.get("charge_commit_type", "none") or "none")
            charge_commit_reason = str(self._persist.get("charge_commit_reason", "") or "")
            charge_commit_source_reason = str(
                self._persist.get("charge_commit_source_reason", "") or ""
            )
            charge_commit_target_soc = self._persist.get("charge_commit_target_soc")
            charge_commit_started_at = self._persist.get("charge_commit_started_at")
            charge_commit_valid_until = self._persist.get("charge_commit_valid_until")
            charge_commit_abort_reason = str(
                self._persist.get("charge_commit_abort_reason", "none") or "none"
            )
            charge_commit_requested_power_w = float(
                self._persist.get("charge_commit_requested_power_w", 0.0) or 0.0
            )
            charge_commit_allow_pv_blend = bool(
                self._persist.get("charge_commit_allow_pv_blend", True)
            )

            # Hard discharge permission for the unified regulation chain.
            # The DecisionEngine decision is already sanitized above, but the
            # ModeArbiter may still have an active discharge/passthrough latch
            # from a previous cycle. This explicit flag prevents such technical
            # holds from producing a short output pulse at SoC minimum or during
            # cell-voltage discharge protection.
            discharge_allowed_for_regulation = not bool(
                discharge_blocked_by_soc_min
                or cell_voltage_discharge_blocked
                or soc_limit == 2
            )

            mode_arbiter_result = self._mode_arbiter.evaluate(
                now=now,
                intent=strategy_intent,
                grid=grid_history_state,
                runtime=regulation_runtime,
                current_ac_mode=self._state(self.entities.ac_mode),
                additional_battery_discharge_w=float(additional_battery_discharge_w or 0.0),
                discharge_allowed=bool(discharge_allowed_for_regulation),
                offgrid_power_w=float(offgrid_power_w),
                offgrid_mode=str(offgrid_mode),
                offgrid_load_active=bool(offgrid_load_active),
                offgrid_source_active=bool(offgrid_source_active),
            )
            
            regulation_power_result = self._regulation_power_controller.calculate(
                intent=strategy_intent,
                arbiter=mode_arbiter_result,
                grid=grid_history_state,
                previous_input_w=float(self._persist.get("last_set_input_w", 0.0) or 0.0),
                previous_output_w=float(self._persist.get("last_set_output_w", 0.0) or 0.0),
                max_input_w=float(max_charge),
                max_output_w=float(max_discharge),
            )
            
            regulation_device_command = self._device_command_builder.build(
                intent=strategy_intent,
                arbiter=mode_arbiter_result,
                power=regulation_power_result,
                current_ac_mode=self._state(self.entities.ac_mode),
                last_input_limit_w=float(self._persist.get("last_set_input_w", 0.0) or 0.0),
                last_output_limit_w=float(self._persist.get("last_set_output_w", 0.0) or 0.0),
                current_input_limit_w=_to_float(
                    self._state(self.entities.input_limit),
                    None,
                ),
                current_output_limit_w=_to_float(
                    self._state(self.entities.output_limit),
                    None,
                ),
                max_input_w=float(max_charge),
                max_output_w=float(max_discharge),
            )

            technical_reason = (
                str(strategic_reason)
                if strategy_state == "idle_safe"
                else str(
                    regulation_device_command.reason
                    or mode_arbiter_result.reason
                    or regulation_power_result.reason
                    or "none"
                )
            )
            strategy_intent.metadata["technical_reason"] = technical_reason

            ac_mode = (
                ZENDURE_MODE_INPUT
                if regulation_device_command.ac_mode == "input"
                else ZENDURE_MODE_OUTPUT
            )
            in_w = (
                float(regulation_device_command.input_limit_w)
                if ac_mode == ZENDURE_MODE_INPUT
                else 0.0
            )
            out_w = (
                float(regulation_device_command.output_limit_w)
                if ac_mode == ZENDURE_MODE_OUTPUT
                else 0.0
            )

            current_ac_mode = str(
                self._state(self.entities.ac_mode) or ""
            )

            active_command_write_pending = bool(
                (
                    ac_mode == ZENDURE_MODE_INPUT
                    and regulation_device_command.should_write_input
                )
                or (
                    ac_mode == ZENDURE_MODE_OUTPUT
                    and regulation_device_command.should_write_output
                )
            )

            command_effectiveness_result = evaluate_command_effectiveness(
                now=dt_util.as_utc(now),
                requested_mode=str(ac_mode),
                input_target_w=float(in_w),
                output_target_w=float(out_w),
                battery_charge_w=float(battery_charge_w),
                battery_discharge_w=float(battery_discharge_w),
                battery_sensor_valid=bool(
                    battery_ac_power_sensor_valid
                ),
                grid_import_w=float(grid_import or 0.0),
                current_ac_mode=current_ac_mode,
                active_command_write_pending=bool(
                    active_command_write_pending
                ),
                previous=self._get_command_effectiveness_state(),
                config=self._command_effectiveness_config,
            )
            self._store_command_effectiveness_result(
                command_effectiveness_result
            )

            effectiveness_retry_direction = (
                command_effectiveness_result.retry_direction
            )

            if effectiveness_retry_direction == "input":
                regulation_device_command.should_write_input = True
                regulation_device_command.skipped = False
                regulation_device_command.skip_reason = "none"
            elif effectiveness_retry_direction == "output":
                regulation_device_command.should_write_output = True
                regulation_device_command.skipped = False
                regulation_device_command.skip_reason = "none"

            regulation_device_command.metadata[
                "effectiveness_retry_direction"
            ] = effectiveness_retry_direction
                
            self._update_regulation_runtime_state(
                now=now,
                requested_mode=str(mode_arbiter_result.requested_mode),
                resolved_mode=str(mode_arbiter_result.resolved_mode),
                active_state=str(mode_arbiter_result.active_regulation_state),
                command_skipped=bool(regulation_device_command.skipped),
                command_skip_reason=str(regulation_device_command.skip_reason),
                current_ac_mode=self._state(self.entities.ac_mode),
                command_ac_mode=str(ac_mode),
                profile=profile,
                grid=grid_history_state,
            )

            is_passthrough = decision.reason in {
                "pv_house_load_passthrough",
                "offgrid_load_support",
            }
            
            manual_standby_no_command = bool(
                ai_mode == AI_MODE_MANUAL
                and str(manual_action) == MANUAL_STANDBY
            )

            if manual_standby_no_command:
                # Stop BSFAI's active side exactly once when manual standby is
                # entered. Later standby cycles stay passive, so external
                # controls are not overwritten. The persisted latch also makes
                # an update/restart in an already active standby safe.
                if not bool(self._persist.get("manual_standby_stop_applied")):
                    standby_direction = active_power_direction(
                        current_ac_mode=self._state(self.entities.ac_mode),
                        last_ac_mode=self._persist.get("last_set_mode"),
                        current_input_limit_w=_to_float(
                            self._state(self.entities.input_limit), 0.0
                        ),
                        current_output_limit_w=_to_float(
                            self._state(self.entities.output_limit), 0.0
                        ),
                        last_input_limit_w=_to_float(
                            self._persist.get("last_set_input_w"), 0.0
                        ),
                        last_output_limit_w=_to_float(
                            self._persist.get("last_set_output_w"), 0.0
                        ),
                        measured_charge_w=battery_charge_w,
                        measured_discharge_w=battery_discharge_w,
                    )

                    standby_command = DeviceCommand(
                        ac_mode=ZENDURE_MODE_OUTPUT,
                        input_limit_w=0.0,
                        output_limit_w=0.0,
                        reason="manual_standby",
                        should_write_mode=standby_direction == "input",
                        should_write_input=standby_direction == "input",
                        should_write_output=standby_direction == "output",
                        skipped=standby_direction is None,
                        skip_reason=(
                            "none"
                            if standby_direction is not None
                            else "unchanged"
                        ),
                        metadata={"command_path": "manual_standby"},
                    )
                    await self._execute_device_command(
                        standby_command,
                        force_power=True,
                        # Preserve the established INPUT-stop then OUTPUT-mode
                        # sequence used when entering passive manual standby.
                        power_before_mode=standby_direction == "input",
                    )

                    self._persist["last_set_input_w"] = 0
                    self._persist["last_set_output_w"] = 0
                    self._persist["last_set_mode"] = ZENDURE_MODE_OUTPUT
                    self._persist["manual_standby_stop_applied"] = True

                    self._persist["regulation_skipped_write_reason"] = (
                        f"manual_standby_stopped_active_{standby_direction}"
                        if standby_direction
                        else "manual_standby_no_active_power"
                    )
                else:
                    self._persist["regulation_skipped_write_reason"] = (
                        "manual_standby_no_command"
                    )

            else:
                self._persist["manual_standby_stop_applied"] = False
                # DeviceCommandBuilder already applied the write tolerance.
                # Force the selected active-side command so a direction change
                # cannot be skipped merely because the Number entity still
                # displays the same watt value as an earlier cycle.
                execution_result = await self._execute_device_command(
                    regulation_device_command,
                    force_power=True,
                )

                if (
                    effectiveness_retry_direction == "input"
                    and execution_result.input_written
                ):
                    self._record_command_effectiveness_retry(
                        now=now,
                        direction="input",
                    )
                elif (
                    effectiveness_retry_direction == "output"
                    and execution_result.output_written
                ):
                    self._record_command_effectiveness_retry(
                        now=now,
                        direction="output",
                    )

            is_charging = ac_mode == ZENDURE_MODE_INPUT and in_w > 0.0

            discharge_command_active = (
                ac_mode == ZENDURE_MODE_OUTPUT
                and out_w > 0.0
                and not is_passthrough
            )

            real_discharge_threshold_w = 30.0

            real_discharge_active = (
                float(battery_discharge_w or 0.0) > real_discharge_threshold_w
            )

            no_relevant_grid_import = float(grid_import or 0.0) <= max(
                60.0,
                float(profile.get("TARGET_IMPORT_W", 10.0) or 10.0)
                + float(
                    profile.get(
                        "DISCHARGE_DEADBAND_W",
                        30.0,
                    )
                    or 30.0
                ),
            )

            pv_covers_load = (
                float(grid_export or 0.0) > 0.0
                or float(pv_w or 0.0) >= max(
                    120.0,
                    float(house_load or 0.0) * 0.80,
                )
            )

            discharge_waiting_for_import = (
                discharge_command_active
                and decision.action == "discharge"
                and not real_discharge_active
                and no_relevant_grid_import
                and pv_covers_load
            )

            is_discharging = (
                discharge_command_active
                and real_discharge_active
            )

            if is_passthrough and out_w > 0.0:
                self._persist["power_state"] = "passthrough"
            elif is_charging:
                self._persist["power_state"] = "charging"
            elif discharge_waiting_for_import:
                self._persist["power_state"] = "discharge_waiting_for_import"
            elif is_discharging:
                self._persist["power_state"] = "discharging"
            else:
                self._persist["power_state"] = "idle"

            if (
                is_charging
                or is_discharging
                or discharge_waiting_for_import
                or (is_passthrough and out_w > 0.0)
            ):
                if not self._persist.get("next_action_time"):
                    self._persist["next_action_time"] = self._stable_iso_minute(now)
            else:
                self._persist["next_action_time"] = None
                
            # Dev9 display-only status hysteresis.
            # The command decision remains authoritative. A single neutral cycle
            # may keep the last active user-facing status for up to one minute,
            # but hard blockers and safe-idle reasons are shown immediately.
            display_decision = decision
            now_utc = dt_util.as_utc(now)
            display_hold_eligible = bool(
                ai_mode != AI_MODE_MANUAL
                and decision.action in {"charge", "discharge", "passthrough"}
                and str(decision.reason or "")
                not in {
                    "emergency_latched_charge",
                    "cell_voltage_emergency_charge",
                }
            )

            if display_hold_eligible:
                self._persist["active_status_display_hold_until"] = (
                    now_utc
                    + timedelta(seconds=ACTIVE_STATUS_DISPLAY_HOLD_S)
                ).isoformat()
                self._persist["active_status_display_action"] = str(
                    decision.action
                )
                self._persist["active_status_display_mode"] = str(
                    decision.ac_mode
                )
                self._persist["active_status_display_reason"] = str(
                    decision.reason
                )
                self._persist["active_status_display_hold_reason"] = "active"

            elif (
                decision.action == "idle"
                and str(decision.reason or "") in ("idle", "state_idle", "standby")
                and ai_mode != AI_MODE_MANUAL
                and engine_health
                in {
                    "pv_sensor_invalid",
                    "no_price_data",
                    "no_current_price",
                }
            ):
                hold_raw = self._persist.get(
                    "active_status_display_hold_until"
                )
                hold_active = False
                if hold_raw:
                    try:
                        hold_dt = dt_util.parse_datetime(str(hold_raw))
                        hold_active = bool(
                            hold_dt is not None and dt_util.as_utc(hold_dt) > now_utc
                        )
                    except Exception:
                        hold_active = False

                no_hard_blocker = (
                    bool(soc_limits_valid)
                    and bool(power_limits_valid)
                    and bool(grid_sensor_valid)
                    and not bool(cell_voltage_emergency_active)
                )

                held_reason = str(
                    self._persist.get(
                        "active_status_display_reason",
                        "",
                    )
                    or ""
                )
                held_action = str(
                    self._persist.get(
                        "active_status_display_action",
                        "",
                    )
                    or ""
                )
                held_mode = str(
                    self._persist.get(
                        "active_status_display_mode",
                        "",
                    )
                    or ""
                )

                if (
                    hold_active
                    and no_hard_blocker
                    and held_action in {"charge", "discharge", "passthrough"}
                    and held_mode in {"input", "output"}
                    and held_reason
                ):
                    display_decision = DecisionResult(
                        action=held_action,
                        ac_mode=held_mode,
                        charge_w=0.0,
                        discharge_w=0.0,
                        reason=held_reason,
                        target_soc=decision.target_soc,
                        current_peak_threshold=decision.current_peak_threshold,
                        current_valley_threshold=decision.current_valley_threshold,
                        economic_discharge_threshold=decision.economic_discharge_threshold,
                        effective_discharge_threshold=decision.effective_discharge_threshold,
                    )
                    self._persist[
                        "active_status_display_hold_reason"
                    ] = "display_hold"
                else:
                    self._persist[
                        "active_status_display_hold_reason"
                    ] = "none"

            else:
                self._persist["active_status_display_hold_until"] = None
                self._persist["active_status_display_hold_reason"] = "none"

            ai_status = self._map_ai_status(
                ai_mode=ai_mode,
                action=display_decision.action,
                reason=display_decision.reason,
            )

            recommendation = self._map_reco(display_decision.action)

            charge_strategy = self._map_charge_strategy(
                ai_mode=ai_mode,
                action=display_decision.action,
                reason=display_decision.reason,
            )

            transparency_ctx = RuntimeSnapshot(
                now=now,
                soc=soc,
                soc_min=float(soc_min),
                soc_max=float(soc_max),
                emergency_soc=float(emergency_soc),
                emergency_charge_w=float(emergency_w),
                max_charge_w=float(max_charge),
                max_discharge_w=float(max_discharge),
                grid_import_w=float(grid_import),
                grid_export_w=float(grid_export),
                pv_w=float(pv_w),
                house_load_w=float(house_load),
                battery_discharge_w=float(battery_discharge_w),
                last_output_w=float(
                    self._persist.get("last_set_output_w", 0.0)
                    or 0.0
                ),
                avg_charge_price=self._persist.get("trade_avg_charge_price"),
                expensive_threshold=float(expensive),
                very_expensive_threshold=float(very_expensive),
                profit_margin_pct=float(profit_margin_pct),
                import_market_price=import_market_price,
                export_market_price=export_market_price,
                ai_mode=ai_mode,
                manual_action=manual_action,
                season=season,
                profile=profile,
                prev_discharge_w=float(self._persist.get("prev_discharge_w", 0.0)),
                prev_charge_w=float(self._persist.get("prev_charge_w", 0.0)),
                battery_capacity_kwh=battery_capacity_kwh,
                peak_factor=peak_factor,
                valley_factor=valley_factor,
                very_cheap_price=very_cheap_price,
                additional_battery_charge_w=additional_battery_charge_w,
                additional_battery_discharge_w=additional_battery_discharge_w,
                pv_charge_start_export_w=float(pv_charge_start_export_w),
                cell_voltage_emergency_active=cell_voltage_emergency_active,
                forecast=forecast_summary,
                pv_charge_start_counter=int(pv_charge_start_counter),
                pv_charge_stop_counter=int(pv_charge_stop_counter),
                pv_charge_latched=bool(pv_charge_latched),
                forecast_wait_block_counter=int(self._persist.get("forecast_wait_block_counter", 0)),
                discharge_blocked_by_soc_min=bool(discharge_blocked_by_soc_min),
                cell_voltage_discharge_blocked=bool(cell_voltage_discharge_blocked),
                pv_houseload_passthrough_active=bool(pv_houseload_passthrough_active),
                pv_houseload_passthrough_target_w=float(pv_houseload_passthrough_target_w),
                pv_houseload_passthrough_stop_reason=str(pv_houseload_passthrough_stop_reason),
                learned_charge_plan=learned_charge_plan,
                learned_planning_enabled=bool(learned_planning_enabled),
                offgrid_power_w=float(offgrid_power_w),
                offgrid_mode=str(offgrid_mode),
                offgrid_available=bool(offgrid_available),
                offgrid_active=bool(offgrid_active),
                offgrid_load_active=bool(offgrid_load_active),
                offgrid_source_active=bool(offgrid_source_active),
                automatic_strategy_active=bool(
                    automatic_strategy_context.active
                ),
                automatic_weighting=str(
                    automatic_strategy_context.weighting
                ),
                automatic_pv_weight=float(
                    automatic_strategy_context.pv_weight
                ),
                automatic_price_weight=float(
                    automatic_strategy_context.price_weight
                ),
                automatic_reserve_weight=float(
                    automatic_strategy_context.reserve_weight
                ),
                automatic_forecast_weight=float(
                    automatic_strategy_context.forecast_weight
                ),
                automatic_discharge_allowed=bool(
                    automatic_strategy_context.metadata.get(
                        "automatic_discharge_allowed",
                        False,
                    )
                ),
                automatic_discharge_reason=str(
                    automatic_strategy_context.metadata.get(
                        "automatic_discharge_reason",
                        "not_evaluated",
                    )
                ),
                automatic_peak_reserve_allowed=bool(
                    automatic_strategy_context.metadata.get(
                        "automatic_peak_reserve_allowed",
                        False,
                    )
                ),
                automatic_peak_reserve_reason=str(
                    automatic_strategy_context.metadata.get(
                        "automatic_peak_reserve_reason",
                        "not_evaluated",
                    )
                ),
                automatic_valley_charge_allowed=bool(
                    automatic_strategy_context.metadata.get(
                        "automatic_valley_charge_allowed",
                        False,
                    )
                ),
                automatic_valley_charge_reason=str(
                    automatic_strategy_context.metadata.get(
                        "automatic_valley_charge_reason",
                        "not_evaluated",
                    )
                ),
                automatic_planning_allowed=bool(
                    automatic_strategy_context.metadata.get(
                        "automatic_planning_allowed",
                        False,
                    )
                ),
                automatic_planning_reason=str(
                    automatic_strategy_context.metadata.get(
                        "automatic_planning_reason",
                        "not_evaluated",
                    )
                ),
                grid_sensor_configured=bool(grid_sensor_configured),
                grid_sensor_valid=bool(grid_sensor_valid),
                pv_sensor_valid=bool(pv_sensor_valid),
                soc_limits_valid=bool(soc_limits_valid),
                power_limits_valid=bool(power_limits_valid),
            )

            transparency_result = self._engine._with_thresholds(
                transparency_ctx,
                DecisionResult(
                    action=display_decision.action,
                    ac_mode=display_decision.ac_mode,
                    charge_w=float(display_decision.charge_w or 0.0),
                    discharge_w=float(display_decision.discharge_w or 0.0),
                    reason=display_decision.reason,
                    target_soc=display_decision.target_soc,
                ),
            )

            current_peak_threshold = transparency_result.current_peak_threshold
            current_valley_threshold = transparency_result.current_valley_threshold
            economic_discharge_threshold = transparency_result.economic_discharge_threshold
            effective_discharge_threshold = transparency_result.effective_discharge_threshold

            self._persist["debug"] = "OK"
            self._persist["last_ts"] = now.isoformat()

            await self._save()

            details = {
                "soc": soc,
                "pv_w": pv_w,
                "pv_sensor_valid": bool(pv_sensor_valid),
                "native_pv_w": native_pv_w,
                "native_pv_configured": native_pv_configured,
                "native_pv_sensor_valid": native_pv_sensor_valid,
                "deficit": float(grid_import),
                "surplus": float(grid_export),
                "grid_sensor_configured": bool(grid_sensor_configured),
                "grid_sensor_valid": bool(grid_sensor_valid),
                "soc_limits_valid": bool(soc_limits_valid),
                "power_limits_valid": bool(power_limits_valid),
                "house_load": int(round(house_load, 0)),
                
                # V4.2.0 regulation / grid history diagnostics
                "regulation_grid_now_w": float(grid_history_state.grid_now_w),
                "regulation_grid_avg_short_w": float(grid_history_state.grid_avg_short_w),
                "regulation_grid_avg_medium_w": float(grid_history_state.grid_avg_medium_w),
                "regulation_grid_delta_w": float(grid_history_state.grid_delta_w),
                "regulation_stable_import_cycles": int(
                    grid_history_state.stable_import_cycles
                ),
                "regulation_stable_export_cycles": int(
                    grid_history_state.stable_export_cycles
                ),
                "regulation_near_target_cycles": int(
                    grid_history_state.near_target_cycles
                ),
                "regulation_fast_load_rise_detected": bool(
                    grid_history_state.fast_load_rise_detected
                ),
                "regulation_fast_load_drop_detected": bool(
                    grid_history_state.fast_load_drop_detected
                ),
                "regulation_post_load_drop_hold_active": bool(
                    grid_history_state.post_load_drop_hold_active
                ),
                "regulation_post_output_overshoot_hold_active": bool(
                    grid_history_state.post_output_overshoot_hold_active
                ),
                
                "price_now": price_now,
                "feed_in_tariff": float(feed_in_tariff),
                "feed_in_tariff_source": str(export_market_price.source),
                "feed_in_tariff_is_dynamic": bool(
                    export_market_price.is_dynamic
                ),
                "feed_in_tariff_is_fallback": bool(
                    export_market_price.is_fallback
                ),
                "feed_in_tariff_validity": str(
                    export_market_price.validity
                ),
                "pv_opportunity_price": float(feed_in_tariff),
                "avg_charge_price": self._persist.get("trade_avg_charge_price"),
                "economic_discharge_threshold": economic_discharge_threshold,
                "effective_discharge_threshold": effective_discharge_threshold,
                # Keep the existing entity runtime key stable so Home Assistant
                # does not create a replacement entity during the update. The
                # displayed monetary unit is supplied dynamically by sensor.py.
                "profit_eur": float(self._persist.get("profit") or 0.0),
                "delta_kwh": float(delta_kwh),
                "is_grid_charge": is_grid_charge,
                "charge_source": charge_source,
                "charge_price_applied": charge_price_applied,
                "charge_price_bootstrap_active": bool(
                    charge_price_bootstrap_active
                ),
                "charge_grid_part_w": float(charge_grid_part_w),
                "charge_pv_part_w": float(charge_pv_part_w),
                "charge_mixed_price_active": bool(
                    float(charge_grid_part_w or 0.0) > 0.0
                    and float(charge_pv_part_w or 0.0) > 0.0
                ),
                "economics_energy_sample_status": economics_energy_result.status,
                "economics_accounting_status": priceable_total.status,
                "economics_energy_elapsed_seconds": float(
                    economics_energy_result.elapsed_seconds
                ),
                "economics_energy_accounted_seconds": float(
                    economics_energy_result.accounted_seconds
                ),
                "economics_energy_day": economics_energy_snapshot.day.isoformat(),
                "economics_energy_daily": (
                    economics_energy_snapshot.daily.as_dict()
                ),
                "economics_energy_total": (
                    economics_energy_snapshot.total.as_dict()
                ),
                "economics_daily": economics_daily_snapshot.as_dict(),
                "economics_total": economics_total_snapshot.as_dict(),
                **economics_runtime_values,
                "battery_ac_power_raw": battery_power,
                "battery_ac_power_sensor_valid": bool(
                    battery_ac_power_sensor_valid
                ),
                "battery_charge_w_est": battery_charge_w,
                "battery_discharge_w_est": battery_discharge_w,
                "discharge_blocked_by_soc_min": discharge_blocked_by_soc_min,
                "discharge_resume_soc": float(
                    self._persist.get("discharge_resume_soc", float(soc_min))
                ),
                "soc_discharge_resume_margin": float(resume_margin),
                "low_soc_protection_strict": bool(profile.get("LOW_SOC_PROTECTION_STRICT", False)),
                "low_soc_pv_charge_requires_export": bool(
                    profile.get("LOW_SOC_PV_CHARGE_REQUIRES_EXPORT", False)
                ),
                "low_soc_discharge_requires_cell_resume": bool(
                    profile.get("LOW_SOC_DISCHARGE_REQUIRES_CELL_RESUME", False)
                ),
                "discharge_protection_active": bool(
                    discharge_blocked_by_soc_min or cell_voltage_discharge_blocked
                ),
                "max_charge": max_charge,
                "max_discharge": max_discharge,
                "set_mode": ac_mode,
                "set_input_w": int(round(in_w, 0)),
                "set_output_w": int(round(out_w, 0)),
                
                # V4.3.0-dev5.7:
                # AC mode write diagnostics.
                "mode_write_requested": self._persist.get(
                    "mode_write_requested"
                ),
                "mode_write_entity_state_before_write": self._persist.get(
                    "mode_write_entity_state"
                ),
                "mode_write_live_entity_state": str(
                    self._state(self.entities.ac_mode) or ""
                ),
                "mode_write_skipped": bool(
                    self._persist.get(
                        "mode_write_skipped",
                        False,
                    )
                ),
                "mode_write_skip_reason": str(
                    self._persist.get(
                        "mode_write_skip_reason",
                        "none",
                    )
                    or "none"
                ),
                "mode_write_last_success": self._persist.get(
                    "mode_write_last_success"
                ),
                
                # V4.3.0-dev5.7:
                # INPUT/OUTPUT write diagnostics.
                "input_write_requested_w": self._persist.get(
                    "input_write_requested_w"
                ),
                "input_write_effective_w": self._persist.get(
                    "input_write_effective_w"
                ),
                "input_write_entity_min_w": self._persist.get(
                    "input_write_entity_min_w"
                ),
                "input_write_entity_max_w": self._persist.get(
                    "input_write_entity_max_w"
                ),
                "input_write_clamped": bool(
                    self._persist.get(
                        "input_write_clamped",
                        False,
                    )
                ),
                "input_write_entity_state_w": self._persist.get(
                    "input_write_entity_state_w"
                ),
                "input_write_skipped": bool(
                    self._persist.get(
                        "input_write_skipped",
                        False,
                    )
                ),
                "input_write_skip_reason": str(
                    self._persist.get(
                        "input_write_skip_reason",
                        "none",
                    )
                    or "none"
                ),
                "input_write_last_success_w": self._persist.get(
                    "input_write_last_success_w"
                ),

                "output_write_requested_w": self._persist.get(
                    "output_write_requested_w"
                ),
                "output_write_effective_w": self._persist.get(
                    "output_write_effective_w"
                ),
                "output_write_entity_min_w": self._persist.get(
                    "output_write_entity_min_w"
                ),
                "output_write_entity_max_w": self._persist.get(
                    "output_write_entity_max_w"
                ),
                "output_write_clamped": bool(
                    self._persist.get(
                        "output_write_clamped",
                        False,
                    )
                ),
                "input_live_entity_state_w": _to_float(
                    self._state(self.entities.input_limit),
                    None,
                ),
                "output_live_entity_state_w": _to_float(
                    self._state(self.entities.output_limit),
                    None,
                ),
                
                "output_write_entity_state_w": self._persist.get(
                    "output_write_entity_state_w"
                ),
                "output_write_skipped": bool(
                    self._persist.get(
                        "output_write_skipped",
                        False,
                    )
                ),
                "output_write_skip_reason": str(
                    self._persist.get(
                        "output_write_skip_reason",
                        "none",
                    )
                    or "none"
                ),
                "output_write_last_success_w": self._persist.get(
                    "output_write_last_success_w"
                ),

                # V4.3.0-dev6.2:
                # Bounded recovery diagnostics for a lost active command.
                "command_effectiveness_direction": str(
                    self._persist.get(
                        "command_effectiveness_direction",
                        "none",
                    )
                ),
                "command_effectiveness_status": str(
                    self._persist.get(
                        "command_effectiveness_status",
                        "inactive",
                    )
                ),
                "command_effectiveness_reason": str(
                    self._persist.get(
                        "command_effectiveness_reason",
                        "not_evaluated",
                    )
                ),
                "command_effectiveness_target_w": float(
                    self._persist.get(
                        "command_effectiveness_target_w",
                        0.0,
                    )
                    or 0.0
                ),
                "command_effectiveness_measured_w": float(
                    self._persist.get(
                        "command_effectiveness_measured_w",
                        0.0,
                    )
                    or 0.0
                ),
                "command_effectiveness_mismatch_cycles": int(
                    self._persist.get(
                        "command_effectiveness_mismatch_cycles",
                        0,
                    )
                    or 0
                ),
                "command_effectiveness_retry_count": int(
                    self._persist.get(
                        "command_effectiveness_retry_count",
                        0,
                    )
                    or 0
                ),
                "command_effectiveness_last_retry_at": self._persist.get(
                    "command_effectiveness_last_retry_at"
                ),
                "command_effectiveness_retry_forced": bool(
                    self._persist.get(
                        "command_effectiveness_retry_forced",
                        False,
                    )
                ),
                "command_effectiveness_max_retries": int(
                    self._command_effectiveness_config.max_retries
                ),
                "command_effectiveness_retry_cooldown_s": float(
                    self._command_effectiveness_config.retry_cooldown_s
                ),

                "regulation_command_path": "unified",
                
                "ai_mode": ai_mode,
                "season_mode": (
                    "manual"
                    if ai_mode == AI_MODE_MANUAL
                    else "summer"
                    if ai_mode == AI_MODE_SUMMER
                    else self._persist.get("season_mode", "winter")
                ),
                "manual_action": manual_action,
                "decision_action": display_decision.action,
                "decision_reason": decision.reason,
                "charge_strategy": charge_strategy,
                "current_peak_threshold": current_peak_threshold,
                "current_valley_threshold": current_valley_threshold,
                
                # V4.2.0 regulation / strategy intent diagnostics
                "regulation_strategy_intent": strategy_intent.intent,
                "regulation_requested_mode": strategy_intent.requested_mode,
                "regulation_requested_power_w": (
                    float(strategy_intent.requested_power_w)
                    if strategy_intent.requested_power_w is not None
                    else None
                ),
                "regulation_strategy_reason": strategy_intent.reason,
                "regulation_strategy_priority": int(strategy_intent.priority),
                "regulation_strategy_allow_mode_switch": bool(
                    strategy_intent.allow_mode_switch
                ),
                "regulation_strategy_force": bool(strategy_intent.force),
                "regulation_pv_handover_policy": str(
                    strategy_intent.pv_handover_policy
                ),
                "regulation_load_coverage_priority": bool(
                    strategy_intent.load_coverage_priority
                ),
                "regulation_discharge_allowed": bool(
                    discharge_allowed_for_regulation
                ),
                
                "regulation_resolved_mode": mode_arbiter_result.resolved_mode,
                "regulation_mode_allowed": bool(mode_arbiter_result.allowed),
                "regulation_mode_arbiter_reason": mode_arbiter_result.reason,
                "regulation_active_state": mode_arbiter_result.active_regulation_state,
                "regulation_active_hold_remaining_s": float(
                    mode_arbiter_result.active_hold_remaining_s
                ),
                "regulation_cooldown_remaining_s": float(
                    mode_arbiter_result.cooldown_remaining_s
                ),
                
                # V4.2.0 regulation / power controller diagnostics
                "regulation_control_grid_w": round(
                    float(
                        regulation_power_result.metadata.get(
                            "control_grid_w",
                            float(grid_history_state.grid_now_w) * 0.6
                            + float(grid_history_state.grid_avg_short_w) * 0.4,
                        )
                        if isinstance(regulation_power_result.metadata, dict)
                        else float(grid_history_state.grid_now_w) * 0.6
                        + float(grid_history_state.grid_avg_short_w) * 0.4
                    ),
                    2,
                ),
                "regulation_raw_target_w": float(regulation_power_result.raw_target_w),
                "regulation_limited_target_w": float(
                    regulation_power_result.limited_target_w
                ),
                "regulation_applied_step_w": float(
                    regulation_power_result.applied_step_w
                ),
                "regulation_final_power_w": float(
                    regulation_power_result.final_power_w
                ),
                "regulation_power_reason": regulation_power_result.reason,
                # V4.3.0-dev5.8:
                # Near-zero regulation diagnostics.
                # Expose the already calculated PowerController metadata without
                # changing regulation behavior.
                "regulation_target_import_w": (
                    regulation_power_result.metadata.get("target_import_w")
                    if isinstance(regulation_power_result.metadata, dict)
                    else None
                ),
                "regulation_effective_deadband_w": (
                    regulation_power_result.metadata.get("effective_deadband_w")
                    if isinstance(regulation_power_result.metadata, dict)
                    else None
                ),
                "regulation_error_w": (
                    regulation_power_result.metadata.get("error_w")
                    if isinstance(regulation_power_result.metadata, dict)
                    else None
                ),
                "regulation_near_zero_active": (
                    regulation_power_result.metadata.get("near_zero_active")
                    if isinstance(regulation_power_result.metadata, dict)
                    else None
                ),
                "regulation_near_zero_reason": (
                    regulation_power_result.metadata.get("near_zero_reason")
                    if isinstance(regulation_power_result.metadata, dict)
                    else None
                ),
                "regulation_near_zero_trim_w": (
                    regulation_power_result.metadata.get("near_zero_trim_w")
                    if isinstance(regulation_power_result.metadata, dict)
                    else None
                ),
                "regulation_economic_target_active": (
                    regulation_power_result.metadata.get("economic_target_active")
                    if isinstance(regulation_power_result.metadata, dict)
                    else None
                ),
                "regulation_economic_target_reason": (
                    regulation_power_result.metadata.get("economic_target_reason")
                    if isinstance(regulation_power_result.metadata, dict)
                    else None
                ),
                "regulation_economic_effective_target_import_w": (
                    regulation_power_result.metadata.get(
                        "economic_effective_target_import_w"
                    )
                    if isinstance(regulation_power_result.metadata, dict)
                    else None
                ),
                "regulation_profile_limited": bool(
                    regulation_power_result.profile_limited
                ),
                "regulation_step_limited": bool(
                    regulation_power_result.step_limited
                ),
                
                # V4.2.0 regulation / device command diagnostics
                "regulation_command_ac_mode": regulation_device_command.ac_mode,
                "regulation_command_input_limit_w": float(
                    regulation_device_command.input_limit_w
                ),
                "regulation_command_output_limit_w": float(
                    regulation_device_command.output_limit_w
                ),
                "regulation_command_reason": regulation_device_command.reason,
                "regulation_command_should_write_mode": bool(
                    regulation_device_command.should_write_mode
                ),
                "regulation_command_should_write_input": bool(
                    regulation_device_command.should_write_input
                ),
                "regulation_command_should_write_output": bool(
                    regulation_device_command.should_write_output
                ),
                "regulation_command_skipped": bool(regulation_device_command.skipped),
                "regulation_command_skip_reason": regulation_device_command.skip_reason,
                
                # V4.2.0 regulation / runtime diagnostics
                "regulation_runtime_last_requested_mode": str(
                    self._persist.get("regulation_last_requested_mode", "idle")
                ),
                "regulation_runtime_last_resolved_mode": str(
                    self._persist.get("regulation_last_resolved_mode", "idle")
                ),
                "regulation_runtime_last_mode_change_ts": self._persist.get(
                    "regulation_last_mode_change_ts"
                ),
                "regulation_runtime_last_command_ts": self._persist.get(
                    "regulation_last_command_ts"
                ),
                "regulation_runtime_active_state": str(
                    self._persist.get("regulation_active_state", "none")
                ),
                "regulation_runtime_active_state_started_ts": self._persist.get(
                    "regulation_active_state_started_ts"
                ),
                "regulation_runtime_pv_charge_latch_started_ts": self._persist.get(
                    "regulation_pv_charge_latch_started_ts"
                ),
                "regulation_runtime_discharge_latch_started_ts": self._persist.get(
                    "regulation_discharge_latch_started_ts"
                ),
                "regulation_runtime_passthrough_latch_started_ts": self._persist.get(
                    "regulation_passthrough_latch_started_ts"
                ),
                "regulation_runtime_skipped_write_reason": str(
                    self._persist.get("regulation_skipped_write_reason", "none")
                ),
                
                "regulation_runtime_post_load_drop_hold_until": self._persist.get(
                    "regulation_post_load_drop_hold_until"
                ),
                "regulation_runtime_post_output_overshoot_hold_until": self._persist.get(
                    "regulation_post_output_overshoot_hold_until"
                ),
                
                "adaptive_peak_active": adaptive_peak_active,
                "device_profile": self.device_profile_key,
                "profile_max_input_w": profile_max_in,
                "profile_max_output_w": profile_max_out,
                
                # V4.2.0 regulation / active profile values
                "regulation_profile_target_import_w": float(
                    profile.get("TARGET_IMPORT_W", 0.0) or 0.0
                ),
                "regulation_profile_export_guard_w": float(
                    profile.get("EXPORT_GUARD_W", 0.0) or 0.0
                ),
                "regulation_profile_grid_history_short_samples": int(
                    profile.get("GRID_HISTORY_SHORT_SAMPLES", 0) or 0
                ),
                "regulation_profile_grid_history_medium_samples": int(
                    profile.get("GRID_HISTORY_MEDIUM_SAMPLES", 0) or 0
                ),
                "regulation_profile_grid_history_max_samples": int(
                    profile.get("GRID_HISTORY_MAX_SAMPLES", 0) or 0
                ),
                "regulation_profile_fast_load_change_w": float(
                    profile.get("FAST_LOAD_CHANGE_W", 0.0) or 0.0
                ),
                "regulation_profile_supports_fast_mode_switch": bool(
                    profile.get("SUPPORTS_FAST_MODE_SWITCH", True)
                ),
                "regulation_profile_mode_switch_cooldown_s": float(
                    profile.get("MODE_SWITCH_COOLDOWN_S", 0.0) or 0.0
                ),
                "regulation_profile_input_after_output_block_s": float(
                    profile.get("INPUT_AFTER_OUTPUT_BLOCK_S", 0.0) or 0.0
                ),
                "regulation_profile_output_after_input_block_s": float(
                    profile.get("OUTPUT_AFTER_INPUT_BLOCK_S", 0.0) or 0.0
                ),
                "regulation_profile_stable_export_cycles_for_pv_charge": int(
                    profile.get("STABLE_EXPORT_CYCLES_FOR_PV_CHARGE", 0) or 0
                ),
                "regulation_profile_stable_import_cycles_for_discharge": int(
                    profile.get("STABLE_IMPORT_CYCLES_FOR_DISCHARGE", 0) or 0
                ),
                "regulation_profile_pv_charge_latch_min_hold_s": float(
                    profile.get("PV_CHARGE_LATCH_MIN_HOLD_S", 0.0) or 0.0
                ),
                "regulation_profile_pv_charge_exit_import_cycles": int(
                    profile.get("PV_CHARGE_EXIT_IMPORT_CYCLES", 0) or 0
                ),
                "regulation_profile_discharge_latch_min_hold_s": float(
                    profile.get("DISCHARGE_LATCH_MIN_HOLD_S", 0.0) or 0.0
                ),
                "regulation_profile_discharge_exit_export_cycles": int(
                    profile.get("DISCHARGE_EXIT_EXPORT_CYCLES", 0) or 0
                ),
                "regulation_profile_passthrough_latch_min_hold_s": float(
                    profile.get("PASSTHROUGH_LATCH_MIN_HOLD_S", 0.0) or 0.0
                ),
                "regulation_profile_passthrough_exit_cycles": int(
                    profile.get("PASSTHROUGH_EXIT_CYCLES", 0) or 0
                ),
                "regulation_profile_post_load_drop_hold_s": float(
                    profile.get("POST_LOAD_DROP_HOLD_S", 0.0) or 0.0
                ),
                "regulation_profile_post_output_overshoot_hold_s": float(
                    profile.get("POST_OUTPUT_OVERSHOOT_HOLD_S", 0.0) or 0.0
                ),
                "regulation_profile_external_battery_discharge_block_w": float(
                    profile.get("EXTERNAL_BATTERY_DISCHARGE_BLOCK_W", 0.0) or 0.0
                ),
                "regulation_profile_supports_passthrough": bool(
                    profile.get("SUPPORTS_PASSTHROUGH", False)
                ),
                "regulation_profile_output_zero_is_neutral": bool(
                    profile.get("OUTPUT_ZERO_IS_NEUTRAL", True)
                ),
                "regulation_profile_input_keepalive_safe": bool(
                    profile.get("INPUT_KEEPALIVE_SAFE", True)
                ),
                "regulation_profile_requires_stable_export_for_input": bool(
                    profile.get("REQUIRES_STABLE_EXPORT_FOR_INPUT", False)
                ),
                "regulation_profile_discharge_target_import_w": float(
                    profile.get(
                        "DISCHARGE_TARGET_IMPORT_W",
                        profile.get("TARGET_IMPORT_W", 10.0),
                    )
                    or 0.0
                ),
                # V4.3.0-dev5.8:
                # Charge-binding diagnostics for learned-planning price gating.
                "charge_commit_phase_debug": self._persist.get(
                    "charge_commit_phase"
                ),
                "charge_commit_optimal_start_debug": self._persist.get(
                    "charge_commit_optimal_start"
                ),
                "charge_commit_latest_start_debug": self._persist.get(
                    "charge_commit_latest_start"
                ),
                "charge_commit_deadline_debug": self._persist.get(
                    "charge_commit_deadline"
                ),
                "charge_commit_acceptable_price_per_kwh_debug": self._persist.get(
                    "charge_commit_acceptable_price_per_kwh"
                ),

                # SF800Pro passthrough / arbiter debug
                "pv_houseload_passthrough_enabled": bool(
                    profile.get("PV_HOUSELOAD_PASSTHROUGH", False)
                ),
                "pv_houseload_passthrough_active": bool(
                    pv_houseload_passthrough_active
                ),
                "pv_houseload_passthrough_applied": (
                    decision.reason == "pv_house_load_passthrough"
                ),
                "pv_houseload_passthrough_forced": bool(
                    self._persist.get(
                        "pv_houseload_passthrough_forced",
                        False,
                    )
                ),
                "pv_houseload_passthrough_mppt_clip_capable": bool(
                    profile.get(
                        "MPPT_CLIPS_WITHOUT_OUTPUT",
                        False,
                    )
                ),
                "pv_houseload_passthrough_target_w": float(
                    pv_houseload_passthrough_target_w
                ),
                "pv_houseload_passthrough_stop_reason": str(
                    pv_houseload_passthrough_stop_reason
                ),
                "pv_houseload_passthrough_export_counter": int(
                    self._persist.get("pv_houseload_passthrough_export_counter", 0)
                ),
                "pv_houseload_passthrough_hold_seconds": float(
                    profile.get("PV_HOUSELOAD_PASSTHROUGH_HOLD_SECONDS", 0.0)
                ),
                "sf800_passthrough_prev_output_w": float(
                    self._persist.get("sf800_passthrough_prev_output_w", 0.0) or 0.0
                ),
                "sf800_passthrough_smoothed_target_w": float(
                    self._persist.get("sf800_passthrough_smoothed_target_w", 0.0) or 0.0
                ),
                "sf800_passthrough_min_output_w": float(
                    profile.get("PV_HOUSELOAD_PASSTHROUGH_MIN_OUTPUT_W", 0.0) or 0.0
                ),
                "sf800_passthrough_max_step_up_w": float(
                    profile.get("PV_HOUSELOAD_PASSTHROUGH_MAX_STEP_UP_W", 0.0) or 0.0
                ),
                "sf800_passthrough_max_step_down_w": float(
                    profile.get("PV_HOUSELOAD_PASSTHROUGH_MAX_STEP_DOWN_W", 0.0) or 0.0
                ),
                "sf800_passthrough_smoothing_alpha": float(
                    profile.get("PV_HOUSELOAD_PASSTHROUGH_SMOOTHING_ALPHA", 0.0) or 0.0
                ),

                "soc_limit": soc_limit,
                "additional_battery_charge_w": additional_battery_charge_w,
                "additional_battery_discharge_w": additional_battery_discharge_w,
                "additional_battery_discharge_active": bool(additional_battery_discharge_active),
                "additional_battery_discharge_block_threshold_w": 50.0,

                # V4.2.x Off-Grid / Inselsteckdose
                "offgrid_power_w": float(offgrid_power_w),
                "offgrid_power_raw_w": float(offgrid_power_raw_w),
                "offgrid_mode": str(offgrid_mode),
                "offgrid_mode_raw": offgrid_mode_raw,
                "offgrid_available": bool(offgrid_available),
                "offgrid_active": bool(offgrid_active),
                "offgrid_load_active": bool(offgrid_load_active),
                "offgrid_source_active": bool(offgrid_source_active),
                "offgrid_load_active_w": float(offgrid_load_active_w),
                "offgrid_rule_reason": (
                    "offgrid_load_observed"
                    if bool(offgrid_load_active)
                    else "none"
                ),
                "offgrid_max_internal_supply_w": float(
                    profile.get("OFFGRID_MAX_INTERNAL_SUPPLY_W", 0.0) or 0.0
                ),
                "offgrid_load_blocks_ac_charge": False,
                "offgrid_strategy_policy": "independent_observation",
                "offgrid_input_affects_energy_balance": bool(
                    profile.get("OFFGRID_INPUT_AFFECTS_ENERGY_BALANCE", False)
                ),
                "offgrid_support_active": False,
                "offgrid_support_target_w": 0.0,

                "pv_charge_start_export_w": float(pv_charge_start_export_w),
                "pv_attributable_export_w": round(
                    float(pv_attributable_export_w),
                    1,
                ),
                "pv_charge_latched": bool(pv_charge_latched),
                "pv_charge_start_counter": int(self._persist.get("pv_charge_start_counter", 0)),
                "pv_charge_stop_counter": int(self._persist.get("pv_charge_stop_counter", 0)),
                "pv_charge_hold_export_threshold_w": max(20.0, float(pv_charge_start_export_w) * 0.5),
                "pv_charge_stop_import_tolerance_w": 100.0,
                "installed_pv_wp": self._get_installed_pv_wp(),
                "soc_limit_status": (
                    "not_configured"
                    if soc_limit is None
                    else "no_limit"
                    if soc_limit == 0
                    else "upper_limit_active"
                    if soc_limit == 1
                    else "lower_limit_active"
                ),
                "effective_target_import_w": profile.get("TARGET_IMPORT_W"),
                "effective_deadband_w": profile.get("DEADBAND_W"),
                "effective_export_guard_w": profile.get("EXPORT_GUARD_W"),
                "effective_kp_up": profile.get("KP_UP"),
                "effective_kp_down": profile.get("KP_DOWN"),
                "effective_max_step_up": profile.get("MAX_STEP_UP"),
                "effective_max_step_down": profile.get("MAX_STEP_DOWN"),
                
                "effective_discharge_deadband_w": profile.get("DISCHARGE_DEADBAND_W"),
                "effective_discharge_kp_up": profile.get("DISCHARGE_KP_UP"),
                "effective_discharge_kp_down": profile.get("DISCHARGE_KP_DOWN"),
                "effective_discharge_max_step_up": profile.get("DISCHARGE_MAX_STEP_UP"),
                "effective_discharge_max_step_down": profile.get("DISCHARGE_MAX_STEP_DOWN"),
                "effective_charge_deadband_w": profile.get("CHARGE_DEADBAND_W"),
                "effective_charge_kp_up": profile.get("CHARGE_KP_UP"),
                "effective_charge_kp_down": profile.get("CHARGE_KP_DOWN"),
                "effective_charge_max_step_up": profile.get("CHARGE_MAX_STEP_UP"),
                "effective_charge_max_step_down": profile.get("CHARGE_MAX_STEP_DOWN"),
                
                "effective_keepalive_min_deficit_w": profile.get("KEEPALIVE_MIN_DEFICIT_W"),
                "effective_keepalive_min_output_w": profile.get("KEEPALIVE_MIN_OUTPUT_W"),
                "effective_soc_discharge_resume_margin": profile.get("SOC_DISCHARGE_RESUME_MARGIN"),
                "expert_mode_enabled": self._expert_mode_enabled(),
                "cell_voltage_protection_enabled": self._cell_voltage_protection_enabled(),
                "configured_lowest_cell_voltage_sensor_count": len(
                    [e for e in self.entities.lowest_cell_voltage_entities if e]
                ),
                "global_lowest_cell_voltage": global_lowest_cell_voltage,
                "cell_voltage_status": cell_voltage_status,
                "cell_voltage_soc_plausibility": cell_voltage_soc_plausibility,
                "cell_voltage_soc_warning_threshold": max(float(soc_min) + 10.0, 20.0),
                "cell_voltage_soc_critical_threshold": max(float(soc_min) + 15.0, 30.0),
                "cell_voltage_warning": self._get_setting(
                    SETTING_CELL_VOLTAGE_WARNING,
                    DEFAULT_CELL_VOLTAGE_WARNING,
                ),
                "cell_voltage_cutoff": self._get_setting(
                    SETTING_CELL_VOLTAGE_CUTOFF,
                    DEFAULT_CELL_VOLTAGE_CUTOFF,
                ),
                "cell_voltage_resume": self._get_setting(
                    SETTING_CELL_VOLTAGE_RESUME,
                    DEFAULT_CELL_VOLTAGE_RESUME,
                ),
                "cell_voltage_discharge_blocked": cell_voltage_discharge_blocked,
                "cell_voltage_resume_threshold": self._persist.get(
                    "cell_voltage_resume_threshold"
                ),
                "cell_voltage_emergency_active": cell_voltage_emergency_active,
                "cell_voltage_post_emergency_discharge_locked": bool(
                    self._persist.get(
                        "cell_voltage_post_emergency_discharge_locked", False
                    )
                ),
                "cell_voltage_normal_charge_observed": bool(
                    self._persist.get("cell_voltage_normal_charge_observed", False)
                ),
                "forecast_status": forecast_summary.status,
                "pv_outlook": forecast_summary.pv_outlook,
                "forecast_remaining_today_kwh": float(forecast_summary.remaining_today_kwh),
                "forecast_tomorrow_kwh": float(forecast_summary.tomorrow_kwh),
                "forecast_next_3h_kwh": float(forecast_summary.next_3h_kwh),
                "forecast_next_6h_kwh": float(forecast_summary.next_6h_kwh),
                "forecast_peak_today_w": float(forecast_summary.peak_today_w),
                "forecast_peak_tomorrow_w": float(forecast_summary.peak_tomorrow_w),
                "forecast_source_name": forecast_summary.source_name,
                "forecast_wait_block_counter": int(
                    self._persist.get("forecast_wait_block_counter", 0)
                ),
                "forecast_base_load_w": float(forecast_base_load_w),

                # V4.1.0 learned charge-window planning diagnostics
                "learned_planning_status": learned_charge_plan.status,
                "learned_planning_mode": learned_charge_plan.mode,
                "learned_planning_blocking_reason": learned_charge_plan.blocking_reason,
                "learned_planning_decision_reason": learned_charge_plan.decision_reason,
                "learned_planning_blocks_competing_grid_charge": bool(
                    learned_planning_blocks_competing_grid_charge
                ),
                "learned_planning_history_days": int(learned_readiness.history_days),
                "learned_planning_usable_days": int(learned_readiness.usable_days),
                "learned_planning_night_window_days": int(learned_readiness.night_window_days),
                "learned_planning_morning_window_days": int(learned_readiness.morning_window_days),
                "learned_planning_evening_window_days": int(learned_readiness.evening_window_days),
                "learned_planning_data_coverage": round(float(learned_readiness.data_coverage), 3),
                "learned_planning_sample_count": len(learned_samples),
                "learned_planning_charge_power_sample_count": len(
                    learned_charge_power_samples
                ),
                "learned_planning_learned_charge_power_w": (
                    round(float(learned_charge_power), 1)
                    if learned_charge_power is not None
                    else None
                ),
                "learned_planning_expected_consumption_kwh": float(
                    learned_charge_plan.expected_consumption_kwh
                ),
                "learned_planning_available_battery_energy_kwh": float(
                    learned_charge_plan.available_battery_energy_kwh
                ),
                "learned_planning_reserve_margin_kwh": float(
                    learned_charge_plan.reserve_margin_kwh
                ),
                "learned_planning_forecast_adjustment_kwh": float(
                    learned_charge_plan.forecast_adjustment_kwh
                ),
                "learned_planning_required_charge_energy_kwh": float(
                    learned_charge_plan.required_charge_energy_kwh
                ),
                "learned_planning_minimum_actionable_charge_energy_kwh": float(
                    learned_charge_plan.minimum_actionable_charge_energy_kwh
                ),
                "learned_planning_effective_charge_power_w": float(
                    learned_charge_plan.effective_charge_power_w
                ),
                "learned_planning_effective_window_slots": int(
                    learned_charge_plan.effective_window_slots
                ),
                "learned_planning_effective_window_minutes": int(
                    learned_charge_plan.effective_window_minutes
                ),
                "learned_planning_deadline": self._stable_iso_minute(
                    learned_charge_plan.planning_deadline
                ),
                "learned_planning_deadline_reason": learned_charge_plan.deadline_reason,
                "learned_planning_optimal_charge_start": self._stable_iso_minute(
                    learned_charge_plan.optimal_charge_start
                ),
                "learned_planning_optimal_charge_end": self._stable_iso_minute(
                    learned_charge_plan.optimal_charge_end
                ),
                "learned_planning_window_score": learned_charge_plan.window_score,
                "learned_planning_enabled": bool(learned_planning_enabled),
                "learned_profile_typical_daily_consumption_kwh": float(
                    learned_profile_diagnostics.typical_daily_consumption_kwh
                ),
                "learned_profile_average_house_load_w": float(
                    learned_profile_diagnostics.average_house_load_w
                ),
                "learned_profile_current_slot_consumption_kwh": float(
                    learned_profile_diagnostics.current_slot_consumption_kwh
                ),
                "learned_profile_current_slot_average_w": float(
                    learned_profile_diagnostics.current_slot_average_w
                ),
                "learned_profile_current_slot_index": int(
                    learned_profile_diagnostics.current_slot_index
                ),
                "strategy_state": strategy_state,
                # V4.3.0-dev5.0 unified automatic-strategy context
                "automatic_strategy_active": bool(
                    automatic_strategy_context.active
                ),
                "automatic_weighting": str(
                    automatic_strategy_context.weighting
                ),
                "automatic_season_context": str(
                    automatic_strategy_context.season_context
                ),
                "automatic_pv_weight": float(
                    automatic_strategy_context.pv_weight
                ),
                "automatic_price_weight": float(
                    automatic_strategy_context.price_weight
                ),
                "automatic_reserve_weight": float(
                    automatic_strategy_context.reserve_weight
                ),
                "automatic_forecast_weight": float(
                    automatic_strategy_context.forecast_weight
                ),
                "automatic_strategy_reason": str(
                    automatic_strategy_context.reason
                ),
                "automatic_discharge_allowed": bool(
                    automatic_strategy_context.metadata.get(
                        "automatic_discharge_allowed",
                        False,
                    )
                ),
                "automatic_discharge_reason": str(
                    automatic_strategy_context.metadata.get(
                        "automatic_discharge_reason",
                        "not_evaluated",
                    )
                ),
                "automatic_peak_reserve_allowed": bool(
                    automatic_strategy_context.metadata.get(
                        "automatic_peak_reserve_allowed",
                        False,
                    )
                ),
                "automatic_peak_reserve_reason": str(
                    automatic_strategy_context.metadata.get(
                        "automatic_peak_reserve_reason",
                        "not_evaluated",
                    )
                ),
                "automatic_valley_charge_allowed": bool(
                    automatic_strategy_context.metadata.get(
                        "automatic_valley_charge_allowed",
                        False,
                    )
                ),
                "automatic_valley_charge_reason": str(
                    automatic_strategy_context.metadata.get(
                        "automatic_valley_charge_reason",
                        "not_evaluated",
                    )
                ),
                "automatic_planning_allowed": bool(
                    automatic_strategy_context.metadata.get(
                        "automatic_planning_allowed",
                        False,
                    )
                ),
                "automatic_planning_reason": str(
                    automatic_strategy_context.metadata.get(
                        "automatic_planning_reason",
                        "not_evaluated",
                    )
                ),
                "automatic_discharge_latch_reason": str(
                    self._persist.get(
                        "automatic_discharge_latch_reason",
                        "none",
                    )
                    or "none"
                ),                
                "automatic_pv_weight_reason": str(
                    automatic_strategy_context.metadata.get(
                        "pv_weight_reason",
                        "unknown",
                    )
                ),
                "automatic_price_weight_reason": str(
                    automatic_strategy_context.metadata.get(
                        "price_weight_reason",
                        "unknown",
                    )
                ),
                "automatic_reserve_weight_reason": str(
                    automatic_strategy_context.metadata.get(
                        "reserve_weight_reason",
                        "unknown",
                    )
                ),
                "automatic_forecast_weight_reason": str(
                    automatic_strategy_context.metadata.get(
                        "forecast_weight_reason",
                        "unknown",
                    )
                ),
                "visible_state": visible_state,
                "strategic_reason": strategic_reason,
                "technical_reason": technical_reason,
                "strategy_priority": strategy_priority,
                "strategy_candidate_count": strategy_candidate_count,
                "strategy_eligible_candidate_count": (
                    strategy_eligible_candidate_count
                ),
                "strategy_selected_rule": strategy_selected_rule,
                "strategy_selected_reason": strategy_selected_reason,
                "strategy_selected_state": strategy_selected_state,
                "strategy_selected_priority": strategy_selected_priority,
                "strategy_selection_override_reason": (
                    strategy_selection_override_reason
                ),
                "strategy_candidates": strategy_candidates,
                "source_reason": source_reason,
                "source_action": source_action,
                "source_ac_mode": source_ac_mode,
                "charge_commit_active": charge_commit_active,
                "charge_commit_type": charge_commit_type,
                "charge_commit_reason": charge_commit_reason,
                "charge_commit_source_reason": charge_commit_source_reason,
                "charge_commit_target_soc": charge_commit_target_soc,
                "charge_commit_started_at": charge_commit_started_at,
                "charge_commit_valid_until": charge_commit_valid_until,
                "charge_commit_abort_reason": charge_commit_abort_reason,
                "charge_commit_requested_power_w": charge_commit_requested_power_w,
                "charge_commit_allow_pv_blend": charge_commit_allow_pv_blend,
                # V4.3.0-dev4.0 charge source allocation
                "charge_source_allocation_active": bool(
                    charge_source_allocation.active
                ),
                "charge_total_target_w": float(
                    charge_source_allocation.total_target_w
                ),
                "charge_pv_available_w": float(
                    charge_source_allocation.pv_available_w
                ),
                "charge_pv_allocated_w": float(
                    charge_source_allocation.pv_allocated_w
                ),
                "charge_native_pv_available_w": float(
                    charge_source_allocation.native_pv_available_w
                ),
                "charge_native_pv_allocated_w": float(
                    charge_source_allocation.native_pv_allocated_w
                ),
                "charge_grid_requested_w": float(
                    charge_source_allocation.grid_requested_w
                ),
                "charge_device_input_w": float(
                    charge_source_allocation.device_input_w
                ),
                "charge_unfilled_w": float(
                    charge_source_allocation.unfilled_w
                ),
                "charge_pv_share_pct": float(
                    charge_source_allocation.pv_share_pct
                ),
                "charge_grid_share_pct": float(
                    charge_source_allocation.grid_share_pct
                ),
                "charge_source_allocation_reason": str(
                    charge_source_allocation.reason
                ),
            }

            def _iso_or_none(val):
                try:
                    if not val:
                        return None
                    dt = dt_util.parse_datetime(str(val))
                    return dt_util.as_utc(dt).isoformat() if dt else None
                except Exception:
                    return None

            next_action_time_state = _iso_or_none(self._persist.get("next_action_time"))

            next_action_state = (
                "charging_active"
                if self._persist.get("power_state") == "charging"
                else "discharging_active"
                if self._persist.get("power_state") == "discharging"
                else "discharge_waiting_for_import"
                if self._persist.get("power_state") == "discharge_waiting_for_import"
                else "pv_house_load_passthrough_active"
                if self._persist.get("power_state") == "passthrough"
                else "none"
            )

            await self._async_capture_debug_sample(now=now, details=details)

            return {
                "status": (
                    STATUS_SENSOR_INVALID
                    if strategic_reason
                    in {
                        "sensor_invalid",
                        "soc_invalid",
                        "grid_sensor_invalid",
                        "soc_limits_invalid",
                        "power_limits_invalid",
                        "cell_voltage_sensor_invalid",
                    }
                    else STATUS_OK
                ),
                "ai_status": ai_status,
                "recommendation": recommendation,
                "debug": "OK",
                **self._debug_status_data(),
                "details": details,
                "decision_reason": decision.reason,
                "next_action_time": next_action_time_state,
                "next_action_state": next_action_state,
                "device_profile": self.device_profile_key,
                "season_mode": (
                    "manual"
                    if ai_mode == AI_MODE_MANUAL
                    else "summer"
                    if ai_mode == AI_MODE_SUMMER
                    else self._persist.get("season_mode", "winter")
                ),
                "fault_level_status": "normal",
                "price_daily_average": daily_avg_price,
                "current_peak_threshold": current_peak_threshold,
                "current_valley_threshold": current_valley_threshold,
                "economic_discharge_threshold": economic_discharge_threshold,
                "effective_discharge_threshold": effective_discharge_threshold,
                "engine_health": engine_health,
                # V4.3.0-dev5.0 unified automatic-strategy context
                "automatic_strategy_active": bool(
                    automatic_strategy_context.active
                ),
                "automatic_weighting": str(
                    automatic_strategy_context.weighting
                ),
                "automatic_season_context": str(
                    automatic_strategy_context.season_context
                ),
                "automatic_pv_weight": float(
                    automatic_strategy_context.pv_weight
                ),
                "automatic_price_weight": float(
                    automatic_strategy_context.price_weight
                ),
                "automatic_reserve_weight": float(
                    automatic_strategy_context.reserve_weight
                ),
                "automatic_forecast_weight": float(
                    automatic_strategy_context.forecast_weight
                ),
                "automatic_strategy_reason": str(
                    automatic_strategy_context.reason
                ),
                "automatic_peak_reserve_allowed": bool(
                    automatic_strategy_context.metadata.get(
                        "automatic_peak_reserve_allowed",
                        False,
                    )
                ),
                "automatic_peak_reserve_reason": str(
                    automatic_strategy_context.metadata.get(
                        "automatic_peak_reserve_reason",
                        "not_evaluated",
                    )
                ),
                "automatic_valley_charge_allowed": bool(
                    automatic_strategy_context.metadata.get(
                        "automatic_valley_charge_allowed",
                        False,
                    )
                ),
                "automatic_valley_charge_reason": str(
                    automatic_strategy_context.metadata.get(
                        "automatic_valley_charge_reason",
                        "not_evaluated",
                    )
                ),
                "automatic_planning_allowed": bool(
                    automatic_strategy_context.metadata.get(
                        "automatic_planning_allowed",
                        False,
                    )
                ),
                "automatic_planning_reason": str(
                    automatic_strategy_context.metadata.get(
                        "automatic_planning_reason",
                        "not_evaluated",
                    )
                ),
                "strategy_state": strategy_state,
                "visible_state": visible_state,
                "strategic_reason": strategic_reason,
                "technical_reason": technical_reason,
                "strategy_priority": strategy_priority,
                "strategy_candidate_count": strategy_candidate_count,
                "strategy_eligible_candidate_count": (
                    strategy_eligible_candidate_count
                ),
                "strategy_selected_rule": strategy_selected_rule,
                "strategy_selected_reason": strategy_selected_reason,
                "strategy_selected_state": strategy_selected_state,
                "strategy_selected_priority": strategy_selected_priority,
                "strategy_selection_override_reason": (
                    strategy_selection_override_reason
                ),
                "strategy_candidates": strategy_candidates,
                "source_reason": source_reason,
                "source_action": source_action,
                "source_ac_mode": source_ac_mode,
                "charge_commit_active": charge_commit_active,
                "charge_commit_type": charge_commit_type,
                "charge_commit_reason": charge_commit_reason,
                "charge_commit_source_reason": charge_commit_source_reason,
                "charge_commit_target_soc": charge_commit_target_soc,
                "charge_commit_started_at": charge_commit_started_at,
                "charge_commit_valid_until": charge_commit_valid_until,
                "charge_commit_abort_reason": charge_commit_abort_reason,
                "charge_commit_requested_power_w": charge_commit_requested_power_w,
                "charge_commit_allow_pv_blend": charge_commit_allow_pv_blend,
                "charge_source_allocation_active": bool(
                    charge_source_allocation.active
                ),
                "charge_total_target_w": float(
                    charge_source_allocation.total_target_w
                ),
                "charge_pv_available_w": float(
                    charge_source_allocation.pv_available_w
                ),
                "charge_pv_allocated_w": float(
                    charge_source_allocation.pv_allocated_w
                ),
                "charge_native_pv_available_w": float(
                    charge_source_allocation.native_pv_available_w
                ),
                "charge_native_pv_allocated_w": float(
                    charge_source_allocation.native_pv_allocated_w
                ),
                "charge_grid_requested_w": float(
                    charge_source_allocation.grid_requested_w
                ),
                "charge_device_input_w": float(
                    charge_source_allocation.device_input_w
                ),
                "charge_unfilled_w": float(
                    charge_source_allocation.unfilled_w
                ),
                "charge_pv_share_pct": float(
                    charge_source_allocation.pv_share_pct
                ),
                "charge_grid_share_pct": float(
                    charge_source_allocation.grid_share_pct
                ),
                "charge_source_allocation_reason": str(
                    charge_source_allocation.reason
                ),
            }

        except Exception as err:
            raise UpdateFailed(str(err)) from err
