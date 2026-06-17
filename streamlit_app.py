"""WCPS — World Cup Prediction Sandbox · Streamlit entry point (Dashboard).

Run locally:
    streamlit run streamlit_app.py
"""

from __future__ import annotations

import app.bootstrap  # noqa: F401  (puts src/ on sys.path)  # isort:skip
import streamlit as st

from app import components as ui
from wcps import data_io, pipeline
from wcps.config import ensure_data_dirs, load_config

st.set_page_config(page_title="WCPS Dashboard", page_icon="⚽", layout="wide")

cfg = load_config()
ensure_data_dirs()
display = cfg["display"]

st.title("⚽ " + display["app_title"])
st.markdown(
    "A **recreational probabilistic simulator** for World Cup matches. Pick a date, "
    "explore each fixture's simulated outcome probabilities, recommended scoreline and "
    "model/ensemble summary, then open a match for the full breakdown."
)

teams = data_io.load_teams()
dates = data_io.available_dates()

if not dates:
    st.warning(
        "No matches found. Add fixtures to `data/raw/matches.json` and daily context "
        "to `data/context/YYYY-MM-DD.json`."
    )
    ui.disclaimer_footer()
    st.stop()

# --- date selector ----------------------------------------------------------
default_mode = display.get("default_date", "latest_with_data")
default_idx = len(dates) - 1 if default_mode != "earliest" else 0
if default_mode == "today" and st.session_state.get("_today") in dates:
    default_idx = dates.index(st.session_state["_today"])

col_date, col_btn = st.columns([3, 1])
with col_date:
    selected_date = st.selectbox(
        "📅 Match date", dates, index=default_idx,
        format_func=lambda d: d,
    )
with col_btn:
    st.write("")
    st.write("")
    regenerate = st.button("🔄 Regenerate", use_container_width=True,
                           help="Re-run all models for this date from the current context.")

matches = data_io.matches_for_date(selected_date)
context = data_io.load_context(selected_date)

if regenerate:
    with st.spinner("Running models…"):
        pipeline.generate_for_date(selected_date)
    st.success("Predictions regenerated.")

# context status line
if context is None:
    st.warning(
        f"⚠️ No daily context file for **{selected_date}** "
        f"(`data/context/{selected_date}.json`). Predictions use neutral assumptions.",
        icon="⚠️",
    )

payload = pipeline.get_or_generate(selected_date)
predictions = payload.get("predictions", {})

has_demo = any(m.get("is_demo") for m in matches)
ui.demo_banner(display.get("show_demo_banner", True), has_demo)

st.subheader(f"{len(matches)} match(es) on {selected_date}")

# --- match cards (responsive grid) -----------------------------------------
cols_per_row = 2
for i in range(0, len(matches), cols_per_row):
    row = st.columns(cols_per_row)
    for j, match in enumerate(matches[i : i + cols_per_row]):
        mp = predictions.get(match["match_id"])
        with row[j]:
            if not mp:
                st.warning(f"No prediction for {match['match_id']}.")
                continue
            ui.match_card(match, mp, teams, display.get("use_flags", True),
                          on_select_key=f"sel_{match['match_id']}")

st.divider()
ui.disclaimer_footer()
