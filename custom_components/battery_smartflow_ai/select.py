from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    AI_MODE_AUTOMATIC,
    AI_MODES,
    DOMAIN,
    INTEGRATION_MANUFACTURER,
    INTEGRATION_MODEL,
    INTEGRATION_VERSION,
    MANUAL_ACTIONS,
    MANUAL_STANDBY,
)


@dataclass(frozen=True, kw_only=True)
class ZendureSelectEntityDescription(SelectEntityDescription):
    """Extended description for Zendure selects."""

    runtime_key: str
    options_list: list[str]
    default_option: str


# ==========================
# Reihenfolge = UI-Reihenfolge
# ==========================
SELECTS: tuple[ZendureSelectEntityDescription, ...] = (
    # 1. Betriebsmodus
    ZendureSelectEntityDescription(
        key="ai_mode",
        translation_key="ai_mode",
        runtime_key="ai_mode",
        options_list=AI_MODES,           # ← NUR stabile Keys!
        default_option=AI_MODE_AUTOMATIC,
        icon="mdi:robot",
    ),

    # 2. Manuelle Aktion
    ZendureSelectEntityDescription(
        key="manual_action",
        translation_key="manual_action",
        runtime_key="manual_action",
        options_list=MANUAL_ACTIONS,     # ← NUR stabile Keys!
        default_option=MANUAL_STANDBY,
        icon="mdi:gesture-tap-button",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]

    add_entities(
        ZendureSmartFlowSelect(entry, coordinator, description)
        for description in SELECTS
    )
    native_runtime = getattr(coordinator, "native_zendure", None)
    if getattr(native_runtime, "configured", False):
        add_entities([ZendureOffgridModeSelect(entry, coordinator)])


class ZendureSmartFlowSelect(SelectEntity):
    """Zendure SmartFlow select entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator,
        description: ZendureSelectEntityDescription,
    ) -> None:
        self.entity_description = description
        self.coordinator = coordinator
        self._entry = entry

        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "translation_key": "control_and_planning",
            "manufacturer": INTEGRATION_MANUFACTURER,
            "model": INTEGRATION_MODEL,
            "sw_version": INTEGRATION_VERSION,
        }

        # ⚠️ WICHTIG:
        # Optionen bleiben technische Keys → Übersetzung erfolgt NUR über translations/*.json
        self._attr_options = list(description.options_list)

        # Initialwert sicher setzen
        if description.runtime_key not in coordinator.runtime_mode:
            coordinator.runtime_mode[description.runtime_key] = description.default_option

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def current_option(self) -> str | None:
        return self.coordinator.runtime_mode.get(self.entity_description.runtime_key)

    async def async_select_option(self, option: str) -> None:
        if option not in self.options:
            return

        self.coordinator.runtime_mode[self.entity_description.runtime_key] = option
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )


class ZendureOffgridModeSelect(SelectEntity):
    """User-initiated proxy for a configured Home Assistant select entity."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:power-plug"

    def __init__(self, entry: ConfigEntry, coordinator) -> None:
        self.coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_offgrid_mode_control"
        self._attr_translation_key = "offgrid_mode_control"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "translation_key": "control_and_planning",
            "manufacturer": INTEGRATION_MANUFACTURER,
            "model": INTEGRATION_MODEL,
            "sw_version": INTEGRATION_VERSION,
        }

    @property
    def options(self) -> list[str]:
        if self._native_control_available:
            return [option for option in ("normal", "eco", "off")]
        return []

    @property
    def available(self) -> bool:
        return self._native_control_available

    @property
    def current_option(self) -> str | None:
        native = self._native_runtime
        if self._native_control_available and native is not None:
            return native.selected_offgrid_mode()
        return None

    async def async_select_option(self, option: str) -> None:
        """Forward an explicit user choice; never change this select automatically."""

        if option not in self.options:
            return
        native = self._native_runtime
        if self._native_control_available and native is not None:
            result = await native.async_select_offgrid_mode(option)
            if getattr(result.status, "value", result.status) != "applied":
                raise HomeAssistantError(
                    f"Could not set native Zendure off-grid mode: {result.reason}"
                )
            self.async_write_ha_state()
            return
        raise HomeAssistantError("Native Zendure off-grid control is not available")

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    @property
    def _native_runtime(self):
        return getattr(self.coordinator, "native_zendure", None)

    @property
    def _native_control_available(self) -> bool:
        native = self._native_runtime
        return bool(
            native is not None
            and callable(getattr(native, "native_offgrid_mode_control_available", None))
            and native.native_offgrid_mode_control_available()
        )
