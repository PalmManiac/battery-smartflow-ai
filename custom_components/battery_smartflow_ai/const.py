from __future__ import annotations

from homeassistant.const import Platform

# ==================================================
# Integration meta
# ==================================================
DOMAIN = "battery_smartflow_ai"

INTEGRATION_NAME = "Battery SmartFlow AI"
INTEGRATION_MANUFACTURER = "PalmManiac"
INTEGRATION_MODEL = "Home Assistant Integration"
INTEGRATION_VERSION = "3.6.4"

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

CONF_SOC_LIMIT_ENTITY = "soc_limit_entity"

# Preis ist optional (Sommer/PV-only Nutzer)
CONF_PRICE_EXPORT_ENTITY = "price_export_entity"  # Tibber Export (attributes.data)
CONF_PRICE_NOW_ENTITY = "price_now_entity"        # direkter Preis-Sensor (€/kWh)

CONF_ADDITIONAL_BATTERY_CHARGE_ENTITY = "additional_battery_charge_entity"

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

# --------------------------------------------------
# Device profiles (V1.5.x / V3.2.0 overrides)
# --------------------------------------------------

CONF_DEVICE_PROFILE = "device_profile"

DEVICE_PROFILE_SF2400AC = "SF2400AC"
DEVICE_PROFILE_SF800PRO = "SF800Pro"
DEVICE_PROFILE_SF1600AC = "SF1600AC"
DEVICE_PROFILE_HYPER2000 = "Hyper 2000"

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
    "manual_charge",
    "manual_discharge",
    "manual_constant_discharge",
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
# Zendure AC Mode options
# ==================================================
ZENDURE_MODE_INPUT = "input"
ZENDURE_MODE_OUTPUT = "output"
