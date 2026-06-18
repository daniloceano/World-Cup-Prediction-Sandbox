# WCPS — Model Notes

Living record of model changes, parameter choices and ideas for future models.
The formal methodology for v1 and v2 lives in
[`materiais_metodos_modelos_v1_v2_previsao_futebol.md`](materiais_metodos_modelos_v1_v2_previsao_futebol.md)
(the methodological source of truth). This file tracks **implementation
decisions** and **future work** — keep it short and dated.

---

## Model naming

The three regimes were renamed (the old ids are gone from the code):

| Current id | Old id | File |
|---|---|---|
| `standard` | `v1` | `src/wcps/models/model_standard.py` |
| `conservative` | `v2` | `src/wcps/models/model_conservative.py` |
| `aggressive` | — (new) | `src/wcps/models/model_aggressive.py` |

The daily-context block is still named `v2_strategic` for backward
compatibility (all three models read from it).

## Implemented models

### standard — static relative strength (`model_standard.py`)
- Seven weighted criteria → aggregate strength `D` → `λ = λ₀ ± αD` (clipped) →
  independent Poisson → Monte Carlo. The neutral / central regime.
- Parameters in `config.yaml › model_standard`: `lambda_0=1.35`, `alpha=1.10`,
  `lambda_min=0.15`, `lambda_max=4.0`, plus the heuristic `weights`.
- Known behaviour (per methodology §3): tends to over-rate favourites and
  under-weight draws — which `conservative` corrects and `aggressive` leans into.

### conservative — strategic World Cup model (`model_conservative.py`)
- Reuses the standard strength core, then adds a **first-goal state mixture**
  (S₀ / S_fav / S_und) simulated explicitly per trial, a low-block compression of
  the favourite, a post-goal space/collapse boost, and a **draw-value
  importance re-weighting** of drawn scorelines (`P(draw)* ≈ P(draw)+Δ_E`).
- Factor → context mappings are documented inline in the model and in
  `docs/data_schema.md` §3.2. They are heuristic (not fitted) — see Caveats.

### aggressive — amplified favourite (`model_aggressive.py`)
- Implements `docs/materiais_metodos_modelo_agressivo_wcps.md`. Standard core +
  favourite amplification `F_sup = 1 + β·A_F`, a three-state mixture
  S₀ / S_F (favourite scores, keeps pressing) / S_C (underdog collapses), and a
  **goleada tail**: scorelines with margin `M ≥ 3` get importance weight
  `1 + γ·T_G` (then renormalised).
- The six aggressive variables (A_F, D_U, G_E, I_P, E_U, T_G) come from an
  optional `aggressive` block in the daily context, otherwise are **derived**
  from `v1_scores` / `v2_strategic` (so it runs on today's context format). See
  `docs/data_schema.md` §3.3.
- Emits extra `metrics`: `p_favourite_win_by_2plus`, `p_favourite_win_by_3plus`,
  `goleada_tail_index`, `offensive_superiority` (methodology §10).
- Parameters in `config.yaml › model_aggressive`: `beta`, `pressure_boost_max`,
  `collapse_boost_max`, `block_compression`, `chase_boost_max`,
  `early_goal_base`, `goleada_gamma`.
- Caveat: by design it can over-rate dominant favourites (e.g. ~90% home win in
  strongly asymmetric matchups). Tune `beta` / `goleada_gamma` down to soften.

---

## Implementation decisions (dated)

### 2026-06-17 — Initial implementation
- Draw value Δ_E implemented as **sample importance weights** rather than
  post-hoc probability surgery, so weighted quantiles/medians stay consistent
  with the re-weighted distribution.
- First-goal states simulated as a categorical draw per Monte Carlo trial; if
  `first_goal_prob` is absent it is derived from the adjusted λ and low-block
  capacity. This keeps v2 runnable even with partial context (flagged
  `quality="degraded"`).
- Recommended score follows methodology §6: keep the modal score if it agrees
  with the preferred outcome, otherwise pick the most probable score *within* the
  preferred outcome (conservative).
- `n_simulations=20000` chosen as a balance of stability vs speed; tune in config.

---

## Caveats (implementation-level)

- All v1/v2 weights and v2 factors are **heuristic**, not estimated by maximum
  likelihood on a historical dataset. Treat outputs as scenario exploration.
- Goals are modelled as (conditionally) independent Poisson; no Dixon–Coles
  low-score correlation correction yet.
- v2's post-goal boost can push total-goals upward in high-collapse matchups;
  inspect `total_goals` stats and tune `space_boost_max` / `collapse_boost_max`.

---

## Ideas for future models (the registry is ready for these)

To add one: create `src/wcps/models/model_<id>.py` with a `BaseModel` subclass
decorated `@REGISTRY.register`, import it in `models/__init__.py`, add a
`model_<id>` section to `config.yaml`, and (optionally) an ensemble weight.

- **v3 — Dixon–Coles correlation**: add low-score dependence to v1/v2.
- **Elo / strength-rating model**: convert a maintained Elo into λ via a
  logistic map; needs a ratings table in `data/`.
- **xG-based model**: drive λ from historical/expected-goals inputs in context.
- **ML model**: gradient-boosted or logistic outcome model trained on past
  matches; must still emit the standardized `Prediction` (e.g. derive a scoreline
  distribution from predicted λ or a learned score grid).
- **Performance-weighted ensemble**: implement the `performance` strategy in
  `ensemble.resolve_weights()` using `evaluation.summarize_by_source()`.
