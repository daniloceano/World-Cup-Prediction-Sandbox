"""Standardized data schemas for WCPS.

Plain ``dataclasses`` are used (no heavy validation dependency). Every model —
v1, v2, and any future model — must return a :class:`Prediction`. The ensemble
reuses the same schema so individual and ensemble outputs are interchangeable
in the UI and on disk.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

# Canonical outcome labels used everywhere in the project.
OUTCOME_HOME = "home"
OUTCOME_DRAW = "draw"
OUTCOME_AWAY = "away"
OUTCOMES = (OUTCOME_HOME, OUTCOME_DRAW, OUTCOME_AWAY)


@dataclass
class StatSummary:
    """Summary statistics for a single simulated quantity (e.g. total goals)."""

    mean: float
    median: float
    lower: float          # value at the configured lower quantile
    upper: float          # value at the configured upper quantile
    lower_q: float        # the lower quantile level used (e.g. 0.05)
    upper_q: float        # the upper quantile level used (e.g. 0.95)

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass
class Prediction:
    """Standardized prediction object produced by every model and the ensemble.

    All probabilities are in [0, 1]. Scorelines are keyed as ``"x-y"`` strings
    (home-away). Summary statistics are stored per quantity in ``stats``.
    """

    # --- identity ----------------------------------------------------------
    model_id: str                       # e.g. "v1", "v2", "ensemble"
    model_version: str                  # e.g. "1.0.0"
    match_id: str
    run_datetime: str                   # ISO-8601 UTC timestamp
    context_ref: str | None             # path/key of the daily context used

    # --- outcome probabilities --------------------------------------------
    prob_home: float
    prob_draw: float
    prob_away: float

    # --- scoreline distribution -------------------------------------------
    scoreline_probs: dict[str, float]   # "x-y" -> probability (truncated/sparse)

    # --- recommendations ---------------------------------------------------
    recommended_outcome: str            # one of OUTCOMES
    recommended_score: str              # "x-y"
    modal_score: str                    # most probable single scoreline
    top_scorelines: list[dict[str, Any]]            # [{"score","prob"}...]
    top_scorelines_in_outcome: list[dict[str, Any]]  # within recommended outcome

    # --- summary statistics (median / quantiles / mean) -------------------
    stats: dict[str, dict[str, float]] = field(default_factory=dict)
    # keys: goals_home, goals_away, total_goals, goal_diff, points_home, points_away

    # --- diagnostics -------------------------------------------------------
    lambda_home: float = 0.0            # expected goals used for the home team
    lambda_away: float = 0.0
    confidence: float = 0.0             # 0..1, margin of the preferred outcome
    quality: str = "ok"                # "ok" | "degraded" | "missing_context"
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Prediction":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in d.items() if k in known})

    @property
    def outcome_probs(self) -> dict[str, float]:
        return {
            OUTCOME_HOME: self.prob_home,
            OUTCOME_DRAW: self.prob_draw,
            OUTCOME_AWAY: self.prob_away,
        }
