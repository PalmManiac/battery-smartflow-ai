from __future__ import annotations
from dataclasses import dataclass


@dataclass
class PowerContext:
    soc: float
    soc_min: float
    soc_max: float

    max_charge_w: float
    max_discharge_w: float

    grid_import_w: float
    grid_export_w: float

    prev_discharge_w: float
    prev_charge_w: float

    target_grid_w: float
    deadband_w: float
    export_guard_w: float
    kp_up: float
    kp_down: float
    max_step_up_w: float
    max_step_down_w: float
    keepalive_min_deficit_w: float
    keepalive_min_output_w: float


class PowerController:

    # --------------------------------------------------
    # Delta discharge (EXAKT aus V2.0.4 übernommen)
    # --------------------------------------------------

    @staticmethod
    def delta_discharge(ctx: PowerContext) -> float:
        if ctx.soc <= ctx.soc_min:
            return 0.0

        net = float(ctx.grid_import_w) - float(ctx.grid_export_w)
        out_w = float(ctx.prev_discharge_w or 0.0)

        if net < -ctx.export_guard_w:
            cut = (abs(net) + ctx.target_grid_w) * 1.4
            out_w = max(0.0, out_w - cut)
            return min(float(ctx.max_discharge_w), out_w)

        err = net - ctx.target_grid_w

        if err > ctx.deadband_w:
            step = min(ctx.max_step_up_w, max(40.0, ctx.kp_up * err))
            out_w += step

        elif err < -ctx.deadband_w:
            step = min(ctx.max_step_down_w, max(60.0, ctx.kp_down * abs(err)))
            out_w -= step

        out_w = max(0.0, min(float(ctx.max_discharge_w), out_w))

        if (
            ctx.prev_discharge_w > ctx.keepalive_min_output_w
            and ctx.grid_import_w <= ctx.keepalive_min_deficit_w
        ):
            out_w = max(out_w, ctx.keepalive_min_output_w)

        return out_w


    # --------------------------------------------------
    # Delta charge (EXAKT aus V2.0.4 übernommen)
    # --------------------------------------------------

    @staticmethod
    def delta_charge(ctx: PowerContext) -> float:
        max_step_up_w = ctx.max_step_up_w * 0.5
        max_step_down_w = ctx.max_step_down_w * 0.5

        if ctx.soc >= ctx.soc_max:
            return 0.0

        net = float(ctx.grid_import_w) - float(ctx.grid_export_w)
        in_w = float(ctx.prev_charge_w or 0.0)

        if net > ctx.deadband_w:
            step = min(max_step_down_w, max(60.0, ctx.kp_down * abs(net)))
            in_w -= step
            return max(0.0, min(float(ctx.max_charge_w), in_w))

        target_net = -ctx.target_grid_w
        err = target_net - net

        if net < -ctx.export_guard_w:
            step = min(max_step_up_w * 1.5, max(40.0, ctx.kp_up * abs(err)))
            in_w += step
            return max(0.0, min(float(ctx.max_charge_w), in_w))

        if err > ctx.deadband_w:
            step = min(max_step_up_w, max(30.0, ctx.kp_up * err))
            in_w += step

        elif err < -ctx.deadband_w:
            step = min(max_step_down_w, max(40.0, ctx.kp_down * abs(err)))
            in_w -= step

        in_w = max(0.0, min(float(ctx.max_charge_w), in_w))
        return in_w
