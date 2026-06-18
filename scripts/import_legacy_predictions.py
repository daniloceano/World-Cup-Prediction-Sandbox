#!/usr/bin/env python
"""CLI: import legacy ChatGPT predictions, mapped onto the official schedule.

Reads ``data/predictions/legacy_chat_predictions.json`` (never modified) and
maps each legacy prediction onto the matching fixture in ``data/raw/matches.json``
by the unordered pair of team codes. The official schedule is the source of
truth for the ``match_id``, the **slate date** (06:00->06:00 window) and the
home/away orientation, so:

* predictions are filed under the correct match day (madrugada-aware);
* their ``match_id`` matches the canonical ``wc-YYYY-MM-DD-HOME-AWAY`` ids used
  by the results file (exact-id evaluation join);
* fixtures whose legacy order was reversed are re-oriented automatically.

Imported predictions are a read-only ``chatgpt_legacy`` source. The importer is
idempotent and safe to re-run. Run:

    python scripts/import_legacy_predictions.py
"""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from wcps import config, data_io, legacy  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Import legacy ChatGPT predictions.")
    ap.add_argument(
        "--legacy-file",
        default=str(config.path("predictions_dir") / "legacy_chat_predictions.json"),
        help="Path to the legacy export JSON.",
    )
    args = ap.parse_args()

    legacy_path = Path(args.legacy_file)
    if not legacy_path.exists():
        print(f"Legacy file not found: {legacy_path}")
        return 1

    cfg = config.load_config()
    config.ensure_data_dirs()
    q = cfg["quantiles"]

    # Official schedule = source of truth, indexed by the unordered team pair.
    sched_by_pair = {
        frozenset({m["home_team"], m["away_team"]}): m
        for m in data_io.load_matches()
    }

    raw = json.loads(legacy_path.read_text(encoding="utf-8"))
    entries = legacy.deduplicate(raw.get("predictions", []))

    by_date: dict[str, dict] = {}
    matched, unmatched = 0, []

    for e in entries:
        hc = legacy.team_code(e.get("team_a", ""))
        ac = legacy.team_code(e.get("team_b", ""))
        sched = sched_by_pair.get(frozenset({hc, ac}))
        if not sched:
            unmatched.append(f"{hc} vs {ac} ({e.get('match_id')})")
            continue

        pred = legacy.convert_entry(e, cfg, str(legacy_path))
        if pred is None:
            unmatched.append(f"{hc} vs {ac} (no available legacy model)")
            continue
        pdict = pred.to_dict()

        # Re-orient to the official home/away order when the legacy order differs.
        if sched["home_team"] != hc:
            pdict = legacy.reorient_prediction(pdict, q["lower"], q["upper"])
        pdict["match_id"] = sched["match_id"]

        ens = deepcopy(pdict)
        ens["model_id"] = "ensemble"
        ens["model_version"] = "legacy-passthrough"
        ens["warnings"] = ["Single-source ensemble from legacy import."]

        date = sched["date"]
        payload = by_date.setdefault(date, {
            "date": date,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "context_available": False,
            "context_valid": False,
            "context_warnings": True,
            "has_legacy_source": True,
            "predictions": {},
        })
        payload["predictions"][sched["match_id"]] = {
            "match_id": sched["match_id"],
            "models": {legacy.LEGACY_SOURCE_ID: pdict},
            "ensemble": ens,
        }
        matched += 1

    for date, payload in by_date.items():
        payload["n_matches"] = len(payload["predictions"])
        data_io.save_predictions(date, payload)

    print(f"Legacy export: {len(raw.get('predictions', []))} entries "
          f"-> {len(entries)} unique fixtures")
    print(f"  mapped onto schedule: {matched} prediction(s) "
          f"across {len(by_date)} date(s)")
    if unmatched:
        print(f"  unmatched (no scheduled fixture): {len(unmatched)}")
        for u in unmatched:
            print(f"    - {u}")
    print("Original legacy export left unmodified (audit trail).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
