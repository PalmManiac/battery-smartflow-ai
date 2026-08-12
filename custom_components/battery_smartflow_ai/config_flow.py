from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_SOC_ENTITY,
    CONF_PV_ENTITY,
    CONF_PV_FORECAST_TODAY_ENTITY,
    CONF_PV_FORECAST_TOMORROW_ENTITY,
    CONF_BATTERY_AC_POWER_ENTITY,
    CONF_ADDITIONAL_BATTERY_CHARGE_ENTITY,
    CONF_ADDITIONAL_BATTERY_DISCHARGE_ENTITY,
    CONF_OFFGRID_POWER_ENTITY,
    CONF_OFFGRID_MODE_ENTITY,
    CONF_PRICE_EXPORT_ENTITY,
    CONF_PRICE_NOW_ENTITY,
    CONF_AC_MODE_ENTITY,
    CONF_INPUT_LIMIT_ENTITY,
    CONF_OUTPUT_LIMIT_ENTITY,
    CONF_GRID_MODE,
    CONF_GRID_POWER_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_GRID_EXPORT_ENTITY,
    GRID_MODE_NONE,
    GRID_MODE_SINGLE,
    GRID_MODE_SPLIT,
    CONF_DEVICE_PROFILE,
    DEFAULT_DEVICE_PROFILE,
    CONF_SOC_LIMIT_ENTITY,
    CONF_PACK_CAPACITY_KWH,
    DEFAULT_PACK_CAPACITY_KWH,
    CONF_INSTALLED_PV_WP,
    DEFAULT_INSTALLED_PV_WP,
    CONF_FEED_IN_TARIFF,
    DEFAULT_FEED_IN_TARIFF,
    # V3.5.0
    CONF_EXPERT_MODE_ENABLED,
    CONF_CELL_VOLTAGE_PROTECTION_ENABLED,
    LOWEST_CELL_VOLTAGE_CONFIG_KEYS,
    DEFAULT_EXPERT_MODE_ENABLED,
    DEFAULT_CELL_VOLTAGE_PROTECTION_ENABLED,
    SETTING_BATTERY_PACKS,
    DEFAULT_BATTERY_PACKS,
    SETTING_CELL_VOLTAGE_WARNING,
    SETTING_CELL_VOLTAGE_CUTOFF,
    SETTING_CELL_VOLTAGE_RESUME,
    SETTING_LEARNED_PLANNING_ENABLED,
    DEFAULT_CELL_VOLTAGE_WARNING,
    DEFAULT_CELL_VOLTAGE_CUTOFF,
    DEFAULT_CELL_VOLTAGE_RESUME,
    DEFAULT_LEARNED_PLANNING_ENABLED,
)

from .device_profiles import DEVICE_PROFILES

EMPTY_ENTITY_VALUES = {
    "",
    "none",
    "null",
    "unknown",
    "unavailable",
}


OPTIONAL_ENTITY_KEYS = (
    CONF_PRICE_EXPORT_ENTITY,
    CONF_PRICE_NOW_ENTITY,
    CONF_SOC_LIMIT_ENTITY,
    CONF_ADDITIONAL_BATTERY_CHARGE_ENTITY,
    CONF_ADDITIONAL_BATTERY_DISCHARGE_ENTITY,
    CONF_OFFGRID_POWER_ENTITY,
    CONF_OFFGRID_MODE_ENTITY,
    CONF_PV_FORECAST_TODAY_ENTITY,
    CONF_PV_FORECAST_TOMORROW_ENTITY,
)


def _normalize_optional_entity(value: Any) -> str | None:
    """Normalize optional entity values stored by older config flows.

    Older entries may contain string values like "None". Those are truthy,
    but invalid as EntitySelector defaults.
    """

    if value is None:
        return None

    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned.lower() in EMPTY_ENTITY_VALUES:
            return None
        return cleaned

    return None


def _cleanup_optional_entities(data: dict[str, Any]) -> None:
    """Remove empty/invalid optional entity placeholders in-place."""

    for key in OPTIONAL_ENTITY_KEYS:
        value = _normalize_optional_entity(data.get(key))
        if value is None:
            data.pop(key, None)
        else:
            data[key] = value
            
            
def _normalize_optional_float(value: Any, default: float = 0.0) -> float:
    """Normalize optional numeric config values.

    Accepts stored floats, ints and strings. Strings with comma decimal
    separators are accepted for resilience, although Home Assistant number
    selectors normally submit dot decimals.
    """

    try:
        if value is None:
            return float(default)

        if isinstance(value, str):
            value = value.strip().replace(",", ".")
            if value == "" or value.lower() in EMPTY_ENTITY_VALUES:
                return float(default)

        return max(0.0, float(value))
    except Exception:
        return float(default)
        
        
def _validate_feed_in_tariff(value: Any) -> float:
    """Validate feed-in tariff from config/reconfigure forms."""

    return _normalize_optional_float(value, DEFAULT_FEED_IN_TARIFF)


class ZendureSmartFlowConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Battery SmartFlow AI."""

    VERSION = 3

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._user_input = dict(user_input)
            return await self.async_step_grid()

        return self.async_show_form(
            step_id="user",
            data_schema=self._base_schema(),
        )

    async def async_step_grid(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        grid_mode = self._user_input.get(CONF_GRID_MODE, GRID_MODE_NONE)

        if user_input is not None:
            self._user_input.update(user_input)

            if grid_mode == GRID_MODE_SPLIT:
                if (
                    not user_input.get(CONF_GRID_IMPORT_ENTITY)
                    or not user_input.get(CONF_GRID_EXPORT_ENTITY)
                ):
                    errors["base"] = "grid_split_missing"

            _cleanup_optional_entities(self._user_input)
            
            self._user_input[CONF_FEED_IN_TARIFF] = _normalize_optional_float(
                self._user_input.get(CONF_FEED_IN_TARIFF),
                DEFAULT_FEED_IN_TARIFF,
            )

            if grid_mode != GRID_MODE_SINGLE:
                self._user_input.pop(CONF_GRID_POWER_ENTITY, None)

            if grid_mode != GRID_MODE_SPLIT:
                self._user_input.pop(CONF_GRID_IMPORT_ENTITY, None)
                self._user_input.pop(CONF_GRID_EXPORT_ENTITY, None)

            if not errors:
                return self.async_create_entry(
                    title="Battery SmartFlow AI",
                    data=self._user_input,
                )

        return self.async_show_form(
            step_id="grid",
            data_schema=self._grid_schema(grid_mode),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None):
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            self._user_input = dict(entry.data)
            self._user_input.update(user_input)
            return await self.async_step_reconfigure_grid()

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self._base_schema(entry),
        )

    async def async_step_reconfigure_grid(
        self,
        user_input: dict[str, Any] | None = None,
    ):
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        grid_mode = self._user_input.get(CONF_GRID_MODE, GRID_MODE_NONE)

        if user_input is not None:
            cleaned = dict(self._user_input)
            cleaned.update(user_input)

            if grid_mode != GRID_MODE_SINGLE:
                cleaned.pop(CONF_GRID_POWER_ENTITY, None)

            if grid_mode != GRID_MODE_SPLIT:
                cleaned.pop(CONF_GRID_IMPORT_ENTITY, None)
                cleaned.pop(CONF_GRID_EXPORT_ENTITY, None)

            if grid_mode == GRID_MODE_SPLIT:
                if (
                    not cleaned.get(CONF_GRID_IMPORT_ENTITY)
                    or not cleaned.get(CONF_GRID_EXPORT_ENTITY)
                ):
                    errors["base"] = "grid_split_missing"

            _cleanup_optional_entities(cleaned)
            
            cleaned[CONF_FEED_IN_TARIFF] = _normalize_optional_float(
                cleaned.get(CONF_FEED_IN_TARIFF),
                DEFAULT_FEED_IN_TARIFF,
            )

            if not errors:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates=cleaned,
                    reason="reconfigure_success",
                )

        return self.async_show_form(
            step_id="reconfigure_grid",
            data_schema=self._grid_schema(grid_mode, entry),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return ZendureSmartFlowOptionsFlow()

    def _base_schema(
        self,
        entry: config_entries.ConfigEntry | None = None,
    ) -> vol.Schema:
        def _val(key: str):
            if not entry:
                return None

            value = entry.data.get(key)

            if key in OPTIONAL_ENTITY_KEYS:
                return _normalize_optional_entity(value)

            return value

        schema: dict[Any, Any] = {}

        schema[
            vol.Required(
                CONF_DEVICE_PROFILE,
                default=_val(CONF_DEVICE_PROFILE) or DEFAULT_DEVICE_PROFILE,
            )
        ] = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    {
                        "value": key,
                        "label": DEVICE_PROFILES[key].get("label", key),
                    }
                    for key in DEVICE_PROFILES
                ],
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        )

        schema[
            vol.Required(CONF_SOC_ENTITY, default=_val(CONF_SOC_ENTITY))
        ] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        )

        soc_limit_val = _val(CONF_SOC_LIMIT_ENTITY)
        if soc_limit_val:
            schema[
                vol.Optional(CONF_SOC_LIMIT_ENTITY, default=soc_limit_val)
            ] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            )
        else:
            schema[
                vol.Optional(CONF_SOC_LIMIT_ENTITY)
            ] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            )

        schema[
            vol.Required(
                CONF_PACK_CAPACITY_KWH,
                default=_val(CONF_PACK_CAPACITY_KWH) or DEFAULT_PACK_CAPACITY_KWH,
            )
        ] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0.1,
                max=20.0,
                step=0.01,
                mode=selector.NumberSelectorMode.BOX,
            )
        )

        schema[
            vol.Optional(
                CONF_INSTALLED_PV_WP,
                default=_val(CONF_INSTALLED_PV_WP) or DEFAULT_INSTALLED_PV_WP,
            )
        ] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0,
                max=50000,
                step=10,
                mode=selector.NumberSelectorMode.BOX,
                unit_of_measurement="Wp",
            )
        )

        schema[
            vol.Required(CONF_PV_ENTITY, default=_val(CONF_PV_ENTITY))
        ] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        )
        
        schema[
            vol.Optional(
                CONF_FEED_IN_TARIFF,
                default=_normalize_optional_float(
                    _val(CONF_FEED_IN_TARIFF),
                    DEFAULT_FEED_IN_TARIFF,
                ),
            )
        ] = vol.All(
            vol.Coerce(float),
            vol.Range(min=0.0, max=1.0),
        )

        pv_forecast_today_val = _val(CONF_PV_FORECAST_TODAY_ENTITY)
        if pv_forecast_today_val:
            schema[
                vol.Optional(
                    CONF_PV_FORECAST_TODAY_ENTITY,
                    default=pv_forecast_today_val,
                )
            ] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            )
        else:
            schema[
                vol.Optional(CONF_PV_FORECAST_TODAY_ENTITY)
            ] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            )

        pv_forecast_tomorrow_val = _val(CONF_PV_FORECAST_TOMORROW_ENTITY)
        if pv_forecast_tomorrow_val:
            schema[
                vol.Optional(
                    CONF_PV_FORECAST_TOMORROW_ENTITY,
                    default=pv_forecast_tomorrow_val,
                )
            ] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            )
        else:
            schema[
                vol.Optional(CONF_PV_FORECAST_TOMORROW_ENTITY)
            ] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            )

        schema[
            vol.Required(
                CONF_BATTERY_AC_POWER_ENTITY,
                default=_val(CONF_BATTERY_AC_POWER_ENTITY),
            )
        ] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        )

        additional_battery_val = _val(CONF_ADDITIONAL_BATTERY_CHARGE_ENTITY)
        if additional_battery_val:
            schema[
                vol.Optional(
                    CONF_ADDITIONAL_BATTERY_CHARGE_ENTITY,
                    default=additional_battery_val,
                )
            ] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            )
        else:
            schema[
                vol.Optional(CONF_ADDITIONAL_BATTERY_CHARGE_ENTITY)
            ] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            )

        additional_battery_discharge_val = _val(CONF_ADDITIONAL_BATTERY_DISCHARGE_ENTITY)
        if additional_battery_discharge_val:
            schema[
                vol.Optional(
                    CONF_ADDITIONAL_BATTERY_DISCHARGE_ENTITY,
                    default=additional_battery_discharge_val,
                )
            ] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            )
        else:
            schema[
                vol.Optional(CONF_ADDITIONAL_BATTERY_DISCHARGE_ENTITY)
            ] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            )

        offgrid_power_val = _val(CONF_OFFGRID_POWER_ENTITY)
        if offgrid_power_val:
            schema[
                vol.Optional(
                    CONF_OFFGRID_POWER_ENTITY,
                    default=offgrid_power_val,
                )
            ] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            )
        else:
            schema[
                vol.Optional(CONF_OFFGRID_POWER_ENTITY)
            ] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            )

        offgrid_mode_val = _val(CONF_OFFGRID_MODE_ENTITY)
        if offgrid_mode_val:
            schema[
                vol.Optional(
                    CONF_OFFGRID_MODE_ENTITY,
                    default=offgrid_mode_val,
                )
            ] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="select")
            )
        else:
            schema[
                vol.Optional(CONF_OFFGRID_MODE_ENTITY)
            ] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="select")
            )

        price_export_val = _val(CONF_PRICE_EXPORT_ENTITY)
        if price_export_val:
            schema[
                vol.Optional(CONF_PRICE_EXPORT_ENTITY, default=price_export_val)
            ] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            )
        else:
            schema[
                vol.Optional(CONF_PRICE_EXPORT_ENTITY)
            ] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            )

        price_now_val = _val(CONF_PRICE_NOW_ENTITY)
        if price_now_val:
            schema[
                vol.Optional(CONF_PRICE_NOW_ENTITY, default=price_now_val)
            ] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            )
        else:
            schema[
                vol.Optional(CONF_PRICE_NOW_ENTITY)
            ] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            )

        schema[
            vol.Required(CONF_AC_MODE_ENTITY, default=_val(CONF_AC_MODE_ENTITY))
        ] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="select")
        )

        schema[
            vol.Required(
                CONF_INPUT_LIMIT_ENTITY,
                default=_val(CONF_INPUT_LIMIT_ENTITY),
            )
        ] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="number")
        )

        schema[
            vol.Required(
                CONF_OUTPUT_LIMIT_ENTITY,
                default=_val(CONF_OUTPUT_LIMIT_ENTITY),
            )
        ] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="number")
        )

        schema[
            vol.Required(
                CONF_GRID_MODE,
                default=_val(CONF_GRID_MODE) or GRID_MODE_SINGLE,
            )
        ] = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    {"value": GRID_MODE_NONE, "label": "Kein Netzsensor"},
                    {"value": GRID_MODE_SINGLE, "label": "Ein Sensor (+ / −)"},
                    {
                        "value": GRID_MODE_SPLIT,
                        "label": "Zwei Sensoren (Bezug & Einspeisung)",
                    },
                ]
            )
        )

        return vol.Schema(schema)

    def _grid_schema(
        self,
        grid_mode: str,
        entry: config_entries.ConfigEntry | None = None,
    ) -> vol.Schema:
        def _val(key: str):
            if not entry:
                return None

            value = entry.data.get(key)

            if isinstance(value, str):
                cleaned = value.strip()
                if cleaned.lower() in EMPTY_ENTITY_VALUES:
                    return None
                return cleaned

            return value

        schema: dict[Any, Any] = {}

        if grid_mode == GRID_MODE_SINGLE:
            schema[
                vol.Required(
                    CONF_GRID_POWER_ENTITY,
                    default=_val(CONF_GRID_POWER_ENTITY),
                )
            ] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            )

        if grid_mode == GRID_MODE_SPLIT:
            schema[
                vol.Required(
                    CONF_GRID_IMPORT_ENTITY,
                    default=_val(CONF_GRID_IMPORT_ENTITY),
                )
            ] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            )
            schema[
                vol.Required(
                    CONF_GRID_EXPORT_ENTITY,
                    default=_val(CONF_GRID_EXPORT_ENTITY),
                )
            ] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            )

        return vol.Schema(schema)


class ZendureSmartFlowOptionsFlow(config_entries.OptionsFlow):
    """Options flow for user-facing system and expert settings."""

    def __init__(self) -> None:
        self._working_options: dict[str, Any] = {}

    def _get_battery_packs(self) -> int:
        try:
            val = self.config_entry.options.get(
                SETTING_BATTERY_PACKS,
                self.config_entry.data.get(
                    SETTING_BATTERY_PACKS,
                    DEFAULT_BATTERY_PACKS,
                ),
            )
            packs = int(val)
            return min(max(packs, 1), 6)
        except Exception:
            return DEFAULT_BATTERY_PACKS

    def _current_options(self) -> dict[str, Any]:
        return dict(self.config_entry.options)

    def _merged_preview(self) -> dict[str, Any]:
        merged = self._current_options()
        merged.update(self._working_options)
        return merged
        
    def _build_merged_options(
        self,
        user_input: dict[str, Any],
    ) -> dict[str, Any]:
        merged_options = dict(self.config_entry.options)

        installed_pv_wp = user_input.get(
            CONF_INSTALLED_PV_WP,
            self.config_entry.options.get(
                CONF_INSTALLED_PV_WP,
                self.config_entry.data.get(
                    CONF_INSTALLED_PV_WP,
                    DEFAULT_INSTALLED_PV_WP,
                ),
            ),
        )

        merged_options[CONF_INSTALLED_PV_WP] = float(installed_pv_wp)

        if CONF_EXPERT_MODE_ENABLED in user_input:
            merged_options[CONF_EXPERT_MODE_ENABLED] = bool(
                user_input[CONF_EXPERT_MODE_ENABLED]
            )

        if CONF_CELL_VOLTAGE_PROTECTION_ENABLED in user_input:
            merged_options[CONF_CELL_VOLTAGE_PROTECTION_ENABLED] = bool(
                user_input[CONF_CELL_VOLTAGE_PROTECTION_ENABLED]
            )
            
        if SETTING_LEARNED_PLANNING_ENABLED in user_input:
            merged_options[SETTING_LEARNED_PLANNING_ENABLED] = bool(
                user_input[SETTING_LEARNED_PLANNING_ENABLED]
            )
            
        for key in LOWEST_CELL_VOLTAGE_CONFIG_KEYS:
            if key in user_input:
                if user_input.get(key):
                    merged_options[key] = user_input[key]
                else:
                    merged_options.pop(key, None)

        for key in (
            SETTING_CELL_VOLTAGE_WARNING,
            SETTING_CELL_VOLTAGE_CUTOFF,
            SETTING_CELL_VOLTAGE_RESUME,
        ):
            if key not in user_input:
                continue
            value = user_input.get(key)
            if value is None:
                continue
            try:
                merged_options[key] = float(value)
            except (TypeError, ValueError):
                continue

        return merged_options

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        self._working_options = {}
        return self.async_show_menu(
            step_id="init",
            menu_options=["general", "expert", "debug"],
        )

    def _debug_coordinator(self):
        """Return the loaded coordinator for this options-flow entry."""

        return self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)

    async def async_step_debug(self, user_input: dict[str, Any] | None = None):
        """Route to the current recording action without changing options."""

        coordinator = self._debug_coordinator()
        if coordinator is None:
            return self.async_abort(reason="debug_integration_not_loaded")

        status = coordinator.debug_recording_status
        if status.active:
            return await self.async_step_debug_stop()
        return await self.async_step_debug_start()

    async def async_step_debug_start(
        self, user_input: dict[str, Any] | None = None
    ):
        """Start one bounded debug recording."""

        coordinator = self._debug_coordinator()
        if coordinator is None:
            return self.async_abort(reason="debug_integration_not_loaded")
        if coordinator.debug_recording_status.active:
            return await self.async_step_debug_stop()

        if user_input is not None:
            await coordinator.async_start_debug_recording(
                duration_minutes=int(user_input["duration_minutes"])
            )
            return self.async_abort(reason="debug_recording_started")

        return self.async_show_form(
            step_id="debug_start",
            data_schema=vol.Schema(
                {
                    vol.Required("duration_minutes", default="10"):
                        selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=["10", "30", "60", "120"],
                                mode=selector.SelectSelectorMode.DROPDOWN,
                            )
                        ),
                }
            ),
        )

    async def async_step_debug_stop(
        self, user_input: dict[str, Any] | None = None
    ):
        """Show current progress and optionally stop the recording."""

        coordinator = self._debug_coordinator()
        if coordinator is None:
            return self.async_abort(reason="debug_integration_not_loaded")
        status = coordinator.debug_recording_status
        if not status.active:
            return self.async_abort(reason="debug_recording_already_stopped")
        if user_input is not None:
            await coordinator.async_stop_debug_recording()
            return self.async_abort(reason="debug_recording_stopped")

        recording_end = (
            status.recording_end.isoformat()
            if status.recording_end is not None
            else "—"
        )
        return self.async_show_form(
            step_id="debug_stop",
            data_schema=vol.Schema({}),
            description_placeholders={
                "recording_end": recording_end,
                "sample_count": str(status.sample_count),
            },
        )

    async def async_step_general(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            merged_options = self._build_merged_options(user_input)
            return self.async_create_entry(title="", data=merged_options)

        options_schema = vol.Schema(
            {
                vol.Optional(CONF_INSTALLED_PV_WP): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=50000,
                        step=10,
                        mode=selector.NumberSelectorMode.BOX,
                        unit_of_measurement="Wp",
                    )
                ),
            }
        )

        suggested_values = {
            CONF_INSTALLED_PV_WP: self.config_entry.options.get(
                CONF_INSTALLED_PV_WP,
                self.config_entry.data.get(
                    CONF_INSTALLED_PV_WP,
                    DEFAULT_INSTALLED_PV_WP,
                ),
            ),
        }

        return self.async_show_form(
            step_id="general",
            data_schema=self.add_suggested_values_to_schema(
                options_schema,
                suggested_values,
            ),
        )

    async def async_step_expert(self, user_input: dict[str, Any] | None = None):
        preview = self._merged_preview()

        if user_input is not None:
            self._working_options.update(user_input)

            if bool(user_input.get(CONF_EXPERT_MODE_ENABLED, False)):
                return await self.async_step_expert_cell_voltage()

            merged_options = self._current_options()
            merged_options.update(self._working_options)
            return self.async_create_entry(title="", data=merged_options)

        options_schema = vol.Schema(
            {
                vol.Optional(CONF_EXPERT_MODE_ENABLED): selector.BooleanSelector(),
                vol.Optional(SETTING_LEARNED_PLANNING_ENABLED): selector.BooleanSelector(),
            }
        )

        suggested_values = {
            CONF_EXPERT_MODE_ENABLED: preview.get(
                CONF_EXPERT_MODE_ENABLED,
                DEFAULT_EXPERT_MODE_ENABLED,
            ),
            SETTING_LEARNED_PLANNING_ENABLED: preview.get(
                SETTING_LEARNED_PLANNING_ENABLED,
                DEFAULT_LEARNED_PLANNING_ENABLED,
            ),
        }

        return self.async_show_form(
            step_id="expert",
            data_schema=self.add_suggested_values_to_schema(
                options_schema,
                suggested_values,
            ),
        )

    async def async_step_expert_cell_voltage(
        self,
        user_input: dict[str, Any] | None = None,
    ):
        preview = self._merged_preview()

        if user_input is not None:
            self._working_options.update(user_input)

            if bool(user_input.get(CONF_CELL_VOLTAGE_PROTECTION_ENABLED, False)):
                return await self.async_step_expert_cell_voltage_config()

            merged_options = self._current_options()
            merged_options.update(self._working_options)
            return self.async_create_entry(title="", data=merged_options)

        options_schema = vol.Schema(
            {
                vol.Optional(CONF_CELL_VOLTAGE_PROTECTION_ENABLED): selector.BooleanSelector(),
            }
        )

        suggested_values = {
            CONF_CELL_VOLTAGE_PROTECTION_ENABLED: preview.get(
                CONF_CELL_VOLTAGE_PROTECTION_ENABLED,
                DEFAULT_CELL_VOLTAGE_PROTECTION_ENABLED,
            ),
        }

        return self.async_show_form(
            step_id="expert_cell_voltage",
            data_schema=self.add_suggested_values_to_schema(
                options_schema,
                suggested_values,
            ),
        )

    async def async_step_expert_cell_voltage_config(
        self,
        user_input: dict[str, Any] | None = None,
    ):
        packs = self._get_battery_packs()
        preview = self._merged_preview()

        if user_input is not None:
            self._working_options.update(user_input)
            merged_options = self._current_options()
            merged_options.update(self._working_options)
            return self.async_create_entry(title="", data=merged_options)

        schema_dict: dict[Any, Any] = {}

        for idx in range(packs):
            key = LOWEST_CELL_VOLTAGE_CONFIG_KEYS[idx]
            schema_dict[vol.Optional(key)] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            )

        schema_dict[
            vol.Optional(SETTING_CELL_VOLTAGE_WARNING)
        ] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=2.50,
                max=3.40,
                step=0.01,
                mode=selector.NumberSelectorMode.BOX,
                unit_of_measurement="V",
            )
        )
        schema_dict[
            vol.Optional(SETTING_CELL_VOLTAGE_CUTOFF)
        ] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=2.50,
                max=3.30,
                step=0.01,
                mode=selector.NumberSelectorMode.BOX,
                unit_of_measurement="V",
            )
        )
        schema_dict[
            vol.Optional(SETTING_CELL_VOLTAGE_RESUME)
        ] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=2.50,
                max=3.40,
                step=0.01,
                mode=selector.NumberSelectorMode.BOX,
                unit_of_measurement="V",
            )
        )

        options_schema = vol.Schema(schema_dict)

        suggested_values: dict[str, Any] = {
            SETTING_CELL_VOLTAGE_WARNING: preview.get(
                SETTING_CELL_VOLTAGE_WARNING,
                DEFAULT_CELL_VOLTAGE_WARNING,
            ),
            SETTING_CELL_VOLTAGE_CUTOFF: preview.get(
                SETTING_CELL_VOLTAGE_CUTOFF,
                DEFAULT_CELL_VOLTAGE_CUTOFF,
            ),
            SETTING_CELL_VOLTAGE_RESUME: preview.get(
                SETTING_CELL_VOLTAGE_RESUME,
                DEFAULT_CELL_VOLTAGE_RESUME,
            ),
        }

        for idx in range(packs):
            key = LOWEST_CELL_VOLTAGE_CONFIG_KEYS[idx]
            suggested_values[key] = preview.get(key)

        return self.async_show_form(
            step_id="expert_cell_voltage_config",
            data_schema=self.add_suggested_values_to_schema(
                options_schema,
                suggested_values,
            ),
        )
