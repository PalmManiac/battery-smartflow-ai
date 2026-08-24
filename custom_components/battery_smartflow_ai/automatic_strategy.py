from __future__ import annotations

from typing import Any

from .regulation_models import SeasonContext, StrategyContext


def _clamp01(value: float) -> float:
    """Clamp a numeric value to the range 0.0 ... 1.0."""
    return max(0.0, min(1.0, float(value)))


def forecast_supports_early_pv_passthrough(
    *,
    forecast_status: str,
    pv_outlook: str,
    remaining_today_kwh: float,
    battery_capacity_kwh: float,
    soc: float,
    soc_max: float,
) -> bool:
    """Return whether forecast PV exceeds the battery's remaining headroom."""

    if str(forecast_status or "").strip().lower() != "available":
        return False
    if str(pv_outlook or "").strip().lower() not in {
        "good",
        "high",
        "very_good",
        "excellent",
        "gut",
    }:
        return False

    capacity = max(0.0, float(battery_capacity_kwh or 0.0))
    if capacity <= 0.0:
        return False

    free_capacity_kwh = capacity * max(
        0.0,
        float(soc_max) - float(soc),
    ) / 100.0

    return float(remaining_today_kwh or 0.0) > free_capacity_kwh + 0.25


class AutomaticStrategy:
    """Build the high-level context for the unified automatic strategy.

    V4.3.0-dev5.1:
    Real PV, price, reserve and forecast weights are calculated for diagnostics.

    The weights are not yet consumed by DecisionEngine and therefore must not
    change charging or discharging behavior.
    """

    def _pv_weight(
        self,
        *,
        pv_w: float,
        house_load_w: float,
        installed_pv_wp: float,
        season_context: SeasonContext,
    ) -> tuple[float, str]:
        """Return the current PV relevance."""

        pv = max(0.0, float(pv_w or 0.0))
        house_load = max(0.0, float(house_load_w or 0.0))
        installed_pv = max(0.0, float(installed_pv_wp or 0.0))

        # Current PV compared with the current house load.
        if house_load > 50.0:
            load_ratio = _clamp01(pv / house_load)
        else:
            load_ratio = 1.0 if pv > 100.0 else 0.0

        # Current PV compared with installed nominal PV power.
        if installed_pv > 0.0:
            installation_ratio = _clamp01(pv / max(300.0, installed_pv * 0.50))
        else:
            installation_ratio = _clamp01(pv / 1500.0)

        weight = (
            load_ratio * 0.65
            + installation_ratio * 0.35
        )

        # Season is only a soft context, never a separate strategy branch.
        if season_context == "summer_like":
            weight += 0.08
        elif season_context == "winter_like":
            weight -= 0.05

        weight = _clamp01(weight)

        if pv <= 20.0:
            reason = "no_current_pv"
        elif load_ratio >= 1.0:
            reason = "pv_covers_house_load"
        elif load_ratio >= 0.50:
            reason = "pv_covers_relevant_load_share"
        else:
            reason = "pv_contribution_low"

        return weight, reason

    def _price_weight(
        self,
        *,
        price_now: float | None,
        price_min: float | None,
        price_max: float | None,
        price_average: float | None,
    ) -> tuple[float, str]:
        """Return how strongly the current price situation should matter.

        Both very cheap and very expensive prices increase price relevance.
        Prices close to the daily average produce a lower weight.
        """

        if price_now is None:
            return 0.20, "current_price_missing"

        current = float(price_now)

        if (
            price_min is None
            or price_max is None
            or float(price_max) <= float(price_min)
        ):
            if price_average is None:
                return 0.35, "price_range_missing"

            average = float(price_average)
            deviation = abs(current - average)
            magnitude = max(abs(current), abs(average))
            if magnitude <= 0.0:
                return 0.35, "price_range_missing"
            relative_deviation = deviation / magnitude

            return (
                _clamp01(0.30 + relative_deviation),
                "price_deviation_from_average",
            )

        low = float(price_min)
        high = float(price_max)
        span = high - low
        position = _clamp01((current - low) / span)

        # Distance from the center:
        # 0.0 at the middle, 1.0 at the cheapest/most expensive edge.
        extremity = abs(position - 0.50) * 2.0

        weight = _clamp01(0.25 + extremity * 0.75)

        if position <= 0.20:
            reason = "very_cheap_price_range"
        elif position <= 0.40:
            reason = "cheap_price_range"
        elif position >= 0.80:
            reason = "very_expensive_price_range"
        elif position >= 0.60:
            reason = "expensive_price_range"
        else:
            reason = "price_near_daily_middle"

        return weight, reason

    def _reserve_weight(
        self,
        *,
        soc: float,
        soc_min: float,
        soc_max: float,
    ) -> tuple[float, str]:
        """Return battery-reserve relevance.

        Low usable SoC means high reserve relevance.
        """

        current_soc = float(soc)
        minimum_soc = float(soc_min)
        maximum_soc = max(minimum_soc + 1.0, float(soc_max))

        usable_range = maximum_soc - minimum_soc
        usable_soc = _clamp01(
            (current_soc - minimum_soc) / usable_range
        )

        weight = _clamp01(1.0 - usable_soc)

        if current_soc <= minimum_soc + 5.0:
            reason = "reserve_critical"
            weight = max(weight, 0.90)
        elif current_soc <= minimum_soc + 15.0:
            reason = "reserve_low"
            weight = max(weight, 0.70)
        elif usable_soc >= 0.80:
            reason = "reserve_high"
        else:
            reason = "reserve_normal"

        return weight, reason

    def _forecast_weight(
        self,
        *,
        forecast_status: str,
        pv_outlook: str,
        remaining_today_kwh: float,
        tomorrow_kwh: float,
    ) -> tuple[float, str]:
        """Return how strongly forecast information should influence strategy."""

        status = str(forecast_status or "").strip().lower()
        outlook = str(pv_outlook or "").strip().lower()

        if status in {
            "",
            "unknown",
            "unavailable",
            "not_configured",
            "no_data",
            "invalid",
        }:
            return 0.10, "forecast_not_available"

        remaining = max(0.0, float(remaining_today_kwh or 0.0))
        tomorrow = max(0.0, float(tomorrow_kwh or 0.0))

        if outlook in {
            "poor",
            "bad",
            "low",
            "very_low",
            "schlecht",
        }:
            return 0.90, "poor_pv_outlook"

        if outlook in {
            "mixed",
            "uncertain",
            "medium",
            "wechselhaft",
        }:
            return 0.65, "mixed_pv_outlook"

        if outlook in {
            "good",
            "high",
            "very_good",
            "excellent",
            "gut",
        }:
            return 0.45, "good_pv_outlook"

        # Generic energy-based fallback.
        combined_forecast = remaining + (tomorrow * 0.35)

        if combined_forecast <= 1.0:
            return 0.85, "forecast_energy_low"
        if combined_forecast <= 4.0:
            return 0.65, "forecast_energy_moderate"
        return 0.45, "forecast_energy_high"

    def _select_weighting(
        self,
        *,
        pv_weight: float,
        price_weight: float,
        reserve_weight: float,
        forecast_weight: float,
    ) -> tuple[str, str]:
        """Return the visible dominant automatic weighting."""

        weights = {
            "pv_oriented": float(pv_weight),
            "price_oriented": float(price_weight),
            "reserve_oriented": float(reserve_weight),
        }

        dominant_name = max(weights, key=weights.get)
        dominant_value = weights[dominant_name]

        sorted_values = sorted(weights.values(), reverse=True)
        second_value = sorted_values[1] if len(sorted_values) > 1 else 0.0

        # A visible orientation is only shown when one factor is clearly strong
        # and sufficiently ahead of the other factors.
        clearly_dominant = (
            dominant_value >= 0.68
            and dominant_value - second_value >= 0.08
        )

        if clearly_dominant:
            return dominant_name, f"{dominant_name}_dominant"

        # A poor or uncertain forecast alone does not become its own visible
        # orientation. It raises the importance of reserve/PV planning, while
        # the visible result remains balanced until one factor dominates.
        if forecast_weight >= 0.80:
            return "balanced", "balanced_with_high_forecast_relevance"

        return "balanced", "no_clear_dominant_weight"
        
    def _automatic_discharge_permission(
        self,
        *,
        price_weight: float,
        price_reason: str,
        reserve_weight: float,
        reserve_reason: str,
        pv_weight: float,
        pv_reason: str,
        grid_import_w: float,
    ) -> tuple[bool, str]:
        """Return whether Automatic may consider economic discharge.

        V4.3.0-dev5.2:
        This is a strategic context permission, not the final discharge
        decision. DecisionEngine still checks the real price threshold,
        market window, SoC and all protection conditions.

        V4.3.0-dev8.3:
        Reserve weighting remains available for planning and diagnostics, but
        it must not create an additional hidden discharge floor above the
        configured minimum SoC.
        """

        if (
            pv_reason == "pv_covers_house_load"
            and float(pv_weight) >= 0.85
            and float(grid_import_w or 0.0) <= 120.0
        ):
            return False, "pv_covers_load_blocks_discharge"

        # V4.3.0-dev5.3.1:
        # Do not block economic discharge through the relative price-weight
        # classification.
        #
        # price_reason only describes the position inside the available price
        # range. Especially later in the day this range may contain only the
        # remaining slots, so an absolutely high price can still appear near
        # the middle of that remaining range.
        #
        # DecisionEngine remains authoritative for:
        # - effective discharge threshold
        # - market discharge window
        # - peak detection
        # - SoC and protection conditions
        return True, "economic_discharge_context_allowed"
        
    def _automatic_peak_reserve_permission(
        self,
        *,
        pv_weight: float,
        pv_reason: str,
        reserve_weight: float,
        reserve_reason: str,
        forecast_weight: float,
        forecast_reason: str,
    ) -> tuple[bool, str]:
        """Return whether Automatic may consider strategic peak-reserve charging.

        V4.3.0-dev5.3:
        This is only the high-level context permission. DecisionEngine still
        validates the future peak, target SoC, charge window, required energy
        and economic spread.

        Strong current PV together with a good forecast blocks optional grid
        charging. Weak PV, poor forecast or a low battery reserve may permit the
        DecisionEngine to evaluate peak-reserve charging.
        """

        strong_pv = bool(
            pv_reason == "pv_covers_house_load"
            and float(pv_weight) >= 0.85
        )

        good_forecast = forecast_reason in {
            "good_pv_outlook",
            "forecast_energy_high",
        }

        if strong_pv and good_forecast:
            return False, "pv_and_good_forecast_block_peak_reserve"

        if (
            float(pv_weight) >= 0.85
            and good_forecast
        ):
            return False, "strong_pv_blocks_peak_reserve"

        if forecast_reason in {
            "poor_pv_outlook",
            "forecast_energy_low",
        }:
            return True, "poor_forecast_allows_peak_reserve"

        if reserve_reason in {
            "reserve_critical",
            "reserve_low",
        }:
            return True, "low_reserve_allows_peak_reserve"

        if (
            pv_reason in {
                "no_current_pv",
                "pv_contribution_low",
            }
            and float(reserve_weight) >= 0.35
        ):
            return True, "weak_pv_and_reserve_need_allow_peak_reserve"

        if (
            forecast_reason in {
                "mixed_pv_outlook",
                "forecast_energy_moderate",
            }
            and float(reserve_weight) >= 0.45
        ):
            return True, "mixed_forecast_and_reserve_allow_peak_reserve"

        return False, "peak_reserve_context_not_required"
        
    def _automatic_valley_charge_permission(
        self,
        *,
        pv_weight: float,
        pv_reason: str,
        reserve_weight: float,
        reserve_reason: str,
        forecast_weight: float,
        forecast_reason: str,
    ) -> tuple[bool, str]:
        """Return whether Automatic may evaluate optional valley charging.

        V4.3.0-dev5.4:
        This is only a strategic context permission.

        DecisionEngine remains authoritative for:
        - the actual valley-price threshold
        - current PV priority and feed-in opportunity cost
        - forecast-based waiting
        - real PV underperformance
        - SoC, energy need and protection conditions

        The context blocks only clearly unnecessary optional grid charging.
        """

        strong_pv = bool(
            pv_reason == "pv_covers_house_load"
            and float(pv_weight) >= 0.85
        )

        good_forecast = forecast_reason in {
            "good_pv_outlook",
            "forecast_energy_high",
        }

        if strong_pv and good_forecast:
            return False, "pv_and_good_forecast_block_valley_charge"

        if (
            reserve_reason == "reserve_high"
            and float(reserve_weight) <= 0.20
        ):
            return False, "high_reserve_blocks_valley_charge"

        if forecast_reason in {
            "poor_pv_outlook",
            "forecast_energy_low",
        }:
            return True, "poor_forecast_allows_valley_charge"

        if reserve_reason in {
            "reserve_critical",
            "reserve_low",
        }:
            return True, "low_reserve_allows_valley_charge"

        if pv_reason in {
            "no_current_pv",
            "pv_contribution_low",
        }:
            return True, "weak_pv_allows_valley_charge"

        if (
            forecast_reason in {
                "mixed_pv_outlook",
                "forecast_energy_moderate",
            }
            and float(reserve_weight) >= 0.25
        ):
            return True, "mixed_forecast_allows_valley_charge"

        return False, "valley_charge_context_not_required"
        
    def _automatic_planning_permission(
        self,
        *,
        pv_weight: float,
        pv_reason: str,
        reserve_weight: float,
        reserve_reason: str,
        forecast_weight: float,
        forecast_reason: str,
    ) -> tuple[bool, str]:
        """Return whether Automatic may evaluate strategic charge planning.

        V4.3.0-dev5.5:
        This is only the high-level context permission.

        DecisionEngine remains authoritative for:
        - learned-planning readiness and charge windows
        - actual valley and future peak prices
        - required battery energy
        - latest-start deadlines
        - forecast-based waiting and reality override
        - SoC and protection conditions

        Planning is blocked only when current PV together with a sufficiently
        good forecast clearly makes optional grid charging unnecessary.
        """

        strong_pv = bool(
            pv_reason == "pv_covers_house_load"
            and float(pv_weight) >= 0.85
        )

        good_forecast = forecast_reason in {
            "good_pv_outlook",
            "forecast_energy_high",
        }

        if strong_pv and good_forecast:
            return False, "pv_and_good_forecast_block_planning"

        if (
            float(pv_weight) >= 0.85
            and good_forecast
            and float(reserve_weight) <= 0.35
        ):
            return False, "strong_pv_and_reserve_block_planning"

        if forecast_reason in {
            "poor_pv_outlook",
            "forecast_energy_low",
        }:
            return True, "poor_forecast_allows_planning"

        if reserve_reason in {
            "reserve_critical",
            "reserve_low",
        }:
            return True, "low_reserve_allows_planning"

        if pv_reason in {
            "no_current_pv",
            "pv_contribution_low",
        }:
            return True, "weak_pv_allows_planning"

        if forecast_reason in {
            "mixed_pv_outlook",
            "forecast_energy_moderate",
        }:
            return True, "mixed_forecast_allows_planning"

        return True, "planning_context_allowed"

    def evaluate(
        self,
        *,
        automatic_mode_active: bool,
        season_context: SeasonContext = "neutral",
        pv_w: float = 0.0,
        house_load_w: float = 0.0,
        installed_pv_wp: float = 0.0,
        soc: float = 0.0,
        soc_min: float = 0.0,
        soc_max: float = 100.0,
        price_now: float | None = None,
        price_min: float | None = None,
        price_max: float | None = None,
        price_average: float | None = None,
        forecast_status: str = "unknown",
        pv_outlook: str = "unknown",
        forecast_remaining_today_kwh: float = 0.0,
        forecast_tomorrow_kwh: float = 0.0,
        grid_import_w: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> StrategyContext:
        """Return the current automatic-strategy context."""

        context_metadata = dict(metadata or {})

        if not bool(automatic_mode_active):
            context_metadata.update(
                {
                    "automatic_discharge_allowed": False,
                    "automatic_discharge_reason": (
                        "automatic_mode_inactive"
                    ),
                    "automatic_peak_reserve_allowed": False,
                    "automatic_peak_reserve_reason": (
                        "automatic_mode_inactive"
                    ),
                    "automatic_valley_charge_allowed": False,
                    "automatic_valley_charge_reason": (
                        "automatic_mode_inactive"
                    ),
                    "automatic_planning_allowed": False,
                    "automatic_planning_reason": (
                        "automatic_mode_inactive"
                    ),
                }
            )

            return StrategyContext(
                active=False,
                weighting="inactive",
                season_context=season_context,
                pv_weight=0.0,
                price_weight=0.0,
                reserve_weight=0.0,
                forecast_weight=0.0,
                reason="automatic_mode_inactive",
                metadata=context_metadata,
            )

        pv_weight, pv_reason = self._pv_weight(
            pv_w=float(pv_w or 0.0),
            house_load_w=float(house_load_w or 0.0),
            installed_pv_wp=float(installed_pv_wp or 0.0),
            season_context=season_context,
        )

        price_weight, price_reason = self._price_weight(
            price_now=price_now,
            price_min=price_min,
            price_max=price_max,
            price_average=price_average,
        )

        reserve_weight, reserve_reason = self._reserve_weight(
            soc=float(soc),
            soc_min=float(soc_min),
            soc_max=float(soc_max),
        )

        forecast_weight, forecast_reason = self._forecast_weight(
            forecast_status=str(forecast_status),
            pv_outlook=str(pv_outlook),
            remaining_today_kwh=float(
                forecast_remaining_today_kwh or 0.0
            ),
            tomorrow_kwh=float(forecast_tomorrow_kwh or 0.0),
        )

        weighting, weighting_reason = self._select_weighting(
            pv_weight=pv_weight,
            price_weight=price_weight,
            reserve_weight=reserve_weight,
            forecast_weight=forecast_weight,
        )
        
        (
            automatic_discharge_allowed,
            automatic_discharge_reason,
        ) = self._automatic_discharge_permission(
            price_weight=price_weight,
            price_reason=price_reason,
            reserve_weight=reserve_weight,
            reserve_reason=reserve_reason,
            pv_weight=pv_weight,
            pv_reason=pv_reason,
            grid_import_w=float(grid_import_w or 0.0),
        )
        (
            automatic_peak_reserve_allowed,
            automatic_peak_reserve_reason,
        ) = self._automatic_peak_reserve_permission(
            pv_weight=pv_weight,
            pv_reason=pv_reason,
            reserve_weight=reserve_weight,
            reserve_reason=reserve_reason,
            forecast_weight=forecast_weight,
            forecast_reason=forecast_reason,
        )
        (
            automatic_valley_charge_allowed,
            automatic_valley_charge_reason,
        ) = self._automatic_valley_charge_permission(
            pv_weight=pv_weight,
            pv_reason=pv_reason,
            reserve_weight=reserve_weight,
            reserve_reason=reserve_reason,
            forecast_weight=forecast_weight,
            forecast_reason=forecast_reason,
        )
        (
            automatic_planning_allowed,
            automatic_planning_reason,
        ) = self._automatic_planning_permission(
            pv_weight=pv_weight,
            pv_reason=pv_reason,
            reserve_weight=reserve_weight,
            reserve_reason=reserve_reason,
            forecast_weight=forecast_weight,
            forecast_reason=forecast_reason,
        )

        context_metadata.update(
            {
                "pv_weight_reason": pv_reason,
                "price_weight_reason": price_reason,
                "reserve_weight_reason": reserve_reason,
                "forecast_weight_reason": forecast_reason,
                "weighting_reason": weighting_reason,
                "automatic_discharge_allowed": bool(
                    automatic_discharge_allowed
                ),
                "automatic_discharge_reason": str(
                    automatic_discharge_reason
                ),
                "automatic_peak_reserve_allowed": bool(
                    automatic_peak_reserve_allowed
                ),
                "automatic_peak_reserve_reason": str(
                    automatic_peak_reserve_reason
                ),
                "automatic_valley_charge_allowed": bool(
                    automatic_valley_charge_allowed
                ),
                "automatic_valley_charge_reason": str(
                    automatic_valley_charge_reason
                ),
                "automatic_planning_allowed": bool(
                    automatic_planning_allowed
                ),
                "automatic_planning_reason": str(
                    automatic_planning_reason
                ),
            }
        )

        return StrategyContext(
            active=True,
            weighting=weighting,
            season_context=season_context,
            pv_weight=round(pv_weight, 3),
            price_weight=round(price_weight, 3),
            reserve_weight=round(reserve_weight, 3),
            forecast_weight=round(forecast_weight, 3),
            reason=weighting_reason,
            metadata=context_metadata,
        )
