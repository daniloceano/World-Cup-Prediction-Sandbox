"""Model standard (formerly v1) — static relative strength + Poisson + Monte Carlo.

Implements §1–§2 / §3 of the methods documents:

1. Normalize the seven heuristic criteria weights.
2. Compute the aggregate relative strength ``D = Σ w̃_i (S_A,i − S_B,i)``.
3. Convert to expected goals ``λ_A = λ0 + αD``, ``λ_B = λ0 − αD`` (clipped).
4. Simulate goals as independent Poisson variables.
5. Monte Carlo to estimate outcome and scoreline probabilities.

This is the central / neutral regime. The conservative and aggressive models
reuse its strength engine (:func:`relative_strength`, :func:`base_lambdas`).
"""

from __future__ import annotations

from typing import Any

import numpy as np

from ..context import V1_CRITERIA, coerce_v1_scores
from ..schemas import Prediction
from ..simulation import make_rng, summarize_simulation
from .base import REGISTRY, BaseModel


def normalized_weights(weights: dict[str, float]) -> dict[str, float]:
    """Normalize raw heuristic weights so they sum to 1 (methodology eq. 1)."""
    total = sum(weights.values())
    if total <= 0:
        n = len(weights) or 1
        return {k: 1.0 / n for k in weights}
    return {k: v / total for k, v in weights.items()}


def relative_strength(
    scores: dict[str, dict[str, float]], weights: dict[str, float]
) -> float:
    """Aggregate weighted strength difference D (positive favours home/Team A)."""
    wn = normalized_weights(weights)
    d = 0.0
    for crit in V1_CRITERIA:
        s = scores.get(crit, {"home": 0.0, "away": 0.0})
        d += wn.get(crit, 0.0) * (s["home"] - s["away"])
    return d


def base_lambdas(d: float, cfg: dict[str, Any]) -> tuple[float, float]:
    """Convert relative strength D into clipped expected goals for both teams."""
    lam0 = cfg["lambda_0"]
    alpha = cfg["alpha"]
    lo, hi = cfg["lambda_min"], cfg["lambda_max"]
    lam_home = float(np.clip(lam0 + alpha * d, lo, hi))
    lam_away = float(np.clip(lam0 - alpha * d, lo, hi))
    return lam_home, lam_away


@REGISTRY.register
class ModelStandard(BaseModel):
    model_id = "standard"
    model_version = "1.0.0"
    display_name = "Standard · Static relative strength"
    description = (
        "Weighted multi-criteria strength → expected goals → independent "
        "Poisson goals → Monte Carlo. The neutral / central regime."
    )
    required_inputs = ("v1_scores",)

    def predict(
        self,
        match: dict[str, Any],
        context: dict[str, Any] | None,
        context_ref: str | None = None,
    ) -> Prediction:
        cfg = self.config["model_standard"]
        sim_cfg = self.config["simulation"]
        q = self.config["quantiles"]

        warnings: list[str] = []
        quality = "ok"
        if context is None:
            warnings.append("No daily context for this match; using neutral scores.")
            quality = "missing_context"
            scores = {c: {"home": 0.0, "away": 0.0} for c in V1_CRITERIA}
        else:
            scores = coerce_v1_scores(context)

        d = relative_strength(scores, cfg["weights"])
        lam_home, lam_away = base_lambdas(d, cfg)

        rng = make_rng(sim_cfg["random_seed"], match["match_id"] + "standard")
        n = sim_cfg["n_simulations"]
        cap = sim_cfg["max_goals"]
        gh = np.clip(rng.poisson(lam_home, n), 0, cap)
        ga = np.clip(rng.poisson(lam_away, n), 0, cap)

        summary = summarize_simulation(
            gh, ga, q["lower"], q["upper"],
            top_n=self.config["display"]["top_scorelines_n"],
        )

        return Prediction(
            **self._base_prediction_kwargs(match, context_ref),
            lambda_home=lam_home,
            lambda_away=lam_away,
            quality=quality,
            warnings=warnings,
            **summary,
        )
