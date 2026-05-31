from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    UPDATE_INTERVAL,
    # config keys
    CONF_SOC_ENTITY,
    CONF_PV_ENTITY,
    CONF_PV_FORECAST_TODAY_ENTITY,
    CONF_PV_FORECAST_TOMORROW_ENTITY,
    CONF_PRICE_EXPORT_ENTITY,
    CONF_PRICE_NOW_ENTITY,
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
    CONF_CELL_VOLTAGE_PROTECTION_ENABLED,
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
    DEFAULT_PRICE_THRESHOLD,
    DEFAULT_VERY_EXPENSIVE_THRESHOLD,
    DEFAULT_EMERGENCY_SOC,
    DEFAULT_EMERGENCY_CHARGE,
    DEFAULT_PROFIT_MARGIN_PCT,
    DEFAULT_BATTERY_PACKS,
    DEFAULT_PEAK_FACTOR,
    DEFAULT_VALLEY_FACTOR,
    DEFAULT_DEVICE_PROFILE,
    DEFAULT_INSTALLED_PV_WP,
    DEFAULT_EXPERT_MODE_ENABLED,
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
    AI_MODE_WINTER,
    AI_MODE_MANUAL,
    MANUAL_STANDBY,
    # statuses
    STATUS_OK,
    STATUS_SENSOR_INVALID,
    AI_STATUS_STANDBY,
    AI_STATUS_CHARGE_SURPLUS,
    AI_STATUS_PRICE_CHARGE,
    AI_STATUS_COVER_DEFICIT,
    AI_STATUS_EXPENSIVE_DISCHARGE,
    AI_STATUS_VERY_EXPENSIVE_FORCE,
    AI_STATUS_EMERGENCY_CHARGE,
    AI_STATUS_MANUAL,
    RECO_STANDBY,
    RECO_CHARGE,
    RECO_DISCHARGE,
    RECO_EMERGENCY,
    ZENDURE_MODE_INPUT,
    ZENDURE_MODE_OUTPUT,
)
from .device_profiles import DEVICE_PROFILES, merge_profile_with_overrides
from .decision_engine import (
    DecisionContext,
    DecisionEngine,
    DecisionResult,
    PricePoint,
)
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
from .strategy_adapter import decision_to_strategy_intent
from .mode_arbiter import ModeArbiter, build_mode_arbiter_config
from .regulation_models import RegulationRuntimeState
from .regulation_power_controller import (
    RegulationPowerController,
    build_regulation_power_config,
)
from .device_command import DeviceCommandBuilder

_LOGGER = logging.getLogger(__name__)
STORE_VERSION = 1


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


@dataclass
class SelectedEntities:
    soc: str
    pv: str
    pv_forecast_today: str | None
    pv_forecast_tomorrow: str | None
    price_export: str | None
    price_now: str | None
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


class ZendureSmartFlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry

        self.device_profile_key = (
            entry.options.get(CONF_DEVICE_PROFILE)
            or entry.data.get(CONF_DEVICE_PROFILE)
            or DEFAULT_DEVICE_PROFILE
        )

        self._device_profile_cfg = DEVICE_PROFILES.get(
            self.device_profile_key,
            DEVICE_PROFILES[DEFAULT_DEVICE_PROFILE],
        )

        self.runtime_settings: dict[str, float] = dict(entry.options)

        self.entities = SelectedEntities(
            soc=str(entry.data[CONF_SOC_ENTITY]),
            pv=str(entry.data[CONF_PV_ENTITY]),
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
            ac_mode=str(entry.data[CONF_AC_MODE_ENTITY]),
            input_limit=str(entry.data[CONF_INPUT_LIMIT_ENTITY]),
            output_limit=str(entry.data[CONF_OUTPUT_LIMIT_ENTITY]),
            soc_limit=entry.data.get(CONF_SOC_LIMIT_ENTITY),
            grid_mode=str(entry.data.get(CONF_GRID_MODE, GRID_MODE_NONE)),
            grid_power=entry.data.get(CONF_GRID_POWER_ENTITY),
            grid_import=entry.data.get(CONF_GRID_IMPORT_ENTITY),
            grid_export=entry.data.get(CONF_GRID_EXPORT_ENTITY),
            lowest_cell_voltage_entities=tuple(
                entry.options.get(key) for key in LOWEST_CELL_VOLTAGE_CONFIG_KEYS
            ),
        )

        self.runtime_mode: dict[str, Any] = {
            "ai_mode": AI_MODE_AUTOMATIC,
            "manual_action": MANUAL_STANDBY,
        }

        self._engine = DecisionEngine()
        
        self._grid_history = GridHistory(
            build_grid_history_config(self._get_active_profile())
        )
        
        self._mode_arbiter = ModeArbiter(
            build_mode_arbiter_config(self._get_active_profile())
        )
        
        self._regulation_power_controller = RegulationPowerController(
            build_regulation_power_config(self._get_active_profile())
        )
        
        self._device_command_builder = DeviceCommandBuilder()

        self._store = Store(hass, STORE_VERSION, f"{DOMAIN}.{entry.entry_id}")
        self._persist: dict[str, Any] = {
            "runtime_mode": dict(self.runtime_mode),

            # last applied setpoints
            "last_set_mode": None,
            "last_set_input_w": None,
            "last_set_output_w": None,
            "prev_discharge_w": 0.0,
            "prev_charge_w": 0.0,

            # basic state
            "power_state": "idle",  # idle|charging|discharging|passthrough
            "emergency_active": False,
            "discharge_blocked_by_soc_min": False,
            "discharge_resume_soc": None,

            # analytics
            "trade_avg_charge_price": None,
            "trade_charged_kwh": 0.0,
            "trade_cycle_below_soc_min": False,
            "prev_soc": None,

            "avg_charge_price": None,
            "charged_kwh": 0.0,
            "discharged_kwh": 0.0,
            "profit_eur": 0.0,
            "last_ts": None,

            # season detection
            "season_mode": "winter",
            "season_counter": 0,

            # cell voltage
            "global_lowest_cell_voltage": None,
            "cell_voltage_status": "disabled",
            "cell_voltage_discharge_blocked": False,
            "cell_voltage_resume_threshold": None,
            "cell_voltage_soc_plausibility": "not_available",

            # PV charge debounce / hysteresis
            "pv_charge_start_counter": 0,
            "pv_charge_stop_counter": 0,
            "pv_charge_latched": False,

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

            # SF800Pro PV charge latch / mode arbiter
            "sf800_pv_charge_latched": False,
            "sf800_pv_charge_started_ts": None,
            "sf800_pv_charge_stop_counter": 0,
            "sf800_mode_arbiter_state": "none",
            "sf800_mode_arbiter_reason": "none",

            # SF800Pro passthrough output smoothing
            "sf800_passthrough_prev_output_w": 0.0,
            "sf800_passthrough_smoothed_target_w": 0.0,
            
            # V4.2.0 regulation execution switch
            "use_regulation_v42_command": False,

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
            "regulation_passthrough_latch_started_ts": None,
            "regulation_skipped_write_reason": "none",

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
        data = await self._store.async_load()
        if isinstance(data, dict):
            self._persist.update(data)
            if "runtime_mode" in data and isinstance(data["runtime_mode"], dict):
                self.runtime_mode.update(data["runtime_mode"])

    async def _save(self) -> None:
        self._persist["runtime_mode"] = dict(self.runtime_mode)
        await self._store.async_save(self._persist)

    def _state(self, entity_id: str | None) -> Any:
        if not entity_id:
            return None
        st = self.hass.states.get(entity_id)
        return st.state if st else None

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
        self.runtime_mode["ai_mode"] = mode

    def set_manual_action(self, action: str) -> None:
        self.runtime_mode["manual_action"] = action

    async def _set_ac_mode(self, mode: str) -> None:
        current = self._state(self.entities.ac_mode)
        if current == mode:
            self._persist["last_set_mode"] = mode
            return

        self._persist["last_set_mode"] = mode
        await self.hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": self.entities.ac_mode, "option": mode},
            blocking=False,
        )

    async def _set_input_limit(self, watts: float) -> None:
        val = int(round(float(watts), 0))
        last = self._persist.get("last_set_input_w")
        if last == val:
            return
        self._persist["last_set_input_w"] = val
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.entities.input_limit, "value": val},
            blocking=False,
        )

    async def _set_output_limit(self, watts: float) -> None:
        val = int(round(float(watts), 0))
        last = self._persist.get("last_set_output_w")
        if last == val:
            return
        self._persist["last_set_output_w"] = val
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.entities.output_limit, "value": val},
            blocking=False,
        )

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

    def _get_price_now(self) -> float | None:
        if self.entities.price_now:
            p = _to_float(self._state(self.entities.price_now), None)
            if p is not None:
                return float(p)
        return None

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
        """Keep only recent learned charge-power samples."""

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

                cleaned.append(
                    {
                        "ts": ts_utc.isoformat(),
                        "power_w": round(power_w, 1),
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

        # Prefer real measured AC charge power. If the battery power sensor does
        # not provide a negative charging value, fall back to the command.
        charge_power_w = measured_charge_w if measured_charge_w > 0.0 else commanded_charge_w

        if charge_power_w < MIN_LEARNED_CHARGE_POWER_SAMPLE_W:
            return

        self._persist.setdefault("learned_charge_power_samples", []).append(
            {
                "ts": dt_util.as_utc(now).isoformat(),
                "power_w": round(charge_power_w, 1),
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

                samples.append(
                    LearningChargePowerSample(
                        ts=dt_util.as_utc(ts),
                        power_w=power_w,
                    )
                )
            except Exception:
                continue

        samples.sort(key=lambda s: s.ts)
        return samples
        
    def _get_regulation_runtime_state(self) -> RegulationRuntimeState:
        """Build transient regulation runtime state from persisted values.

        V4.2.0 transition:
        This is diagnostic-only for now. Later this state will become the
        authoritative runtime state for ModeArbiter/PowerController/Command.
        """

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
            
        # Post-load-drop hold:
        # If a large load drop happens while output was active, avoid switching
        # directly into INPUT/PV charge. Let the new controller ramp output down first.
        if bool(getattr(grid, "fast_load_drop_detected", False)) and (
            last_output_w > 0.0
            or previous_active_state == "discharge_active"
            or active_state == "discharge_active"
        ):
            self._persist["regulation_post_load_drop_hold_until"] = (
                now_utc + timedelta(seconds=post_load_drop_hold_s)
            ).isoformat()

        # Post-output-overshoot hold:
        # If output causes/keeps export beyond guard, block immediate INPUT handover.
        grid_now_w = float(getattr(grid, "grid_now_w", 0.0) or 0.0)
        if grid_now_w <= -abs(export_guard_w) and (
            last_output_w > 0.0
            or previous_active_state == "discharge_active"
            or active_state == "discharge_active"
        ):
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
    ) -> tuple[int, int, bool]:
        start_counter = int(self._persist.get("pv_charge_start_counter", 0) or 0)
        stop_counter = int(self._persist.get("pv_charge_stop_counter", 0) or 0)
        latched = bool(self._persist.get("pv_charge_latched", False))

        start_threshold = float(pv_charge_start_export_w or 0.0)

        start_required_cycles = 2
        stop_required_cycles = 8

        hold_export_threshold = max(20.0, start_threshold * 0.5)
        small_import_tolerance_w = 100.0
        hard_import_threshold_w = 140.0
        weak_export_threshold = max(10.0, start_threshold * 0.15)

        export_w = max(0.0, float(grid_export_w or 0.0))
        import_w = max(0.0, float(grid_import_w or 0.0))

        has_start_surplus = export_w >= start_threshold
        has_hold_surplus = export_w >= hold_export_threshold
        import_is_small = import_w <= small_import_tolerance_w

        real_weakness = (
            import_w >= hard_import_threshold_w
            and export_w <= weak_export_threshold
        )

        if latched:
            start_counter = 0

            if real_weakness:
                stop_counter += 1
            elif has_hold_surplus or import_is_small:
                stop_counter = 0
            else:
                stop_counter += 1

            if stop_counter >= stop_required_cycles:
                latched = False
                stop_counter = 0

        else:
            stop_counter = 0

            if has_start_surplus:
                start_counter += 1
            else:
                start_counter = 0

            if start_counter >= start_required_cycles:
                latched = True
                start_counter = 0
                stop_counter = 0

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
    ) -> tuple[bool, float, str]:
        enabled = bool(profile.get("PV_HOUSELOAD_PASSTHROUGH", False))

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
            pv_charge_latched = bool(self._persist.get("sf800_pv_charge_latched", False))

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

            if active:
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
                    not pv_charge_latched
                    and enough_pv
                    and enough_house_load
                    and useful_target
                    and export_val < float(pv_charge_start_export_w or 0.0)
                    and import_val <= max(250.0, house_val * 0.50)
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
        self._persist["pv_houseload_passthrough_export_counter"] = int(export_counter)
        self._persist["pv_houseload_passthrough_target_w"] = float(target_w or 0.0)
        self._persist["pv_houseload_passthrough_stop_reason"] = str(stop_reason)

        return bool(active), float(target_w or 0.0), str(stop_reason)

    def _is_sf800_pv_houseload_passthrough_enabled(self, profile: dict[str, Any]) -> bool:
        return bool(profile.get("PV_HOUSELOAD_PASSTHROUGH", False))

    def _sf800_hold_active(
        self,
        now,
        started_ts_raw: str | None,
        hold_seconds: float,
    ) -> bool:
        if not started_ts_raw:
            return False

        try:
            started = dt_util.parse_datetime(str(started_ts_raw))
            if started is None:
                return False

            elapsed = (
                dt_util.as_utc(now) - dt_util.as_utc(started)
            ).total_seconds()

            return elapsed < float(hold_seconds)
        except Exception:
            return False

    def _sf800_update_pv_charge_latch(
        self,
        now,
        profile: dict[str, Any],
        decision: DecisionResult,
        grid_import_w: float,
        grid_export_w: float,
        pv_charge_start_export_w: float,
        protection_active: bool,
    ) -> tuple[bool, str]:
        enabled = self._is_sf800_pv_houseload_passthrough_enabled(profile)
        if not enabled:
            self._persist["sf800_pv_charge_latched"] = False
            self._persist["sf800_pv_charge_started_ts"] = None
            self._persist["sf800_pv_charge_stop_counter"] = 0
            return False, "disabled"

        latched = bool(self._persist.get("sf800_pv_charge_latched", False))
        started_ts = self._persist.get("sf800_pv_charge_started_ts")
        stop_counter = int(self._persist.get("sf800_pv_charge_stop_counter", 0) or 0)

        hold_seconds = float(profile.get("PV_CHARGE_LATCH_HOLD_SECONDS", 300.0) or 300.0)
        stop_cycles = int(profile.get("PV_CHARGE_LATCH_STOP_CYCLES", 18) or 18)

        export_w = max(0.0, float(grid_export_w or 0.0))
        import_w = max(0.0, float(grid_import_w or 0.0))
        start_threshold = float(pv_charge_start_export_w or 0.0)

        hold_active = self._sf800_hold_active(now, started_ts, hold_seconds)

        decision_is_pv_charge = (
            decision.ac_mode == "input"
            and float(decision.charge_w or 0.0) > 0.0
            and decision.reason == "pv_surplus_charge"
        )

        if protection_active:
            latched = False
            started_ts = None
            stop_counter = 0
            reason = "protection_active"

        elif decision_is_pv_charge:
            if not latched:
                started_ts = dt_util.as_utc(now).isoformat()
            latched = True
            stop_counter = 0
            reason = "pv_charge_decision"

        elif latched:
            weak_pv_charge_conditions = (
                export_w < max(10.0, start_threshold * 0.15)
                and import_w > 140.0
            )

            if hold_active:
                reason = "hold_active"
            elif weak_pv_charge_conditions:
                stop_counter += 1
                reason = "weakness_counting"
                if stop_counter >= stop_cycles:
                    latched = False
                    started_ts = None
                    stop_counter = 0
                    reason = "weakness_stop"
            else:
                stop_counter = 0
                reason = "latched"

        else:
            reason = "not_latched"

        self._persist["sf800_pv_charge_latched"] = bool(latched)
        self._persist["sf800_pv_charge_started_ts"] = started_ts
        self._persist["sf800_pv_charge_stop_counter"] = int(stop_counter)

        return bool(latched), str(reason)

    def _sf800_apply_mode_arbiter(
        self,
        now,
        profile: dict[str, Any],
        decision: DecisionResult,
        pv_w: float,
        house_load_w: float,
        grid_import_w: float,
        grid_export_w: float,
        max_discharge_w: float,
        pv_charge_start_export_w: float,
        discharge_blocked_by_soc_min: bool,
        cell_voltage_discharge_blocked: bool,
        cell_voltage_emergency_active: bool,
        additional_battery_charge_w: float,
    ) -> DecisionResult:
        enabled = self._is_sf800_pv_houseload_passthrough_enabled(profile)
        if not enabled:
            self._persist["sf800_mode_arbiter_state"] = "disabled"
            self._persist["sf800_mode_arbiter_reason"] = "disabled"
            return decision

        protection_active = bool(
            discharge_blocked_by_soc_min
            or cell_voltage_discharge_blocked
            or cell_voltage_emergency_active
            or float(additional_battery_charge_w or 0.0) > 0.0
        )

        pv_charge_latched, pv_charge_latch_reason = self._sf800_update_pv_charge_latch(
            now=now,
            profile=profile,
            decision=decision,
            grid_import_w=float(grid_import_w or 0.0),
            grid_export_w=float(grid_export_w or 0.0),
            pv_charge_start_export_w=float(pv_charge_start_export_w),
            protection_active=protection_active,
        )

        passthrough_active = bool(
            self._persist.get("pv_houseload_passthrough_active", False)
        )
        passthrough_target_w = float(
            self._persist.get("pv_houseload_passthrough_target_w", 0.0) or 0.0
        )

        decision_is_true_priority_charge = (
            decision.ac_mode == "input"
            and float(decision.charge_w or 0.0) > 0.0
            and decision.reason
            in {
                "very_cheap_force_charge",
                "emergency_latched_charge",
                "cell_voltage_emergency_charge",
                "manual_charge",
            }
        )
        
        decision_is_manual_priority_discharge = (
            decision.ac_mode == "output"
            and float(decision.discharge_w or 0.0) > 0.0
            and decision.reason
            in {
                "manual_discharge",
                "manual_constant_discharge",
            }
        )

        if protection_active:
            self._persist["sf800_mode_arbiter_state"] = "protection"
            self._persist["sf800_mode_arbiter_reason"] = "protection_active"
            return decision

        if decision_is_true_priority_charge:
            self._persist["sf800_mode_arbiter_state"] = "priority_charge"
            self._persist["sf800_mode_arbiter_reason"] = decision.reason
            return decision

        if decision_is_manual_priority_discharge:
            self._persist["sf800_mode_arbiter_state"] = "manual_priority_discharge"
            self._persist["sf800_mode_arbiter_reason"] = decision.reason

            # Clear SF800Pro latches that could otherwise override manual discharge.
            self._persist["pv_houseload_passthrough_active"] = False
            self._persist["pv_houseload_passthrough_started_ts"] = None
            self._persist["pv_houseload_passthrough_export_counter"] = 0
            self._persist["pv_houseload_passthrough_target_w"] = 0.0
            self._persist["pv_houseload_passthrough_stop_reason"] = "manual_priority_discharge"

            self._persist["sf800_pv_charge_latched"] = False
            self._persist["sf800_pv_charge_started_ts"] = None
            self._persist["sf800_pv_charge_stop_counter"] = 0

            return decision

        if pv_charge_latched:
            if decision.reason == "pv_house_load_passthrough":
                self._persist["sf800_mode_arbiter_state"] = "pv_charge_latched"
                self._persist["sf800_mode_arbiter_reason"] = (
                    f"blocked_passthrough_{pv_charge_latch_reason}"
                )
                return DecisionResult(
                    action="charge",
                    ac_mode="input",
                    charge_w=max(80.0, float(decision.charge_w or 0.0)),
                    discharge_w=0.0,
                    reason="pv_surplus_charge",
                    target_soc=decision.target_soc,
                )

            if decision.ac_mode == "input":
                self._persist["sf800_mode_arbiter_state"] = "pv_charge_latched"
                self._persist["sf800_mode_arbiter_reason"] = pv_charge_latch_reason
                return decision

        if passthrough_active and passthrough_target_w > 0.0:
            self._persist["sf800_mode_arbiter_state"] = "passthrough_latched"
            self._persist["sf800_mode_arbiter_reason"] = "hold_output"

            return DecisionResult(
                action="passthrough",
                ac_mode="output",
                charge_w=0.0,
                discharge_w=min(
                    float(passthrough_target_w),
                    float(max_discharge_w),
                ),
                reason="pv_house_load_passthrough",
                target_soc=decision.target_soc,
            )

        self._persist["sf800_mode_arbiter_state"] = "normal"
        self._persist["sf800_mode_arbiter_reason"] = "normal_decision"
        return decision

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
            return blocked

        cell_v = float(global_lowest_cell_voltage)

        if cell_v <= float(cutoff):
            blocked = True
        elif cell_v >= float(resume):
            blocked = False

        self._persist["cell_voltage_discharge_blocked"] = blocked
        return blocked

    def _classify_charge_source(
        self,
        delta_kwh: float,
        grid_import_w: float,
        grid_export_w: float,
        decision_charge_w: float,
        decision_ac_mode: str,
        price_now: float | None,
        decision_reason: str | None = None,
    ) -> tuple[bool, float, str]:
        if delta_kwh <= 0:
            return False, 0.0, "no_charge_delta"

        if decision_ac_mode != "input":
            return False, 0.0, "not_in_input_mode"

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
        }

        if decision_reason in price_driven_charge_reasons:
            if price_now is not None:
                return True, float(price_now), str(decision_reason)
            return False, 0.0, "price_driven_charge_price_missing"

        charge_cmd_w = max(0.0, float(decision_charge_w or 0.0))
        if charge_cmd_w <= 0.0:
            return False, 0.0, "no_charge_command"

        import_w = max(0.0, float(grid_import_w or 0.0))
        export_w = max(0.0, float(grid_export_w or 0.0))

        export_threshold = 40.0
        noise_import_threshold = 60.0
        strong_import_threshold = max(120.0, min(charge_cmd_w * 0.35, 500.0))

        if export_w >= export_threshold:
            return False, 0.0, "pv_surplus_export"

        if import_w <= noise_import_threshold:
            return False, 0.0, "pv_or_free_low_import"

        if price_now is None:
            return False, 0.0, "price_missing_assume_free"

        if import_w >= strong_import_threshold:
            return True, float(price_now), "grid_charge"

        return False, 0.0, "mixed_bias_pv"

    def _parse_price_points(self, now) -> list[PricePoint]:
        if not self.entities.price_export:
            return []

        st = self.hass.states.get(self.entities.price_export)
        if not st:
            return []

        attrs = st.attributes or {}

        raw = (
            attrs.get("rates")
            or attrs.get("data")
            or attrs.get("unit_rate_forecast")
        )

        if not raw:
            return []

        if isinstance(raw, dict):
            raw = raw.get("rates") or raw.get("data") or raw.get("timeslots")

        if not isinstance(raw, list):
            return []

        tz = dt_util.get_default_time_zone()

        def normalize(dt):
            if not dt:
                return None
            if dt.tzinfo is None:
                return dt.replace(tzinfo=tz)
            return dt.astimezone(tz)

        now = normalize(now)

        out: list[PricePoint] = []

        for item in raw:
            if not isinstance(item, dict):
                continue

            if "validFrom" in item and "validTo" in item:
                start = item.get("validFrom")
                end = item.get("validTo")

                cents = None
                uinfo = item.get("unitRateInformation") or {}
                rates_list = uinfo.get("rates") or []
                if rates_list and isinstance(rates_list[0], dict):
                    cents = _to_float(
                        rates_list[0].get("latestGrossUnitRateCentsPerKwh"),
                        None,
                    )

                if not start or not end or cents is None:
                    continue

                t_start = normalize(dt_util.parse_datetime(str(start)))
                t_end = normalize(dt_util.parse_datetime(str(end)))

                if not t_start or not t_end:
                    continue

                if t_end <= t_start:
                    continue

                if t_end <= now:
                    continue

                price = float(cents) / 100.0
                out.append(PricePoint(start=t_start, end=t_end, price=price))
                continue

            start = (
                item.get("start_time")
                or item.get("starts_at")
                or item.get("start")
                or item.get("time")
            )

            end = (
                item.get("end_time")
                or item.get("ends_at")
                or item.get("end")
            )

            p = _to_float(
                item.get("price_per_kwh")
                or item.get("value_inc_vat")
                or item.get("value")
                or item.get("unit_rate")
                or item.get("price"),
                None,
            )

            if not start or p is None:
                continue

            t_start = normalize(dt_util.parse_datetime(str(start)))
            if not t_start:
                continue

            if end:
                t_end = normalize(dt_util.parse_datetime(str(end)))
                if not t_end:
                    continue
            else:
                t_end = t_start + timedelta(minutes=15)

            if t_end <= t_start:
                continue

            if t_end <= now:
                continue

            out.append(PricePoint(start=t_start, end=t_end, price=float(p)))

        out.sort(key=lambda x: x.start)
        return out

    def _season_detection(self, pv_w: float, export_w: float) -> str:
        season = self._persist.get("season_mode", "winter")
        counter = int(self._persist.get("season_counter", 0))

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

        if summer_signal:
            counter += 1
        elif winter_signal:
            counter -= 1
        else:
            if counter > 0:
                counter -= 1
            elif counter < 0:
                counter += 1

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
        }

        return season

    def _map_ai_status(self, ai_mode: str, action: str, reason: str) -> str:
        if ai_mode == AI_MODE_MANUAL:
            return AI_STATUS_MANUAL
        if action == "passthrough" or reason == "pv_house_load_passthrough":
            return AI_STATUS_STANDBY
        if action == "emergency":
            return AI_STATUS_EMERGENCY_CHARGE
        if action == "charge":
            if reason == "pv_surplus_charge":
                return AI_STATUS_CHARGE_SURPLUS
            if "valley" in reason or "planning" in reason or "price" in reason:
                return AI_STATUS_PRICE_CHARGE
            return AI_STATUS_CHARGE_SURPLUS
        if action == "discharge":
            if "very_expensive" in reason or "adaptive_peak" in reason:
                return AI_STATUS_VERY_EXPENSIVE_FORCE
            if "price" in reason:
                return AI_STATUS_EXPENSIVE_DISCHARGE
            return AI_STATUS_COVER_DEFICIT
        return AI_STATUS_STANDBY

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

        return "none"

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            if self._persist.get("last_ts") is None:
                await self._load()
                self._persist["last_ts"] = dt_util.utcnow().isoformat()

            now = dt_util.utcnow()

            soc = _to_float(self._state(self.entities.soc), None)
            pv = _to_float(self._state(self.entities.pv), None)

            if soc is None or pv is None:
                return {
                    "status": STATUS_SENSOR_INVALID,
                    "ai_status": AI_STATUS_STANDBY,
                    "recommendation": RECO_STANDBY,
                    "debug": "SENSOR_INVALID",
                    "details": {
                        "soc_raw": self._state(self.entities.soc),
                        "pv_raw": self._state(self.entities.pv),
                    },
                    "decision_reason": "sensor_invalid",
                    "next_action_time": None,
                    "next_action_state": "none",
                    "device_profile": self.device_profile_key,
                    "season_mode": self._persist.get("season_mode", "winter"),
                    "fault_level_status": "normal",
                }

            soc = float(soc)
            pv_w = float(pv)

            battery_capacity_kwh = self._get_battery_capacity()

            prev_soc = self._persist.get("prev_soc")
            delta_kwh = 0.0

            if prev_soc is not None and battery_capacity_kwh > 0:
                soc_delta_pct = soc - prev_soc
                delta_kwh = battery_capacity_kwh * (soc_delta_pct / 100.0)

            self._persist["prev_soc"] = soc

            profile = self._get_active_profile()

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

            expensive = self._get_setting(SETTING_PRICE_THRESHOLD, DEFAULT_PRICE_THRESHOLD)
            very_expensive = self._get_setting(
                SETTING_VERY_EXPENSIVE_THRESHOLD,
                DEFAULT_VERY_EXPENSIVE_THRESHOLD,
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

            ai_mode = str(self.runtime_mode.get("ai_mode", AI_MODE_AUTOMATIC))
            manual_action = str(self.runtime_mode.get("manual_action", MANUAL_STANDBY))

            grid_import, grid_export = self._get_grid()
            if grid_import is None or grid_export is None:
                grid_import = 0.0
                grid_export = 0.0
                
            grid_history_state = self._grid_history.update(
                grid_import_w=float(grid_import or 0.0),
                grid_export_w=float(grid_export or 0.0),
            )

            price_now = self._get_price_now()
            price_points = self._parse_price_points(now)

            forecast_summary = build_forecast_summary(
                hass=self.hass,
                today_entity_id=self.entities.pv_forecast_today,
                tomorrow_entity_id=self.entities.pv_forecast_tomorrow,
                installed_pv_wp=self._get_installed_pv_wp(),
                forecast_base_load_w=float(forecast_base_load_w),
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

                self._persist["sf800_pv_charge_latched"] = False
                self._persist["sf800_pv_charge_started_ts"] = None
                self._persist["sf800_pv_charge_stop_counter"] = 0

            daily_avg_price = None
            if price_points:
                prices = [p.price for p in price_points]
                if prices:
                    daily_avg_price = sum(prices) / len(prices)

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

            pv_charge_start_counter, pv_charge_stop_counter, pv_charge_latched = (
                self._update_pv_charge_hysteresis(
                    grid_import_w=float(grid_import or 0.0),
                    grid_export_w=float(grid_export or 0.0),
                    pv_w=float(pv_w or 0.0),
                    pv_charge_start_export_w=float(pv_charge_start_export_w),
                )
            )

            very_cheap_price = self.runtime_settings.get("very_cheap_price", None)
            if very_cheap_price is not None:
                try:
                    very_cheap_price = float(very_cheap_price)
                except Exception:
                    very_cheap_price = None

            engine_health = "ok"
            if not price_points:
                engine_health = "no_price_data"
            elif price_now is None:
                engine_health = "no_current_price"

            battery_raw = self._state(self.entities.battery_ac_power)
            battery_power = _to_float(battery_raw, 0.0)
            battery_power = float(battery_power or 0.0)

            battery_discharge_w = max(0.0, battery_power)
            battery_charge_w = max(0.0, -battery_power)

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
                price_points=price_points,
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

            discharge_blocked_by_soc_min = self._update_discharge_resume_hysteresis(
                soc=float(soc),
                soc_min=float(soc_min),
                resume_margin=float(resume_margin),
            )

            if float(soc) <= float(soc_min):
                self._persist["trade_avg_charge_price"] = 0.0
                self._persist["trade_charged_kwh"] = 0.0
                self._persist["trade_cycle_below_soc_min"] = True
            elif float(soc) > float(soc_min):
                self._persist["trade_cycle_below_soc_min"] = False

            cell_voltage_emergency_active = bool(
                self._cell_voltage_protection_enabled()
                and global_lowest_cell_voltage is not None
                and float(global_lowest_cell_voltage)
                <= float(
                    self._get_setting(
                        SETTING_CELL_VOLTAGE_WARNING,
                        DEFAULT_CELL_VOLTAGE_WARNING,
                    )
                )
            )

            manual_mode_active = ai_mode == AI_MODE_MANUAL

            if manual_mode_active:
                self._persist["pv_houseload_passthrough_active"] = False
                self._persist["pv_houseload_passthrough_started_ts"] = None
                self._persist["pv_houseload_passthrough_export_counter"] = 0
                self._persist["pv_houseload_passthrough_target_w"] = 0.0
                self._persist["pv_houseload_passthrough_stop_reason"] = "manual_mode"

                self._persist["sf800_pv_charge_latched"] = False
                self._persist["sf800_pv_charge_started_ts"] = None
                self._persist["sf800_pv_charge_stop_counter"] = 0

                pv_houseload_passthrough_active = False
                pv_houseload_passthrough_target_w = 0.0
                pv_houseload_passthrough_stop_reason = "manual_mode"
            else:
                pv_houseload_passthrough_active, pv_houseload_passthrough_target_w, pv_houseload_passthrough_stop_reason = (
                    self._update_pv_houseload_passthrough(
                        now=now,
                        profile=profile,
                        soc=float(soc),
                        soc_min=float(soc_min),
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
                    )
                )

            ctx = DecisionContext(
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
                price_now=price_now,
                avg_charge_price=self._persist.get("trade_avg_charge_price"),
                expensive_threshold=float(expensive),
                very_expensive_threshold=float(very_expensive),
                profit_margin_pct=float(profit_margin_pct),
                price_points=price_points,
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

            decision = self._engine.evaluate(ctx)

            decision = self._sf800_apply_mode_arbiter(
                now=now,
                profile=profile,
                decision=decision,
                pv_w=float(pv_w),
                house_load_w=float(house_load),
                grid_import_w=float(grid_import or 0.0),
                grid_export_w=float(grid_export or 0.0),
                max_discharge_w=float(max_discharge),
                pv_charge_start_export_w=float(pv_charge_start_export_w),
                discharge_blocked_by_soc_min=bool(discharge_blocked_by_soc_min),
                cell_voltage_discharge_blocked=bool(cell_voltage_discharge_blocked),
                cell_voltage_emergency_active=bool(cell_voltage_emergency_active),
                additional_battery_charge_w=float(additional_battery_charge_w or 0.0),
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
                    
            # V4.2.0 carryover safety for legacy execution:
            # Do not keep PV charge/keepalive active when there is no real export and
            # the house is importing from grid. This prevents INPUT 80 W from being held
            # by the old PV charge latch during weak/cloudy PV or low-SoC situations.
            if (
                decision.ac_mode == "input"
                and float(decision.charge_w or 0.0) > 0.0
                and decision.reason == "pv_surplus_charge"
            ):
                export_w = max(0.0, float(grid_export or 0.0))
                import_w = max(0.0, float(grid_import or 0.0))

                weak_export_threshold_w = max(10.0, float(pv_charge_start_export_w) * 0.25)
                real_import_threshold_w = max(80.0, float(profile.get("TARGET_IMPORT_W", 10.0)) * 4.0)

                if export_w < weak_export_threshold_w and import_w > real_import_threshold_w:
                    decision.charge_w = 0.0
                    decision.discharge_w = 0.0
                    decision.action = "idle"
                    decision.ac_mode = "output"
                    decision.reason = "pv_charge_blocked_no_stable_export"

                    self._persist["pv_charge_latched"] = False
                    self._persist["pv_charge_start_counter"] = 0
                    self._persist["pv_charge_stop_counter"] = 0

            charge_price_applied = None
            charge_source = "no_charge_delta"
            is_grid_charge = False

            if delta_kwh > 0:
                is_below_soc_min_cycle = bool(
                    self._persist.get("trade_cycle_below_soc_min", False)
                )

                is_grid_charge, applied_price, charge_source = self._classify_charge_source(
                    delta_kwh=float(delta_kwh),
                    grid_import_w=float(grid_import or 0.0),
                    grid_export_w=float(grid_export or 0.0),
                    decision_charge_w=float(decision.charge_w or 0.0),
                    decision_ac_mode=str(decision.ac_mode),
                    price_now=price_now,
                    decision_reason=str(decision.reason),
                )

                charge_price_applied = float(applied_price)

                if not is_below_soc_min_cycle:
                    charged_kwh = float(self._persist.get("trade_charged_kwh", 0.0) or 0.0)
                    avg_price = self._persist.get("trade_avg_charge_price")

                    new_total_kwh = charged_kwh + float(delta_kwh)

                    if new_total_kwh > 0:
                        if avg_price is None:
                            new_avg = float(applied_price)
                        else:
                            new_avg = (
                                (float(avg_price) * charged_kwh + float(applied_price) * float(delta_kwh))
                                / new_total_kwh
                            )
                    else:
                        new_avg = 0.0

                    self._persist["trade_charged_kwh"] = new_total_kwh
                    self._persist["trade_avg_charge_price"] = new_avg

            if (
                delta_kwh < 0
                and price_now is not None
                and decision.ac_mode == "output"
                and float(decision.discharge_w or 0.0) > 0.0
                and decision.reason != "pv_house_load_passthrough"
            ):
                sold_kwh = abs(float(delta_kwh))
                avg_price = self._persist.get("trade_avg_charge_price")

                if avg_price is not None and sold_kwh > 0:
                    profit = (float(price_now) - float(avg_price)) * sold_kwh

                    self._persist["profit_eur"] = (
                        float(self._persist.get("profit_eur", 0.0))
                        + float(profit)
                    )

                    remaining_kwh = (
                        float(self._persist.get("trade_charged_kwh", 0.0))
                        - sold_kwh
                    )

                    remaining_kwh = max(0.0, remaining_kwh)
                    self._persist["trade_charged_kwh"] = remaining_kwh

                    if remaining_kwh <= 0:
                        self._persist["trade_charged_kwh"] = 0.0
                        self._persist["trade_avg_charge_price"] = 0.0

            adaptive_peak_active = decision.reason == "adaptive_peak_discharge"

            if decision.reason == "pv_house_load_passthrough":
                self._persist["prev_discharge_w"] = 0.0
            else:
                self._persist["prev_discharge_w"] = float(decision.discharge_w or 0.0)

            if decision.ac_mode == "input" and float(decision.charge_w or 0.0) > 0.0:
                self._persist["prev_charge_w"] = float(decision.charge_w)
            else:
                self._persist["prev_charge_w"] = 0.0

            soc_limit = self._get_soc_limit()
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
                decision.reason = "cell_voltage_cutoff_block"

            self._remember_learned_charge_power_sample(
                now,
                decision=decision,
                battery_charge_w=float(battery_charge_w),
            )
            
            strategy_intent = decision_to_strategy_intent(decision)
            
            regulation_runtime = self._get_regulation_runtime_state()

            mode_arbiter_result = self._mode_arbiter.evaluate(
                now=now,
                intent=strategy_intent,
                grid=grid_history_state,
                runtime=regulation_runtime,
                current_ac_mode=self._state(self.entities.ac_mode),
                additional_battery_discharge_w=float(additional_battery_discharge_w or 0.0),
            )
            
            regulation_power_result = self._regulation_power_controller.calculate(
                intent=strategy_intent,
                arbiter=mode_arbiter_result,
                grid=grid_history_state,
                previous_input_w=float(self._persist.get("last_set_input_w", 0.0) or 0.0),
                previous_output_w=float(self._persist.get("last_set_output_w", 0.0) or 0.0),
            )
            
            regulation_device_command = self._device_command_builder.build(
                intent=strategy_intent,
                arbiter=mode_arbiter_result,
                power=regulation_power_result,
                current_ac_mode=self._state(self.entities.ac_mode),
                last_input_limit_w=float(self._persist.get("last_set_input_w", 0.0) or 0.0),
                last_output_limit_w=float(self._persist.get("last_set_output_w", 0.0) or 0.0),
            )

            legacy_ac_mode = (
                ZENDURE_MODE_INPUT
                if decision.ac_mode == "input"
                else ZENDURE_MODE_OUTPUT
            )
            legacy_in_w = (
                float(decision.charge_w)
                if legacy_ac_mode == ZENDURE_MODE_INPUT
                else 0.0
            )
            legacy_out_w = (
                float(decision.discharge_w)
                if legacy_ac_mode == ZENDURE_MODE_OUTPUT
                else 0.0
            )

            use_regulation_v42_command = bool(
                self._persist.get("use_regulation_v42_command", False)
            )

            if use_regulation_v42_command:
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
            else:
                ac_mode = legacy_ac_mode
                in_w = legacy_in_w
                out_w = legacy_out_w
                
            self._update_regulation_runtime_state(
                now=now,
                requested_mode=str(mode_arbiter_result.requested_mode),
                resolved_mode=str(mode_arbiter_result.resolved_mode),
                active_state=str(mode_arbiter_result.active_regulation_state),
                command_skipped=bool(regulation_device_command.skipped) if use_regulation_v42_command else False,
                command_skip_reason=(
                    str(regulation_device_command.skip_reason)
                    if use_regulation_v42_command
                    else "legacy_active"
                ),
                current_ac_mode=self._state(self.entities.ac_mode),
                command_ac_mode=str(regulation_device_command.ac_mode),
                profile=profile,
                grid=grid_history_state,
            )

            is_passthrough = decision.reason == "pv_house_load_passthrough"

            if ac_mode == ZENDURE_MODE_INPUT:
                if self._persist.get("last_set_output_w", 0) != 0:
                    await self._set_output_limit(0)

            await self._set_ac_mode(ac_mode)
            await self._set_input_limit(in_w)
            await self._set_output_limit(out_w)

            is_charging = ac_mode == ZENDURE_MODE_INPUT and in_w > 0.0
            is_discharging = (
                ac_mode == ZENDURE_MODE_OUTPUT
                and out_w > 0.0
                and not is_passthrough
            )

            if is_passthrough and out_w > 0.0:
                self._persist["power_state"] = "passthrough"
            elif is_charging:
                self._persist["power_state"] = "charging"
            elif is_discharging:
                self._persist["power_state"] = "discharging"
            else:
                self._persist["power_state"] = "idle"

            if is_charging or is_discharging or (is_passthrough and out_w > 0.0):
                self._persist["next_action_time"] = now.isoformat()
            else:
                self._persist["next_action_time"] = None

            ai_status = self._map_ai_status(
                ai_mode=ai_mode,
                action=decision.action,
                reason=decision.reason,
            )

            recommendation = self._map_reco(decision.action)

            charge_strategy = self._map_charge_strategy(
                ai_mode=ai_mode,
                action=decision.action,
                reason=decision.reason,
            )

            transparency_ctx = DecisionContext(
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
                price_now=price_now,
                avg_charge_price=self._persist.get("trade_avg_charge_price"),
                expensive_threshold=float(expensive),
                very_expensive_threshold=float(very_expensive),
                profit_margin_pct=float(profit_margin_pct),
                price_points=price_points,
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
            )

            transparency_result = self._engine._with_thresholds(
                transparency_ctx,
                DecisionResult(
                    action=decision.action,
                    ac_mode=decision.ac_mode,
                    charge_w=float(decision.charge_w or 0.0),
                    discharge_w=float(decision.discharge_w or 0.0),
                    reason=decision.reason,
                    target_soc=decision.target_soc,
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
                "deficit": float(grid_import),
                "surplus": float(grid_export),
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
                "avg_charge_price": self._persist.get("trade_avg_charge_price"),
                "economic_discharge_threshold": economic_discharge_threshold,
                "effective_discharge_threshold": effective_discharge_threshold,
                "profit_eur": float(self._persist.get("profit_eur") or 0.0),
                "delta_kwh": float(delta_kwh),
                "is_grid_charge": is_grid_charge,
                "charge_source": charge_source,
                "charge_price_applied": charge_price_applied,
                "battery_ac_power_raw": battery_power,
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

                # V4.2.0 regulation execution switch / comparison
                "regulation_v42_command_enabled": bool(use_regulation_v42_command),
                "regulation_legacy_set_mode": legacy_ac_mode,
                "regulation_legacy_set_input_w": int(round(legacy_in_w, 0)),
                "regulation_legacy_set_output_w": int(round(legacy_out_w, 0)),
                "regulation_command_diff_mode": (
                    str(regulation_device_command.ac_mode) != str(legacy_ac_mode)
                ),
                "regulation_command_diff_input_w": round(
                    float(regulation_device_command.input_limit_w) - float(legacy_in_w),
                    2,
                ),
                "regulation_command_diff_output_w": round(
                    float(regulation_device_command.output_limit_w) - float(legacy_out_w),
                    2,
                ),
                "regulation_command_matches_legacy": (
                    str(regulation_device_command.ac_mode) == str(legacy_ac_mode)
                    and abs(
                        float(regulation_device_command.input_limit_w) - float(legacy_in_w)
                    ) < 1.0
                    and abs(
                        float(regulation_device_command.output_limit_w) - float(legacy_out_w)
                    ) < 1.0
                ),
                
                "ai_mode": ai_mode,
                "manual_action": manual_action,
                "decision_reason": decision.reason,
                "charge_strategy": charge_strategy,
                
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
                    float(grid_history_state.grid_now_w) * 0.6
                    + float(grid_history_state.grid_avg_short_w) * 0.4,
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
                "sf800_pv_charge_latched": bool(
                    self._persist.get("sf800_pv_charge_latched", False)
                ),
                "sf800_pv_charge_stop_counter": int(
                    self._persist.get("sf800_pv_charge_stop_counter", 0)
                ),
                "sf800_mode_arbiter_state": str(
                    self._persist.get("sf800_mode_arbiter_state", "none")
                ),
                "sf800_mode_arbiter_reason": str(
                    self._persist.get("sf800_mode_arbiter_reason", "none")
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
                "pv_charge_start_export_w": float(pv_charge_start_export_w),
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
                "learned_planning_effective_charge_power_w": float(
                    learned_charge_plan.effective_charge_power_w
                ),
                "learned_planning_effective_window_slots": int(
                    learned_charge_plan.effective_window_slots
                ),
                "learned_planning_effective_window_minutes": int(
                    learned_charge_plan.effective_window_minutes
                ),
                "learned_planning_deadline": (
                    learned_charge_plan.planning_deadline.isoformat()
                    if learned_charge_plan.planning_deadline
                    else None
                ),
                "learned_planning_deadline_reason": learned_charge_plan.deadline_reason,
                "learned_planning_optimal_charge_start": (
                    learned_charge_plan.optimal_charge_start.isoformat()
                    if learned_charge_plan.optimal_charge_start
                    else None
                ),
                "learned_planning_optimal_charge_end": (
                    learned_charge_plan.optimal_charge_end.isoformat()
                    if learned_charge_plan.optimal_charge_end
                    else None
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
                else "pv_house_load_passthrough_active"
                if self._persist.get("power_state") == "passthrough"
                else "none"
            )

            return {
                "status": STATUS_OK,
                "ai_status": ai_status,
                "recommendation": recommendation,
                "debug": "OK",
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
                    else "winter"
                    if ai_mode == AI_MODE_WINTER
                    else self._persist.get("season_mode", "winter")
                ),
                "fault_level_status": "normal",
                "price_daily_average": daily_avg_price,
                "current_peak_threshold": current_peak_threshold,
                "current_valley_threshold": current_valley_threshold,
                "economic_discharge_threshold": economic_discharge_threshold,
                "effective_discharge_threshold": effective_discharge_threshold,
                "engine_health": engine_health,
            }

        except Exception as err:
            raise UpdateFailed(str(err)) from err
