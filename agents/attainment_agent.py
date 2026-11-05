from __future__ import annotations

import pandas as pd

from .base import Agent, Context
from .calendar_utils import quarter_months


class AttainmentAgent(Agent):
    """Calculates bookings vs quota for the month, quarter and year to date."""
    name = "Attainment Agent"
    role = "Compute MTD / QTD / YTD quota attainment per rep"

    def run(self, ctx: Context) -> str:
        as_of = pd.Timestamp(ctx.config["as_of_date"])
        reps, quotas, deals = (ctx.frames[k] for k in ("reps", "quotas", "deals"))

        won = deals[(deals["stage"] == "Closed Won") & (deals["close_date"] <= as_of)].copy()
        won["month"] = won["close_date"].dt.month
        won = won[won["close_date"].dt.year == as_of.year]

        monthly = (quotas[quotas["year"] == as_of.year]
                   .merge(won.groupby(["rep_id", "month"])["amount"].sum().rename("bookings").reset_index(),
                          on=["rep_id", "month"], how="left")
                   .fillna({"bookings": 0}))
        monthly["attainment"] = monthly["bookings"] / monthly["quota"]
        ctx.frames["monthly"] = monthly

        m, qm = as_of.month, quarter_months(as_of.date())

        def agg(mask, label):
            g = monthly[mask].groupby("rep_id")[["bookings", "quota"]].sum()
            g.columns = [f"{label}_bookings", f"{label}_quota"]
            g[f"{label}_attainment"] = g[f"{label}_bookings"] / g[f"{label}_quota"]
            return g

        summary = (reps.set_index("rep_id")
                   .join(agg(monthly["month"] == m, "mtd"))
                   .join(agg(monthly["month"].isin(qm), "qtd"))
                   .join(agg(monthly["month"] <= m, "ytd")))
        # QTD/YTD quotas above include the full current month; keep a "closed periods" view too.
        closed = monthly[monthly["month"] < m]
        summary["months_at_or_above_quota"] = (closed[closed["attainment"] >= 1]
                                               .groupby("rep_id").size()).reindex(summary.index).fillna(0).astype(int)
        summary["closed_months"] = closed.groupby("rep_id").size().reindex(summary.index).fillna(0).astype(int)
        ctx.frames["summary"] = summary

        team = summary["mtd_bookings"].sum() / summary["mtd_quota"].sum()
        ytd = summary["ytd_bookings"].sum() / summary["ytd_quota"].sum()
        return f"Team MTD attainment {team:.0%} of full-month quota; YTD {ytd:.0%} (incl. current month quota)"
