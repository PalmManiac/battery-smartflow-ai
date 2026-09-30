from __future__ import annotations

from .regulation_models import ChargeSourceAllocation


class ChargeSourceAllocator:
    """Allocate a strategic battery charge target between PV and grid.

    V4.4.0-dev8:
    Besides the diagnostic source split, the allocator calculates the AC input
    command. AC-coupled PV remains part of that command; directly connected
    native PV is reserved against the battery-side total charge limit, not the
    separately enforced AC inlet rating.
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
        max_total_charge_w: float | None = None,
        native_pv_w: float = 0.0,
        native_pv_valid: bool = False,
    ) -> ChargeSourceAllocation:
        """Calculate the provisional PV/grid split of an AC-Ladebindung.

        The estimated AC-coupled PV contribution is the PV power remaining
        after the measured house load. Native PV is a separate measurement
        connected directly to the battery system.

        Example:
            total charge target = 1800 W
            PV after house load = 650 W
            provisional grid request = 1150 W
        """
        max_grid_input = max(0.0, float(max_grid_input_w or 0.0))
        configured_total_limit = (
            max_grid_input_w
            if max_total_charge_w is None
            else max_total_charge_w
        )
        max_total_charge = max(
            0.0,
            float(configured_total_limit or 0.0),
        )
        total_target = min(
            max(0.0, float(total_target_w or 0.0)),
            max_total_charge,
        )

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

        native_pv_available = (
            max(0.0, float(native_pv_w or 0.0))
            if bool(native_pv_valid)
            else 0.0
        )
        native_pv_allocated = min(total_target, native_pv_available)
        ac_charge_headroom = max(0.0, max_total_charge - native_pv_allocated)
        device_input_limit = min(max_grid_input, ac_charge_headroom)
        target_after_native_pv = max(0.0, total_target - native_pv_allocated)

        if not bool(allow_pv_blend):
            grid_requested = min(total_target, device_input_limit)
            unfilled = max(
                0.0,
                total_target - native_pv_allocated - grid_requested,
            )

            return ChargeSourceAllocation(
                active=True,
                total_target_w=round(total_target, 2),
                native_pv_available_w=round(native_pv_available, 2),
                native_pv_allocated_w=round(native_pv_allocated, 2),
                pv_available_w=0.0,
                pv_allocated_w=0.0,
                grid_requested_w=round(grid_requested, 2),
                device_input_w=round(grid_requested, 2),
                unfilled_w=round(unfilled, 2),
                pv_share_pct=round(
                    (native_pv_allocated / total_target) * 100.0,
                    1,
                ),
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
            target_after_native_pv,
            pv_available,
        )

        remaining_target = max(
            0.0,
            target_after_native_pv - pv_allocated,
        )

        grid_requested = min(remaining_target, device_input_limit)

        unfilled = max(
            0.0,
            remaining_target - grid_requested,
        )

        # The controlled device input contains AC-coupled PV and grid power,
        # but excludes native PV connected directly to the battery system.
        # Also absorb AC-coupled PV surplus above a stale strategic target.
        planned_input = pv_allocated + grid_requested
        # Native PV contributes to the battery-side total charge ceiling, not
        # the AC inlet rating. Keep the AC hardware limit separate and only
        # reserve native PV from the remaining total battery-charge headroom.
        pv_surplus_input = min(pv_available, device_input_limit)
        device_input = min(
            device_input_limit,
            max(planned_input, pv_surplus_input),
        )

        pv_share_pct = (
            ((pv_allocated + native_pv_allocated) / total_target) * 100.0
            if total_target > 0.0
            else 0.0
        )

        grid_share_pct = (
            (grid_requested / total_target) * 100.0
            if total_target > 0.0
            else 0.0
        )

        if native_pv_allocated >= total_target:
            reason = "native_pv_covers_total_charge_target"
        elif native_pv_allocated > 0.0 and pv_allocated <= 0.0:
            reason = "native_pv_priority_grid_fills_remainder"
        elif pv_allocated <= 0.0:
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
            native_pv_available_w=round(native_pv_available, 2),
            native_pv_allocated_w=round(native_pv_allocated, 2),
            grid_requested_w=round(grid_requested, 2),
            device_input_w=round(device_input, 2),
            unfilled_w=round(unfilled, 2),
            pv_share_pct=round(pv_share_pct, 1),
            grid_share_pct=round(grid_share_pct, 1),
            reason=reason,
        )
