#!/usr/bin/env python3
"""
Offline: move stored natural beauty from the six-component OWA score to the two-part score
(streets: green view + canopy; scenery: terrain + water), no API calls, no GEE.

Reads each place's stored v9_breakdown component scores (so earlier offline patches to water, region
and so on are kept), applies pillars.natural_beauty.nb_two_part, and rewrites natural_beauty score,
contribution, details.score_v9 and the breakdown's blend fields.  Idempotent: a place already marked
method=two_part_v10 is recomputed from the same components and gives the same result.  Run
recompute_catalog_composites.py --in-place --no-census afterwards.

  cd /Users/adamwright/Dev/home-fit
  PYTHONPATH=. python3 scripts/catalog/recompute_natural_beauty_two_part_offline.py --dry-run
  PYTHONPATH=. python3 scripts/catalog/recompute_natural_beauty_two_part_offline.py
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from typing import Any, Dict, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

_OLD_KEYS = ("owa_components", "owa_score", "weights")


def recompute_place(score: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Recompute one place in place; returns {'before','after'} or None when the stored data cannot support it."""
    from pillars import natural_beauty as NB

    nb = (score.get("livability_pillars") or {}).get("natural_beauty")
    if not nb or not isinstance(nb.get("score"), (int, float)):
        return None
    details = nb.get("details") or {}
    # Older batch runs (NYC, LA) keep the breakdown at the pillar root or under breakdown.
    v9 = next((c for c in (details.get("v9_breakdown"), nb.get("v9_breakdown"),
                           (nb.get("breakdown") or {}).get("v9_breakdown"))
               if isinstance(c, dict) and "gvi_score" in c), None)
    if v9 is None:
        return None
    i = v9.get("inputs") or {}
    missing = NB.streets_inputs_missing(i.get("gvi_pct"), i.get("canopy_pct"))
    parts = NB.nb_two_part(v9, None, None, streets_missing=missing)
    if not parts:
        return None
    before = nb["score"]
    nb["score"] = parts["score"]
    details["score_v9"] = parts["score"]
    details.setdefault("score_before_two_part", before)
    v9["method"] = "two_part_v10"
    v9["streets_score"] = parts["streets"]
    v9["scenery_score"] = parts["scenery"]
    v9["blend_raw"] = parts["blend"]
    v9["streets_share"] = parts["streets_share"]
    v9["low_confidence"] = True if missing else None
    v9["missing_parts"] = ["streets"] if missing else None
    for k in _OLD_KEYS:
        v9.pop(k, None)
    details["scoring_formula"] = NB.NATURAL_BEAUTY_SCORING_FORMULA
    if "scoring_formula" in nb:  # older batches (NYC, LA) also keep the stamp at the pillar root
        nb["scoring_formula"] = NB.NATURAL_BEAUTY_SCORING_FORMULA
    nb["details"] = details
    if isinstance(nb.get("weight"), (int, float)):
        nb["contribution"] = round(nb["weight"] * nb["score"] / 100.0, 4)
    return {"before": before, "after": nb["score"]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--metro", action="append", help="metro key (repeatable); default all")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    changed = 0
    for path in sorted(glob.glob(os.path.join(ROOT, "data", "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))):
        metro = re.match(r"(.+?)_metro_place_catalog", os.path.basename(path)).group(1)
        if args.metro and metro not in args.metro:
            continue
        out, deltas = [], []
        for line in open(path, encoding="utf-8"):
            row = json.loads(line)
            sc = row.get("score")
            info = recompute_place(sc) if isinstance(sc, dict) else None
            if info:
                deltas.append(info["after"] - info["before"])
            out.append(json.dumps(row, ensure_ascii=False))
        if deltas:
            print(f"{metro:13} recomputed {len(deltas):3d}  mean change {sum(deltas) / len(deltas):+6.2f}")
        changed += len(deltas)
        if deltas and not args.dry_run:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(out) + "\n")
    print(f"{changed} places recomputed" + (" (dry run, nothing written)" if args.dry_run else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
