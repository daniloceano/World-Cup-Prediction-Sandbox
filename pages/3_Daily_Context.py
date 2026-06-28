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
    "Paste the JSON from **Prompt A** (`docs/prompt_a.txt`, today's matches) — or "
    "from the **round prompt** (`docs/prompt_a_round.txt`, every match of the round "
    "across several days). Validate it, then **Save & generate**: the context is "
    "split into per-date `data/context/YYYY-MM-DD.json` files, the fixtures are "
    "registered automatically, and predictions are generated for every date. "
    "Context files are preserved as an audit trail. For final scores use **Prompt B** "
    "on the History page."
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


def _save(ctx) -> list[str]:
    # Split into per-date context files (supports the round prompt's multiple
    # dates as well as a single day) and register the fixtures.
    written = data_io.save_context_by_date(ctx, default_date=date)
    st.success(f"Saved context for {len(written)} date(s): {', '.join(written)}.")
    n_teams, n_matches = data_io.sync_schedule_from_context(ctx)
    if n_matches or n_teams:
        st.info(f"Registered {n_matches} new fixture(s) and {n_teams} new team(s) "
                "into the schedule.")
    return written


if validate_clicked or save_clicked or gen_clicked:
    ctx, err = _parse(text)
    if err:
        st.error(err)
    else:
        ok = _show_validation(ctx)
        written = _save(ctx) if (save_clicked or gen_clicked) and ok else []
        if gen_clicked and ok:
            total = 0
            with st.spinner(f"Generating predictions for {len(written)} date(s)…"):
                for d in written:
                    payload = pipeline.generate_for_date(d)
                    total += payload["n_matches"]
            st.success(f"Generated predictions for {total} match(es) "
                       f"across {len(written)} date(s).")
            st.page_link("streamlit_app.py", label="→ Back to dashboard", icon="⚽")

st.divider()
with st.expander("📋 Where do I get the JSON?"):
    st.markdown(
        "- **Today only:** `docs/prompt_a.txt`\n"
        "- **Whole round (all matches, several days):** `docs/prompt_a_round.txt`\n\n"
        "Both ask ChatGPT for the seven v1 criteria scores and the v2 strategic fields "
        "per match, in the exact JSON shape this page expects (the round prompt just "
        "returns matches spanning multiple dates). See `docs/daily_context_prompt.md` "
        "and `docs/data_schema.md` for the full reference."
    )
ui.disclaimer_footer()
