"""Run the multi-agent pipeline from the command line and print a rep summary.

    python run_pipeline.py                  # uses as_of_date from comp_plan.json
    python run_pipeline.py --as-of 2026-10-30
"""
import argparse

from agents import run_pipeline

parser = argparse.ArgumentParser()
parser.add_argument("--as-of", help="Override the as-of date (YYYY-MM-DD)")
parser.add_argument("--out", help="Optional CSV path for the full rep summary")
args = parser.parse_args()

ctx = run_pipeline(args.as_of)
print("Agent trace")
for t in ctx.trace:
    print(f"  [{t.status}] {t.agent:<17} {t.seconds*1000:6.1f} ms  {t.summary}")
s = ctx.frames["summary"]
cols = ["rep_name", "mtd_bookings", "mtd_quota", "pace_index", "pacing_status",
        "projected_month_attainment", "risk_score", "risk_level", "projected_payout"]
print("\n" + s[cols].sort_values("risk_score", ascending=False).to_string(
    formatters={"mtd_bookings": "${:,.0f}".format, "mtd_quota": "${:,.0f}".format,
                "pace_index": "{:.0%}".format, "projected_month_attainment": "{:.0%}".format,
                "projected_payout": "${:,.0f}".format}))
print("\nTeam summary:", ctx.frames["team_summary"])
if ctx.issues:
    print("Data issues:", *ctx.issues, sep="\n  - ")
if args.out:
    s.to_csv(args.out)
    print(f"Saved {args.out}")
