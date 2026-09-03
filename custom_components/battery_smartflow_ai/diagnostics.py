"""Native Home Assistant diagnostics download for the latest BSFAI package."""

from __future__ import annotations

import json
from functools import partial
from pathlib import Path
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .debug_exporter import DEBUG_DIRECTORY
from .debug_package import redact_secrets


def _load_latest_package(path: str, *, config_directory: str) -> dict[str, Any]:
    """Load only a JSON package inside BSFAI's dedicated debug directory."""

    allowed_directory = (Path(config_directory).resolve() / DEBUG_DIRECTORY).resolve()
    package_path = Path(path).resolve()
    if package_path.parent != allowed_directory or not package_path.is_file():
        return {
            "status": "debug_package_unavailable",
            "message": "No downloadable Battery SmartFlow AI debug package is available.",
        }

    with package_path.open("r", encoding="utf-8") as handle:
        package = json.load(handle)
    return redact_secrets(package)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return the latest completed recording through HA's diagnostics download."""

    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    native = getattr(coordinator, "native_zendure", None)
    native_path = native.capture_path if native is not None else None
    debug_path = (
        coordinator.debug_last_package_path if coordinator is not None else None
    )
    path = native_path or debug_path
    if not path:
        return {
            "status": "debug_package_unavailable",
            "message": "Create a debug recording or configure the native Zendure test first.",
            "native_zendure": (
                native.diagnostic_data() if native is not None else None
            ),
        }
    package = await hass.async_add_executor_job(
        partial(
            _load_latest_package,
            path,
            config_directory=hass.config.config_dir,
        )
    )
    if native_path:
        return {
            "native_zendure": native.diagnostic_data(),
            "package": package,
        }
    return package
