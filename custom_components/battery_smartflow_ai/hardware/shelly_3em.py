"""Read signed grid power from a classic Shelly 3EM (Gen1)."""

from __future__ import annotations

import base64
import math

from .shelly_pro_3em import validate_shelly_host


class Shelly3EMError(Exception):
    """Raised when the classic Shelly 3EM cannot provide a valid reading."""


def parse_shelly_3em_power(payload: object) -> float:
    """Return aggregate grid power in watts, positive import and negative export."""

    if not isinstance(payload, dict):
        raise Shelly3EMError("invalid_status_payload")

    value = payload.get("total_power")
    if value is None:
        emeters = payload.get("emeters")
        if not isinstance(emeters, list) or len(emeters) != 3:
            raise Shelly3EMError("missing_total_power")
        powers = []
        for emeter in emeters:
            if not isinstance(emeter, dict) or emeter.get("is_valid") is False:
                raise Shelly3EMError("invalid_phase_power")
            powers.append(emeter.get("power"))
        if any(power is None for power in powers):
            raise Shelly3EMError("missing_phase_power")
        value = powers

    try:
        power = sum(float(part) for part in value) if isinstance(value, list) else float(value)
    except (TypeError, ValueError) as err:
        raise Shelly3EMError("invalid_total_power") from err
    if not math.isfinite(power):
        raise Shelly3EMError("invalid_total_power")
    return power


async def async_read_shelly_3em_power(
    session,
    *,
    host: str,
    password: str = "",
    timeout_seconds: float = 1.5,
) -> float:
    """Poll the Gen1 ``/status`` endpoint, using Basic Auth when configured."""

    normalized_host = validate_shelly_host(host)
    host_for_url = f"[{normalized_host}]" if ":" in normalized_host else normalized_host
    headers = None
    if password:
        credentials = base64.b64encode(f"admin:{password}".encode()).decode("ascii")
        headers = {"Authorization": f"Basic {credentials}"}

    async with session.get(
        f"http://{host_for_url}/status",
        timeout=timeout_seconds,
        headers=headers,
    ) as response:
        if response.status == 401:
            raise Shelly3EMError(
                "authentication_failed" if password else "authentication_required"
            )
        if response.status >= 400:
            raise Shelly3EMError(f"http_{response.status}")
        return parse_shelly_3em_power(await response.json(content_type=None))
