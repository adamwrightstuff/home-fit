#!/usr/bin/env python3
"""
Re-score housing_value for the locations whose pin resolved a broken census geography.

CONFIRMED root cause (evidence): these pins landed in empty/water/park/commercial tracts
(Southport -> water tract 990000 pop 0; Pelham Bay -> park; Maspeth -> pop 0) OR the April
build's census fetch transiently failed (Chinatown/Glendale tracts have real data now). All
showed median_home_value=0 / fallback_applied=True / confidence<=40 — fabricated.

Fix lives in census_api.get_housing_data (swaps an empty tract for the nearest populated one);
this re-runs get_housing_value_score for the affected places and cascades total_score.
Targets are detected (confidence<=40), not hardcoded. Backup .bakHousing.

Usage: python3 scripts/fix_housing_empty_tracts.py
"""
from __future__ import annotations
import json, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pillars.housing_value import get_housing_value_score  # noqa

CATALOGS = ["data/nyc_metro_place_catalog_scores_merged.jsonl",
            "data/la_metro_place_catalog_scores_merged.jsonl"]
PILLAR = "housing_value"


def main():
    shifts = []
    for fn in CATALOGS:
        if not os.path.isfile(fn):
            continue
        shutil.copyfile(fn, fn + ".bakHousing")
        tmp = fn + ".new"
        n = 0
        with open(fn) as src, open(tmp, "w") as out:
            for line in src:
                try:
                    row = json.loads(line)
                except Exception:
                    out.write(line); continue
                sc = row.get("score", {})
                hv = sc.get("livability_pillars", {}).get(PILLAR)
                cat = row.get("catalog", {})
                conf = hv.get("confidence") if hv else None
                if hv and isinstance(conf, (int, float)) and conf <= 40:
                    try:
                        new, det = get_housing_value_score(float(cat["lat"]), float(cat["lon"]))
                    except Exception as e:
                        print(f"   ERROR {cat.get('name')}: {e}", flush=True)
                        out.write(json.dumps(row) + "\n"); continue
                    if new is not None:
                        old = hv["score"]
                        w = hv.get("weight") or 0.0
                        hv["score"] = round(new, 1)
                        hv["contribution"] = round(new * w / 100.0, 4)
                        hv["confidence"] = det.get("confidence", 70) if isinstance(det, dict) else 70
                        hv["_rescore_version"] = "housing_empty_tract_fix"
                        tsb = sc.get("total_score_breakdown", {}).get(PILLAR)
                        if tsb:
                            oc = tsb["contribution"]
                            nc = round(new * (tsb.get("weight") or 0.0) / 100.0, 4)
                            tsb["score"] = round(new, 1); tsb["contribution"] = nc
                            sc["total_score"] = round(sc["total_score"] - oc + nc, 4)
                        shifts.append((cat.get("name", ""), old, round(new, 1)))
                        n += 1
                out.write(json.dumps(row) + "\n")
        os.replace(tmp, fn)
        print(f"{fn}: re-scored {n} (backup: {fn}.bakHousing)", flush=True)
    print("\nfixed:")
    for nm, o, nw in sorted(shifts, key=lambda x: x[0]):
        print(f"   {nm:14s} {o} -> {nw}", flush=True)


if __name__ == "__main__":
    main()
