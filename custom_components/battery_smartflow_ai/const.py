from __future__ import annotations

try:
    from homeassistant.const import Platform
except ModuleNotFoundError as err:
    if err.name is None or not err.name.startswith("homeassistant"):
        raise

    from enum import StrEnum

    class Platform(StrEnum):
        """Minimal platform names for standalone core imports."""

        SENSOR = "sensor"
        NUMBER = "number"
        SELECT = "select"

# ==================================================
# Integration meta
# ==================================================
DOMAIN = "battery_smartflow_ai"

INTEGRATION_NAME = "Battery SmartFlow AI"

VIRTUAL_DEVICE_MODELS = {
    "de": "Virtuelles Gerät",
    "en": "Virtual device",
    "fr": "Appareil virtuel",
    "nl": "Virtueel apparaat",
}


def virtual_device_model(language: str | None) -> str:
    """Return the short virtual-device label for the HA backend language."""
    language_code = (language or "en").replace("_", "-").split("-", 1)[0]
    return VIRTUAL_DEVICE_MODELS.get(language_code, VIRTUAL_DEVICE_MODELS["en"])


INTEGRATION_MANUFACTURER = "PalmManiac"
INTEGRATION_MODEL = "Home Assistant Integration"
INTEGRATION_VERSION = "5.0.0.dev16"

# V5 native Zendure discovery is observation-only in the first development
# build. The App Token is account discovery material and must never be copied
# to entity states, logs or diagnostics.
CONF_NATIVE_ZENDURE_APP_TOKEN = "native_zendure_app_token"
CONF_NATIVE_ZENDURE_SELECTED_DEVICE = "native_zendure_selected_device"
CONF_NATIVE_ZENDURE_CONTROL_ENABLED = "native_zendure_control_enabled"

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
]

# ==================================================
# Config Flow – required/optional entities
# ==================================================
CONF_SOC_ENTITY = "soc_entity"
CONF_PV_ENTITY = "pv_entity"
CONF_NATIVE_PV_ENTITY = "native_pv_entity"

CONF_SOC_LIMIT_ENTITY = "soc_limit_entity"

# Preis ist optional (Sommer/PV-only Nutzer)
CONF_PRICE_EXPORT_ENTITY = "price_export_entity"  # Tibber Export (attributes.data)
CONF_PRICE_NOW_ENTITY = "price_now_entity"        # direct price sensor (currency/kWh)
CONF_DYNAMIC_FEED_IN_PRICE_ENTITY = "dynamic_feed_in_price_entity"

CONF_ADDITIONAL_BATTERY_CHARGE_ENTITY = "additional_battery_charge_entity"
CONF_ADDITIONAL_BATTERY_DISCHARGE_ENTITY = "additional_battery_discharge_entity"

# V4.0.0 optionale PV-Forecast-Sensoren (zuerst Solcast)
CONF_PV_FORECAST_TODAY_ENTITY = "pv_forecast_today_entity"
CONF_PV_FORECAST_TOMORROW_ENTITY = "pv_forecast_tomorrow_entity"

# Zendure Steuer-Entitäten
CONF_AC_MODE_ENTITY = "ac_mode_entity"            # select input/output
CONF_INPUT_LIMIT_ENTITY = "input_limit_entity"    # number W
CONF_OUTPUT_LIMIT_ENTITY = "output_limit_entity"  # number W

# Grid Setup (empfohlen, weil wir daraus den Hausverbrauch intern berechnen)
CONF_GRID_MODE = "grid_mode"
CONF_GRID_POWER_ENTITY = "grid_power_entity"      # +import / -export
CONF_GRID_IMPORT_ENTITY = "grid_import_entity"    # import W
CONF_GRID_EXPORT_ENTITY = "grid_export_entity"    # export W

# --- Config entry keys ---
CONF_PACK_CAPACITY_KWH = "pack_capacity_kwh"
CONF_BATTERY_AC_POWER_ENTITY = "battery_ac_power_entity"

# --- New for V3.2.0 ---
CONF_INSTALLED_PV_WP = "installed_pv_wp"
CONF_PROFILE_OVERRIDES = "profile_overrides"

# --- New for V3.5.0 ---
CONF_EXPERT_MODE_ENABLED = "expert_mode_enabled"
CONF_CELL_VOLTAGE_PROTECTION_ENABLED = "cell_voltage_protection_enabled"

CONF_LOWEST_CELL_VOLTAGE_PACK_1 = "lowest_cell_voltage_pack_1"
CONF_LOWEST_CELL_VOLTAGE_PACK_2 = "lowest_cell_voltage_pack_2"
CONF_LOWEST_CELL_VOLTAGE_PACK_3 = "lowest_cell_voltage_pack_3"
CONF_LOWEST_CELL_VOLTAGE_PACK_4 = "lowest_cell_voltage_pack_4"
CONF_LOWEST_CELL_VOLTAGE_PACK_5 = "lowest_cell_voltage_pack_5"
CONF_LOWEST_CELL_VOLTAGE_PACK_6 = "lowest_cell_voltage_pack_6"

LOWEST_CELL_VOLTAGE_CONFIG_KEYS = [
    CONF_LOWEST_CELL_VOLTAGE_PACK_1,
    CONF_LOWEST_CELL_VOLTAGE_PACK_2,
    CONF_LOWEST_CELL_VOLTAGE_PACK_3,
    CONF_LOWEST_CELL_VOLTAGE_PACK_4,
    CONF_LOWEST_CELL_VOLTAGE_PACK_5,
    CONF_LOWEST_CELL_VOLTAGE_PACK_6,
]

CONF_OFFGRID_POWER_ENTITY = "offgrid_power_entity"
CONF_OFFGRID_MODE_ENTITY = "offgrid_mode_entity"

CONF_FEED_IN_TARIFF = "feed_in_tariff"

# --- Helper constants for dynamic GUI profile override entities ---
PROFILE_OVERRIDE_PREFIX = "profile_override_"

# --- Runtime settings ---
SETTING_BATTERY_PACKS = "battery_packs"

SETTING_VALLEY_FACTOR = "valley_factor"
SETTING_VERY_CHEAP_PRICE = "very_cheap_price"

# --- New runtime settings for V3.5.0 ---
SETTING_CELL_VOLTAGE_WARNING = "cell_voltage_warning"
SETTING_CELL_VOLTAGE_CUTOFF = "cell_voltage_cutoff"
SETTING_CELL_VOLTAGE_RESUME = "cell_voltage_resume"

SETTING_PV_CHARGE_START_EXPORT_W = "pv_charge_start_export_w"

SETTING_FORECAST_BASE_LOAD = "forecast_base_load"

SETTING_LEARNED_PLANNING_ENABLED = "learned_planning_enabled"

# Default
DEFAULT_PACK_CAPACITY_KWH = 2.88
DEFAULT_BATTERY_PACKS = 1

DEFAULT_VALLEY_FACTOR = 0.85
DEFAULT_VERY_CHEAP_PRICE = 0.0

# --- New defaults for V3.2.0 / V3.5.0 ---
DEFAULT_INSTALLED_PV_WP = 0.0

DEFAULT_EXPERT_MODE_ENABLED = False
DEFAULT_CELL_VOLTAGE_PROTECTION_ENABLED = False

DEFAULT_CELL_VOLTAGE_WARNING = 3.10
DEFAULT_CELL_VOLTAGE_CUTOFF = 3.00
DEFAULT_CELL_VOLTAGE_RESUME = 3.18

DEFAULT_PV_CHARGE_START_EXPORT_W = 80.0

DEFAULT_FORECAST_BASE_LOAD = 300.0

DEFAULT_LEARNED_PLANNING_ENABLED = True

DEFAULT_OFFGRID_LOAD_ACTIVE_W = 50.0

DEFAULT_FEED_IN_TARIFF = 0.0

# --------------------------------------------------
# Device profiles (V1.5.x / V3.2.0 overrides)
# --------------------------------------------------

CONF_DEVICE_PROFILE = "device_profile"

DEVICE_PROFILE_SF2400AC = "SF2400AC"
DEVICE_PROFILE_SF2400PRO = "SF2400Pro"
DEVICE_PROFILE_SF800PRO = "SF800Pro"
DEVICE_PROFILE_SF1600AC = "SF1600AC"
DEVICE_PROFILE_SF3000MIXACPLUS = "SF3000MixAC+"
DEVICE_PROFILE_SF4000MIXACPLUS = "SF4000MixAC+"
DEVICE_PROFILE_SF4000MIXPRO = "SF4000MixPro"
DEVICE_PROFILE_HYPER2000 = "Hyper 2000"
DEVICE_PROFILE_HUB2000 = "HUB 2000"

DEFAULT_DEVICE_PROFILE = DEVICE_PROFILE_SF2400AC

GRID_MODE_NONE = "none"
GRID_MODE_SINGLE = "single"
GRID_MODE_SPLIT = "split"

# ==================================================
# Runtime select modes (internal values remain EN)
# ==================================================
AI_MODE_AUTOMATIC = "automatic"
AI_MODE_SUMMER = "summer"      # stable internal key, UI label = Autarkie
AI_MODE_WINTER = "winter"      # migration-only legacy key
AI_MODE_MANUAL = "manual"

# Active selectable modes.
# Do not include winter anymore. Stored/legacy winter values are normalized
# to automatic in the coordinator.
AI_MODES = [AI_MODE_AUTOMATIC, AI_MODE_SUMMER, AI_MODE_MANUAL]


def normalize_ai_mode(mode: str | None) -> str:
    """Normalize persisted legacy or invalid operating-mode values."""

    if mode == AI_MODE_WINTER:
        return AI_MODE_AUTOMATIC
    if mode in AI_MODES:
        return str(mode)
    return AI_MODE_AUTOMATIC

MANUAL_STANDBY = "standby"
MANUAL_CHARGE = "charge"
MANUAL_DISCHARGE = "discharge"
MANUAL_CONST_DISCHARGE = "constant_discharge"

MANUAL_ACTIONS = [
    MANUAL_STANDBY,
    MANUAL_CHARGE,
    MANUAL_DISCHARGE,
    MANUAL_CONST_DISCHARGE,
]

# ==================================================
# Settings (Number entities) – entity keys
# ==================================================
SETTING_SOC_MIN = "soc_min"
SETTING_SOC_MAX = "soc_max"
SETTING_MAX_CHARGE = "max_charge"
SETTING_MAX_DISCHARGE = "max_discharge"

SETTING_PRICE_THRESHOLD = "price_threshold"
SETTING_VERY_EXPENSIVE_THRESHOLD = "very_expensive_threshold"

SETTING_EMERGENCY_SOC = "emergency_soc"           # Notladung wenn SoC <= x
SETTING_EMERGENCY_CHARGE = "emergency_charge"     # Notladeleistung (W)

SETTING_PROFIT_MARGIN_PCT = "profit_margin_pct"   # Arbitrage/Planung

SETTING_PEAK_FACTOR = "peak_factor"

# ==================================================
# Defaults
# ==================================================
UPDATE_INTERVAL = 10  # seconds

DEFAULT_SOC_MIN = 12.0
DEFAULT_SOC_MAX = 100.0  # Herstellerempfehlung ✔

DEFAULT_MAX_CHARGE = 2400.0
DEFAULT_MAX_DISCHARGE = 700.0


DEFAULT_EMERGENCY_SOC = 8.0
DEFAULT_EMERGENCY_CHARGE = 1200.0

DEFAULT_PROFIT_MARGIN_PCT = 27.0

DEFAULT_PEAK_FACTOR = 1.35

# ==================================================
# Status / Enum values (internal)
# ==================================================
STATUS_INIT = "init"
STATUS_OK = "ok"
STATUS_SENSOR_INVALID = "sensor_invalid"
STATUS_PRICE_INVALID = "price_invalid"

AI_STATUS_STANDBY = "standby"
AI_STATUS_CHARGE_SURPLUS = "charge_surplus"
AI_STATUS_PRICE_CHARGE = "price_charge"
AI_STATUS_COVER_DEFICIT = "cover_deficit"
AI_STATUS_EXPENSIVE_DISCHARGE = "expensive_discharge"
AI_STATUS_VERY_EXPENSIVE_FORCE = "very_expensive_force"
AI_STATUS_EMERGENCY_CHARGE = "emergency_charge"
AI_STATUS_MANUAL = "manual"

RECO_STANDBY = "standby"
RECO_CHARGE = "charge"
RECO_DISCHARGE = "discharge"
RECO_EMERGENCY = "emergency_charge"

STATUS_ENUMS = [
    STATUS_INIT,
    STATUS_OK,
    STATUS_SENSOR_INVALID,
    STATUS_PRICE_INVALID,
]

AI_STATUS_ENUMS = [
    AI_STATUS_STANDBY,
    AI_STATUS_CHARGE_SURPLUS,
    AI_STATUS_PRICE_CHARGE,
    AI_STATUS_COVER_DEFICIT,
    AI_STATUS_EXPENSIVE_DISCHARGE,
    AI_STATUS_VERY_EXPENSIVE_FORCE,
    AI_STATUS_EMERGENCY_CHARGE,
    AI_STATUS_MANUAL,
]

RECO_ENUMS = [
    RECO_STANDBY,
    RECO_CHARGE,
    RECO_DISCHARGE,
    RECO_EMERGENCY,
]

# ==================================================
# Planning enums (V1.4.0)
# ==================================================
NEXT_ACTION_STATE_ENUMS = [
    "none",
    "planned_charge",
    "planned_discharge",
    "charging_active",
    "discharging_active",
    "discharge_waiting_for_import",
    "manual_charge",
    "manual_discharge",
    "manual_constant_discharge",
    "emergency_charge",
    "pv_house_load_passthrough_active",
]

NEXT_PLANNED_ACTION_ENUMS = [
    "none",
    "charge",
    "discharge",
    "wait",
    "emergency",
]

# ==================================================
# Cell voltage status enums (V3.5.0)
# ==================================================
CELL_VOLTAGE_STATUS_ENUMS = [
    "disabled",
    "normal",
    "warning",
    "cutoff_active",
    "sensor_invalid",
]

# ==================================================
# Cell voltage SoC plausibility enums (V3.5.0)
# ==================================================
CELL_VOLTAGE_SOC_PLAUSIBILITY_ENUMS = [
    "normal",
    "warning",
    "critical",
    "not_available",
]

# ==================================================
# Forecast enums (V4.0.0)
# Forecast bleibt immer optional.
# ==================================================
FORECAST_STATUS_NOT_CONFIGURED = "not_configured"
FORECAST_STATUS_UNAVAILABLE = "unavailable"
FORECAST_STATUS_AVAILABLE = "available"

FORECAST_STATUS_ENUMS = [
    FORECAST_STATUS_NOT_CONFIGURED,
    FORECAST_STATUS_UNAVAILABLE,
    FORECAST_STATUS_AVAILABLE,
]

PV_OUTLOOK_UNKNOWN = "unknown"
PV_OUTLOOK_POOR = "poor"
PV_OUTLOOK_MIXED = "mixed"
PV_OUTLOOK_GOOD = "good"

PV_OUTLOOK_ENUMS = [
    PV_OUTLOOK_UNKNOWN,
    PV_OUTLOOK_POOR,
    PV_OUTLOOK_MIXED,
    PV_OUTLOOK_GOOD,
]

# ==================================================
# Charge strategy enums (V4.0.0 transparency)
# ==================================================
CHARGE_STRATEGY_ENUMS = [
    "none",
    "pv_surplus",
    "planning_latest_start",
    "planning_forecast_poor",
    "planning_forecast_mixed",
    "planning_reality_override",
    "reserve",
    "valley_boost",
    "valley_boost_mixed",
    "very_cheap",
    "emergency",
    "manual",
    "valley_opportunity",
    "valley_opportunity_mixed",
    "learned_planning",
]

STRATEGY_STATE_ENUMS = [
    "protection",
    "emergency_charge",
    "manual_charge",
    "manual_discharge",
    "manual_idle",
    "ac_charge_committed",
    "ac_charge_planned",
    "ac_charge_price",
    "ac_charge_learned",
    "ac_charge_reserve",
    "pv_surplus_charge",
    "load_coverage",
    "economic_discharge",
    "offgrid_support",
    "passthrough",
    "hold",
    "idle_ready",
    "idle_safe",
]

VISIBLE_STATE_ENUMS = [
    "ready",
    "safe_idle",
    "protection_active",
    "emergency_charge",
    "manual",
    "grid_charge",
    "pv_charge",
    "reserve_charge",
    "autarky_cover",
    "load_coverage",
    "economic_discharge",
    "waiting_for_charge_window",
    "waiting_blocked",
    "hold",
]

BOOLEAN_STATE_ENUMS = ["no", "yes"]

SOURCE_ACTION_ENUMS = [
    "idle",
    "charge",
    "discharge",
    "emergency",
    "passthrough",
]

SOURCE_AC_MODE_ENUMS = ["input", "output"]

# Stable strategy/decision reasons exposed by the V4.3 adapter. These values
# remain language-independent recorder states and are translated by HA.
STRATEGY_REASON_ENUMS = [
    "none",
    "idle",
    "state_idle",
    "standby",
    "no_strategy_needed",
    "sensor_invalid",
    "soc_invalid",
    "grid_sensor_invalid",
    "soc_limits_invalid",
    "power_limits_invalid",
    "cell_voltage_sensor_invalid",
    "additional_battery_charging_block",
    "additional_battery_discharging_block",
    "pv_charge_blocked_by_discharge_protection",
    "pv_charge_blocked_no_stable_export",
    "soc_limit_upper",
    "soc_limit_lower",
    "soc_min_resume_block",
    "cell_voltage_cutoff_block",
    "emergency_latched_charge",
    "cell_voltage_emergency_charge",
    "manual_charge",
    "manual_constant_discharge",
    "manual_discharge",
    "manual_idle",
    "charge_commit_active",
    "charge_commit_waiting_price",
    "strategic_ac_charge_blocked_price_conflict",
    "learned_charge_window_active",
    "learned_charge_window_latest_start_reached",
    "learned_charge_window_deadline_too_close_start_now",
    "learned_charge_window_wait",
    "learned_charge_window_no_charge_needed",
    "planning_latest_start",
    "planning_forecast_poor",
    "planning_forecast_mixed",
    "planning_forecast_reality_override",
    "very_cheap_force_charge",
    "valley_boost_charge",
    "valley_boost_charge_mixed_forecast",
    "valley_opportunity_charge",
    "valley_opportunity_charge_mixed_forecast",
    "summer_peak_reserve_charge",
    "summer_peak_reserve_hold",
    "pv_surplus_charge",
    "pv_export_confirmed",
    "pv_house_load_passthrough",
    "offgrid_load_support",
    "offgrid_load_active_blocks_ac_charge",
    "summer_cover_deficit",
    "load_coverage",
    "adaptive_peak_discharge",
    "very_expensive_force_discharge",
    "price_based_discharge",
]

DECISION_REASON_ENUMS = [
    "standby",
    "state_idle",
    "state_enter_discharge",
    "state_discharging",
    "state_enter_charge",
    "state_charging",
    "expensive_discharge",
    "very_expensive_force_discharge",
    "emergency_latched_charge",
    "summer_cover_deficit",
    "pv_surplus_charge",
    "soc_min_enforced",
    "pv_house_load_passthrough",
    "soc_limit_upper",
    "soc_limit_lower",
    "manual_mode",
    "manual_standby",
    "manual_charge",
    "manual_discharge",
    "manual_constant_discharge",
    "manual_idle",
    "idle",
    "adaptive_peak_discharge",
    "price_based_discharge",
    "valley_boost_charge",
    "planning_latest_start",
    "planning_forecast_poor",
    "planning_forecast_mixed",
    "learned_charge_window_not_ready",
    "learned_charge_window_wait",
    "learned_charge_window_active",
    "charge_commit_active",
    "learned_charge_window_latest_start_reached",
    "learned_charge_window_no_charge_needed",
    "valley_opportunity_charge",
    "valley_opportunity_charge_mixed_forecast",
    "valley_boost_charge_mixed_forecast",
    "planning_forecast_reality_override",
    "very_cheap_force_charge",
    "additional_battery_charging_block",
    "additional_battery_discharging_block",
    "offgrid_load_active_blocks_ac_charge",
    "offgrid_load_support",
    "soc_min_resume_block",
    "cell_voltage_cutoff_block",
    "cell_voltage_emergency_charge",
    "pv_charge_blocked_by_discharge_protection",
    "learned_charge_window_deadline_too_close_start_now",
    "soc_invalid",
    "grid_sensor_invalid",
    "soc_limits_invalid",
    "power_limits_invalid",
    "cell_voltage_sensor_invalid",
    "summer_peak_reserve_charge",
    "summer_peak_reserve_hold",
]

TECHNICAL_REASON_ENUMS = [
    "none",
    "sensor_invalid",
    "soc_invalid",
    "grid_sensor_invalid",
    "soc_limits_invalid",
    "power_limits_invalid",
    "cell_voltage_sensor_invalid",
    "hold_no_power_change",
    "idle_zero_power",
    "manual_constant_output_step_limited",
    "passthrough_output_step_limited",
    "output_inside_deadband",
    "output_increase_to_reduce_import",
    "output_fast_increase_to_reduce_import",
    "output_decrease_to_avoid_export",
    "output_fast_decrease_to_avoid_export",
    "output_inside_deadband_near_zero_persistent_import_trim",
    "output_increase_to_reduce_import_near_zero_persistent_import_trim",
    "output_fast_increase_to_reduce_import_near_zero_persistent_import_trim",
    "output_decrease_to_avoid_export_near_zero_persistent_import_trim",
    "output_fast_decrease_to_avoid_export_near_zero_persistent_import_trim",
    "output_inside_deadband_discharge_keepalive",
    "output_decrease_to_avoid_export_discharge_keepalive",
    "output_fast_decrease_to_avoid_export_discharge_keepalive",
    "pv_input_inside_deadband",
    "pv_input_increase_from_export",
    "pv_input_fast_increase_from_export",
    "pv_input_decrease_to_avoid_import",
    "pv_input_fast_decrease_to_avoid_import",
    "pv_input_inside_deadband_current_grid_cap",
    "pv_input_increase_from_export_current_grid_cap",
    "pv_input_fast_increase_from_export_current_grid_cap",
    "pv_input_decrease_to_avoid_import_current_grid_cap",
    "pv_input_fast_decrease_to_avoid_import_current_grid_cap",
    "manual_charge_fixed_input_power",
    "planned_charge_fixed_input_power",
    "emergency_charge_fixed_input_power",
    "ramp_down_output_step_limited",
    "ramp_down_input_step_limited",
    "blocked_by_arbiter_pv_charge_wait_current_export",
]

# ==================================================
# Charge commit enums (V4.3.0-dev2)
# ==================================================

CHARGE_COMMIT_TYPE_ENUMS = [
    "none",
    "planning",
    "learned",
    "very_cheap",
    "valley",
    "opportunity",
    "reserve",
]

CHARGE_COMMIT_ABORT_REASON_ENUMS = [
    "none",
    "target_soc_reached",
    "max_soc_reached",
    "target_unreachable_battery_full",
    "target_nearly_reached_discharge_window",
    "learned_charge_no_longer_needed",
    "deadline_passed",
    "battery_full",
    "price_window_expired",
    "price_condition_lost",
    "protection_cutoff",
    "cell_voltage_cutoff",
    "soc_invalid",
    "sensor_invalid",
    "additional_battery_discharging_blocks_charge",
    "offgrid_load_blocks_ac_charge",
    "autarky_mode_selected",
    "manual_mode_selected",
    "user_disabled_automatic",
    "device_error",
    "unsafe_measurements",
]

AUTOMATIC_WEIGHTING_ENUMS = [
    "inactive",
    "pv_oriented",
    "balanced",
    "price_oriented",
    "reserve_oriented",
]

# ==================================================
# Zendure AC Mode options
# ==================================================
ZENDURE_MODE_INPUT = "input"
ZENDURE_MODE_OUTPUT = "output"
