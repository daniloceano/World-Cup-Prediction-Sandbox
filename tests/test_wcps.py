"""Basic test suite for WCPS.

Covers: context validation, model output shape, ensemble aggregation, the
end-to-end prediction pipeline on sample inputs, and evaluation metrics.
"""

from __future__ import annotations

import pytest

from wcps import data_io, evaluation, pipeline
from wcps.config import load_config
from wcps.context import validate_context
from wcps.ensemble import combine
from wcps.models import REGISTRY
from wcps.schemas import OUTCOMES, Prediction

CFG = load_config()
DEMO_MATCH = {
    "match_id": "test-match",
    "home_team": "ARG",
    "away_team": "KSA",
    "date": "2026-06-17",
}
DEMO_CONTEXT = data_io.context_for_match("2026-06-17", "demo-2026-06-17-ARG-KSA")


# --- schema / validation ----------------------------------------------------
def test_context_validation_ok():
    ctx = data_io.load_context("2026-06-17")
    result = validate_context(ctx)
    assert result.ok


def test_context_validation_missing():
    result = validate_context(None)
    assert not result.ok
    assert result.errors


def test_context_validation_warns_on_missing_criteria():
    ctx = {"date": "x", "matches": [{"match_id": "m", "v1_scores": {}}]}
    result = validate_context(ctx)
    assert result.ok  # usable...
    assert result.per_match["m"]  # ...but warns


# --- model output shape -----------------------------------------------------
@pytest.mark.parametrize("model_id", ["v1", "v2"])
def test_model_output_shape(model_id):
    model = REGISTRY.get(model_id)(CFG)
    pred = model.predict(DEMO_MATCH, DEMO_CONTEXT, context_ref="test")
    assert isinstance(pred, Prediction)
    probs = (pred.prob_home, pred.prob_draw, pred.prob_away)
    assert all(0.0 <= p <= 1.0 for p in probs)
    assert pytest.approx(sum(probs), abs=1e-6) == 1.0
    assert pred.recommended_outcome in OUTCOMES
    assert "-" in pred.recommended_score
    for key in ("goals_home", "goals_away", "total_goals", "goal_diff"):
        assert key in pred.stats
    # scoreline distribution sums to ~1 (truncation aside)
    assert 0.9 <= sum(pred.scoreline_probs.values()) <= 1.0001


def test_model_reproducible():
    model = REGISTRY.get("v1")(CFG)
    p1 = model.predict(DEMO_MATCH, DEMO_CONTEXT)
    p2 = model.predict(DEMO_MATCH, DEMO_CONTEXT)
    assert p1.prob_home == pytest.approx(p2.prob_home)
    assert p1.scoreline_probs == p2.scoreline_probs


def test_v2_increases_draw_for_strategic_underdog():
    """v2 should raise the draw probability vs v1 when the draw is valuable."""
    v1 = REGISTRY.get("v1")(CFG).predict(DEMO_MATCH, DEMO_CONTEXT)
    v2 = REGISTRY.get("v2")(CFG).predict(DEMO_MATCH, DEMO_CONTEXT)
    assert v2.prob_draw > v1.prob_draw


# --- ensemble ---------------------------------------------------------------
def test_ensemble_aggregation():
    preds = [REGISTRY.get(mid)(CFG).predict(DEMO_MATCH, DEMO_CONTEXT)
             for mid in ("v1", "v2")]
    ens = combine(preds, CFG, DEMO_MATCH["match_id"])
    assert ens.model_id == "ensemble"
    total = ens.prob_home + ens.prob_draw + ens.prob_away
    assert pytest.approx(total, abs=1e-6) == 1.0
    # equal-weight ensemble draw prob lies between the members
    lo = min(p.prob_draw for p in preds)
    hi = max(p.prob_draw for p in preds)
    assert lo - 1e-9 <= ens.prob_draw <= hi + 1e-9


# --- pipeline ---------------------------------------------------------------
def test_pipeline_generates_for_demo_date():
    payload = pipeline.generate_for_date("2026-06-17", save=False)
    assert payload["n_matches"] >= 1
    for mp in payload["predictions"].values():
        assert "v1" in mp["models"] and "v2" in mp["models"]
        assert mp["ensemble"]["model_id"] == "ensemble"


# --- evaluation -------------------------------------------------------------
def test_evaluation_metrics():
    actual = {"home_goals": 1, "away_goals": 2}
    pred = REGISTRY.get("v1")(CFG).predict(DEMO_MATCH, DEMO_CONTEXT).to_dict()
    res = evaluation.evaluate_prediction(pred, actual)
    assert res["true_outcome"] == "away"
    assert 0.0 <= res["brier"] <= 2.0
    assert res["log_loss"] >= 0.0
