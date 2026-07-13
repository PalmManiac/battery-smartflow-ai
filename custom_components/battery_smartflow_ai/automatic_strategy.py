from __future__ import annotations

from typing import Any

from .regulation_models import SeasonContext, StrategyContext


class AutomaticStrategy:
    """Build the high-level context for the unified automatic strategy.

    V4.3.0-dev5.0:
    Foundation only. The returned weights are not yet used by DecisionEngine
    and therefore must not change existing behavior.
    """

    def evaluate(
        self,
        *,
        automatic_mode_active: bool,
        season_context: SeasonContext = "neutral",
        metadata: dict[str, Any] | None = None,
    ) -> StrategyContext:
        """Return the current automatic-strategy context."""

        if not bool(automatic_mode_active):
            return StrategyContext(
                active=False,
                weighting="inactive",
                season_context=season_context,
                pv_weight=0.0,
                price_weight=0.0,
                reserve_weight=0.0,
                forecast_weight=0.0,
                reason="automatic_mode_inactive",
                metadata=dict(metadata or {}),
            )

        # V4.3.0-dev5.0:
        # Deliberately neutral defaults. Later development steps will derive
        # these weights from PV, forecast, price, SoC and reserve conditions.
        return StrategyContext(
            active=True,
            weighting="balanced",
            season_context=season_context,
            pv_weight=0.5,
            price_weight=0.5,
            reserve_weight=0.5,
            forecast_weight=0.5,
            reason="foundation_balanced_defaults",
            metadata=dict(metadata or {}),
        )