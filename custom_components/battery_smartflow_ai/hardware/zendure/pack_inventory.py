"""Stabilize intermittent battery-pack inventory reports."""

from __future__ import annotations

LEGACY_GROUPED_PACK_MODELS = frozenset(
    {"hyper2000", "hub2000", "solarflowhub2000"}
)
_PACK_MEMBERSHIP_CONFIRMATIONS = 2


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

    The initial complete report establishes the baseline. Every later change,
    including additions, removals, and identity replacements, is held as a
    candidate until the same membership appears in two consecutive complete
    reports. Alternating reports therefore cannot make the visible inventory
    flicker between different pack sets.
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
    ) -> frozenset[str]:
        candidate = frozenset(pack_ids)
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
