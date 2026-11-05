from __future__ import annotations

import numpy as np
import pandas as pd

from .base import Agent, Context


def _clip01(x):
    return np.clip(x, 0, 1)


class RiskAgent(Agent):
    """Scores each rep's risk of missing quota (0-100) and explains the drivers."""
    name = "Risk Agent"
    role = "Quota risk scoring: pacing gap, pipeline coverage, trend, deal concentration"

    def run(self, ctx: Context) -> str:
        cfg = ctx.config["risk"]
        w = cfg["weights"]
        s = ctx.frames["summary"]
        monthly = ctx.frames["monthly"]
        deals = ctx.frames["deals"]
        as_of = pd.Timestamp(ctx.config["as_of_date"])

        # 1) Pacing gap: how far below the expected-to-date line the rep is.
        pace_gap = _clip01((1 - s["pace_index"]) / 0.5)

        # 2) Pipeline coverage: weighted pipeline closing this quarter vs. quota still to close.
        remaining = (s["qtd_quota"] - s["qtd_bookings"]).clip(lower=1)
        s["weighted_coverage"] = s["weighted_pipe_quarter"] / remaining
        s.loc[s["qtd_bookings"] >= s["qtd_quota"], "weighted_coverage"] = np.inf
        tgt = cfg["target_weighted_coverage"]
        coverage = _clip01((tgt - s["weighted_coverage"]) / tgt)

        # 3) Trend: last 3 closed months vs the 3 before.
        closed = monthly[monthly["month"] < as_of.month].sort_values("month")
        def trend(g):
            a = g["attainment"].tolist()
            return np.mean(a[-6:-3]) - np.mean(a[-3:]) if len(a) >= 6 else 0.0
        s["attainment_trend_drop"] = closed.groupby("rep_id").apply(trend, include_groups=False).reindex(s.index).fillna(0)
        trend_r = _clip01(s["attainment_trend_drop"] / 0.30)

        # 4) Concentration: share of weighted quarter pipeline sitting in a single deal.
        q_end = ctx.frames["calendar"]["quarter_end"]
        open_ = deals[(deals["stage"] != "Closed Won") & (deals["close_date"].dt.date <= q_end)].copy()
        open_["weighted"] = open_["amount"] * open_["probability"]
        top_share = (open_.groupby("rep_id")["weighted"].max() / open_.groupby("rep_id")["weighted"].sum())
        s["top_deal_share"] = top_share.reindex(s.index).fillna(1.0)
        conc = _clip01((s["top_deal_share"] - 0.30) / 0.40)

        s["risk_score"] = (w["pacing_gap"] * pace_gap + w["pipeline_coverage"] * coverage
                           + w["trend"] * trend_r + w["concentration"] * conc).round(0)
        s["risk_level"] = np.select([s["risk_score"] >= cfg["high"], s["risk_score"] >= cfg["medium"]],
                                    ["High", "Medium"], "Low")

        reasons = []
        for rid, r in s.iterrows():
            why = []
            if pace_gap[rid] > 0.2:
                why.append(f"{r.pace_index:.0%} of expected pace (gap ${r.gap_to_pace:,.0f})")
            if coverage[rid] > 0.2:
                why.append(f"weighted pipeline covers only {r.weighted_coverage:.1f}x of remaining quarter quota")
            if trend_r[rid] > 0.2:
                why.append(f"attainment down {r.attainment_trend_drop:.0%} vs prior 3 months")
            if conc[rid] > 0.2:
                why.append(f"{r.top_deal_share:.0%} of pipeline in one deal")
            reasons.append("; ".join(why) or "No material risk drivers")
        s["risk_drivers"] = reasons

        c = s["risk_level"].value_counts().to_dict()
        return f"High risk {c.get('High', 0)}, Medium {c.get('Medium', 0)}, Low {c.get('Low', 0)}"
