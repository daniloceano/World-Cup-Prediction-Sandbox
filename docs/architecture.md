# WCPS — Architecture

> WCPS is a **recreational probabilistic simulation sandbox** for World Cup
> matches. It is for fun, analysis and visualization only — **not** betting,
> gambling, odds optimization, or financial advice. No bookmaker/betting data
> or APIs are used.

## 1. Chosen stack and why

| Layer | Choice | Reason |
|---|---|---|
| Language | Python 3.11+ | The models are numeric Monte Carlo simulations; the project is data-science oriented. |
| UI | **Streamlit** | Single language end-to-end, near-zero frontend boilerplate, fast to iterate, trivial free deployment (Streamlit Community Cloud). Matches the "simple, maintainable, runnable today" goal. |
| Numerics | NumPy | Vectorized Poisson / Monte Carlo. |
| Tables | pandas | Display + evaluation. |
| Charts | Altair (ships with Streamlit) | Clean declarative charts, no extra dependency. |
| Storage | JSON + CSV on disk | No database needed in v1; auditable, diff-friendly, easy to migrate to SQLite/Postgres later. |
| Config | single `config.yaml` | One place to tune behaviour without editing code. |

A Next.js + Vercel frontend with a Python backend was considered and rejected
for v1: it doubles the languages and deployment surface for no user-facing
benefit on a single-user analytical tool. The model layer is deliberately
UI-agnostic (pure functions returning standardized objects), so a different
frontend can be added later without touching the models.

## 2. Repository layout

```
world_cup_predictor_sandbox/
├── config.yaml              # central configuration (single source of tuning)
├── streamlit_app.py         # Streamlit entry point = Dashboard
├── pages/                   # additional Streamlit pages
│   ├── 1_Match_Detail.py
│   ├── 2_History.py
│   └── 3_Daily_Context.py
├── app/                     # UI helpers (not the models)
│   ├── bootstrap.py         # puts src/ on sys.path
│   └── components.py        # cards, charts, formatting
├── src/wcps/                # the engine (UI-independent, importable, testable)
│   ├── config.py            # config + path resolution
│   ├── schemas.py           # Prediction / StatSummary dataclasses
│   ├── flags.py             # country code -> flag emoji
│   ├── context.py           # daily-context validation
│   ├── simulation.py        # Monte Carlo -> standardized summaries
│   ├── data_io.py           # JSON/CSV read/write
│   ├── models/
│   │   ├── base.py          # BaseModel interface + REGISTRY
│   │   ├── model_standard.py     # static relative strength (ex-v1)
│   │   ├── model_conservative.py # strategic / draw-friendly (ex-v2)
│   │   └── model_aggressive.py   # amplified favourite / goleada (new)
│   ├── ensemble.py          # combine models -> ensemble Prediction
│   ├── pipeline.py          # orchestration + persistence
│   └── evaluation.py        # historical metrics
├── scripts/
│   └── generate_predictions.py   # CLI
├── data/
│   ├── raw/                 # teams.json, matches.json (schedule)
│   ├── context/             # daily ChatGPT JSON: YYYY-MM-DD.json (audit trail)
│   ├── predictions/         # generated per-date prediction payloads
│   ├── results/             # actual_results.json
│   └── processed/           # reserved for future intermediate data
├── docs/                    # this folder
└── tests/                   # pytest suite
```

## 3. Data flow

```
 data/raw/matches.json  ─┐
                         ├─►  pipeline.generate_for_date(date)
 data/context/DATE.json ─┘            │
        (validated by context.py)     │   for each match:
                                       ▼
                         each active model  (REGISTRY.active_models)
                              v1.predict() ┐
                              v2.predict() ┼─►  ensemble.combine()
                              ...          ┘          │
                                                      ▼
                         data/predictions/DATE.json  (models + ensemble,
                                                      standardized schema)
                                                      │
                         ┌────────────────────────────┼───────────────────┐
                         ▼                             ▼                   ▼
                   Dashboard cards            Match Detail page      History page
                                                                  (joins actual_results.json
                                                                   via evaluation.py)
```

Predictions are **derived artifacts** — they can be deleted and regenerated from
`matches.json` + the context files at any time (the CLI `--all` rebuilds them).
Context files are never modified by the app; they are the audit record.

## 4. Model registry (plugin architecture)

Every model subclasses `BaseModel` (`src/wcps/models/base.py`) and registers
itself with the global `REGISTRY` via the `@REGISTRY.register` decorator. The
app and the ensemble only depend on:

* `model_id`, `model_version`, `display_name`, `description`, `required_inputs`;
* `predict(match, context, context_ref) -> Prediction`.

`REGISTRY.active_models(config)` returns the instantiated models whose
`model_<id>.active` flag is true in `config.yaml`. **Nothing is hard-coded to v1
and v2** — adding `v3`, an Elo model, an xG model, or an ML model means dropping
a new `model_<id>.py` file and importing it in `models/__init__.py`. See the
README section "Adding a new model".

Every model returns the same `Prediction` dataclass (`src/wcps/schemas.py`):
identity, outcome probabilities, scoreline distribution, recommended
outcome/score, modal & top scorelines, per-quantity quantile statistics,
effective lambdas, confidence and warnings/quality metadata.

## 5. Ensemble design

`ensemble.combine()` takes the list of model `Prediction`s and emits one more
`Prediction` (`model_id="ensemble"`) using the **same schema**, so the UI treats
it like any model. v1 implements:

* `equal` — uniform average (default);
* `weighted` — explicit per-model weights from `config.yaml`.

Outcome probabilities are weighted-averaged; scoreline distributions are mixed
(weighted) and renormalized; quantile statistics are reconstructed by sampling
the mixed scoreline distribution. The weighting policy is isolated in
`resolve_weights()`, so future strategies (`performance`, `phase_weighted`,
`matchup_weighted`) are a one-function change — they are already recognized
config values that currently fall back to equal/weighted behaviour.

## 6. Configuration

All tunables live in `config.yaml`: simulation count & seed, quantile levels,
v1/v2 parameters, model activation, ensemble strategy & weights, display
options, and file paths. `src/wcps/config.py` resolves the project root robustly
(env var `WCPS_ROOT`, else by walking up to `config.yaml`) so there are **no
fragile absolute paths** and the app runs identically locally and in deployment.

## 7. Deployment choice

**Streamlit Community Cloud** (free):

1. Push this repo to GitHub.
2. On <https://share.streamlit.io>, create an app pointing at `streamlit_app.py`.
3. `requirements.txt` is picked up automatically; no secrets are required.
4. Paths are repo-relative, so the demo data works immediately after deploy.

Predictions are generated on demand (`pipeline.get_or_generate`) and cached to
`data/predictions/`. On Community Cloud the filesystem is ephemeral, which is
fine: predictions transparently regenerate from committed context. To persist
predictions/results across restarts, commit them to the repo or migrate
`data_io` to SQLite/Postgres (the I/O layer is the only thing that would change).
