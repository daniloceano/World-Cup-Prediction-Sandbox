"""Import legacy ChatGPT predictions as a read-only ``chatgpt_legacy`` source.

The legacy export (``data/predictions/legacy_chat_predictions.json``) comes from a
previous ChatGPT conversation and uses a different schema: full team names,
``team_a_win`` / ``team_b_win`` orientation, only the top scorelines (no full
distribution or quantiles), some reversed-order duplicate fixtures, and a few
``modal_score`` values like ``"0-1 / 1-1"``.

This module converts each legacy entry into the standardized :class:`Prediction`
so it can be displayed and evaluated alongside the live models — **without**
re-running anything. The original export file is never modified; it remains the
audit trail. Imported predictions carry ``model_id="chatgpt_legacy"`` and are
flagged ``quality="degraded"`` because their scoreline distribution is partial.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from .schemas import OUTCOME_AWAY, OUTCOME_DRAW, OUTCOME_HOME, Prediction
from .simulation import stat_summary

LEGACY_SOURCE_ID = "chatgpt_legacy"

# Full team name -> 3-letter code (FIFA-style). Extend as new teams appear.
NAME_TO_CODE: dict[str, str] = {
    "qatar": "QAT", "switzerland": "SUI", "brazil": "BRA", "morocco": "MAR",
    "haiti": "HAI", "scotland": "SCO", "germany": "GER", "curacao": "CUW",
    "netherlands": "NED", "japan": "JPN", "ivory coast": "CIV", "ecuador": "ECU",
    "sweden": "SWE", "tunisia": "TUN", "spain": "ESP", "cape verde": "CPV",
    "belgium": "BEL", "egypt": "EGY", "saudi arabia": "KSA", "uruguay": "URU",
    "iran": "IRN", "new zealand": "NZL", "france": "FRA", "senegal": "SEN",
    "iraq": "IRQ", "norway": "NOR", "argentina": "ARG", "algeria": "ALG",
    "austria": "AUT", "jordan": "JOR",
}

_OUTCOME_MAP = {
    "team_a_win": OUTCOME_HOME,
    "draw": OUTCOME_DRAW,
    "team_b_win": OUTCOME_AWAY,
}


def team_code(name: str) -> str:
    """Map a full team name to a 3-letter code (fallback: first 3 letters)."""
    key = name.strip().lower()
    if key in NAME_TO_CODE:
        return NAME_TO_CODE[key]
    letters = "".join(c for c in name if c.isalpha())
    return (letters[:3] or "UNK").upper()


def _active_model_block(entry: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    """Return (version_tag, model_block) for whichever legacy model is available."""
    models = entry.get("models", {})
    for mid in ("model_v2", "model_v1"):  # prefer the strategic model when present
        block = models.get(mid)
        if block and block.get("available"):
            return ("legacy-" + mid.replace("model_", ""), block)
    return None


def _scoreline_dict(block: dict[str, Any]) -> dict[str, float]:
    """Build a (renormalized) partial scoreline distribution from the top lists."""
    merged: dict[str, float] = {}
    for key in ("top_scorelines_overall", "top_scorelines_within_most_likely_outcome"):
        for item in block.get(key, []) or []:
            score = item.get("score")
            prob = item.get("probability")
            if score and "-" in score and prob is not None:
                merged[score] = max(merged.get(score, 0.0), float(prob))
    if not merged:
        rec = block.get("recommended_score")
        if rec and "-" in rec:
            merged[rec] = 1.0
    total = sum(merged.values()) or 1.0
    return {k: v / total for k, v in merged.items()}


def _top_list(items: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    out = []
    for it in items or []:
        if it.get("score") and it.get("probability") is not None:
            out.append({"score": it["score"], "prob": float(it["probability"])})
    return out


def _stats_from_scoreline(
    scoreline: dict[str, float], lower_q: float, upper_q: float
) -> dict[str, dict[str, float]]:
    if not scoreline:
        return {}
    scores = list(scoreline.keys())
    w = np.array([scoreline[s] for s in scores], dtype=float)
    gh = np.array([int(s.split("-")[0]) for s in scores])
    ga = np.array([int(s.split("-")[1]) for s in scores])
    total = gh + ga
    diff = gh - ga
    pts_h = np.where(diff > 0, 3, np.where(diff == 0, 1, 0))
    pts_a = np.where(diff < 0, 3, np.where(diff == 0, 1, 0))
    return {
        "goals_home": stat_summary(gh, lower_q, upper_q, w).to_dict(),
        "goals_away": stat_summary(ga, lower_q, upper_q, w).to_dict(),
        "total_goals": stat_summary(total, lower_q, upper_q, w).to_dict(),
        "goal_diff": stat_summary(diff, lower_q, upper_q, w).to_dict(),
        "points_home": stat_summary(pts_h, lower_q, upper_q, w).to_dict(),
        "points_away": stat_summary(pts_a, lower_q, upper_q, w).to_dict(),
    }


def convert_entry(
    entry: dict[str, Any], config: dict[str, Any], context_ref: str
) -> Prediction | None:
    """Convert one legacy prediction entry into a standardized Prediction."""
    active = _active_model_block(entry)
    if active is None:
        return None
    version_tag, block = active
    q = config["quantiles"]

    probs = block.get("outcome_probabilities", {})
    p_home = float(probs.get("team_a_win") or 0.0)
    p_draw = float(probs.get("draw") or 0.0)
    p_away = float(probs.get("team_b_win") or 0.0)
    s = p_home + p_draw + p_away
    if s > 0:
        p_home, p_draw, p_away = p_home / s, p_draw / s, p_away / s

    rec_outcome = _OUTCOME_MAP.get(block.get("recommended_outcome"), OUTCOME_HOME)
    rec_score = block.get("recommended_score") or "0-0"

    warnings = [
        "Imported from a legacy ChatGPT export (read-only).",
        f"Underlying legacy model: {version_tag}.",
        "Scoreline distribution is partial (top scorelines only); "
        "summary statistics are approximate.",
    ]

    modal = block.get("modal_score") or rec_score
    if "/" in modal:  # e.g. "0-1 / 1-1": ambiguous tie reported in the conversation
        warnings.append(f"Legacy modal score was ambiguous ({modal!r}); used first value.")
        modal = modal.split("/")[0].strip()
    for note in block.get("extraction_notes", []) or []:
        warnings.append(f"Note: {note}")

    scoreline = _scoreline_dict(block)
    stats = _stats_from_scoreline(scoreline, q["lower"], q["upper"])
    lam_home = stats.get("goals_home", {}).get("mean", 0.0)
    lam_away = stats.get("goals_away", {}).get("mean", 0.0)

    ordered = sorted(probs and [p_home, p_draw, p_away], reverse=True)
    confidence = float(ordered[0] - ordered[1]) if len(ordered) >= 2 else 0.0

    return Prediction(
        model_id=LEGACY_SOURCE_ID,
        model_version=version_tag,
        match_id=entry["match_id"],
        run_datetime=entry.get("prediction_date") or entry.get("match_date") or "",
        context_ref=context_ref,
        prob_home=p_home,
        prob_draw=p_draw,
        prob_away=p_away,
        scoreline_probs=scoreline,
        recommended_outcome=rec_outcome,
        recommended_score=rec_score,
        modal_score=modal,
        top_scorelines=_top_list(block.get("top_scorelines_overall"))
        or _top_list(block.get("top_scorelines_within_most_likely_outcome")),
        top_scorelines_in_outcome=_top_list(
            block.get("top_scorelines_within_most_likely_outcome")
        ),
        stats=stats,
        lambda_home=lam_home,
        lambda_away=lam_away,
        confidence=confidence,
        quality="degraded",
        warnings=warnings,
    )


def _swap_score(score: str) -> str:
    """'2-1' -> '1-2'."""
    x, y = score.split("-")
    return f"{y}-{x}"


def reorient_prediction(
    pred: dict[str, Any], lower_q: float, upper_q: float
) -> dict[str, Any]:
    """Mirror a prediction to the opposite home/away orientation.

    Used when the legacy fixture order differs from the official schedule (e.g.
    legacy stored Ecuador-home but the official fixture is Côte d'Ivoire-home).
    Swaps the home/away probabilities, every scoreline, the recommendations and
    the effective lambdas, then recomputes the summary stats from the swapped
    scoreline distribution. The draw probability and total-goals stats are
    orientation-invariant and remain correct.
    """
    p = dict(pred)
    p["prob_home"], p["prob_away"] = p["prob_away"], p["prob_home"]
    p["scoreline_probs"] = {_swap_score(s): v for s, v in p["scoreline_probs"].items()}
    p["recommended_outcome"] = {
        "home": "away", "away": "home", "draw": "draw",
    }[p["recommended_outcome"]]
    p["recommended_score"] = _swap_score(p["recommended_score"])
    p["modal_score"] = _swap_score(p["modal_score"])
    p["top_scorelines"] = [
        {"score": _swap_score(t["score"]), "prob": t["prob"]} for t in p["top_scorelines"]
    ]
    p["top_scorelines_in_outcome"] = [
        {"score": _swap_score(t["score"]), "prob": t["prob"]}
        for t in p["top_scorelines_in_outcome"]
    ]
    p["lambda_home"], p["lambda_away"] = p["lambda_away"], p["lambda_home"]
    p["stats"] = _stats_from_scoreline(p["scoreline_probs"], lower_q, upper_q)
    return p


def _completeness(entry: dict[str, Any]) -> int:
    """Score how complete a legacy entry is (for de-duplicating reversed copies)."""
    active = _active_model_block(entry)
    if not active:
        return -1
    _, block = active
    return (len(block.get("top_scorelines_overall", []) or [])
            + len(block.get("top_scorelines_within_most_likely_outcome", []) or []))


def deduplicate(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse reversed-order duplicate fixtures, keeping the most complete one."""
    best: dict[tuple, dict[str, Any]] = {}
    for e in entries:
        key = (
            e.get("match_date"),
            frozenset({e.get("team_a", ""), e.get("team_b", "")}),
            e.get("kickoff_time"),
        )
        if key not in best or _completeness(e) > _completeness(best[key]):
            best[key] = e
    # preserve original order by first appearance of each key
    seen: set[tuple] = set()
    out: list[dict[str, Any]] = []
    for e in entries:
        key = (
            e.get("match_date"),
            frozenset({e.get("team_a", ""), e.get("team_b", "")}),
            e.get("kickoff_time"),
        )
        if key not in seen:
            seen.add(key)
            out.append(best[key])
    return out


def to_match_record(entry: dict[str, Any]) -> dict[str, Any]:
    """Build a schedule record (matches.json shape) from a legacy entry."""
    kickoff = ""
    kt = entry.get("kickoff_time") or ""
    if "T" in kt:
        kickoff = kt.split("T")[1].replace("Z", "").rstrip(":0") or kt.split("T")[1]
        kickoff = kt.split("T")[1][:5] + " UTC"
    return {
        "match_id": entry["match_id"],
        "date": entry.get("match_date"),
        "kickoff": kickoff,
        "venue": entry.get("venue"),
        "phase": entry.get("phase") or "group",
        "group": entry.get("group"),
        "home_team": team_code(entry.get("team_a", "")),
        "away_team": team_code(entry.get("team_b", "")),
        "is_demo": False,
        "source": "legacy_chat_import",
    }


def collect_teams(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return team metadata records for every team in the legacy entries."""
    teams: dict[str, dict[str, Any]] = {}
    for e in entries:
        for name in (e.get("team_a"), e.get("team_b")):
            if not name:
                continue
            code = team_code(name)
            teams[code] = {"code": code, "name": name, "is_demo": False}
    return list(teams.values())
