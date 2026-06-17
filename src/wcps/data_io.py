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
