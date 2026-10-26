# BSFAI and Zendure sensor catalog

This appendix lists sensors created by the integration. BSFAI calculation and status sensors are separate from Zendure hardware readings.

## Home & grid

| Sensor | Meaning | `key` |
|---|---|---|
| Grid power | Grid power reported by the configured meter. | `grid_power` |
| Shelly grid phase A power | Grid power on phase A reported by Shelly Pro 3EM. | `grid_phase_a_power` |
| Shelly grid phase B power | Grid power on phase B reported by Shelly Pro 3EM. | `grid_phase_b_power` |
| Shelly grid phase C power | Grid power on phase C reported by Shelly Pro 3EM. | `grid_phase_c_power` |
| House load | Calculated household load at the shared grid connection. | `house_load` |

## Status & control

| Sensor | Meaning | `key` |
|---|---|---|
| Native Zendure test status | State of native Zendure observation. | `native_zendure_status` |
| Native Zendure control | Active native communication and control path. | `native_zendure_control` |
| Native Zendure devices found | Number of detected native Zendure devices. | `native_zendure_device_count` |
| Native Zendure messages received | Number of native Zendure messages received. | `native_zendure_message_count` |
| Last native Zendure message | Time of the last native Zendure message. | `native_zendure_last_message` |
| Native Zendure initial-sync package | Name of the saved initial-capture package. | `native_zendure_last_capture` |
| Native Zendure error | Latest error reported by the native Zendure test. | `native_zendure_error` |
| Zendure hardware connection | Reachability of the Zendure hardware connection. | `native_zendure_watchdog` |
| Active device profile | Device profile used for the system. | `device_profile` |
| Adaptive peak detected | Whether an adaptive price peak was detected. | `adaptive_peak_active` |
| Charge strategy | Charging strategy currently in use. | `charge_strategy` |
| Full-charge maintenance | State of planned full-charge maintenance. | `full_charge_maintenance_state` |
| Full-charge maintenance active | Whether full-charge maintenance is active. | `full_charge_maintenance_active` |
| Next recommended full charge | Time of the next recommended full charge. | `full_charge_maintenance_next_recommended` |
| Engine status | Readiness and detected input-data errors. | `engine_health` |
| Control context | Current regulation context (price, PV, or manual). | `season_mode` |
| Hardware SoC limit status | Detected hardware SoC-limit state. | `soc_limit_status` |
| Fault status | Summary severity of detected faults. | `fault_level_status` |
| System status | Overall state of BSFAI regulation. | `status` |
| AI status | State of AI-assisted regulation. | `ai_status` |
| AI recommendation | Current regulation recommendation. | `recommendation` |
| Decision reason | Reason for the current regulation decision. | `decision_reason` |
| Next action | Next planned action and its state. | `next_action_state` |
| Next action start time | Scheduled time of the next action. | `next_action_time` |

## PV forecast

| Sensor | Meaning | `key` |
|---|---|---|
| Forecast status | Availability of PV forecast data. | `forecast_status` |
| PV outlook | Summary of the expected PV outlook. | `pv_outlook` |
| Usable PV forecast remaining today | Usable PV energy for the stated period. | `forecast_remaining_today_kwh` |
| Usable PV forecast tomorrow | Usable PV energy for the stated period. | `forecast_tomorrow_kwh` |
| Usable PV forecast next 3 hours | Usable PV energy for the stated period. | `forecast_next_3h_kwh` |
| Usable PV forecast next 6 hours | Usable PV energy for the stated period. | `forecast_next_6h_kwh` |
| Gross PV forecast remaining today | Gross PV forecast before BSFAI adjustments for the stated period. | `forecast_gross_remaining_today_kwh` |
| Gross PV forecast tomorrow | Gross PV forecast before BSFAI adjustments for the stated period. | `forecast_gross_tomorrow_kwh` |
| Gross PV forecast next 3 hours | Gross PV forecast before BSFAI adjustments for the stated period. | `forecast_gross_next_3h_kwh` |
| Gross PV forecast next 6 hours | Gross PV forecast before BSFAI adjustments for the stated period. | `forecast_gross_next_6h_kwh` |

## Learning-based charging plan

| Sensor | Meaning | `key` |
|---|---|---|
| Charge planning: Learning status | Charging plan and its timing or energy values produced by the learning model. | `learned_planning_status` |
| Charge planning: Mode | Charging plan and its timing or energy values produced by the learning model. | `learned_planning_mode` |
| Charge planning: Planned charge start | Charging plan and its timing or energy values produced by the learning model. | `learned_planning_optimal_charge_start` |
| Charge planning: Deadline | Charging plan and its timing or energy values produced by the learning model. | `learned_planning_deadline` |
| Charge planning: Recharge energy | Charging plan and its timing or energy values produced by the learning model. | `learned_planning_required_charge_energy_kwh` |
| Charge planning: Window size | Charging plan and its timing or energy values produced by the learning model. | `learned_planning_effective_window_minutes` |

## Prices & economics

| Sensor | Meaning | `key` |
|---|---|---|
| Prices – Dynamic daily average | Shows the current value for “Prices – Dynamic daily average”. | `price_daily_average` |
| Prices – Current peak threshold | Price threshold currently used by BSFAI regulation. | `current_peak_threshold` |
| Prices – Current valley threshold | Price threshold currently used by BSFAI regulation. | `current_valley_threshold` |
| Prices – Economic discharge threshold | Price threshold currently used by BSFAI regulation. | `economic_discharge_threshold` |
| Prices – Effective discharge threshold | Price threshold currently used by BSFAI regulation. | `effective_discharge_threshold` |
| Current – Import price | Current grid import price. | `price_now` |
| Current – Export price | Feed-in tariff currently used by BSFAI. | `feed_in_tariff` |
| Current – Applied battery charge price | Charging price BSFAI assigns to current charging. | `charge_price_applied` |
| Prices – Current avg. charge price (estimated) | Estimated average charging price for the current SoC cycle. | `avg_charge_price` |
| Prices – Avg. grid charging price | Weighted average value of recorded energy quantities and prices. | `economics_average_grid_charge_price` |
| Prices – Avg. PV opportunity value | Weighted average value of recorded energy quantities and prices. | `economics_average_pv_opportunity_value` |
| Prices – Avg. total charge price (grid + PV) | Lifetime weighted average price of grid and PV charging. | `economics_average_battery_charge_price` |
| Prices – Avg. export price | Weighted average value of recorded energy quantities and prices. | `economics_average_export_price` |
| Prices – Avg. battery discharge value | Weighted average value of recorded energy quantities and prices. | `economics_average_battery_discharge_value` |
| Prices – Avg. PV to Home Return | Weighted average value of recorded energy quantities and prices. | `economics_average_native_pv_to_home_return` |

## Cell-voltage protection

| Sensor | Meaning | `key` |
|---|---|---|
| Global lowest cell voltage | Lowest detected cell voltage across monitored packs. | `global_lowest_cell_voltage` |
| Cell-voltage emergency charge active | Whether cell-voltage protection requests emergency charging. | `cell_voltage_emergency_active` |
| Discharge blocked by cell-voltage protection | Whether cell-voltage protection blocks discharge. | `cell_voltage_discharge_blocked` |
| SoC / cell voltage plausibility | Plausibility assessment of SoC and cell voltage. | `cell_voltage_soc_plausibility` |
| Cell-voltage status | Cell-voltage protection state. | `cell_voltage_status` |

## Debug recording

| Sensor | Meaning | `key` |
|---|---|---|
| Debug recording active | Status of the time-limited debug recording. | `debug_recording_active` |
| Debug recording ends at | Status of the time-limited debug recording. | `debug_recording_ends_at` |
| Debug samples recorded | Status of the time-limited debug recording. | `debug_sample_count` |
| Last debug package | Status of the time-limited debug recording. | `debug_last_package` |
| Last debug error | Status of the time-limited debug recording. | `debug_last_error` |

## Regulation training

| Sensor | Meaning | `key` |
|---|---|---|
| Regulation training active | Whether regulation training is running. | `regulation_training_active` |
| Regulation training samples | Number of training samples collected. | `regulation_training_sample_count` |
| Saved training sessions | Number of saved training sessions. | `regulation_training_saved_sessions` |
| Regulation training result | Latest regulation training result. | `regulation_training_result` |

## Energy & balance

| Sensor | Meaning | `key` |
|---|---|---|
| Balance since start – Legacy trading profit | Shows the current value for “Balance since start – Legacy trading profit”. | `profit_eur` |
| Balance today – Grid charging cost | Recorded energy quantity or economic balance for the stated period. | `economics_daily_grid_charge_cost` |
| Balance today – PV opportunity cost | Recorded energy quantity or economic balance for the stated period. | `economics_daily_pv_opportunity_cost` |
| Balance today – Export revenue | Recorded energy quantity or economic balance for the stated period. | `economics_daily_export_revenue` |
| Balance today – Avoided grid import cost | Recorded energy quantity or economic balance for the stated period. | `economics_daily_avoided_grid_import_cost` |
| Balance today – Battery benefit | Recorded energy quantity or economic balance for the stated period. | `economics_daily_battery_benefit` |
| Balance today – Native PV self-consumption value | Recorded energy quantity or economic balance for the stated period. | `economics_daily_native_pv_self_consumption_value` |
| Balance since start – Grid charging cost | Recorded energy quantity or economic balance for the stated period. | `economics_total_grid_charge_cost` |
| Balance since start – PV opportunity cost | Recorded energy quantity or economic balance for the stated period. | `economics_total_pv_opportunity_cost` |
| Balance since start – Export revenue | Recorded energy quantity or economic balance for the stated period. | `economics_total_export_revenue` |
| Balance since start – Avoided grid import cost | Recorded energy quantity or economic balance for the stated period. | `economics_total_avoided_grid_import_cost` |
| Balance since start – Battery benefit | Recorded energy quantity or economic balance for the stated period. | `economics_total_battery_benefit` |
| Balance since start – Native PV self-consumption value | Recorded energy quantity or economic balance for the stated period. | `economics_total_native_pv_self_consumption_value` |
| Balance since start – Economic efficiency | Recorded energy quantity or economic balance for the stated period. | `economics_total_economic_efficiency_pct` |
| Energy today – Grid to battery | Recorded energy quantity or economic balance for the stated period. | `economics_daily_grid_to_battery_kwh` |
| Energy today – PV to battery | Recorded energy quantity or economic balance for the stated period. | `economics_daily_pv_to_battery_kwh` |
| Energy today – Grid export | Recorded energy quantity or economic balance for the stated period. | `economics_daily_grid_export_kwh` |
| Energy today – Battery to home | Recorded energy quantity or economic balance for the stated period. | `economics_daily_battery_to_home_kwh` |
| Energy today – Battery to grid | Recorded energy quantity or economic balance for the stated period. | `economics_daily_battery_to_grid_kwh` |
| Energy today – Native PV to home | Recorded energy quantity or economic balance for the stated period. | `economics_daily_native_pv_to_home_kwh` |
| Energy since start – Grid to battery | Recorded energy quantity or economic balance for the stated period. | `economics_total_grid_to_battery_kwh` |
| Energy since start – PV to battery | Recorded energy quantity or economic balance for the stated period. | `economics_total_pv_to_battery_kwh` |
| Energy since start – Grid export | Recorded energy quantity or economic balance for the stated period. | `economics_total_grid_export_kwh` |
| Energy since start – Battery to home | Recorded energy quantity or economic balance for the stated period. | `economics_total_battery_to_home_kwh` |
| Energy since start – Battery to grid | Recorded energy quantity or economic balance for the stated period. | `economics_total_battery_to_grid_kwh` |
| Energy since start – Native PV to home | Recorded energy quantity or economic balance for the stated period. | `economics_total_native_pv_to_home_kwh` |

## Zendure hardware sensors

**Main unit**

| Sensor | Meaning | Schlüssel |
|---|---|---|
| Battery count | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `pack_count` |
| Nominal capacity | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `capacity_kwh` |
| Battery power | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `power_w` |
| Off-grid power | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `offgrid_power_w` |
| Cell voltage difference | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `cell_delta_v` |
| Wi-Fi signal strength | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `rssi` |
| Estimated time until empty | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `remaining_output_time` |
| Available energy | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `available_energy` |
| Round-trip efficiency | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `roundtrip_efficiency` |
| Total energy charged | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `charged_energy` |
| Total energy discharged | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `discharged_energy` |
| Total PV energy | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `pv_energy` |
| Switching operations | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `switching_count` |
| Hardware minimum SoC | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `soc_min` |
| Hardware maximum SoC | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `soc_max` |
| Battery heating | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `heating` |
| Setpoint storage | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `setpoint_storage` |
| Device data | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `data_ready` |
| Grid connection | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `grid_connection` |
| PV status | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `pv_status` |
| SoC calibration | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `soc_calibration` |
| Pass-through | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `passthrough` |
| Reverse flow | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `reverse_flow` |
| Off-grid mode | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `offgrid_mode` |
| Error status | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `error_status` |
| Online status | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `online` |
| State of charge | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `soc_pct` |
| Charge power | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `charge_power_w` |
| Discharge power | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `discharge_power_w` |
| AC input power | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `ac_input_power_w` |
| AC output power | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `ac_output_power_w` |
| PV power | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `pv_power_w` |
| Operating mode | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `mode` |
| Temperature | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `temperature_c` |
| Maximum cell temperature | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `cell_temperature_c` |
| Battery voltage | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `battery_voltage_v` |
| Voltage | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `voltage_v` |
| Current | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `current_a` |
| Lowest cell voltage | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `cell_min_v` |
| Highest cell voltage | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `cell_max_v` |
| State code | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `state_code` |
| Pack type | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `pack_type` |
| Fault code | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `fault_code` |
| Protection active | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `protection_active` |
| Firmware | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `firmware` |
| Product ID | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `product_id` |
| Device profile | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `profile` |
| Communication path | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `transport` |
| Control status | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `control_state` |
| Zendure HEMS | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `hems` |
| Last data received | Current measurement or status reported by the Zendure main unit. Availability depends on model. | `last_message` |

**Battery packs**

| These values appear as separate sensors for each detected pack.

| Sensor | Meaning | Schlüssel |
|---|---|---|
| Status | Measurement or status reported by the respective Zendure battery pack. Some diagnostic values are disabled by default. | `status` |
| Cell voltage difference | Measurement or status reported by the respective Zendure battery pack. Some diagnostic values are disabled by default. | `cell_delta_v` |
| Nominal capacity | Measurement or status reported by the respective Zendure battery pack. Some diagnostic values are disabled by default. | `capacity_kwh` |
| Battery power | Measurement or status reported by the respective Zendure battery pack. Some diagnostic values are disabled by default. | `power_w` |
| Battery heating | Measurement or status reported by the respective Zendure battery pack. Some diagnostic values are disabled by default. | `heating_active` |
| State of charge | Measurement or status reported by the respective Zendure battery pack. Some diagnostic values are disabled by default. | `soc_pct` |
| Charge power | Measurement or status reported by the respective Zendure battery pack. Some diagnostic values are disabled by default. | `charge_power_w` |
| Discharge power | Measurement or status reported by the respective Zendure battery pack. Some diagnostic values are disabled by default. | `discharge_power_w` |
| Voltage | Measurement or status reported by the respective Zendure battery pack. Some diagnostic values are disabled by default. | `voltage_v` |
| Current | Measurement or status reported by the respective Zendure battery pack. Some diagnostic values are disabled by default. | `current_a` |
| Lowest cell voltage | Measurement or status reported by the respective Zendure battery pack. Some diagnostic values are disabled by default. | `cell_min_v` |
| Highest cell voltage | Measurement or status reported by the respective Zendure battery pack. Some diagnostic values are disabled by default. | `cell_max_v` |
| Maximum cell temperature | Measurement or status reported by the respective Zendure battery pack. Some diagnostic values are disabled by default. | `temperature_c` |
| State code | Measurement or status reported by the respective Zendure battery pack. Some diagnostic values are disabled by default. | `state_code` |
| Pack type | Measurement or status reported by the respective Zendure battery pack. Some diagnostic values are disabled by default. | `pack_type` |
| Fault code | Measurement or status reported by the respective Zendure battery pack. Some diagnostic values are disabled by default. | `fault_code` |
| Protection active | Measurement or status reported by the respective Zendure battery pack. Some diagnostic values are disabled by default. | `protection_active` |
| Firmware | Measurement or status reported by the respective Zendure battery pack. Some diagnostic values are disabled by default. | `firmware` |
| Last data received | Measurement or status reported by the respective Zendure battery pack. Some diagnostic values are disabled by default. | `last_message` |

**Optional raw main-unit diagnostics**

| Field | Description |
|---|---|
| `acStatus` | Raw `acStatus` value from Zendure; meaning depends on model and firmware. |
| `aiState` | Raw `aiState` value from Zendure; meaning depends on model and firmware. |
| `batCalTime` | Raw `batCalTime` value from Zendure; meaning depends on model and firmware. |
| `bindstate` | Raw `bindstate` value from Zendure; meaning depends on model and firmware. |
| `dcStatus` | Raw `dcStatus` value from Zendure; meaning depends on model and firmware. |
| `factoryModeState` | Raw `factoryModeState` value from Zendure; meaning depends on model and firmware. |
| `gridStandard` | Raw `gridStandard` value from Zendure; meaning depends on model and firmware. |
| `IOTState` | Raw `IOTState` value from Zendure; meaning depends on model and firmware. |
| `LCNState` | Raw `LCNState` value from Zendure; meaning depends on model and firmware. |
| `localAPIEnable` | Raw `localAPIEnable` value from Zendure; meaning depends on model and firmware. |
| `net` | Raw `net` value from Zendure; meaning depends on model and firmware. |
| `oldMode` | Raw `oldMode` value from Zendure; meaning depends on model and firmware. |
| `OTAState` | Raw `OTAState` value from Zendure; meaning depends on model and firmware. |
| `phaseSwitch` | Raw `phaseSwitch` value from Zendure; meaning depends on model and firmware. |
| `socLimit` | Raw `socLimit` value from Zendure; meaning depends on model and firmware. |
| `socCompSwitch` | Raw `socCompSwitch` value from Zendure; meaning depends on model and firmware. |
| `writeRsp` | Raw `writeRsp` value from Zendure; meaning depends on model and firmware. |
| `packNum` | Raw `packNum` value from Zendure; meaning depends on model and firmware. |
| `PowerCycle` | Raw `PowerCycle` value from Zendure; meaning depends on model and firmware. |
| `solarPower1` | Power for the respective MPPT input, when provided. |
| `solarPower2` | Power for the respective MPPT input, when provided. |
| `solarPower3` | Power for the respective MPPT input, when provided. |
| `solarPower4` | Power for the respective MPPT input, when provided. |
| `solarPower5` | Power for the respective MPPT input, when provided. |
| `solarPower6` | Power for the respective MPPT input, when provided. |

| Feld | Description |
|---|---|
| `solarPower1` | Power for the corresponding MPPT input, when provided by the device. |
| `solarPower2` | Power for the corresponding MPPT input, when provided by the device. |
| `solarPower3` | Power for the corresponding MPPT input, when provided by the device. |
| `solarPower4` | Power for the corresponding MPPT input, when provided by the device. |
| `solarPower5` | Power for the corresponding MPPT input, when provided by the device. |
| `solarPower6` | Power for the corresponding MPPT input, when provided by the device. |

Internal keys help locate entities in developer tools. Display names can be changed by Home Assistant or the user.
