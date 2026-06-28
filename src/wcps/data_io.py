"""Data input/output for WCPS.

Simple JSON/CSV-backed persistence (no database required in v1). All readers
fail gracefully — a missing file yields an empty collection rather than an
exception — so the app stays usable while data is incrementally added.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import config


# --- low-level helpers ------------------------------------------------------
def _read_json(p: Path, default: Any) -> Any:
    if not p.exists():
        return default
    with p.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_json(p: Path, data: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


# --- teams ------------------------------------------------------------------
def load_teams() -> dict[str, dict[str, Any]]:
    """Return a mapping ``code -> team metadata``."""
    raw = _read_json(config.path("teams_file"), {"teams": []})
    return {t["code"]: t for t in raw.get("teams", [])}


# --- matches (schedule) -----------------------------------------------------
def load_matches() -> list[dict[str, Any]]:
    """Return the full list of scheduled matches."""
    raw = _read_json(config.path("matches_file"), {"matches": []})
    return raw.get("matches", [])


def matches_for_date(date: str) -> list[dict[str, Any]]:
    """Return matches scheduled on ``date`` (``YYYY-MM-DD``)."""
    return [m for m in load_matches() if m.get("date") == date]


def get_match(match_id: str) -> dict[str, Any] | None:
    for m in load_matches():
        if m.get("match_id") == match_id:
            return m
    return None


def upsert_team_records(records: list[dict[str, Any]]) -> int:
    """Insert/merge team records (keyed by ``code``). Returns number added."""
    p = config.path("teams_file")
    raw = _read_json(p, {"teams": []})
    by_code = {t["code"]: t for t in raw.get("teams", [])}
    added = 0
    for rec in records:
        code = rec.get("code")
        if not code:
            continue
        if code not in by_code:
            added += 1
        by_code[code] = {**by_code.get(code, {}), **rec}
    raw["teams"] = sorted(by_code.values(), key=lambda t: t["code"])
    _write_json(p, raw)
    return added


def upsert_match_records(records: list[dict[str, Any]]) -> int:
    """Insert/merge match records (keyed by ``match_id``). Returns number added."""
    p = config.path("matches_file")
    raw = _read_json(p, {"matches": []})
    by_id = {m["match_id"]: m for m in raw.get("matches", [])}
    added = 0
    for rec in records:
        mid = rec.get("match_id")
        if not mid:
            continue
        if mid not in by_id:
            added += 1
        by_id[mid] = {**by_id.get(mid, {}), **rec}
    raw["matches"] = sorted(
        by_id.values(), key=lambda m: (m.get("date") or "", m["match_id"])
    )
    _write_json(p, raw)
    return added


def schedule_records_from_context(
    ctx: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Build (team_records, match_records) from a daily context. Pure, no I/O.

    Entries missing ``match_id`` or team codes are skipped, keeping older
    minimal context files backward-compatible.
    """
    if not ctx:
        return ([], [])
    top_date = ctx.get("date")
    matches: list[dict[str, Any]] = []
    teams: list[dict[str, Any]] = []
    for e in ctx.get("matches", []):
        mid = e.get("match_id")
        home, away = e.get("home_team"), e.get("away_team")
        if not (mid and home and away):
            continue
        kickoff = ""
        kt = e.get("kickoff_utc") or ""
        if "T" in kt:
            kickoff = kt.split("T")[1][:5] + " UTC"
        matches.append({
            "match_id": mid,
            "date": e.get("date") or top_date,
            "kickoff": kickoff,
            "venue": e.get("venue"),
            "phase": e.get("phase") or "group",
            "group": e.get("group"),
            "home_team": home,
            "away_team": away,
            "is_demo": False,
            "source": "daily_context",
        })
        if e.get("home_name"):
            teams.append({"code": home, "name": e["home_name"], "is_demo": False})
        if e.get("away_name"):
            teams.append({"code": away, "name": e["away_name"], "is_demo": False})
    return (teams, matches)


def sync_schedule_from_context(ctx: dict[str, Any] | None) -> tuple[int, int]:
    """Register fixtures/teams described in a daily context into the schedule.

    The daily context (Prompt A) carries per-match metadata (teams, kickoff,
    venue, group). This upserts them into ``matches.json`` / ``teams.json`` so
    predictions can run for a date without manually editing the schedule.
    Returns (teams_added, matches_added).
    """
    teams, matches = schedule_records_from_context(ctx)
    n_teams = upsert_team_records(teams) if teams else 0
    n_matches = upsert_match_records(matches) if matches else 0
    return (n_teams, n_matches)


def available_dates() -> list[str]:
    """Sorted unique dates that have at least one scheduled match."""
    return sorted({m["date"] for m in load_matches() if m.get("date")})


# --- daily context ----------------------------------------------------------
def context_path(date: str) -> Path:
    return config.path("context_dir") / f"{date}.json"


def load_context(date: str) -> dict[str, Any] | None:
    """Load the daily context JSON for a date, or None if it is absent."""
    p = context_path(date)
    if not p.exists():
        return None
    return _read_json(p, None)


def split_context_by_date(
    ctx: dict[str, Any], default_date: str | None = None
) -> dict[str, list[dict[str, Any]]]:
    """Group a context's matches by each match's slate ``date``.

    Supports the round prompt (matches spanning several dates) and the single-day
    prompt alike. Matches without a ``date`` fall back to the doc's top-level
    ``date`` or ``default_date``.
    """
    groups: dict[str, list[dict[str, Any]]] = {}
    top = ctx.get("date") or default_date
    for m in ctx.get("matches", []):
        d = m.get("date") or top
        if d:
            groups.setdefault(d, []).append(m)
    return groups


def save_context_by_date(
    ctx: dict[str, Any], default_date: str | None = None
) -> list[str]:
    """Write/merge a (possibly multi-date) context into per-date context files.

    Each date's file is merged by ``match_id`` (new entries override). Returns the
    sorted list of dates written. This is how the round prompt's single paste
    becomes the per-date ``data/context/YYYY-MM-DD.json`` files the app expects.
    """
    groups = split_context_by_date(ctx, default_date)
    written: list[str] = []
    for date, entries in groups.items():
        existing = load_context(date) or {"date": date, "matches": []}
        by_id = {e.get("match_id"): e for e in existing.get("matches", [])}
        for m in entries:
            by_id[m.get("match_id")] = m
        existing["date"] = date
        existing["matches"] = [v for k, v in by_id.items() if k]
        for meta_key in ("generated_by", "timezone", "round"):
            if meta_key in ctx and meta_key not in existing:
                existing[meta_key] = ctx[meta_key]
        _write_json(context_path(date), existing)
        written.append(date)
    return sorted(written)


def context_for_match(date: str, match_id: str) -> dict[str, Any] | None:
    """Return the per-match context block from a day's context file."""
    ctx = load_context(date)
    if not ctx:
        return None
    for entry in ctx.get("matches", []):
        if entry.get("match_id") == match_id:
            return entry
    return None


# --- predictions ------------------------------------------------------------
def predictions_path(date: str) -> Path:
    return config.path("predictions_dir") / f"{date}.json"


def save_predictions(date: str, payload: dict[str, Any]) -> Path:
    """Persist a day's prediction payload (per match: models + ensemble)."""
    p = predictions_path(date)
    _write_json(p, payload)
    return p


def load_predictions(date: str) -> dict[str, Any] | None:
    p = predictions_path(date)
    if not p.exists():
        return None
    return _read_json(p, None)


# --- actual results ---------------------------------------------------------
def load_actual_results() -> dict[str, dict[str, Any]]:
    """Return ``match_id -> {home_goals, away_goals, ...}``."""
    raw = _read_json(config.path("actual_results_file"), {"results": []})
    return {r["match_id"]: r for r in raw.get("results", [])}


def save_actual_result(
    match_id: str, home_goals: int, away_goals: int, **extra: Any
) -> None:
    """Insert or update a single actual result, preserving the rest."""
    p = config.path("actual_results_file")
    raw = _read_json(p, {"results": []})
    results = [r for r in raw.get("results", []) if r["match_id"] != match_id]
    record = {"match_id": match_id, "home_goals": int(home_goals),
              "away_goals": int(away_goals)}
    record.update(extra)
    results.append(record)
    _write_json(p, {"results": results})


def get_actual_result(match_id: str) -> dict[str, Any] | None:
    return load_actual_results().get(match_id)


def ingest_results(payload: Any) -> tuple[int, list[str]]:
    """Ingest a Prompt B results payload (or bare list) into actual_results.json.

    Accepts either ``{"results": [...]}`` or a plain list of result objects, each
    with ``match_id``, ``home_goals``, ``away_goals`` (plus optional
    ``status``/``notes``). Upserts by ``match_id``. Returns (count_saved, errors).
    """
    if isinstance(payload, dict):
        items = payload.get("results", [])
    elif isinstance(payload, list):
        items = payload
    else:
        return (0, ["Top-level JSON must be an object with 'results' or a list."])

    saved = 0
    errors: list[str] = []
    for i, r in enumerate(items):
        try:
            mid = r["match_id"]
            hg, ag = int(r["home_goals"]), int(r["away_goals"])
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(f"Result #{i + 1}: {exc}")
            continue
        extra = {k: r[k] for k in ("status", "notes") if k in r}
        save_actual_result(mid, hg, ag, **extra)
        saved += 1
    return (saved, errors)
