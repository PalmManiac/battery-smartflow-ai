"""Minimal import bootstrap for pure strategy tests without Home Assistant."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
import sys
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "custom_components" / "battery_smartflow_ai"


def _install_module(name: str, module: ModuleType) -> None:
    sys.modules.setdefault(name, module)


def bootstrap() -> None:
    """Expose the integration's pure modules with tiny HA type stubs."""

    custom_components = ModuleType("custom_components")
    custom_components.__path__ = [str(ROOT / "custom_components")]
    _install_module("custom_components", custom_components)

    package = ModuleType("custom_components.battery_smartflow_ai")
    package.__path__ = [str(PACKAGE_ROOT)]
    _install_module("custom_components.battery_smartflow_ai", package)

    homeassistant = ModuleType("homeassistant")
    homeassistant.__path__ = []
    _install_module("homeassistant", homeassistant)

    ha_const = ModuleType("homeassistant.const")

    class Platform(str, Enum):
        SENSOR = "sensor"
        SELECT = "select"
        NUMBER = "number"

    ha_const.Platform = Platform
    _install_module("homeassistant.const", ha_const)

    ha_core = ModuleType("homeassistant.core")

    class HomeAssistant:
        pass

    ha_core.HomeAssistant = HomeAssistant
    _install_module("homeassistant.core", ha_core)

    ha_util = ModuleType("homeassistant.util")
    ha_util.__path__ = []
    _install_module("homeassistant.util", ha_util)

    ha_dt = ModuleType("homeassistant.util.dt")
    ha_dt.parse_datetime = lambda value: datetime.fromisoformat(value)
    ha_dt.as_local = lambda value: value
    ha_dt.as_utc = lambda value: value
    _install_module("homeassistant.util.dt", ha_dt)
