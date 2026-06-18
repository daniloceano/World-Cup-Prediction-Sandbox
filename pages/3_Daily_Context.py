"""Daily context page — paste/validate the daily JSON and (re)generate predictions.

Workflow: every morning, request the daily context from ChatGPT (see
docs/daily_context_prompt.md), paste the JSON here, validate it, save it to
data/context/YYYY-MM-DD.json, then generate predictions.
"""

from __future__ import annotations

import json

import app.bootstrap  # noqa: F401  # isort:skip
import streamlit as st

from app import components as ui
from wcps import data_io, pipeline
from wcps.config import load_config
from wcps.context import validate_context

st.set_page_config(page_title="WCPS · Daily Context", page_icon="📝", layout="wide")
cfg = load_config()

st.title("📝 Daily context")
st.markdown(
    "Paste the daily JSON from **Prompt A** in `docs/daily_context_prompt.md` "
    "(ChatGPT auto-detects today's date and lists today's matches). Validate it, "
    "save it to `data/context/YYYY-MM-DD.json`, then generate predictions — "
    "saving also registers today's fixtures into the schedule automatically. "
    "Original context files are preserved as an audit trail. "
    "For yesterday's final scores, use **Prompt B** and add them on the History side "
    "(`data/results/actual_results.json`)."
)

dates = data_io.available_dates()
date = st.text_input(
    "Date (YYYY-MM-DD)", value=dates[-1] if dates else "2026-06-17"
)

existing = data_io.load_context(date)
default_text = json.dumps(existing, indent=2, ensure_ascii=False) if existing else ""
if existing:
    st.caption(f"A context file already exists for {date}. Editing will overwrite it.")

text = st.text_area("Daily context JSON", value=default_text, height=360,
                    placeholder='{ "date": "YYYY-MM-DD", "matches": [ ... ] }')

c1, c2, c3 = st.columns(3)
validate_clicked = c1.button("✅ Validate", use_container_width=True)
save_clicked = c2.button("💾 Save", use_container_width=True)
gen_clicked = c3.button("⚙️ Save & generate predictions", use_container_width=True,
                        type="primary")


def _parse(raw: str):
    try:
        return json.loads(raw), None
    except json.JSONDecodeError as e:
        return None, f"Invalid JSON: {e}"


def _show_validation(ctx) -> bool:
    result = validate_context(ctx)
    for err in result.errors:
        st.error(err)
    for w in result.warnings:
        st.warning(w)
    any_match_warn = False
    for mid, warns in result.per_match.items():
        if warns:
            any_match_warn = True
            with st.expander(f"⚠️ {mid} — {len(warns)} note(s)"):
                for w in warns:
                    st.write("•", w)
    if result.ok and not result.warnings and not any_match_warn:
        st.success("Context is valid and complete. ✅")
    elif result.ok:
        st.info("Context is usable but has warnings (predictions will be flagged).")
    return result.ok


def _save(ctx) -> None:
    path = data_io.context_path(date)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(ctx, fh, indent=2, ensure_ascii=False)
    st.success(f"Saved to `{path}`.")
    # Register fixtures/teams the context describes (Prompt A metadata), so the
    # date shows up in the dashboard even before predictions are generated.
    n_teams, n_matches = data_io.sync_schedule_from_context(ctx)
    if n_matches or n_teams:
        st.info(f"Registered {n_matches} new fixture(s) and {n_teams} new team(s) "
                "into the schedule.")


if validate_clicked or save_clicked or gen_clicked:
    ctx, err = _parse(text)
    if err:
        st.error(err)
    else:
        ok = _show_validation(ctx)
        if (save_clicked or gen_clicked) and ok:
            _save(ctx)
        if gen_clicked and ok:
            with st.spinner("Generating predictions…"):
                payload = pipeline.generate_for_date(date)
            st.success(f"Generated predictions for {payload['n_matches']} match(es).")
            st.page_link("streamlit_app.py", label="→ Back to dashboard", icon="⚽")

st.divider()
with st.expander("📋 Where do I get the daily JSON?"):
    st.markdown(
        "Use the prompt template in **`docs/daily_context_prompt.md`** with ChatGPT each "
        "morning. It asks for the seven v1 criteria scores and the v2 strategic fields per "
        "match, in the exact JSON shape this page expects. See **`docs/data_schema.md`** "
        "for the full field reference."
    )
ui.disclaimer_footer()
