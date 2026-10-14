#!/usr/bin/env python3
"""
Offline test of the Voronoi-style spillover cap: for each shared beach, the geographically
closest place keeps full credit (today's behavior, unchanged); every other place that also
sees it as a candidate gets its score capped at a lower ceiling instead of the full beach
score. Tests a few candidate cap values against nyc_water_candidates.csv, no Overpass calls.

Usage:
    python3 scripts/catalog/simulate_spillover_cap.py nyc_water_candidates.csv
"""
import csv
import sys
import math
import collections

CAPS = [25.0, 20.0, 17.0, 12.0, 8.0]  # 25=no change, 20=swimming_area level, others progressively stricter


def decay(base, d):
    if d > 3000:
        base *= math.exp(-0.00025 * (d - 3000))
    return base


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "nyc_water_candidates.csv"
    rows = list(csv.DictReader(open(path)))

    beach_rows = []
    for r in rows:
        if r["feature_type"] != "beach" or not r["feature_name"]:
            continue
        tc = r["feature_true_distance_to_coastline_m"]
        if not tc:
            continue
        try:
            if float(tc) > 2000:
                continue
        except ValueError:
            continue
        d = r["feature_distance_from_center_m"]
        if not d:
            continue
        beach_rows.append({"place": r["place_name"], "name": r["feature_name"], "dist": float(d)})

    by_name = collections.defaultdict(dict)
    for r in beach_rows:
        p, d = r["place"], r["dist"]
        if p not in by_name[r["name"]] or d < by_name[r["name"]][p]:
            by_name[r["name"]][p] = d

    shared = {name: places for name, places in by_name.items() if len(places) >= 3}

    print(f"{'Beach':<32} {'Place':<20} {'dist':>7} {'role':<10}  " + "  ".join(f"cap={c:g}" for c in CAPS))
    for name, places in sorted(shared.items(), key=lambda x: -len(x[1]))[:10]:
        ranked = sorted(places.items(), key=lambda x: x[1])
        primary_place, primary_dist = ranked[0]
        for place, dist in ranked:
            role = "PRIMARY" if place == primary_place else "spillover"
            cap_scores = []
            for cap in CAPS:
                base = 25.0 if role == "PRIMARY" else cap
                cap_scores.append(f"{decay(base, dist):5.1f}")
            print(f"{name[:32]:<32} {place:<20} {dist:>6.0f}m {role:<10}  " + "  ".join(cap_scores))
        print()


if __name__ == "__main__":
    main()
