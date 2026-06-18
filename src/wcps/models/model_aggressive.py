"""Model aggressive (new) — amplified favourite + accumulated pressure + goleada tail.

Implements ``docs/materiais_metodos_modelo_agressivo_wcps.md``. Starts from the
standard relative-strength core, then represents the "favourite scores early and
turns superiority into a rout" regime:

* the favourite's expected goals are amplified by an offensive-superiority
  factor ``F_sup = 1 + β·A_F`` (§6.1, §7);
* a three-state mixture S0 / S_F (favourite scores, keeps pressing) / S_C
  (underdog collapses) (§5.2), with the favourite getting a pressure boost
  ``F_pressao`` and, in the collapse state, an extra ``F_colapso`` while the
  underdog opens up (``F_risco``) (§6.4–§6.5, §7);
* a *goleada tail*: scorelines with margin ``M = G_F − G_U ≥ 3`` are
  importance-weighted by ``(1 + γ·T_G)`` and the distribution renormalised
  (§6.6).

The six aggressive variables (A_F, D_U, G_E, I_P, E_U, T_G) are read from an
optional ``aggressive`` block in the daily context when present, otherwise
derived from the existing ``v1_scores`` / ``v2_strategic`` so the model runs with
today's daily-context format. Mappings are documented inline and in
``docs/data_schema.md``.

Extra outputs (§10): ``P(M ≥ 2)`` (wide win) and ``P(M ≥ 3)`` (blowout) plus the
goleada-tail index are reported in ``Prediction.metrics``.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from ..schemas import Prediction
from ..simulation import make_rng, summarize_simulation
from .base import REGISTRY, BaseModel
from .model_standard import base_lambdas, relative_strength


def _clip01(x: float) -> float:
    return float(min(1.0, max(0.0, x)))


def _aggressive_params(
    context: dict[str, Any] | None, d: float, fav_is_home: bool
) -> dict[str, Any]:
    """Resolve the six aggressive variables from context (explicit or derived).

    Explicit values live in an optional ``aggressive`` block; missing ones are
    derived from the standard strength gap and the ``v2_strategic`` block so the
    model works with the current daily-context format.
    """
    agg = (context or {}).get("aggressive", {}) or {}
    strat = (context or {}).get("v2_strategic", {}) or {}
    fg = strat.get("first_goal_prob") or {}

    # A_F — offensive superiority of the favourite, from the strength gap.
    a_f = agg.get("offensive_superiority")
    if a_f is None:
        a_f = _clip01(abs(d) * 1.8)

    # D_U — underdog defensive fragility = inverse of low-block capacity.
    d_u = agg.get("underdog_fragility")
    if d_u is None:
        d_u = _clip01(1.0 - float(strat.get("low_block_capacity", 0.0) or 0.0))

    # G_E — probability the favourite scores early.
    g_e = agg.get("early_goal_prob")
    if g_e is None:
        fav_first = fg.get("home") if fav_is_home else fg.get("away")
        g_e = float(fav_first) if fav_first is not None else None

    # I_P — post-goal intensity (favourite keeps attacking).
    i_p = agg.get("post_goal_intensity")
    if i_p is None:
        nv = (strat.get("need_to_win") or {})
        fav_need = nv.get("home") if fav_is_home else nv.get("away")
        i_p = _clip01(0.5 + 0.5 * float(fav_need)) if fav_need is not None else 0.6

    # E_U — underdog exposure / collapse risk after conceding.
    e_u = agg.get("underdog_exposure")
    if e_u is None:
        e_u = _clip01(float(strat.get("collapse_risk_weaker", 0.0) or 0.0))

    # T_G — goleada tail index, from the technical asymmetry.
    t_g = agg.get("goleada_tail")
    if t_g is None:
        t_g = _clip01(0.5 * a_f + 0.5 * d_u)

    return {
        "A_F": _clip01(a_f), "D_U": _clip01(d_u), "G_E": g_e,
        "I_P": _clip01(i_p), "E_U": _clip01(e_u), "T_G": _clip01(t_g),
        "low_block_capacity": float(strat.get("low_block_capacity", 0.0) or 0.0),
        "_has_strat": "v2_strategic" in (context or {}),
    }


@REGISTRY.register
class ModelAggressive(BaseModel):
    model_id = "aggressive"
    model_version = "1.0.0"
    display_name = "Aggressive · Amplified favourite"
    description = (
        "Standard core + favourite amplification, accumulated pressure after an "
        "early goal, and a goleada tail that lifts blowout scorelines (2-0, 3-0, "
        "3-1, 4-0). The 'favourite turns superiority into a rout' regime."
    )
    required_inputs = ("v1_scores",)

    def predict(
        self,
        match: dict[str, Any],
        context: dict[str, Any] | None,
        context_ref: str | None = None,
    ) -> Prediction:
        cfg = self.config["model_aggressive"]
        std_cfg = self.config["model_standard"]
        sim_cfg = self.config["simulation"]
        q = self.config["quantiles"]

        warnings: list[str] = []
        quality = "ok"

        from ..context import V1_CRITERIA, coerce_v1_scores

        if context is None:
            warnings.append("No daily context; aggressive falls back to a neutral toss-up.")
            quality = "missing_context"
            scores = {c: {"home": 0.0, "away": 0.0} for c in V1_CRITERIA}
        else:
            scores = coerce_v1_scores(context)

        d = relative_strength(scores, std_cfg["weights"])
        lam_home, lam_away = base_lambdas(d, std_cfg)

        # --- favourite / underdog -----------------------------------------
        favorite = ((context or {}).get("v2_strategic", {}) or {}).get("favorite")
        if favorite not in ("home", "away"):
            favorite = "home" if d >= 0 else "away"
        fav_is_home = favorite == "home"
        lam_fav = lam_home if fav_is_home else lam_away
        lam_und = lam_away if fav_is_home else lam_home

        ap = _aggressive_params(context, d, fav_is_home)
        if not ap["_has_strat"]:
            warnings.append("No 'v2_strategic'/'aggressive' block; parameters derived from strength only.")
            if quality == "ok":
                quality = "degraded"

        # --- amplified favourite + factors (§6, §7) -----------------------
        f_sup = 1.0 + cfg["beta"] * ap["A_F"]                       # F_sup
        f_pressure = 1.0 + cfg["pressure_boost_max"] * ap["I_P"]    # F_pressao
        f_collapse = 1.0 + cfg["collapse_boost_max"] * ap["E_U"]    # F_colapso
        f_bloco = 1.0 - cfg["block_compression"] * ap["low_block_capacity"]
        f_risco = 1.0 + cfg["chase_boost_max"]                      # underdog opens up

        lam_fav_aggr = max(0.05, lam_fav * f_sup)
        lam_und0 = max(0.05, lam_und * f_bloco)

        # --- early-goal state probabilities (§6.3, §5.2) ------------------
        g_e = ap["G_E"]
        if g_e is None:
            # derive from amplified intensities + base early-goal rate
            base = cfg["early_goal_base"]
            g_e = _clip01(base + 0.4 * ap["A_F"])
        p_fav_early = _clip01(g_e)
        p_collapse = p_fav_early * ap["E_U"]      # S_C
        p_fav = p_fav_early - p_collapse          # S_F
        p_none = max(0.0, 1.0 - p_fav_early)      # S0
        probs = np.array([p_none, p_fav, p_collapse], dtype=float)
        probs = probs / probs.sum()

        # --- Monte Carlo state mixture ------------------------------------
        rng = make_rng(sim_cfg["random_seed"], match["match_id"] + "aggressive")
        n = sim_cfg["n_simulations"]
        cap = sim_cfg["max_goals"]
        state = rng.choice(3, size=n, p=probs)    # 0:none 1:fav 2:collapse
        g_fav = np.zeros(n, dtype=int)
        g_und = np.zeros(n, dtype=int)

        # S0 — no early goal: favourite already amplified, underdog compressed
        m0 = state == 0
        g_fav[m0] = rng.poisson(lam_fav_aggr, m0.sum())
        g_und[m0] = rng.poisson(lam_und0, m0.sum())

        # S_F — favourite scores first and keeps pressing (+1, then F_pressao)
        mF = state == 1
        g_fav[mF] = 1 + rng.poisson(lam_fav_aggr * f_pressure, mF.sum())
        g_und[mF] = rng.poisson(lam_und0, mF.sum())

        # S_C — underdog collapses: favourite gets F_pressao·F_colapso, und opens up
        mC = state == 2
        g_fav[mC] = 1 + rng.poisson(lam_fav_aggr * f_pressure * f_collapse, mC.sum())
        g_und[mC] = rng.poisson(lam_und * f_risco, mC.sum())

        g_fav = np.clip(g_fav, 0, cap)
        g_und = np.clip(g_und, 0, cap)

        # --- goleada-tail re-weighting (§6.6): P(M>=3) *= (1 + γ·T_G) ------
        margin = g_fav - g_und
        weights = np.ones(n)
        gamma_tg = cfg["goleada_gamma"] * ap["T_G"]
        if gamma_tg > 0:
            weights[margin >= 3] = 1.0 + gamma_tg

        # map favourite/underdog back to home/away
        gh, ga = (g_fav, g_und) if fav_is_home else (g_und, g_fav)

        summary = summarize_simulation(
            gh, ga, q["lower"], q["upper"],
            weights=weights,
            top_n=self.config["display"]["top_scorelines_n"],
        )

        # --- extra metrics (§10): wide-win / blowout probabilities ---------
        wsum = float(weights.sum())
        p_margin_ge2 = float(weights[margin >= 2].sum() / wsum)
        p_margin_ge3 = float(weights[margin >= 3].sum() / wsum)
        metrics = {
            "p_favourite_win_by_2plus": p_margin_ge2,
            "p_favourite_win_by_3plus": p_margin_ge3,
            "goleada_tail_index": ap["T_G"],
            "offensive_superiority": ap["A_F"],
        }

        lam_home_eff = lam_fav_aggr if fav_is_home else lam_und0
        lam_away_eff = lam_und0 if fav_is_home else lam_fav_aggr

        return Prediction(
            **self._base_prediction_kwargs(match, context_ref),
            lambda_home=lam_home_eff,
            lambda_away=lam_away_eff,
            quality=quality,
            warnings=warnings,
            metrics=metrics,
            **summary,
        )
