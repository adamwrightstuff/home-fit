#!/usr/bin/env python3
"""
Recompute neighborhood_amenities (v3 amenity-access model) from each catalog place's
stored business_list and cascade into total_score + longevity_index. No network: the
OSM query is unchanged, so the stored business_list is valid input; only the scoring
math changed. Writes to a NEW file for review.

Cascades (both linear, verified): total contribution = score*weight/100;
longevity factor = stored_contribution/score (constant ~0.2551). Amenities does not
feed a happiness component, so happiness_index is untouched.
"""
from __future__ import annotations

import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pillars.neighborhood_amenities import (  # noqa: E402
    _score_walkable_density, _score_walkable_variety, _score_essentials_proximity,
    _T1_DAILY, _T2_SOCIAL, _T3_CULTURE, _T4_SERVICES,
)

WALK_M = 800


def recompute(business_list):
    walk = [b for b in business_list if (b.get("distance_m") or 9999) <= WALK_M]
    t1 = [b for b in walk if b.get("type") in _T1_DAILY]
    t2 = [b for b in walk if b.get("type") in _T2_SOCIAL]
    t3 = [b for b in walk if b.get("type") in _T3_CULTURE]
    t4 = [b for b in walk if b.get("type") in _T4_SERVICES]
    dens = _score_walkable_density(walk, 50)
    var = _score_walkable_variety(t1, t2, t3, t4, 25)
    prox = _score_essentials_proximity(walk, 25)
    return round(dens + var + prox, 1), dens, var, prox, len(walk)


def apply_cascade(sc, new, dens, var, prox, nwalk):
    na = sc["livability_pillars"]["neighborhood_amenities"]
    old = na["score"]
    na["score"] = new
    w = na["weight"]
    na["contribution"] = round(new * w / 100.0, 4)
    bd = na.setdefault("breakdown", {})
    hw = bd.setdefault("home_walkability", {})
    hw["score"] = new  # full amenity-access score (drives frontend narrative)
    hw["breakdown"] = {"density": dens, "variety": var, "proximity": prox}
    hw["businesses_within_walk"] = nwalk
    na["_rescore_version"] = "amenities_v3_walkable_density"

    tsb = sc["total_score_breakdown"]["neighborhood_amenities"]
    old_c = tsb["contribution"]
    new_c = round(new * tsb["weight"] / 100.0, 4)
    tsb["score"] = new
    tsb["contribution"] = new_c
    sc["total_score"] = round(sc["total_score"] - old_c + new_c, 4)

    lb = sc.get("longevity_index_breakdown")
    if lb and "neighborhood_amenities" in lb and old:
        factor = lb["neighborhood_amenities"] / old
        old_l = lb["neighborhood_amenities"]
        new_l = round(new * factor, 4)
        lb["neighborhood_amenities"] = new_l
        if "neighborhood_amenities" in sc.get("longevity_index_contributions", {}):
            sc["longevity_index_contributions"]["neighborhood_amenities"] = new_l
        sc["longevity_index"] = round(sc.get("longevity_index", 0) - old_l + new_l, 4)
    return old, new


def main():
    src = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else src.replace(".jsonl", ".v3amen.jsonl")
    n_upd = n_skip = 0
    shifts = []
    with open(out, "w") as f:
        for line in open(src):
            try:
                row = json.loads(line)
            except Exception:
                f.write(line)
                continue
            sc = row.get("score", {})
            na = sc.get("livability_pillars", {}).get("neighborhood_amenities", {})
            bl = na.get("business_list") or na.get("breakdown", {}).get("business_list")
            if bl is not None and na.get("score") is not None:
                new, dens, var, prox, nwalk = recompute(bl)
                o, n = apply_cascade(sc, new, dens, var, prox, nwalk)
                shifts.append((o, n))
                n_upd += 1
            else:
                n_skip += 1
            f.write(json.dumps(row) + "\n")
    print(f"Wrote {out}")
    print(f"Updated {n_upd}, skipped {n_skip}")
    if shifts:
        o = [a for a, _ in shifts]; n = [b for _, b in shifts]
        print(f"amenities mean {statistics.mean(o):.1f} -> {statistics.mean(n):.1f}  "
              f"stdev {statistics.pstdev(o):.1f} -> {statistics.pstdev(n):.1f}")


if __name__ == "__main__":
    main()
