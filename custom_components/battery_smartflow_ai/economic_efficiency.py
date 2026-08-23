"""Economic efficiency derived from the persistent BSFAI value ledger."""

from __future__ import annotations

from math import isfinite


MIN_EVALUATED_ENERGY_KWH = 0.1


def economic_efficiency_pct(
    *,
    grid_charge_cost: float,
    pv_opportunity_cost: float,
    battery_benefit: float,
    charged_energy_kwh: float,
    discharged_energy_kwh: float,
) -> float | None:
    """Return economic value recovery in percent, or None if not meaningful.

    One hundred percent means the economic value of discharged battery energy
    exactly covers the valued grid-charge and PV-opportunity input. Values above
    100 percent represent an economic surplus. A non-positive input value has no
    finite cost-recovery ratio and is therefore deliberately unavailable.
    """

    values = (
        float(grid_charge_cost),
        float(pv_opportunity_cost),
        float(battery_benefit),
        float(charged_energy_kwh),
        float(discharged_energy_kwh),
    )
    if not all(isfinite(value) for value in values):
        return None

    if (
        charged_energy_kwh < MIN_EVALUATED_ENERGY_KWH
        or discharged_energy_kwh < MIN_EVALUATED_ENERGY_KWH
    ):
        return None

    valued_input = float(grid_charge_cost) + float(pv_opportunity_cost)
    if valued_input <= 0.0:
        return None

    discharged_value = float(battery_benefit) + valued_input
    return round((discharged_value / valued_input) * 100.0, 1)
