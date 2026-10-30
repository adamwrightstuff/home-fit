#!/usr/bin/env python3
"""
Offline: recompute natural beauty (V9) for places whose natural-beauty REGION changed.

V9 normalizes green-view index and tree canopy against a regional median (pillars/natural_beauty.py,
_get_nb_region).  Each stored place keeps the region it was scored with in
details.v9_breakdown.region.  This re-derives the region from the place's coordinates with the current
lookup and, only where it differs from the stored one, re-runs _apply_v9_formula on the stored tree
analysis (no API calls, no GEE) and rewrites natural_beauty score, contribution, details.score_v9 and
details.v9_breakdown.  Places whose region is unchanged are left untouched, so unrelated drift is never
mixed in.  Run recompute_catalog_composites.py --in-place --no-census afterwards.

  cd /Users/adamwright/Dev/home-fit
  PYTHONPATH=. python3 scripts/catalog/recompute_natural_beauty_region_offline.py --dry-run
  PYTHONPATH=. python3 scripts/catalog/recompute_natural_beauty_region_offline.py --metro las_vegas
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


def recompute_place(score: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Recompute one place in place when its region changed; returns {'region_before','region_after',
    'before','after'} or None when nothing needed doing (or the stored data cannot support it)."""
    from pillars import natural_beauty as NB

    nb = (score.get("livability_pillars") or {}).get("natural_beauty")
    if not nb or not isinstance(nb.get("score"), (int, float)):
        return None
    details = nb.get("details") or {}
    v9 = details.get("v9_breakdown") or {}
    stored_region = v9.get("region")
    coords = score.get("coordinates") or {}
    if stored_region is None or "lat" not in coords or "lon" not in coords:
        return None
    new_region = NB._get_nb_region(coords["lat"], coords["lon"])
    if new_region == stored_region:
        return None
    tree = details.get("tree_analysis") or {}
    if not (tree.get("natural_context") or {}).get("component_scores"):
        return None
    try:
        new_score, new_v9 = NB._apply_v9_formula({}, tree, lat=coords["lat"], lon=coords["lon"])
    except NB.NaturalBeautyNoData:
        return None  # a no-data place is the fail-loud script's to handle; leave it as stored
    before = nb["score"]
    nb["score"] = round(float(new_score), 2)
    details["score_v9"] = round(float(new_score), 2)
    details["v9_breakdown"] = new_v9
    nb["details"] = details
    if isinstance(nb.get("weight"), (int, float)):
        nb["contribution"] = round(nb["weight"] * nb["score"] / 100.0, 4)
    return {"region_before": stored_region, "region_after": new_region, "before": before, "after": nb["score"]}


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
        out, deltas, moves = [], [], {}
        for line in open(path, encoding="utf-8"):
            row = json.loads(line)
            sc = row.get("score")
            info = recompute_place(sc) if isinstance(sc, dict) else None
            if info:
                deltas.append(info["after"] - info["before"])
                k = f"{info['region_before']}->{info['region_after']}"
                moves[k] = moves.get(k, 0) + 1
            out.append(json.dumps(row, ensure_ascii=False))
        if deltas:
            print(f"{metro:13} recomputed {len(deltas):3d}  mean change {sum(deltas) / len(deltas):+6.2f}  {moves}")
        changed += len(deltas)
        if deltas and not args.dry_run:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(out) + "\n")
    print(f"{changed} places recomputed" + (" (dry run, nothing written)" if args.dry_run else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
