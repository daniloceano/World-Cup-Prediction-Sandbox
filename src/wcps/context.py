"""Validation for the daily context JSON files.

Each morning the user pastes a ChatGPT-generated (or hand-written) context file
into ``data/context/YYYY-MM-DD.json``. This module checks structure and flags
missing fields so the app can clearly show when a prediction was generated with
incomplete context.

Validation is intentionally lenient: missing strategic fields fall back to
neutral defaults (so a prediction can still run) but produce warnings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# The seven v1 criteria (see methodology §1.1).
V1_CRITERIA = (
    "fifa_ranking",
    "short_form",
    "long_form",
    "injuries",
    "weather_adaptation",
    "off_field",
    "tactical_similarity",
)


@dataclass
class ValidationResult:
    """Outcome of validating one context file."""

    ok: bool
    errors: list[str] = field(default_factory=list)        # block prediction
    warnings: list[str] = field(default_factory=list)      # degrade quality
    per_match: dict[str, list[str]] = field(default_factory=dict)  # match warnings

    @property
    def has_warnings(self) -> bool:
        return bool(self.warnings) or any(self.per_match.values())


def validate_context(ctx: dict[str, Any] | None) -> ValidationResult:
    """Validate a full daily-context document."""
    if ctx is None:
        return ValidationResult(ok=False, errors=["No context file found for this date."])

    errors: list[str] = []
    warnings: list[str] = []
    per_match: dict[str, list[str]] = {}

    if "date" not in ctx:
        warnings.append("Top-level 'date' field is missing.")
    matches = ctx.get("matches")
    if not isinstance(matches, list) or not matches:
        errors.append("Context has no 'matches' array (or it is empty).")
        return ValidationResult(ok=False, errors=errors, warnings=warnings)

    for entry in matches:
        mid = entry.get("match_id", "<unknown>")
        per_match[mid] = validate_match_context(entry)

    return ValidationResult(
        ok=not errors, errors=errors, warnings=warnings, per_match=per_match
    )


def validate_match_context(entry: dict[str, Any]) -> list[str]:
    """Validate one match block; return a list of warning strings (may be empty)."""
    warnings: list[str] = []
    if "match_id" not in entry:
        warnings.append("Missing 'match_id'.")

    scores = entry.get("v1_scores", {})
    if not scores:
        warnings.append("Missing 'v1_scores' — v1 will treat the match as a toss-up.")
    else:
        for crit in V1_CRITERIA:
            if crit not in scores:
                warnings.append(f"v1_scores missing criterion '{crit}' (treated as 0).")
            else:
                cell = scores[crit]
                for side in ("home", "away"):
                    val = cell.get(side) if isinstance(cell, dict) else None
                    if val is None:
                        warnings.append(f"v1_scores.{crit}.{side} missing (treated as 0).")
                    elif not -1.0 <= float(val) <= 1.0:
                        warnings.append(f"v1_scores.{crit}.{side}={val} outside [-1, 1].")

    if "v2_strategic" not in entry:
        warnings.append("Missing 'v2_strategic' — v2 falls back to neutral strategy.")

    return warnings


def coerce_v1_scores(entry: dict[str, Any]) -> dict[str, dict[str, float]]:
    """Return v1 scores with missing criteria/sides filled with neutral 0.0."""
    raw = entry.get("v1_scores", {}) or {}
    out: dict[str, dict[str, float]] = {}
    for crit in V1_CRITERIA:
        cell = raw.get(crit, {}) or {}
        out[crit] = {
            "home": float(cell.get("home", 0.0) or 0.0),
            "away": float(cell.get("away", 0.0) or 0.0),
        }
    return out
