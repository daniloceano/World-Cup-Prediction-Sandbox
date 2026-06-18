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
# Inline context so the tests do not depend on mutable files under data/context/.
DEMO_CONTEXT = {
    "match_id": "test-match",
    "home_team": "ARG",
    "away_team": "KSA",
    "v1_scores": {
        "fifa_ranking": {"home": 1.0, "away": -1.0},
        "short_form": {"home": 0.5, "away": -0.5},
        "long_form": {"home": 0.5, "away": 0.0},
        "injuries": {"home": 0.0, "away": -0.5},
        "weather_adaptation": {"home": 0.0, "away": 0.5},
        "off_field": {"home": 0.0, "away": 0.0},
        "tactical_similarity": {"home": 0.5, "away": -0.5},
    },
    "v2_strategic": {
        "favorite": "home",
        "low_block_capacity": 0.8,
        "draw_value_weaker": 0.85,
        "need_to_win": {"home": 0.7, "away": 0.2},
        "first_goal_prob": {"home": 0.55, "away": 0.10, "none": 0.35},
        "collapse_risk_weaker": 0.6,
        "is_group_debut": True,
        "transition_threat_weaker": 0.3,
        "set_piece_threat_weaker": 0.4,
    },
}


# --- schema / validation ----------------------------------------------------
def test_context_validation_ok():
    ctx = {"date": "2026-06-17", "matches": [DEMO_CONTEXT]}
    result = validate_context(ctx)
    assert result.ok
    assert not result.per_match["test-match"]  # complete -> no warnings


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
@pytest.mark.parametrize("model_id", ["standard", "conservative", "aggressive"])
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
    model = REGISTRY.get("standard")(CFG)
    p1 = model.predict(DEMO_MATCH, DEMO_CONTEXT)
    p2 = model.predict(DEMO_MATCH, DEMO_CONTEXT)
    assert p1.prob_home == pytest.approx(p2.prob_home)
    assert p1.scoreline_probs == p2.scoreline_probs


def test_conservative_increases_draw_for_strategic_underdog():
    """Conservative should raise the draw probability vs standard when the draw is valuable."""
    std = REGISTRY.get("standard")(CFG).predict(DEMO_MATCH, DEMO_CONTEXT)
    cons = REGISTRY.get("conservative")(CFG).predict(DEMO_MATCH, DEMO_CONTEXT)
    assert cons.prob_draw > std.prob_draw


def test_aggressive_amplifies_favourite_and_blowouts():
    """Aggressive should favour the strong home side more and lift blowout mass vs standard."""
    std = REGISTRY.get("standard")(CFG).predict(DEMO_MATCH, DEMO_CONTEXT)
    aggr = REGISTRY.get("aggressive")(CFG).predict(DEMO_MATCH, DEMO_CONTEXT)
    # DEMO_CONTEXT is a strong home favourite -> aggressive raises the home win prob
    assert aggr.prob_home > std.prob_home
    # blowout metrics are reported and in [0, 1]
    assert 0.0 <= aggr.metrics["p_favourite_win_by_3plus"] <= 1.0
    assert aggr.metrics["p_favourite_win_by_2plus"] >= aggr.metrics["p_favourite_win_by_3plus"]


# --- ensemble ---------------------------------------------------------------
def test_ensemble_aggregation():
    preds = [REGISTRY.get(mid)(CFG).predict(DEMO_MATCH, DEMO_CONTEXT)
             for mid in ("standard", "conservative", "aggressive")]
    ens = combine(preds, CFG, DEMO_MATCH["match_id"])
    assert ens.model_id == "ensemble"
    total = ens.prob_home + ens.prob_draw + ens.prob_away
    assert pytest.approx(total, abs=1e-6) == 1.0
    # equal-weight ensemble draw prob lies between the members
    lo = min(p.prob_draw for p in preds)
    hi = max(p.prob_draw for p in preds)
    assert lo - 1e-9 <= ens.prob_draw <= hi + 1e-9


# --- pipeline ---------------------------------------------------------------
def test_predict_match_runs_all_models():
    # predict_match orchestrates every active model + the ensemble
    result = pipeline.predict_match(DEMO_MATCH, DEMO_CONTEXT)
    assert {"standard", "conservative", "aggressive"} <= set(result["models"])
    assert result["ensemble"]["model_id"] == "ensemble"


def test_pipeline_preserves_legacy_without_context():
    # a date that only has imported legacy predictions (no context) keeps them
    # read-only: legacy source preserved, no neutral live models fabricated.
    date = next(
        (d for d in data_io.available_dates()
         if (p := data_io.load_predictions(d))
         and any("chatgpt_legacy" in mp.get("models", {})
                 for mp in p["predictions"].values())
         and data_io.load_context(d) is None),
        None,
    )
    assert date, "expected a legacy-only date without context"
    payload = pipeline.generate_for_date(date, save=False)
    mp = next(mp for mp in payload["predictions"].values()
              if "chatgpt_legacy" in mp["models"])
    assert "chatgpt_legacy" in mp["models"]
    assert "standard" not in mp["models"]


def test_legacy_reorientation():
    from wcps import legacy

    p = {
        "prob_home": 0.6, "prob_draw": 0.25, "prob_away": 0.15,
        "scoreline_probs": {"2-0": 0.5, "1-1": 0.3, "0-1": 0.2},
        "recommended_outcome": "home", "recommended_score": "2-0", "modal_score": "2-0",
        "top_scorelines": [{"score": "2-0", "prob": 0.5}],
        "top_scorelines_in_outcome": [{"score": "2-0", "prob": 0.5}],
        "lambda_home": 1.8, "lambda_away": 0.7, "stats": {},
    }
    r = legacy.reorient_prediction(p, 0.05, 0.95)
    assert (r["prob_home"], r["prob_draw"], r["prob_away"]) == (0.15, 0.25, 0.6)
    assert r["recommended_outcome"] == "away"
    assert r["recommended_score"] == "0-2"
    assert r["scoreline_probs"] == {"0-2": 0.5, "1-1": 0.3, "1-0": 0.2}
    assert (r["lambda_home"], r["lambda_away"]) == (0.7, 1.8)


# --- legacy import ----------------------------------------------------------
def test_legacy_conversion():
    from wcps import legacy

    entry = {
        "match_id": "x_a_b",
        "match_date": "2026-06-13",
        "team_a": "Qatar",
        "team_b": "Switzerland",
        "models": {
            "model_v1": {
                "available": True,
                "outcome_probabilities": {"team_a_win": 0.167, "draw": 0.235,
                                          "team_b_win": 0.598},
                "recommended_outcome": "team_b_win",
                "recommended_score": "0-1",
                "modal_score": "0-1",
                "top_scorelines_overall": [
                    {"score": "0-1", "probability": 0.134, "outcome": "team_b_win"},
                    {"score": "1-1", "probability": 0.115, "outcome": "draw"},
                ],
                "top_scorelines_within_most_likely_outcome": [
                    {"score": "0-1", "probability": 0.134, "outcome": "team_b_win"},
                ],
                "extraction_notes": [],
            },
            "model_v2": {"available": False},
        },
    }
    pred = legacy.convert_entry(entry, CFG, "legacy.json")
    assert pred.model_id == "chatgpt_legacy"
    assert pred.model_version == "legacy-v1"
    assert pred.recommended_outcome == "away"
    assert pytest.approx(pred.prob_home + pred.prob_draw + pred.prob_away, abs=1e-6) == 1.0
    assert pred.scoreline_probs  # partial distribution reconstructed
    assert pred.quality == "degraded"


def test_legacy_modal_disambiguation_and_dedup():
    from wcps import legacy

    assert legacy.team_code("Ivory Coast") == "CIV"
    # ambiguous modal "0-1 / 1-1" -> first value, with a warning
    entry = {
        "match_id": "m", "match_date": "2026-06-16", "team_a": "Iraq", "team_b": "Norway",
        "models": {"model_v2": {
            "available": True,
            "outcome_probabilities": {"team_a_win": 0.144, "draw": 0.298, "team_b_win": 0.558},
            "recommended_outcome": "team_b_win", "recommended_score": "0-1",
            "modal_score": "0-1 / 1-1",
            "top_scorelines_overall": [{"score": "0-1", "probability": 0.141}],
            "top_scorelines_within_most_likely_outcome": [],
            "extraction_notes": [],
        }},
    }
    pred = legacy.convert_entry(entry, CFG, "x")
    assert pred.modal_score == "0-1"
    assert any("ambiguous" in w for w in pred.warnings)

    # reversed-order duplicates collapse to one fixture
    a = {"match_id": "a", "match_date": "d", "team_a": "Sweden", "team_b": "Tunisia",
         "kickoff_time": "T", "models": {"model_v1": {"available": True,
         "top_scorelines_overall": [], "top_scorelines_within_most_likely_outcome": [{"x": 1}]}}}
    b = {"match_id": "b", "match_date": "d", "team_a": "Tunisia", "team_b": "Sweden",
         "kickoff_time": "T", "models": {"model_v1": {"available": True,
         "top_scorelines_overall": [{"x": 1}], "top_scorelines_within_most_likely_outcome": [{"x": 1}]}}}
    deduped = legacy.deduplicate([a, b])
    assert len(deduped) == 1
    assert deduped[0]["match_id"] == "b"  # more complete entry kept


# --- daily context -> schedule sync ----------------------------------------
def test_schedule_records_from_context():
    ctx = {
        "date": "2026-07-01",
        "matches": [
            {
                "match_id": "2026-07-01_brazil_chile",
                "kickoff_utc": "2026-07-01T19:00:00Z",
                "venue": "Sample Park",
                "group": "Z",
                "home_team": "BRA", "away_team": "CHI",
                "home_name": "Brazil", "away_name": "Chile",
                "v1_scores": {}, "v2_strategic": {},
            },
            {"match_id": None},                # skipped: no id
            {"home_team": "X", "away_team": "Y"},  # skipped: no match_id
        ],
    }
    teams, matches = data_io.schedule_records_from_context(ctx)
    assert len(matches) == 1
    m = matches[0]
    assert m["match_id"] == "2026-07-01_brazil_chile"
    assert m["date"] == "2026-07-01"
    assert m["kickoff"] == "19:00 UTC"
    assert m["is_demo"] is False
    assert {t["code"] for t in teams} == {"BRA", "CHI"}


def test_schedule_records_backward_compatible_with_minimal_context():
    # Old minimal context (no metadata) registers nothing, does not crash.
    teams, matches = data_io.schedule_records_from_context(
        {"date": "x", "matches": [{"match_id": "m", "v1_scores": {}}]}
    )
    assert teams == [] and matches == []


# --- evaluation -------------------------------------------------------------
def test_evaluation_metrics():
    actual = {"home_goals": 1, "away_goals": 2}
    pred = REGISTRY.get("standard")(CFG).predict(DEMO_MATCH, DEMO_CONTEXT).to_dict()
    res = evaluation.evaluate_prediction(pred, actual)
    assert res["true_outcome"] == "away"
    assert 0.0 <= res["brier"] <= 2.0
    assert res["log_loss"] >= 0.0


def test_evaluation_join_is_robust():
    """Result↔prediction join tolerates id convention, reversed order, date drift."""
    from wcps import evaluation as ev

    # parse codes from a 'wc-...' id
    assert ev._result_team_codes("wc-2026-06-13-QAT-SUI", {}) == ("QAT", "SUI")
    assert ev._parse_date("wc-2026-06-16-ARG-ALG").isoformat() == "2026-06-16"

    actuals = {
        "wc-2026-06-14-CIV-ECU": {"home_goals": 1, "away_goals": 0},   # CIV home
        "wc-2026-06-16-ARG-ALG": {"home_goals": 3, "away_goals": 0},
    }
    index = ev._index_actuals(actuals)

    # prediction stored with REVERSED order (ECU home) -> goals must be swapped
    oriented = ev._match_actual("ECU", "CIV", "2026-06-14", actuals, index,
                                "2026-06-14_ecuador_ivory-coast")
    assert oriented == {"home_goals": 0, "away_goals": 1}

    # prediction dated a day later (madrugada slate shift) still matches
    oriented2 = ev._match_actual("ARG", "ALG", "2026-06-17", actuals, index,
                                 "2026-06-17_argentina_algeria")
    assert oriented2 == {"home_goals": 3, "away_goals": 0}

    # exact match_id fast path
    assert ev._match_actual("X", "Y", "d", {"m": {"home_goals": 2, "away_goals": 1}},
                            {}, "m") == {"home_goals": 2, "away_goals": 1}


def test_ingest_results_parsing():
    # parsing/validation only — counts good rows, reports bad ones, no real write
    import wcps.data_io as dio

    saved_calls = []
    orig = dio.save_actual_result
    dio.save_actual_result = lambda mid, hg, ag, **e: saved_calls.append((mid, hg, ag))
    try:
        ok, errs = dio.ingest_results({"results": [
            {"match_id": "a", "home_goals": 1, "away_goals": 0},
            {"match_id": "b", "home_goals": "2", "away_goals": "2", "status": "final"},
            {"match_id": "c", "home_goals": 1},  # invalid: missing away_goals
        ]})
    finally:
        dio.save_actual_result = orig
    assert ok == 2
    assert len(errs) == 1
    assert saved_calls == [("a", 1, 0), ("b", 2, 2)]
