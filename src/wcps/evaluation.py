"""Historical evaluation metrics.

Compares stored predictions against actual results and computes simple,
numerically safe metrics per model and for the ensemble:

* outcome accuracy;
* exact-score accuracy;
* Brier score (multiclass) for outcome probabilities;
* log loss (clipped) for outcome probabilities.

The output is structured so it can also feed calibration plots later.
"""

from __future__ import annotations

import math
import re
from datetime import date as _date
from typing import Any

from . import data_io
from .schemas import OUTCOME_AWAY, OUTCOME_DRAW, OUTCOME_HOME

_EPS = 1e-12

_DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_CODE_RE = re.compile(r"^[A-Z]{2,4}$")


def actual_outcome(home_goals: int, away_goals: int) -> str:
    if home_goals > away_goals:
        return OUTCOME_HOME
    if home_goals < away_goals:
        return OUTCOME_AWAY
    return OUTCOME_DRAW


def _safe_log(p: float) -> float:
    return math.log(min(1.0, max(_EPS, p)))


def evaluate_prediction(pred: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
    """Per-prediction metrics against one actual result."""
    hg, ag = actual["home_goals"], actual["away_goals"]
    true_outcome = actual_outcome(hg, ag)
    true_score = f"{hg}-{ag}"

    probs = {
        OUTCOME_HOME: pred["prob_home"],
        OUTCOME_DRAW: pred["prob_draw"],
        OUTCOME_AWAY: pred["prob_away"],
    }
    pred_outcome = pred["recommended_outcome"]
    pred_score = pred["recommended_score"]

    # Brier (multiclass): sum over classes of (p - y)^2
    brier = sum(
        (probs[o] - (1.0 if o == true_outcome else 0.0)) ** 2
        for o in (OUTCOME_HOME, OUTCOME_DRAW, OUTCOME_AWAY)
    )
    logloss = -_safe_log(probs[true_outcome])

    return {
        "true_outcome": true_outcome,
        "true_score": true_score,
        "pred_outcome": pred_outcome,
        "pred_score": pred_score,
        "outcome_correct": bool(pred_outcome == true_outcome),
        "score_correct": bool(pred_score == true_score),
        "brier": brier,
        "log_loss": logloss,
        "prob_assigned_true": probs[true_outcome],
    }


def _result_team_codes(match_id: str, result: dict[str, Any]) -> tuple[str, str] | None:
    """Best-effort (home_code, away_code) for a result: explicit fields or id parse.

    Parsing splits the id on non-alphanumerics and takes the two trailing
    all-caps team codes, so it works for ``wc-2026-06-13-QAT-SUI`` regardless of
    the separators or prefix used.
    """
    h, a = result.get("home_team"), result.get("away_team")
    if h and a:
        return (str(h).upper(), str(a).upper())
    codes = [t for t in re.split(r"[^A-Za-z0-9]+", match_id) if _CODE_RE.match(t)]
    return (codes[-2], codes[-1]) if len(codes) >= 2 else None


def _parse_date(s: str | None) -> _date | None:
    """Extract a YYYY-MM-DD date from anywhere in a string (e.g. inside a match_id)."""
    if not s:
        return None
    m = _DATE_RE.search(str(s))
    if not m:
        return None
    try:
        return _date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _index_actuals(actuals: dict[str, dict[str, Any]]) -> dict[frozenset, list[dict[str, Any]]]:
    """Index results by the unordered pair of team codes for orientation-agnostic joins."""
    index: dict[frozenset, list[dict[str, Any]]] = {}
    for mid, r in actuals.items():
        codes = _result_team_codes(mid, r)
        if not codes:
            continue
        rec = {
            "home_code": codes[0],
            "away_code": codes[1],
            "home_goals": r["home_goals"],
            "away_goals": r["away_goals"],
            "date": _parse_date(r.get("date")) or _parse_date(mid),
            "match_id": mid,
        }
        index.setdefault(frozenset(codes), []).append(rec)
    return index


def _match_actual(
    pred_home: str | None,
    pred_away: str | None,
    pred_date: str | None,
    actuals: dict[str, dict[str, Any]],
    actual_index: dict[frozenset, list[dict[str, Any]]],
    match_id: str,
) -> dict[str, Any] | None:
    """Find the actual result for a prediction, oriented to the prediction's home/away.

    Tries an exact ``match_id`` hit first; otherwise joins on the unordered pair
    of team codes (picking the nearest date when a pair recurs) and re-orients
    the goals so ``home_goals``/``away_goals`` always refer to the prediction's
    home/away — making the join robust to differing ``match_id`` conventions,
    reversed fixture order, and the madrugada date shift.
    """
    if match_id in actuals:
        r = actuals[match_id]
        return {"home_goals": r["home_goals"], "away_goals": r["away_goals"]}

    if not (pred_home and pred_away):
        return None
    candidates = actual_index.get(frozenset({pred_home.upper(), pred_away.upper()}))
    if not candidates:
        return None

    pd = _parse_date(pred_date)
    def _dist(c: dict[str, Any]) -> int:
        return abs((c["date"] - pd).days) if (pd and c["date"]) else 0
    cand = min(candidates, key=_dist)

    if cand["home_code"] == pred_home.upper():
        return {"home_goals": cand["home_goals"], "away_goals": cand["away_goals"]}
    # reversed fixture order -> swap goals into the prediction's orientation
    return {"home_goals": cand["away_goals"], "away_goals": cand["home_goals"]}


def result_for_match(
    match: dict[str, Any], actuals: dict[str, dict[str, Any]] | None = None
) -> dict[str, Any] | None:
    """Find the actual result for a scheduled match, oriented to its home/away.

    Same robust join used by :func:`build_history` (exact ``match_id`` first,
    then team pair + nearest date, re-orienting the goals). Use this in the UI so
    final scores show even when the result's ``match_id`` convention differs from
    the match/prediction one.
    """
    actuals = actuals if actuals is not None else data_io.load_actual_results()
    index = _index_actuals(actuals)
    return _match_actual(
        match.get("home_team"), match.get("away_team"), match.get("date"),
        actuals, index, match.get("match_id", ""),
    )


def recent_results_for_team(
    code: str,
    before_date: str | None = None,
    limit: int = 5,
    actuals: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Return a team's most recent finished results (newest first).

    Each row is from ``code``'s perspective: ``{date, opponent, gf, ga,
    outcome ('W'/'D'/'L'), venue ('H'/'A')}``. If ``before_date`` is given, only
    results strictly before it are returned (the team's form *going into* a
    match). Works across differing ``match_id`` conventions via the same parser
    used by the evaluation join.
    """
    code = code.upper()
    actuals = actuals if actuals is not None else data_io.load_actual_results()
    cutoff = _parse_date(before_date) if before_date else None

    rows: list[dict[str, Any]] = []
    for mid, r in actuals.items():
        codes = _result_team_codes(mid, r)
        if not codes or code not in codes:
            continue
        dt = _parse_date(r.get("date")) or _parse_date(mid)
        if cutoff and dt and dt >= cutoff:
            continue
        home, away = codes
        if code == home:
            gf, ga, opp, venue = r["home_goals"], r["away_goals"], away, "H"
        else:
            gf, ga, opp, venue = r["away_goals"], r["home_goals"], home, "A"
        outcome = "W" if gf > ga else "D" if gf == ga else "L"
        rows.append({
            "date": dt.isoformat() if dt else "",
            "_sort": dt or _date.min,
            "opponent": opp, "gf": gf, "ga": ga,
            "outcome": outcome, "venue": venue,
        })
    rows.sort(key=lambda x: x["_sort"], reverse=True)
    for x in rows:
        x.pop("_sort")
    return rows[:limit]


def fifa_ranking_pick(match: dict[str, Any]) -> str | None:
    """Benchmark pick: the better FIFA-ranked team's outcome ('home'/'away').

    Reads ``v1_scores.fifa_ranking`` from the match's daily context (the only
    ranking signal stored). Returns ``None`` when there is no context/ranking or
    the two sides are tied. The pick is mapped to *this match's* home/away even
    if the context stored the fixture in the opposite order. This baseline never
    predicts a draw — it always backs the higher-ranked side to win.
    """
    date, mid = match.get("date"), match.get("match_id")
    entry = data_io.context_for_match(date, mid) if date and mid else None
    if entry is None and date:
        pair = {match.get("home_team"), match.get("away_team")}
        for e in (data_io.load_context(date) or {}).get("matches", []):
            if {e.get("home_team"), e.get("away_team")} == pair:
                entry = e
                break
    if not entry:
        return None
    fr = (entry.get("v1_scores") or {}).get("fifa_ranking") or {}
    try:
        h, a = float(fr.get("home")), float(fr.get("away"))
    except (TypeError, ValueError):
        return None
    if h == a:
        return None
    fav_code = entry.get("home_team") if h > a else entry.get("away_team")
    if fav_code == match.get("home_team"):
        return "home"
    if fav_code == match.get("away_team"):
        return "away"
    return None


def build_history(config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Join every stored prediction with its actual result (if available).

    Returns a flat list of rows, one per (match, source) where source is each
    model id and ``ensemble``. The result join is tolerant of differing
    ``match_id`` conventions, reversed home/away order, and a +/-1 day shift
    (see :func:`_match_actual`). Rows without an actual result are still returned
    (with ``evaluated=False``) so the UI can show pending matches. Each row also
    carries the FIFA-ranking benchmark pick for its match (``fifa_pick`` and,
    when evaluated, ``fifa_pick_correct``).
    """
    actuals = data_io.load_actual_results()
    actual_index = _index_actuals(actuals)
    rows: list[dict[str, Any]] = []

    for date in data_io.available_dates():
        payload = data_io.load_predictions(date)
        if not payload:
            continue
        for match_id, mp in payload.get("predictions", {}).items():
            match = data_io.get_match(match_id) or {}
            actual = _match_actual(
                match.get("home_team"), match.get("away_team"), match.get("date") or date,
                actuals, actual_index, match_id,
            )
            # match-level benchmark + true outcome (shared by all sources)
            fifa_pick = fifa_ranking_pick(match) if match else None
            true_out = (
                actual_outcome(actual["home_goals"], actual["away_goals"])
                if actual is not None else None
            )

            sources = dict(mp.get("models", {}))
            sources["ensemble"] = mp.get("ensemble", {})
            for source, pred in sources.items():
                if not pred:
                    continue
                row = {
                    "date": date,
                    "match_id": match_id,
                    "home_team": match.get("home_team"),
                    "away_team": match.get("away_team"),
                    "phase": match.get("phase"),
                    "source": source,
                    "is_demo": match.get("is_demo", False),
                    "evaluated": actual is not None,
                    "fifa_pick": fifa_pick,
                }
                if actual is not None:
                    row.update(evaluate_prediction(pred, actual))
                    row["fifa_pick_correct"] = (
                        (fifa_pick == true_out) if fifa_pick else None
                    )
                rows.append(row)
    return rows


def benchmark_summary(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Compare each source's outcome accuracy to the FIFA-ranking benchmark.

    Restricted to the **same subset** of matches: those that are evaluated AND
    have a benchmark pick (i.e. a daily context with FIFA-ranking scores). Returns
    ``None`` when no such matches exist. ``by_source`` holds each source's
    win-accuracy over that subset, and ``benchmark_accuracy`` is how often the
    higher-ranked team actually won.
    """
    applicable = [r for r in rows if r.get("evaluated") and r.get("fifa_pick")]
    if not applicable:
        return None
    by_match = {r["match_id"]: bool(r.get("fifa_pick_correct")) for r in applicable}
    n = len(by_match)
    by_source: dict[str, list[bool]] = {}
    for r in applicable:
        by_source.setdefault(r["source"], []).append(bool(r["outcome_correct"]))
    return {
        "n": n,
        "benchmark_accuracy": sum(by_match.values()) / n,
        "by_source": {s: sum(v) / len(v) for s, v in by_source.items()},
    }


def team_source_accuracy(
    code: str, rows: list[dict[str, Any]]
) -> dict[str, Any]:
    """Per-model winner accuracy over every evaluated match involving a team.

    Returns ``{"sources": {src: {n, accuracy}}, "benchmark": {n, accuracy}|None,
    "n_matches": int}`` where accuracy is the outcome hit-rate restricted to
    matches that featured ``code`` (home or away). The benchmark is the
    FIFA-ranking baseline over the same team's matches that have a pick.
    """
    code = code.upper()
    involved = [
        r for r in rows
        if r.get("evaluated") and code in (r.get("home_team"), r.get("away_team"))
    ]
    by_source: dict[str, list[bool]] = {}
    for r in involved:
        by_source.setdefault(r["source"], []).append(bool(r["outcome_correct"]))
    sources = {
        s: {"n": len(v), "accuracy": sum(v) / len(v)} for s, v in by_source.items()
    }
    by_match = {
        r["match_id"]: bool(r.get("fifa_pick_correct"))
        for r in involved if r.get("fifa_pick")
    }
    benchmark = (
        {"n": len(by_match), "accuracy": sum(by_match.values()) / len(by_match)}
        if by_match else None
    )
    return {
        "sources": sources,
        "benchmark": benchmark,
        "n_matches": len({r["match_id"] for r in involved}),
    }


def summarize_by_source(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Aggregate metrics per source (model id / ensemble) over evaluated rows."""
    summary: dict[str, dict[str, Any]] = {}
    by_source: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        if r.get("evaluated"):
            by_source.setdefault(r["source"], []).append(r)

    for source, items in by_source.items():
        n = len(items)
        if n == 0:
            continue
        summary[source] = {
            "n": n,
            "outcome_accuracy": sum(i["outcome_correct"] for i in items) / n,
            "exact_score_accuracy": sum(i["score_correct"] for i in items) / n,
            "mean_brier": sum(i["brier"] for i in items) / n,
            "mean_log_loss": sum(i["log_loss"] for i in items) / n,
        }
    return summary
