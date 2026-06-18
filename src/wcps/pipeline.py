"""Prediction pipeline — generate, persist and load predictions for a date.

Flow:
    matches (schedule) + daily context  ->  each active model  ->  ensemble
                                          ->  saved JSON payload  ->  UI / eval

The payload for a date is a dict keyed by ``match_id`` with the individual model
predictions and the ensemble, all stored using the standardized schema. Original
context files are never modified — they remain the audit trail.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from . import data_io
from .config import load_config
from .context import validate_context
from .ensemble import combine
from .models import REGISTRY
from .schemas import Prediction


def predict_match(
    match: dict[str, Any],
    context_entry: dict[str, Any] | None,
    config: dict[str, Any] | None = None,
    context_ref: str | None = None,
) -> dict[str, Any]:
    """Run all active models + ensemble for one match. Returns a serializable dict."""
    config = config or load_config()
    models = REGISTRY.active_models(config)

    model_preds: list[Prediction] = [
        m.predict(match, context_entry, context_ref) for m in models
    ]
    ensemble_pred = combine(model_preds, config, match["match_id"], context_ref)

    return {
        "match_id": match["match_id"],
        "models": {p.model_id: p.to_dict() for p in model_preds},
        "ensemble": ensemble_pred.to_dict(),
    }


def generate_for_date(
    date: str, config: dict[str, Any] | None = None, save: bool = True
) -> dict[str, Any]:
    """Generate predictions for every match scheduled on ``date``.

    Returns the full payload and (optionally) persists it to
    ``data/predictions/<date>.json``.
    """
    config = config or load_config()
    context = data_io.load_context(date)
    # Register any fixtures/teams the context describes (Prompt A metadata) so a
    # date can be predicted without hand-editing the schedule. No-op for older
    # minimal context files.
    data_io.sync_schedule_from_context(context)
    matches = data_io.matches_for_date(date)
    validation = validate_context(context)
    context_ref = str(data_io.context_path(date)) if context else None

    # Preserve any already-stored predictions (e.g. imported legacy sources),
    # so regenerating live models never clobbers them.
    existing = (data_io.load_predictions(date) or {}).get("predictions", {})
    ctx_by_id = {e.get("match_id"): e for e in (context or {}).get("matches", [])}

    predictions: dict[str, Any] = {}
    for match in matches:
        mid = match["match_id"]
        ctx_entry = ctx_by_id.get(mid)
        prev = existing.get(mid)
        if ctx_entry is not None:
            # Context available -> run live models, but keep any existing
            # read-only source (e.g. imported chatgpt_legacy) alongside them.
            result = predict_match(match, ctx_entry, config, context_ref)
            live_ids = set(REGISTRY.ids())
            for sid, sp in (prev or {}).get("models", {}).items():
                if sid not in result["models"] and sid not in live_ids:
                    result["models"][sid] = sp
            predictions[mid] = result
        elif prev is not None:
            # No context: never fabricate neutral live predictions; keep what
            # is already stored (imported legacy, etc.).
            predictions[mid] = prev
        # else: no context and nothing stored -> leave this match unpredicted.

    payload = {
        "date": date,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "context_available": context is not None,
        "context_valid": validation.ok,
        "context_warnings": validation.has_warnings,
        "n_matches": len(predictions),
        "predictions": predictions,
    }

    if save and predictions:
        data_io.save_predictions(date, payload)
    return payload


def get_or_generate(date: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return cached predictions for a date, generating them on first access."""
    existing = data_io.load_predictions(date)
    if existing:
        return existing
    return generate_for_date(date, config)
