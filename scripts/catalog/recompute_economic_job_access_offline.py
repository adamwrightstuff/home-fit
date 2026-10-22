#!/usr/bin/env python3
"""
Offline: recompute the economic_opportunity pillar's job-access blend from stored values.

economic_opportunity = 0.55 x job access (gravity over the LODES job grid) + 0.45 x market quality,
or market quality alone when the grid does not cover the place.  Market quality is stored in each
place's economic_opportunity.summary.market_quality_score, so changing the job grid (see
data_sources/job_accessibility.py) needs no API call: this re-reads each place's coordinates, recomputes
job access, and rewrites score, contribution and summary.job_access_score.  Run
recompute_catalog_composites.py --in-place --no-census afterwards so total_score and the composites follow.

  cd /Users/adamwright/Dev/home-fit
  PYTHONPATH=. python3 scripts/catalog/recompute_economic_job_access_offline.py --dry-run
  PYTHONPATH=. python3 scripts/catalog/recompute_economic_job_access_offline.py            # all metros
  PYTHONPATH=. python3 scripts/catalog/recompute_economic_job_access_offline.py --metro boston --metro las_vegas
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from typing import Any, Callable, Dict, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

JOB_WEIGHT, MARKET_WEIGHT = 0.55, 0.45  # keep in step with pillars/economic_opportunity.py


def recompute_place(score: Dict[str, Any], job_access: Callable[[float, float], Optional[float]]) -> Optional[Dict[str, Any]]:
    """Update one place's economic_opportunity in place; returns {'before', 'after', 'ja_before', 'ja_after'}
    or None when the place has no usable economic pillar."""
    eo = (score.get("livability_pillars") or {}).get("economic_opportunity")
    if not eo or not isinstance(eo.get("score"), (int, float)):
        return None
    summary = eo.get("summary") or {}
    mq = summary.get("market_quality_score")
    if not isinstance(mq, (int, float)):
        return None
    coords = score.get("coordinates") or {}
    ja = job_access(coords["lat"], coords["lon"])
    after = round(JOB_WEIGHT * ja + MARKET_WEIGHT * mq, 1) if ja is not None else float(mq)
    info = {"before": eo["score"], "after": after, "ja_before": summary.get("job_access_score"), "ja_after": ja}
    eo["score"] = after
    if isinstance(eo.get("weight"), (int, float)):
        eo["contribution"] = round(eo["weight"] * after / 100.0, 4)
    summary["job_access_score"] = ja
    eo["summary"] = summary
    return info


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--metro", action="append", help="metro key (repeatable); default all")
    ap.add_argument("--dry-run", action="store_true", help="report changes, write nothing")
    args = ap.parse_args()

    from data_sources.job_accessibility import job_access_score

    pattern = os.path.join(ROOT, "data", "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl")
    changed = total = 0
    for path in sorted(glob.glob(pattern)):
        metro = re.match(r"(.+?)_metro_place_catalog", os.path.basename(path)).group(1)
        if args.metro and metro not in args.metro:
            continue
        out, deltas = [], []
        for line in open(path, encoding="utf-8"):
            row = json.loads(line)
            sc = row.get("score")
            info = recompute_place(sc, job_access_score) if isinstance(sc, dict) else None
            if info:
                total += 1
                if info["after"] != info["before"]:
                    changed += 1
                    deltas.append(info["after"] - info["before"])
            out.append(json.dumps(row, ensure_ascii=False))
        mean = sum(deltas) / len(deltas) if deltas else 0.0
        print(f"{metro:13} places changed {len(deltas):4d}   mean change {mean:+6.2f}")
        if not args.dry_run:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(out) + "\n")
    print(f"{changed} of {total} places changed" + (" (dry run, nothing written)" if args.dry_run else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
