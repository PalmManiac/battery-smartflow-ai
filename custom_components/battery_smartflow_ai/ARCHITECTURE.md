# Battery SmartFlow AI – Architecture

**Version:** 3.1.2 | **Last Updated:** 2026-03-15

## Overview

Battery SmartFlow AI is a **rule-based Home Assistant custom integration** for intelligent battery storage management. It monitors household state (SoC, grid power, electricity prices, PV forecast) every 10 seconds and optimizes charging/discharging decisions across multiple battery systems (Zendure AC + BYD DC).

**Core Goal:** Minimize costs via cheap-window loading, peak-price discharge, and smart bridging during expensive hours (e.g., GO tariff 00–05 cheap → 05–08 expensive).

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│   Home Assistant (HA) State Machine                      │
│   (Sensor Entities: SoC, Grid, PV, Price, Forecast)    │
└────────────────┬──────────────────────────────────────┘
                 │ (read every 10s)
                 ▼
┌─────────────────────────────────────────────────────────┐
│  ZendureSmartFlowCoordinator (coordinator.py)           │
│  ────────────────────────────────────────────────────   │
│  1. Read HA sensors → DecisionContext                   │
│  2. Apply hysteresis filters (BYD, wallbox)             │
│  3. DecisionEngine.evaluate() → action                  │
│  4. _manage_byd_night_charge() (v3.2)                   │
│  5. Write setpoints to Zendure/BYD                      │
│  6. Persist state (HA Store + entry.options)            │
└────────┬─────────────────────────────────────────────┘
         │
    ┌────┴──────────────────────────────┐
    ▼                                    ▼
┌──────────────────┐      ┌──────────────────────────┐
│ Zendure SF2400AC │      │ BYD HVS (DC) via SMA WR  │
│ - select.ac_mode │      │ - input_select (Modbus) │
│ - number.*_limit │      │ - input_number (power)  │
└──────────────────┘      └──────────────────────────┘
```

---

## Main Modules & Responsibilities

| Module | Purpose |
|--------|---------|
| **`__init__.py`** | Setup entry point, `ZendureSmartFlowCoordinator` initialization, platform setup |
| **`const.py`** | All constants, config keys, entity keys, defaults, platform list |
| **`coordinator.py`** | 10s polling loop, sensor reading, decision execution, BYD night-charge management, state persistence |
| **`decision_engine.py`** | 8-rule priority engine (Emergency → Peak → Arbitrage → Planning → Valley → PV → Summer → Manual) |
| **`sensor.py`** | Status/recommendation/profit sensors, night_charge_status enum (`charging`, `goal_reached`, `no_need`, `discharge_paused`, `inactive`) |
| **`number.py`** | User-configurable settings (SoC min/max, daytime_consumption_w ☀, nighttime_consumption_w 🌙, thresholds, etc.) |
| **`select.py`** | Mode selectors (`ai_mode`: auto/summer/winter/manual; `manual_action`: standby/charge/discharge/constant_discharge) |
| **`switch.py`** | `PvNightChargeSwitch` – Toggle PV-forecast-based night loading |
| **`config_flow.py`** | Initial setup wizard, entity/battery config validation |
| **`device_profiles.py`** | Zendure model profiles (SF2400AC, SF800Pro) with capacity/power limits |

---

## Entity Types & Platforms

Detaillierte Entity-Dokumentation → **ENTITY_REGISTRY.md**

Kurz:
- **SENSOR:** Status, AI Status, Recommendation, Profit, Night Charge Status
- **NUMBER:** SoC min/max, Max Charge/Discharge, Price Thresholds, Daytime/Nighttime Consumption
- **SELECT:** AI Mode, Manual Action
- **SWITCH:** PV Night Loading

---

## Coordinator Data Flow (10s Cycle)

```python
async _async_update_data():
    # 1. Read all input sensors
    soc_z = float(HA state: zendure_soc)
    soc_b = float(HA state: byd_soc)
    soc_limit = float(HA state: soc_limit_entity)
    pv_w = float(HA state: pv_power)
    grid_w = float(HA state: grid_power)
    price_eur = float(HA state: price_now)
    pv_forecast_kwh = float(HA state: pv_forecast)  # [v3.2]

    # 2. Apply hysteresis filters (prevent fluttering)
    byd_discharge_active = _hys_byd_discharge.update(byd_power, now)
    wallbox_charging = _hys_wallbox_grid.update(wallbox_power, now)

    # 3. Build DecisionContext
    ctx = DecisionContext(
        soc_z, soc_b, capacity_z, capacity_b,
        pv_w, grid_w, soc_limit,
        price_eur, price_export_data[],
        is_night=(00:00 <= hour < 05:00),
        ai_mode, manual_action,
        ...
    )

    # 4. Evaluate decision rules
    decision = engine.evaluate(ctx)
    # → (action, ai_status, recommendation, reason_text)

    # 5. Manage BYD night charging (v3.2)
    _manage_byd_night_charge():
        if 00:00 <= now < 05:00 and pv_forecast_enabled:
            # Calculate night-load plan
            nighttime_kwh = nighttime_w * (5.0 - now.hour - now.minute/60) / 1000
            target_total = bridge_kwh + nighttime_kwh + max(0, daily_kwh - pv_for_battery)
            charge_needed = max(0, target_total - total_available)

            # Prioritize Zendure, then BYD
            z_charge = min(z_capacity_gap, charge_needed)
            byd_charge = max(0, charge_needed - z_charge)

            # If BYD usable ≤ bridge → "Akku Pause" (freeze, prevent discharge)
            if byd_usable <= bridge_kwh:
                set_byd_mode("Akku Pause")
                _byd_discharge_paused = True
            else:
                set_byd_mode("Akku schnell laden" or "Akku automatisch")
        else:
            if _byd_night_active or _byd_discharge_paused:
                set_byd_mode("Akku automatisch")  # Resume

    # 6. Execute on Zendure (service calls)
    if decision.zendure_mode != current_mode:
        await hass.services.call("select", "select_option",
            {"entity_id": ac_mode_entity, "option": decision.zendure_mode})
    if decision.zendure_input_w != current_input:
        await hass.services.call("number", "set_value",
            {"entity_id": input_limit_entity, "value": decision.zendure_input_w})

    # 7. Update entity states (sensors, numbers, switches)
    self.async_set_updated_data({
        "soc_z": soc_z,
        "soc_b": soc_b,
        "ai_status": decision.ai_status,
        "recommendation": decision.recommendation,
        "night_charge_status": night_plan.status,
        "profit_eur": self._persist["profit_eur"],
        ...
    })
```

---

## External Input Entities

Required input entities → **ENTITY_REGISTRY.md**

Quick: Zendure (SoC, Mode, Limits), Grid Power, PV Power, Price Sensor, + optional BYD/PV-Forecast/Wallbox

---

## State Persistence

### HA Store (survives HA restart)
```python
_persist = {
    "night_plan": {              # Nightly load plan
        "status": str,           # "charging" | "goal_reached" | "no_need" | "discharge_paused"
        "z_target_soc": float,   # Zendure goal (%)
        "b_target_soc": float,   # BYD goal (%)
        "z_charge_kwh": float,   # Zendure energy to load (kWh)
        "b_charge_kwh": float,   # BYD energy to load (kWh)
    },
    "trade_avg_charge_price": float,  # Arbitrage avg buy price (€/kWh)
    "profit_eur": float,              # Cumulative gain
    "season_mode": str,               # "winter" | "summer"
    "power_state": str,               # "idle" | "charging" | "discharging"
}
```

### entry.options (HA config store, survives restart)
```python
entry.options = {
    "soc_min": 12.0,
    "soc_max": 100.0,
    "max_charge": 2400,
    "max_discharge": 700,
    "price_threshold": 0.35,
    "very_expensive_threshold": 0.49,
    "emergency_soc": 8.0,
    "emergency_charge": 1200,
    "profit_margin_pct": 27,
    "valley_factor": 0.85,
    "peak_factor": 1.35,
    "pv_forecast_enabled": 1.0,        # [v3.2]
    "daytime_consumption_w": 500.0,    # [v3.2]
    "nighttime_consumption_w": 500.0,  # [v3.2]
}
```

### Runtime (in-memory, lost on HA restart)
```python
_byd_night_active: bool        # Night load sequence running
_byd_discharge_paused: bool    # BYD frozen ("Akku Pause")
_hys_byd_charge, _hys_byd_discharge: _HysteresisState
_hys_wallbox_grid, _hys_wallbox_pv: _HysteresisState
```

---

## Decision Engine Priority Rules

1. **Emergency** – If `soc ≤ emergency_soc` → force max charge (preempt all)
2. **Peak** – If `price > very_expensive OR adaptive_peak` → max discharge
3. **Arbitrage** – If `price > avg_charge + margin` → discharge for profit
4. **Planning** – Cheap window detected + peak coming → load now
5. **ValleyBoost** – Winter + price in valley → charge at discount
6. **PvRule** – PV surplus available → use for battery/grid
7. **SummerRule** – Summer mode + house deficit → charge from grid
8. **ManualRule** – Explicit user `ai_mode=manual` action
9. *(Idle)* – No rule matches → standby

Each rule checks its conditions in sequence; first match executes.

---

## BYD Night Charge Logic (v3.2)

**Time Window:** 00:00 → 05:00 (cheap window for GO tariff)

**States:**
- `charging` – BYD actively loading (mode="Akku schnell laden")
- `goal_reached` – BYD at target SoC (mode="Akku automatisch")
- `no_need` – Sufficient energy for bridge (mode="Akku automatisch")
- `discharge_paused` – BYD frozen to protect bridge (mode="Akku Pause")
- `inactive` – Outside time window or feature disabled

**Load Formula:**
```
pv_for_battery = max(0, pv_forecast_kwh - daytime_consumption_w*10h/1000)
nighttime_kwh  = nighttime_consumption_w/1000 * max(0, 5.0 - now.hour - now.minute/60)
target_total   = bridge_kwh + nighttime_kwh + max(0, daily_kwh - pv_for_battery)
charge_needed  = max(0, target_total - total_available)

z_charge = min(z_capacity_gap, charge_needed)    # Zendure first
byd_charge = max(0, charge_needed - z_charge)    # BYD remainder
```

**Threshold Table** (defaults: 500W daytime, 500W nighttime):
| PV Forecast | Zendure Load | BYD Load | Z Goal | B Goal |
|---|---|---|---|---|
| 0–5 kWh | 5.51 kWh | 10.0 kWh | 100% | 100% |
| 7 kWh | 5.51 kWh | 8.5 kWh | 100% | 85% |
| 10 kWh | 5.51 kWh | 5.5 kWh | 100% | 55% |
| 15 kWh | 5.51 kWh | 0.5 kWh | 100% | 5% |
| ≥17 kWh | 4.0 kWh | 0.0 kWh | 74% | 0% |

---

## Important Constraints & Caveats

### Zendure Control
- Controlled via HA `select` (AC mode) + `number` (W limits) entities
- Service calls: `select.select_option`, `number.set_value`
- No direct device API; depends on Zendure HA integration

### BYD Control
- **Indirect via Modbus TCP** → SMA WR → input_select (HA automation "Akkusteuerung")
- Only works if `additional_battery_mode_entity` configured
- Modbus writes minimized: ~0–2 per night (via `_byd_discharge_paused` state guard)
- Three modes: "Akku schnell laden" (charge), "Akku automatisch" (discharge allowed), "Akku Pause" (freeze)

### Hysteresis Filters
- **BYD charge/discharge:** Prevents rapid mode-switching on power fluctuations
- **Wallbox:** `delay_off = 300s` (prevent premature stop on short pauses)
- Thresholds hardcoded to 80W with configurable delays

### Night Charge Availability
- Requires `pv_forecast_entity` configured
- Requires `additional_battery_mode_entity` + capacity config
- Toggle via `switch.pv_nachtladung` (stored in `entry.options`)
- Disabled outside 00:00–05:00 or if feature flag off

### Price Data
- Depends on `price_export_entity` for multi-hour forecast (Tibber API)
- If unavailable, falls back to "PV only" rules (no arbitrage)
- Peak-price detection adaptive based on price history

### Restart Behavior
- `entry.options` restored on HA restart (user settings persist)
- `_persist` dict restored from HA Store
- Runtime hysteresis + night-charge flags reset (can cause transient modeswitch on restart)

---

## Debug Checklist

- [ ] Check `sensor.battery_smartflow_ai_status` – integration healthy?
- [ ] Check `sensor.battery_smartflow_ai_ai_status` – which rule is active?
- [ ] Check `sensor.battery_smartflow_ai_night_charge_status` – BYD load state?
- [ ] Check `number.battery_smartflow_ai_daytime_consumption_w` (☀) + `nighttime_consumption_w` (🌙) – correct household draw?
- [ ] Check `switch.battery_smartflow_ai_pv_nachtladung` – feature enabled?
- [ ] Verify `pv_forecast_entity` has valid kWh value (check HA History)
- [ ] Check HA logs for `DecisionEngine` rule flow (`_LOGGER.debug()`)
- [ ] Verify Zendure/BYD `select`/`number` entities respond to service calls
- [ ] If BYD not charging: check `input_select.akku_steuerung_sma_wr` state (Modbus lag?)

---

## Files Reference

| File | Lines | Purpose |
|------|-------|---------|
| `const.py` | 230 | Constants, config keys, entity keys, defaults |
| `__init__.py` | 57 | Setup, config migration |
| `coordinator.py` | ~1800 | Main loop, `_manage_byd_night_charge()`, sensor reading |
| `decision_engine.py` | ~700 | Rule evaluation, DecisionContext |
| `sensor.py` | ~500 | Status sensors |
| `number.py` | ~300 | User settings |
| `select.py` | ~150 | Mode selectors |
| `switch.py` | ~100 | PV night-load toggle |
| `config_flow.py` | ~500 | Setup wizard |
