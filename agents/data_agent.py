from __future__ import annotations

from pathlib import Path

import pandas as pd

from .base import Agent, Context


class DataAgent(Agent):
    """Loads reps, quotas and deals, and validates them before anything is calculated."""
    name = "Data Agent"
    role = "Load and validate CRM exports (reps, quotas, deals)"

    def run(self, ctx: Context) -> str:
        d = Path(ctx.data_dir)
        reps = pd.read_csv(d / "reps.csv")
        quotas = pd.read_csv(d / "quotas.csv")
        deals = pd.read_csv(d / "deals.csv", parse_dates=["created_date", "close_date"])

        issues = ctx.issues
        dupes = deals["deal_id"].duplicated().sum()
        if dupes:
            issues.append(f"{dupes} duplicate deal IDs removed")
            deals = deals.drop_duplicates("deal_id")
        neg = (deals["amount"] <= 0).sum()
        if neg:
            issues.append(f"{neg} deals with non-positive amount excluded")
            deals = deals[deals["amount"] > 0]
        orphan = ~deals["rep_id"].isin(reps["rep_id"])
        if orphan.any():
            issues.append(f"{orphan.sum()} deals reference unknown reps and were excluded")
            deals = deals[~orphan]
        no_quota = set(reps["rep_id"]) - set(quotas["rep_id"])
        if no_quota:
            issues.append(f"Reps without quota: {', '.join(sorted(no_quota))}")

        ctx.frames.update(reps=reps, quotas=quotas, deals=deals)
        won = (deals["stage"] == "Closed Won").sum()
        return (f"Loaded {len(reps)} reps, {len(quotas)} quota rows, {len(deals)} deals "
                f"({won} closed won, {len(deals) - won} open); {len(issues)} data issues")
