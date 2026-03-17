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
    CONF_WALLBOX_POWER_ENTITY,
    # PV-Forecast (v3.2)
    CONF_PV_FORECAST_ENTITY,
    CONF_ADDITIONAL_BATTERY_SOC_ENTITY,
    CONF_ADDITIONAL_BATTERY_CAPACITY_KWH,
    CONF_ADDITIONAL_BATTERY_MODE_ENTITY,
    CONF_ADDITIONAL_BATTERY_POWER_ENTITY,
    CONF_ADDITIONAL_BATTERY_CHARGE_MODE,
    CONF_ADDITIONAL_BATTERY_STOP_MODE,
    CONF_ADDITIONAL_BATTERY_PAUSE_MODE,
    SETTING_PV_FORECAST_ENABLED,
    SETTING_DAYTIME_CONSUMPTION_W,
    SETTING_NIGHTTIME_CONSUMPTION_W,
    DEFAULT_ADDITIONAL_BATTERY_CAPACITY_KWH,
    DEFAULT_PV_FORECAST_ENABLED,
    DEFAULT_DAYTIME_CONSUMPTION_W,
    DEFAULT_NIGHTTIME_CONSUMPTION_W,
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
    # modes
    AI_MODE_AUTOMATIC,
    AI_MODE_SUMMER,
    AI_MODE_WINTER,
    AI_MODE_MANUAL,
    MANUAL_STANDBY,
    MANUAL_CHARGE,
    MANUAL_DISCHARGE,
    # statuses
    STATUS_OK,
    STATUS_SENSOR_INVALID,
    AI_STATUS_STANDBY,
    AI_STATUS_CHARGE_SURPLUS,
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
    CONF_DEVICE_PROFILE,
    DEFAULT_DEVICE_PROFILE,
)

from .device_profiles import DEVICE_PROFILES
from .decision_engine import DecisionEngine, DecisionContext, PricePoint

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


class _HysteresisState:
    """Hysteresis-Tracker: verzögert ON- und OFF-Übergänge.

    delay_on_s  – Signal muss >= threshold für diese Dauer anliegen, bevor active=True.
    delay_off_s – Signal muss < threshold für diese Dauer anliegen, bevor active=False.
    threshold   – Aktivierungsschwelle in W.
    """

    def __init__(self, delay_on_s: float, delay_off_s: float, threshold: float = 80.0) -> None:
        self.delay_on_s = delay_on_s
        self.delay_off_s = delay_off_s
        self.threshold = threshold
        self.active = False
        self._pending_since: datetime | None = None

    def update(self, value: float, now: datetime) -> bool:
        """Wert einspeisen, hysterese-gefilterten Zustand zurückgeben."""
        above = value >= self.threshold
        if self.active:
            if not above:
                if self._pending_since is None:
                    self._pending_since = now
                elif (now - self._pending_since).total_seconds() >= self.delay_off_s:
                    self.active = False
                    self._pending_since = None
            else:
                self._pending_since = None
        else:
            if above:
                if self._pending_since is None:
                    self._pending_since = now
                elif (now - self._pending_since).total_seconds() >= self.delay_on_s:
                    self.active = True
                    self._pending_since = None
            else:
                self._pending_since = None
        return self.active


@dataclass
class SelectedEntities:
    soc: str
    pv: str
    price_export: str | None
    price_now: str | None
    ac_mode: str
    input_limit: str
    output_limit: str
    battery_ac_power: str
    additional_battery_charge: str | None
    additional_battery_discharge: str | None
    wallbox_power: str | None

    soc_limit: str | None

    grid_mode: str
    grid_power: str | None
    grid_import: str | None
    grid_export: str | None

    # PV-Forecast-basierte Nachtladung (v3.2)
    pv_forecast: str | None
    additional_battery_soc: str | None
    additional_battery_mode: str | None    # input_select für BYD-Steuerung (optional)
    additional_battery_power: str | None   # input_number für BYD-Leistung (optional)


class ZendureSmartFlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry

        # --- Device profile selection ---
        self.device_profile_key = (
            entry.options.get(CONF_DEVICE_PROFILE)
            or entry.data.get(CONF_DEVICE_PROFILE)
            or DEFAULT_DEVICE_PROFILE
        )

        self._device_profile_cfg = DEVICE_PROFILES.get(
            self.device_profile_key,
            DEVICE_PROFILES[DEFAULT_DEVICE_PROFILE],
        )

        # runtime settings mirror of entry.options (used by number entities)
        self.runtime_settings: dict[str, float] = dict(entry.options)

        self.entities = SelectedEntities(
            soc=str(entry.data[CONF_SOC_ENTITY]),
            pv=str(entry.data[CONF_PV_ENTITY]),
            battery_ac_power=str(
                entry.options.get(CONF_BATTERY_AC_POWER_ENTITY)
                or entry.data.get(CONF_BATTERY_AC_POWER_ENTITY, "")
            ),
            additional_battery_charge=entry.data.get(CONF_ADDITIONAL_BATTERY_CHARGE_ENTITY),
            additional_battery_discharge=entry.data.get(CONF_ADDITIONAL_BATTERY_DISCHARGE_ENTITY),
            wallbox_power=entry.data.get(CONF_WALLBOX_POWER_ENTITY),
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
            # PV-Forecast (v3.2)
            pv_forecast=entry.data.get(CONF_PV_FORECAST_ENTITY),
            additional_battery_soc=entry.data.get(CONF_ADDITIONAL_BATTERY_SOC_ENTITY),
            additional_battery_mode=entry.data.get(CONF_ADDITIONAL_BATTERY_MODE_ENTITY),
            additional_battery_power=entry.data.get(CONF_ADDITIONAL_BATTERY_POWER_ENTITY),
        )

        # BYD-Steuerungs-Modus-Strings (konfigurierbar, Defaults: SMA-Modbus-Werte)
        self._byd_charge_mode: str = entry.data.get(
            CONF_ADDITIONAL_BATTERY_CHARGE_MODE, "Akku schnell laden"
        )
        self._byd_stop_mode: str = entry.data.get(
            CONF_ADDITIONAL_BATTERY_STOP_MODE, "Akku automatisch"
        )
        self._byd_pause_mode: str = entry.data.get(
            CONF_ADDITIONAL_BATTERY_PAUSE_MODE, "Akku Pause"
        )
        # Zustandsmerker: BYD aktuell durch SmartFlow-Nachtladung gesteuert?
        self._byd_night_active: bool = False
        # Zustandsmerker: BYD-Entladung zum Schutz der Überbrückungsenergie pausiert?
        self._byd_discharge_paused: bool = False

        self.runtime_mode: dict[str, Any] = {
            "ai_mode": AI_MODE_AUTOMATIC,
            "manual_action": MANUAL_STANDBY,
        }

        self._engine = DecisionEngine()

        # Hysterese-Tracker für BYD und Wallbox Koordination
        self._hys_byd_charge    = _HysteresisState(delay_on_s=15, delay_off_s=45, threshold=80.0)
        self._hys_byd_discharge = _HysteresisState(delay_on_s=15, delay_off_s=300, threshold=80.0)
        self._hys_wallbox_pv    = _HysteresisState(delay_on_s=25, delay_off_s=45, threshold=500.0)
        self._hys_wallbox_grid  = _HysteresisState(delay_on_s=5,  delay_off_s=45, threshold=7000.0)

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
            "power_state": "idle",  # idle|charging|discharging
            "emergency_active": False,

            # analytics
            "trade_avg_charge_price": None,
            "trade_charged_kwh": 0.0,
            "prev_soc": None,

            "avg_charge_price": None,
            "charged_kwh": 0.0,
            "discharged_kwh": 0.0,
            "profit_eur": 0.0,
            "last_ts": None,

            # season detection (Option A)
            "season_mode": "winter",  # winter|summer
            "season_counter": 0,

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

    def _parse_price_points(self, now) -> list[PricePoint]:
        """
        Universal price parser (production hardened).

        Supports:
        - Tibber (attributes.data[])
        - Octopus (attributes.rates[])
        - Octopus Germany (unit_rate_forecast[])
        - EPEX style exports
        - Generic 15min APIs

        Handles:
        - Mixed timezones (UTC / CET)
        - Broken Octopus slots (end <= start)
        - DST edge cases
        """

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
                return dt_util.replace(dt, tzinfo=tz)
            return dt.astimezone(tz)

        now = normalize(now)

        out: list[PricePoint] = []

        for item in raw:
            if not isinstance(item, dict):
                continue

            # Octopus Germany unit_rate_forecast format
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

                price = float(cents) / 100.0  # cents -> €
                out.append(PricePoint(start=t_start, end=t_end, price=price))
                continue

            # Generic / Tibber / Octopus "rates" format
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
        """
        Option A: Season detection stays here.
        Very slow moving anti-flip counter.
        """
        season = self._persist.get("season_mode", "winter")
        counter = int(self._persist.get("season_counter", 0))

        summer_signal = (pv_w > 800.0 and export_w > 300.0)
        winter_signal = (pv_w < 400.0 and export_w < 100.0)

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
        return season

    def _map_ai_status(self, ai_mode: str, action: str, reason: str) -> str:
        if ai_mode == AI_MODE_MANUAL:
            return AI_STATUS_MANUAL
        if action == "emergency":
            return AI_STATUS_EMERGENCY_CHARGE
        if action == "charge":
            return AI_STATUS_CHARGE_SURPLUS
        if action == "discharge":
            if "very_expensive" in reason or "adaptive_peak" in reason:
                return AI_STATUS_VERY_EXPENSIVE_FORCE
            if "price" in reason:
                return AI_STATUS_EXPENSIVE_DISCHARGE
            return AI_STATUS_COVER_DEFICIT
        return AI_STATUS_STANDBY

    def _map_reco(self, action: str) -> str:
        if action == "charge":
            return RECO_CHARGE
        if action == "discharge":
            return RECO_DISCHARGE
        if action == "emergency":
            return RECO_EMERGENCY
        return RECO_STANDBY

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

            # -----------------------------
            # Battery capacity
            # -----------------------------
            battery_capacity_kwh = self._get_battery_capacity()

            # -----------------------------
            # Energy delta calculation
            # -----------------------------
            prev_soc = self._persist.get("prev_soc")
            delta_kwh = 0.0

            if prev_soc is not None and battery_capacity_kwh > 0:
                soc_delta_pct = soc - prev_soc
                delta_kwh = battery_capacity_kwh * (soc_delta_pct / 100.0)

            self._persist["prev_soc"] = soc

            profile = self._device_profile_cfg

            soc_min = self._get_setting(
                SETTING_SOC_MIN,
                profile.get("SOC_MIN", DEFAULT_SOC_MIN),
            )
            soc_max = self._get_setting(
                SETTING_SOC_MAX,
                profile.get("SOC_MAX", DEFAULT_SOC_MAX),
            )

            max_charge = self._get_setting(
                SETTING_MAX_CHARGE,
                profile.get("MAX_CHARGE_W", DEFAULT_MAX_CHARGE),
            )
            max_discharge = self._get_setting(
                SETTING_MAX_DISCHARGE,
                profile.get("MAX_DISCHARGE_W", DEFAULT_MAX_DISCHARGE),
            )

            # Clamp against profile hard limits
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

            ai_mode = str(self.runtime_mode.get("ai_mode", AI_MODE_AUTOMATIC))
            manual_action = str(self.runtime_mode.get("manual_action", MANUAL_STANDBY))

            grid_import, grid_export = self._get_grid()
            if grid_import is None or grid_export is None:
                grid_import = 0.0
                grid_export = 0.0

            # --- Grid Epsilon Filter (Messfehler-Filterung) ---
            grid_import = float(grid_import)
            grid_export = float(grid_export)
            GRID_EPSILON = 120.0
            # Beide aktiv → nur der größere zählt
            if grid_import > GRID_EPSILON and grid_export > GRID_EPSILON:
                if grid_import >= grid_export:
                    grid_export = 0.0
                else:
                    grid_import = 0.0
            # Kleine Messfehler entfernen
            if grid_import < GRID_EPSILON:
                grid_import = 0.0
            if grid_export < GRID_EPSILON:
                grid_export = 0.0

            price_now = self._get_price_now()
            price_points = self._parse_price_points(now)

            # --- BYD + Wallbox Koordination (Hysterese-gefiltert) ---
            byd_charge_raw = _to_float(
                self._state(self.entities.additional_battery_charge), 0.0,
            )
            byd_charge_raw = float(byd_charge_raw or 0.0)

            byd_discharge_raw = _to_float(
                self._state(self.entities.additional_battery_discharge), 0.0,
            )
            byd_discharge_raw = float(byd_discharge_raw or 0.0)

            wallbox_raw = _to_float(
                self._state(self.entities.wallbox_power), 0.0,
            )
            wallbox_raw = float(wallbox_raw or 0.0)

            # Hysterese anwenden
            byd_charge_active    = self._hys_byd_charge.update(byd_charge_raw, now)
            byd_discharge_active = self._hys_byd_discharge.update(byd_discharge_raw, now)
            wallbox_pv_active    = self._hys_wallbox_pv.update(
                wallbox_raw if wallbox_raw < 7000.0 else 0.0, now
            )
            wallbox_grid_active  = self._hys_wallbox_grid.update(wallbox_raw, now)

            # Hysterese-gefilterte Werte für DecisionContext
            additional_battery_charge_w    = byd_charge_raw    if byd_charge_active    else 0.0
            additional_battery_discharge_w = byd_discharge_raw if byd_discharge_active else 0.0
            wallbox_active_w               = wallbox_raw if (wallbox_pv_active or wallbox_grid_active) else 0.0

            # --- PV-Forecast + BYD SoC (v3.2) ---
            pv_forecast_enabled = float(
                self.runtime_settings.get(SETTING_PV_FORECAST_ENABLED, DEFAULT_PV_FORECAST_ENABLED)
            ) >= 1.0

            pv_forecast_kwh = -1.0
            if pv_forecast_enabled and self.entities.pv_forecast:
                raw_pv = self._state(self.entities.pv_forecast)
                val_pv = _to_float(raw_pv, None)
                if val_pv is not None:
                    pv_forecast_kwh = float(val_pv)

            additional_battery_soc_val = -1.0
            if self.entities.additional_battery_soc:
                raw_byd_soc = self._state(self.entities.additional_battery_soc)
                val_byd_soc = _to_float(raw_byd_soc, None)
                if val_byd_soc is not None:
                    additional_battery_soc_val = float(val_byd_soc)

            additional_battery_capacity = float(
                self.entry.data.get(
                    CONF_ADDITIONAL_BATTERY_CAPACITY_KWH, DEFAULT_ADDITIONAL_BATTERY_CAPACITY_KWH
                )
            )
            daytime_consumption_w = float(
                self.runtime_settings.get(SETTING_DAYTIME_CONSUMPTION_W, DEFAULT_DAYTIME_CONSUMPTION_W)
            )
            nighttime_consumption_w = float(
                self.runtime_settings.get(SETTING_NIGHTTIME_CONSUMPTION_W, DEFAULT_NIGHTTIME_CONSUMPTION_W)
            )
            # Abgeleitete kWh-Werte aus den W-Einstellungen
            pv_self_consumption_kwh = daytime_consumption_w / 1000.0 * 10.0   # 08–18 Uhr = 10h
            bridge_kwh              = nighttime_consumption_w / 1000.0 * 3.0   # 05–08 Uhr = 3h
            daily_consumption_kwh   = (nighttime_consumption_w / 1000.0 * 14.0
                                       + daytime_consumption_w / 1000.0 * 10.0)

            # --- Daily price average ---
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

            very_cheap_price = self.runtime_settings.get("very_cheap_price", None)
            if very_cheap_price is not None:
                try:
                    very_cheap_price = float(very_cheap_price)
                except Exception:
                    very_cheap_price = None

            current_peak_threshold = None
            if daily_avg_price is not None:
                current_peak_threshold = max(
                    daily_avg_price * peak_factor,
                    daily_avg_price + 0.03,
                )

            current_valley_threshold = None
            if daily_avg_price is not None:
                current_valley_threshold = daily_avg_price * valley_factor

            # --- Engine health ---
            engine_health = "ok"
            if not price_points:
                engine_health = "no_price_data"
            elif price_now is None:
                engine_health = "no_current_price"

            # -----------------------------
            # House load estimate
            # -----------------------------
            battery_raw = self._state(self.entities.battery_ac_power)
            battery_power = _to_float(battery_raw, 0.0)
            battery_power = float(battery_power or 0.0)

            # Nur Entladung berücksichtigen
            battery_discharge_w = max(0.0, battery_power)

            house_load = max(
                0.0,
                float(grid_import)
                + float(pv_w)
                + float(battery_discharge_w)
                - float(grid_export)
            )

            # -----------------------------
            # Season detection
            # -----------------------------
            season = self._season_detection(
                pv_w=pv_w,
                export_w=float(grid_export),
            )

            # -----------------------------
            # Engine Context
            # -----------------------------

            # Nachtverbrauch: Hauslaststunden bis 05:00 Uhr (GO-Günstigfenster)
            # Tagsüber ist nighttime_h=0 → nighttime_kwh=0 → kein Einfluss auf Tagsbetrieb
            _nighttime_h = max(0.0, 5.0 - now.hour - now.minute / 60.0)
            _nighttime_kwh = nighttime_consumption_w / 1000.0 * _nighttime_h

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
                wallbox_active_w=wallbox_active_w,
                # PV-Forecast (v3.2)
                pv_forecast_kwh=pv_forecast_kwh,
                additional_battery_soc=additional_battery_soc_val,
                additional_battery_capacity_kwh=additional_battery_capacity,
                daily_consumption_kwh=daily_consumption_kwh,
                bridge_kwh=bridge_kwh,
                nighttime_kwh=_nighttime_kwh,
                pv_self_consumption_kwh=pv_self_consumption_kwh,
            )

            decision = self._engine.evaluate(ctx)
            # Decision reason merken für _manage_byd_night_charge (Fix 3)
            self._last_decision_reason = decision.reason if decision else "idle"

            # --- BYD Nachtladung (v3.2) ---
            if pv_forecast_enabled:
                await self._manage_byd_night_charge(ctx, now)

            # -----------------------------
            # Profit Tracking – Charging
            # -----------------------------
            if delta_kwh > 0 and price_now is not None:
                charged_kwh = self._persist.get("trade_charged_kwh", 0.0)
                avg_price = self._persist.get("trade_avg_charge_price")

                new_total_kwh = charged_kwh + delta_kwh

                if avg_price is None:
                    new_avg = price_now
                else:
                    new_avg = (
                        (avg_price * charged_kwh + price_now * delta_kwh)
                        / new_total_kwh
                    )

                self._persist["trade_charged_kwh"] = new_total_kwh
                self._persist["trade_avg_charge_price"] = new_avg

            # -----------------------------
            # Profit Tracking – Discharging
            # -----------------------------
            if (
                delta_kwh < 0
                and price_now is not None
                and decision.ac_mode == "output"
                and float(decision.discharge_w or 0.0) > 0.0
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
                        self._persist["trade_avg_charge_price"] = None

            adaptive_peak_active = decision.reason == "adaptive_peak_discharge"

            # Persist previous discharge for delta controller
            self._persist["prev_discharge_w"] = float(decision.discharge_w or 0.0)

            # Charge memory for delta controller
            if decision.ac_mode == "input" and float(decision.charge_w or 0.0) > 0.0:
                self._persist["prev_charge_w"] = float(decision.charge_w)
            else:
                self._persist["prev_charge_w"] = 0.0

            # -----------------------------
            # BMS SoC limit (directional block)
            # -----------------------------
            soc_limit = self._get_soc_limit()
            if soc_limit == 1 and decision.ac_mode == "input" and float(decision.charge_w or 0.0) > 0:
                decision.charge_w = 0.0
                decision.action = "idle"
                decision.reason = "soc_limit_upper"
            elif soc_limit == 2 and decision.ac_mode == "output" and float(decision.discharge_w or 0.0) > 0:
                decision.discharge_w = 0.0
                decision.action = "idle"
                decision.reason = "soc_limit_lower"

            # Enforce soc_min on discharge
            if decision.ac_mode == "output" and soc <= float(soc_min):
                decision.discharge_w = 0.0
                decision.action = "idle"
                decision.reason = "soc_min_enforced"

            # -----------------------------
            # Apply setpoints
            # -----------------------------
            ac_mode = (
                ZENDURE_MODE_INPUT
                if decision.ac_mode == "input"
                else ZENDURE_MODE_OUTPUT
            )
            in_w = float(decision.charge_w) if ac_mode == ZENDURE_MODE_INPUT else 0.0
            out_w = float(decision.discharge_w) if ac_mode == ZENDURE_MODE_OUTPUT else 0.0

            # Zendure requires output_limit=0 before AC input
            if ac_mode == ZENDURE_MODE_INPUT:
                if self._persist.get("last_set_output_w", 0) != 0:
                    await self._set_output_limit(0)

            await self._set_ac_mode(ac_mode)

            await self._set_input_limit(in_w)
            await self._set_output_limit(out_w)

            self._persist["last_set_output_w"] = out_w

            is_charging = ac_mode == ZENDURE_MODE_INPUT and in_w > 0.0
            is_discharging = ac_mode == ZENDURE_MODE_OUTPUT and out_w > 0.0

            if is_charging:
                self._persist["power_state"] = "charging"
            elif is_discharging:
                self._persist["power_state"] = "discharging"
            else:
                self._persist["power_state"] = "idle"

            if is_charging or is_discharging:
                self._persist["next_action_time"] = now.isoformat()
            else:
                self._persist["next_action_time"] = None

            # -----------------------------
            # AI status + recommendation
            # -----------------------------
            ai_status = self._map_ai_status(
                ai_mode=ai_mode,
                action=decision.action,
                reason=decision.reason,
            )
            recommendation = self._map_reco(decision.action)

            # -----------------------------
            # Persist + return payload
            # -----------------------------
            self._persist["debug"] = "OK"
            self._persist["last_ts"] = now.isoformat()

            await self._save()

            details = {
                "soc": soc,
                "pv_w": pv_w,
                "deficit": float(grid_import),
                "surplus": float(grid_export),
                "house_load": int(round(house_load, 0)),
                "price_now": price_now,
                "avg_charge_price": self._persist.get("trade_avg_charge_price"),
                "profit_eur": float(self._persist.get("profit_eur") or 0.0),
                "max_charge": max_charge,
                "max_discharge": max_discharge,
                "set_mode": ac_mode,
                "set_input_w": int(round(in_w, 0)),
                "set_output_w": int(round(out_w, 0)),
                "ai_mode": ai_mode,
                "manual_action": manual_action,
                "decision_reason": decision.reason,
                "adaptive_peak_active": adaptive_peak_active,
                "device_profile": self.device_profile_key,
                "profile_max_input_w": profile_max_in,
                "profile_max_output_w": profile_max_out,
                "soc_limit": soc_limit,
                "additional_battery_charge_w": int(round(additional_battery_charge_w, 0)),
                "additional_battery_discharge_w": int(round(additional_battery_discharge_w, 0)),
                "wallbox_active_w": int(round(wallbox_active_w, 0)),
                "byd_charge_active": byd_charge_active,
                "byd_discharge_active": byd_discharge_active,
                "wallbox_pv_active": wallbox_pv_active,
                "wallbox_grid_active": wallbox_grid_active,
                "soc_limit_status": (
                    "not_configured"
                    if soc_limit is None
                    else "no_limit"
                    if soc_limit == 0
                    else "upper_limit_active"
                    if soc_limit == 1
                    else "lower_limit_active"
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
                else "none"
            )

            # Nachtlade-Plan für Sensor-Ausgabe aufbereiten
            _np = self._persist.get("night_plan", {})

            # Verfügbare Energie Gesamt (Zendure + BYD) für Dashboard-Sensor
            _z_usable_rt = max(0.0, (ctx.soc - ctx.soc_min) / 100.0 * ctx.battery_capacity_kwh)
            _byd_usable_rt = (
                max(0.0, ctx.additional_battery_soc / 100.0 * ctx.additional_battery_capacity_kwh)
                if ctx.additional_battery_soc >= 0 and ctx.additional_battery_capacity_kwh > 0
                else 0.0
            )
            total_available_kwh = round(_z_usable_rt + _byd_usable_rt, 3)

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
                "engine_health": engine_health,
                # Nachtladung Transparenz-Sensoren (v3.2)
                "night_charge_status": _np.get("status", "inactive"),
                "night_charge_pv_kwh": _np.get("pv_kwh"),
                "night_charge_byd_target_soc": _np.get("byd_ziel_soc"),
                "night_charge_byd_kwh": _np.get("byd_laden_kwh"),
                "night_charge_zendure_target_soc": _np.get("zendure_ziel_soc"),
                "night_charge_zendure_kwh": _np.get("zendure_laden_kwh"),
                "total_available_kwh": total_available_kwh,
                "night_plan": _np,
            }

        except Exception as err:
            raise UpdateFailed(str(err)) from err

    # ==========================================================
    # PV-Forecast-basierte BYD-Nachtladung (v3.2)
    # ==========================================================

    async def _manage_byd_night_charge(
        self, ctx: DecisionContext, now: datetime
    ) -> None:
        """Steuert BYD-Ladung während des GO-Günstigfensters (00:00–05:00).

        Wird bei jedem Coordinator-Zyklus (10s) aufgerufen wenn Feature aktiv.
        Schreibt nur bei Zustandswechsel (Modus-Änderung) auf HA-Entitäten.
        """
        # Außerhalb des Nacht-Fensters: Sicherheitsstopp falls noch aktiv + Pause aufheben
        if not (0 <= now.hour < 5):
            self._persist.pop("night_soc_snapshot", None)  # Für nächste Nacht zurücksetzen
            if self._byd_night_active:
                _LOGGER.info("SmartFlow Nachtladen: Fenster 05:00 überschritten – BYD → %s", self._byd_stop_mode)
                await self._byd_set_mode(self._byd_stop_mode)
                self._byd_night_active = False
            if self._byd_discharge_paused:
                _LOGGER.info("SmartFlow Nachtladen: 05:00 – Entladepause aufheben → %s", self._byd_stop_mode)
                await self._byd_set_mode(self._byd_stop_mode)
                self._byd_discharge_paused = False
            return

        # Ohne gültigen PV-Forecast: keine Aktion
        if ctx.pv_forecast_kwh < 0:
            return

        # Ohne konfigurierte BYD-Steuerentität: keine Aktion
        if not self.entities.additional_battery_mode:
            return

        # BYD-Ladebedarf berechnen (identische Formel wie _calc_pv_aware_zendure_target_soc)
        z_usable = max(0.0, (ctx.soc - ctx.soc_min) / 100.0 * ctx.battery_capacity_kwh)
        z_capacity = ctx.battery_capacity_kwh * (ctx.soc_max - ctx.soc_min) / 100.0
        byd_usable = 0.0
        if ctx.additional_battery_soc >= 0 and ctx.additional_battery_capacity_kwh > 0:
            byd_usable = max(0.0, ctx.additional_battery_soc / 100.0 * ctx.additional_battery_capacity_kwh)

        total_avail = z_usable + byd_usable
        total_max = z_capacity + ctx.additional_battery_capacity_kwh
        # Haushaltslast abziehen: PV-Anteil, der direkt an den Verbraucher geht (nicht in Batterie)
        _pv_for_battery = max(0.0, ctx.pv_forecast_kwh - ctx.pv_self_consumption_kwh)
        target_total = min(
            total_max,
            ctx.bridge_kwh + ctx.nighttime_kwh + max(0.0, ctx.daily_consumption_kwh - _pv_for_battery),
        )
        charge_needed = max(0.0, target_total - total_avail)
        z_charge = min(max(0.0, z_capacity - z_usable), charge_needed)
        # Fix 3: z_charge nur abziehen wenn SmartFlow Zendure wirklich lädt
        _ZENDURE_CHARGING_REASONS = frozenset({
            "night_charge_go_window", "planning_latest_start",
            "valley_boost_charge", "manual_charge",
            "emergency_latched_charge", "pv_surplus_charge",
        })
        zendure_is_charging = getattr(self, "_last_decision_reason", "idle") in _ZENDURE_CHARGING_REASONS
        effective_z_charge = z_charge if zendure_is_charging else 0.0
        byd_charge = max(0.0, charge_needed - effective_z_charge)

        current_byd_soc = ctx.additional_battery_soc if ctx.additional_battery_soc >= 0 else 0.0

        # Snapshot SoC zu Fensterbeginn (einmal pro Nacht, beim ersten Aufruf im GO-Fenster)
        if "night_soc_snapshot" not in self._persist:
            self._persist["night_soc_snapshot"] = {
                "byd": current_byd_soc,
                "zendure": ctx.soc,
            }
        _snap = self._persist["night_soc_snapshot"]
        byd_actual_kwh = (
            max(0.0, (current_byd_soc - _snap["byd"]) / 100.0 * ctx.additional_battery_capacity_kwh)
            if ctx.additional_battery_capacity_kwh > 0 else 0.0
        )
        zendure_actual_kwh = max(0.0, (ctx.soc - _snap["zendure"]) / 100.0 * ctx.battery_capacity_kwh)

        # BYD Ziel-SoC berechnen
        byd_target_soc = current_byd_soc
        if ctx.additional_battery_capacity_kwh > 0:
            byd_target_soc = min(
                100.0,
                current_byd_soc + byd_charge / ctx.additional_battery_capacity_kwh * 100.0,
            )

        # Zendure Ziel-SoC berechnen (für Dashboard-Transparenz)
        z_target_soc = ctx.soc
        if ctx.battery_capacity_kwh > 0:
            z_target_soc = min(ctx.soc_max, ctx.soc + z_charge / ctx.battery_capacity_kwh * 100.0)

        # Aktuellen BYD-Modus lesen
        current_mode = self._state(self.entities.additional_battery_mode)

        # Status und Modus ermitteln (no-need-Zweig mit Entladeschutz)
        if current_byd_soc >= byd_target_soc - 0.5 or byd_charge < 0.5:
            # Ziel erreicht oder kein Ladebedarf
            was_night_active = self._byd_night_active   # merken VOR Reset (Fix 2)
            self._byd_night_active = False

            if byd_usable <= ctx.bridge_kwh:
                # Überbrückungsenergie schützen: BYD einfrieren
                if current_mode != self._byd_pause_mode:
                    _LOGGER.info(
                        "SmartFlow Nachtladen: BYD %.2f kWh ≤ Brücke %.2f kWh → %s",
                        byd_usable, ctx.bridge_kwh, self._byd_pause_mode,
                    )
                    await self._byd_set_mode(self._byd_pause_mode)
                    self._byd_discharge_paused = True
                night_status = "discharge_paused"
            else:
                # BYD hat mehr als Bridge → Entladung erlaubt
                # Nur zurücksetzen wenn WIR den Modus gesetzt haben (Fix 2)
                if current_mode in (self._byd_charge_mode, self._byd_pause_mode):
                    if was_night_active or self._byd_discharge_paused:
                        _LOGGER.info(
                            "SmartFlow Nachtladen: BYD Ziel %.0f%% erreicht (aktuell %.0f%%) → %s",
                            byd_target_soc, current_byd_soc, self._byd_stop_mode,
                        )
                        await self._byd_set_mode(self._byd_stop_mode)
                        self._byd_discharge_paused = False
                night_status = "no_need" if byd_charge < 0.5 else "goal_reached"
        else:
            night_status = "charging"

        # Nachtlade-Plan persistieren (überlebt HA-Neustart, sichtbar am nächsten Morgen)
        night_plan: dict[str, Any] = {
            "status": night_status,
            "pv_kwh": round(ctx.pv_forecast_kwh, 2),
            "byd_ziel_soc": round(byd_target_soc, 1),
            "byd_laden_kwh": round(byd_actual_kwh, 2),
            "byd_leistung_w": self._persist.get("night_plan", {}).get("byd_leistung_w"),
            "zendure_ziel_soc": round(z_target_soc, 1),
            "zendure_laden_kwh": round(zendure_actual_kwh, 2),
            "timestamp": now.strftime("%H:%M %d.%m.%Y"),
        }
        self._persist["night_plan"] = night_plan

        if night_status == "charging":
            # Laden starten/fortsetzen
            if current_mode != self._byd_charge_mode:
                remaining_h = max(0.25, 5.0 - now.hour - now.minute / 60.0)
                byd_power = int(
                    min(3600, max(500, round(byd_charge / remaining_h * 1000 / 100) * 100))
                )
                night_plan["byd_leistung_w"] = byd_power  # Beim Start setzen
                self._persist["night_plan"] = night_plan
                _LOGGER.info(
                    "SmartFlow Nachtladen: BYD %.1fkWh laden → Ziel %.0f%%, %dW (%s bleibt)",
                    byd_charge, byd_target_soc, byd_power,
                    f"{remaining_h:.1f}h",
                )
                if self.entities.additional_battery_power:
                    await self.hass.services.async_call(
                        "input_number",
                        "set_value",
                        {
                            "entity_id": self.entities.additional_battery_power,
                            "value": byd_power,
                        },
                    )
                await self._byd_set_mode(self._byd_charge_mode)
            self._byd_night_active = True

    async def _byd_set_mode(self, mode: str) -> None:
        """Schreibt BYD-Steuermodus auf input_select (nur wenn Entität konfiguriert)."""
        if not self.entities.additional_battery_mode:
            return
        await self.hass.services.async_call(
            "input_select",
            "select_option",
            {
                "entity_id": self.entities.additional_battery_mode,
                "option": mode,
            },
        )
