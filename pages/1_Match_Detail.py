"""Match detail page — full breakdown for one selected match."""

from __future__ import annotations

import app.bootstrap  # noqa: F401  # isort:skip
from typing import Any

import pandas as pd
import streamlit as st

from app import components as ui
from wcps import data_io, pipeline
from wcps.config import load_config
from wcps import evaluation
from wcps.evaluation import actual_outcome

st.set_page_config(page_title="WCPS · Match Detail", page_icon="🔍", layout="wide")
cfg = load_config()
teams = data_io.load_teams()


def _stats_table(stats: dict[str, dict[str, float]]) -> pd.DataFrame:
    labels = {
        "goals_home": "Goals (home)",
        "goals_away": "Goals (away)",
        "total_goals": "Total goals",
        "goal_diff": "Goal difference",
        "points_home": "Points (home)",
        "points_away": "Points (away)",
    }
    rows = []
    for key, label in labels.items():
        s = stats.get(key)
        if not s:
            continue
        rows.append({
            "Quantity": label,
            "Mean": round(s["mean"], 2),
            "Median": round(s["median"], 2),
            f"P{int(s['lower_q']*100)}": round(s["lower"], 2),
            f"P{int(s['upper_q']*100)}": round(s["upper"], 2),
        })
    return pd.DataFrame(rows).set_index("Quantity")


def _scoreline_table(items: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(
        [{"Score": it["score"], "Probability": it["prob"]} for it in items]
    )


def _render_model_block(p: dict[str, Any], home: str, away: str) -> None:
    cols = st.columns(4)
    cols[0].metric("Preferred", ui.outcome_word(p["recommended_outcome"], home, away))
    cols[1].metric("Rec. score", p["recommended_score"])
    cols[2].metric("Modal", p["modal_score"])
    cols[3].metric("Confidence", ui.confidence_badge(p["confidence"]))
    st.caption(
        f"Model `{p['model_id']}` v{p['model_version']} · "
        f"λ home={p['lambda_home']:.2f}, λ away={p['lambda_away']:.2f} · run {p['run_datetime']}"
    )
    if p.get("warnings"):
        for w in p["warnings"]:
            st.caption(f"⚠️ {w}")

    metrics = p.get("metrics") or {}
    if metrics:
        m = st.columns(3)
        if "p_favourite_win_by_2plus" in metrics:
            m[0].metric("Wide win P(≥2)", f"{metrics['p_favourite_win_by_2plus']:.0%}")
        if "p_favourite_win_by_3plus" in metrics:
            m[1].metric("Blowout P(≥3)", f"{metrics['p_favourite_win_by_3plus']:.0%}")
        if "goleada_tail_index" in metrics:
            m[2].metric("Goleada tail", f"{metrics['goleada_tail_index']:.2f}")

    a, b = st.columns(2)
    with a:
        st.markdown("**Outcome probabilities**")
        st.altair_chart(ui.outcome_bar_chart(p, home, away), use_container_width=True)
        st.markdown("**Summary statistics**")
        st.dataframe(_stats_table(p["stats"]), use_container_width=True)
    with b:
        st.markdown("**Top scorelines (overall)**")
        st.dataframe(
            _scoreline_table(p["top_scorelines"]).style.format({"Probability": "{:.1%}"}),
            use_container_width=True, hide_index=True,
        )
        st.markdown(f"**Top scorelines within preferred outcome**")
        st.dataframe(
            _scoreline_table(p["top_scorelines_in_outcome"]).style.format(
                {"Probability": "{:.1%}"}),
            use_container_width=True, hide_index=True,
        )


# --- select a match ---------------------------------------------------------
all_matches = data_io.load_matches()
if not all_matches:
    st.warning("No matches available.")
    st.stop()

match_ids = [m["match_id"] for m in all_matches]
def _predicted_ids() -> set[str]:
    out: set[str] = set()
    for d in data_io.available_dates():
        p = data_io.load_predictions(d)
        if p:
            out.update(p.get("predictions", {}))
    return out


predicted = _predicted_ids()
default_id = st.session_state.get("selected_match")
if default_id not in match_ids:
    # prefer a match that actually has a prediction over a result-only fixture
    default_id = next((m for m in match_ids if m in predicted), match_ids[0])


def _fmt(mid: str) -> str:
    m = data_io.get_match(mid) or {}
    h = teams.get(m.get("home_team", ""), {}).get("name", m.get("home_team", ""))
    a = teams.get(m.get("away_team", ""), {}).get("name", m.get("away_team", ""))
    return f"{m.get('date','')} · {h} vs {a}"


match_id = st.selectbox(
    "Match", match_ids, index=match_ids.index(default_id), format_func=_fmt
)
match = data_io.get_match(match_id)
date = match["date"]
home, away = match["home_team"], match["away_team"]
h_lab = ui.team_label(home, teams, cfg["display"]["use_flags"])
a_lab = ui.team_label(away, teams, cfg["display"]["use_flags"])

payload = pipeline.get_or_generate(date)
mp = payload.get("predictions", {}).get(match_id)
if not mp:
    st.warning("No prediction available yet. Regenerate from the dashboard.")
    st.stop()

models = mp["models"]
ens = mp["ensemble"]

# --- header -----------------------------------------------------------------
st.title(f"{h_lab}  vs  {a_lab}")
meta = [f"📅 {date}"]
if match.get("kickoff"):
    meta.append(f"🕒 {match['kickoff']}")
if match.get("venue"):
    meta.append(f"📍 {match['venue']}")
if match.get("phase"):
    meta.append(f"🏆 {match['phase']} {match.get('group','')}".rstrip())
st.caption("  ·  ".join(meta))
ui.demo_banner(cfg["display"].get("show_demo_banner", True), match.get("is_demo", False))

note = ui.quality_note(ens["quality"])
if note:
    st.warning(note)

# --- actual result + comparison --------------------------------------------
actual = evaluation.result_for_match(match)
if actual:
    real_out = actual_outcome(actual["home_goals"], actual["away_goals"])
    st.success(
        f"**Final result: {actual['home_goals']}–{actual['away_goals']}** "
        f"· {ui.outcome_word(real_out, home, away)}"
    )
    eval_rows = []
    sources_all = {**models, "ensemble": ens}
    for src, p in sources_all.items():
        eval_rows.append({
            "source": src,
            "Predicted outcome": ui.outcome_word(p["recommended_outcome"], home, away),
            "Outcome ✓": "✅" if p["recommended_outcome"] == real_out else "❌",
            "Predicted score": p["recommended_score"],
            "Exact score ✓": "✅" if p["recommended_score"] ==
            f"{actual['home_goals']}-{actual['away_goals']}" else "❌",
        })
    st.markdown("**Historical comparison**")
    st.dataframe(pd.DataFrame(eval_rows).set_index("source"), use_container_width=True)

# --- recent form (last results of each team) --------------------------------
st.subheader("Recent form")
st.caption("Last results of each team going into this match (newest first).")
ui.recent_form_block(home, away, teams, cfg["display"]["use_flags"], before_date=date)

# --- which model has been best for each team --------------------------------
st.subheader("Model accuracy by team")
st.caption(
    "Winner hit-rate of each model — and the FIFA-ranking benchmark — across all "
    "evaluated matches involving each team. Helps see which model reads each side best."
)
ui.team_model_accuracy_block(
    home, away, teams, cfg["display"]["use_flags"], evaluation.build_history(cfg)
)

# --- ensemble headline ------------------------------------------------------
st.subheader("Ensemble summary")
c = st.columns(4)
c[0].metric("Preferred", ui.outcome_word(ens["recommended_outcome"], home, away))
c[1].metric("Recommended score", ens["recommended_score"])
c[2].metric("Modal score", ens["modal_score"])
c[3].metric("Confidence", ui.confidence_badge(ens["confidence"]))

left, right = st.columns(2)
with left:
    st.markdown("**Outcome probabilities (ensemble)**")
    st.altair_chart(ui.outcome_bar_chart(ens, home, away), use_container_width=True)
with right:
    st.markdown("**Scoreline heatmap (ensemble)**")
    st.altair_chart(ui.scoreline_heatmap(ens, home, away), use_container_width=True)

# --- model comparison -------------------------------------------------------
st.subheader("Model comparison")
st.altair_chart(ui.model_comparison_chart(models, ens), use_container_width=True)

comp_rows = []
sources = {**models, "ensemble": ens}
for src, p in sources.items():
    comp_rows.append({
        "source": src,
        f"{home} win": p["prob_home"],
        "Draw": p["prob_draw"],
        f"{away} win": p["prob_away"],
        "Preferred": ui.outcome_word(p["recommended_outcome"], home, away),
        "Rec. score": p["recommended_score"],
        "λ home": round(p["lambda_home"], 2),
        "λ away": round(p["lambda_away"], 2),
    })
comp_df = pd.DataFrame(comp_rows).set_index("source")
st.dataframe(
    comp_df.style.format({f"{home} win": "{:.1%}", "Draw": "{:.1%}",
                          f"{away} win": "{:.1%}"}),
    use_container_width=True,
)

# --- per-model detail tabs --------------------------------------------------
st.subheader("Per-model & ensemble detail")
order = list(models) + ["ensemble"]
tabs = st.tabs([ui.source_label(s) for s in order])
for tab, src in zip(tabs, order):
    with tab:
        _render_model_block(sources[src], home, away)

# --- daily context used -----------------------------------------------------
st.subheader("Daily context used")
ctx_entry = data_io.context_for_match(date, match_id)
if ctx_entry is None:
    st.info("No daily context for this match — models used neutral assumptions.")
else:
    with st.expander("Show raw context JSON"):
        st.json(ctx_entry)

st.divider()
ui.disclaimer_footer()
