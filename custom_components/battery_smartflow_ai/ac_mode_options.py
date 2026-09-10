"""Resolve semantic AC directions to select options exposed by integrations."""

from __future__ import annotations

from collections.abc import Iterable
import re


_ALIASES = {
    "input": frozenset(("input", "inputmode", "acinputmode")),
    "output": frozenset(("output", "outputmode", "acoutputmode")),
}


def _normalized(value: object) -> str:
    """Return a comparison-only representation of one option."""

    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def canonical_ac_mode(value: object) -> str | None:
    """Return ``input`` or ``output`` for a recognized option label."""

    normalized = _normalized(value)
    for mode, aliases in _ALIASES.items():
        if normalized in aliases:
            return mode
    return None


def resolve_ac_mode_option(
    requested_mode: object,
    options: Iterable[object],
) -> str | None:
    """Resolve a direction to the exact select option, failing on ambiguity."""

    requested = canonical_ac_mode(requested_mode)
    if requested is None:
        return None

    matches = [
        str(option)
        for option in options
        if canonical_ac_mode(option) == requested
    ]
    if len(matches) != 1:
        return None
    return matches[0]
