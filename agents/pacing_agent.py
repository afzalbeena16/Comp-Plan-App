from __future__ import annotations

import numpy as np
import pandas as pd

from .base import Agent, Context
from .calendar_utils import business_days, month_bounds, quarter_bounds


class PacingAgent(Agent):
    """Compares bookings to where each rep *should* be by today, and projects period-end results."""
    name = "Pacing Agent"
    role = "Quota pacing: expected-to-date, pace index, projected month/quarter end"

    def run(self, ctx: Context) -> str:
        as_of = pd.Timestamp(ctx.config["as_of_date"]).date()
        th = ctx.config["pacing_thresholds"]
        s = ctx.frames["summary"]
        deals = ctx.frames["deals"]

        m0, m1 = month_bounds(as_of)
        q0, q1 = quarter_bounds(as_of)
        m_elapsed = business_days(m0, as_of) / business_days(m0, m1)
        q_elapsed = business_days(q0, as_of) / business_days(q0, q1)
        ctx.frames["calendar"] = dict(month_start=m0, month_end=m1, quarter_start=q0, quarter_end=q1,
                                      month_elapsed=m_elapsed, quarter_elapsed=q_elapsed)

        s["mtd_expected"] = s["mtd_quota"] * m_elapsed
        s["qtd_expected"] = s["qtd_quota"] * q_elapsed
        s["pace_index"] = s["mtd_bookings"] / s["mtd_expected"]          # 1.0 = exactly on pace
        s["qtd_pace_index"] = s["qtd_bookings"] / s["qtd_expected"]
        s["gap_to_pace"] = s["mtd_expected"] - s["mtd_bookings"]

        # Projection blends two forecasts: straight-line run rate, and booked + weighted pipeline
        # closing inside the period. Each alone is biased (run rate ignores pipeline, pipeline ignores
        # deals not yet created), so the app uses the average.
        open_ = deals[deals["stage"] != "Closed Won"].copy()
        open_["weighted"] = open_["amount"] * open_["probability"]
        in_month = open_[open_["close_date"].dt.date <= m1].groupby("rep_id")["weighted"].sum()
        in_qtr = open_[open_["close_date"].dt.date <= q1].groupby("rep_id")["weighted"].sum()
        s["weighted_pipe_month"] = in_month.reindex(s.index).fillna(0)
        s["weighted_pipe_quarter"] = in_qtr.reindex(s.index).fillna(0)
        s["pipeline_month_bookings"] = s["mtd_bookings"] + s["weighted_pipe_month"]
        s["run_rate_month_bookings"] = s["mtd_bookings"] / m_elapsed
        s["projected_month_bookings"] = (s["pipeline_month_bookings"] + s["run_rate_month_bookings"]) / 2
        s["projected_month_attainment"] = s["projected_month_bookings"] / s["mtd_quota"]
        s["projected_quarter_attainment"] = (s["qtd_bookings"] + s["weighted_pipe_quarter"]) / s["qtd_quota"]

        s["pacing_status"] = np.select(
            [s["pace_index"] >= th["ahead"], s["pace_index"] >= th["on_pace"]],
            ["Ahead", "On pace"], "Behind")

        counts = s["pacing_status"].value_counts().to_dict()
        return (f"{m_elapsed:.0%} of month / {q_elapsed:.0%} of quarter elapsed (business days); "
                f"Ahead {counts.get('Ahead', 0)}, On pace {counts.get('On pace', 0)}, Behind {counts.get('Behind', 0)}")
