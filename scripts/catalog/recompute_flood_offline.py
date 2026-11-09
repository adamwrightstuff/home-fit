#!/usr/bin/env python3
"""
Offline: recompute the climate_risk pillar's flood component from the FEMA snapshot. New files only.

Reads data/fema_flood_zones_catalog.json (fetch_fema_flood_snapshot.py), classifies each place's zones with
data_sources.fema_flood (the same code the live pillar uses) and rewrites climate_risk's flood points, summary, score and
contribution. A place whose flood component cannot be measured (zone D, no mapped polygon, or a FEMA request that failed
and is stored as null) loses the flood component: the score is built from the components that remain and the pillar is
marked degraded, as pillars/climate_risk.py does. A place whose pin is not in the snapshot is left as stored.

Then, per changed place: total_score_breakdown, total_score (by the change in the summed contributions). The happiness index is recomputed afterwards with recompute_happiness_only.py on the written files. Nothing is
written in place; the input files are never modified. No API, Census or Overpass call.

  cd /Users/adamwright/Dev/home-fit/.claude/worktrees/dpv2-climate-risk
  PYTHONPATH=. python3 scripts/catalog/recompute_flood_offline.py --out-dir analysis/climate_dpv2_2026-11-03
  PYTHONPATH=. python3 scripts/catalog/recompute_happiness_only.py analysis/climate_dpv2_2026-11-03/*.jsonl
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from data_sources.fema_flood import FLOOD_MAX_PTS_DEFAULT, flood_zone_from_features  # noqa: E402

# Keep in step with pillars/climate_risk.py (not imported: importing the pillar initializes Earth Engine).
MAX_PTS = {"heat": 25.0, "air": 20.0, "flood": 30.0, "trend": 25.0}
MIN_COMPONENTS = 3
_BD_KEYS = {"heat": "heat_exposure_pts", "air": "air_quality_pts", "trend": "climate_trend_pts"}


def _num(x: Any) -> Optional[float]:
    return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def recompute_place(score: Dict[str, Any], features: Optional[list], request_failed: bool = False) -> Optional[Dict[str, Any]]:
    """
    Update one place's climate_risk in place. features is the snapshot's zone list; request_failed is True when the
    snapshot holds null for the pin. Returns {'before','after','tier'} or None when the place is left as stored.
    """
    cr = (score.get("livability_pillars") or {}).get("climate_risk")
    if not cr or not isinstance(cr.get("score"), (int, float)):
        return None
    bd = cr.get("breakdown") or {}
    pts: Dict[str, Optional[float]] = {k: _num(bd.get(v)) for k, v in _BD_KEYS.items()}
    if request_failed:
        flood = {"flood_zone_pts": None, "risk_tier": None, "fld_zone": None, "label": None}
    else:
        flood = flood_zone_from_features(features, FLOOD_MAX_PTS_DEFAULT)
        if flood is None:
            return None
    pts["flood"] = None if flood["flood_zone_pts"] is None else round(min(MAX_PTS["flood"], max(0.0, float(flood["flood_zone_pts"]))), 2)
    present = [k for k, v in pts.items() if v is not None]
    if len(present) < MIN_COMPONENTS:
        return None
    missing = [k for k in MAX_PTS if k not in present]
    before = cr["score"]
    after = round(min(100.0, sum(pts[k] for k in present) / sum(MAX_PTS[k] for k in present) * 100.0), 1)
    flood_100 = None if pts["flood"] is None else round(pts["flood"] / MAX_PTS["flood"] * 100.0, 1)
    bd["flood_zone_pts"] = pts["flood"]
    bd["flood_zone_score_0_100"] = flood_100
    cr["breakdown"] = bd
    summary = cr.get("summary") or {}
    summary.update({"flood_zone_score": flood_100, "flood_risk_tier": flood["risk_tier"], "fld_zone": flood["fld_zone"],
                    "flood_label": flood["label"], "components_missing": missing})
    cr["summary"] = summary
    dq = cr.get("data_quality") or {}
    reasons = [r for r in (dq.get("degraded_reasons") or []) if not str(r).startswith(("flood_", "climate_risk_missing_components: flood"))]
    if "flood" in missing:
        reasons.append("climate_risk_missing_components: flood")
        reasons.append({"d": "flood_zone_d_undetermined", "unmapped": "flood_no_mapped_polygon"}.get(flood["risk_tier"], "flood_lookup_failed"))
    dq["degraded_reasons"] = list(dict.fromkeys(reasons))
    dq["degraded"] = bool(dq["degraded_reasons"])
    cr["data_quality"] = dq
    cr["score"] = after
    if isinstance(cr.get("weight"), (int, float)):
        cr["contribution"] = round(cr["weight"] * after / 100.0, 4)
    return {"before": before, "after": after, "tier": flood["risk_tier"]}


def update_composites(score: Dict[str, Any]) -> None:
    """Carry a changed climate pillar into total_score_breakdown and total_score (offline)."""
    pillars = score["livability_pillars"]
    cr = pillars["climate_risk"]
    tb = (score.get("total_score_breakdown") or {}).get("climate_risk")
    old_sum = (tb or {}).get("contribution")
    if isinstance(tb, dict):
        tb["score"], tb["contribution"] = cr["score"], cr["contribution"]
    old_total = score.get("total_score")
    if isinstance(old_total, (int, float)) and isinstance(old_sum, (int, float)):
        score["total_score"] = round(old_total + (cr["contribution"] - old_sum), 2)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", required=True, help="new folder for the recomputed files (must be empty or absent)")
    ap.add_argument("--glob", default=os.path.join(ROOT, "data", "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))
    args = ap.parse_args()
    if os.path.isdir(args.out_dir) and os.listdir(args.out_dir):
        sys.exit(f"{args.out_dir} is not empty; new files only")
    os.makedirs(args.out_dir, exist_ok=True)
    from scripts.catalog.fetch_fema_flood_snapshot import SNAPSHOT, place_key

    places = json.load(open(SNAPSHOT, encoding="utf-8"))["places"]
    records: List[Dict[str, Any]] = []
    not_in_snapshot = 0
    for path in sorted(glob.glob(args.glob)):
        metro = re.match(r"(.+?)_metro_place_catalog", os.path.basename(path)).group(1)
        out = []
        for line in open(path, encoding="utf-8"):
            row = json.loads(line)
            sc = row.get("score")
            if isinstance(sc, dict) and (sc.get("livability_pillars") or {}).get("climate_risk"):
                c = sc.get("coordinates") or {}
                key = place_key(c["lat"], c["lon"]) if "lat" in c and "lon" in c else None
                if key not in places:
                    not_in_snapshot += 1
                else:
                    total_before = sc.get("total_score")
                    info = recompute_place(sc, places[key], request_failed=places[key] is None)
                    if info:
                        update_composites(sc)
                        records.append({"metro": metro, "name": (row.get("catalog") or {}).get("name"), "tier": info["tier"],
                                        "climate_before": info["before"], "climate_after": info["after"],
                                        "total_before": total_before, "total_after": sc.get("total_score")})
            out.append(json.dumps(row, ensure_ascii=False))
        with open(os.path.join(args.out_dir, os.path.basename(path)), "w", encoding="utf-8") as f:
            f.write("\n".join(out) + "\n")
    changed = [r for r in records if r["climate_after"] != r["climate_before"]]
    with open(os.path.join(args.out_dir, "diff.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(records[0]))
        w.writeheader()
        w.writerows(records)
    print(f"{len(changed)} of {len(records)} places changed; {not_in_snapshot} left as stored (pin not in the snapshot); wrote {args.out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
