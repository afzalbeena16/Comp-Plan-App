import numpy as np
import pandas as pd
import pytest

from agents import run_pipeline
from agents.calendar_utils import business_days
from agents.payout_agent import payout_factor


@pytest.fixture(scope="module")
def ctx():
    return run_pipeline("2026-10-16")


def test_all_agents_succeed(ctx):
    assert [t.status for t in ctx.trace] == ["ok"] * 6


def test_attainment_matches_raw_deals(ctx):
    deals = ctx.frames["deals"]
    won = deals[(deals.stage == "Closed Won") & (deals.close_date.dt.month == 10)
                & (deals.close_date <= "2026-10-16")]
    s = ctx.frames["summary"]
    assert np.isclose(s["mtd_bookings"].sum(), won["amount"].sum())


def test_pacing_status_consistent_with_index(ctx):
    s = ctx.frames["summary"]
    assert (s.loc[s.pacing_status == "Ahead", "pace_index"] >= 1.05).all()
    assert (s.loc[s.pacing_status == "Behind", "pace_index"] < 0.95).all()


def test_risk_scores_in_range_and_ordered(ctx):
    s = ctx.frames["summary"]
    assert s["risk_score"].between(0, 100).all()
    assert s.loc[s.risk_level == "High", "risk_score"].min() >= 60


def test_payout_curve():
    f = payout_factor([0.3, 0.5, 0.8, 1.0, 1.2, 3.0])
    assert list(np.round(f, 2)) == [0.0, 0.5, 0.8, 1.0, 1.3, 2.0]


def test_business_days():
    assert business_days(pd.Timestamp("2026-10-01").date(), pd.Timestamp("2026-10-31").date()) == 22


def test_data_agent_flags_bad_rows(tmp_path):
    import shutil
    from agents.orchestrator import ROOT
    for f in ("reps.csv", "quotas.csv", "deals.csv"):
        shutil.copy(ROOT / "data" / f, tmp_path / f)
    deals = pd.read_csv(tmp_path / "deals.csv")
    bad = deals.head(2).copy()
    bad.loc[:, "amount"] = -5
    pd.concat([deals, bad.assign(deal_id=["X1", "X2"]), deals.head(1)]).to_csv(tmp_path / "deals.csv", index=False)
    ctx = run_pipeline("2026-10-16", data_dir=tmp_path)
    assert any("duplicate" in i for i in ctx.issues)
    assert any("non-positive" in i for i in ctx.issues)
