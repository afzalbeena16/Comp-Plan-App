from __future__ import annotations

import os

from .base import Agent, Context


class InsightsAgent(Agent):
    """Turns the numbers into short coaching notes for each rep and a team summary.

    Uses rule-based text by default. If ANTHROPIC_API_KEY is set and the `anthropic`
    package is installed, it asks Claude for the team summary instead.
    """
    name = "Insights Agent"
    role = "Write rep coaching notes and a team summary"

    def run(self, ctx: Context) -> str:
        s = ctx.frames["summary"]
        notes = []
        for _, r in s.iterrows():
            if r.risk_level == "High":
                action = "Review pipeline this week and pull forward late-stage deals."
            elif r.risk_level == "Medium":
                action = "Add pipeline for next month and confirm close dates on commit deals."
            elif r.pacing_status == "Ahead":
                action = "On track for accelerators; protect big deals from slipping."
            else:
                action = "Keep current cadence."
            notes.append(f"{r.pacing_status} ({r.pace_index:.0%} of pace), projected "
                         f"{r.projected_month_attainment:.0%} of month quota. {action}")
        s["coaching_note"] = notes

        team_summary = self._rule_summary(s)
        source = "rules"
        if os.getenv("ANTHROPIC_API_KEY"):
            try:
                team_summary = self._llm_summary(s, team_summary)
                source = "Claude"
            except Exception as exc:  # fall back silently to rules
                ctx.issues.append(f"LLM summary unavailable ({type(exc).__name__}); used rule-based summary")
        ctx.frames["team_summary"] = team_summary
        return f"Wrote {len(notes)} coaching notes and a team summary ({source})"

    @staticmethod
    def _rule_summary(s) -> str:
        att = s["mtd_bookings"].sum() / s["mtd_expected"].sum()
        proj = s["projected_month_bookings"].sum() / s["mtd_quota"].sum()
        high = s[s["risk_level"] == "High"].sort_values("risk_score", ascending=False)["rep_name"].tolist()
        ahead = s[s["pacing_status"] == "Ahead"].sort_values("pace_index", ascending=False)["rep_name"].tolist()
        parts = [f"The team is at {att:.0%} of expected pace and projected to finish the month at {proj:.0%} of quota."]
        if ahead:
            parts.append(f"{len(ahead)} rep(s) ahead of pace, led by {', '.join(ahead[:3])}.")
        if high:
            parts.append(f"{len(high)} rep(s) are high risk: {', '.join(high)}. Focus 1:1s on pipeline and close dates.")
        return " ".join(parts)

    @staticmethod
    def _llm_summary(s, fallback: str) -> str:
        import anthropic  # optional dependency

        cols = ["rep_name", "pacing_status", "pace_index", "projected_month_attainment", "risk_level", "risk_drivers"]
        table = s[cols].to_csv(index=False, float_format="%.2f")
        client = anthropic.Anthropic()
        msg = client.messages.create(
            model=os.getenv("COMP_APP_MODEL", "claude-sonnet-4-5"),
            max_tokens=300,
            messages=[{"role": "user", "content":
                       "You are a sales operations analyst. In 3-4 sentences, summarize quota pacing and risk for "
                       "this sales team for a VP of Sales. Be specific and use numbers.\n\n" + table}],
        )
        return msg.content[0].text.strip() or fallback
