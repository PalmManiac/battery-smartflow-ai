"""Stabilize intermittent battery-pack inventory reports."""

from __future__ import annotations

import math
from collections.abc import Mapping

LEGACY_GROUPED_PACK_MODELS = frozenset(
    {"hyper2000", "hub2000", "solarflowhub2000"}
)
_PACK_MEMBERSHIP_CONFIRMATIONS = 2


def normalize_pack_count(value: object) -> int | None:
    """Return a non-negative integral pack count without coercing bad values."""

    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float):
        if math.isfinite(value) and value >= 0 and value.is_integer():
            return int(value)
        return None
    if isinstance(value, str):
        text = value.strip()
        if text.isdecimal():
            return int(text)
    return None


def reported_pack_count(payload: object) -> int | None:
    """Find the current ``packNum`` in common Zendure report envelopes."""

    if not isinstance(payload, Mapping):
        return None
    for container in (payload.get("properties"), payload.get("state"), payload):
        if not isinstance(container, Mapping):
            continue
        count = normalize_pack_count(container.get("packNum"))
        if count is not None:
            return count
    return None


def requires_stable_pack_membership(product_model: str | None) -> bool:
    """Return whether a model needs confirmation before changing pack IDs."""

    model_key = "".join(
        character
        for character in str(product_model or "").casefold()
        if character.isalnum()
    )
    return model_key in LEGACY_GROUPED_PACK_MODELS


class PackMembershipStabilizer:
    """Require repeated complete reports before changing a grouped pack list.

    When Zendure reports ``packNum``, a pack list whose identity count does not
    match it is a sparse group update, not an inventory snapshot. Such updates
    do not establish or alter membership. Complete membership changes are held
    until the same set appears in two complete reports, so alternating packet
    groups cannot make the visible inventory flicker between pack sets.
    """

    def __init__(self) -> None:
        self.current: frozenset[str] | None = None
        self._candidate: frozenset[str] | None = None
        self._candidate_count = 0

    def observe(
        self,
        pack_ids: frozenset[str],
        *,
        confirm_changes: bool,
        expected_count: int | None = None,
    ) -> frozenset[str] | None:
        candidate = frozenset(pack_ids)
        if expected_count is not None and len(candidate) != expected_count:
            # A grouped report may contain only the pack whose properties were
            # refreshed. It is not evidence that the other packs disappeared.
            return self.current
        if self.current is None or not confirm_changes:
            self.current = candidate
            self._clear_candidate()
            return self.current

        if candidate == self.current:
            self._clear_candidate()
            return self.current

        if candidate == self._candidate:
            self._candidate_count += 1
        else:
            self._candidate = candidate
            self._candidate_count = 1

        if self._candidate_count >= _PACK_MEMBERSHIP_CONFIRMATIONS:
            self.current = candidate
            self._clear_candidate()
        return self.current

    def _clear_candidate(self) -> None:
        self._candidate = None
        self._candidate_count = 0
