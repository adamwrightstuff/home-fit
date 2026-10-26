#!/usr/bin/env python3
"""
Education data-limit flags (DPv2 P9 and P11), offline, from stored levels. Scores are not changed.

  PYTHONPATH=. python3 scripts/catalog/flag_education_data_limits.py [--dry-run]

Per place with a score:
  - a level with no rated school (and not a choice level, which is intentional): the pillar is marked degraded with
    "quality_education_levels_missing" (score is from the remaining levels).
  - a level scored from the 2015-16 NCES attendance survey: data_warnings "zone_map_2015_16" (the doc records 90% agreement
    with current maps in 143 checks, so about 10% of those zones may have changed).
  - a level scored from the nearest schools because no zone map covers the point: data_warnings "no_zone_map".
Idempotent: earlier flags of these three kinds are removed first. The pin_sensitive warning is left alone.
"""
from __future__ import annotations

import argparse
import glob
import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PREFIXES = ("zone_map_2015_16", "no_zone_map")
DEGRADED_PREFIX = "quality_education_levels_missing"


def apply(p: dict) -> dict:
    bd = p.get("breakdown") or {}
    lv = bd.get("levels") or {}
    dq = p.setdefault("data_quality", {})
    warns = [w for w in (dq.get("data_warnings") or []) if not str(w).startswith(PREFIXES)]
    reasons = [r for r in (dq.get("degraded_reasons") or []) if not str(r).startswith(DEGRADED_PREFIX)]
    missing = [k for k, v in lv.items() if v.get("score") is None and v.get("source") != "choice"
               and (v.get("pool") or {}).get("scope") != "citywide"]
    old = [k for k, v in lv.items() if v.get("source") == "zone" and (v.get("zone") or {}).get("vintage") == "2015-16"]
    near = [k for k, v in lv.items() if v.get("source") in ("nearest", "district_far")]
    if missing:
        reasons.append(f"{DEGRADED_PREFIX}: no rated school at {', '.join(missing)}; scored from the other levels")
    if old:
        warns.append(f"zone_map_2015_16: {', '.join(old)} use the 2015-16 attendance survey; about 10% of those zones may have changed")
    if near:
        warns.append(f"no_zone_map: {', '.join(near)} scored from the nearest schools because no zone map covers the point")
    dq["data_warnings"], dq["degraded_reasons"] = warns, reasons
    if missing:
        dq["degraded"] = True
    elif dq.get("degraded") and not reasons:
        dq["degraded"] = False
    return {"missing": bool(missing), "old": bool(old), "near": bool(near)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    tot = {"missing": 0, "old": 0, "near": 0}
    for path in sorted(glob.glob(os.path.join(REPO, "data", "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))):
        out = []
        for line in open(path):
            row = json.loads(line)
            p = ((row.get("score") or {}).get("livability_pillars") or {}).get("quality_education")
            if p and p.get("score") is not None:
                for k, v in apply(p).items():
                    tot[k] += v
            out.append(json.dumps(row, ensure_ascii=False))
        if not args.dry_run:
            with open(path + ".tmp", "w") as f:
                f.write("\n".join(out) + "\n")
            os.replace(path + ".tmp", path)
    print(f"places flagged: degraded (missing level) {tot['missing']}, 2015-16 zone {tot['old']}, no zone map {tot['near']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
