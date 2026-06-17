"""Historical evaluation metrics.

Compares stored predictions against actual results and computes simple,
numerically safe metrics per model and for the ensemble:

* outcome accuracy;
* exact-score accuracy;
* Brier score (multiclass) for outcome probabilities;
* log loss (clipped) for outcome probabilities.

The output is structured so it can also feed calibration plots later.
"""

from __future__ import annotations

import math
from typing import Any

from . import data_io
from .schemas import OUTCOME_AWAY, OUTCOME_DRAW, OUTCOME_HOME

_EPS = 1e-12


def actual_outcome(home_goals: int, away_goals: int) -> str:
    if home_goals > away_goals:
        return OUTCOME_HOME
    if home_goals < away_goals:
        return OUTCOME_AWAY
    return OUTCOME_DRAW


def _safe_log(p: float) -> float:
    return math.log(min(1.0, max(_EPS, p)))


def evaluate_prediction(pred: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
    """Per-prediction metrics against one actual result."""
    hg, ag = actual["home_goals"], actual["away_goals"]
    true_outcome = actual_outcome(hg, ag)
    true_score = f"{hg}-{ag}"

    probs = {
        OUTCOME_HOME: pred["prob_home"],
        OUTCOME_DRAW: pred["prob_draw"],
        OUTCOME_AWAY: pred["prob_away"],
    }
    pred_outcome = pred["recommended_outcome"]
    pred_score = pred["recommended_score"]

    # Brier (multiclass): sum over classes of (p - y)^2
    brier = sum(
        (probs[o] - (1.0 if o == true_outcome else 0.0)) ** 2
        for o in (OUTCOME_HOME, OUTCOME_DRAW, OUTCOME_AWAY)
    )
    logloss = -_safe_log(probs[true_outcome])

    return {
        "true_outcome": true_outcome,
        "true_score": true_score,
        "pred_outcome": pred_outcome,
        "pred_score": pred_score,
        "outcome_correct": bool(pred_outcome == true_outcome),
        "score_correct": bool(pred_score == true_score),
        "brier": brier,
        "log_loss": logloss,
        "prob_assigned_true": probs[true_outcome],
    }


def build_history(config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Join every stored prediction with its actual result (if available).

    Returns a flat list of rows, one per (match, source) where source is each
    model id and ``ensemble``. Rows without an actual result are still returned
    (with ``evaluated=False``) so the UI can show pending matches.
    """
    actuals = data_io.load_actual_results()
    rows: list[dict[str, Any]] = []

    for date in data_io.available_dates():
        payload = data_io.load_predictions(date)
        if not payload:
            continue
        for match_id, mp in payload.get("predictions", {}).items():
            match = data_io.get_match(match_id) or {}
            actual = actuals.get(match_id)
            sources = dict(mp.get("models", {}))
            sources["ensemble"] = mp.get("ensemble", {})
            for source, pred in sources.items():
                if not pred:
                    continue
                row = {
                    "date": date,
                    "match_id": match_id,
                    "home_team": match.get("home_team"),
                    "away_team": match.get("away_team"),
                    "phase": match.get("phase"),
                    "source": source,
                    "is_demo": match.get("is_demo", False),
                    "evaluated": actual is not None,
                }
                if actual is not None:
                    row.update(evaluate_prediction(pred, actual))
                rows.append(row)
    return rows


def summarize_by_source(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Aggregate metrics per source (model id / ensemble) over evaluated rows."""
    summary: dict[str, dict[str, Any]] = {}
    by_source: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        if r.get("evaluated"):
            by_source.setdefault(r["source"], []).append(r)

    for source, items in by_source.items():
        n = len(items)
        if n == 0:
            continue
        summary[source] = {
            "n": n,
            "outcome_accuracy": sum(i["outcome_correct"] for i in items) / n,
            "exact_score_accuracy": sum(i["score_correct"] for i in items) / n,
            "mean_brier": sum(i["brier"] for i in items) / n,
            "mean_log_loss": sum(i["log_loss"] for i in items) / n,
        }
    return summary
