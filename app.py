"""Compensation Plan App - Streamlit dashboard over the multi-agent pipeline.

    streamlit run app.py
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from agents import run_pipeline
from agents.orchestrator import load_config
from agents.payout_agent import payout_factor

st.set_page_config(page_title="Compensation Plan App", page_icon="📈", layout="wide")

# Status colors carry state only and always ship with a text label.
STATUS = {"Ahead": "#0ca30c", "On pace": "#fab219", "Behind": "#d03b3b",
          "Low": "#0ca30c", "Medium": "#fab219", "High": "#d03b3b"}
SERIES = ["#2a78d6", "#eb6834"]  # categorical slots 1-2
ICON = {"Ahead": "▲", "On pace": "●", "Behind": "▼", "Low": "●", "Medium": "◆", "High": "▲"}


def style(fig: go.Figure, height=380) -> go.Figure:
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=50, b=10), legend_title_text="",
                      legend=dict(orientation="h", yanchor="top", y=-0.12, x=0),
                      hoverlabel=dict(font_size=13), bargap=0.35)
    fig.update_xaxes(showgrid=True, gridwidth=1, zeroline=False)
    fig.update_yaxes(showgrid=False, zeroline=False)
    return fig


@st.cache_data(show_spinner="Running agents...")
def load(as_of: str):
    ctx = run_pipeline(as_of)
    trace = pd.DataFrame([t.__dict__ for t in ctx.trace])
    return (ctx.frames["summary"].reset_index(), ctx.frames["monthly"], ctx.frames["deals"],
            ctx.frames["calendar"], ctx.frames["team_summary"], trace, ctx.issues, ctx.config)


cfg = load_config()
st.title("Compensation Plan App")
st.caption(f"{cfg['plan_name']} · multi-agent quota attainment, pacing and risk analysis · demo data")

f1, f2, f3, f4 = st.columns([1.2, 1, 1, 1.4])
as_of = f1.date_input("As of date", value=date.fromisoformat(cfg["as_of_date"]),
                      min_value=date(2026, 1, 5), max_value=date(2026, 12, 31))
summary, monthly, deals, cal, team_summary, trace, issues, run_cfg = load(as_of.isoformat())
regions = f2.multiselect("Region", sorted(summary["region"].unique()))
managers = f3.multiselect("Manager", sorted(summary["manager"].unique()))
risk_filter = f4.multiselect("Risk level", ["High", "Medium", "Low"])

s = summary.copy()
if regions:
    s = s[s["region"].isin(regions)]
if managers:
    s = s[s["manager"].isin(managers)]
if risk_filter:
    s = s[s["risk_level"].isin(risk_filter)]
if s.empty:
    st.warning("No reps match these filters.")
    st.stop()

PCT = ["mtd_attainment", "qtd_attainment", "projected_month_attainment", "projected_quarter_attainment",
       "attainment_trend_drop", "top_deal_share", "pace_index"]


def pct_view(df):
    """Copy with ratio columns scaled to 0-100 so tables show whole percents."""
    out = df.copy()
    for c in PCT:
        if c in out:
            out[c] = out[c] * 100
    return out


def pct(label):
    return st.column_config.NumberColumn(label, format="%.0f%%")


s["label"] = s["pacing_status"].map(lambda x: f"{ICON[x]} {x}")
s["risk_label"] = s["risk_level"].map(lambda x: f"{ICON[x]} {x}")

# ---------- KPI row ----------
mtd_b, mtd_q, exp = s["mtd_bookings"].sum(), s["mtd_quota"].sum(), s["mtd_expected"].sum()
k = st.columns(5)
k[0].metric("MTD bookings", f"${mtd_b:,.0f}", f"{mtd_b / mtd_q:.0%} of ${mtd_q:,.0f} quota", delta_color="off", delta_arrow="off")
k[1].metric("Team pace", f"{mtd_b / exp:.0%}", f"{mtd_b - exp:+,.0f} vs expected-to-date")
k[2].metric("Projected month-end", f"{s['projected_month_bookings'].sum() / mtd_q:.0%}",
            f"${s['projected_month_bookings'].sum():,.0f}", delta_color="off", delta_arrow="off")
k[3].metric("Reps at high risk", int((s["risk_level"] == "High").sum()),
            f"{int((s['pacing_status'] == 'Behind').sum())} behind pace", delta_color="off", delta_arrow="off")
k[4].metric("Projected payout", f"${s['projected_payout'].sum():,.0f}",
            f"target ${s['monthly_target_variable'].sum():,.0f}", delta_color="off", delta_arrow="off")
st.caption(f"{cal['month_elapsed']:.0%} of the month and {cal['quarter_elapsed']:.0%} of the quarter elapsed "
           f"(business days, {cal['month_start']:%b %d}–{cal['month_end']:%b %d}).")
st.info(team_summary, icon="🤖")

tabs = st.tabs(["Quota pacing", "Risk analysis", "Attainment trend", "Payouts", "Rep drilldown", "Agent trace"])

# ---------- Pacing ----------
with tabs[0]:
    order = s.sort_values("pace_index")["rep_name"].tolist()
    c1, c2 = st.columns(2)
    fig = px.bar(s, x="pace_index", y="rep_name", orientation="h", color="pacing_status",
                 color_discrete_map=STATUS, category_orders={"rep_name": order,
                                                             "pacing_status": ["Ahead", "On pace", "Behind"]},
                 custom_data=["mtd_bookings", "mtd_expected", "gap_to_pace"],
                 title="Pace index (bookings ÷ expected-to-date)")
    fig.update_traces(hovertemplate="<b>%{y}</b><br>Pace %{x:.0%}<br>Booked $%{customdata[0]:,.0f}"
                                    "<br>Expected $%{customdata[1]:,.0f}<br>Gap $%{customdata[2]:,.0f}<extra></extra>",
                      marker_line_width=0)
    fig.add_vline(x=1, line_dash="dot", line_width=1, annotation_text="On pace", annotation_position="top")
    fig.update_xaxes(tickformat=".0%", title=None)
    fig.update_yaxes(title=None)
    c1.plotly_chart(style(fig, 440), use_container_width=True)

    fig = go.Figure()
    fig.add_bar(y=s["rep_name"], x=s["mtd_bookings"], orientation="h", name="Booked MTD",
                marker_color=SERIES[0], hovertemplate="<b>%{y}</b><br>Booked $%{x:,.0f}<extra></extra>")
    fig.add_scatter(y=s["rep_name"], x=s["mtd_expected"], mode="markers", name="Expected to date",
                    marker=dict(symbol="line-ns", size=18, line=dict(width=3, color=SERIES[1])),
                    hovertemplate="<b>%{y}</b><br>Expected $%{x:,.0f}<extra></extra>")
    fig.add_scatter(y=s["rep_name"], x=s["projected_month_bookings"], mode="markers", name="Projected month-end",
                    marker=dict(symbol="diamond-open", size=10, color="#6250d6", line=dict(width=2)),
                    hovertemplate="<b>%{y}</b><br>Projected $%{x:,.0f}<extra></extra>")
    fig.update_layout(title="Booked vs expected-to-date vs projected ($)")
    fig.update_yaxes(categoryorder="array", categoryarray=order[::-1])
    fig.update_xaxes(tickprefix="$", tickformat=",.0f")
    c2.plotly_chart(style(fig, 440), use_container_width=True)

    st.dataframe(
        pct_view(s)[["rep_name", "region", "mtd_quota", "mtd_bookings", "mtd_expected", "gap_to_pace", "pace_index", "label",
           "weighted_pipe_month", "projected_month_attainment", "qtd_attainment", "projected_quarter_attainment"]]
        .sort_values("pace_index"),
        hide_index=True, use_container_width=True,
        column_config={
            "rep_name": "Rep", "region": "Region", "label": "Status",
            "mtd_quota": st.column_config.NumberColumn("Month quota", format="$%,.0f"),
            "mtd_bookings": st.column_config.NumberColumn("Booked MTD", format="$%,.0f"),
            "mtd_expected": st.column_config.NumberColumn("Expected to date", format="$%,.0f"),
            "gap_to_pace": st.column_config.NumberColumn("Gap to pace", format="$%,.0f"),
            "pace_index": st.column_config.ProgressColumn("Pace", format="%.0f%%", min_value=0, max_value=150),
            "weighted_pipe_month": st.column_config.NumberColumn("Weighted pipe (month)", format="$%,.0f"),
            "projected_month_attainment": pct("Proj. month"),
            "qtd_attainment": pct("QTD attain."),
            "projected_quarter_attainment": pct("Proj. quarter"),
        })

# ---------- Risk ----------
with tabs[1]:
    c1, c2 = st.columns([1.1, 1])
    r = s.copy()
    r["coverage_plot"] = r["weighted_coverage"].replace(np.inf, 3).clip(upper=3)
    r["tag"] = np.where(r["risk_level"] == "Low", "", r["rep_name"])  # label only reps that need attention
    fig = px.scatter(r, x="pace_index", y="coverage_plot", color="risk_level", color_discrete_map=STATUS,
                     symbol="risk_level", symbol_map={"Low": "circle", "Medium": "diamond", "High": "triangle-up"},
                     category_orders={"risk_level": ["High", "Medium", "Low"]}, text="tag",
                     custom_data=["risk_score", "risk_drivers", "rep_name"],
                     title="Risk map: pace vs weighted pipeline coverage")
    fig.update_traces(marker=dict(size=13, line=dict(width=2, color="white")), textposition="top center",
                      textfont_size=10, cliponaxis=False,
                      hovertemplate="<b>%{customdata[2]}</b><br>Pace %{x:.0%} · Coverage %{y:.1f}x"
                                    "<br>Risk score %{customdata[0]:.0f}<br>%{customdata[1]}<extra></extra>")
    fig.add_vline(x=1, line_dash="dot", line_width=1)
    fig.add_hline(y=run_cfg["risk"]["target_weighted_coverage"], line_dash="dot", line_width=1,
                  annotation_text="Target coverage", annotation_position="top left")
    fig.update_xaxes(tickformat=".0%", title="Pace index",
                     range=[r["pace_index"].min() - 0.1, r["pace_index"].max() + 0.12])
    fig.update_yaxes(title="Weighted pipeline coverage (x, capped at 3)", showgrid=True,
                     range=[0, max(1.5, r["coverage_plot"].max() + 0.2)])
    c1.plotly_chart(style(fig, 460), use_container_width=True)

    w = run_cfg["risk"]["weights"]
    c2.markdown("**How the risk score works (0–100)**")
    c2.markdown(
        f"- **Pacing gap** ({w['pacing_gap']} pts): how far bookings are below expected-to-date\n"
        f"- **Pipeline coverage** ({w['pipeline_coverage']} pts): weighted pipeline closing this quarter "
        f"vs quota still to close (target {run_cfg['risk']['target_weighted_coverage']}x)\n"
        f"- **Trend** ({w['trend']} pts): drop in attainment over the last 3 months vs the 3 before\n"
        f"- **Concentration** ({w['concentration']} pts): share of pipeline riding on one deal\n\n"
        f"High ≥ {run_cfg['risk']['high']}, Medium ≥ {run_cfg['risk']['medium']}.")
    st.dataframe(
        pct_view(s).sort_values("risk_score", ascending=False)[["rep_name", "manager", "risk_score", "risk_label",
                                                      "weighted_coverage", "attainment_trend_drop",
                                                      "top_deal_share", "risk_drivers"]],
        hide_index=True, use_container_width=True,
        column_config={
            "rep_name": "Rep", "manager": "Manager", "risk_label": "Risk",
            "risk_score": st.column_config.ProgressColumn("Risk score", format="%d", min_value=0, max_value=100),
            "weighted_coverage": st.column_config.NumberColumn("Coverage", format="%.1fx"),
            "attainment_trend_drop": pct("Trend drop"),
            "top_deal_share": pct("Top deal share"),
            "risk_drivers": st.column_config.TextColumn("Drivers", width="large"),
        })

# ---------- Trend ----------
with tabs[2]:
    m = monthly[monthly["rep_id"].isin(s["rep_id"]) & (monthly["month"] < as_of.month)]
    team = m.groupby("month")[["bookings", "quota"]].sum()
    team["attainment"] = team["bookings"] / team["quota"]
    pick = st.selectbox("Compare a rep against the team", s.sort_values("rep_name")["rep_name"])
    rid = s.loc[s["rep_name"] == pick, "rep_id"].iloc[0]
    rep_m = m[m["rep_id"] == rid].set_index("month")
    months = [date(2026, i, 1).strftime("%b") for i in team.index]
    fig = go.Figure()
    fig.add_scatter(x=months, y=team["attainment"], name="Team", mode="lines+markers",
                    line=dict(width=2, color=SERIES[0]), marker=dict(size=8),
                    hovertemplate="%{x}: %{y:.0%}<extra>Team</extra>")
    fig.add_scatter(x=months, y=rep_m["attainment"].reindex(team.index), name=pick, mode="lines+markers",
                    line=dict(width=2, color=SERIES[1]), marker=dict(size=8),
                    hovertemplate="%{x}: %{y:.0%}<extra>" + pick + "</extra>")
    fig.add_hline(y=1, line_dash="dot", line_width=1, annotation_text="Quota", annotation_position="right")
    fig.update_layout(title="Monthly attained goal (% of quota), closed months", hovermode="x unified")
    fig.update_yaxes(tickformat=".0%", showgrid=True)
    fig.update_xaxes(showgrid=False)
    st.plotly_chart(style(fig, 400), use_container_width=True)

    hm = m.merge(s[["rep_id", "rep_name"]], on="rep_id").pivot(index="rep_name", columns="month", values="attainment")
    hm.columns = [date(2026, c, 1).strftime("%b") for c in hm.columns]
    st.markdown("**Monthly attainment by rep**")
    st.dataframe(hm.style.format("{:.0%}").background_gradient(cmap="Blues", vmin=0.3, vmax=1.4),
                 use_container_width=True)

# ---------- Payouts ----------
with tabs[3]:
    p = run_cfg["payout"]
    c1, c2 = st.columns([1, 1.2])
    xs = np.linspace(0, 2.2, 221)
    ys = payout_factor(xs, p["threshold"], p["accelerator_start"], p["accelerator_rate"], p["cap"])
    fig = go.Figure()
    fig.add_scatter(x=xs, y=ys, mode="lines", name="Plan curve", line=dict(width=2, color=SERIES[0]),
                    hovertemplate="Attainment %{x:.0%} → payout %{y:.0%} of target<extra></extra>")
    fig.add_scatter(x=s["projected_month_attainment"], y=s["payout_factor_projected"], mode="markers",
                    name="Reps (projected)", text=s["rep_name"],
                    marker=dict(size=10, color=SERIES[1], line=dict(width=2, color="white")),
                    hovertemplate="<b>%{text}</b><br>%{x:.0%} → %{y:.0%}<extra></extra>")
    fig.update_layout(title="Payout curve: threshold, accelerator and cap")
    fig.update_xaxes(tickformat=".0%", title="Attainment")
    fig.update_yaxes(tickformat=".0%", title="Payout as % of target variable", showgrid=True)
    c1.plotly_chart(style(fig, 400), use_container_width=True)
    c1.caption(f"No payout below {p['threshold']:.0%} attainment; 1:1 up to {p['accelerator_start']:.0%}; "
               f"{p['accelerator_rate']}x accelerator above; capped at {p['cap']:.0%} of target.")
    c2.dataframe(
        pct_view(s).sort_values("projected_payout", ascending=False)[
            ["rep_name", "role", "monthly_target_variable", "mtd_attainment",
             "projected_month_attainment", "projected_payout"]],
        hide_index=True, use_container_width=True, height=440,
        column_config={
            "rep_name": "Rep", "role": "Role",
            "monthly_target_variable": st.column_config.NumberColumn("Target variable", format="$%,.0f"),
            "mtd_attainment": pct("MTD attain."),
            "projected_month_attainment": pct("Proj. attain."),
            "projected_payout": st.column_config.NumberColumn("Proj. payout", format="$%,.0f"),
        })

# ---------- Drilldown ----------
with tabs[4]:
    pick = st.selectbox("Rep", s.sort_values("risk_score", ascending=False)["rep_name"], key="drill")
    r = s[s["rep_name"] == pick].iloc[0]
    a = st.columns(4)
    a[0].metric("Pacing", r["label"], f"{r['pace_index']:.0%} of expected", delta_color="off", delta_arrow="off")
    a[1].metric("Risk", r["risk_label"], f"score {r['risk_score']:.0f}/100", delta_color="off", delta_arrow="off")
    a[2].metric("Projected month", f"{r['projected_month_attainment']:.0%}",
                f"${r['projected_month_bookings']:,.0f} of ${r['mtd_quota']:,.0f}", delta_color="off", delta_arrow="off")
    a[3].metric("Projected payout", f"${r['projected_payout']:,.0f}",
                f"target ${r['monthly_target_variable']:,.0f}", delta_color="off", delta_arrow="off")
    st.markdown(f"**Coaching note:** {r['coaching_note']}  \n**Risk drivers:** {r['risk_drivers']}")
    d = deals[(deals["rep_id"] == r["rep_id"]) & (deals["stage"] != "Closed Won")].copy()
    d["weighted"] = d["amount"] * d["probability"]
    st.markdown("**Open pipeline**")
    st.dataframe(d.sort_values("close_date")[["deal_id", "account", "stage", "amount", "probability",
                                              "weighted", "close_date"]],
                 hide_index=True, use_container_width=True,
                 column_config={"amount": st.column_config.NumberColumn("Amount", format="$%,.0f"),
                                "weighted": st.column_config.NumberColumn("Weighted", format="$%,.0f"),
                                "probability": st.column_config.NumberColumn("Prob.", format="%.2f"),
                                "close_date": st.column_config.DateColumn("Close date")})

# ---------- Agent trace ----------
with tabs[5]:
    st.markdown("Each agent owns one job and writes its results to a shared context that the next agent reads.")
    t = trace.copy()
    t["ms"] = (t["seconds"] * 1000).round(1)
    st.dataframe(t[["agent", "status", "ms", "summary"]], hide_index=True, use_container_width=True,
                 column_config={"agent": "Agent", "status": "Status", "ms": "Time (ms)",
                                "summary": st.column_config.TextColumn("Output", width="large")})
    if issues:
        st.warning("Data issues:\n- " + "\n- ".join(issues))
    else:
        st.success("Data Agent found no data quality issues.")
    st.download_button("Download rep summary (CSV)", summary.to_csv(index=False), "rep_summary.csv", "text/csv")
