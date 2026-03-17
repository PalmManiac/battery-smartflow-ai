SF800PRO_PROFILE = {
    # --- UI ---
    "label": "Zendure SF800Pro",

    # --- Discharge controller tuning ---
    "TARGET_IMPORT_W": 30.0,
    "DEADBAND_W": 35.0,
    "EXPORT_GUARD_W": 40.0,
    "KP_UP": 0.40,
    "KP_DOWN": 0.75,
    "MAX_STEP_UP": 250.0,
    "MAX_STEP_DOWN": 400.0,
    "KEEPALIVE_MIN_DEFICIT_W": 15.0,
    "KEEPALIVE_MIN_OUTPUT_W": 60.0,

    # --- Hardware limits (safety clamp) ---
    "MAX_INPUT_W": 1000.0,
    "MAX_OUTPUT_W": 800.0,
}


SF2400AC_PROFILE = {
    # --- UI ---
    "label": "Zendure SF2400AC",

    # --- Discharge controller tuning ---
    "TARGET_IMPORT_W": 20.0,
    "DEADBAND_W": 100.0,
    "EXPORT_GUARD_W": 100.0,
    "KP_UP": 0.45,
    "KP_DOWN": 0.55,
    "MAX_STEP_UP": 300.0,
    "MAX_STEP_DOWN": 350.0,
    "KEEPALIVE_MIN_DEFICIT_W": 20.0,
    "KEEPALIVE_MIN_OUTPUT_W": 100.0,

    # --- Hardware limits (safety clamp) ---
    "MAX_INPUT_W": 2400.0,
    "MAX_OUTPUT_W": 2400.0,
}


SF1600AC_PROFILE = {
    # --- UI ---
    "label": "Zendure SF1600AC+",

    # --- Discharge controller tuning ---
    "TARGET_IMPORT_W": 35.0,
    "DEADBAND_W": 40.0,
    "EXPORT_GUARD_W": 45.0,
    "KP_UP": 0.55,
    "KP_DOWN": 0.95,
    "MAX_STEP_UP": 300.0,
    "MAX_STEP_DOWN": 350.0,
    "KEEPALIVE_MIN_DEFICIT_W": 15.0,
    "KEEPALIVE_MIN_OUTPUT_W": 60.0,

    # --- Hardware limits (safety clamp) ---
    "MAX_INPUT_W": 1600.0,
    "MAX_OUTPUT_W": 1600.0,
}

DEVICE_PROFILES = {
    "SF800Pro": SF800PRO_PROFILE,
    "SF2400AC": SF2400AC_PROFILE,
    "SF1600AC": SF1600AC_PROFILE,
}
