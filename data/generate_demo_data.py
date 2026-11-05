"""Generate synthetic demo data for the Compensation Plan App.

All names, accounts and numbers are fictional. Re-run to regenerate:
    python data/generate_demo_data.py
"""
from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

SEED = 42
YEAR = 2026
AS_OF = date(2026, 10, 16)  # demo "today" - mid-month so pacing is meaningful
OUT = Path(__file__).resolve().parent

REPS = [
    # rep_id, name, role, region, manager, monthly_quota, annual_variable_ote, profile
    ("R001", "Ava Thompson", "Account Executive", "West", "Daniel Reyes", 60000, 60000, "star"),
    ("R002", "Liam Carter", "Account Executive", "West", "Daniel Reyes", 60000, 60000, "steady"),
    ("R003", "Sofia Martinez", "Account Executive", "West", "Daniel Reyes", 55000, 55000, "slipping"),
    ("R004", "Noah Patel", "Senior Account Executive", "Central", "Hannah Brooks", 80000, 80000, "steady"),
    ("R005", "Emma Wilson", "Account Executive", "Central", "Hannah Brooks", 55000, 55000, "star"),
    ("R006", "Ethan Nguyen", "Account Executive", "Central", "Hannah Brooks", 55000, 55000, "struggling"),
    ("R007", "Olivia Brown", "Senior Account Executive", "East", "Marcus Lee", 80000, 80000, "steady"),
    ("R008", "Mason Kim", "Account Executive", "East", "Marcus Lee", 60000, 60000, "lumpy"),
    ("R009", "Isabella Garcia", "Account Executive", "East", "Marcus Lee", 60000, 60000, "star"),
    ("R010", "Lucas Ahmed", "SDR-to-AE (Ramping)", "East", "Marcus Lee", 35000, 40000, "ramping"),
    ("R011", "Mia Johnson", "Account Executive", "South", "Priya Shah", 55000, 55000, "slipping"),
    ("R012", "James Okafor", "Account Executive", "South", "Priya Shah", 55000, 55000, "steady"),
]

# Mean monthly attainment by profile; "slipping" declines over the year.
PROFILE_MEAN = {"star": 1.18, "steady": 0.98, "struggling": 0.68, "lumpy": 0.95, "ramping": 0.75}
PROFILE_SD = {"star": 0.12, "steady": 0.10, "struggling": 0.12, "lumpy": 0.45, "ramping": 0.15}

ACCOUNT_WORDS_A = ["North", "Blue", "Summit", "Bright", "Iron", "Silver", "Harbor", "Cedar", "Atlas", "Nova",
                   "Granite", "Pioneer", "Vertex", "Willow", "Falcon", "Crescent"]
ACCOUNT_WORDS_B = ["Logistics", "Health", "Foods", "Capital", "Systems", "Retail", "Energy", "Labs", "Media",
                   "Freight", "Analytics", "Partners", "Dynamics", "Works"]
OPEN_STAGES = [("Discovery", 0.10), ("Proposal", 0.35), ("Negotiation", 0.65), ("Commit", 0.85)]


def month_target(profile: str, month: int, rng: random.Random) -> float:
    if profile == "slipping":
        mean = 1.10 - 0.06 * (month - 1)  # strong start, fading
        sd = 0.08
    elif profile == "ramping":
        mean = min(0.45 + 0.07 * month, 1.0)
        sd = 0.10
    else:
        mean, sd = PROFILE_MEAN[profile], PROFILE_SD[profile]
    return max(0.15, rng.gauss(mean, sd))


def split_amount(total: float, rng: random.Random) -> list[int]:
    n = max(1, round(total / rng.uniform(9000, 22000)))
    weights = [rng.random() + 0.2 for _ in range(n)]
    s = sum(weights)
    return [int(round(total * w / s, -2)) for w in weights]


def account(rng: random.Random) -> str:
    return f"{rng.choice(ACCOUNT_WORDS_A)} {rng.choice(ACCOUNT_WORDS_B)}"


def main() -> None:
    rng = random.Random(SEED)
    reps_rows, quota_rows, deal_rows = [], [], []
    deal_no = 1000

    for rep_id, name, role, region, mgr, mq, ote, profile in REPS:
        reps_rows.append(dict(rep_id=rep_id, rep_name=name, role=role, region=region, manager=mgr,
                              annual_variable_ote=ote, plan_profile=profile))
        for m in range(1, 13):
            quota = mq if not (profile == "ramping" and m < 4) else int(mq * 0.6)
            quota_rows.append(dict(rep_id=rep_id, year=YEAR, month=m, quota=quota))
            first = date(YEAR, m, 1)
            last = (date(YEAR + (m == 12), m % 12 + 1, 1) - timedelta(days=1))
            if first > AS_OF:
                continue
            attain = month_target(profile, m, rng)
            if m == AS_OF.month:
                # Current month: only part of the month has elapsed.
                frac = (AS_OF.day / last.day) * rng.uniform(0.85, 1.35)
                if profile == "struggling":
                    frac *= 0.55
                if profile == "slipping":
                    frac *= 0.75
                attain *= frac
                last = AS_OF
            for amt in split_amount(quota * attain, rng):
                deal_no += 1
                close = first + timedelta(days=rng.randint(0, (last - first).days))
                deal_rows.append(dict(deal_id=f"D{deal_no}", rep_id=rep_id, account=account(rng), amount=amt,
                                      stage="Closed Won", probability=1.0,
                                      created_date=close - timedelta(days=rng.randint(20, 90)),
                                      close_date=close))

        # Open pipeline expected to close in the rest of the current month / quarter.
        cov = {"star": 2.4, "steady": 1.8, "struggling": 0.8, "lumpy": 2.0, "ramping": 1.3, "slipping": 1.0}[profile]
        remaining = mq * 2.5
        for amt in split_amount(remaining * cov * rng.uniform(0.8, 1.2), rng):
            deal_no += 1
            stage, prob = rng.choice(OPEN_STAGES)
            close = AS_OF + timedelta(days=rng.randint(3, 75))
            deal_rows.append(dict(deal_id=f"D{deal_no}", rep_id=rep_id, account=account(rng), amount=amt,
                                  stage=stage, probability=prob,
                                  created_date=AS_OF - timedelta(days=rng.randint(5, 60)), close_date=close))

    pd.DataFrame(reps_rows).to_csv(OUT / "reps.csv", index=False)
    pd.DataFrame(quota_rows).to_csv(OUT / "quotas.csv", index=False)
    pd.DataFrame(deal_rows).sort_values(["rep_id", "close_date"]).to_csv(OUT / "deals.csv", index=False)
    print(f"Wrote {len(reps_rows)} reps, {len(quota_rows)} quota rows, {len(deal_rows)} deals to {OUT}")


if __name__ == "__main__":
    main()
