# ENTITY_REGISTRY – Battery SmartFlow AI

Essenzielle Entitäten der Integration: Generated + Required Input.

---

## 🔴 Generated Entities (von der Integration erstellt)

### **SENSOR (Read-Only)**
| Entity | Beschreibung |
|--------|-------------|
| `sensor.battery_smartflow_ai_status` | Integration Health: `ok`, `sensor_invalid` |
| `sensor.battery_smartflow_ai_ai_status` | Aktuelle Rule: `standby`, `charge_surplus`, `expensive_discharge`, etc. |
| `sensor.battery_smartflow_ai_recommendation` | Aktion: `charge`, `discharge`, `standby`, `emergency_charge` |
| `sensor.battery_smartflow_ai_profit_eur` | Arbitrage-Gewinn (€) |
| `sensor.battery_smartflow_ai_night_charge_status` | BYD Nachtlad: `charging`, `goal_reached`, `no_need`, `discharge_paused`, `inactive` |

### **NUMBER (Einstellungen)**
| Entity | Default | Beschreibung |
|--------|---------|-------------|
| `number.battery_smartflow_ai_soc_min` | 12% | Min. State of Charge |
| `number.battery_smartflow_ai_soc_max` | 100% | Max. State of Charge |
| `number.battery_smartflow_ai_max_charge` | 2400 W | Max Lade-Leistung |
| `number.battery_smartflow_ai_max_discharge` | 700 W | Max Entlade-Leistung |
| `number.battery_smartflow_ai_price_threshold` | 0.35 €/kWh | Preis-Schwelle |
| `number.battery_smartflow_ai_very_expensive_threshold` | 0.49 €/kWh | Sehr-teuer-Schwelle |
| `number.battery_smartflow_ai_emergency_soc` | 8% | Emergency-Trigger |
| `number.battery_smartflow_ai_daytime_consumption_w` | 500 W | Tagesverbrauch (für PV-Prognose) |
| `number.battery_smartflow_ai_nighttime_consumption_w` | 500 W | Nachtverbrauch (für Nachtlad) |

### **SELECT (Mode Control)**
| Entity | Optionen | Beschreibung |
|--------|----------|-------------|
| `select.battery_smartflow_ai_ai_mode` | `automatic`, `summer`, `winter`, `manual` | Betriebsmodus |

### **SWITCH (Feature Toggles)**
| Entity | Beschreibung |
|--------|-------------|
| `switch.battery_smartflow_ai_pv_nachtladung` | PV-Prognose Nachtladen ein/aus (v3.2) |

---

## 🔵 Required Input Entities (müssen konfiguriert sein)

### **Zendure (Primary)**
```
sensor.zendure_soc               # State of Charge (0-100%)
select.zendure_ac_mode           # Mode: input/output
number.zendure_input_limit       # Input Power Limit (W)
number.zendure_output_limit      # Output Power Limit (W)
```

### **Grid**
```
sensor.grid_power                # Grid Power (+import/-export in W)
```

### **PV**
```
sensor.pv_power_now              # PV Current Power (W)
```

### **Price**
```
sensor.tibber_price_now          # Electricity Price (€/kWh)
```

---

## 🟡 Optional Input Entities (für v3.2 Features)

### **BYD Battery (Nachtladen)**
```
sensor.byd_soc                            # BYD State of Charge (%)
input_select.akku_steuerung_sma_wr       # BYD Mode Control (via Modbus)
```

### **PV Forecast (Nachtlad-Planung)**
```
sensor.pv_forecast_tomorrow_kwh          # Tomorrow's PV Forecast (kWh)
```

### **Wallbox (Hysterese-Stabilität)**
```
sensor.wallbox_power                     # Wallbox Current Power (W)
```

---

## ✅ Setup Checkliste

**Minimum (Basis):**
- [x] Zendure SoC, AC Mode, Input/Output Limits
- [x] Grid Power
- [x] PV Power
- [x] Price Sensor
- [x] `sensor.battery_smartflow_ai_status` = `ok`

**Empfohlen (+v3.2):**
- [x] Alle Minimum
- [x] BYD SoC + Mode
- [x] PV Forecast
- [x] Wallbox Power

---

**Zuletzt aktualisiert:** 2026-03-16
