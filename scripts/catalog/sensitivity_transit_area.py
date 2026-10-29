#!/usr/bin/env python3
"""
Offline sensitivity (DPv2 P6) of the area-average transit score to its judgment parameters, from the saved sample
points (refetch_transit_sample_points.py) and commuter rail distances (refetch_commuter_rail_distance.py). No API calls.
Varies one parameter at a time across its recorded range at the shipped anchor 44.42 and reports the per-place change in
transit points (median / 95th percentile / max) and the change in the catalog mean. Radii cannot be varied offline
(counts exist only at 800 m and 1,200 m); a different radius needs a re-fetch.

  cd /Users/adamwright/Dev/home-fit && PYTHONPATH=. python3 scripts/catalog/sensitivity_transit_area.py
"""
from __future__ import annotations

import glob
import json
import math
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.catalog.recompute_transit_v3_area_offline import BONUS_KEYS, row_key  # noqa: E402

ANCHOR = 44.42
BASE = {"subway": 3.0, "commuter": 3.0, "light": 2.0, "bus": 0.7}
CREDIT_BASE = [(1200, 1.0), (4490, 0.5), (7930, 0.25), (9980, 0.0)]
CREDIT_75 = [(1200, 1.0), (4490, 0.5), (7930, 0.0)]  # cut off at the 75th percentile instead of the 85th


def load(p):
    return {json.loads(l)["key"]: json.loads(l) for l in open(ROOT / p)}


def credit(d, pts):
    if d <= pts[0][0]:
        return 1.0
    for (a, fa), (b, fb) in zip(pts, pts[1:]):
        if d <= b:
            return fa + (fb - fa) * (d - a) / (b - a)
    return 0.0


def score(points, d, bonus, w, pts):
    out = []
    for p in points:
        rail = w["commuter"] * p["commuter_rail"] if p["commuter_rail"] > 0 else (0.0 if d is None else w["commuter"] * credit(d, pts))
        x = w["subway"] * p["subway"] + w["light"] * p["light_rail"] + w["bus"] * p["bus"] + rail
        out.append(0.0 if x <= 0 else 100.0 * min(1.0, math.log(1 + x) / math.log(1 + ANCHOR)))
    return min(100.0, st.mean(out) + bonus)


def main():
    sp, cr = load("analysis/transit_sample_points.jsonl"), load("analysis/commuter_rail_distance.jsonl")
    rows = []
    for fn in sorted(glob.glob(str(ROOT / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))):
        for line in open(fn):
            rec = json.loads(line)
            t = ((rec.get("score") or {}).get("livability_pillars") or {}).get("public_transit_access")
            k = row_key(fn, rec)
            if not t or t.get("score") is None or k not in sp or k not in cr:
                continue
            near = cr[k]["nearest"]
            rows.append((sp[k]["points"], near[0]["m"] if near else None,
                         sum((t.get("breakdown") or {}).get(x) or 0 for x in BONUS_KEYS)))
    base = [score(p, d, b, BASE, CREDIT_BASE) for p, d, b in rows]
    print(f"{len(rows)} places, catalog mean {st.mean(base):.1f}\n")
    print("parameter (range)                         median / 95th / max per-place change   catalog mean change")
    variants = []
    for name, key, vals in (("commuter rail weight", "commuter", (2.0, 4.0)), ("light rail weight", "light", (1.0, 3.0)),
                            ("subway weight", "subway", (2.0, 4.0)), ("bus weight", "bus", (0.5, 1.0))):
        for v in vals:
            variants.append((f"{name} {v}", {**BASE, key: v}, CREDIT_BASE))
    variants.append(("commuter drive credit cut at 4.93 mi", BASE, CREDIT_75))
    variants.append(("no commuter drive credit", {**BASE}, [(1200, 1.0), (1201, 0.0)]))
    for label, w, pts in variants:
        new = [score(p, d, b, w, pts) for p, d, b in rows]
        ch = sorted(abs(a - b) for a, b in zip(new, base))
        print(f"{label:40s} {st.median(ch):5.1f} / {ch[int(len(ch) * .95)]:5.1f} / {ch[-1]:5.1f}      {st.mean(new) - st.mean(base):+.1f}")


if __name__ == "__main__":
    main()
