# BSFAI and Zendure sensor catalog

This appendix lists sensors created by the integration. BSFAI calculation and status sensors are separate from Zendure hardware readings.

## Home & grid

| Sensor | Meaning | `key` |
|---|---|---|
| Grid power | Grid power reported by the configured meter. | `grid_power` |
| Shelly grid phase A power | Grid power on phase A reported by Shelly Pro 3EM. | `grid_phase_a_power` |
| Shelly grid phase B power | Grid power on phase B reported by Shelly Pro 3EM. | `grid_phase_b_power` |
| Shelly grid phase C power | Grid power on phase C reported by Shelly Pro 3EM. | `grid_phase_c_power` |
| House load | Shows household consumption calculated from grid power, PV power, and battery flow. | `house_load` |

## Status & control

| Sensor | Meaning | `key` |
|---|---|---|
| Native Zendure test status | Shows “Native Zendure test status” for native Zendure observation or control.<br>States: Not configured — function disabled; Discovering devices; Connecting; Capturing initial data; Observation active; Error — error detected. | `native_zendure_status` |
| Native Zendure control | Shows “Native Zendure control” for native Zendure observation or control.<br>States: Disabled; No data; Cloud; Cloud; ZenSDK; Local; Not supported. | `native_zendure_control` |
| Native Zendure devices found | Shows “Native Zendure devices found” for native Zendure observation or control. | `native_zendure_device_count` |
| Native Zendure messages received | Shows “Native Zendure messages received” for native Zendure observation or control. | `native_zendure_message_count` |
| Last native Zendure message | Shows “Last native Zendure message” for native Zendure observation or control. | `native_zendure_last_message` |
| Native Zendure initial-sync package | Shows “Native Zendure initial-sync package” for native Zendure observation or control. | `native_zendure_last_capture` |
| Native Zendure error | Shows “Native Zendure error” for native Zendure observation or control. | `native_zendure_error` |
| Zendure hardware connection | Shows “Zendure hardware connection” for native Zendure observation or control.<br>States: Online — device reachable; Connection unstable; Offline — device unreachable; Direct check unavailable; Unknown — status unknown. | `native_zendure_watchdog` |
| Active device profile | Device profile used for the system. | `device_profile` |
| Adaptive peak detected | Whether an adaptive price peak was detected.<br>States: No — inactive; Yes — active. | `adaptive_peak_active` |
| Charge strategy | Charging strategy currently in use.<br>States: No special charge strategy active — no strategy active; PV surplus charging — charging from PV surplus; Price charging at latest start time; Price charging due to poor PV forecast; Price charging with mixed PV forecast; Price charging due to weak live PV despite good forecast; Very-cheap threshold: maximum charging; Price valley charging; Price valley charging, reduced due to forecast; Emergency charging; Manual charge strategy — manual setting; Opportunistic valley charging; Opportunistic valley charging with mixed forecast; Learned charge-window planning; Strategic peak reserve. | `charge_strategy` |
| Full-charge maintenance | State of planned full-charge maintenance.<br>States: Unknown — status unknown; Not due; Due soon — maintenance is due soon; Due — maintenance is due; Waiting for favorable window; Charging to full; Confirming full charge; Completed — maintenance completed; Blocked — maintenance cannot currently run. | `full_charge_maintenance_state` |
| Full-charge maintenance active | Whether full-charge maintenance is active.<br>States: Yes — active; No — inactive. | `full_charge_maintenance_active` |
| Next recommended full charge | Time of the next recommended full charge. | `full_charge_maintenance_next_recommended` |
| Engine status | Readiness and detected input-data errors.<br>States: System normal; No price data available; No current electricity price; Invalid sensor data. | `engine_health` |
| Control context | Current regulation context (price, PV, or manual).<br>States: Price; PV; Manual — manual setting. | `season_mode` |
| Hardware SoC limit status | Detected hardware SoC-limit state.<br>States: Hardware SoC limit state unavailable — feature not configured; No limit active; Upper SoC limit active (charging blocked); Lower SoC limit active (discharging blocked). | `soc_limit_status` |
| Fault status | Summary severity of detected faults.<br>States: No fault / everything normal — normal operation; Warning (device continues running); Fault / protection active — error detected. | `fault_level_status` |
| System status | Overall state of BSFAI regulation.<br>States: Initialization; OK; Invalid sensor data; Invalid price data. | `status` |
| AI status | State of AI-assisted regulation.<br>States: Ready; Charging (PV surplus); Charging (price advantage); Discharging (cover house load); Discharging (high electricity price); Forced discharge (extreme prices); Emergency charge active; Manual mode — manual setting. | `ai_status` |
| AI recommendation | Current regulation recommendation.<br>States: No action; Charging — battery charging; Discharging — battery discharging; Emergency charging. | `recommendation` |
| Decision reason | Reason for the current regulation decision.<br>States: Ready; No demand detected; Discharging started (demand detected); Discharging active (house load coverage); Charging started (surplus detected); Charging active; Discharging due to high electricity price; Forced discharge due to extreme price peak; Emergency charge active (latched); Autarky: cover house load; Charge PV surplus; Discharge stopped (SoC minimum reached); SF800Pro: PV house-load passthrough active; Charging blocked (upper SoC limit active); Discharging blocked (lower SoC limit active); Manual mode active; Manual standby; Manual charging; Manual discharging; Constant discharge active; Manual ready; Ready — no charging or discharging; Discharging due to price peak; Price-based discharging; Price valley detected. Maximum charging; Price charging started (latest meaningful start time reached); Price charging due to poor PV forecast; Price charging with mixed PV forecast; Learned charge planning not ready yet; Learned charge planning waits for optimal charge window; Learned charge window active; AC charge binding active; AC charge binding waiting for price window; Learned planning: latest start time reached; Learned planning: no recharge required; Price valley used because real PV is barely available; Price valley used with mixed forecast and weak real PV; Price valley detected, but reduced due to mixed PV forecast; Price charging started: real PV too weak despite good forecast; Very-cheap threshold reached: maximum charging active; Additional battery charging: discharging blocked; Additional battery discharging: charging blocked; Discharging blocked (re-enable threshold not reached yet); Discharging blocked (cell-voltage protection active); Emergency charge active (cell voltage critical); PV charging blocked because discharging is still blocked by SoC/cell protection; Learned planning: deadline too close, start now; Safe idle: battery SoC is invalid; Safe idle: native battery capacity is unavailable; Safe idle: grid sensor data is unavailable; Discharge temporarily held during a grid sensor gap; Safe idle: configured SoC limits are invalid; Safe idle: configured power limits are invalid; Discharging blocked: cell-voltage sensor is unavailable; Island socket active: automatic grid charging blocked; Island socket active: supplied by battery/PV; Automatic: securing high-price window; Automatic: holding battery reserve for later price peak. | `decision_reason` |
| Next action | Next planned action and its state.<br>States: No action — no strategy active; Planned charging; Planned discharge; Charging active; Discharging active; Manual charging; Manual discharging; Constant discharge active; Emergency charging; SF800Pro: PV house-load passthrough active; Discharge allowed – waiting for grid import. | `next_action_state` |
| Next action start time | Scheduled time of the next action. | `next_action_time` |

## PV forecast

| Sensor | Meaning | `key` |
|---|---|---|
| Forecast status | Shows PV energy expected to remain usable after household use and system losses for Forecast status.<br>States: Not configured — feature not configured; No forecast data available — data unavailable; Forecast data available — data available. | `forecast_status` |
| PV outlook | Summary of the expected PV outlook.<br>States: Unknown — status unknown; Poor — poor PV outlook; Mixed — mixed PV outlook; Good — good PV outlook. | `pv_outlook` |
| Usable PV forecast remaining today | Shows PV energy expected to remain usable after household use and system losses for Usable PV forecast remaining today. | `forecast_remaining_today_kwh` |
| Usable PV forecast tomorrow | Shows PV energy expected to remain usable after household use and system losses for Usable PV forecast tomorrow. | `forecast_tomorrow_kwh` |
| Usable PV forecast next 3 hours | Shows PV energy expected to remain usable after household use and system losses for Usable PV forecast next 3 hours. | `forecast_next_3h_kwh` |
| Usable PV forecast next 6 hours | Shows PV energy expected to remain usable after household use and system losses for Usable PV forecast next 6 hours. | `forecast_next_6h_kwh` |
| Gross PV forecast remaining today | Shows the gross PV forecast before BSFAI adjustments for Gross PV forecast remaining today. | `forecast_gross_remaining_today_kwh` |
| Gross PV forecast tomorrow | Shows the gross PV forecast before BSFAI adjustments for Gross PV forecast tomorrow. | `forecast_gross_tomorrow_kwh` |
| Gross PV forecast next 3 hours | Shows the gross PV forecast before BSFAI adjustments for Gross PV forecast next 3 hours. | `forecast_gross_next_3h_kwh` |
| Gross PV forecast next 6 hours | Shows the gross PV forecast before BSFAI adjustments for Gross PV forecast next 6 hours. | `forecast_gross_next_6h_kwh` |

## Learning-based charging plan

| Sensor | Meaning | `key` |
|---|---|---|
| Charge planning: Learning status | Shows the value “Charge planning: Learning status” calculated by the learning model.<br>States: Not started yet; Collecting data; Not enough learning data; Ready — operating data available; Active — function is active. | `learned_planning_status` |
| Charge planning: Mode | Shows the value “Charge planning: Mode” calculated by the learning model.<br>States: Disabled — function disabled; Collecting data; Classic planning; Learned planning ready — operating data available; Learned planning waiting for charge window; Learned planning active — battery charging; Classic planning; Learned planning waiting for charge window; Learned planning active. | `learned_planning_mode` |
| Charge planning: Planned charge start | Shows the value “Charge planning: Planned charge start” calculated by the learning model. | `learned_planning_optimal_charge_start` |
| Charge planning: Deadline | Shows the value “Charge planning: Deadline” calculated by the learning model. | `learned_planning_deadline` |
| Charge planning: Recharge energy | Shows the value “Charge planning: Recharge energy” calculated by the learning model. | `learned_planning_required_charge_energy_kwh` |
| Charge planning: Window size | Shows the value “Charge planning: Window size” calculated by the learning model. | `learned_planning_effective_window_minutes` |

## Prices & economics

| Sensor | Meaning | `key` |
|---|---|---|
| Prices – Dynamic daily average | Shows the price value or threshold “Prices – Dynamic daily average” calculated by BSFAI. | `price_daily_average` |
| Prices – Current peak threshold | Shows the price value or threshold “Prices – Current peak threshold” calculated by BSFAI. | `current_peak_threshold` |
| Prices – Current valley threshold | Shows the price value or threshold “Prices – Current valley threshold” calculated by BSFAI. | `current_valley_threshold` |
| Prices – Economic discharge threshold | Shows the price value or threshold “Prices – Economic discharge threshold” calculated by BSFAI. | `economic_discharge_threshold` |
| Prices – Effective discharge threshold | Shows the price value or threshold “Prices – Effective discharge threshold” calculated by BSFAI. | `effective_discharge_threshold` |
| Current – Import price | Current grid import price. | `price_now` |
| Current – Export price | Feed-in tariff currently used by BSFAI. | `feed_in_tariff` |
| Current – Applied battery charge price | Shows the price BSFAI assigns to current charging for its ongoing calculation. | `charge_price_applied` |
| Prices – Current avg. charge price (estimated) | Shows the estimated average charging cost for the current SoC cycle. | `avg_charge_price` |
| Prices – Avg. grid charging price | Shows the quantity- or energy-weighted average for “Prices – Avg. grid charging price”. | `economics_average_grid_charge_price` |
| Prices – Avg. PV opportunity value | Shows the quantity- or energy-weighted average for “Prices – Avg. PV opportunity value”. | `economics_average_pv_opportunity_value` |
| Prices – Avg. total charge price (grid + PV) | Shows the quantity- or energy-weighted average for “Prices – Avg. total charge price (grid + PV)”. | `economics_average_battery_charge_price` |
| Prices – Avg. export price | Shows the quantity- or energy-weighted average for “Prices – Avg. export price”. | `economics_average_export_price` |
| Prices – Avg. battery discharge value | Shows the quantity- or energy-weighted average for “Prices – Avg. battery discharge value”. | `economics_average_battery_discharge_value` |
| Prices – Avg. PV to Home Return | Shows the quantity- or energy-weighted average for “Prices – Avg. PV to Home Return”. | `economics_average_native_pv_to_home_return` |

## Cell-voltage protection

| Sensor | Meaning | `key` |
|---|---|---|
| Global lowest cell voltage | Lowest detected cell voltage across monitored packs. | `global_lowest_cell_voltage` |
| Cell-voltage emergency charge active | Whether cell-voltage protection requests emergency charging.<br>States: No — inactive; Yes — active. | `cell_voltage_emergency_active` |
| Discharge blocked by cell-voltage protection | Whether cell-voltage protection blocks discharge.<br>States: No — inactive; Yes — active. | `cell_voltage_discharge_blocked` |
| SoC / cell voltage plausibility | Plausibility assessment of SoC and cell voltage.<br>States: Plausible — normal operation; Noticeable; Critically implausible; Not available. | `cell_voltage_soc_plausibility` |
| Cell-voltage status | Cell-voltage protection state.<br>States: Disabled — function disabled; Normal — normal operation; Warning range active; Discharge cutoff active; Invalid sensor data. | `cell_voltage_status` |

## Debug recording

| Sensor | Meaning | `key` |
|---|---|---|
| Debug recording active | Shows the status or result of the time-limited debug recording.<br>States: No — inactive; Yes — active. | `debug_recording_active` |
| Debug recording ends at | Shows the status or result of the time-limited debug recording. | `debug_recording_ends_at` |
| Debug samples recorded | Shows the status or result of the time-limited debug recording. | `debug_sample_count` |
| Last debug package | Shows the status or result of the time-limited debug recording. | `debug_last_package` |
| Last debug error | Shows the status or result of the time-limited debug recording. | `debug_last_error` |

## Regulation training

| Sensor | Meaning | `key` |
|---|---|---|
| Regulation training active | Shows the status, amount, or result of the optional regulation-training data.<br>States: No — inactive; Yes — active. | `regulation_training_active` |
| Regulation training samples | Shows the status, amount, or result of the optional regulation-training data. | `regulation_training_sample_count` |
| Saved training sessions | Shows the status, amount, or result of the optional regulation-training data. | `regulation_training_saved_sessions` |
| Regulation training result | Shows the status, amount, or result of the optional regulation-training data.<br>States: Not trained; Training in progress; Shadow candidate available; No safe improvement found; More training data needed; Interrupted – partial data saved. | `regulation_training_result` |

## Energy & balance

| Sensor | Meaning | `key` |
|---|---|---|
| Balance since start – Legacy trading profit | Shows the economic surplus calculated since the start of the ledger. | `profit_eur` |
| Balance today – Grid charging cost | Shows the calculated monetary amount for “Balance today – Grid charging cost”. | `economics_daily_grid_charge_cost` |
| Balance today – PV opportunity cost | Shows the calculated monetary amount for “Balance today – PV opportunity cost”. | `economics_daily_pv_opportunity_cost` |
| Balance today – Export revenue | Shows the calculated monetary amount for “Balance today – Export revenue”. | `economics_daily_export_revenue` |
| Balance today – Avoided grid import cost | Shows the calculated monetary amount for “Balance today – Avoided grid import cost”. | `economics_daily_avoided_grid_import_cost` |
| Balance today – Battery benefit | Shows the calculated monetary amount for “Balance today – Battery benefit”. | `economics_daily_battery_benefit` |
| Balance today – Native PV self-consumption value | Shows the calculated monetary amount for “Balance today – Native PV self-consumption value”. | `economics_daily_native_pv_self_consumption_value` |
| Balance since start – Grid charging cost | Shows the calculated monetary amount for “Balance since start – Grid charging cost”. | `economics_total_grid_charge_cost` |
| Balance since start – PV opportunity cost | Shows the calculated monetary amount for “Balance since start – PV opportunity cost”. | `economics_total_pv_opportunity_cost` |
| Balance since start – Export revenue | Shows the calculated monetary amount for “Balance since start – Export revenue”. | `economics_total_export_revenue` |
| Balance since start – Avoided grid import cost | Shows the calculated monetary amount for “Balance since start – Avoided grid import cost”. | `economics_total_avoided_grid_import_cost` |
| Balance since start – Battery benefit | Shows the calculated monetary amount for “Balance since start – Battery benefit”. | `economics_total_battery_benefit` |
| Balance since start – Native PV self-consumption value | Shows the calculated monetary amount for “Balance since start – Native PV self-consumption value”. | `economics_total_native_pv_self_consumption_value` |
| Balance since start – Economic efficiency | Shows the calculated monetary amount for “Balance since start – Economic efficiency”. | `economics_total_economic_efficiency_pct` |
| Energy today – Grid to battery | Shows the recorded energy quantity for “Energy today – Grid to battery”. | `economics_daily_grid_to_battery_kwh` |
| Energy today – PV to battery | Shows the recorded energy quantity for “Energy today – PV to battery”. | `economics_daily_pv_to_battery_kwh` |
| Energy today – Grid export | Shows the recorded energy quantity for “Energy today – Grid export”. | `economics_daily_grid_export_kwh` |
| Energy today – Battery to home | Shows the recorded energy quantity for “Energy today – Battery to home”. | `economics_daily_battery_to_home_kwh` |
| Energy today – Battery to grid | Shows the recorded energy quantity for “Energy today – Battery to grid”. | `economics_daily_battery_to_grid_kwh` |
| Energy today – Native PV to home | Shows the recorded energy quantity for “Energy today – Native PV to home”. | `economics_daily_native_pv_to_home_kwh` |
| Energy since start – Grid to battery | Shows the recorded energy quantity for “Energy since start – Grid to battery”. | `economics_total_grid_to_battery_kwh` |
| Energy since start – PV to battery | Shows the recorded energy quantity for “Energy since start – PV to battery”. | `economics_total_pv_to_battery_kwh` |
| Energy since start – Grid export | Shows the recorded energy quantity for “Energy since start – Grid export”. | `economics_total_grid_export_kwh` |
| Energy since start – Battery to home | Shows the recorded energy quantity for “Energy since start – Battery to home”. | `economics_total_battery_to_home_kwh` |
| Energy since start – Battery to grid | Shows the recorded energy quantity for “Energy since start – Battery to grid”. | `economics_total_battery_to_grid_kwh` |
| Energy since start – Native PV to home | Shows the recorded energy quantity for “Energy since start – Native PV to home”. | `economics_total_native_pv_to_home_kwh` |

## Zendure hardware sensors

**Main unit**

| Sensor | Meaning | `key` |
|---|---|---|
| Battery count | Shows how many battery packs the main unit currently detects. | `pack_count` |
| Nominal capacity | Shows the total nominal capacity of the connected battery packs configured in the main unit, in kWh. | `capacity_kwh` |
| Battery power | Shows the total battery power reported by the main unit. | `power_w` |
| Off-grid power | Shows the power at the off-grid output. | `offgrid_power_w` |
| Wi-Fi signal strength | Shows Wi-Fi signal strength in dBm. | `rssi` |
| Estimated time until empty | Estimates how long the battery can continue supplying energy at the current discharge rate. | `remaining_output_time` |
| Available energy | Shows currently available battery energy in kWh. | `available_energy_kwh` |
| Round-trip efficiency | Shows the estimated efficiency across charging and subsequent discharging, as a percentage. | `roundtrip_efficiency_pct` |
| Total energy charged | Shows the total energy charged according to the device, in kWh. | `charged_energy_kwh` |
| Total energy discharged | Shows the total energy delivered according to the device, in kWh. | `discharged_energy_kwh` |
| Total PV energy | Shows the total PV energy reported by the device, in kWh. | `pv_energy_kwh` |
| Switching operations | Shows the device-reported counter of switching operations. | `switching_count` |
| Hardware minimum SoC | Shows the lower SoC limit configured in the hardware. | `hardware_soc_min` |
| Hardware maximum SoC | Shows the upper SoC limit configured in the hardware. | `hardware_soc_max` |
| Battery heating | Shows whether the battery heater is on or off.<br>States: On — heater enabled; Off — heater disabled. | `heating_active` |
| Setpoint storage | Shows whether power setpoints are stored persistently or only temporarily.<br>States: Persistent storage — setpoint stored persistently; Temporary control — setpoint is temporary; Unknown — status unknown. | `setpoint_storage` |
| Device data | Shows whether the device is providing the required operating data.<br>States: Not ready — operating data not ready; Ready — operating data available; Unknown — status unknown. | `dataReady` |
| Grid connection | Shows whether the device is connected to the grid.<br>States: Disconnected — no grid connection; Connected — grid connection established; Unknown — status unknown. | `gridState` |
| PV status | Shows whether the device reports its PV input as active.<br>States: Inactive — function is inactive; Active — function is active; Unknown — status unknown. | `pvStatus` |
| SoC calibration | Shows whether SoC is normal or currently being calibrated.<br>States: Normal — normal operation; Calibrating — SoC calibration is running; Unknown — status unknown. | `socStatus` |
| Pass-through | Shows whether pass-through between the grid input and output is active.<br>States: Inactive — function is inactive; Active — function is active; Unknown — status unknown. | `pass` |
| Reverse flow | Shows whether reverse flow at the device is detected or enabled.<br>States: Inactive — function is inactive; Active — function is active; Unknown — status unknown. | `reverseState` |
| Off-grid mode | Shows the configured mode for off-grid operation.<br>States: Standard; Economic; Disabled — function disabled; Unknown — status unknown. | `gridOffMode` |
| Error status | Shows whether the device reports an error state.<br>States: No error — no error reported; Error — error detected; Unknown — status unknown. | `is_error` |
| Online status | Shows whether the device is currently detected as online or offline.<br>States: Online — device reachable; Offline — device unreachable. | `online` |
| State of charge | Shows battery state of charge as a percentage. | `soc_pct` |
| Charge power | Shows current charging power for this battery pack in watts. | `charge_power_w` |
| Discharge power | Shows current discharging power for this battery pack in watts. | `discharge_power_w` |
| AC input power | Shows electrical power at the AC input in watts. | `ac_input_power_w` |
| AC output power | Shows electrical power at the AC output in watts. | `ac_output_power_w` |
| PV power | Shows current PV input power in watts. | `pv_power_w` |
| Operating mode | Shows whether the device is idle, charging, or discharging.<br>States: Idle — no charging or discharging; Charging — battery charging; Discharging — battery discharging; Unknown — status unknown. | `mode` |
| Temperature | Shows the temperature of the main unit in °C. | `temperature_c` |
| Battery voltage | Shows battery voltage at the main unit in volts. | `battery_voltage_v` |
| Firmware | Shows the device firmware version. | `firmware` |
| Product ID | Shows the device product identifier. | `product_id` |
| Device profile | Shows the detected device or model profile. | `profile` |
| Communication path | Shows the communication path used to reach the device.<br>States: Home Assistant / Z-HA; Cloud; Local; ZenSDK. | `transport` |
| Control status | Shows whether the device is observed, eligible, enabled, actively controlled, or blocked.<br>States: Observation — observation only, no active control; Eligible — device can be controlled; Enabled — control has been enabled; Active — function is active; Blocked by HEMS — Zendure HEMS prevents control; Unsupported — feature or device not supported; Offline — device unreachable. | `control_state` |
| Zendure HEMS | Shows the state of Zendure HEMS control.<br>States: Active — function is active; Inactive — function is inactive; Unknown — status unknown; Outdated — status report is stale; Invalid — status report is invalid; Unsupported — feature or device not supported. | `hems` |
| Last data received | Shows the time, and therefore freshness, of the last received device data. | `last_message` |


**Battery packs**

These values appear as separate sensors for each detected pack.

| Sensor | Meaning | `key` |
|---|---|---|
| Status | Shows the operating state of this individual battery pack.<br>States: Idle — no charging or discharging; Charging — battery charging; Discharging — battery discharging. | `status` |
| Cell voltage difference | Shows the voltage difference between the highest and lowest cell in the pack. | `cell_delta_v` |
| Nominal capacity | Shows the total installed nominal battery capacity in kWh. | `capacity_kwh` |
| Battery power | Shows the battery power currently reported by the device. | `power_w` |
| Battery heating | Shows the operating state of the heater inside the battery.<br>States: On — heater enabled; Off — heater disabled. | `heating_active` |
| State of charge | Shows battery state of charge as a percentage. | `soc_pct` |
| Charge power | Shows current charging power for this battery pack in watts. | `charge_power_w` |
| Discharge power | Shows current discharging power for this battery pack in watts. | `discharge_power_w` |
| Voltage | Shows battery-pack voltage in volts. | `voltage_v` |
| Current | Shows battery-pack current in amperes. | `current_a` |
| Lowest cell voltage | Shows the lowest cell voltage within this pack. | `cell_min_v` |
| Highest cell voltage | Shows the highest cell voltage within this pack. | `cell_max_v` |
| Maximum cell temperature | Shows the temperature reported by the main unit in °C. | `temperature_c` |
| State code | Shows the numeric status code reported by the pack. The exact code table depends on Zendure and firmware. | `state_code` |
| Pack type | Shows the type identifier reported for this battery pack. | `pack_type` |
| Fault code | Shows the fault code reported by this pack; 0 usually means no fault code is set. | `fault_code` |
| Protection active | Shows whether this pack’s battery protection is active. | `protection_active` |
| Firmware | Shows the device firmware version. | `firmware` |
| Last data received | Shows the time, and therefore freshness, of the last received device data. | `last_message` |

**Optional raw main-unit diagnostics**

| Field | Description |
|---|---|
| `acStatus` | Shows the AC operating state reported by the device; code values vary by model. |
| `aiState` | Shows the Zendure AI/automation state; code values vary by model. |
| `batCalTime` | Shows the battery-calibration time value supplied by the device. |
| `bindstate` | Shows the device binding or pairing state. |
| `dcStatus` | Shows the DC operating state reported by the device; code values vary by model. |
| `factoryModeState` | Shows whether Zendure factory mode is active. |
| `gridStandard` | Shows the grid-standard identifier used by the device. |
| `IOTState` | Shows the device IoT/cloud connection state. |
| `LCNState` | Shows a Zendure internal LCN status code; its code table is model-dependent. |
| `localAPIEnable` | Shows whether the local device API is enabled. |
| `net` | Shows a Zendure internal network status value; its code table is model-dependent. |
| `oldMode` | Shows the previous operating mode retained by the device. |
| `OTAState` | Shows the state of an over-the-air firmware update. |
| `phaseSwitch` | Shows the device phase-switch state; meaning may depend on model. |
| `socLimit` | Shows the SoC limit configured in the device as a raw value. |
| `socCompSwitch` | Shows whether SoC compensation is enabled in the device. |
| `writeRsp` | Shows the device response to the latest write or control command. |
| `packNum` | Shows the battery-pack count reported by Zendure. |
| `PowerCycle` | Shows the device-reported power-cycle value; encoding depends on model. |
| `solarPower1` | Power for the respective MPPT input, when provided. |
| `solarPower2` | Power for the respective MPPT input, when provided. |
| `solarPower3` | Power for the respective MPPT input, when provided. |
| `solarPower4` | Power for the respective MPPT input, when provided. |
| `solarPower5` | Power for the respective MPPT input, when provided. |
| `solarPower6` | Power for the respective MPPT input, when provided. |
