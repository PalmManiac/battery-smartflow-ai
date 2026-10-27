from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any
from uuid import uuid4

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

from .battery_groups import (
    migrate_single_device_group,
    remove_group,
    save_group,
)
from .const import (
    CONF_AC_MODE_ENTITY,
    CONF_ADDITIONAL_BATTERY_CHARGE_ENTITY,
    CONF_ADDITIONAL_BATTERY_DISCHARGE_ENTITY,
    CONF_BATTERY_AC_POWER_ENTITY,
    CONF_BATTERY_GROUPS,
    CONF_CELL_VOLTAGE_PROTECTION_ENABLED,
    CONF_DEVICE_PROFILE,
    CONF_DYNAMIC_FEED_IN_PRICE_ENTITY,
    CONF_ENERGY_SCOPES,
    # V3.5.0
    CONF_EXPERT_MODE_ENABLED,
    CONF_FEED_IN_TARIFF,
    CONF_GRID_EXPORT_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_GRID_MODE,
    CONF_GRID_POWER_ENTITY,
    CONF_HEMS_DASHBOARD_ENABLED,
    CONF_INPUT_LIMIT_ENTITY,
    CONF_INSTALLED_PV_WP,
    CONF_NATIVE_PV_ENTITY,
    CONF_NATIVE_ZENDURE_ALWAYS_SMART_MODE_1,
    CONF_NATIVE_ZENDURE_APP_TOKEN,
    CONF_NATIVE_ZENDURE_CONTROL_ENABLED,
    CONF_NATIVE_ZENDURE_CONTROL_TRANSPORT,
    CONF_NATIVE_ZENDURE_DEVICE_SETUPS,
    CONF_NATIVE_ZENDURE_LEGACY_PROVISION,
    CONF_NATIVE_ZENDURE_LEGACY_WIFI_PASSWORD,
    CONF_NATIVE_ZENDURE_LEGACY_WIFI_SSID,
    CONF_NATIVE_ZENDURE_LOCAL_MQTT_PASSWORD,
    CONF_NATIVE_ZENDURE_LOCAL_MQTT_PORT,
    CONF_NATIVE_ZENDURE_LOCAL_MQTT_SERVER,
    CONF_NATIVE_ZENDURE_LOCAL_MQTT_USERNAME,
    CONF_NATIVE_ZENDURE_SELECTED_DEVICE,
    CONF_NATIVE_ZENDURE_ZENSDK_IP,
    CONF_NATIVE_ZENDURE_ZENSDK_IP_CLEAR,
    CONF_OFFGRID_MODE_ENTITY,
    CONF_OFFGRID_POWER_ENTITY,
    CONF_OUTPUT_LIMIT_ENTITY,
    CONF_PACK_CAPACITY_KWH,
    CONF_PRICE_EXPORT_ENTITY,
    CONF_PRICE_NOW_ENTITY,
    CONF_PV_ENTITY,
    CONF_PV_FORECAST_CONFIG_ENTRIES,
    CONF_PV_FORECAST_TODAY_ENTITY,
    CONF_PV_FORECAST_TOMORROW_ENTITY,
    CONF_SHELLY_3EM_HOST,
    CONF_SHELLY_3EM_PASSWORD,
    CONF_SHELLY_PRO_3EM_HOST,
    CONF_SHELLY_PRO_3EM_PASSWORD,
    CONF_SOC_ENTITY,
    CONF_SOC_LIMIT_ENTITY,
    DEFAULT_BATTERY_PACKS,
    DEFAULT_CELL_VOLTAGE_CUTOFF,
    DEFAULT_CELL_VOLTAGE_PROTECTION_ENABLED,
    DEFAULT_CELL_VOLTAGE_RESUME,
    DEFAULT_CELL_VOLTAGE_WARNING,
    DEFAULT_DEVICE_PROFILE,
    DEFAULT_EXPERT_MODE_ENABLED,
    DEFAULT_FEED_IN_TARIFF,
    DEFAULT_FULL_CHARGE_MAINTENANCE_ENABLED,
    DEFAULT_FULL_CHARGE_MAINTENANCE_INTERVAL_DAYS,
    DEFAULT_INSTALLED_PV_WP,
    DEFAULT_LEARNED_PLANNING_ENABLED,
    DEFAULT_PACK_CAPACITY_KWH,
    DOMAIN,
    GRID_MODE_DIRECT_SHELLY,
    GRID_MODE_NONE,
    GRID_MODE_SHELLY_3EM,
    GRID_MODE_SHELLY_PRO_3EM,
    GRID_MODE_SHELLY_PRO_3EM_MODBUS,
    GRID_MODE_SHELLY_PRO_3EM_OPTIONS,
    GRID_MODE_SINGLE,
    GRID_MODE_SPLIT,
    LOWEST_CELL_VOLTAGE_CONFIG_KEYS,
    SETTING_BATTERY_PACKS,
    SETTING_CELL_VOLTAGE_CUTOFF,
    SETTING_CELL_VOLTAGE_RESUME,
    SETTING_CELL_VOLTAGE_WARNING,
    SETTING_FULL_CHARGE_MAINTENANCE_ENABLED,
    SETTING_FULL_CHARGE_MAINTENANCE_INTERVAL_DAYS,
    SETTING_LEARNED_PLANNING_ENABLED,
)
from .core.models import ZendureTransport
from .device_profiles import (
    DEVICE_PROFILE_MODELS,
    remove_deprecated_profile_overrides,
)
from .energy_scopes import (
    GRID_MODE_NONE as ENERGY_GRID_MODE_NONE,
)
from .energy_scopes import (
    GRID_MODE_SIGNED as ENERGY_GRID_MODE_SIGNED,
)
from .energy_scopes import (
    GRID_MODE_SPLIT as ENERGY_GRID_MODE_SPLIT,
)
from .energy_scopes import (
    PV_SOURCE_AGGREGATE,
    PV_SOURCE_COMPONENTS,
    normalize_energy_scope_config,
    remove_energy_scope,
    save_energy_scope,
)
from .forecast import async_energy_forecast_sources
from .hardware.shelly_pro_3em import validate_shelly_host
from .hardware.zendure.cloud import ZendureCloudClient, ZendureCloudError
from .hardware.zendure.device_matrix import (
    VerificationLevel,
    preferred_local_transport,
    resolve_zendure_device,
)
from .hardware.zendure.legacy import (
    async_provision_legacy_device,
    legacy_provisioning_default,
)
from .hardware.zendure.zensdk import normalize_zensdk_ipv4
from .native_config_ui import (
    STORED_APP_TOKEN_MASK,
    native_device_label,
    native_device_summary_line,
    resolve_app_token_input,
)
from .native_device_setup import (
    SETUP_COMPLETE,
    reconcile_device_setups,
    save_device_setup,
    setup_is_complete,
)
from .price_currency import price_input_profile, resolve_price_currency

EMPTY_ENTITY_VALUES = {
    "",
    "none",
    "null",
    "unknown",
    "unavailable",
}


def _shelly_grid_keys(grid_mode: str) -> tuple[str | None, str | None]:
    """Return the config keys for the selected locally polled Shelly model."""

    if grid_mode in GRID_MODE_SHELLY_PRO_3EM_OPTIONS:
        return CONF_SHELLY_PRO_3EM_HOST, CONF_SHELLY_PRO_3EM_PASSWORD
    if grid_mode == GRID_MODE_SHELLY_3EM:
        return CONF_SHELLY_3EM_HOST, CONF_SHELLY_3EM_PASSWORD
    return None, None


def _native_transport_options(identity) -> tuple[ZendureTransport, ...]:
    """Expose Cloud plus only the verified local path for one model."""

    local = preferred_local_transport(identity)
    return (
        (ZendureTransport.CLOUD_MQTT, local)
        if local is not None
        else (ZendureTransport.CLOUD_MQTT,)
    )


def _requested_native_transport(user_input, identity) -> ZendureTransport:
    """Parse an explicit choice; new setups start safely on Cloud."""

    raw = user_input.get(
        CONF_NATIVE_ZENDURE_CONTROL_TRANSPORT,
        ZendureTransport.CLOUD_MQTT.value,
    )
    try:
        return ZendureTransport(str(raw))
    except ValueError:
        return ZendureTransport.CLOUD_MQTT


OPTIONAL_ENTITY_KEYS = (
    CONF_NATIVE_PV_ENTITY,
    CONF_PRICE_EXPORT_ENTITY,
    CONF_PRICE_NOW_ENTITY,
    CONF_DYNAMIC_FEED_IN_PRICE_ENTITY,
    CONF_SOC_LIMIT_ENTITY,
    CONF_ADDITIONAL_BATTERY_CHARGE_ENTITY,
    CONF_ADDITIONAL_BATTERY_DISCHARGE_ENTITY,
    CONF_OFFGRID_POWER_ENTITY,
    CONF_OFFGRID_MODE_ENTITY,
    CONF_PV_FORECAST_TODAY_ENTITY,
    CONF_PV_FORECAST_TOMORROW_ENTITY,
)

# These belonged to the V5 single-device/Z-HA control model. Native V6 obtains
# battery state and sends commands through its per-system device adapter.
LEGACY_BATTERY_ENTITY_KEYS = (
    CONF_SOC_ENTITY,
    CONF_SOC_LIMIT_ENTITY,
    CONF_PACK_CAPACITY_KWH,
    CONF_BATTERY_AC_POWER_ENTITY,
    CONF_ADDITIONAL_BATTERY_CHARGE_ENTITY,
    CONF_ADDITIONAL_BATTERY_DISCHARGE_ENTITY,
    CONF_NATIVE_PV_ENTITY,
    CONF_AC_MODE_ENTITY,
    CONF_INPUT_LIMIT_ENTITY,
    CONF_OUTPUT_LIMIT_ENTITY,
    CONF_OFFGRID_POWER_ENTITY,
    CONF_OFFGRID_MODE_ENTITY,
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


def _normalize_forecast_entries(value: Any) -> list[str]:
    """Normalize the multi-select value and remove duplicate entry IDs."""

    if not isinstance(value, (list, tuple, set)):
        return []
    return list(dict.fromkeys(str(item) for item in value if str(item).strip()))


def _apply_forecast_selection(data: dict[str, Any]) -> None:
    """Prefer Energy forecast entries while retaining untouched legacy data."""

    if CONF_PV_FORECAST_CONFIG_ENTRIES not in data:
        return
    selected = _normalize_forecast_entries(data[CONF_PV_FORECAST_CONFIG_ENTRIES])
    if selected:
        data[CONF_PV_FORECAST_CONFIG_ENTRIES] = selected
    else:
        data.pop(CONF_PV_FORECAST_CONFIG_ENTRIES, None)
    data.pop(CONF_PV_FORECAST_TODAY_ENTITY, None)
    data.pop(CONF_PV_FORECAST_TOMORROW_ENTITY, None)
            
            
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


def _validate_native_zensdk_ip(
    user_input: Mapping[str, Any], identity: Any
) -> tuple[str | None, str | None, bool]:
    """Validate a per-device direct ZenSDK IPv4 override from the setup form."""

    raw_ip = str(user_input.get(CONF_NATIVE_ZENDURE_ZENSDK_IP, "")).strip()
    clear_ip = bool(user_input.get(CONF_NATIVE_ZENDURE_ZENSDK_IP_CLEAR, False))
    if raw_ip and clear_ip:
        return "zensdk_ip_clear_conflict", None, False
    if not raw_ip:
        return None, None, clear_ip
    matrix = resolve_zendure_device(identity)
    if (
        matrix is None
        or matrix.transport(ZendureTransport.ZENSDK).read
        is VerificationLevel.UNSUPPORTED
    ):
        return "zensdk_ip_unsupported", None, False
    try:
        return None, normalize_zensdk_ipv4(raw_ip), False
    except ValueError:
        return "invalid_zensdk_ip", None, False


def _update_native_zensdk_ip(
    setup_map: Mapping[str, Any],
    device_id: str,
    address: str | None,
    *,
    clear: bool = False,
    clear_blank: bool = False,
) -> dict[str, Any]:
    """Persist only this device's explicit LAN address in the setup map."""

    result = reconcile_device_setups((), setup_map)
    record = result["devices"].get(device_id)
    if record is None:
        raise ValueError("native_device_not_discovered")
    if clear or (clear_blank and address is None):
        record.pop("zensdk_ip", None)
    elif address is not None:
        record["zensdk_ip"] = address
    return result


class ZendureSmartFlowConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Battery SmartFlow AI."""

    VERSION = 6

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        return await self.async_step_native_login(user_input)

    async def async_step_native_login(self, user_input=None):
        """Discover first; native setup never requires entities from another integration."""
        errors = {}
        if user_input is not None:
            existing_options = dict(getattr(self, "_native_options", {}))
            token = resolve_app_token_input(
                user_input.get(CONF_NATIVE_ZENDURE_APP_TOKEN),
                existing_options.get(CONF_NATIVE_ZENDURE_APP_TOKEN),
            )
            try:
                from homeassistant.helpers.aiohttp_client import async_get_clientsession

                session = async_get_clientsession(self.hass)

                async def post_json(url, **kwargs):
                    async with session.post(url, **kwargs) as response:
                        payload = await response.json(content_type=None)

                    class Response:
                        async def json(self):
                            return payload

                    return Response()

                self._native_bootstrap = await ZendureCloudClient(
                    post_json
                ).async_discover(token)
                self._native_options = dict(
                    getattr(self, "_native_options", {})
                )
                self._native_options[CONF_NATIVE_ZENDURE_APP_TOKEN] = token
                self._native_setup_map = reconcile_device_setups(
                    self._native_bootstrap.devices,
                    self._native_options.get(CONF_NATIVE_ZENDURE_DEVICE_SETUPS),
                    legacy_selected_device=self._native_options.get(
                        CONF_NATIVE_ZENDURE_SELECTED_DEVICE
                    ),
                    legacy_transport=self._native_options.get(
                        CONF_NATIVE_ZENDURE_CONTROL_TRANSPORT
                    ),
                )
                if getattr(self, "_native_reconfigure", False):
                    self._native_reconfigure_device_ids = [
                        item.candidate.candidate_id
                        for item in self._native_bootstrap.devices
                        if item.candidate.supported
                    ]
                    self._native_reconfigure_index = 0
                    if not self._native_reconfigure_device_ids:
                        return self.async_show_form(
                            step_id="native_login",
                            errors={"base": "no_supported_devices"},
                            data_schema=vol.Schema(
                                {
                                    vol.Optional(
                                        CONF_NATIVE_ZENDURE_APP_TOKEN,
                                        default=STORED_APP_TOKEN_MASK,
                                    ): selector.TextSelector(
                                        selector.TextSelectorConfig(
                                            type=selector.TextSelectorType.PASSWORD
                                        )
                                    )
                                }
                            ),
                        )
                else:
                    self._native_reconfigure_device_ids = None
                return await self.async_step_native_device()
            except ZendureCloudError as error:
                errors["base"] = error.reason
            except Exception:
                errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="native_login", errors=errors,
            data_schema=vol.Schema({
                (
                    vol.Optional(
                        CONF_NATIVE_ZENDURE_APP_TOKEN,
                        default=STORED_APP_TOKEN_MASK,
                    )
                    if getattr(self, "_native_reconfigure", False)
                    and getattr(self, "_native_options", {}).get(
                        CONF_NATIVE_ZENDURE_APP_TOKEN
                    )
                    else vol.Required(CONF_NATIVE_ZENDURE_APP_TOKEN)
                ): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                ),
            }),
        )

    async def async_step_native_device(self, user_input=None):
        devices = self._native_bootstrap.devices
        if getattr(self, "_native_setup_map", None) is None:
            self._native_setup_map = reconcile_device_setups(devices)
        if getattr(self, "_native_reconfigure_device_ids", None) is not None:
            pending = (
                self._native_reconfigure_device_ids[
                    self._native_reconfigure_index
                ]
                if self._native_reconfigure_index
                < len(self._native_reconfigure_device_ids)
                else None
            )
        else:
            pending = next(
                (
                    item.candidate.candidate_id
                    for item in devices
                    if item.candidate.supported
                    and self._native_setup_map["devices"].get(
                        item.candidate.candidate_id, {}
                    ).get("setup_status") != SETUP_COMPLETE
                ),
                None,
            )
        errors = {}
        if user_input is not None:
            selected = next(
                (
                    item for item in devices
                    if item.candidate.candidate_id
                    == user_input.get(CONF_NATIVE_ZENDURE_SELECTED_DEVICE)
                ),
                None,
            )
            profile = resolve_zendure_device(selected.candidate.identity) if selected else None
            if selected is None or selected.candidate.candidate_id != pending:
                errors["base"] = "device_not_found"
            elif profile is None:
                errors["base"] = "unsupported_device"
            else:
                chosen_transport = _requested_native_transport(
                    user_input, selected.candidate.identity
                )
                ip_error, zensdk_ip, clear_zensdk_ip = _validate_native_zensdk_ip(
                    user_input, selected.candidate.identity
                )
                if ip_error is not None:
                    errors["base"] = ip_error
                elif chosen_transport not in _native_transport_options(
                    selected.candidate.identity
                ):
                    errors["base"] = "device_not_found"
                elif (
                    chosen_transport is ZendureTransport.LOCAL_MQTT
                    and not str(user_input.get(
                        CONF_NATIVE_ZENDURE_LOCAL_MQTT_SERVER, ""
                    )).strip()
                ):
                    errors["base"] = "local_mqtt_required"
                else:
                    if (
                        chosen_transport is ZendureTransport.LOCAL_MQTT
                        and bool(user_input.get(
                            CONF_NATIVE_ZENDURE_LEGACY_PROVISION, False
                        ))
                    ):
                        local_port = int(user_input.get(
                            CONF_NATIVE_ZENDURE_LOCAL_MQTT_PORT, 1883
                        ))
                        wifi_ssid = str(user_input.get(
                            CONF_NATIVE_ZENDURE_LEGACY_WIFI_SSID, ""
                        )).strip()
                        wifi_password = resolve_app_token_input(
                            user_input.get(
                                CONF_NATIVE_ZENDURE_LEGACY_WIFI_PASSWORD
                            ),
                            self._native_options.get(
                                CONF_NATIVE_ZENDURE_LEGACY_WIFI_PASSWORD
                            ),
                        )
                        if local_port != 1883:
                            errors["base"] = "legacy_port_required"
                        elif not wifi_ssid or not wifi_password:
                            errors["base"] = "legacy_wifi_required"
                        else:
                            identity = selected.candidate.identity
                            try:
                                if not identity.device_id:
                                    raise ValueError("legacy_device_id_missing")
                                await async_provision_legacy_device(
                                    self.hass,
                                    serial_number=str(
                                        identity.serial_number or ""
                                    ),
                                    display_name=selected.candidate.display_name,
                                    mqtt_server=str(user_input[
                                        CONF_NATIVE_ZENDURE_LOCAL_MQTT_SERVER
                                    ]).strip(),
                                    wifi_ssid=wifi_ssid,
                                    wifi_password=wifi_password,
                                )
                            except Exception as error:
                                reason = str(error) or type(error).__name__
                                errors["base"] = (
                                    reason
                                    if reason in {
                                        "legacy_ble_device_not_found",
                                        "legacy_device_id_missing",
                                    }
                                    else "legacy_provision_failed"
                                )
                    if errors:
                        return self.async_show_form(
                            step_id="native_device",
                            errors=errors,
                            data_schema=ZendureSmartFlowOptionsFlow._native_device_schema(
                                devices,
                                bool(
                                    getattr(self, "_native_options", {}).get(
                                        CONF_NATIVE_ZENDURE_CONTROL_ENABLED, False
                                    )
                                ),
                                getattr(self, "_native_options", None),
                                target_device_id=pending,
                            ),
                            description_placeholders={
                                "device_summary": ZendureSmartFlowOptionsFlow._native_device_summary(
                                    devices
                                )
                            },
                        )
                    self._native_setup_map = save_device_setup(
                        self._native_setup_map,
                        selected.candidate.candidate_id,
                        chosen_transport.value,
                    )
                    self._native_setup_map = _update_native_zensdk_ip(
                        self._native_setup_map,
                        selected.candidate.candidate_id,
                        zensdk_ip,
                        clear=clear_zensdk_ip,
                        clear_blank=True,
                    )
                    active_device_id = self._native_options.get(
                        CONF_NATIVE_ZENDURE_SELECTED_DEVICE
                    )
                    if not active_device_id:
                        active_device_id = selected.candidate.candidate_id
                        self._native_options[
                            CONF_NATIVE_ZENDURE_SELECTED_DEVICE
                        ] = active_device_id
                    if selected.candidate.candidate_id == active_device_id:
                        self._native_options[
                            CONF_NATIVE_ZENDURE_CONTROL_TRANSPORT
                        ] = chosen_transport.value
                        self._native_options[
                            CONF_NATIVE_ZENDURE_CONTROL_ENABLED
                        ] = bool(
                            user_input.get(
                                CONF_NATIVE_ZENDURE_CONTROL_ENABLED,
                                self._native_options.get(
                                    CONF_NATIVE_ZENDURE_CONTROL_ENABLED, False
                                ),
                            )
                        )
                    for key in (
                        CONF_NATIVE_ZENDURE_LOCAL_MQTT_SERVER,
                        CONF_NATIVE_ZENDURE_LOCAL_MQTT_PORT,
                        CONF_NATIVE_ZENDURE_LOCAL_MQTT_USERNAME,
                        CONF_NATIVE_ZENDURE_LOCAL_MQTT_PASSWORD,
                        CONF_NATIVE_ZENDURE_LEGACY_WIFI_SSID,
                        CONF_NATIVE_ZENDURE_LEGACY_WIFI_PASSWORD,
                    ):
                        if key in user_input:
                            if key in {
                                CONF_NATIVE_ZENDURE_LOCAL_MQTT_PASSWORD,
                                CONF_NATIVE_ZENDURE_LEGACY_WIFI_PASSWORD,
                            }:
                                self._native_options[key] = resolve_app_token_input(
                                    user_input[key],
                                    self._native_options.get(key),
                                )
                            else:
                                self._native_options[key] = user_input[key]
                    if getattr(self, "_native_reconfigure_device_ids", None) is not None:
                        self._native_reconfigure_index += 1
                        if self._native_reconfigure_index < len(
                            self._native_reconfigure_device_ids
                        ):
                            next_id = self._native_reconfigure_device_ids[
                                self._native_reconfigure_index
                            ]
                            return self.async_show_form(
                                step_id="native_device",
                                data_schema=(
                                    ZendureSmartFlowOptionsFlow._native_device_schema(
                                        devices,
                                        bool(
                                            self._native_options.get(
                                                CONF_NATIVE_ZENDURE_CONTROL_ENABLED,
                                                False,
                                            )
                                        ),
                                        self._native_options,
                                        target_device_id=next_id,
                                    )
                                ),
                                description_placeholders={
                                    "device_summary": (
                                        ZendureSmartFlowOptionsFlow._native_device_summary(
                                            devices
                                        )
                                    )
                                },
                            )
                        self._native_options[
                            CONF_NATIVE_ZENDURE_DEVICE_SETUPS
                        ] = self._native_setup_map
                        entry = self._migration_entry
                        self._user_input["connection_type"] = "native"
                        self._user_input.setdefault(
                            CONF_DEVICE_PROFILE, profile.profile_key
                        )
                        return self.async_update_and_abort(
                            entry,
                            data=self._user_input,
                            options=self._native_options,
                            reason="reconfigure_success",
                        )
                    if setup_is_complete(self._native_setup_map):
                        self._native_options[
                            CONF_NATIVE_ZENDURE_DEVICE_SETUPS
                        ] = self._native_setup_map
                        self._native_options.setdefault(
                            CONF_NATIVE_ZENDURE_CONTROL_ENABLED, False
                        )
                        self._native_options.update({
                            key: value for key, value in user_input.items()
                            if key in {
                                CONF_NATIVE_ZENDURE_LOCAL_MQTT_SERVER,
                                CONF_NATIVE_ZENDURE_LOCAL_MQTT_PORT,
                                CONF_NATIVE_ZENDURE_LOCAL_MQTT_USERNAME,
                                CONF_NATIVE_ZENDURE_LOCAL_MQTT_PASSWORD,
                                CONF_NATIVE_ZENDURE_LEGACY_WIFI_SSID,
                                CONF_NATIVE_ZENDURE_LEGACY_WIFI_PASSWORD,
                            }
                        })
                        self._user_input = dict(
                            getattr(self, "_migration_entry", None).data
                            if getattr(self, "_migration_entry", None) is not None
                            else {}
                        )
                        self._user_input["connection_type"] = "native"
                        self._user_input[CONF_DEVICE_PROFILE] = profile.profile_key
                        return await self.async_step_native_external()
                    next_id = next(
                        item.candidate.candidate_id for item in devices
                        if item.candidate.supported
                        and self._native_setup_map["devices"].get(
                            item.candidate.candidate_id, {}
                        ).get("setup_status") != SETUP_COMPLETE
                    )
                    return self.async_show_form(
                        step_id="native_device",
                        data_schema=ZendureSmartFlowOptionsFlow._native_device_schema(
                            devices, target_device_id=next_id
                        ),
                        description_placeholders={
                            "device_summary": (
                                ZendureSmartFlowOptionsFlow._native_device_summary(
                                    devices
                                )
                            )
                        },
                    )
        return self.async_show_form(
            step_id="native_device", errors=errors,
            data_schema=ZendureSmartFlowOptionsFlow._native_device_schema(
                devices,
                bool(
                    getattr(self, "_native_options", {}).get(
                        CONF_NATIVE_ZENDURE_CONTROL_ENABLED, False
                    )
                ),
                getattr(self, "_native_options", None),
                target_device_id=pending,
            ),
            description_placeholders={
                "device_summary": (
                    ZendureSmartFlowOptionsFlow._native_device_summary(devices)
                ),
            },
        )

    async def async_step_native_external(self, user_input=None):
        migration_entry = getattr(self, "_migration_entry", None)
        if user_input is not None:
            self._user_input.update(user_input)
            return await self.async_step_grid()
        return self.async_show_form(
            step_id="native_external",
            data_schema=self._base_schema(
                migration_entry,
                native=True,
                forecast_options=await self._forecast_options(),
            ),
        )

    async def async_step_grid(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        grid_mode = self._user_input.get(CONF_GRID_MODE, GRID_MODE_NONE)

        if user_input is not None:
            self._user_input.update(user_input)

            shelly_host_key, shelly_password_key = _shelly_grid_keys(grid_mode)
            if shelly_host_key:
                try:
                    self._user_input[shelly_host_key] = validate_shelly_host(
                        self._user_input.get(shelly_host_key, "")
                    )
                except ValueError:
                    errors["base"] = "invalid_shelly_host"

            if grid_mode == GRID_MODE_SPLIT:
                if (
                    not user_input.get(CONF_GRID_IMPORT_ENTITY)
                    or not user_input.get(CONF_GRID_EXPORT_ENTITY)
                ):
                    errors["base"] = "grid_split_missing"

            _cleanup_optional_entities(self._user_input)
            _apply_forecast_selection(self._user_input)
            
            self._user_input[CONF_FEED_IN_TARIFF] = _normalize_optional_float(
                self._user_input.get(CONF_FEED_IN_TARIFF),
                DEFAULT_FEED_IN_TARIFF,
            )

            if grid_mode != GRID_MODE_SINGLE:
                self._user_input.pop(CONF_GRID_POWER_ENTITY, None)

            if grid_mode != GRID_MODE_SPLIT:
                self._user_input.pop(CONF_GRID_IMPORT_ENTITY, None)
                self._user_input.pop(CONF_GRID_EXPORT_ENTITY, None)

            for host_key in (CONF_SHELLY_PRO_3EM_HOST, CONF_SHELLY_3EM_HOST):
                if host_key != shelly_host_key:
                    self._user_input.pop(host_key, None)

            shelly_password = str(self._user_input.pop(shelly_password_key, "") or "").strip() if shelly_password_key else ""
            for password_key in (CONF_SHELLY_PRO_3EM_PASSWORD, CONF_SHELLY_3EM_PASSWORD):
                self._user_input.pop(password_key, None)
            if shelly_password and shelly_password != STORED_APP_TOKEN_MASK:
                self._native_options = getattr(self, "_native_options", {})
                self._native_options[shelly_password_key] = shelly_password

            migration_entry = getattr(self, "_migration_entry", None)
            if not errors and migration_entry is not None:
                # Preserve the config entry identity and non-hardware inputs.
                # Home Assistant state storage is keyed by entry_id, so this
                # also retains learned state and accumulated statistics.
                for key in LEGACY_BATTERY_ENTITY_KEYS:
                    self._user_input.pop(key, None)
                self._user_input["connection_type"] = "native"

                options = dict(migration_entry.options)
                options.update(getattr(self, "_native_options", {}))
                for key in (
                    *LEGACY_BATTERY_ENTITY_KEYS,
                    *LOWEST_CELL_VOLTAGE_CONFIG_KEYS,
                ):
                    options.pop(key, None)
                options.pop(CONF_DEVICE_PROFILE, None)
                return self.async_update_and_abort(
                    migration_entry,
                    data=self._user_input,
                    options=options,
                    reason="reconfigure_success",
                )

            if not errors:
                return self.async_create_entry(
                    title="Battery SmartFlow AI",
                    data=self._user_input,
                    options=getattr(self, "_native_options", {}),
                )

        return self.async_show_form(
            step_id="grid",
            data_schema=self._grid_schema(
                grid_mode, getattr(self, "_migration_entry", None)
            ),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None):
        entry = self._get_reconfigure_entry()

        if entry.data.get("connection_type") != "native":
            # Convert the existing config entry in place so its options and
            # entry-id-backed runtime store survive the move from V5 controls.
            self._migration_entry = entry
            self._native_options = dict(entry.options)
            return await self.async_step_native_login()

        self._migration_entry = entry
        self._native_options = dict(entry.options)
        self._native_reconfigure = True

        if user_input is not None:
            self._user_input = dict(entry.data)
            self._user_input.update(user_input)
            return await self.async_step_reconfigure_grid()

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self._base_schema(
                entry, forecast_options=await self._forecast_options()
            ),
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

            shelly_host_key, shelly_password_key = _shelly_grid_keys(grid_mode)
            if shelly_host_key:
                try:
                    cleaned[shelly_host_key] = validate_shelly_host(
                        cleaned.get(shelly_host_key, "")
                    )
                except ValueError:
                    errors["base"] = "invalid_shelly_host"

            if grid_mode != GRID_MODE_SINGLE:
                cleaned.pop(CONF_GRID_POWER_ENTITY, None)

            if grid_mode != GRID_MODE_SPLIT:
                cleaned.pop(CONF_GRID_IMPORT_ENTITY, None)
                cleaned.pop(CONF_GRID_EXPORT_ENTITY, None)

            for host_key in (CONF_SHELLY_PRO_3EM_HOST, CONF_SHELLY_3EM_HOST):
                if host_key != shelly_host_key:
                    cleaned.pop(host_key, None)

            if grid_mode == GRID_MODE_SPLIT:
                if (
                    not cleaned.get(CONF_GRID_IMPORT_ENTITY)
                    or not cleaned.get(CONF_GRID_EXPORT_ENTITY)
                ):
                    errors["base"] = "grid_split_missing"

            _cleanup_optional_entities(cleaned)
            _apply_forecast_selection(cleaned)

            shelly_password = str(cleaned.pop(shelly_password_key, "") or "").strip() if shelly_password_key else ""
            for password_key in (CONF_SHELLY_PRO_3EM_PASSWORD, CONF_SHELLY_3EM_PASSWORD):
                cleaned.pop(password_key, None)
            options_updates = dict(entry.options)
            for password_key in (CONF_SHELLY_PRO_3EM_PASSWORD, CONF_SHELLY_3EM_PASSWORD):
                if password_key != shelly_password_key or not shelly_password:
                    options_updates.pop(password_key, None)
            if shelly_password_key and shelly_password and shelly_password != STORED_APP_TOKEN_MASK:
                options_updates[shelly_password_key] = shelly_password
            
            cleaned[CONF_FEED_IN_TARIFF] = _normalize_optional_float(
                cleaned.get(CONF_FEED_IN_TARIFF),
                DEFAULT_FEED_IN_TARIFF,
            )

            if not errors:
                if getattr(self, "_native_reconfigure", False):
                    self._user_input = cleaned
                    self._native_options = dict(entry.options)
                    self._native_options.update(options_updates)
                    return await self.async_step_native_login()
                # The entry update listener reloads the integration after the
                # data/options change, so use the non-reloading flow helper.
                return self.async_update_and_abort(
                    entry,
                    data=cleaned,
                    options=options_updates,
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
        *, native: bool = False,
        forecast_options: list[dict[str, str]] | None = None,
    ) -> vol.Schema:
        def _val(key: str):
            if not entry:
                return None

            value = entry.data.get(key)

            if key in OPTIONAL_ENTITY_KEYS:
                return _normalize_optional_entity(value)

            return value

        schema: dict[Any, Any] = {}
        currency = resolve_price_currency(
            getattr(self.hass.config, "currency", None)
        )
        price_profile = price_input_profile(currency)

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
                        "label": DEVICE_PROFILE_MODELS[key].label,
                    }
                    for key in DEVICE_PROFILE_MODELS
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

        is_native = native or bool(
            entry and entry.data.get("connection_type") == "native"
        )
        if is_native:
            pv_value = _val(CONF_PV_ENTITY)
            pv_entity_key = (
                vol.Optional(CONF_PV_ENTITY, default=pv_value)
                if pv_value
                else vol.Optional(CONF_PV_ENTITY)
            )
        else:
            pv_entity_key = vol.Required(
                CONF_PV_ENTITY, default=_val(CONF_PV_ENTITY)
            )
        schema[pv_entity_key] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        )

        native_pv_val = _val(CONF_NATIVE_PV_ENTITY)
        if native_pv_val:
            schema[
                vol.Optional(CONF_NATIVE_PV_ENTITY, default=native_pv_val)
            ] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            )
        else:
            schema[vol.Optional(CONF_NATIVE_PV_ENTITY)] = selector.EntitySelector(
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
        ] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0.0,
                max=price_profile.maximum,
                step=price_profile.step,
                mode=selector.NumberSelectorMode.BOX,
                unit_of_measurement=currency.price_unit,
            )
        )

        dynamic_feed_in_val = _val(CONF_DYNAMIC_FEED_IN_PRICE_ENTITY)
        if dynamic_feed_in_val:
            schema[
                vol.Optional(
                    CONF_DYNAMIC_FEED_IN_PRICE_ENTITY,
                    default=dynamic_feed_in_val,
                )
            ] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            )
        else:
            schema[
                vol.Optional(CONF_DYNAMIC_FEED_IN_PRICE_ENTITY)
            ] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            )

        selected_forecasts = _normalize_forecast_entries(
            _val(CONF_PV_FORECAST_CONFIG_ENTRIES)
        )
        available_forecasts = list(forecast_options or [])
        known_ids = {item["value"] for item in available_forecasts}
        for entry_id in selected_forecasts:
            if entry_id not in known_ids:
                available_forecasts.append(
                    {"value": entry_id, "label": entry_id}
                )
        forecast_key = (
            vol.Optional(
                CONF_PV_FORECAST_CONFIG_ENTRIES,
                default=selected_forecasts,
            )
            if selected_forecasts
            else vol.Optional(CONF_PV_FORECAST_CONFIG_ENTRIES)
        )
        schema[forecast_key] = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=available_forecasts,
                multiple=True,
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
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
                    GRID_MODE_NONE,
                    GRID_MODE_SINGLE,
                    GRID_MODE_SPLIT,
                    GRID_MODE_SHELLY_PRO_3EM,
                    GRID_MODE_SHELLY_PRO_3EM_MODBUS,
                    GRID_MODE_SHELLY_3EM,
                ],
                translation_key="grid_mode",
            )
        )

        if native or (entry and (
            entry.data.get("connection_type") == "native"
            or entry.options.get(CONF_NATIVE_ZENDURE_CONTROL_ENABLED, False)
        )):
            hardware_keys = {
                CONF_DEVICE_PROFILE, CONF_SOC_ENTITY, CONF_SOC_LIMIT_ENTITY,
                CONF_PACK_CAPACITY_KWH, CONF_NATIVE_PV_ENTITY,
                CONF_BATTERY_AC_POWER_ENTITY,
                CONF_ADDITIONAL_BATTERY_CHARGE_ENTITY,
                CONF_ADDITIONAL_BATTERY_DISCHARGE_ENTITY,
                CONF_AC_MODE_ENTITY,
                CONF_INPUT_LIMIT_ENTITY, CONF_OUTPUT_LIMIT_ENTITY,
                CONF_OFFGRID_POWER_ENTITY, CONF_OFFGRID_MODE_ENTITY,
            }
            schema = {key: value for key, value in schema.items() if key.schema not in hardware_keys}
        return vol.Schema(schema)

    async def _forecast_options(self) -> list[dict[str, str]]:
        """List the same solar-forecast providers exposed to HA Energy."""

        try:
            return await async_energy_forecast_sources(self.hass)
        except Exception:
            return []

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

        if grid_mode in GRID_MODE_DIRECT_SHELLY:
            host_key, password_key = _shelly_grid_keys(grid_mode)
            schema[
                vol.Required(
                    host_key,
                    default=_val(host_key) or "",
                )
            ] = selector.TextSelector()
            stored_password = (
                entry.options.get(password_key)
                if entry is not None
                else None
            )
            if grid_mode != GRID_MODE_SHELLY_PRO_3EM_MODBUS:
                schema[
                    vol.Optional(
                        password_key,
                        default=(STORED_APP_TOKEN_MASK if stored_password else ""),
                    )
                ] = selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.PASSWORD
                    )
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
        self._native_bootstrap = None
        self._native_token: str | None = None
        self._native_setup_map: dict[str, Any] | None = None

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
        merged_options = remove_deprecated_profile_overrides(
            self.config_entry.options
        )

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

        if SETTING_FULL_CHARGE_MAINTENANCE_ENABLED in user_input:
            merged_options[SETTING_FULL_CHARGE_MAINTENANCE_ENABLED] = bool(
                user_input[SETTING_FULL_CHARGE_MAINTENANCE_ENABLED]
            )
        if SETTING_FULL_CHARGE_MAINTENANCE_INTERVAL_DAYS in user_input:
            merged_options[SETTING_FULL_CHARGE_MAINTENANCE_INTERVAL_DAYS] = int(
                user_input[SETTING_FULL_CHARGE_MAINTENANCE_INTERVAL_DAYS]
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
            menu_options=[
                "general",
                "expert",
                "dashboard",
                "smart_mode",
                "native_zendure",
                "systems_groups",
                "energy_scopes",
                "training",
                "debug",
            ],
        )

    def _energy_scope_config(self):
        return normalize_energy_scope_config(
            self.config_entry.options.get(CONF_ENERGY_SCOPES)
        )

    def _energy_scope_choices(self):
        scopes = self._energy_scope_config()["scopes"]
        return [
            {"value": scope_id, "label": scope["name"]}
            for scope_id, scope in sorted(
                scopes.items(), key=lambda item: item[1]["name"].casefold()
            )
        ]

    async def async_step_energy_scopes(self, user_input=None):
        """Manage persistent measurement and forecast scopes."""

        menu_options = ["energy_scope_create"]
        if self._energy_scope_choices():
            menu_options.extend(
                ("energy_scope_edit_select", "energy_scope_remove_select")
            )
        return self.async_show_menu(
            step_id="energy_scopes", menu_options=menu_options
        )

    def _energy_scope_schema(self, current=None):
        current = current or {}
        groups = self._group_choices()
        if not groups:
            groups = [{"value": "", "label": "Keine Gruppe zugeordnet"}]
        return vol.Schema(
            {
                vol.Required("name", default=current.get("name", "")): str,
                vol.Optional("group_ids", default=current.get("group_ids", [])): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=groups,
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    "grid_mode", default=current.get("grid_mode", ENERGY_GRID_MODE_NONE)
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            ENERGY_GRID_MODE_NONE,
                            ENERGY_GRID_MODE_SIGNED,
                            ENERGY_GRID_MODE_SPLIT,
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        translation_key="energy_scope_grid_mode",
                    )
                ),
                vol.Optional(
                    "grid_power_entities",
                    default=current.get("grid_power_entities", []),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", multiple=True)
                ),
                vol.Optional(
                    "grid_phase_power_entities",
                    default=current.get("grid_phase_power_entities", []),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", multiple=True)
                ),
                vol.Optional(
                    "grid_import_entities",
                    default=current.get("grid_import_entities", []),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", multiple=True)
                ),
                vol.Optional(
                    "grid_export_entities",
                    default=current.get("grid_export_entities", []),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", multiple=True)
                ),
                vol.Optional(
                    "price_entity",
                    description={"suggested_value": current["price_entity"]}
                    if current.get("price_entity") else None,
                ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
                vol.Optional(
                    "export_price_entity",
                    description={"suggested_value": current["export_price_entity"]}
                    if current.get("export_price_entity") else None,
                ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
            }
        )

    async def async_step_energy_scope_create(self, user_input=None):
        if user_input is not None:
            self._active_energy_scope_id = uuid4().hex
            self._draft_energy_scope = {
                **user_input,
                "pv_sources": [],
            }
            return self.async_show_menu(
                step_id="energy_scope_pv_sources",
                menu_options=["energy_scope_pv_add", "energy_scope_save"],
            )
        return self.async_show_form(
            step_id="energy_scope_create",
            data_schema=self._energy_scope_schema(),
        )

    async def async_step_energy_scope_pv_sources(self, user_input=None):
        """Collect and map each PV source and its forecast provider."""

        menu_options = ["energy_scope_pv_add", "energy_scope_save"]
        if self._draft_energy_scope.get("pv_sources"):
            menu_options.append("energy_scope_pv_remove_select")
        if self._active_energy_scope_id in self._energy_scope_config()["scopes"]:
            menu_options.insert(0, "energy_scope_edit")
        return self.async_show_menu(
            step_id="energy_scope_pv_sources", menu_options=menu_options
        )

    async def async_step_energy_scope_edit_select(self, user_input=None):
        choices = self._energy_scope_choices()
        if user_input is not None:
            scope_id = str(user_input["scope_id"])
            scope = self._energy_scope_config()["scopes"].get(scope_id)
            if scope is None:
                return self.async_abort(reason="scope_not_found")
            self._active_energy_scope_id = scope_id
            self._draft_energy_scope = dict(scope)
            return await self.async_step_energy_scope_pv_sources()
        return self.async_show_form(
            step_id="energy_scope_edit_select",
            data_schema=vol.Schema(
                {
                    vol.Required("scope_id"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=choices,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    async def async_step_energy_scope_edit(self, user_input=None):
        if user_input is not None:
            self._draft_energy_scope.update({
                **user_input,
                "price_entity": user_input.get("price_entity") or "",
                "export_price_entity": user_input.get("export_price_entity") or "",
            })
            return await self.async_step_energy_scope_pv_sources()
        return self.async_show_form(
            step_id="energy_scope_edit",
            data_schema=self._energy_scope_schema(self._draft_energy_scope),
        )

    async def async_step_energy_scope_pv_add(self, user_input=None):
        if user_input is not None:
            source = {
                "id": uuid4().hex,
                "name": user_input["source_name"],
                "mode": user_input["source_mode"],
                "power_entities": user_input.get("power_entities", []),
                "forecast_entry_ids": user_input.get("forecast_entry_ids", []),
                "installed_power_wp": user_input.get("installed_power_wp"),
            }
            self._draft_energy_scope.setdefault("pv_sources", []).append(source)
            return await self.async_step_energy_scope_pv_sources()
        try:
            forecast_options = await async_energy_forecast_sources(self.hass)
        except Exception:
            forecast_options = []
        return self.async_show_form(
            step_id="energy_scope_pv_add",
            data_schema=vol.Schema(
                {
                    vol.Required("source_name"): str,
                    vol.Required("source_mode", default=PV_SOURCE_AGGREGATE): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[PV_SOURCE_AGGREGATE, PV_SOURCE_COMPONENTS],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            translation_key="energy_scope_pv_mode",
                        )
                    ),
                    vol.Optional("power_entities", default=[]): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor", multiple=True)
                    ),
                    vol.Optional("installed_power_wp"): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=100000,
                            step=10,
                            mode=selector.NumberSelectorMode.BOX,
                            unit_of_measurement="Wp",
                        )
                    ),
                    vol.Optional(
                        "forecast_entry_ids", default=[]
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=forecast_options,
                            multiple=True,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    async def async_step_energy_scope_pv_remove_select(self, user_input=None):
        sources = self._draft_energy_scope.get("pv_sources", [])
        choices = [
            {"value": source["id"], "label": source["name"]}
            for source in sources
        ]
        if user_input is not None:
            source_id = str(user_input["source_id"])
            self._draft_energy_scope["pv_sources"] = [
                source for source in sources if source["id"] != source_id
            ]
            return await self.async_step_energy_scope_pv_sources()
        if not choices:
            return self.async_abort(reason="no_pv_sources")
        return self.async_show_form(
            step_id="energy_scope_pv_remove_select",
            data_schema=vol.Schema(
                {
                    vol.Required("source_id"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=choices,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    async def async_step_energy_scope_save(self, user_input=None):
        scope_id = getattr(self, "_active_energy_scope_id", None)
        scope = getattr(self, "_draft_energy_scope", None)
        if not scope_id or not isinstance(scope, dict):
            return self.async_abort(reason="scope_not_found")
        try:
            config = save_energy_scope(
                self._energy_scope_config(), scope_id=scope_id, scope=scope
            )
        except (TypeError, ValueError):
            return self.async_show_form(
                step_id="energy_scope_edit",
                data_schema=self._energy_scope_schema(scope),
                errors={"base": "invalid_energy_scope"},
            )
        options = dict(self.config_entry.options)
        options[CONF_ENERGY_SCOPES] = config
        return self.async_create_entry(title="", data=options)

    async def async_step_energy_scope_remove_select(self, user_input=None):
        choices = self._energy_scope_choices()
        if user_input is not None:
            options = dict(self.config_entry.options)
            options[CONF_ENERGY_SCOPES] = remove_energy_scope(
                self._energy_scope_config(), str(user_input["scope_id"])
            )
            return self.async_create_entry(title="", data=options)
        return self.async_show_form(
            step_id="energy_scope_remove_select",
            data_schema=vol.Schema(
                {
                    vol.Required("scope_id"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=choices,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    async def async_step_systems_groups(
        self, user_input: dict[str, Any] | None = None
    ):
        """Open the persistent device and battery-group editor."""

        menu_options = ["group_create"]
        if self._group_choices():
            menu_options.extend(("group_edit_select", "group_remove"))
        return self.async_show_menu(
            step_id="systems_groups", menu_options=menu_options
        )

    def _group_config(self):
        """Read groups and include the safe one-time legacy-system migration."""

        options = self.config_entry.options
        return migrate_single_device_group(
            options.get(CONF_BATTERY_GROUPS),
            setup_map=options.get(CONF_NATIVE_ZENDURE_DEVICE_SETUPS),
            selected_device_id=options.get(CONF_NATIVE_ZENDURE_SELECTED_DEVICE),
        )

    def _group_device_choices(self, *, include_members=()):
        """Build safe display labels for configured systems and saved members."""

        options = self.config_entry.options
        setup_map = options.get(CONF_NATIVE_ZENDURE_DEVICE_SETUPS, {})
        records = setup_map.get("devices", {}) if isinstance(setup_map, Mapping) else {}
        choices = {}
        if isinstance(records, Mapping):
            for device_id, record in records.items():
                if not isinstance(device_id, str) or not isinstance(record, Mapping):
                    continue
                if record.get("setup_status") != SETUP_COMPLETE:
                    continue
                name = str(record.get("display_name") or record.get("model") or "Zendure")
                model = str(record.get("model") or "").strip()
                if model and model.casefold() not in name.casefold():
                    name = f"{name} – {model}"
                suffix = record.get("serial_suffix")
                if suffix:
                    name = f"{name} · SN {suffix}"
                if record.get("online") is False:
                    name = f"{name} (offline)"
                choices[device_id] = name
        groups = self._group_config()
        for group in groups["groups"].values():
            for device_id in group["members"]:
                if device_id not in choices:
                    public_suffix = hashlib.sha256(device_id.encode()).hexdigest()[:6]
                    choices[device_id] = f"Offline / derzeit nicht erkannt ({public_suffix})"
        for device_id in include_members:
            if device_id not in choices:
                public_suffix = hashlib.sha256(device_id.encode()).hexdigest()[:6]
                choices[device_id] = f"Offline / derzeit nicht erkannt ({public_suffix})"
        label_counts: dict[str, int] = {}
        for label in choices.values():
            normalized = label.casefold()
            label_counts[normalized] = label_counts.get(normalized, 0) + 1
        for device_id, label in tuple(choices.items()):
            if label_counts.get(label.casefold(), 0) <= 1:
                continue
            record = records.get(device_id, {}) if isinstance(records, Mapping) else {}
            serial_suffix = (
                str(record.get("serial_suffix") or "").strip()
                if isinstance(record, Mapping)
                else ""
            )
            suffix = serial_suffix or hashlib.sha256(device_id.encode()).hexdigest()[:6]
            marker = "SN" if serial_suffix else "ID"
            choices[device_id] = f"{label} · {marker} {suffix}"
        return [
            {"value": device_id, "label": label}
            for device_id, label in sorted(choices.items(), key=lambda item: item[1].casefold())
        ]

    def _group_choices(self):
        groups = self._group_config()["groups"]
        return [
            {"value": group_id, "label": group["name"]}
            for group_id, group in sorted(groups.items(), key=lambda item: item[1]["name"].casefold())
        ]

    async def async_step_group_create(self, user_input=None):
        """Create one named group; all chosen memberships are explicit."""

        if user_input is not None:
            try:
                groups = save_group(
                    self._group_config(),
                    group_id=uuid4().hex,
                    name=user_input["name"],
                    members=user_input.get("members", []),
                    move_members=True,
                )
            except (KeyError, TypeError, ValueError):
                return self.async_abort(reason="invalid_group")
            options = dict(self.config_entry.options)
            options[CONF_BATTERY_GROUPS] = groups
            return self.async_create_entry(title="", data=options)

        return self.async_show_form(
            step_id="group_create",
            data_schema=vol.Schema(
                {
                    vol.Required("name"): str,
                    vol.Optional("members", default=[]): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=self._group_device_choices(),
                            multiple=True,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    async def async_step_group_edit_select(self, user_input=None):
        """Select a saved group to rename or move configured devices."""

        choices = self._group_choices()
        if not choices:
            return self.async_abort(reason="no_groups")
        if user_input is not None:
            self._active_group_id = str(user_input["group_id"])
            return await self.async_step_group_edit()
        return self.async_show_form(
            step_id="group_edit_select",
            data_schema=vol.Schema(
                {vol.Required("group_id"): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=choices, mode=selector.SelectSelectorMode.DROPDOWN)
                )}
            ),
        )

    async def async_step_group_edit(self, user_input=None):
        """Persist one group edit and atomically move selected memberships."""

        group_id = getattr(self, "_active_group_id", None)
        groups = self._group_config()
        current = groups["groups"].get(group_id)
        if current is None:
            return self.async_abort(reason="group_not_found")
        if user_input is not None:
            try:
                groups = save_group(
                    groups,
                    group_id=group_id,
                    name=user_input["name"],
                    members=user_input.get("members", []),
                    move_members=True,
                )
            except (KeyError, TypeError, ValueError):
                return self.async_abort(reason="invalid_group")
            options = dict(self.config_entry.options)
            options[CONF_BATTERY_GROUPS] = groups
            return self.async_create_entry(title="", data=options)
        schema = vol.Schema(
            {
                vol.Required("name"): str,
                vol.Optional("members", default=[]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=self._group_device_choices(
                            include_members=current["members"]
                        ),
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="group_edit",
            data_schema=self.add_suggested_values_to_schema(
                schema,
                {"name": current["name"], "members": current["members"]},
            ),
        )

    async def async_step_group_remove(self, user_input=None):
        """Remove only the selected group, leaving its devices ungrouped."""

        choices = self._group_choices()
        if not choices:
            return self.async_abort(reason="no_groups")
        if user_input is not None:
            options = dict(self.config_entry.options)
            options[CONF_BATTERY_GROUPS] = remove_group(
                self._group_config(),
                str(user_input["group_id"]),
            )
            return self.async_create_entry(title="", data=options)
        return self.async_show_form(
            step_id="group_remove",
            data_schema=vol.Schema(
                {vol.Required("group_id"): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=choices, mode=selector.SelectSelectorMode.DROPDOWN)
                )}
            ),
        )

    async def async_step_smart_mode(
        self, user_input: dict[str, Any] | None = None
    ):
        """Choose whether Zendure devices should stay in Smart Mode 1 at idle."""

        if user_input is not None:
            options = dict(self.config_entry.options)
            options.update(self._working_options)
            options[CONF_NATIVE_ZENDURE_ALWAYS_SMART_MODE_1] = bool(
                user_input.get(CONF_NATIVE_ZENDURE_ALWAYS_SMART_MODE_1, True)
            )
            return self.async_create_entry(title="", data=options)

        return self.async_show_form(
            step_id="smart_mode",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_NATIVE_ZENDURE_ALWAYS_SMART_MODE_1,
                        default=bool(
                            self.config_entry.options.get(
                                CONF_NATIVE_ZENDURE_ALWAYS_SMART_MODE_1, True
                            )
                        ),
                    ): selector.BooleanSelector(),
                }
            ),
        )

    async def async_step_dashboard(self, user_input: dict[str, Any] | None = None):
        """Configure the optional standalone HEMS dashboard."""

        if user_input is not None:
            options = dict(self.config_entry.options)
            options[CONF_HEMS_DASHBOARD_ENABLED] = bool(
                user_input.get(CONF_HEMS_DASHBOARD_ENABLED, False)
            )
            return self.async_create_entry(title="", data=options)

        return self.async_show_form(
            step_id="dashboard",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_HEMS_DASHBOARD_ENABLED,
                        default=bool(
                            self.config_entry.options.get(
                                CONF_HEMS_DASHBOARD_ENABLED, False
                            )
                        ),
                    ): selector.BooleanSelector(),
                }
            ),
        )

    async def async_step_native_zendure(
        self, user_input: dict[str, Any] | None = None
    ):
        """Validate the App Token and discover devices without storing MQTT data."""

        errors: dict[str, str] = {}
        if user_input is not None:
            token = resolve_app_token_input(
                user_input.get(CONF_NATIVE_ZENDURE_APP_TOKEN),
                self.config_entry.options.get(CONF_NATIVE_ZENDURE_APP_TOKEN),
            )
            try:
                from homeassistant.helpers.aiohttp_client import async_get_clientsession

                session = async_get_clientsession(self.hass)

                async def post_json(url: str, **kwargs: Any):
                    async with session.post(url, **kwargs) as response:
                        payload = await response.json(content_type=None)

                    class Response:
                        async def json(self):
                            return payload

                    return Response()

                self._native_bootstrap = await ZendureCloudClient(
                    post_json
                ).async_discover(token)
                self._native_token = token
                self._native_setup_map = reconcile_device_setups(
                    self._native_bootstrap.devices,
                    self.config_entry.options.get(CONF_NATIVE_ZENDURE_DEVICE_SETUPS),
                    legacy_selected_device=self.config_entry.options.get(
                        CONF_NATIVE_ZENDURE_SELECTED_DEVICE
                    ),
                    legacy_transport=self.config_entry.options.get(
                        CONF_NATIVE_ZENDURE_CONTROL_TRANSPORT
                    ),
                )
                return await self.async_step_native_zendure_device()
            except ZendureCloudError as error:
                errors["base"] = error.reason
            except Exception:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="native_zendure",
            data_schema=self._native_token_schema(),
            errors=errors,
        )

    def _native_token_schema(self) -> vol.Schema:
        configured = bool(
            self.config_entry.options.get(CONF_NATIVE_ZENDURE_APP_TOKEN)
        )
        token_key = (
            vol.Optional(
                CONF_NATIVE_ZENDURE_APP_TOKEN,
                default=STORED_APP_TOKEN_MASK,
            )
            if configured
            else vol.Required(CONF_NATIVE_ZENDURE_APP_TOKEN)
        )
        schema: dict[Any, Any] = {
            token_key: selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            )
        }
        return vol.Schema(schema)

    async def async_step_native_zendure_device(
        self, user_input: dict[str, Any] | None = None
    ):
        """Select one test system while retaining all devices for observation."""

        if self._native_bootstrap is None or self._native_token is None:
            return await self.async_step_native_zendure()

        devices = self._native_bootstrap.devices
        if self._native_setup_map is None:
            self._native_setup_map = reconcile_device_setups(
                devices,
                self.config_entry.options.get(CONF_NATIVE_ZENDURE_DEVICE_SETUPS),
                legacy_selected_device=self.config_entry.options.get(
                    CONF_NATIVE_ZENDURE_SELECTED_DEVICE
                ),
                legacy_transport=self.config_entry.options.get(
                    CONF_NATIVE_ZENDURE_CONTROL_TRANSPORT
                ),
            )
        pending = next(
            (
                item.candidate.candidate_id
                for item in devices
                if item.candidate.supported
                and self._native_setup_map["devices"].get(
                    item.candidate.candidate_id, {}
                ).get("setup_status") != SETUP_COMPLETE
            ),
            None,
        )
        if user_input is not None:
            selected = str(user_input[CONF_NATIVE_ZENDURE_SELECTED_DEVICE])
            valid = {item.candidate.candidate_id for item in devices}
            if selected not in valid or (pending is not None and selected != pending):
                return self.async_show_form(
                    step_id="native_zendure_device",
                    data_schema=self._native_device_schema(
                        devices,
                        bool(self.config_entry.options.get(
                            CONF_NATIVE_ZENDURE_CONTROL_ENABLED, False
                        )),
                        self.config_entry.options,
                    ),
                    errors={"base": "device_not_found"},
                    description_placeholders={
                        "device_summary": self._native_device_summary(devices)
                    },
                )
            options = dict(self.config_entry.options)
            options.update(self._working_options)
            options[CONF_NATIVE_ZENDURE_APP_TOKEN] = self._native_token
            selected_device = next(
                item for item in devices
                if item.candidate.candidate_id == selected
            )
            if not selected_device.candidate.supported:
                return self.async_show_form(
                    step_id="native_zendure_device",
                    data_schema=self._native_device_schema(
                        devices, True, options, target_device_id=pending
                    ),
                    errors={"base": "unsupported_device"},
                    description_placeholders={
                        "device_summary": self._native_device_summary(devices)
                    },
                )
            chosen_transport = _requested_native_transport(
                user_input, selected_device.candidate.identity
            )
            ip_error, zensdk_ip, clear_zensdk_ip = _validate_native_zensdk_ip(
                user_input, selected_device.candidate.identity
            )
            if ip_error is not None:
                return self.async_show_form(
                    step_id="native_zendure_device",
                    data_schema=self._native_device_schema(
                        devices,
                        bool(options.get(CONF_NATIVE_ZENDURE_CONTROL_ENABLED, False)),
                        options,
                        target_device_id=selected if pending is not None else None,
                    ),
                    errors={"base": ip_error},
                    description_placeholders={
                        "device_summary": self._native_device_summary(devices)
                    },
                )
            if chosen_transport not in _native_transport_options(
                selected_device.candidate.identity
            ):
                return self.async_show_form(
                    step_id="native_zendure_device",
                    data_schema=self._native_device_schema(devices, True, options),
                    errors={"base": "device_not_found"},
                    description_placeholders={
                        "device_summary": self._native_device_summary(devices)
                    },
                )
            # Keep the existing single-device controller as the V5-compatible
            # fallback. New accounts use the first configured device; setup of
            # further devices never silently changes the active controller.
            is_active_device = (
                options.get(CONF_NATIVE_ZENDURE_SELECTED_DEVICE) == selected
            )
            if not options.get(CONF_NATIVE_ZENDURE_SELECTED_DEVICE):
                options[CONF_NATIVE_ZENDURE_SELECTED_DEVICE] = selected
                options[CONF_NATIVE_ZENDURE_CONTROL_ENABLED] = True
                options[CONF_NATIVE_ZENDURE_CONTROL_TRANSPORT] = (
                    chosen_transport.value
                )
                is_active_device = True
            if chosen_transport is ZendureTransport.LOCAL_MQTT:
                server = str(
                    user_input.get(CONF_NATIVE_ZENDURE_LOCAL_MQTT_SERVER, "")
                ).strip()
                if not server:
                    return self.async_show_form(
                        step_id="native_zendure_device",
                        data_schema=self._native_device_schema(
                            devices,
                            bool(user_input.get(
                                CONF_NATIVE_ZENDURE_CONTROL_ENABLED, False
                            )),
                            options,
                            target_device_id=selected,
                        ),
                        errors={"base": "local_mqtt_required"},
                        description_placeholders={
                            "device_summary": self._native_device_summary(devices)
                        },
                    )
                options[CONF_NATIVE_ZENDURE_LOCAL_MQTT_SERVER] = server
                local_port = int(
                    user_input.get(CONF_NATIVE_ZENDURE_LOCAL_MQTT_PORT, 1883)
                )
                options[CONF_NATIVE_ZENDURE_LOCAL_MQTT_PORT] = local_port
                options[CONF_NATIVE_ZENDURE_LOCAL_MQTT_USERNAME] = str(
                    user_input.get(CONF_NATIVE_ZENDURE_LOCAL_MQTT_USERNAME, "")
                ).strip()
                options[CONF_NATIVE_ZENDURE_LOCAL_MQTT_PASSWORD] = (
                    resolve_app_token_input(
                        user_input.get(CONF_NATIVE_ZENDURE_LOCAL_MQTT_PASSWORD),
                        options.get(CONF_NATIVE_ZENDURE_LOCAL_MQTT_PASSWORD),
                    )
                )
                wifi_ssid = str(
                    user_input.get(CONF_NATIVE_ZENDURE_LEGACY_WIFI_SSID, "")
                ).strip()
                wifi_password = resolve_app_token_input(
                    user_input.get(CONF_NATIVE_ZENDURE_LEGACY_WIFI_PASSWORD),
                    options.get(CONF_NATIVE_ZENDURE_LEGACY_WIFI_PASSWORD),
                )
                if wifi_ssid:
                    options[CONF_NATIVE_ZENDURE_LEGACY_WIFI_SSID] = wifi_ssid
                if wifi_password:
                    options[CONF_NATIVE_ZENDURE_LEGACY_WIFI_PASSWORD] = wifi_password
                if bool(user_input.get(CONF_NATIVE_ZENDURE_LEGACY_PROVISION, False)):
                    if local_port != 1883:
                        return self.async_show_form(
                            step_id="native_zendure_device",
                            data_schema=self._native_device_schema(devices, True, options),
                            errors={"base": "legacy_port_required"},
                            description_placeholders={
                                "device_summary": self._native_device_summary(devices)
                            },
                        )
                    if not wifi_ssid or not wifi_password:
                        return self.async_show_form(
                            step_id="native_zendure_device",
                            data_schema=self._native_device_schema(
                                devices, True, options
                            ),
                            errors={"base": "legacy_wifi_required"},
                            description_placeholders={
                                "device_summary": self._native_device_summary(devices)
                            },
                        )
                    identity = selected_device.candidate.identity
                    try:
                        if not identity.device_id:
                            raise ValueError("legacy_device_id_missing")
                        await async_provision_legacy_device(
                            self.hass,
                            serial_number=str(identity.serial_number or ""),
                            display_name=selected_device.candidate.display_name,
                            mqtt_server=server,
                            wifi_ssid=wifi_ssid,
                            wifi_password=wifi_password,
                        )
                    except Exception as error:
                        reason = str(error) or type(error).__name__
                        allowed = {
                            "legacy_ble_device_not_found",
                            "legacy_device_id_missing",
                        }
                        return self.async_show_form(
                            step_id="native_zendure_device",
                            data_schema=self._native_device_schema(
                                devices, True, options
                            ),
                            errors={
                                "base": reason if reason in allowed else "legacy_provision_failed"
                            },
                            description_placeholders={
                                "device_summary": self._native_device_summary(devices)
                            },
                        )
            self._native_setup_map = save_device_setup(
                self._native_setup_map, selected, chosen_transport.value
            )
            self._native_setup_map = _update_native_zensdk_ip(
                self._native_setup_map,
                selected,
                zensdk_ip,
                clear=clear_zensdk_ip,
                clear_blank=pending is not None,
            )
            options[CONF_NATIVE_ZENDURE_DEVICE_SETUPS] = self._native_setup_map
            if is_active_device:
                options[CONF_NATIVE_ZENDURE_CONTROL_ENABLED] = bool(
                    user_input.get(
                        CONF_NATIVE_ZENDURE_CONTROL_ENABLED,
                        options.get(CONF_NATIVE_ZENDURE_CONTROL_ENABLED, False),
                    )
                )
                options[CONF_NATIVE_ZENDURE_CONTROL_TRANSPORT] = chosen_transport.value
            self._working_options = options
            migration = self.config_entry.data.get("v5_migration")
            if isinstance(migration, Mapping):
                from .v5_migration import confirm_native_binding

                data = dict(self.config_entry.data)
                data["v5_migration"] = confirm_native_binding(
                    migration,
                    native_candidate_id=selected,
                )
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=data,
                )
            next_pending = next(
                (
                    item.candidate.candidate_id
                    for item in devices
                    if item.candidate.supported
                    and self._native_setup_map["devices"].get(
                        item.candidate.candidate_id, {}
                    ).get("setup_status") != SETUP_COMPLETE
                ),
                None,
            )
            if next_pending is not None:
                return self.async_show_form(
                    step_id="native_zendure_device",
                    data_schema=self._native_device_schema(
                        devices, True, options, target_device_id=next_pending
                    ),
                    description_placeholders={
                        "device_summary": self._native_device_summary(devices)
                    },
                )
            options[CONF_NATIVE_ZENDURE_DEVICE_SETUPS] = self._native_setup_map
            return self.async_create_entry(title="", data=options)

        return self.async_show_form(
            step_id="native_zendure_device",
            data_schema=self._native_device_schema(
                devices,
                bool(self.config_entry.options.get(
                    CONF_NATIVE_ZENDURE_CONTROL_ENABLED, False
                )),
                self.config_entry.options,
                target_device_id=pending,
            ),
            description_placeholders={
                "device_summary": self._native_device_summary(devices)
            },
        )

    @staticmethod
    def _native_device_schema(
        devices,
        native_control_enabled: bool = False,
        stored_options: dict[str, Any] | None = None,
        target_device_id: str | None = None,
    ) -> vol.Schema:
        options = stored_options or {}
        setup_map = options.get(CONF_NATIVE_ZENDURE_DEVICE_SETUPS, {})
        setup_records = (
            setup_map.get("devices", {})
            if isinstance(setup_map, Mapping)
            else {}
        )
        device_record = (
            setup_records.get(target_device_id, {})
            if isinstance(setup_records, Mapping) and target_device_id
            else {}
        )
        stored_transport = device_record.get("transport") or (
            options.get(CONF_NATIVE_ZENDURE_CONTROL_TRANSPORT)
            if target_device_id is None
            or target_device_id == options.get(CONF_NATIVE_ZENDURE_SELECTED_DEVICE)
            else None
        )
        if stored_transport not in {item.value for item in ZendureTransport}:
            selected_id = options.get(CONF_NATIVE_ZENDURE_SELECTED_DEVICE)
            selected_item = next(
                (
                    item for item in devices
                    if item.candidate.candidate_id == selected_id
                ),
                None,
            )
            inherited = (
                preferred_local_transport(selected_item.candidate.identity)
                if stored_options is not None and selected_item is not None
                else None
            )
            # Legacy Local MQTT is usable only after the physical device has
            # accepted its broker configuration and publishes fresh properties
            # there. Older entries have no explicit choice, so start them on
            # the reliable Cloud path instead of silently selecting Local.
            if inherited is ZendureTransport.LOCAL_MQTT:
                inherited = None
            stored_transport = (
                inherited.value
                if inherited is not None
                else ZendureTransport.CLOUD_MQTT.value
            )
        transport_devices = [
            item for item in devices
            if target_device_id is None
            or item.candidate.candidate_id == target_device_id
        ]
        available_transports = sorted(
            {
                transport.value
                for item in transport_devices
                for transport in _native_transport_options(item.candidate.identity)
            },
            key=lambda value: (
                value != ZendureTransport.CLOUD_MQTT.value,
                value,
            ),
        )
        zensdk_devices = [
            item
            for item in transport_devices
            if (
                (matrix := resolve_zendure_device(item.candidate.identity))
                is not None
                and matrix.transport(ZendureTransport.ZENSDK).read
                is not VerificationLevel.UNSUPPORTED
            )
        ]
        schema = {
                vol.Required(CONF_NATIVE_ZENDURE_SELECTED_DEVICE):
                    selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                {
                                    "value": item.candidate.candidate_id,
                                    "label": native_device_label(
                                        item.candidate.display_name,
                                        item.candidate.identity.product_model,
                                        item.pack_count,
                                    ),
                                }
                                for item in devices
                                if item.candidate.supported
                                if target_device_id is None
                                or item.candidate.candidate_id == target_device_id
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                vol.Required(
                    CONF_NATIVE_ZENDURE_CONTROL_TRANSPORT,
                    default=stored_transport,
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=available_transports,
                        translation_key="zendure_transport",
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(
                    CONF_NATIVE_ZENDURE_CONTROL_ENABLED,
                    default=native_control_enabled,
                ): selector.BooleanSelector(),
            }
        if zensdk_devices:
            schema.update({
                vol.Optional(
                    CONF_NATIVE_ZENDURE_ZENSDK_IP,
                    default=(
                        device_record.get("zensdk_ip", "")
                        if target_device_id is not None
                        else ""
                    ),
                ): selector.TextSelector(),
                vol.Optional(
                    CONF_NATIVE_ZENDURE_ZENSDK_IP_CLEAR,
                    default=False,
                ): selector.BooleanSelector(),
            })
        if any(
            preferred_local_transport(item.candidate.identity)
            is ZendureTransport.LOCAL_MQTT
            for item in devices
        ):
            schema.update({
                vol.Optional(
                    CONF_NATIVE_ZENDURE_LOCAL_MQTT_SERVER,
                    default=options.get(CONF_NATIVE_ZENDURE_LOCAL_MQTT_SERVER, ""),
                ): selector.TextSelector(),
                vol.Optional(
                    CONF_NATIVE_ZENDURE_LOCAL_MQTT_PORT,
                    default=options.get(CONF_NATIVE_ZENDURE_LOCAL_MQTT_PORT, 1883),
                ): selector.NumberSelector(selector.NumberSelectorConfig(
                    min=1, max=65535, mode=selector.NumberSelectorMode.BOX,
                )),
                vol.Optional(
                    CONF_NATIVE_ZENDURE_LOCAL_MQTT_USERNAME,
                    default=options.get(CONF_NATIVE_ZENDURE_LOCAL_MQTT_USERNAME, ""),
                ): selector.TextSelector(),
                vol.Optional(
                    CONF_NATIVE_ZENDURE_LOCAL_MQTT_PASSWORD,
                    default=(
                        STORED_APP_TOKEN_MASK
                        if options.get(CONF_NATIVE_ZENDURE_LOCAL_MQTT_PASSWORD)
                        else ""
                    ),
                ): selector.TextSelector(selector.TextSelectorConfig(
                    type=selector.TextSelectorType.PASSWORD
                )),
                vol.Optional(
                    CONF_NATIVE_ZENDURE_LEGACY_WIFI_SSID,
                    default=options.get(CONF_NATIVE_ZENDURE_LEGACY_WIFI_SSID, ""),
                ): selector.TextSelector(),
                vol.Optional(
                    CONF_NATIVE_ZENDURE_LEGACY_WIFI_PASSWORD,
                    default=(
                        STORED_APP_TOKEN_MASK
                        if options.get(CONF_NATIVE_ZENDURE_LEGACY_WIFI_PASSWORD)
                        else ""
                    ),
                ): selector.TextSelector(selector.TextSelectorConfig(
                    type=selector.TextSelectorType.PASSWORD
                )),
                vol.Optional(
                    CONF_NATIVE_ZENDURE_LEGACY_PROVISION,
                    default=legacy_provisioning_default(stored_transport),
                ): selector.BooleanSelector(),
            })
        return vol.Schema(schema)

    @staticmethod
    def _native_device_summary(devices) -> str:
        return "\n".join(
            native_device_summary_line(
                item.candidate.display_name,
                item.candidate.identity.product_model,
                item.pack_count,
                item.online,
            )
            for item in devices
        )

    def _debug_coordinator(self):
        """Return the loaded coordinator for this options-flow entry."""

        return self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)

    async def async_step_training(self, user_input: dict[str, Any] | None = None):
        """Route to the training action without changing integration options."""

        coordinator = self._debug_coordinator()
        if coordinator is None:
            return self.async_abort(reason="debug_integration_not_loaded")
        if coordinator.regulation_training_status["active"]:
            return await self.async_step_training_stop()
        return await self.async_step_training_start()

    async def async_step_training_start(
        self, user_input: dict[str, Any] | None = None
    ):
        """Start a bounded passive training session from the settings menu."""

        coordinator = self._debug_coordinator()
        if coordinator is None:
            return self.async_abort(reason="debug_integration_not_loaded")
        if coordinator.regulation_training_status["active"]:
            return await self.async_step_training_stop()

        if user_input is not None:
            await coordinator.async_start_regulation_training(
                duration_minutes=int(user_input["duration_minutes"]),
                direction=str(user_input["direction"]),
            )
            return await self.async_step_training_started()

        return self.async_show_form(
            step_id="training_start",
            data_schema=vol.Schema(
                {
                    vol.Required("duration_minutes", default="1440"):
                        selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=["10", "30", "60", "120", "1440"],
                                mode=selector.SelectSelectorMode.DROPDOWN,
                            )
                        ),
                    vol.Required("direction", default="both"):
                        selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=["both", "charge", "discharge"],
                                mode=selector.SelectSelectorMode.DROPDOWN,
                            )
                        ),
                }
            ),
        )

    async def async_step_training_stop(
        self, user_input: dict[str, Any] | None = None
    ):
        """Confirm and stop the active passive training session."""

        coordinator = self._debug_coordinator()
        if coordinator is None:
            return self.async_abort(reason="debug_integration_not_loaded")
        status = coordinator.regulation_training_status
        if not status["active"]:
            return await self.async_step_init()
        if user_input is not None:
            await coordinator.async_stop_regulation_training()
            return await self.async_step_training_stopped()

        return self.async_show_form(
            step_id="training_stop",
            data_schema=vol.Schema({}),
            description_placeholders={
                "training_end": str(status["ends_at"] or "—"),
                "sample_count": str(status["sample_count"]),
            },
        )

    async def async_step_training_started(
        self, user_input: dict[str, Any] | None = None
    ):
        """Confirm that passive training started without writing options."""

        if user_input is not None:
            return await self.async_step_init()
        return self.async_show_form(
            step_id="training_started", data_schema=vol.Schema({})
        )

    async def async_step_training_stopped(
        self, user_input: dict[str, Any] | None = None
    ):
        """Confirm that training stopped and return to integration settings."""

        if user_input is not None:
            return await self.async_step_init()
        return self.async_show_form(
            step_id="training_stopped", data_schema=vol.Schema({})
        )

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
            return await self.async_step_debug_started()

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
            return await self.async_step_debug_stopped()

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

    async def async_step_debug_started(
        self, user_input: dict[str, Any] | None = None
    ):
        """Show a translated confirmation without writing integration options."""

        if user_input is not None:
            return await self.async_step_init()
        return self.async_show_form(
            step_id="debug_started",
            data_schema=vol.Schema({}),
        )

    async def async_step_debug_stopped(
        self, user_input: dict[str, Any] | None = None
    ):
        """Show a translated export confirmation without writing options."""

        if user_input is not None:
            return await self.async_step_init()
        return self.async_show_form(
            step_id="debug_stopped",
            data_schema=vol.Schema({}),
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
                vol.Optional(SETTING_FULL_CHARGE_MAINTENANCE_ENABLED): selector.BooleanSelector(),
                vol.Optional(SETTING_FULL_CHARGE_MAINTENANCE_INTERVAL_DAYS): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=7,
                        max=90,
                        step=1,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
            }
        )

        coordinator = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        runtime = getattr(coordinator, "native_zendure", None)
        if (runtime is not None and hasattr(runtime, "selected_capacity")
            and runtime.selected_capacity().reason == "unknown_pack_profile"):
            options_schema = options_schema.extend({
                vol.Optional("native_capacity_override_kwh", default=preview.get("native_capacity_override_kwh", 0)):
                    selector.NumberSelector(selector.NumberSelectorConfig(
                        min=0, step=0.01, mode=selector.NumberSelectorMode.BOX,
                        unit_of_measurement="kWh",
                    )),
            })

        suggested_values = {
            CONF_EXPERT_MODE_ENABLED: preview.get(
                CONF_EXPERT_MODE_ENABLED,
                DEFAULT_EXPERT_MODE_ENABLED,
            ),
            SETTING_LEARNED_PLANNING_ENABLED: preview.get(
                SETTING_LEARNED_PLANNING_ENABLED,
                DEFAULT_LEARNED_PLANNING_ENABLED,
            ),
            SETTING_FULL_CHARGE_MAINTENANCE_ENABLED: preview.get(
                SETTING_FULL_CHARGE_MAINTENANCE_ENABLED,
                DEFAULT_FULL_CHARGE_MAINTENANCE_ENABLED,
            ),
            SETTING_FULL_CHARGE_MAINTENANCE_INTERVAL_DAYS: preview.get(
                SETTING_FULL_CHARGE_MAINTENANCE_INTERVAL_DAYS,
                DEFAULT_FULL_CHARGE_MAINTENANCE_INTERVAL_DAYS,
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
        if (self.config_entry.data.get("connection_type") == "native"
            or self.config_entry.options.get(CONF_NATIVE_ZENDURE_CONTROL_ENABLED, False)):
            packs = 0  # Native pack measurements are inputs, not entity selectors.
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
