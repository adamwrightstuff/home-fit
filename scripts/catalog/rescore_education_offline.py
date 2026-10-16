#!/usr/bin/env python3
"""
Re-score quality_education for catalog places from the local SchoolDigger snapshot: no API calls.

Uses pillars.schools.get_school_data with each place's stored early-education bonus (so no OpenStreetMap
query either). Rewrites the pillar's score, breakdown, by_level, summary; run enable_education_weight.py,
recompute_catalog_composites.py --no-census and check_education.py afterwards.

  PYTHONPATH=. python3 scripts/catalog/rescore_education_offline.py [--metro la] [--dry-run]

Needs data_cache/schooldigger_snapshot/<ST>.json.gz (fetch_school_snapshot.py) for each state.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)
from data_sources import school_snapshot  # noqa: E402
from data_sources.schools_api import normalize_state  # noqa: E402
from pillars.schools import get_school_data, summary_extras  # noqa: E402

METROS = ("nyc", "la", "sf", "seattle", "austin", "chicago")
VERSION = "zoned_v1_snapshot"


def _area_type(sc: dict) -> str:
    for v in (sc.get("livability_pillars") or {}).values():
        if isinstance(v, dict):
            a = (v.get("area_classification") or {}).get("area_type") or (v.get("details") or {}).get("area_type")
            if a:
                return a
    return "suburban"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--metro", choices=METROS, action="append")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    for m in args.metro or METROS:
        path = os.path.join(REPO, "data", f"{m}_metro_place_catalog_scores_merged.composites_recomputed.jsonl")
        out, changed, skipped = [], 0, 0
        for line in open(path):
            row = json.loads(line)
            sc, cat = row.get("score") or {}, row.get("catalog") or {}
            p = (sc.get("livability_pillars") or {}).get("quality_education")
            st = normalize_state((sc.get("location_info") or {}).get("state"))
            try:
                lat, lon = float(cat["lat"]), float(cat["lon"])
            except (KeyError, TypeError, ValueError):
                lat = lon = None
            if p is None or lat is None or not school_snapshot.load_state(st):
                skipped += 1
                out.append(line.rstrip("\n"))
                continue
            early = (p.get("breakdown") or {}).get("early_ed_bonus")
            score, by_level, bd = get_school_data(
                (sc.get("location_info") or {}).get("zip"), st, (sc.get("location_info") or {}).get("city"),
                lat, lon, _area_type(sc), cat.get("name"),
                early_ed_bonus_override=float(early) if early is not None else None)
            if bd.get("model") != "zoned_v1":
                skipped += 1
                out.append(line.rstrip("\n"))
                continue
            p["score"] = score
            p["breakdown"] = bd
            p["by_level"] = by_level
            p["total_schools_rated"] = bd.get("total_schools_rated")
            p["summary"] = {**(p.get("summary") or {}), "base_avg_rating": round(bd.get("base_avg_rating", 0), 2),
                            "total_schools_rated": bd.get("total_schools_rated", 0),
                            "excellent_schools_count": bd.get("excellent_schools_count", 0),
                            "early_ed_bonus": round(bd.get("early_ed_bonus", 0), 2), **summary_extras(bd)}
            p["_rescore_version"] = VERSION
            changed += 1
            out.append(json.dumps(row, ensure_ascii=False))
        print(f"{m}: rescored {changed}, skipped {skipped}")
        if not args.dry_run:
            tmp = path + ".tmp"
            with open(tmp, "w") as f:
                f.write("\n".join(out) + "\n")
            os.replace(tmp, path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
