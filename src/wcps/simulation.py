"""Monte Carlo helpers shared by all models.

These functions turn arrays of simulated goals (optionally weighted, to support
v2's strategic re-weighting of draws) into the standardized summary objects:
outcome probabilities, scoreline distributions, quantile statistics and the
recommended scoreline.

Keeping this logic here means every model produces consistent, comparable
outputs and the math lives in one auditable place.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from .schemas import OUTCOME_AWAY, OUTCOME_DRAW, OUTCOME_HOME, StatSummary


def make_rng(base_seed: int, match_id: str) -> np.random.Generator:
    """Deterministic per-match RNG so runs are reproducible yet decorrelated."""
    offset = abs(hash(match_id)) % (10**6)
    return np.random.default_rng(base_seed + offset)


def weighted_quantile(
    values: np.ndarray, q: float, weights: np.ndarray | None = None
) -> float:
    """Weighted quantile (linear interpolation). ``q`` in [0, 1]."""
    values = np.asarray(values, dtype=float)
    if weights is None:
        return float(np.quantile(values, q))
    weights = np.asarray(weights, dtype=float)
    order = np.argsort(values)
    v, w = values[order], weights[order]
    cw = np.cumsum(w) - 0.5 * w
    cw /= np.sum(w)
    return float(np.interp(q, cw, v))


def stat_summary(
    values: np.ndarray,
    lower_q: float,
    upper_q: float,
    weights: np.ndarray | None = None,
) -> StatSummary:
    """Compute mean/median/quantiles for one simulated quantity."""
    values = np.asarray(values, dtype=float)
    if weights is None:
        mean = float(np.mean(values))
        median = float(np.median(values))
    else:
        w = np.asarray(weights, dtype=float)
        wsum = float(np.sum(w))
        mean = float(np.sum(values * w) / wsum)
        median = weighted_quantile(values, 0.5, w)
    return StatSummary(
        mean=mean,
        median=median,
        lower=weighted_quantile(values, lower_q, weights),
        upper=weighted_quantile(values, upper_q, weights),
        lower_q=lower_q,
        upper_q=upper_q,
    )


def summarize_simulation(
    goals_home: np.ndarray,
    goals_away: np.ndarray,
    lower_q: float,
    upper_q: float,
    weights: np.ndarray | None = None,
    top_n: int = 5,
    max_scoreline_goals: int = 8,
) -> dict[str, Any]:
    """Reduce raw simulation samples to standardized prediction components.

    Returns a dict with outcome probabilities, scoreline distribution, modal /
    recommended scores, top scorelines (overall and within the modal outcome),
    and per-quantity statistics. Supports optional sample weights so models can
    re-weight scenarios (e.g. v2's strategic draw value) without resampling.
    """
    gh = np.asarray(goals_home, dtype=int)
    ga = np.asarray(goals_away, dtype=int)
    n = gh.size
    w = np.ones(n) if weights is None else np.asarray(weights, dtype=float)
    wsum = float(np.sum(w))

    # --- outcome probabilities --------------------------------------------
    diff = gh - ga
    p_home = float(np.sum(w[diff > 0]) / wsum)
    p_away = float(np.sum(w[diff < 0]) / wsum)
    p_draw = float(np.sum(w[diff == 0]) / wsum)

    outcome_probs = {
        OUTCOME_HOME: p_home,
        OUTCOME_DRAW: p_draw,
        OUTCOME_AWAY: p_away,
    }
    recommended_outcome = max(outcome_probs, key=outcome_probs.get)

    # --- scoreline distribution (truncated for storage) -------------------
    scoreline_probs: dict[str, float] = {}
    cap = max_scoreline_goals
    ch = np.clip(gh, 0, cap)
    ca = np.clip(ga, 0, cap)
    for x in range(cap + 1):
        mx = ch == x
        if not mx.any():
            continue
        for y in range(cap + 1):
            mask = mx & (ca == y)
            if mask.any():
                p = float(np.sum(w[mask]) / wsum)
                if p > 0:
                    scoreline_probs[f"{x}-{y}"] = p

    # sorted scoreline list (overall)
    ordered = sorted(scoreline_probs.items(), key=lambda kv: kv[1], reverse=True)
    top_scorelines = [{"score": s, "prob": p} for s, p in ordered[:top_n]]
    modal_score = ordered[0][0] if ordered else "0-0"

    # top scorelines WITHIN the most likely outcome
    def in_outcome(score: str) -> bool:
        x, y = (int(v) for v in score.split("-"))
        if recommended_outcome == OUTCOME_HOME:
            return x > y
        if recommended_outcome == OUTCOME_AWAY:
            return x < y
        return x == y

    in_out = [(s, p) for s, p in ordered if in_outcome(s)]
    top_in_outcome = [{"score": s, "prob": p} for s, p in in_out[:top_n]]

    # --- recommended score (methodology §6: outcome + modal + coherence) ---
    recommended_score = _recommended_score(
        recommended_outcome, modal_score, in_out, outcome_probs
    )

    # --- per-quantity statistics ------------------------------------------
    total = gh + ga
    points_home = np.where(diff > 0, 3, np.where(diff == 0, 1, 0))
    points_away = np.where(diff < 0, 3, np.where(diff == 0, 1, 0))
    stats = {
        "goals_home": stat_summary(gh, lower_q, upper_q, w).to_dict(),
        "goals_away": stat_summary(ga, lower_q, upper_q, w).to_dict(),
        "total_goals": stat_summary(total, lower_q, upper_q, w).to_dict(),
        "goal_diff": stat_summary(diff, lower_q, upper_q, w).to_dict(),
        "points_home": stat_summary(points_home, lower_q, upper_q, w).to_dict(),
        "points_away": stat_summary(points_away, lower_q, upper_q, w).to_dict(),
    }

    # confidence = margin between top and second outcome probability
    sorted_probs = sorted(outcome_probs.values(), reverse=True)
    confidence = float(sorted_probs[0] - sorted_probs[1])

    return {
        "prob_home": p_home,
        "prob_draw": p_draw,
        "prob_away": p_away,
        "scoreline_probs": scoreline_probs,
        "recommended_outcome": recommended_outcome,
        "recommended_score": recommended_score,
        "modal_score": modal_score,
        "top_scorelines": top_scorelines,
        "top_scorelines_in_outcome": top_in_outcome,
        "stats": stats,
        "confidence": confidence,
    }


def _recommended_score(
    outcome: str,
    modal_score: str,
    in_outcome_sorted: list[tuple[str, float]],
    outcome_probs: dict[str, float],
) -> str:
    """Pick the recommended scoreline (methodology §6).

    Combine the most likely outcome, the modal scoreline and strategic
    coherence. If the modal score already agrees with the preferred outcome we
    keep it; otherwise we fall back to the most probable score *within* the
    preferred outcome, favouring a conservative low scoreline.
    """
    if not in_outcome_sorted:
        return modal_score

    mx, my = (int(v) for v in modal_score.split("-"))
    modal_outcome = (
        OUTCOME_HOME if mx > my else OUTCOME_AWAY if mx < my else OUTCOME_DRAW
    )
    if modal_outcome == outcome:
        return modal_score
    # modal disagrees with preferred outcome -> conservative pick within outcome
    return in_outcome_sorted[0][0]
