"""Reusable Streamlit UI components and small formatting helpers.

Keeping presentation logic here keeps the page files short and consistent.
"""

from __future__ import annotations

from typing import Any

import altair as alt
import pandas as pd
import streamlit as st

from wcps import data_io, evaluation
from wcps.flags import label_for
from wcps.schemas import OUTCOME_AWAY, OUTCOME_DRAW, OUTCOME_HOME

OUTCOME_COLORS = {OUTCOME_HOME: "#2563eb", OUTCOME_DRAW: "#9ca3af", OUTCOME_AWAY: "#dc2626"}

# Friendly labels for prediction sources (model ids + ensemble + legacy).
SOURCE_LABELS = {
    "standard": "Standard",
    "conservative": "Conservative",
    "aggressive": "Aggressive",
    "ensemble": "Ensemble",
    "chatgpt_legacy": "ChatGPT (legacy)",
}


def source_label(source: str) -> str:
    return SOURCE_LABELS.get(source, source)


# --- formatting -------------------------------------------------------------
def team_label(code: str, teams: dict[str, Any], use_flags: bool = True) -> str:
    name = teams.get(code, {}).get("name", code)
    return label_for(code, name) if use_flags else name


def outcome_word(outcome: str, home: str, away: str) -> str:
    return {
        OUTCOME_HOME: f"{home} win",
        OUTCOME_DRAW: "Draw",
        OUTCOME_AWAY: f"{away} win",
    }[outcome]


def confidence_badge(conf: float) -> str:
    if conf >= 0.40:
        return "🟢 High"
    if conf >= 0.18:
        return "🟡 Medium"
    return "🔴 Low"


def quality_note(quality: str) -> str | None:
    return {
        "missing_context": "⚠️ Generated without daily context (neutral assumptions).",
        "degraded": "⚠️ Partial/approximate prediction — see the model's warnings.",
    }.get(quality)


# --- banners ----------------------------------------------------------------
def demo_banner(show: bool, has_demo: bool) -> None:
    if show and has_demo:
        st.info(
            "🧪 **Demo data shown.** These are clearly fabricated fixtures for a "
            "recreational simulation sandbox — not real predictions, not betting advice.",
            icon="🧪",
        )


def disclaimer_footer() -> None:
    st.caption(
        "WCPS is a recreational probabilistic **simulation sandbox** for analysis and "
        "visualization only. It is not betting, gambling, odds optimization, or financial advice."
    )


# --- charts -----------------------------------------------------------------
def outcome_bar_chart(pred: dict[str, Any], home: str, away: str) -> alt.Chart:
    df = pd.DataFrame(
        {
            "outcome": [f"{home} win", "Draw", f"{away} win"],
            "probability": [pred["prob_home"], pred["prob_draw"], pred["prob_away"]],
            "key": [OUTCOME_HOME, OUTCOME_DRAW, OUTCOME_AWAY],
        }
    )
    return (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X("probability:Q", scale=alt.Scale(domain=[0, 1]),
                    axis=alt.Axis(format="%")),
            y=alt.Y("outcome:N", sort=None, title=None),
            color=alt.Color("key:N",
                            scale=alt.Scale(domain=list(OUTCOME_COLORS),
                                            range=list(OUTCOME_COLORS.values())),
                            legend=None),
            tooltip=[alt.Tooltip("probability:Q", format=".1%"), "outcome:N"],
        )
        .properties(height=130)
    )


def scoreline_heatmap(pred: dict[str, Any], home: str, away: str, max_g: int = 5) -> alt.Chart:
    rows = []
    for score, prob in pred["scoreline_probs"].items():
        x, y = (int(v) for v in score.split("-"))
        if x <= max_g and y <= max_g:
            rows.append({"home_goals": x, "away_goals": y, "probability": prob})
    df = pd.DataFrame(rows)
    return (
        alt.Chart(df)
        .mark_rect()
        .encode(
            x=alt.X("away_goals:O", title=f"{away} goals"),
            y=alt.Y("home_goals:O", title=f"{home} goals",
                    sort=alt.EncodingSortField("home_goals", order="descending")),
            color=alt.Color("probability:Q", scale=alt.Scale(scheme="blues"),
                            legend=alt.Legend(format=".0%", title="P")),
            tooltip=[alt.Tooltip("home_goals:O"), alt.Tooltip("away_goals:O"),
                     alt.Tooltip("probability:Q", format=".1%")],
        )
        .properties(height=260)
    )


def model_comparison_chart(model_preds: dict[str, dict], ensemble: dict) -> alt.Chart:
    rows = []
    sources = dict(model_preds)
    sources["ensemble"] = ensemble
    for source, p in sources.items():
        for key, label in [("prob_home", "Home"), ("prob_draw", "Draw"),
                           ("prob_away", "Away")]:
            rows.append({"source": source, "outcome": label, "probability": p[key]})
    df = pd.DataFrame(rows)
    return (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X("source:N", title=None),
            y=alt.Y("probability:Q", axis=alt.Axis(format="%"),
                    scale=alt.Scale(domain=[0, 1])),
            color=alt.Color("outcome:N", legend=alt.Legend(title="Outcome")),
            column=alt.Column("outcome:N", title=None),
            tooltip=["source:N", "outcome:N", alt.Tooltip("probability:Q", format=".1%")],
        )
        .properties(height=180, width=110)
    )


# --- match card -------------------------------------------------------------
def match_card(
    match: dict[str, Any],
    mp: dict[str, Any],
    teams: dict[str, Any],
    use_flags: bool,
    on_select_key: str,
) -> None:
    """Render a compact match card with a 'Details' selector button."""
    ens = mp["ensemble"]
    home, away = match["home_team"], match["away_team"]
    h_lab = team_label(home, teams, use_flags)
    a_lab = team_label(away, teams, use_flags)

    actual = evaluation.result_for_match(match)

    with st.container(border=True):
        top = st.columns([3, 1])
        with top[0]:
            st.markdown(f"### {h_lab}  vs  {a_lab}")
            meta = []
            if match.get("kickoff"):
                meta.append(f"🕒 {match['kickoff']}")
            if match.get("venue"):
                meta.append(f"📍 {match['venue']}")
            if match.get("phase"):
                grp = f" {match.get('group','')}".rstrip()
                meta.append(f"🏆 {match['phase']}{grp}")
            if meta:
                st.caption("  ·  ".join(meta))
        with top[1]:
            if actual:
                st.success(f"Final {actual['home_goals']}–{actual['away_goals']}")
            else:
                st.caption("No result yet")

        # outcome probabilities
        st.altair_chart(outcome_bar_chart(ens, home, away), use_container_width=True)

        cols = st.columns(3)
        cols[0].metric("Preferred", outcome_word(ens["recommended_outcome"], home, away))
        cols[1].metric("Score", ens["recommended_score"])
        cols[2].metric("Confidence", confidence_badge(ens["confidence"]))

        note = quality_note(ens["quality"])
        if note:
            st.caption(note)

        st.caption(
            f"Ensemble of {len(mp['models'])} models · "
            f"modal {ens['modal_score']}"
        )
        if st.button("🔍 Details", key=on_select_key, use_container_width=True):
            st.session_state["selected_match"] = match["match_id"]
            st.session_state["selected_date"] = match["date"]
            st.switch_page("pages/1_Match_Detail.py")


def recent_form_block(
    home: str,
    away: str,
    teams: dict[str, Any],
    use_flags: bool,
    before_date: str | None = None,
    limit: int = 5,
) -> None:
    """Render both teams' last results (newest first) side by side."""
    badges = {"W": "🟢", "D": "🟡", "L": "🔴"}
    cols = st.columns(2)
    for col, code in zip(cols, (home, away)):
        with col:
            st.markdown(f"**{team_label(code, teams, use_flags)}** — recent results")
            rows = evaluation.recent_results_for_team(
                code, before_date=before_date, limit=limit
            )
            if not rows:
                st.caption("No recorded results yet.")
                continue
            # compact form summary (W/D/L badges, newest → oldest)
            st.markdown(" ".join(badges[r["outcome"]] for r in rows))
            for r in rows:
                opp = team_label(r["opponent"], teams, use_flags)
                place = "vs" if r["venue"] == "H" else "@"
                st.caption(
                    f"{badges[r['outcome']]} **{r['gf']}–{r['ga']}** {place} {opp}  ·  {r['date']}"
                )


def team_model_accuracy_block(
    home: str,
    away: str,
    teams: dict[str, Any],
    use_flags: bool,
    rows: list[dict[str, Any]],
) -> None:
    """Per team: each model's (and the benchmark's) winner hit-rate so far."""
    cols = st.columns(2)
    for col, code in zip(cols, (home, away)):
        with col:
            st.markdown(f"**{team_label(code, teams, use_flags)}** — model hit-rate")
            data = evaluation.team_source_accuracy(code, rows)
            if not data["sources"]:
                st.caption("No evaluated matches for this team yet.")
                continue
            table = [
                {"Source": source_label(s), "Matches": d["n"], "Outcome acc.": d["accuracy"]}
                for s, d in data["sources"].items()
            ]
            if data["benchmark"]:
                b = data["benchmark"]
                table.append({"Source": "Benchmark (FIFA rank)",
                              "Matches": b["n"], "Outcome acc.": b["accuracy"]})
            df = pd.DataFrame(table).sort_values("Outcome acc.", ascending=False)
            st.dataframe(
                df.style.format({"Outcome acc.": "{:.0%}"}),
                hide_index=True, use_container_width=True,
            )
            best = max(data["sources"].items(), key=lambda kv: kv[1]["accuracy"])
            st.caption(
                f"Best model so far: **{source_label(best[0])}** "
                f"({best[1]['accuracy']:.0%} over {best[1]['n']} match(es))."
            )


def result_only_card(
    match: dict[str, Any], teams: dict[str, Any], use_flags: bool
) -> None:
    """Compact card for a scheduled match that has a real result but no prediction."""
    home, away = match["home_team"], match["away_team"]
    h_lab = team_label(home, teams, use_flags)
    a_lab = team_label(away, teams, use_flags)
    actual = evaluation.result_for_match(match)
    with st.container(border=True):
        st.markdown(f"### {h_lab}  vs  {a_lab}")
        meta = []
        if match.get("kickoff"):
            meta.append(f"🕒 {match['kickoff']}")
        if match.get("group"):
            meta.append(f"🏆 {match.get('phase','')} {match['group']}".strip())
        if meta:
            st.caption("  ·  ".join(meta))
        if actual:
            st.success(f"Final {actual['home_goals']}–{actual['away_goals']}")
        st.caption("No model prediction for this match (no daily context was provided).")
