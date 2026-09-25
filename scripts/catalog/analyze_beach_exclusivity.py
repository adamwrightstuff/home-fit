#!/usr/bin/env python3
"""
Offline analysis of nyc_water_candidates.csv (the full-candidate export, not just winners) to
validate a fix for the cross-neighborhood beach-reuse problem -- no Overpass calls, just the
data already on disk from today's export_full_water_candidates.py run.

Two questions:
1. EXCLUSIVITY GAP: for each real, ocean-confirmed named beach that's currently winning for
   multiple places, how much farther are the "borrowing" places than the actual closest one?
   If we only credited a beach to whichever place is genuinely closest to it, how many of the
   104 false positives would lose their score vs. keep a legitimate claim?
2. RADIUS-CUT SIMULATION: if we capped the water search radius to some tighter value (5km, 8km,
   10km instead of 15-18km), would every one of the 16 real ground-truth beach towns still find
   their own real winning beach? (We already know their real winner's distance: 251m-3600m.)

Usage:
    python3 scripts/catalog/analyze_beach_exclusivity.py nyc_water_candidates.csv
"""
import csv
import sys
import collections
import math

GROUND_TRUTH = {
    "Coney Island", "Rockaway Beach", "Brighton Beach", "Long Beach", "Old Greenwich",
    "Westport", "Stamford", "New Rochelle", "Port Washington", "Manhasset", "Darien",
    "Southport", "Larchmont", "Mamaroneck", "Port Chester", "Cold Spring Harbor", "Pelham Bay",
}


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "nyc_water_candidates.csv"
    rows = list(csv.DictReader(open(path)))

    # Only real, ocean-confirmed beach candidates (type=beach, true_distance_to_coastline <=2000)
    beach_rows = []
    for r in rows:
        if r["feature_type"] != "beach":
            continue
        tc = r["feature_true_distance_to_coastline_m"]
        if tc == "" or tc is None:
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
        beach_rows.append({
            "place": r["place_name"],
            "name": r["feature_name"] or None,
            "dist": float(d),
        })

    print("=" * 70)
    print("QUESTION 1: EXCLUSIVITY GAP")
    print("=" * 70)
    print("For each named beach with multiple places as candidates, closest vs farthest place\n")

    by_name = collections.defaultdict(list)
    for r in beach_rows:
        if r["name"]:
            by_name[r["name"]].append(r)

    # Only look at names that are shared across 2+ DISTINCT places
    exclusive_losers = 0
    exclusive_keepers = 0
    for name, candidates in sorted(by_name.items(), key=lambda x: -len({c["place"] for c in x[1]})):
        # dedupe: min distance per place for this feature
        place_dist = {}
        for c in candidates:
            if c["place"] not in place_dist or c["dist"] < place_dist[c["place"]]:
                place_dist[c["place"]] = c["dist"]
        if len(place_dist) < 2:
            continue
        ranked = sorted(place_dist.items(), key=lambda x: x[1])
        closest_place, closest_dist = ranked[0]
        exclusive_keepers += 1
        exclusive_losers += len(ranked) - 1
        print(f"--- {name} ({len(ranked)} places see this as a candidate) ---")
        for place, dist in ranked[:8]:
            gap = dist - closest_dist
            tag = "CLOSEST (keeps it)" if place == closest_place else f"+{gap:.0f}m farther than {closest_place}"
            print(f"  {place:<22} {dist:>7.0f}m   {tag}")
        if len(ranked) > 8:
            print(f"  ... and {len(ranked)-8} more")
        print()

    print(f"SUMMARY: under a strict exclusivity rule (only the single closest place keeps a shared "
          f"beach), {exclusive_losers} place-instances across the catalog would lose a shared "
          f"beach they're currently winning on, {exclusive_keepers} would keep one.\n")

    print("=" * 70)
    print("QUESTION 2: RADIUS-CUT SIMULATION")
    print("=" * 70)
    print("Would ground-truth beach towns still find their real beach under a tighter radius?\n")

    for cap in (5000, 8000, 10000):
        survived = 0
        lost = []
        for place in GROUND_TRUTH:
            candidates = [r for r in beach_rows if r["place"] == place]
            if not candidates:
                lost.append((place, None))
                continue
            best = min(c["dist"] for c in candidates)
            if best <= cap:
                survived += 1
            else:
                lost.append((place, best))
        print(f"--- radius cap {cap/1000:.0f}km ---")
        print(f"  {survived}/{len(GROUND_TRUTH)} ground-truth towns keep a real beach within range")
        for place, dist in lost:
            print(f"  LOST: {place} (closest real beach at {dist}m)" if dist else f"  LOST: {place} (no beach candidate found at all)")
        print()


if __name__ == "__main__":
    main()
