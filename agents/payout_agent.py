from __future__ import annotations

import numpy as np

from .base import Agent, Context


def payout_factor(attainment, threshold=0.5, accel_start=1.0, accel_rate=1.5, cap=2.0):
    """Plan curve: 0 below threshold, 1:1 up to 100%, accelerated above, capped."""
    a = np.asarray(attainment, dtype=float)
    base = np.where(a < threshold, 0.0, np.minimum(a, accel_start))
    accel = np.where(a > accel_start, (a - accel_start) * accel_rate, 0.0)
    return np.minimum(base + accel, cap)


class PayoutAgent(Agent):
    """Applies the comp plan curve to estimate commission for the month."""
    name = "Payout Agent"
    role = "Estimate variable pay from attainment using the plan curve"

    def run(self, ctx: Context) -> str:
        p = ctx.config["payout"]
        s = ctx.frames["summary"]
        kw = dict(threshold=p["threshold"], accel_start=p["accelerator_start"],
                  accel_rate=p["accelerator_rate"], cap=p["cap"])
        s["monthly_target_variable"] = s["annual_variable_ote"] / 12
        s["earned_to_date"] = s["monthly_target_variable"] * payout_factor(s["mtd_attainment"], **kw)
        s["projected_payout"] = s["monthly_target_variable"] * payout_factor(s["projected_month_attainment"], **kw)
        s["payout_factor_projected"] = payout_factor(s["projected_month_attainment"], **kw)
        return (f"Projected month payout ${s['projected_payout'].sum():,.0f} vs target "
                f"${s['monthly_target_variable'].sum():,.0f}")
