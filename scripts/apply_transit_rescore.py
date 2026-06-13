#!/usr/bin/env python3
"""
Recompute public_transit_access (v2 absolute-supply model) from each catalog place's
stored route counts and cascade into total_score. No network: route counts are stored,
only the scoring math changed. Transit feeds total_score only (happiness 'commute' is an
independent census-commute metric; not in longevity). Writes to a NEW file for review.

New score = 100 * min(1, log(1 + 3*heavy + 2*light + 0.7*bus) / log(1+400)), then the
existing 5% commute-time weighting is preserved by reusing the stored commute_time
component so the recompute matches the live pillar.
"""
from __future__ import annotations

import json
import math
import os
import statistics
import sys

ANCHOR = 250.0
COMMUTE_WEIGHT = 0.05


def abs_supply(weighted):
    if weighted <= 0:
        return 0.0
    return 100.0 * min(1.0, math.log(1.0 + weighted) / math.log(1.0 + ANCHOR))


def recompute(summary, commute_component):
    h = summary.get("heavy_rail_routes") or 0
    l = summary.get("light_rail_routes") or 0
    b = summary.get("bus_routes") or 0
    supply = abs_supply(3.0 * h + 2.0 * l + 0.7 * b)
    # preserve the live pillar's 5% commute-time blend using the stored commute_time score
    if commute_component is not None and commute_component > 0:
        total = supply * (1.0 - COMMUTE_WEIGHT) + commute_component * COMMUTE_WEIGHT
    else:
        total = supply
    return round(min(100.0, max(0.0, total)), 1), abs_supply(3.0 * h), abs_supply(2.0 * l), abs_supply(0.7 * b)


def apply_cascade(sc, new, hs, ls, bs):
    pt = sc["livability_pillars"]["public_transit_access"]
    old = pt["score"]
    pt["score"] = new
    w = pt["weight"]
    pt["contribution"] = round(new * w / 100.0, 4)
    bd = pt.setdefault("breakdown", {})
    bd["heavy_rail"] = round(hs, 1)
    bd["light_rail"] = round(ls, 1)
    bd["bus"] = round(bs, 1)
    pt["_rescore_version"] = "transit_v2_absolute_supply"

    tsb = sc["total_score_breakdown"]["public_transit_access"]
    old_c = tsb["contribution"]
    new_c = round(new * tsb["weight"] / 100.0, 4)
    tsb["score"] = new
    tsb["contribution"] = new_c
    sc["total_score"] = round(sc["total_score"] - old_c + new_c, 4)
    return old, new


def main():
    src = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else src.replace(".jsonl", ".v2transit.jsonl")
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
            pt = sc.get("livability_pillars", {}).get("public_transit_access", {})
            summ = pt.get("summary", {})
            if pt.get("score") is not None and summ:
                commute = pt.get("breakdown", {}).get("commute_time")
                new, hs, ls, bs = recompute(summ, commute)
                o, n = apply_cascade(sc, new, hs, ls, bs)
                shifts.append((o, n))
                n_upd += 1
            else:
                n_skip += 1
            f.write(json.dumps(row) + "\n")
    print(f"Wrote {out}")
    print(f"Updated {n_upd}, skipped {n_skip}")
    if shifts:
        o = [a for a, _ in shifts]; n = [b for _, b in shifts]
        print(f"transit mean {statistics.mean(o):.1f} -> {statistics.mean(n):.1f}  "
              f"stdev {statistics.pstdev(o):.1f} -> {statistics.pstdev(n):.1f}")


if __name__ == "__main__":
    main()
