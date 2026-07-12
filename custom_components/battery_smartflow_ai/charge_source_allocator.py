from __future__ import annotations

from .regulation_models import ChargeSourceAllocation


class ChargeSourceAllocator:
    """Allocate a strategic battery charge target between PV and grid.

    V4.3.0-dev4.0:
    The allocator is diagnostic-only. It calculates a provisional source split
    but does not yet modify the StrategyIntent, PowerController result or final
    device command.
    """

    def allocate(
        self,
        *,
        charge_commit_active: bool,
        allow_pv_blend: bool,
        total_target_w: float,
        pv_w: float,
        house_load_w: float,
        max_grid_input_w: float,
    ) -> ChargeSourceAllocation:
        """Calculate the provisional PV/grid split of an AC-Ladebindung.

        The estimated PV contribution is the PV power remaining after the
        measured house load.

        Example:
            total charge target = 1800 W
            PV after house load = 650 W
            provisional grid request = 1150 W
        """
        total_target = max(0.0, float(total_target_w or 0.0))
        max_grid_input = max(0.0, float(max_grid_input_w or 0.0))

        if not bool(charge_commit_active):
            return ChargeSourceAllocation(
                active=False,
                total_target_w=total_target,
                reason="no_active_charge_binding",
            )

        if total_target <= 0.0:
            return ChargeSourceAllocation(
                active=False,
                total_target_w=0.0,
                reason="no_charge_target",
            )

        if not bool(allow_pv_blend):
            grid_requested = min(total_target, max_grid_input)
            unfilled = max(0.0, total_target - grid_requested)

            return ChargeSourceAllocation(
                active=True,
                total_target_w=round(total_target, 2),
                pv_available_w=0.0,
                pv_allocated_w=0.0,
                grid_requested_w=round(grid_requested, 2),
                unfilled_w=round(unfilled, 2),
                pv_share_pct=0.0,
                grid_share_pct=round(
                    (grid_requested / total_target) * 100.0,
                    1,
                ),
                reason="pv_blend_disabled",
            )

        pv_available = max(
            0.0,
            float(pv_w or 0.0) - float(house_load_w or 0.0),
        )

        pv_allocated = min(
            total_target,
            pv_available,
        )

        remaining_target = max(
            0.0,
            total_target - pv_allocated,
        )

        grid_requested = min(
            remaining_target,
            max_grid_input,
        )

        unfilled = max(
            0.0,
            remaining_target - grid_requested,
        )

        pv_share_pct = (
            (pv_allocated / total_target) * 100.0
            if total_target > 0.0
            else 0.0
        )

        grid_share_pct = (
            (grid_requested / total_target) * 100.0
            if total_target > 0.0
            else 0.0
        )

        if pv_allocated <= 0.0:
            reason = "grid_only_no_pv_surplus"
        elif grid_requested <= 0.0:
            reason = "pv_covers_total_charge_target"
        elif unfilled > 0.0:
            reason = "mixed_charge_grid_limit_reached"
        else:
            reason = "mixed_pv_grid_charge"

        return ChargeSourceAllocation(
            active=True,
            total_target_w=round(total_target, 2),
            pv_available_w=round(pv_available, 2),
            pv_allocated_w=round(pv_allocated, 2),
            grid_requested_w=round(grid_requested, 2),
            unfilled_w=round(unfilled, 2),
            pv_share_pct=round(pv_share_pct, 1),
            grid_share_pct=round(grid_share_pct, 1),
            reason=reason,
        )