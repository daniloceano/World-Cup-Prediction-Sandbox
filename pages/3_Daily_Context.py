"""Daily context page — paste the JSON, the date(s) are auto-detected.

Paste the output of Prompt A (today) or the round prompt (whole round). The
page reads the slate date(s) straight from the JSON — you never type a date —
splits the context into per-date files, registers fixtures and generates
predictions for every date.
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
    "Paste the JSON from **Prompt A** (`docs/prompt_a.txt`, today) or the **round "
    "prompt** (`docs/prompt_a_round.txt`, every match of the round). The **date(s) "
    "are detected automatically from the JSON** — no need to type anything. On "
    "**Save & generate**, the context is split into per-date "
    "`data/context/YYYY-MM-DD.json` files, fixtures are registered, and predictions "
    "are generated for every date. For final scores use **Prompt B** on History."
)

text = st.text_area(
    "Context JSON (Prompt A or round prompt)", height=380,
    placeholder='{ "date": "YYYY-MM-DD", "matches": [ ... ] }   '
                'or a round JSON spanning several dates',
)

with st.expander("⚙️ Options (rarely needed)"):
    fallback_date = st.text_input(
        "Fallback date (only used for matches that have no 'date' in the JSON)",
        value="", placeholder="YYYY-MM-DD",
    ).strip() or None

c1, c2, c3 = st.columns(3)
validate_clicked = c1.button("✅ Validate", use_container_width=True)
save_clicked = c2.button("💾 Save", use_container_width=True)
gen_clicked = c3.button("⚙️ Save & generate", use_container_width=True, type="primary")


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


if validate_clicked or save_clicked or gen_clicked:
    ctx, err = _parse(text)
    if err:
        st.error(err)
    else:
        ok = _show_validation(ctx)
        groups = data_io.split_context_by_date(ctx, default_date=fallback_date)
        detected = sorted(groups)

        if detected:
            counts = ", ".join(f"{d} ({len(groups[d])})" for d in detected)
            st.info(f"📅 Detected {len(detected)} date(s) — matches per date: {counts}")
        else:
            st.error("No date found in the JSON. Make sure each match has a `date`, "
                     "or set a fallback date under Options.")

        if (save_clicked or gen_clicked) and ok and detected:
            written = data_io.save_context_by_date(ctx, default_date=fallback_date)
            st.success(f"Saved context for {len(written)} date(s): {', '.join(written)}.")
            n_teams, n_matches = data_io.sync_schedule_from_context(ctx)
            if n_matches or n_teams:
                st.info(f"Registered {n_matches} new fixture(s) and {n_teams} new "
                        "team(s) into the schedule.")
            if gen_clicked:
                total = 0
                with st.spinner(f"Generating predictions for {len(written)} date(s)…"):
                    for d in written:
                        total += pipeline.generate_for_date(d)["n_matches"]
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
        "returns matches spanning multiple dates). The date is read from the JSON "
        "automatically. See `docs/daily_context_prompt.md` and `docs/data_schema.md`."
    )
ui.disclaimer_footer()
