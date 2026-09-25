#!/usr/bin/env python3
"""
Offline simulation of a continuous distance-decay curve (no flat 0-3km zone, no hard radius
cutoff) against nyc_water_candidates.csv -- no Overpass calls, just today's already-pulled data.

Tests several decay steepness values (tau, in meters -- score = 25 * exp(-d/tau)) against two
groups:
  1. The 16 ground-truth real beach towns' own real winning beach distance (should stay high).
  2. Each shared beach's closest ("legit") place vs its farthest current borrower (the legit
     one should stay high, the farthest borrower should drop meaningfully).

Picks the curve that keeps ground truth near-max while meaningfully suppressing the farthest
borrowers, without ever hard-zeroing a real beach at any distance (which the old flat-then-cliff
approach didn't do either, but the point here is to check exactly how well a smooth curve
does both jobs).

Usage:
    python3 scripts/catalog/simulate_continuous_decay.py nyc_water_candidates.csv
"""
import csv
import sys
import math
import collections

GROUND_TRUTH = {
    "Coney Island", "Rockaway Beach", "Brighton Beach", "Long Beach", "Old Greenwich",
    "Westport", "Stamford", "New Rochelle", "Port Washington", "Manhasset", "Darien",
    "Southport", "Larchmont", "Mamaroneck", "Port Chester", "Cold Spring Harbor", "Pelham Bay",
}

TAUS = [2000, 3000, 4000, 5000, 6000]


def score(d, tau):
    return 25.0 * math.exp(-d / tau)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "nyc_water_candidates.csv"
    rows = list(csv.DictReader(open(path)))

    beach_rows = []
    for r in rows:
        if r["feature_type"] != "beach":
            continue
        tc = r["feature_true_distance_to_coastline_m"]
        if not tc:
            continue
        try:
            tc_f = float(tc)
        except ValueError:
            continue
        if tc_f > 2000:
            continue
        d = r["feature_distance_from_center_m"]
        if not d:
            continue
        beach_rows.append({"place": r["place_name"], "name": r["feature_name"] or None, "dist": float(d)})

    print("=" * 78)
    print("GROUND TRUTH: real beach town's own winning distance -> score under each tau")
    print("=" * 78)
    header = "  ".join(f"tau={t}" for t in TAUS)
    print(f"{'Place':<20} {'dist':>7}   {header}")
    gt_mins = {}
    for place in sorted(GROUND_TRUTH):
        candidates = [r for r in beach_rows if r["place"] == place]
        if not candidates:
            print(f"{place:<20} {'N/A':>7}")
            continue
        best = min(c["dist"] for c in candidates)
        gt_mins[place] = best
        scores = "  ".join(f"{score(best, t):6.1f}" for t in TAUS)
        print(f"{place:<20} {best:>6.0f}m   {scores}")

    avg_gt_scores = {t: sum(score(d, t) for d in gt_mins.values()) / len(gt_mins) for t in TAUS}
    print(f"\n{'AVG':<20} {'':>7}   " + "  ".join(f"{avg_gt_scores[t]:6.1f}" for t in TAUS))

    print()
    print("=" * 78)
    print("SHARED BEACHES: closest (legit) vs farthest (borrower) -> score under each tau")
    print("=" * 78)
    by_name = collections.defaultdict(dict)
    for r in beach_rows:
        if not r["name"]:
            continue
        p, d = r["place"], r["dist"]
        if p not in by_name[r["name"]] or d < by_name[r["name"]][p]:
            by_name[r["name"]][p] = d

    shared = {name: places for name, places in by_name.items() if len(places) >= 4}
    print(f"{'Beach':<32} {'closest':>9} {'farthest':>9}   " + "  ".join(f"tau={t}(close/far)" for t in TAUS))
    for name, places in sorted(shared.items(), key=lambda x: -len(x[1]))[:15]:
        ranked = sorted(places.items(), key=lambda x: x[1])
        closest_d = ranked[0][1]
        farthest_d = ranked[-1][1]
        cells = "  ".join(f"{score(closest_d,t):5.1f}/{score(farthest_d,t):<5.1f}" for t in TAUS)
        print(f"{name[:32]:<32} {closest_d:>8.0f}m {farthest_d:>8.0f}m   {cells}")


if __name__ == "__main__":
    main()
