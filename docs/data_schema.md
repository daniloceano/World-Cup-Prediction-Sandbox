# WCPS — Data Schemas

All on-disk data is JSON (CSV-friendly later). Demo records carry `"is_demo": true`.

---

## 1. Teams — `data/raw/teams.json`

```json
{
  "teams": [
    {"code": "ARG", "name": "Argentina", "confederation": "CONMEBOL", "is_demo": true}
  ]
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `code` | string | yes | 3-letter FIFA/ISO-style key used everywhere (`flags.py` maps it to an emoji). |
| `name` | string | yes | Display name. |
| `confederation` | string | no | UEFA / CONMEBOL / AFC / CAF / CONCACAF / OFC. |
| `is_demo` | bool | no | Mark fabricated entries. |

---

## 2. Matches (schedule) — `data/raw/matches.json`

```json
{
  "matches": [
    {
      "match_id": "demo-2026-06-17-ARG-KSA",
      "date": "2026-06-17",
      "kickoff": "13:00",
      "venue": "Demo Stadium, Sample City",
      "phase": "group",
      "group": "C",
      "home_team": "ARG",
      "away_team": "KSA",
      "is_demo": true
    }
  ]
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `match_id` | string | yes | Globally unique, stable key. Canonical convention: `wc-YYYY-MM-DD-<HOME>-<AWAY>` (uppercase FIFA codes, slate date). Demo fixtures use a `demo-…` prefix; legacy-imported ones use `YYYY-MM-DD_home_away`. The History join tolerates all three. |
| `date` | string | yes | `YYYY-MM-DD`. Drives the date selector. |
| `kickoff` | string | no | Local time, free-form (e.g. `19:00`). |
| `venue` | string | no | Stadium/city. |
| `phase` | string | no | `group` / `round_of_16` / `quarter` / `semi` / `final`. Used by History. |
| `group` | string | no | Group letter for group-stage. |
| `home_team`, `away_team` | string | yes | Team `code`s (Team A = home, Team B = away). |
| `is_demo` | bool | no | Marks demo fixtures. |

---

## 3. Daily context — `data/context/YYYY-MM-DD.json`

The file the user pastes each morning (from the ChatGPT prompt). **Preserved as
an audit trail — never modified by the app.**

```json
{
  "date": "2026-06-17",
  "generated_by": "ChatGPT daily context prompt v1",
  "matches": [
    {
      "match_id": "demo-2026-06-17-ARG-KSA",
      "home_team": "ARG",
      "away_team": "KSA",
      "v1_scores": {
        "fifa_ranking":        {"home": 1.0,  "away": -1.0},
        "short_form":          {"home": 0.5,  "away": -0.5},
        "long_form":           {"home": 0.5,  "away": 0.0},
        "injuries":            {"home": 0.0,  "away": -0.5},
        "weather_adaptation":  {"home": 0.0,  "away": 0.5},
        "off_field":           {"home": 0.0,  "away": 0.0},
        "tactical_similarity": {"home": 0.5,  "away": -0.5}
      },
      "v2_strategic": {
        "favorite": "home",
        "low_block_capacity": 0.8,
        "draw_value_weaker": 0.85,
        "need_to_win": {"home": 0.7, "away": 0.2},
        "first_goal_prob": {"home": 0.55, "away": 0.10, "none": 0.35},
        "collapse_risk_weaker": 0.6,
        "is_group_debut": true,
        "transition_threat_weaker": 0.3,
        "set_piece_threat_weaker": 0.4
      },
      "notes": "free text"
    }
  ]
}
```

### 3.1 `v1_scores` — the seven criteria (methodology §1.1)

Each criterion has a `home` and `away` score in **`[-1.0, +1.0]`** where `+1.0`
is a strong advantage for that side and `0.0` is neutral. Missing criteria/sides
default to `0.0` (with a validation warning).

| Key | Criterion | Raw weight* |
|---|---|---|
| `fifa_ranking` | FIFA ranking position | 1.5 |
| `short_form` | Last ~5 games | 2.5 |
| `long_form` | Last ~15 games | 1.0 |
| `injuries` | Key absences / suspensions | 1.5 |
| `weather_adaptation` | Weather & relative adaptation | 1.0 |
| `off_field` | Off-field noise / instability | 1.0 |
| `tactical_similarity` | Form vs similar tactical profiles | 2.5 |

\* Weights live in `config.yaml` (`model_standard.weights`) and are normalized to sum 1.

### 3.2 `v2_strategic` — strategic layer (methodology §4)

All optional; missing fields fall back to neutral and produce a "degraded"
quality flag. Values in `[0, 1]` unless noted.

Used by `model_conservative` (and as a fallback source for `model_aggressive`).

| Key | Symbol | Meaning | Effect in `model_conservative` |
|---|---|---|---|
| `favorite` | — | `"home"`/`"away"` (else inferred from strength D) | Sets which side gets the favourite adjustments. |
| `low_block_capacity` | `B_D` | Underdog's ability to hold a low block | Compresses favourite λ initially; boosts λ once the favourite scores (block opens). |
| `draw_value_weaker` | `V_E` | How valuable a draw is for the weaker side | Importance-weights drawn scorelines so `P(draw)* ≈ P(draw)+Δ_E` (Δ_E capped by config). |
| `need_to_win` | `N_V` | `{home, away}` pressure to attack | Informational in v1 of v2 (reserved for future use). |
| `first_goal_prob` | `P(G₁)` | `{home, away, none}` who scores first / stays 0-0 | Drives the first-goal state mixture. If omitted, derived from λ + low block. |
| `collapse_risk_weaker` | `C_g` | Underdog disorganization after conceding | Amplifies favourite λ in the post-goal state (goleada risk). |
| `is_group_debut` | — | Group-stage opener? | Applies the debut damping factor to the favourite. |
| `transition_threat_weaker` | — | Underdog counter-attack threat | Mildly raises underdog λ. |
| `set_piece_threat_weaker` | — | Underdog set-piece threat | Mildly raises underdog λ. |

`first_goal_prob` values are normalized to sum to 1 automatically.

### 3.3 `aggressive` — optional block for `model_aggressive` (methodology §6)

Entirely optional. When absent, `model_aggressive` **derives** these from the
strength gap and `v2_strategic`, so the daily prompt does **not** need to provide
them. Provide any subset to override a derived value. All in `[0, 1]`.

| Key | Symbol | Meaning | Derived from (if omitted) |
|---|---|---|---|
| `offensive_superiority` | `A_F` | Favourite's relative attacking power | `min(1, |D|·1.8)` |
| `underdog_fragility` | `D_U` | Underdog concedes many chances | `1 − low_block_capacity` |
| `early_goal_prob` | `G_E` | Favourite scores early | `first_goal_prob[favourite]` |
| `post_goal_intensity` | `I_P` | Favourite keeps pressing after scoring | `need_to_win[favourite]` (≈0.6 default) |
| `underdog_exposure` | `E_U` | Underdog opens up / collapses after conceding | `collapse_risk_weaker` |
| `goleada_tail` | `T_G` | Tendency toward 3+ goal margins | `0.5·A_F + 0.5·D_U` |

---

## 4. Prediction output — `data/predictions/YYYY-MM-DD.json`

Generated artifact (regeneratable). Top level:

```json
{
  "date": "2026-06-17",
  "generated_at": "2026-06-17T10:00:00+00:00",
  "context_available": true,
  "context_valid": true,
  "context_warnings": false,
  "n_matches": 2,
  "predictions": {
    "<match_id>": {
      "match_id": "<match_id>",
      "models":  {"standard": { Prediction }, "conservative": { Prediction }, "aggressive": { Prediction }},
      "ensemble": { Prediction }
    }
  }
}
```

### 4.1 `Prediction` object (same schema for every model and the ensemble)

| Field | Type | Meaning |
|---|---|---|
| `model_id`, `model_version` | string | Identity (`"standard"`, `"conservative"`, `"aggressive"`, `"ensemble"`). |
| `match_id` | string | Match key. |
| `run_datetime` | string | ISO-8601 UTC. |
| `context_ref` | string/null | Path of the context file used. |
| `prob_home`, `prob_draw`, `prob_away` | float | Outcome probabilities (sum 1). |
| `scoreline_probs` | object | `"x-y" -> probability` (truncated at `max_scoreline_goals`). |
| `recommended_outcome` | string | `"home"`/`"draw"`/`"away"`. |
| `recommended_score` | string | `"x-y"` (methodology §6 logic). |
| `modal_score` | string | Single most probable scoreline. |
| `top_scorelines` | list | `[{score, prob}]` overall. |
| `top_scorelines_in_outcome` | list | `[{score, prob}]` within preferred outcome. |
| `stats` | object | Per-quantity `{mean, median, lower, upper, lower_q, upper_q}` for `goals_home`, `goals_away`, `total_goals`, `goal_diff`, `points_home`, `points_away`. |
| `lambda_home`, `lambda_away` | float | Effective expected goals used. |
| `confidence` | float | Margin between top two outcome probabilities. |
| `quality` | string | `"ok"` / `"degraded"` / `"missing_context"`. |
| `warnings` | list | Human-readable notes. |
| `metrics` | object | Optional model-specific scalars (empty for most). `model_aggressive` fills `p_favourite_win_by_2plus`, `p_favourite_win_by_3plus`, `goleada_tail_index`, `offensive_superiority`. |

---

## 5. Actual results — `data/results/actual_results.json`

This file is the **versioned, committed record** of real results, used for
historical evaluation. Append to it (by hand or via Prompt B output); it is the
source of truth for model-performance metrics.

```json
{
  "results": [
    {"match_id": "wc-2026-06-14-GER-CUW", "home_goals": 7, "away_goals": 1,
     "status": "final", "notes": "Germany 7-1 Curaçao."}
  ]
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `match_id` | string | yes | Canonical `wc-YYYY-MM-DD-<HOME>-<AWAY>`. Need not match a prediction's id verbatim — the join also pairs by team set + date (see below). |
| `home_goals`, `away_goals` | int | yes | Full-time goals, in the listed home/away order. |
| `home_team`, `away_team` | string | no | Uppercase codes; help the join when the `match_id` is non-standard. |
| `status` | string | no | e.g. `final`. |
| `notes` | string | no | Free text. |

**Robust join.** `evaluation.build_history` pairs each result with the matching
prediction even when conventions differ: it first tries an exact `match_id`,
then falls back to the **unordered team pair** (nearest date if a pair recurs)
and **re-orients** the goals to the prediction's home/away. This makes the
committed results evaluate correctly against predictions that use a different
`match_id` style, reversed fixture order, or a ±1-day (madrugada) slate shift.

---

## 5b. Legacy ChatGPT export — `data/predictions/legacy_chat_predictions.json`

An imported-from-ChatGPT archive in its **own** schema (not the app schema): an
`export_metadata` block plus a `predictions` array where each entry has
`match_id`, `team_a`/`team_b` (full names), `models.model_v1` / `models.model_v2`
with `outcome_probabilities` (`team_a_win`/`draw`/`team_b_win`),
`recommended_outcome`, `recommended_score`, `modal_score`, and the top scoreline
lists. `scripts/import_legacy_predictions.py` converts these into the standard
`Prediction` schema (§4.1) as the `chatgpt_legacy` source — mapping
`team_a→home`, reconstructing a *partial* `scoreline_probs` from the top lists,
and approximating `stats` from it (flagged `quality="degraded"`). The original
file is preserved unmodified as the audit record.

## 6. Evaluation summary (computed, not stored)

`evaluation.benchmark_summary()` compares each source's winner-accuracy to a
**FIFA-ranking baseline** (always back the higher-ranked team to win, from the
context's `fifa_ranking`) over the same subset of matches that have a ranking and
a result — shown on the History page.

`evaluation.summarize_by_source()` returns, per source (`standard`, `conservative`, `aggressive`, `ensemble`):
`n`, `outcome_accuracy`, `exact_score_accuracy`, `mean_brier`, `mean_log_loss`.
Per-match rows also expose `outcome_correct`, `score_correct`, `brier`,
`log_loss`, `prob_assigned_true` — a calibration-friendly structure for future
reliability plots.
