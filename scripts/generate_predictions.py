#!/usr/bin/env python
"""CLI: generate WCPS predictions for one date or all scheduled dates.

Examples
--------
    # one date
    python scripts/generate_predictions.py --date 2026-06-17

    # every date that has scheduled matches
    python scripts/generate_predictions.py --all

    # validate context only, do not write predictions
    python scripts/generate_predictions.py --date 2026-06-17 --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make src/ importable without installation.
_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from wcps import data_io, pipeline  # noqa: E402
from wcps.config import ensure_data_dirs  # noqa: E402
from wcps.context import validate_context  # noqa: E402


def _report_validation(date: str) -> None:
    ctx = data_io.load_context(date)
    result = validate_context(ctx)
    status = "OK" if result.ok else "ERRORS"
    print(f"  context: {status}", end="")
    if ctx is None:
        print(" (no context file — neutral assumptions)")
        return
    n_warn = sum(len(w) for w in result.per_match.values()) + len(result.warnings)
    print(f" ({n_warn} warning(s))")
    for err in result.errors:
        print(f"    ! {err}")


def run_date(date: str, dry_run: bool) -> None:
    matches = data_io.matches_for_date(date)
    print(f"[{date}] {len(matches)} match(es)")
    _report_validation(date)
    if not matches:
        print("  no matches scheduled — skipped")
        return
    payload = pipeline.generate_for_date(date, save=not dry_run)
    for mid, mp in payload["predictions"].items():
        ens = mp["ensemble"]
        print(
            f"  - {mid}: {ens['recommended_outcome']:>4} "
            f"{ens['recommended_score']} "
            f"(H {ens['prob_home']:.0%} / D {ens['prob_draw']:.0%} / "
            f"A {ens['prob_away']:.0%})"
        )
    if dry_run:
        print("  [dry-run] predictions NOT written")
    else:
        print(f"  saved -> {data_io.predictions_path(date)}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate WCPS predictions.")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--date", help="Single date YYYY-MM-DD")
    g.add_argument("--all", action="store_true", help="All scheduled dates")
    ap.add_argument("--dry-run", action="store_true",
                    help="Validate and simulate without writing prediction files")
    args = ap.parse_args()

    ensure_data_dirs()
    dates = data_io.available_dates() if args.all else [args.date]
    if not dates:
        print("No scheduled dates found.")
        return 1
    for date in dates:
        run_date(date, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
