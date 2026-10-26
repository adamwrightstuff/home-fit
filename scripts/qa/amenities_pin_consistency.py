#!/usr/bin/env python3
"""
Re-validation check (DPv2 P12) for neighborhood amenities: does each stored business list match the stored pin?

A business list is measured from the pin the place was scored at. If a place's stored coordinates later changed (or the
list came from another place), the stored distances disagree with distances recomputed from the stored coordinates.
Reads the catalog only (no network). Prints places whose median disagreement exceeds the threshold (default 100 m).

  PYTHONPATH=. python3 scripts/qa/amenities_pin_consistency.py [--threshold-m 100]
Exit code 1 if any place is flagged.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def hav(a, b, c, d):
    p = math.pi / 180
    x = math.sin((c - a) * p / 2) ** 2 + math.cos(a * p) * math.cos(c * p) * math.sin((d - b) * p / 2) ** 2
    return 12742000 * math.asin(math.sqrt(x))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold-m", type=float, default=100.0)
    args = ap.parse_args()
    flagged, checked = [], 0
    for f in sorted(glob.glob(str(ROOT / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))):
        metro = os.path.basename(f).split("_metro")[0]
        for line in open(f, encoding="utf-8"):
            if not line.strip():
                continue
            r = json.loads(line)
            s = r.get("score") or {}
            a = (s.get("livability_pillars") or {}).get("neighborhood_amenities") or {}
            bl = (a.get("breakdown") or {}).get("business_list") or []
            co = s.get("coordinates") or {}
            if a.get("score") is None or len(bl) < 3 or "lat" not in co:
                continue
            diffs = sorted(abs(hav(co["lat"], co["lon"], b["lat"], b["lon"]) - b["distance_m"])
                           for b in bl if b.get("lat") is not None and b.get("distance_m") is not None)
            checked += 1
            med = diffs[len(diffs) // 2] if diffs else 0
            if med > args.threshold_m:
                flagged.append((metro, r["catalog"].get("name"), round(med), a["score"]))
    flagged.sort(key=lambda x: -x[2])
    print(f"checked {checked} places; flagged {len(flagged)} (median distance disagreement over {args.threshold_m:.0f} m)")
    for m, n, d, sc in flagged:
        print(f"  {m:12s} {n:28s} {d:>8d} m  score {sc}")
    return 1 if flagged else 0


if __name__ == "__main__":
    sys.exit(main())
