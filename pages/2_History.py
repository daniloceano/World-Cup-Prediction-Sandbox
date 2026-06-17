"""Historical performance page — model & ensemble evaluation vs actual results."""

from __future__ import annotations

import app.bootstrap  # noqa: F401  # isort:skip
import pandas as pd
import streamlit as st

from app import components as ui
from wcps import data_io, evaluation
from wcps.config import load_config

st.set_page_config(page_title="WCPS · History", page_icon="📊", layout="wide")
cfg = load_config()

st.title("📊 Historical performance")
st.caption(
    "Accuracy and probabilistic scores for each model and the ensemble, computed over "
    "matches that already have an actual result recorded."
)

rows = evaluation.build_history(cfg)
if not rows:
    st.info("No predictions stored yet. Generate predictions from the dashboard first.")
    st.stop()

evaluated = [r for r in rows if r.get("evaluated")]
pending = [r for r in rows if not r.get("evaluated")]

# --- summary metrics by source ---------------------------------------------
summary = evaluation.summarize_by_source(rows)
if summary:
    st.subheader("Summary by source")
    sdf = pd.DataFrame(summary).T
    sdf.index.name = "source"
    show = sdf.rename(columns={
        "n": "N",
        "outcome_accuracy": "Outcome acc.",
        "exact_score_accuracy": "Exact score acc.",
        "mean_brier": "Mean Brier ↓",
        "mean_log_loss": "Mean log loss ↓",
    })
    st.dataframe(
        show.style.format({
            "Outcome acc.": "{:.1%}", "Exact score acc.": "{:.1%}",
            "Mean Brier ↓": "{:.3f}", "Mean log loss ↓": "{:.3f}",
        }),
        use_container_width=True,
    )
    st.caption("↓ = lower is better. Brier and log loss use the outcome probabilities.")
else:
    st.info("No matches with actual results yet — add results to see metrics.")

# --- per-match evaluated detail --------------------------------------------
if evaluated:
    st.subheader("Evaluated matches")
    df = pd.DataFrame(evaluated)
    df["outcome_correct"] = df["outcome_correct"].map({True: "✅", False: "❌"})
    df["score_correct"] = df["score_correct"].map({True: "✅", False: "❌"})
    cols = ["date", "match_id", "source", "phase", "true_outcome", "pred_outcome",
            "outcome_correct", "true_score", "pred_score", "score_correct",
            "brier", "log_loss"]
    cols = [c for c in cols if c in df.columns]
    st.dataframe(
        df[cols].style.format({"brier": "{:.3f}", "log_loss": "{:.3f}"}),
        use_container_width=True, hide_index=True,
    )

if pending:
    st.subheader("Pending matches (no actual result yet)")
    pdf = pd.DataFrame(pending)[["date", "match_id", "source"]].drop_duplicates("match_id")
    st.dataframe(pdf, use_container_width=True, hide_index=True)

st.divider()
ui.disclaimer_footer()
