"""Home Assistant configuration of the neutral system Clock."""

from __future__ import annotations

from homeassistant.util import dt as dt_util

from ...core.clock import SystemClock


class HomeAssistantClock(SystemClock):
    """Use Home Assistant's configured timezone for local calendar logic."""

    def __init__(self) -> None:
        super().__init__(local_timezone=dt_util.get_default_time_zone())
