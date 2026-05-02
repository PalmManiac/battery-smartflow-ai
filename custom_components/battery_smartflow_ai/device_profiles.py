from __future__ import annotations

PROFILE_OVERRIDE_FIELDS = {
    "TARGET_IMPORT_W": {
        "label": "Ziel-Netzbezug",
        "min": 0.0,
        "max": 300.0,
        "step": 5.0,
        "unit": "W",
        "icon": "mdi:transmission-tower-import",
    },
    "DEADBAND_W": {
        "label": "Deadband (Legacy)",
        "min": 0.0,
        "max": 200.0,
        "step": 5.0,
        "unit": "W",
        "icon": "mdi:arrow-expand-horizontal",
    },
    "EXPORT_GUARD_W": {
        "label": "Export-Schutz",
        "min": 0.0,
        "max": 300.0,
        "step": 5.0,
        "unit": "W",
        "icon": "mdi:shield-outline",
    },
    "KP_UP": {
        "label": "KP Hochregeln (Legacy)",
        "min": 0.10,
        "max": 2.00,
        "step": 0.01,
        "unit": "",
        "icon": "mdi:chart-line-variant",
    },
    "KP_DOWN": {
        "label": "KP Runterregeln (Legacy)",
        "min": 0.10,
        "max": 2.00,
        "step": 0.01,
        "unit": "",
        "icon": "mdi:chart-line-variant",
    },
    "MAX_STEP_UP": {
        "label": "Max. Schritt Hochregeln (Legacy)",
        "min": 50.0,
        "max": 2000.0,
        "step": 10.0,
        "unit": "W",
        "icon": "mdi:arrow-up-bold",
    },
    "MAX_STEP_DOWN": {
        "label": "Max. Schritt Runterregeln (Legacy)",
        "min": 50.0,
        "max": 2000.0,
        "step": 10.0,
        "unit": "W",
        "icon": "mdi:arrow-down-bold",
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

# Optional: diese Felder sollen zwar sichtbar, aber nicht editierbar sein
PROFILE_FIXED_FIELDS = {
    "MAX_INPUT_W",
    "MAX_OUTPUT_W",
}

SF800PRO_PROFILE = {
    # --- UI ---
    "label": "Zendure SF800Pro",

    # --- Legacy controller tuning ---
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

    # --- SF800Pro-specific PV routing behavior ---
    # Some SF800Pro setups without P1 / smart meter do not route PV neutrally
    # in idle/output 0. This passthrough pulls PV towards house load.
    "PV_HOUSELOAD_PASSTHROUGH": True,
    "PV_HOUSELOAD_PASSTHROUGH_HOLD_SECONDS": 90.0,
    "PV_HOUSELOAD_PASSTHROUGH_MIN_PV_W": 120.0,
    "PV_HOUSELOAD_PASSTHROUGH_MIN_HOUSE_LOAD_W": 120.0,
    "PV_HOUSELOAD_PASSTHROUGH_EXPORT_STOP_CYCLES": 6,

    # --- SF800Pro-specific PV charge latch ---
    "PV_CHARGE_LATCH_HOLD_SECONDS": 180.0,
    "PV_CHARGE_LATCH_STOP_CYCLES": 12,
    
    # --- Charge controller tuning ---
    "CHARGE_DEADBAND_W": 35.0,
    "CHARGE_KP_UP": 0.40,
    "CHARGE_KP_DOWN": 0.75,
    "CHARGE_MAX_STEP_UP": 250.0,
    "CHARGE_MAX_STEP_DOWN": 400.0,

    # --- Discharge controller tuning ---
    "DISCHARGE_DEADBAND_W": 35.0,
    "DISCHARGE_KP_UP": 0.40,
    "DISCHARGE_KP_DOWN": 0.75,
    "DISCHARGE_MAX_STEP_UP": 250.0,
    "DISCHARGE_MAX_STEP_DOWN": 400.0,

    # --- Hardware limits (safety clamp) ---
    "MAX_INPUT_W": 1000.0,
    "MAX_OUTPUT_W": 800.0,
}

SF2400AC_PROFILE = {
    # --- UI ---
    "label": "Zendure SF2400AC",

    # --- Legacy controller tuning ---
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

    # --- SF800Pro-specific PV routing behavior ---
    "PV_HOUSELOAD_PASSTHROUGH": False,
    "PV_HOUSELOAD_PASSTHROUGH_HOLD_SECONDS": 0.0,
    "PV_HOUSELOAD_PASSTHROUGH_MIN_PV_W": 0.0,
    "PV_HOUSELOAD_PASSTHROUGH_MIN_HOUSE_LOAD_W": 0.0,
    "PV_HOUSELOAD_PASSTHROUGH_EXPORT_STOP_CYCLES": 0,

    # --- SF800Pro-specific PV charge latch ---
    "PV_CHARGE_LATCH_HOLD_SECONDS": 0.0,
    "PV_CHARGE_LATCH_STOP_CYCLES": 0,

    # --- Charge controller tuning ---
    "CHARGE_DEADBAND_W": 30.0,
    "CHARGE_KP_UP": 0.65,
    "CHARGE_KP_DOWN": 0.90,
    "CHARGE_MAX_STEP_UP": 550.0,
    "CHARGE_MAX_STEP_DOWN": 800.0,

    # --- Discharge controller tuning ---
    "DISCHARGE_DEADBAND_W": 30.0,
    "DISCHARGE_KP_UP": 0.65,
    "DISCHARGE_KP_DOWN": 0.90,
    "DISCHARGE_MAX_STEP_UP": 550.0,
    "DISCHARGE_MAX_STEP_DOWN": 800.0,

    # --- Hardware limits (safety clamp) ---
    "MAX_INPUT_W": 2400.0,
    "MAX_OUTPUT_W": 2400.0,
}

SF2400PRO_PROFILE = {
    # --- UI ---
    "label": "Zendure SF2400Pro",

    # --- Legacy controller tuning ---
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

    # --- SF800Pro-specific PV routing behavior ---
    "PV_HOUSELOAD_PASSTHROUGH": False,
    "PV_HOUSELOAD_PASSTHROUGH_HOLD_SECONDS": 0.0,
    "PV_HOUSELOAD_PASSTHROUGH_MIN_PV_W": 0.0,
    "PV_HOUSELOAD_PASSTHROUGH_MIN_HOUSE_LOAD_W": 0.0,
    "PV_HOUSELOAD_PASSTHROUGH_EXPORT_STOP_CYCLES": 0,

    # --- SF800Pro-specific PV charge latch ---
    "PV_CHARGE_LATCH_HOLD_SECONDS": 0.0,
    "PV_CHARGE_LATCH_STOP_CYCLES": 0,

    # --- Charge controller tuning ---
    "CHARGE_DEADBAND_W": 30.0,
    "CHARGE_KP_UP": 0.65,
    "CHARGE_KP_DOWN": 0.90,
    "CHARGE_MAX_STEP_UP": 550.0,
    "CHARGE_MAX_STEP_DOWN": 800.0,

    # --- Discharge controller tuning ---
    "DISCHARGE_DEADBAND_W": 30.0,
    "DISCHARGE_KP_UP": 0.65,
    "DISCHARGE_KP_DOWN": 0.90,
    "DISCHARGE_MAX_STEP_UP": 550.0,
    "DISCHARGE_MAX_STEP_DOWN": 800.0,

    # --- Hardware limits (safety clamp) ---
    "MAX_INPUT_W": 2400.0,
    "MAX_OUTPUT_W": 2400.0,
}

SF1600AC_PROFILE = {
    # --- UI ---
    "label": "Zendure SF1600AC+",

    # --- Legacy controller tuning ---
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

    # --- SF800Pro-specific PV routing behavior ---
    "PV_HOUSELOAD_PASSTHROUGH": False,
    "PV_HOUSELOAD_PASSTHROUGH_HOLD_SECONDS": 0.0,
    "PV_HOUSELOAD_PASSTHROUGH_MIN_PV_W": 0.0,
    "PV_HOUSELOAD_PASSTHROUGH_MIN_HOUSE_LOAD_W": 0.0,
    "PV_HOUSELOAD_PASSTHROUGH_EXPORT_STOP_CYCLES": 0,

    # --- SF800Pro-specific PV charge latch ---
    "PV_CHARGE_LATCH_HOLD_SECONDS": 0.0,
    "PV_CHARGE_LATCH_STOP_CYCLES": 0,

    # --- Charge controller tuning ---
    "CHARGE_DEADBAND_W": 40.0,
    "CHARGE_KP_UP": 0.55,
    "CHARGE_KP_DOWN": 0.95,
    "CHARGE_MAX_STEP_UP": 450.0,
    "CHARGE_MAX_STEP_DOWN": 900.0,

    # --- Discharge controller tuning ---
    "DISCHARGE_DEADBAND_W": 40.0,
    "DISCHARGE_KP_UP": 0.55,
    "DISCHARGE_KP_DOWN": 0.95,
    "DISCHARGE_MAX_STEP_UP": 450.0,
    "DISCHARGE_MAX_STEP_DOWN": 900.0,

    # --- Hardware limits (safety clamp) ---
    "MAX_INPUT_W": 1600.0,
    "MAX_OUTPUT_W": 1600.0,
}

HYPER2000_PROFILE = {
    # --- UI ---
    "label": "Zendure Hyper 2000",

    # --- Legacy controller tuning ---
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

    # --- SF800Pro-specific PV routing behavior ---
    "PV_HOUSELOAD_PASSTHROUGH": False,
    "PV_HOUSELOAD_PASSTHROUGH_HOLD_SECONDS": 0.0,
    "PV_HOUSELOAD_PASSTHROUGH_MIN_PV_W": 0.0,
    "PV_HOUSELOAD_PASSTHROUGH_MIN_HOUSE_LOAD_W": 0.0,
    "PV_HOUSELOAD_PASSTHROUGH_EXPORT_STOP_CYCLES": 0,

    # --- SF800Pro-specific PV charge latch ---
    "PV_CHARGE_LATCH_HOLD_SECONDS": 0.0,
    "PV_CHARGE_LATCH_STOP_CYCLES": 0,

    # --- Charge controller tuning ---
    "CHARGE_DEADBAND_W": 30.0,
    "CHARGE_KP_UP": 0.65,
    "CHARGE_KP_DOWN": 0.90,
    "CHARGE_MAX_STEP_UP": 550.0,
    "CHARGE_MAX_STEP_DOWN": 800.0,

    # --- Discharge controller tuning ---
    "DISCHARGE_DEADBAND_W": 30.0,
    "DISCHARGE_KP_UP": 0.65,
    "DISCHARGE_KP_DOWN": 0.90,
    "DISCHARGE_MAX_STEP_UP": 550.0,
    "DISCHARGE_MAX_STEP_DOWN": 800.0,

    # --- Hardware limits (safety clamp) ---
    "MAX_INPUT_W": 1200.0,
    "MAX_OUTPUT_W": 1200.0,
}

HUB2000_PROFILE = {
    # --- UI ---
    "label": "Zendure HUB2000",

    # --- Legacy controller tuning ---
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

    # --- SF800Pro-specific PV routing behavior ---
    "PV_HOUSELOAD_PASSTHROUGH": False,
    "PV_HOUSELOAD_PASSTHROUGH_HOLD_SECONDS": 0.0,
    "PV_HOUSELOAD_PASSTHROUGH_MIN_PV_W": 0.0,
    "PV_HOUSELOAD_PASSTHROUGH_MIN_HOUSE_LOAD_W": 0.0,
    "PV_HOUSELOAD_PASSTHROUGH_EXPORT_STOP_CYCLES": 0,

    # --- SF800Pro-specific PV charge latch ---
    "PV_CHARGE_LATCH_HOLD_SECONDS": 0.0,
    "PV_CHARGE_LATCH_STOP_CYCLES": 0,

    # --- Charge controller tuning ---
    "CHARGE_DEADBAND_W": 30.0,
    "CHARGE_KP_UP": 0.65,
    "CHARGE_KP_DOWN": 0.90,
    "CHARGE_MAX_STEP_UP": 550.0,
    "CHARGE_MAX_STEP_DOWN": 800.0,

    # --- Discharge controller tuning ---
    "DISCHARGE_DEADBAND_W": 30.0,
    "DISCHARGE_KP_UP": 0.65,
    "DISCHARGE_KP_DOWN": 0.90,
    "DISCHARGE_MAX_STEP_UP": 550.0,
    "DISCHARGE_MAX_STEP_DOWN": 800.0,

    # --- Hardware limits (safety clamp) ---
    "MAX_INPUT_W": 1800.0,
    "MAX_OUTPUT_W": 1200.0,
}

DEVICE_PROFILES = {
    "SF800Pro": SF800PRO_PROFILE,
    "SF2400AC": SF2400AC_PROFILE,
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

    for key in PROFILE_OVERRIDE_FIELDS:
        if key in overrides and overrides[key] is not None:
            try:
                profile[key] = float(overrides[key])
            except (TypeError, ValueError):
                continue

    return profile
