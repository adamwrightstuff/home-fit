#!/usr/bin/env python3
"""
Recompute air_travel_access for the catalog under the commute-time band model.

The prior model plateaued at 100 within 25km of a hub AND summed the best 3 airports, so
every place in a multi-airport metro saturated (all 105 LA places scored exactly 100 —
zero differentiation while consuming a full pillar's weight). The new model scores from
estimated drive time to the best reachable airport (area-type-aware speed x road
circuity), capped by service level, with a small bonus for a second hub within ~60 min.

Offline + deterministic: airports are a static file and distance is haversine, so this
reproduces what the live pillar computes — no network, no rate-limit risk. Air travel
feeds only total_score (not happiness/longevity/status), so the cascade is pillar
contribution -> total_score, using each place's CURRENT weight (post education-enable).

Backup .bakAir. Usage: python3 scripts/rescore_air_travel.py
"""
from __future__ import annotations

import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pillars.air_travel_access import get_air_travel_score  # noqa: E402

CATALOGS = [
    "data/nyc_metro_place_catalog_scores_merged.jsonl",
    "data/la_metro_place_catalog_scores_merged.jsonl",
]
PILLAR = "air_travel_access"


def area_type_of(sc: dict) -> str | None:
    return (sc.get("data_quality_summary", {})
            .get("area_classification", {}).get("effective_area_type"))


def main():
    shifts = []
    for fn in CATALOGS:
        if not os.path.isfile(fn):
            continue
        shutil.copyfile(fn, fn + ".bakAir")
        tmp = fn + ".new"
        n = 0
        with open(fn) as src, open(tmp, "w") as out:
            for line in src:
                try:
                    row = json.loads(line)
                except Exception:
                    out.write(line)
                    continue
                cat = row.get("catalog", {})
                sc = row.get("score", {})
                ta = sc.get("livability_pillars", {}).get(PILLAR)
                try:
                    lat, lon = float(cat["lat"]), float(cat["lon"])
                except (TypeError, ValueError, KeyError):
                    out.write(json.dumps(row) + "\n")
                    continue
                if ta:
                    new, _det = get_air_travel_score(lat, lon, area_type=area_type_of(sc))
                    new = round(new, 1)
                    old = ta["score"]
                    w = ta.get("weight") or 0.0
                    ta["score"] = new
                    ta["contribution"] = round(new * w / 100.0, 4)
                    ta["_rescore_version"] = "air_travel_commute_bands"
                    tsb = sc.get("total_score_breakdown", {}).get(PILLAR)
                    if tsb:
                        oc = tsb["contribution"]
                        nc = round(new * (tsb.get("weight") or 0.0) / 100.0, 4)
                        tsb["score"] = new
                        tsb["contribution"] = nc
                        sc["total_score"] = round(sc["total_score"] - oc + nc, 4)
                    shifts.append((cat.get("name", ""), old, new))
                    n += 1
                out.write(json.dumps(row) + "\n")
        os.replace(tmp, fn)
        print(f"{fn}: rescored {n} places (backup: {fn}.bakAir)", flush=True)

    import numpy as np
    vals = np.array([n for _, _, n in shifts])
    print(f"\nnew air_travel distribution: min={vals.min():.0f} median={np.median(vals):.0f} "
          f"max={vals.max():.0f} std={vals.std():.1f}  (was: LA all=100, std=0)", flush=True)


if __name__ == "__main__":
    main()
