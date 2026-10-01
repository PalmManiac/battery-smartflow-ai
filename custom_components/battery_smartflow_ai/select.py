from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    AI_MODE_AUTOMATIC,
    AI_MODES,
    CONF_OFFGRID_MODE_ENTITY,
    DOMAIN,
    INTEGRATION_MANUFACTURER,
    INTEGRATION_MODEL,
    INTEGRATION_VERSION,
    MANUAL_ACTIONS,
    MANUAL_STANDBY,
)
from .offgrid_select import (
    OFFGRID_MODE_OPTIONS,
    matching_offgrid_options,
    normalize_offgrid_option,
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
    offgrid_entity_id = entry.data.get(CONF_OFFGRID_MODE_ENTITY)
    native_runtime = getattr(coordinator, "native_zendure", None)
    if offgrid_entity_id or getattr(native_runtime, "configured", False):
        add_entities([ZendureOffgridModeSelect(entry, coordinator, offgrid_entity_id)])


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

    def __init__(self, entry: ConfigEntry, coordinator, source_entity_id: str | None) -> None:
        self.coordinator = coordinator
        self.source_entity_id = source_entity_id
        self._source_options: dict[str, str] = {}
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
        return [option for option in OFFGRID_MODE_OPTIONS if option in self._source_options]

    @property
    def available(self) -> bool:
        if self._native_control_available:
            return True
        source = (
            self.hass.states.get(self.source_entity_id)
            if self.hass and self.source_entity_id else None
        )
        return bool(
            source is not None
            and source.state not in {"unknown", "unavailable"}
            and normalize_offgrid_option(source.state) in self._source_options
            and len(self._source_options) >= 2
        )

    @property
    def current_option(self) -> str | None:
        native = self._native_runtime
        if self._native_control_available and native is not None:
            return native.selected_offgrid_mode()
        source = (
            self.hass.states.get(self.source_entity_id)
            if self.hass and self.source_entity_id else None
        )
        if source is None:
            return None
        option = normalize_offgrid_option(source.state)
        return option if option in self._source_options else None

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
        if self.source_entity_id is None:
            raise HomeAssistantError("No Zendure off-grid mode source is configured")
        upstream_option = self._source_options[option]
        if not self.available:
            return
        await self.hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": self.source_entity_id, "option": upstream_option},
            blocking=True,
        )
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        self._refresh_source_options()
        removers = []
        if self.source_entity_id:
            removers.append(
                async_track_state_change_event(
                    self.hass,
                    [self.source_entity_id],
                    self._handle_source_state_change,
                )
            )
        native = self._native_runtime
        if native is not None and hasattr(self.coordinator, "async_add_listener"):
            removers.append(self.coordinator.async_add_listener(self.async_write_ha_state))
        self.async_on_remove(lambda: [remove() for remove in removers])

    def _refresh_source_options(self) -> None:
        source = self.hass.states.get(self.source_entity_id) if self.source_entity_id else None
        raw_options = source.attributes.get("options", []) if source is not None else []
        self._source_options = matching_offgrid_options(raw_options)

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

    async def _handle_source_state_change(self, _event: Event) -> None:
        self._refresh_source_options()
        self.async_write_ha_state()
