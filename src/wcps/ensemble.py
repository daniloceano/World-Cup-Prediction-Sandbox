"""Ensemble layer — combine all active models into one prediction.

The ensemble consumes a list of standardized :class:`Prediction` objects and
emits another :class:`Prediction` (``model_id="ensemble"``) using the same
schema, so the UI treats it like any other model.

Supported strategies (config ``ensemble.strategy``):
* ``equal``    — simple average of active models (default);
* ``weighted`` — explicit per-model weights from config.

Future strategies (``performance``, ``phase_weighted``, ``matchup_weighted``)
are recognised and currently fall back to weighted/equal behaviour. The
combination math is isolated in :func:`combine` so swapping the weighting policy
later is a one-function change.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import numpy as np

from .schemas import OUTCOMES, Prediction
from .simulation import stat_summary

ENSEMBLE_ID = "ensemble"
ENSEMBLE_VERSION = "1.0.0"


def resolve_weights(
    predictions: list[Prediction], config: dict[str, Any]
) -> dict[str, float]:
    """Return normalized per-model weights according to the configured strategy."""
    ens = config.get("ensemble", {})
    strategy = ens.get("strategy", "equal")
    ids = [p.model_id for p in predictions]

    if strategy == "weighted":
        raw = ens.get("weights", {})
        weights = {mid: float(raw.get(mid, 1.0)) for mid in ids}
    else:
        # equal (and, for now, the not-yet-implemented adaptive strategies)
        weights = {mid: 1.0 for mid in ids}

    total = sum(weights.values()) or 1.0
    return {mid: w / total for mid, w in weights.items()}


def combine(
    predictions: list[Prediction],
    config: dict[str, Any],
    match_id: str,
    context_ref: str | None = None,
) -> Prediction:
    """Combine individual model predictions into an ensemble prediction."""
    if not predictions:
        raise ValueError("Cannot build an ensemble from zero predictions.")

    q = config["quantiles"]
    weights = resolve_weights(predictions, config)
    top_n = config["display"]["top_scorelines_n"]

    # --- outcome probabilities: weighted average ---------------------------
    probs = {o: 0.0 for o in OUTCOMES}
    for p in predictions:
        w = weights[p.model_id]
        probs["home"] += w * p.prob_home
        probs["draw"] += w * p.prob_draw
        probs["away"] += w * p.prob_away
    s = sum(probs.values()) or 1.0
    probs = {k: v / s for k, v in probs.items()}

    recommended_outcome = max(probs, key=probs.get)

    # --- scoreline distribution: weighted mixture --------------------------
    scoreline: dict[str, float] = {}
    for p in predictions:
        w = weights[p.model_id]
        for score, prob in p.scoreline_probs.items():
            scoreline[score] = scoreline.get(score, 0.0) + w * prob
    tot = sum(scoreline.values()) or 1.0
    scoreline = {k: v / tot for k, v in scoreline.items()}

    ordered = sorted(scoreline.items(), key=lambda kv: kv[1], reverse=True)
    top_scorelines = [{"score": sc, "prob": pr} for sc, pr in ordered[:top_n]]
    modal_score = ordered[0][0] if ordered else "0-0"

    def in_outcome(score: str) -> bool:
        x, y = (int(v) for v in score.split("-"))
        if recommended_outcome == "home":
            return x > y
        if recommended_outcome == "away":
            return x < y
        return x == y

    in_out = [(sc, pr) for sc, pr in ordered if in_outcome(sc)]
    top_in_outcome = [{"score": sc, "prob": pr} for sc, pr in in_out[:top_n]]

    # recommended score: modal if it matches outcome, else conservative pick
    recommended_score = modal_score
    if in_out:
        mx, my = (int(v) for v in modal_score.split("-"))
        modal_out = "home" if mx > my else "away" if mx < my else "draw"
        if modal_out != recommended_outcome:
            recommended_score = in_out[0][0]

    # --- summary statistics: reconstruct from scoreline mixture ------------
    stats = _stats_from_scoreline(scoreline, q["lower"], q["upper"])

    sorted_probs = sorted(probs.values(), reverse=True)
    confidence = float(sorted_probs[0] - sorted_probs[1])

    quality = "ok"
    warnings: list[str] = []
    if any(p.quality == "missing_context" for p in predictions):
        quality = "missing_context"
        warnings.append("At least one member model ran without daily context.")
    elif any(p.quality == "degraded" for p in predictions):
        quality = "degraded"

    lam_home = sum(weights[p.model_id] * p.lambda_home for p in predictions)
    lam_away = sum(weights[p.model_id] * p.lambda_away for p in predictions)

    return Prediction(
        model_id=ENSEMBLE_ID,
        model_version=ENSEMBLE_VERSION,
        match_id=match_id,
        run_datetime=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        context_ref=context_ref,
        prob_home=probs["home"],
        prob_draw=probs["draw"],
        prob_away=probs["away"],
        scoreline_probs=scoreline,
        recommended_outcome=recommended_outcome,
        recommended_score=recommended_score,
        modal_score=modal_score,
        top_scorelines=top_scorelines,
        top_scorelines_in_outcome=top_in_outcome,
        stats=stats,
        lambda_home=lam_home,
        lambda_away=lam_away,
        confidence=confidence,
        quality=quality,
        warnings=warnings,
    )


def _stats_from_scoreline(
    scoreline: dict[str, float], lower_q: float, upper_q: float
) -> dict[str, dict[str, float]]:
    """Reconstruct quantile statistics by sampling the mixed scoreline distribution."""
    if not scoreline:
        return {}
    scores = list(scoreline.keys())
    probs = np.array([scoreline[s] for s in scores], dtype=float)
    probs /= probs.sum()
    gh = np.array([int(s.split("-")[0]) for s in scores])
    ga = np.array([int(s.split("-")[1]) for s in scores])

    # deterministic large multinomial expansion for stable quantiles
    n = 20000
    rng = np.random.default_rng(0)
    idx = rng.choice(len(scores), size=n, p=probs)
    sh, sa = gh[idx], ga[idx]
    total = sh + sa
    diff = sh - sa
    pts_h = np.where(diff > 0, 3, np.where(diff == 0, 1, 0))
    pts_a = np.where(diff < 0, 3, np.where(diff == 0, 1, 0))
    return {
        "goals_home": stat_summary(sh, lower_q, upper_q).to_dict(),
        "goals_away": stat_summary(sa, lower_q, upper_q).to_dict(),
        "total_goals": stat_summary(total, lower_q, upper_q).to_dict(),
        "goal_diff": stat_summary(diff, lower_q, upper_q).to_dict(),
        "points_home": stat_summary(pts_h, lower_q, upper_q).to_dict(),
        "points_away": stat_summary(pts_a, lower_q, upper_q).to_dict(),
    }
