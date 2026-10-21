"""Stabilize intermittent battery-pack inventory reports."""

from __future__ import annotations

LEGACY_GROUPED_PACK_MODELS = frozenset(
    {"hyper2000", "hub2000", "solarflowhub2000"}
)
_PACK_REMOVAL_CONFIRMATIONS = 2


def requires_stable_pack_membership(product_model: str | None) -> bool:
    """Return whether a model needs confirmation before retiring pack IDs."""

    model_key = "".join(
        character
        for character in str(product_model or "").casefold()
        if character.isalnum()
    )
    return model_key in LEGACY_GROUPED_PACK_MODELS


class PackMembershipStabilizer:
    """Keep known packs through one incomplete report for grouped legacy models.

    New pack identities are admitted immediately. A report that removes any
    known identity is held as a candidate until the same membership appears in
    two consecutive complete reports. This avoids a single sparse or transient
    report making the battery inventory appear to shrink and expand rapidly.
    """

    def __init__(self) -> None:
        self.current: frozenset[str] | None = None
        self._candidate: frozenset[str] | None = None
        self._candidate_count = 0

    def observe(
        self,
        pack_ids: frozenset[str],
        *,
        confirm_removals: bool,
    ) -> frozenset[str]:
        candidate = frozenset(pack_ids)
        if self.current is None or not confirm_removals:
            self.current = candidate
            self._clear_candidate()
            return self.current

        if candidate == self.current:
            self._clear_candidate()
            return self.current

        if self.current.issubset(candidate):
            self.current = candidate
            self._clear_candidate()
            return self.current

        if candidate == self._candidate:
            self._candidate_count += 1
        else:
            self._candidate = candidate
            self._candidate_count = 1

        if self._candidate_count >= _PACK_REMOVAL_CONFIRMATIONS:
            self.current = candidate
            self._clear_candidate()
        else:
            # Preserve previously known identities while allowing newly seen
            # packs through immediately; only removals are debounced.
            self.current = self.current | candidate
        return self.current

    def _clear_candidate(self) -> None:
        self._candidate = None
        self._candidate_count = 0
