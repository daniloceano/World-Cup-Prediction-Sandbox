"""Model v2 — v1 strength engine + strategic World Cup adjustments.

Implements the methodology of §4 of the methods document. v2 keeps v1's
relative-strength → expected-goals core, then layers a strategic state-mixture
on top:

* a likely *game plan* (low-block compression of the favourite, §4.3);
* a *first-goal* state split S0 / S_A / S_B (§4.4–§4.5);
* a *space / collapse* boost for the favourite once it scores first (§4.5–§4.6);
* a *draw value* re-weighting of drawn scorelines (§4.2).

The first-goal split is simulated explicitly: each Monte Carlo trial first draws
which state occurs, then samples goals under that state's adjusted intensities.
Drawn scorelines are then importance-weighted by the strategic value of the
draw, mirroring ``P(draw)* = P(draw) + Δ_E``.

All factor → context mappings are documented inline and in
``docs/data_schema.md`` so the strategic layer stays auditable.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from ..schemas import Prediction
from ..simulation import make_rng, summarize_simulation
from .base import REGISTRY, BaseModel
from .model_v1 import base_lambdas, relative_strength


def _strategic(context: dict[str, Any] | None) -> dict[str, Any]:
    """Extract the v2 strategic block with neutral defaults for missing fields."""
    s = (context or {}).get("v2_strategic", {}) or {}
    fg = s.get("first_goal_prob") or {}
    ntw = s.get("need_to_win") or {}
    return {
        "favorite": s.get("favorite"),                      # "home"|"away"|None
        "low_block_capacity": float(s.get("low_block_capacity", 0.0) or 0.0),  # B_D
        "draw_value_weaker": float(s.get("draw_value_weaker", 0.0) or 0.0),    # V_E
        "collapse_risk_weaker": float(s.get("collapse_risk_weaker", 0.0) or 0.0),  # C_g
        "is_group_debut": bool(s.get("is_group_debut", False)),
        "transition_threat_weaker": float(s.get("transition_threat_weaker", 0.0) or 0.0),
        "set_piece_threat_weaker": float(s.get("set_piece_threat_weaker", 0.0) or 0.0),
        "need_to_win": {
            "home": float(ntw.get("home", 0.0) or 0.0),
            "away": float(ntw.get("away", 0.0) or 0.0),
        },
        "first_goal_prob": {
            "home": fg.get("home"),
            "away": fg.get("away"),
            "none": fg.get("none"),
        },
        "_has_block": "v2_strategic" in (context or {}),
    }


@REGISTRY.register
class ModelV2(BaseModel):
    model_id = "v2"
    model_version = "1.0.0"
    display_name = "v2 · Strategic (World Cup)"
    description = (
        "v1 strength core + strategic layer: low-block plan, first-goal state "
        "mixture, post-goal space/collapse, and draw value re-weighting."
    )
    required_inputs = ("v1_scores", "v2_strategic")

    def predict(
        self,
        match: dict[str, Any],
        context: dict[str, Any] | None,
        context_ref: str | None = None,
    ) -> Prediction:
        cfg = self.config["model_v2"]
        v1_cfg = self.config["model_v1"]
        sim_cfg = self.config["simulation"]
        q = self.config["quantiles"]

        warnings: list[str] = []
        quality = "ok"

        # --- v1 strength core ---------------------------------------------
        from ..context import V1_CRITERIA, coerce_v1_scores

        if context is None:
            warnings.append("No daily context; v2 falls back to a neutral toss-up.")
            quality = "missing_context"
            scores = {c: {"home": 0.0, "away": 0.0} for c in V1_CRITERIA}
        else:
            scores = coerce_v1_scores(context)

        d = relative_strength(scores, v1_cfg["weights"])
        lam_home, lam_away = base_lambdas(d, v1_cfg)

        strat = _strategic(context)
        if not strat["_has_block"]:
            warnings.append("Missing 'v2_strategic'; strategic layer is neutral.")
            if quality == "ok":
                quality = "degraded"

        # --- identify favourite / underdog --------------------------------
        favorite = strat["favorite"]
        if favorite not in ("home", "away"):
            favorite = "home" if d >= 0 else "away"
        fav_is_home = favorite == "home"

        lam_fav = lam_home if fav_is_home else lam_away
        lam_und = lam_away if fav_is_home else lam_home

        # --- initial-state factors (§4.3, §4.7) ---------------------------
        bd = strat["low_block_capacity"]
        f_bloco = 1.0 - cfg["low_block_max_compression"] * bd           # compress favourite
        f_estreia = cfg["debut_factor"] if strat["is_group_debut"] else 1.0
        f_transition = 1.0 + 0.30 * strat["transition_threat_weaker"]   # underdog counters
        f_setpiece = 1.0 + 0.20 * strat["set_piece_threat_weaker"]

        lam_fav0 = max(0.05, lam_fav * f_bloco * f_estreia)
        lam_und0 = max(0.05, lam_und * f_transition * f_setpiece)

        # --- post-first-goal factors (§4.5, §4.6) -------------------------
        collapse = strat["collapse_risk_weaker"]
        # favourite finds space once the block opens; collapse amplifies it.
        f_space = 1.0 + cfg["space_boost_max"] * bd + cfg["collapse_boost_max"] * collapse
        f_chase = 1.0 + cfg["chase_boost_max"]    # team trailing pushes & gets stretched

        # --- first-goal state probabilities (§4.4) ------------------------
        p_fav, p_und, p_none = self._first_goal_probs(
            strat, fav_is_home, lam_fav0, lam_und0, bd
        )

        # --- Monte Carlo state mixture ------------------------------------
        rng = make_rng(sim_cfg["random_seed"], match["match_id"] + "v2")
        n = sim_cfg["n_simulations"]
        cap = sim_cfg["max_goals"]

        state = rng.choice(3, size=n, p=[p_none, p_fav, p_und])  # 0:none 1:fav 2:und
        g_fav = np.zeros(n, dtype=int)
        g_und = np.zeros(n, dtype=int)

        # S0 — no early goal: cagey, low-scoring (favours draws / 1-0)
        m0 = state == 0
        comp = cfg["cagey_draw_compression"]
        g_fav[m0] = rng.poisson(lam_fav0 * comp, m0.sum())
        g_und[m0] = rng.poisson(lam_und0 * comp, m0.sum())

        # S_fav — favourite scores first: +1 guaranteed, then space/collapse boost
        mF = state == 1
        g_fav[mF] = 1 + rng.poisson(lam_fav0 * f_space, mF.sum())
        g_und[mF] = rng.poisson(lam_und0 * f_chase, mF.sum())

        # S_und — underdog scores first (rare): they hold +1, favourite chases
        mU = state == 2
        g_und[mU] = 1 + rng.poisson(lam_und0, mU.sum())
        g_fav[mU] = rng.poisson(lam_fav0 * f_chase, mU.sum())

        g_fav = np.clip(g_fav, 0, cap)
        g_und = np.clip(g_und, 0, cap)

        # map favourite/underdog back to home/away
        gh, ga = (g_fav, g_und) if fav_is_home else (g_und, g_fav)

        # --- draw-value importance weights (§4.2) -------------------------
        # Scale drawn samples so the weighted draw probability rises by ~Δ_E,
        # i.e. P(draw)* ≈ P(draw) + Δ_E, leaving the win mass proportionally
        # reduced. Numerically stable and exactly recoverable in summaries.
        delta_e = cfg["draw_value_max_weight"] * strat["draw_value_weaker"]
        weights = np.ones(n)
        if delta_e > 0:
            draws = gh == ga
            p_draw_raw = draws.mean()
            if p_draw_raw > 0:
                weights[draws] = 1.0 + delta_e / p_draw_raw

        summary = summarize_simulation(
            gh, ga, q["lower"], q["upper"],
            weights=weights,
            top_n=self.config["display"]["top_scorelines_n"],
        )

        lam_home_eff = lam_fav0 if fav_is_home else lam_und0
        lam_away_eff = lam_und0 if fav_is_home else lam_fav0

        return Prediction(
            **self._base_prediction_kwargs(match, context_ref),
            lambda_home=lam_home_eff,
            lambda_away=lam_away_eff,
            quality=quality,
            warnings=warnings,
            **summary,
        )

    @staticmethod
    def _first_goal_probs(
        strat: dict[str, Any],
        fav_is_home: bool,
        lam_fav0: float,
        lam_und0: float,
        low_block: float,
    ) -> tuple[float, float, float]:
        """Return (p_fav_first, p_und_first, p_none).

        Uses explicit context values when present; otherwise derives them from
        the adjusted intensities, with a low-block boost to the 'no early goal'
        mass (a disciplined block keeps the score 0-0 longer, §4.4).
        """
        fg = strat["first_goal_prob"]
        home_v, away_v, none_v = fg["home"], fg["away"], fg["none"]
        if None not in (home_v, away_v, none_v):
            p_home, p_away, p_none = float(home_v), float(away_v), float(none_v)
            p_fav = p_home if fav_is_home else p_away
            p_und = p_away if fav_is_home else p_home
        else:
            p_none = float(np.clip(0.12 + 0.30 * low_block, 0.05, 0.55))
            remaining = 1.0 - p_none
            total = lam_fav0 + lam_und0
            share_fav = lam_fav0 / total if total > 0 else 0.5
            p_fav = remaining * share_fav
            p_und = remaining * (1.0 - share_fav)

        s = p_fav + p_und + p_none
        if s <= 0:
            return 0.34, 0.33, 0.33
        return p_fav / s, p_und / s, p_none / s
