from __future__ import annotations

from homeassistant.const import Platform

# ==================================================
# Integration meta
# ==================================================
DOMAIN = "battery_smartflow_ai"

INTEGRATION_NAME = "Battery SmartFlow AI"
INTEGRATION_MANUFACTURER = "PalmManiac"
INTEGRATION_MODEL = "Home Assistant Integration"
INTEGRATION_VERSION = "3.1.2"

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SWITCH,
]

# ==================================================
# Config Flow – required/optional entities
# ==================================================
CONF_SOC_ENTITY = "soc_entity"
CONF_PV_ENTITY = "pv_entity"

CONF_SOC_LIMIT_ENTITY = "soc_limit_entity"

# Preis ist optional (Sommer/PV-only Nutzer)
CONF_PRICE_EXPORT_ENTITY = "price_export_entity"  # Tibber Export (attributes.data)
CONF_PRICE_NOW_ENTITY = "price_now_entity"        # direkter Preis-Sensor (€/kWh)

CONF_ADDITIONAL_BATTERY_CHARGE_ENTITY = "additional_battery_charge_entity"
CONF_ADDITIONAL_BATTERY_DISCHARGE_ENTITY = "additional_battery_discharge_entity"
CONF_WALLBOX_POWER_ENTITY = "wallbox_power_entity"

# PV-Forecast-basierte Nachtladung (v3.2)
CONF_PV_FORECAST_ENTITY              = "pv_forecast_entity"
CONF_ADDITIONAL_BATTERY_SOC_ENTITY   = "additional_battery_soc_entity"
CONF_ADDITIONAL_BATTERY_CAPACITY_KWH = "additional_battery_capacity_kwh"
CONF_ADDITIONAL_BATTERY_MODE_ENTITY  = "additional_battery_mode_entity"    # input_select (optional)
CONF_ADDITIONAL_BATTERY_POWER_ENTITY = "additional_battery_power_entity"   # input_number (optional)
CONF_ADDITIONAL_BATTERY_CHARGE_MODE  = "additional_battery_charge_mode"    # z.B. "Akku schnell laden"
CONF_ADDITIONAL_BATTERY_STOP_MODE    = "additional_battery_stop_mode"      # z.B. "Akku automatisch"
CONF_ADDITIONAL_BATTERY_PAUSE_MODE   = "additional_battery_pause_mode"     # z.B. "Akku Pause" (kein Laden, kein Entladen)

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

# --- Runtime settings ---
SETTING_BATTERY_PACKS = "battery_packs"

SETTING_VALLEY_FACTOR = "valley_factor"
SETTING_VERY_CHEAP_PRICE = "very_cheap_price"

# PV-Forecast Runtime-Einstellungen (v3.2)
SETTING_PV_FORECAST_ENABLED      = "pv_forecast_enabled"       # 0.0 = aus, 1.0 = an
SETTING_DAYTIME_CONSUMPTION_W    = "daytime_consumption_w"     # Hausverbrauch tagsüber (08–18 Uhr) in W
SETTING_NIGHTTIME_CONSUMPTION_W  = "nighttime_consumption_w"   # Hausverbrauch nachts + Morgenbrücke in W

# Default
DEFAULT_PACK_CAPACITY_KWH = 2.88
DEFAULT_BATTERY_PACKS = 1

DEFAULT_VALLEY_FACTOR = 0.85
DEFAULT_VERY_CHEAP_PRICE = None

# PV-Forecast Defaults (v3.2)
DEFAULT_ADDITIONAL_BATTERY_CAPACITY_KWH = 0.0
DEFAULT_PV_FORECAST_ENABLED      = 0.0
DEFAULT_DAYTIME_CONSUMPTION_W    = 500.0   # Watt (08–18 Uhr, 10h → 5 kWh Direktverbrauch)
DEFAULT_NIGHTTIME_CONSUMPTION_W  = 500.0   # Watt (Nacht + Brücke 05–08 Uhr)

# --------------------------------------------------
# Device profiles (V1.5.x)
# --------------------------------------------------

CONF_DEVICE_PROFILE = "device_profile"

DEVICE_PROFILE_SF2400AC = "SF2400AC"
DEVICE_PROFILE_SF800PRO = "SF800Pro"

DEFAULT_DEVICE_PROFILE = DEVICE_PROFILE_SF2400AC

GRID_MODE_NONE = "none"
GRID_MODE_SINGLE = "single"
GRID_MODE_SPLIT = "split"

# ==================================================
# Runtime select modes (internal values remain EN)
# ==================================================
AI_MODE_AUTOMATIC = "automatic"
AI_MODE_SUMMER = "summer"
AI_MODE_WINTER = "winter"
AI_MODE_MANUAL = "manual"

AI_MODES = [AI_MODE_AUTOMATIC, AI_MODE_SUMMER, AI_MODE_WINTER, AI_MODE_MANUAL]

MANUAL_STANDBY = "standby"
MANUAL_CHARGE = "charge"
MANUAL_DISCHARGE = "discharge"
MANUAL_CONST_DISCHARGE = "constant_discharge"

MANUAL_ACTIONS = [MANUAL_STANDBY, MANUAL_CHARGE, MANUAL_DISCHARGE, MANUAL_CONST_DISCHARGE]

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

DEFAULT_PRICE_THRESHOLD = 0.35
DEFAULT_VERY_EXPENSIVE_THRESHOLD = 0.49

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
    "manual_charge",
    "manual_discharge",
    "emergency_charge",
]

NEXT_PLANNED_ACTION_ENUMS = [
    "none",
    "charge",
    "discharge",
    "wait",
    "emergency",
]

# ==================================================
# Zendure AC Mode options
# ==================================================
ZENDURE_MODE_INPUT = "input"
ZENDURE_MODE_OUTPUT = "output"
