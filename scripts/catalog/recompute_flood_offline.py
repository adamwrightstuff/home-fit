#!/usr/bin/env python3
"""
Offline: recompute the climate_risk pillar's flood component from the FEMA snapshot.

Reads data/fema_flood_zones_catalog.json (fetch_fema_flood_snapshot.py), classifies each place's zones
with data_sources.fema_flood (the same code the live pillar uses), and rewrites climate_risk's
flood_zone_pts, flood_zone_score_0_100, summary flood fields, score and contribution.  The score is
min(100, heat + air + flood + trend points), as in pillars/climate_risk.py.  Run
recompute_catalog_composites.py --in-place --no-census afterwards so total_score and composites follow.

  cd /Users/adamwright/Dev/home-fit
  PYTHONPATH=. python3 scripts/catalog/recompute_flood_offline.py --dry-run
  PYTHONPATH=. python3 scripts/catalog/recompute_flood_offline.py                  # all metros
  PYTHONPATH=. python3 scripts/catalog/recompute_flood_offline.py --metro boston   # repeatable
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

from data_sources.fema_flood import FLOOD_MAX_PTS_DEFAULT, flood_zone_from_features  # noqa: E402

FLOOD_MAX_PTS = 30.0  # keep in step with pillars/climate_risk.py
NEUTRAL_FLOOD_PTS = FLOOD_MAX_PTS * 0.5  # the pillar's score when FEMA is unavailable
_PTS_KEYS = ("heat_exposure_pts", "air_quality_pts", "climate_trend_pts")


def recompute_place(score: Dict[str, Any], features: Optional[list]) -> Optional[Dict[str, Any]]:
    """Update one place's climate_risk in place; returns {'before','after','tier'} or None if it cannot be done."""
    cr = (score.get("livability_pillars") or {}).get("climate_risk")
    bd = (cr or {}).get("breakdown") or {}
    if not cr or not isinstance(cr.get("score"), (int, float)) or not all(isinstance(bd.get(k), (int, float)) for k in _PTS_KEYS):
        return None
    flood = flood_zone_from_features(features, FLOOD_MAX_PTS_DEFAULT)
    if flood is None:
        pts, tier, zone, label = NEUTRAL_FLOOD_PTS, None, None, None
    else:
        pts, tier, zone, label = float(flood["flood_zone_pts"]), flood["risk_tier"], flood["fld_zone"], flood["label"]
    pts = round(min(FLOOD_MAX_PTS, max(0.0, pts)), 2)
    before = cr["score"]
    after = round(min(100.0, bd["heat_exposure_pts"] + bd["air_quality_pts"] + pts + bd["climate_trend_pts"]), 1)
    flood_100 = round(pts / FLOOD_MAX_PTS * 100.0, 1)
    bd["flood_zone_pts"] = pts
    bd["flood_zone_score_0_100"] = flood_100
    summary = cr.get("summary") or {}
    summary.update({"flood_zone_score": flood_100, "flood_risk_tier": tier, "fld_zone": zone, "flood_label": label})
    cr["summary"] = summary
    cr["score"] = after
    if isinstance(cr.get("weight"), (int, float)):
        cr["contribution"] = round(cr["weight"] * after / 100.0, 4)
    return {"before": before, "after": after, "tier": tier}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--metro", action="append", help="metro key (repeatable); default all")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    from scripts.catalog.fetch_fema_flood_snapshot import SNAPSHOT, place_key

    places = json.load(open(SNAPSHOT, encoding="utf-8"))["places"]
    changed = total = missing = 0
    for path in sorted(glob.glob(os.path.join(ROOT, "data", "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))):
        metro = re.match(r"(.+?)_metro_place_catalog", os.path.basename(path)).group(1)
        if args.metro and metro not in args.metro:
            continue
        out, deltas, tiers = [], [], {}
        for line in open(path, encoding="utf-8"):
            row = json.loads(line)
            sc = row.get("score")
            if isinstance(sc, dict):
                c = sc.get("coordinates") or {}
                key = place_key(c["lat"], c["lon"]) if "lat" in c and "lon" in c else None
                if places.get(key) is None:  # not in the snapshot, or its FEMA request failed: leave the place as stored
                    missing += 1
                else:
                    info = recompute_place(sc, places[key])
                    if info:
                        total += 1
                        tiers[info["tier"]] = tiers.get(info["tier"], 0) + 1
                        if info["after"] != info["before"]:
                            deltas.append(info["after"] - info["before"])
            out.append(json.dumps(row, ensure_ascii=False))
        changed += len(deltas)
        mean = sum(deltas) / len(deltas) if deltas else 0.0
        print(f"{metro:13} changed {len(deltas):4d}  mean change {mean:+6.2f}  tiers {dict(sorted(tiers.items(), key=lambda kv: str(kv[0])))}")
        if not args.dry_run:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(out) + "\n")
    print(f"{changed} of {total} places changed; {missing} places left as stored (not in the snapshot or the FEMA request failed)" + (" (dry run)" if args.dry_run else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
