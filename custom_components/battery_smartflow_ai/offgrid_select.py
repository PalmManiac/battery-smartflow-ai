from __future__ import annotations

from collections.abc import Iterable

OFFGRID_MODE_OPTIONS = ("off", "normal", "eco")


def normalize_offgrid_option(value: object) -> str | None:
    """Map common upstream labels to the stable BSFAI option keys."""

    normalized = str(value or "").strip().casefold()
    if normalized in {"off", "aus", "0", "disabled", "deaktiviert"}:
        return "off"
    if normalized in {"normal", "on", "1", "standard", "standard mode", "normalbetrieb"}:
        return "normal"
    if normalized in {"eco", "economic", "economical", "ökonomisch", "oekonomisch", "2"}:
        return "eco"
    return None


def matching_offgrid_options(options: Iterable[object] | None) -> dict[str, str]:
    """Return supported stable options mapped to their exact upstream labels."""

    matches: dict[str, str] = {}
    for option in options or ():
        canonical = normalize_offgrid_option(option)
        if canonical is not None:
            matches.setdefault(canonical, str(option))
    return matches
