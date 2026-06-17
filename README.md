# ⚽ WCPS — World Cup Prediction Sandbox

A **recreational probabilistic simulator** for World Cup matches. Pick a date,
see every fixture's simulated outcome probabilities, recommended scoreline and
an ensemble of models, then drill into any match for the full breakdown —
scoreline heatmaps, quantile statistics, model comparison and historical
accuracy once real results are in.

> ⚠️ **Disclaimer.** WCPS is for **fun, analysis and visualization only**. It is
> a probabilistic *simulation sandbox* — **not** betting, gambling, odds
> optimization, or financial advice. It uses **no** bookmaker or betting data.

It ships with two models from the methodology in
[`docs/`](docs/materiais_metodos_modelos_v1_v2_previsao_futebol.md):

- **v1** — static relative-strength → expected goals → independent Poisson → Monte Carlo.
- **v2** — v1 plus strategic World Cup adjustments (draw value, low block, first-goal
  state, post-goal collapse).

The model layer is a plugin registry, so **v3 / Elo / xG / ML models can be added
without touching the app**.

---

## Features

- 📅 **Dashboard** — date selector + clean match cards (flags, kickoff, venue,
  probabilities, preferred outcome, recommended score, confidence, result status).
- 🔍 **Match detail** — per-model and ensemble outputs, outcome bar chart,
  scoreline heatmap, top scorelines (overall & within the preferred outcome),
  median/quantile statistics, daily context used, and historical comparison.
- 📊 **History** — outcome & exact-score accuracy, Brier score and log loss, per
  model and ensemble.
- 📝 **Daily context** — paste the daily ChatGPT JSON, validate it, save it,
  regenerate predictions.
- ⚙️ **CLI** + single `config.yaml` for everything tunable.

---

## Quick start

```bash
# 1. (optional) create an environment, then install deps
pip install -r requirements.txt

# 2. run the app  (demo data is included, so it works immediately)
streamlit run streamlit_app.py
```

Open the URL Streamlit prints (default <http://localhost:8501>). The app loads
with demo fixtures clearly marked as demo data.

> Tested with Python 3.11–3.13, Streamlit ≥ 1.30.

---

## How it works (data flow)

```
data/raw/matches.json + data/context/<date>.json
        → each active model (v1, v2, …) → ensemble
        → data/predictions/<date>.json  → dashboard / detail / history
```

Predictions are derived artifacts: delete them anytime and regenerate. Daily
context files are **never modified** by the app — they are the audit trail.
Full reference: [`docs/architecture.md`](docs/architecture.md) and
[`docs/data_schema.md`](docs/data_schema.md).

---

## Daily workflow

### Add daily context
Each morning, ask ChatGPT for the day's match context using the template in
[`docs/daily_context_prompt.md`](docs/daily_context_prompt.md). Then either:

- **In the app:** open **Daily Context** → paste JSON → **Validate** →
  **Save & generate predictions**; or
- **By hand:** save the JSON to `data/context/YYYY-MM-DD.json`.

The app clearly flags predictions made with **missing or incomplete** context.

### Generate predictions
- From the dashboard: pick the date (predictions auto-generate on first view;
  use **🔄 Regenerate** after editing context), or
- From the CLI:

```bash
python scripts/generate_predictions.py --date 2026-06-17   # one date
python scripts/generate_predictions.py --all               # all scheduled dates
python scripts/generate_predictions.py --date 2026-06-17 --dry-run  # validate only
```

### Add actual results
Edit [`data/results/actual_results.json`](data/results/actual_results.json):

```json
{"results": [
  {"match_id": "demo-2026-06-14-GER-JPN", "home_goals": 1, "away_goals": 2, "status": "final"}
]}
```

The **History** page and each match's **detail** page then show whether every
model/ensemble got the outcome and exact score right, plus Brier/log-loss.

---

## Adding a new model

The app is **not** hard-coded to v1/v2. To add, say, `v3`:

1. Create `src/wcps/models/model_v3.py`:

   ```python
   from ..schemas import Prediction
   from ..simulation import make_rng, summarize_simulation
   from .base import REGISTRY, BaseModel

   @REGISTRY.register
   class ModelV3(BaseModel):
       model_id = "v3"
       model_version = "1.0.0"
       display_name = "v3 · My new model"
       required_inputs = ("v1_scores",)

       def predict(self, match, context, context_ref=None):
           # ... compute λ_home, λ_away however you like ...
           rng = make_rng(self.config["simulation"]["random_seed"], match["match_id"] + "v3")
           n = self.config["simulation"]["n_simulations"]
           gh = rng.poisson(lam_home, n); ga = rng.poisson(lam_away, n)
           q = self.config["quantiles"]
           summary = summarize_simulation(gh, ga, q["lower"], q["upper"])
           return Prediction(**self._base_prediction_kwargs(match, context_ref),
                             lambda_home=lam_home, lambda_away=lam_away,
                             quality="ok", warnings=[], **summary)
   ```

2. Import it in [`src/wcps/models/__init__.py`](src/wcps/models/__init__.py).
3. Add a `model_v3:` section (with `active: true`) to `config.yaml`, and a weight
   under `ensemble.weights` if you use the weighted strategy.

That's it — the dashboard, detail page, ensemble and evaluation pick it up
automatically. See [`docs/model_notes.md`](docs/model_notes.md) for ideas
(Dixon–Coles, Elo, xG, ML).

---

## Configuration

Everything tunable lives in [`config.yaml`](config.yaml): simulation count &
seed, quantile levels, v1/v2 parameters, model activation, ensemble strategy &
weights, display options, and file paths. No need to edit source code for basic
changes.

---

## Tests

```bash
pytest -q
```

Covers context validation, model output shape & reproducibility, the v2-raises-
draws property, ensemble aggregation, the end-to-end pipeline, and evaluation
metrics.

---

## Deploy (Streamlit Community Cloud, free)

1. Push this repo to GitHub.
2. Go to <https://share.streamlit.io>, "New app", point it at `streamlit_app.py`.
3. `requirements.txt` is detected automatically; no secrets required.
4. Demo data is committed, so the app works right after deploy.

Notes & alternatives (Vercel/Next.js trade-offs, persistence): see
[`docs/architecture.md`](docs/architecture.md) §7.

---

## Project layout

```
config.yaml            # central config
streamlit_app.py       # Dashboard (entry point)
pages/                 # Match Detail, History, Daily Context
app/                   # UI helpers (cards, charts)
src/wcps/              # engine: models, ensemble, pipeline, evaluation, I/O
scripts/               # CLI
data/                  # raw (schedule/teams), context, predictions, results
docs/                  # methodology + architecture + schemas + prompts
tests/                 # pytest suite
```

---

## Limitations

- v1/v2 weights and v2 strategic factors are **heuristic**, not statistically
  fitted. Outputs are scenario exploration, not forecasts of record.
- Goals use (conditionally) independent Poisson; no Dixon–Coles low-score
  correction yet.
- Quality depends on the daily context; the app flags incomplete context but
  cannot detect wrong-but-plausible inputs.
- Demo fixtures are fabricated and labelled as such — replace `data/raw/` with
  the real schedule before drawing any conclusions.

Recreational and analytical. Not for betting.
