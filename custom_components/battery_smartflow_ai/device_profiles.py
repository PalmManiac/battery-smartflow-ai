from __future__ import annotations


# V4.2.0:
# Normal user-editable profile fields.
#
# Legacy controller values DEADBAND_W / KP_* / MAX_STEP_* are intentionally no
# longer part of the normal override UI focus. They remain in the profiles as
# fallback/migration values and are still accepted in merge_profile_with_overrides()
# via PROFILE_MIGRATION_OVERRIDE_FIELDS.
PROFILE_OVERRIDE_FIELDS = {
    "TARGET_IMPORT_W": {
        "label": "Ziel-Netzbezug",
        "min": 0.0,
        "max": 300.0,
        "step": 5.0,
        "unit": "W",
        "icon": "mdi:transmission-tower-import",
    },
    "DISCHARGE_TARGET_IMPORT_W": {
        "label": "Entladen Ziel-Netzbezug",
        "min": -50.0,
        "max": 100.0,
        "step": 1.0,
        "unit": "W",
        "icon": "mdi:transmission-tower-export",
    },
    "EXPORT_GUARD_W": {
        "label": "Export-Schutz",
        "min": 0.0,
        "max": 300.0,
        "step": 5.0,
        "unit": "W",
        "icon": "mdi:shield-outline",
    },
    "KEEPALIVE_MIN_DEFICIT_W": {
        "label": "Keepalive Mindestdefizit",
        "min": 0.0,
        "max": 200.0,
        "step": 5.0,
        "unit": "W",
        "icon": "mdi:flash-outline",
    },
    "KEEPALIVE_MIN_OUTPUT_W": {
        "label": "Keepalive Mindestleistung",
        "min": 0.0,
        "max": 300.0,
        "step": 5.0,
        "unit": "W",
        "icon": "mdi:flash",
    },
    "SOC_DISCHARGE_RESUME_MARGIN": {
        "label": "SoC Wiederfreigabe-Margin",
        "min": 0.0,
        "max": 15.0,
        "step": 0.5,
        "unit": "%",
        "icon": "mdi:battery-sync",
    },
    "PV_HOUSELOAD_PASSTHROUGH_MIN_PV_W": {
        "label": "Passthrough Mindest-PV",
        "min": 20.0,
        "max": 300.0,
        "step": 5.0,
        "unit": "W",
        "icon": "mdi:solar-power-variant-outline",
    },
    "PV_HOUSELOAD_PASSTHROUGH_MIN_HOUSE_LOAD_W": {
        "label": "Passthrough Mindest-Hauslast",
        "min": 20.0,
        "max": 300.0,
        "step": 5.0,
        "unit": "W",
        "icon": "mdi:home-lightning-bolt-outline",
    },
    "CHARGE_DEADBAND_W": {
        "label": "Laden Deadband",
        "min": 0.0,
        "max": 200.0,
        "step": 5.0,
        "unit": "W",
        "icon": "mdi:battery-plus-outline",
    },
    "CHARGE_KP_UP": {
        "label": "Laden KP Hochregeln",
        "min": 0.10,
        "max": 2.00,
        "step": 0.01,
        "unit": "",
        "icon": "mdi:chart-line-variant",
    },
    "CHARGE_KP_DOWN": {
        "label": "Laden KP Runterregeln",
        "min": 0.10,
        "max": 2.00,
        "step": 0.01,
        "unit": "",
        "icon": "mdi:chart-line-variant",
    },
    "CHARGE_MAX_STEP_UP": {
        "label": "Laden Max. Schritt Hochregeln",
        "min": 50.0,
        "max": 2000.0,
        "step": 10.0,
        "unit": "W",
        "icon": "mdi:arrow-up-bold",
    },
    "CHARGE_MAX_STEP_DOWN": {
        "label": "Laden Max. Schritt Runterregeln",
        "min": 50.0,
        "max": 2000.0,
        "step": 10.0,
        "unit": "W",
        "icon": "mdi:arrow-down-bold",
    },
    "DISCHARGE_DEADBAND_W": {
        "label": "Entladen Deadband",
        "min": 0.0,
        "max": 200.0,
        "step": 5.0,
        "unit": "W",
        "icon": "mdi:battery-minus-outline",
    },
    "DISCHARGE_KP_UP": {
        "label": "Entladen KP Hochregeln",
        "min": 0.10,
        "max": 2.00,
        "step": 0.01,
        "unit": "",
        "icon": "mdi:chart-line-variant",
    },
    "DISCHARGE_KP_DOWN": {
        "label": "Entladen KP Runterregeln",
        "min": 0.10,
        "max": 2.00,
        "step": 0.01,
        "unit": "",
        "icon": "mdi:chart-line-variant",
    },
    "DISCHARGE_MAX_STEP_UP": {
        "label": "Entladen Max. Schritt Hochregeln",
        "min": 50.0,
        "max": 2000.0,
        "step": 10.0,
        "unit": "W",
        "icon": "mdi:arrow-up-bold",
    },
    "DISCHARGE_MAX_STEP_DOWN": {
        "label": "Entladen Max. Schritt Runterregeln",
        "min": 50.0,
        "max": 2000.0,
        "step": 10.0,
        "unit": "W",
        "icon": "mdi:arrow-down-bold",
    },
}


# V4.2.0:
# Legacy fields are no longer part of the normal profile editor focus, but
# old stored overrides should still be accepted for migration/backward
# compatibility until the V4.3.0 cleanup.
PROFILE_MIGRATION_OVERRIDE_FIELDS = {
    "DEADBAND_W",
    "KP_UP",
    "KP_DOWN",
    "MAX_STEP_UP",
    "MAX_STEP_DOWN",
}


# Optional: diese Felder sollen zwar sichtbar, aber nicht editierbar sein.
PROFILE_FIXED_FIELDS = {
    "MAX_INPUT_W",
    "MAX_OUTPUT_W",
}


# ---------------------------------------------------------------------------
# Shared V4.2.0 regulation defaults
# ---------------------------------------------------------------------------

V42_GRID_HISTORY_DEFAULTS = {
    "GRID_HISTORY_SHORT_SAMPLES": 3,
    "GRID_HISTORY_MEDIUM_SAMPLES": 6,
    "GRID_HISTORY_MAX_SAMPLES": 12,
    "FAST_LOAD_CHANGE_W": 600.0,
    "FAST_LOAD_STDDEV_FACTOR": 3.5,
    "FAST_LOAD_STDDEV_MIN_W": 80.0,
}


V42_MODE_ARBITER_DEFAULTS = {
    "MODE_SWITCH_COOLDOWN_S": 30.0,
    "INPUT_AFTER_OUTPUT_BLOCK_S": 60.0,
    "OUTPUT_AFTER_INPUT_BLOCK_S": 30.0,
    "STABLE_EXPORT_CYCLES_FOR_PV_CHARGE": 3,
    "STABLE_IMPORT_CYCLES_FOR_DISCHARGE": 2,
    "EXTERNAL_BATTERY_DISCHARGE_BLOCK_W": 50.0,
}


V42_LATCH_HOLD_DEFAULTS = {
    "PV_CHARGE_LATCH_MIN_HOLD_S": 120.0,
    "PV_CHARGE_EXIT_IMPORT_CYCLES": 3,
    "DISCHARGE_LATCH_MIN_HOLD_S": 60.0,
    "DISCHARGE_EXIT_EXPORT_CYCLES": 3,
    "PASSTHROUGH_LATCH_MIN_HOLD_S": 120.0,
    "PASSTHROUGH_EXIT_CYCLES": 3,
    "POST_LOAD_DROP_HOLD_S": 60.0,
    "POST_OUTPUT_OVERSHOOT_HOLD_S": 60.0,
}


V42_DEFAULT_CAPABILITIES = {
    "SUPPORTS_PASSTHROUGH": False,
    # Device quirk: MPPT regelt auf 0 W ab, sobald weder Akku noch Output
    # den PV-Strom abnehmen können (z. B. Akku voll + Einspeiseverbot).
    # Der MPPT läuft erst wieder an, wenn der Output geöffnet wird.
    "MPPT_CLIPS_WITHOUT_OUTPUT": False,
    "OUTPUT_ZERO_IS_NEUTRAL": True,
    "INPUT_KEEPALIVE_SAFE": True,
    "REQUIRES_STABLE_EXPORT_FOR_INPUT": False,
    "SUPPORTS_FAST_MODE_SWITCH": True,
}


V42_SF800PRO_CAPABILITIES = {
    "SUPPORTS_PASSTHROUGH": True,
    "MPPT_CLIPS_WITHOUT_OUTPUT": True,
    "OUTPUT_ZERO_IS_NEUTRAL": True,
    "INPUT_KEEPALIVE_SAFE": False,
    "REQUIRES_STABLE_EXPORT_FOR_INPUT": True,
    "SUPPORTS_FAST_MODE_SWITCH": False,
}


V42_COMMON_DEFAULTS = {
    **V42_GRID_HISTORY_DEFAULTS,
    **V42_MODE_ARBITER_DEFAULTS,
    **V42_LATCH_HOLD_DEFAULTS,
    **V42_DEFAULT_CAPABILITIES,
}


# ---------------------------------------------------------------------------
# Legacy / transition passthrough defaults
# ---------------------------------------------------------------------------

PASSTHROUGH_DISABLED_DEFAULTS = {
    # Legacy SF800Pro-specific keys, kept for V4.1.x/V4.2 transition code.
    "PV_HOUSELOAD_PASSTHROUGH": False,
    "PV_HOUSELOAD_PASSTHROUGH_HOLD_SECONDS": 0.0,
    "PV_HOUSELOAD_PASSTHROUGH_MIN_PV_W": 0.0,
    "PV_HOUSELOAD_PASSTHROUGH_MIN_HOUSE_LOAD_W": 0.0,
    "PV_HOUSELOAD_PASSTHROUGH_EXPORT_STOP_CYCLES": 0,

    # Legacy SF800Pro passthrough output smoothing, kept as transition fallback.
    "PV_HOUSELOAD_PASSTHROUGH_MIN_OUTPUT_W": 0.0,
    "PV_HOUSELOAD_PASSTHROUGH_MAX_STEP_UP_W": 0.0,
    "PV_HOUSELOAD_PASSTHROUGH_MAX_STEP_DOWN_W": 0.0,
    "PV_HOUSELOAD_PASSTHROUGH_SMOOTHING_ALPHA": 0.0,

    # Legacy PV charge latch keys, kept as transition fallback.
    "PV_CHARGE_LATCH_HOLD_SECONDS": 0.0,
    "PV_CHARGE_LATCH_STOP_CYCLES": 0,
}


SF800PRO_PASSTHROUGH_DEFAULTS = {
    # Legacy SF800Pro-specific keys, kept until V4.2/V4.3 cleanup.
    "PV_HOUSELOAD_PASSTHROUGH": True,
    "PV_HOUSELOAD_PASSTHROUGH_HOLD_SECONDS": 300.0,
    "PV_HOUSELOAD_PASSTHROUGH_MIN_PV_W": 120.0,
    "PV_HOUSELOAD_PASSTHROUGH_MIN_HOUSE_LOAD_W": 120.0,
    "PV_HOUSELOAD_PASSTHROUGH_EXPORT_STOP_CYCLES": 18,

    # Legacy SF800Pro passthrough output smoothing.
    # Candidate for removal/deactivation once GridHistory + PowerController
    # step limits fully replace this behavior.
    "PV_HOUSELOAD_PASSTHROUGH_MIN_OUTPUT_W": 80.0,
    "PV_HOUSELOAD_PASSTHROUGH_MAX_STEP_UP_W": 100.0,
    "PV_HOUSELOAD_PASSTHROUGH_MAX_STEP_DOWN_W": 150.0,
    "PV_HOUSELOAD_PASSTHROUGH_SMOOTHING_ALPHA": 0.30,

    # Legacy PV charge latch keys.
    "PV_CHARGE_LATCH_HOLD_SECONDS": 300.0,
    "PV_CHARGE_LATCH_STOP_CYCLES": 18,

    # V4.2.0 generalized equivalents.
    "PV_CHARGE_LATCH_MIN_HOLD_S": 300.0,
    "PV_CHARGE_EXIT_IMPORT_CYCLES": 18,
    "PASSTHROUGH_LATCH_MIN_HOLD_S": 300.0,
    "PASSTHROUGH_EXIT_CYCLES": 18,
}


# ---------------------------------------------------------------------------
# Device profiles
# ---------------------------------------------------------------------------

SF800PRO_PROFILE = {
    # --- UI ---
    "label": "Zendure SF800Pro",

    # --- Legacy controller tuning / fallback ---
    "TARGET_IMPORT_W": 30.0,
    "DEADBAND_W": 35.0,
    "EXPORT_GUARD_W": 40.0,
    "KP_UP": 0.40,
    "KP_DOWN": 0.75,
    "MAX_STEP_UP": 250.0,
    "MAX_STEP_DOWN": 400.0,

    # --- Shared / other tuning ---
    "KEEPALIVE_MIN_DEFICIT_W": 15.0,
    "KEEPALIVE_MIN_OUTPUT_W": 60.0,
    "SOC_DISCHARGE_RESUME_MARGIN": 3.0,

    # --- Low-SoC / cell-voltage protection behavior ---
    # SF800Pro batteries appear more sensitive near low SoC.
    # Keep this strict behavior profile-specific to avoid restricting stronger systems.
    "LOW_SOC_PROTECTION_STRICT": True,
    "LOW_SOC_PV_CHARGE_REQUIRES_EXPORT": True,
    "LOW_SOC_DISCHARGE_REQUIRES_CELL_RESUME": True,

    # --- V4.2.0 regulation / capabilities ---
    **V42_COMMON_DEFAULTS,
    **V42_SF800PRO_CAPABILITIES,
    **SF800PRO_PASSTHROUGH_DEFAULTS,

    # --- Charge controller tuning ---
    "CHARGE_DEADBAND_W": 35.0,
    "CHARGE_KP_UP": 0.40,
    "CHARGE_KP_DOWN": 0.75,
    "CHARGE_MAX_STEP_UP": 250.0,
    "CHARGE_MAX_STEP_DOWN": 400.0,

    # --- Discharge controller tuning ---
    "DISCHARGE_TARGET_IMPORT_W": 0.0,
    "DISCHARGE_DEADBAND_W": 35.0,
    "DISCHARGE_KP_UP": 0.40,
    "DISCHARGE_KP_DOWN": 0.75,
    "DISCHARGE_MAX_STEP_UP": 250.0,
    "DISCHARGE_MAX_STEP_DOWN": 400.0,

    # --- Hardware limits (safety clamp) ---
    "MAX_INPUT_W": 1000.0,
    "MAX_OUTPUT_W": 800.0,
    
    "SUPPORTS_OFFGRID_SOCKET": False,
    "SUPPORTS_OFFGRID_INPUT": False,
    "OFFGRID_MAX_INTERNAL_SUPPLY_W": 0.0,
    "OFFGRID_LOAD_ACTIVE_W": 50.0,
    "OFFGRID_LOAD_BLOCKS_AC_CHARGE": False,
    "OFFGRID_INPUT_AFFECTS_ENERGY_BALANCE": False,
}


SF800PRO2_PROFILE = {
    # --- UI ---
    "label": "Zendure SF800Pro2",

    # --- Legacy controller tuning / fallback ---
    # Slightly more conservative than SF800Pro. The Pro2 seems to react quickly
    # and can become nervous when chasing 0 W too aggressively.
    "TARGET_IMPORT_W": 20.0,
    "DEADBAND_W": 45.0,
    "EXPORT_GUARD_W": 80.0,
    "KP_UP": 0.30,
    "KP_DOWN": 0.55,
    "MAX_STEP_UP": 120.0,
    "MAX_STEP_DOWN": 220.0,

    # --- Shared / other tuning ---
    "KEEPALIVE_MIN_DEFICIT_W": 20.0,
    "KEEPALIVE_MIN_OUTPUT_W": 80.0,
    "SOC_DISCHARGE_RESUME_MARGIN": 3.0,

    # --- Low-SoC / cell-voltage protection behavior ---
    # Keep the strict SF800Pro behavior for now. The Pro2 still belongs to the
    # smaller 800 W class and should not be treated like the stronger 2400-series.
    "LOW_SOC_PROTECTION_STRICT": True,
    "LOW_SOC_PV_CHARGE_REQUIRES_EXPORT": True,
    "LOW_SOC_DISCHARGE_REQUIRES_CELL_RESUME": True,

    # --- V4.2.0 regulation / capabilities ---
    **V42_COMMON_DEFAULTS,
    **V42_SF800PRO_CAPABILITIES,
    **SF800PRO_PASSTHROUGH_DEFAULTS,

    # --- V4.2.0 mode stability ---
    # Avoid frequent INPUT/OUTPUT changes on the smaller 800 W platform.
    "SUPPORTS_FAST_MODE_SWITCH": False,
    "MODE_SWITCH_COOLDOWN_S": 45.0,
    "INPUT_AFTER_OUTPUT_BLOCK_S": 90.0,
    "OUTPUT_AFTER_INPUT_BLOCK_S": 45.0,

    # Require slightly more stable grid evidence before starting charge/discharge.
    "STABLE_EXPORT_CYCLES_FOR_PV_CHARGE": 4,
    "STABLE_IMPORT_CYCLES_FOR_DISCHARGE": 3,

    # Keep active regulation states a bit longer to avoid short mode flicker.
    "PV_CHARGE_LATCH_MIN_HOLD_S": 150.0,
    "DISCHARGE_LATCH_MIN_HOLD_S": 90.0,
    "PASSTHROUGH_LATCH_MIN_HOLD_S": 150.0,

    # --- Charge controller tuning ---
    # More damped than SF800Pro to reduce short INPUT spikes and fast jumps.
    "CHARGE_DEADBAND_W": 50.0,
    "CHARGE_KP_UP": 0.25,
    "CHARGE_KP_DOWN": 0.45,
    "CHARGE_MAX_STEP_UP": 120.0,
    "CHARGE_MAX_STEP_DOWN": 180.0,

    # --- Discharge controller tuning ---
    # Do not chase exact 0 W. A small intentional import target is calmer.
    "DISCHARGE_TARGET_IMPORT_W": 20.0,
    "DISCHARGE_DEADBAND_W": 45.0,
    "DISCHARGE_KP_UP": 0.30,
    "DISCHARGE_KP_DOWN": 0.55,
    "DISCHARGE_MAX_STEP_UP": 120.0,
    "DISCHARGE_MAX_STEP_DOWN": 220.0,

    # --- Hardware limits (safety clamp) ---
    "MAX_INPUT_W": 1000.0,
    "MAX_OUTPUT_W": 800.0,

    # --- Off-Grid / island socket ---
    # No confirmed Off-Grid socket support for this profile yet.
    "SUPPORTS_OFFGRID_SOCKET": False,
    "SUPPORTS_OFFGRID_INPUT": False,
    "OFFGRID_MAX_INTERNAL_SUPPLY_W": 0.0,
    "OFFGRID_LOAD_ACTIVE_W": 50.0,
    "OFFGRID_LOAD_BLOCKS_AC_CHARGE": False,
    "OFFGRID_INPUT_AFFECTS_ENERGY_BALANCE": False,
}


SF2400AC_PROFILE = {
    # --- UI ---
    "label": "Zendure SF2400AC",

    # --- Legacy controller tuning / fallback ---
    "TARGET_IMPORT_W": 10.0,
    "DEADBAND_W": 30.0,
    "EXPORT_GUARD_W": 80.0,
    "KP_UP": 0.65,
    "KP_DOWN": 0.90,
    "MAX_STEP_UP": 550.0,
    "MAX_STEP_DOWN": 800.0,

    # --- Shared / other tuning ---
    "KEEPALIVE_MIN_DEFICIT_W": 15.0,
    "KEEPALIVE_MIN_OUTPUT_W": 60.0,
    "SOC_DISCHARGE_RESUME_MARGIN": 3.0,

    # --- Low-SoC / cell-voltage protection behavior ---
    "LOW_SOC_PROTECTION_STRICT": False,
    "LOW_SOC_PV_CHARGE_REQUIRES_EXPORT": False,
    "LOW_SOC_DISCHARGE_REQUIRES_CELL_RESUME": False,

    # --- V4.2.0 regulation / capabilities ---
    **V42_COMMON_DEFAULTS,
    **PASSTHROUGH_DISABLED_DEFAULTS,

    # --- Charge controller tuning ---
    "CHARGE_DEADBAND_W": 30.0,
    "CHARGE_KP_UP": 0.65,
    "CHARGE_KP_DOWN": 0.90,
    "CHARGE_MAX_STEP_UP": 550.0,
    "CHARGE_MAX_STEP_DOWN": 800.0,

    # --- Discharge controller tuning ---
    "DISCHARGE_TARGET_IMPORT_W": -10.0,
    "DISCHARGE_DEADBAND_W": 30.0,
    "DISCHARGE_KP_UP": 0.65,
    "DISCHARGE_KP_DOWN": 0.90,
    "DISCHARGE_MAX_STEP_UP": 550.0,
    "DISCHARGE_MAX_STEP_DOWN": 800.0,

    # --- Hardware limits (safety clamp) ---
    "MAX_INPUT_W": 2400.0,
    "MAX_OUTPUT_W": 2400.0,
    
    "SUPPORTS_OFFGRID_SOCKET": True,
    "SUPPORTS_OFFGRID_INPUT": True,
    "OFFGRID_MAX_INTERNAL_SUPPLY_W": 2400.0,
    "OFFGRID_LOAD_ACTIVE_W": 50.0,
    "OFFGRID_LOAD_BLOCKS_AC_CHARGE": True,
    "OFFGRID_INPUT_AFFECTS_ENERGY_BALANCE": False,
}


SF2400ACPLUS_PROFILE = {
    # --- UI ---
    "label": "Zendure SF2400AC+",

    # --- Legacy controller tuning / fallback ---
    "TARGET_IMPORT_W": 10.0,
    "DEADBAND_W": 30.0,
    "EXPORT_GUARD_W": 80.0,
    "KP_UP": 0.65,
    "KP_DOWN": 0.90,
    "MAX_STEP_UP": 550.0,
    "MAX_STEP_DOWN": 800.0,

    # --- Shared / other tuning ---
    "KEEPALIVE_MIN_DEFICIT_W": 15.0,
    "KEEPALIVE_MIN_OUTPUT_W": 60.0,
    "SOC_DISCHARGE_RESUME_MARGIN": 3.0,

    # --- Low-SoC / cell-voltage protection behavior ---
    "LOW_SOC_PROTECTION_STRICT": False,
    "LOW_SOC_PV_CHARGE_REQUIRES_EXPORT": False,
    "LOW_SOC_DISCHARGE_REQUIRES_CELL_RESUME": False,

    # --- V4.2.0 regulation / capabilities ---
    **V42_COMMON_DEFAULTS,
    **PASSTHROUGH_DISABLED_DEFAULTS,

    # --- Charge controller tuning ---
    "CHARGE_DEADBAND_W": 30.0,
    "CHARGE_KP_UP": 0.65,
    "CHARGE_KP_DOWN": 0.90,
    "CHARGE_MAX_STEP_UP": 550.0,
    "CHARGE_MAX_STEP_DOWN": 800.0,

    # --- Discharge controller tuning ---
    "DISCHARGE_TARGET_IMPORT_W": -10.0,
    "DISCHARGE_DEADBAND_W": 30.0,
    "DISCHARGE_KP_UP": 0.65,
    "DISCHARGE_KP_DOWN": 0.90,
    "DISCHARGE_MAX_STEP_UP": 550.0,
    "DISCHARGE_MAX_STEP_DOWN": 800.0,

    # --- Hardware limits (safety clamp) ---
    "MAX_INPUT_W": 2400.0,
    "MAX_OUTPUT_W": 2400.0,
    
    "SUPPORTS_OFFGRID_SOCKET": True,
    "SUPPORTS_OFFGRID_INPUT": True,
    "OFFGRID_MAX_INTERNAL_SUPPLY_W": 2400.0,
    "OFFGRID_LOAD_ACTIVE_W": 50.0,
    "OFFGRID_LOAD_BLOCKS_AC_CHARGE": True,
    "OFFGRID_INPUT_AFFECTS_ENERGY_BALANCE": False,
}


SF2400PRO_PROFILE = {
    # --- UI ---
    "label": "Zendure SF2400Pro",

    # --- Legacy controller tuning / fallback ---
    "TARGET_IMPORT_W": 10.0,
    "DEADBAND_W": 30.0,
    "EXPORT_GUARD_W": 80.0,
    "KP_UP": 0.65,
    "KP_DOWN": 0.90,
    "MAX_STEP_UP": 550.0,
    "MAX_STEP_DOWN": 800.0,

    # --- Shared / other tuning ---
    "KEEPALIVE_MIN_DEFICIT_W": 15.0,
    "KEEPALIVE_MIN_OUTPUT_W": 60.0,
    "SOC_DISCHARGE_RESUME_MARGIN": 3.0,

    # --- Low-SoC / cell-voltage protection behavior ---
    "LOW_SOC_PROTECTION_STRICT": False,
    "LOW_SOC_PV_CHARGE_REQUIRES_EXPORT": False,
    "LOW_SOC_DISCHARGE_REQUIRES_CELL_RESUME": False,

    # --- V4.2.0 regulation / capabilities ---
    **V42_COMMON_DEFAULTS,
    **PASSTHROUGH_DISABLED_DEFAULTS,

    # --- Charge controller tuning ---
    "CHARGE_DEADBAND_W": 30.0,
    "CHARGE_KP_UP": 0.65,
    "CHARGE_KP_DOWN": 0.90,
    "CHARGE_MAX_STEP_UP": 550.0,
    "CHARGE_MAX_STEP_DOWN": 800.0,

    # --- Discharge controller tuning ---
    "DISCHARGE_TARGET_IMPORT_W": -5.0,
    "DISCHARGE_DEADBAND_W": 30.0,
    "DISCHARGE_KP_UP": 0.65,
    "DISCHARGE_KP_DOWN": 0.90,
    "DISCHARGE_MAX_STEP_UP": 550.0,
    "DISCHARGE_MAX_STEP_DOWN": 800.0,

    # --- Hardware limits (safety clamp) ---
    "MAX_INPUT_W": 2400.0,
    "MAX_OUTPUT_W": 2400.0,
    
    "SUPPORTS_OFFGRID_SOCKET": True,
    "SUPPORTS_OFFGRID_INPUT": True,
    "OFFGRID_MAX_INTERNAL_SUPPLY_W": 2400.0,
    "OFFGRID_LOAD_ACTIVE_W": 50.0,
    "OFFGRID_LOAD_BLOCKS_AC_CHARGE": True,
    "OFFGRID_INPUT_AFFECTS_ENERGY_BALANCE": False,
}


SF1600AC_PROFILE = {
    # --- UI ---
    "label": "Zendure SF1600AC+",

    # --- Legacy controller tuning / fallback ---
    "TARGET_IMPORT_W": 35.0,
    "DEADBAND_W": 40.0,
    "EXPORT_GUARD_W": 45.0,
    "KP_UP": 0.55,
    "KP_DOWN": 0.95,
    "MAX_STEP_UP": 450.0,
    "MAX_STEP_DOWN": 900.0,

    # --- Shared / other tuning ---
    "KEEPALIVE_MIN_DEFICIT_W": 15.0,
    "KEEPALIVE_MIN_OUTPUT_W": 60.0,
    "SOC_DISCHARGE_RESUME_MARGIN": 3.0,

    # --- Low-SoC / cell-voltage protection behavior ---
    "LOW_SOC_PROTECTION_STRICT": False,
    "LOW_SOC_PV_CHARGE_REQUIRES_EXPORT": False,
    "LOW_SOC_DISCHARGE_REQUIRES_CELL_RESUME": False,

    # --- V4.2.0 regulation / capabilities ---
    **V42_COMMON_DEFAULTS,
    **PASSTHROUGH_DISABLED_DEFAULTS,

    # --- Charge controller tuning ---
    "CHARGE_DEADBAND_W": 40.0,
    "CHARGE_KP_UP": 0.55,
    "CHARGE_KP_DOWN": 0.95,
    "CHARGE_MAX_STEP_UP": 450.0,
    "CHARGE_MAX_STEP_DOWN": 900.0,

    # --- Discharge controller tuning ---
    "DISCHARGE_TARGET_IMPORT_W": 0.0,
    "DISCHARGE_DEADBAND_W": 40.0,
    "DISCHARGE_KP_UP": 0.55,
    "DISCHARGE_KP_DOWN": 0.95,
    "DISCHARGE_MAX_STEP_UP": 450.0,
    "DISCHARGE_MAX_STEP_DOWN": 900.0,

    # --- Hardware limits (safety clamp) ---
    "MAX_INPUT_W": 1600.0,
    "MAX_OUTPUT_W": 1600.0,
    
    "SUPPORTS_OFFGRID_SOCKET": False,
    "SUPPORTS_OFFGRID_INPUT": False,
    "OFFGRID_MAX_INTERNAL_SUPPLY_W": 0.0,
    "OFFGRID_LOAD_ACTIVE_W": 50.0,
    "OFFGRID_LOAD_BLOCKS_AC_CHARGE": False,
    "OFFGRID_INPUT_AFFECTS_ENERGY_BALANCE": False,
}


HYPER2000_PROFILE = {
    # --- UI ---
    "label": "Zendure Hyper 2000",

    # --- Legacy controller tuning / fallback ---
    "TARGET_IMPORT_W": 10.0,
    "DEADBAND_W": 30.0,
    "EXPORT_GUARD_W": 80.0,
    "KP_UP": 0.65,
    "KP_DOWN": 0.90,
    "MAX_STEP_UP": 550.0,
    "MAX_STEP_DOWN": 800.0,

    # --- Shared / other tuning ---
    "KEEPALIVE_MIN_DEFICIT_W": 15.0,
    "KEEPALIVE_MIN_OUTPUT_W": 60.0,
    "SOC_DISCHARGE_RESUME_MARGIN": 3.0,

    # --- Low-SoC / cell-voltage protection behavior ---
    "LOW_SOC_PROTECTION_STRICT": False,
    "LOW_SOC_PV_CHARGE_REQUIRES_EXPORT": False,
    "LOW_SOC_DISCHARGE_REQUIRES_CELL_RESUME": False,

    # --- V4.2.0 regulation / capabilities ---
    **V42_COMMON_DEFAULTS,
    **PASSTHROUGH_DISABLED_DEFAULTS,

    # --- Charge controller tuning ---
    "CHARGE_DEADBAND_W": 30.0,
    "CHARGE_KP_UP": 0.65,
    "CHARGE_KP_DOWN": 0.90,
    "CHARGE_MAX_STEP_UP": 550.0,
    "CHARGE_MAX_STEP_DOWN": 800.0,

    # --- Discharge controller tuning ---
    "DISCHARGE_TARGET_IMPORT_W": -5.0,
    "DISCHARGE_DEADBAND_W": 30.0,
    "DISCHARGE_KP_UP": 0.65,
    "DISCHARGE_KP_DOWN": 0.90,
    "DISCHARGE_MAX_STEP_UP": 550.0,
    "DISCHARGE_MAX_STEP_DOWN": 800.0,

    # --- Hardware limits (safety clamp) ---
    "MAX_INPUT_W": 1200.0,
    "MAX_OUTPUT_W": 1200.0,
    
    "SUPPORTS_OFFGRID_SOCKET": False,
    "SUPPORTS_OFFGRID_INPUT": False,
    "OFFGRID_MAX_INTERNAL_SUPPLY_W": 0.0,
    "OFFGRID_LOAD_ACTIVE_W": 50.0,
    "OFFGRID_LOAD_BLOCKS_AC_CHARGE": False,
    "OFFGRID_INPUT_AFFECTS_ENERGY_BALANCE": False,
}


HUB2000_PROFILE = {
    # --- UI ---
    "label": "Zendure HUB2000",

    # --- Legacy controller tuning / fallback ---
    "TARGET_IMPORT_W": 10.0,
    "DEADBAND_W": 30.0,
    "EXPORT_GUARD_W": 80.0,
    "KP_UP": 0.65,
    "KP_DOWN": 0.90,
    "MAX_STEP_UP": 550.0,
    "MAX_STEP_DOWN": 800.0,

    # --- Shared / other tuning ---
    "KEEPALIVE_MIN_DEFICIT_W": 15.0,
    "KEEPALIVE_MIN_OUTPUT_W": 60.0,
    "SOC_DISCHARGE_RESUME_MARGIN": 3.0,

    # --- Low-SoC / cell-voltage protection behavior ---
    "LOW_SOC_PROTECTION_STRICT": False,
    "LOW_SOC_PV_CHARGE_REQUIRES_EXPORT": False,
    "LOW_SOC_DISCHARGE_REQUIRES_CELL_RESUME": False,

    # --- V4.2.0 regulation / capabilities ---
    **V42_COMMON_DEFAULTS,
    **PASSTHROUGH_DISABLED_DEFAULTS,

    # --- Charge controller tuning ---
    "CHARGE_DEADBAND_W": 30.0,
    "CHARGE_KP_UP": 0.65,
    "CHARGE_KP_DOWN": 0.90,
    "CHARGE_MAX_STEP_UP": 550.0,
    "CHARGE_MAX_STEP_DOWN": 800.0,

    # --- Discharge controller tuning ---
    "DISCHARGE_TARGET_IMPORT_W": 0.0,
    "DISCHARGE_DEADBAND_W": 30.0,
    "DISCHARGE_KP_UP": 0.65,
    "DISCHARGE_KP_DOWN": 0.90,
    "DISCHARGE_MAX_STEP_UP": 550.0,
    "DISCHARGE_MAX_STEP_DOWN": 800.0,

    # --- Hardware limits (safety clamp) ---
    "MAX_INPUT_W": 1800.0,
    "MAX_OUTPUT_W": 1200.0,
    
    "SUPPORTS_OFFGRID_SOCKET": False,
    "SUPPORTS_OFFGRID_INPUT": False,
    "OFFGRID_MAX_INTERNAL_SUPPLY_W": 0.0,
    "OFFGRID_LOAD_ACTIVE_W": 50.0,
    "OFFGRID_LOAD_BLOCKS_AC_CHARGE": False,
    "OFFGRID_INPUT_AFFECTS_ENERGY_BALANCE": False,
}


DEVICE_PROFILES = {
    "SF800Pro": SF800PRO_PROFILE,
    "SF800Pro2": SF800PRO2_PROFILE,
    "SF2400AC": SF2400AC_PROFILE,
    "SF2400AC+": SF2400ACPLUS_PROFILE,
    "SF2400Pro": SF2400PRO_PROFILE,
    "SF1600AC": SF1600AC_PROFILE,
    "Hyper 2000": HYPER2000_PROFILE,
    "HUB 2000": HUB2000_PROFILE,
}


def get_profile_config(profile_key: str) -> dict:
    return DEVICE_PROFILES.get(profile_key, DEVICE_PROFILES["SF2400AC"])


def get_profile_defaults(profile_key: str) -> dict:
    profile = get_profile_config(profile_key)
    return {
        key: value
        for key, value in profile.items()
        if key in PROFILE_OVERRIDE_FIELDS
    }


def merge_profile_with_overrides(profile_key: str, overrides: dict | None) -> dict:
    profile = dict(get_profile_config(profile_key))
    if not overrides:
        return profile

    allowed_override_keys = set(PROFILE_OVERRIDE_FIELDS) | PROFILE_MIGRATION_OVERRIDE_FIELDS

    for key in allowed_override_keys:
        if key in overrides and overrides[key] is not None:
            try:
                profile[key] = float(overrides[key])
            except (TypeError, ValueError):
                continue

    return profile
