#!/usr/bin/env python3
"""
Compute the 40th-percentile floors used by the NB/AO scenery preference gate
(frontend/lib/nbPreference.ts NB_PREFERENCE_FLOOR, frontend/lib/aoPreference.ts
AO_PREFERENCE_FLOOR) plus the new waterfront sub-type floors needed to convert
that gate from a hard AND-filter to a gradient multiplicative penalty.

Reads the current 4-metro catalog directly -- same source the existing hardcoded
constants were derived from (see BACKLOG.md "Hardcoded NB/AO preference floors
won't generalize..."). Rerun and re-paste into the two TS files whenever the
underlying catalog changes enough to matter (new metro, big rescore) -- this is
an offline admin tool, not called at request time (see CLAUDE.md's live-vs-batch
distinction).

Main AO/NB components: percentile taken over ALL places (every place has some
value for these, even if low).

Waterfront sub-types (ocean_beach/lake_river/bay_harbor): percentile taken over
only the places where that sub-type is nonzero. Most places are inland and score
literally 0 on e.g. bay_harbor, so an all-places percentile would just be 0 and
gate nothing -- the floor needs to answer "how strong is this among places that
have ANY of this feature," not "among the whole catalog."

Usage:
    PYTHONPATH=. python3 scripts/baselines/compute_preference_floors.py
"""
import json
import statistics
from pathlib import Path

CATALOG_FILES = [
    "data/nyc_metro_place_catalog_scores_merged.composites_recomputed.jsonl",
    "data/sf_metro_place_catalog_scores_merged.composites_recomputed.jsonl",
    "data/la_metro_place_catalog_scores_merged.composites_recomputed.jsonl",
    "data/seattle_metro_place_catalog_scores_merged.composites_recomputed.jsonl",
]

# Mirrors AO_COMPONENT_MAX in frontend/lib/aoPreference.ts -- raw contribution
# caps from active_outdoors.py (daily<=35, wild<=50, waterfront<=25).
AO_COMPONENT_MAX = {
    "daily_urban_outdoors": 35.0,
    "wild_adventure": 50.0,
    "waterfront_lifestyle": 25.0,
}

NB_V9_COMPONENTS = [
    "gvi_score", "water_score", "canopy_score", "topo_score", "landcover_score", "bio_score",
]

WATERFRONT_SUBTYPES = ["ocean_beach", "lake_river", "bay_harbor"]

PERCENTILE = 40


def percentile(values, pct):
    if not values:
        return None
    s = sorted(values)
    k = (len(s) - 1) * (pct / 100.0)
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


def load_places():
    places = []
    for path in CATALOG_FILES:
        p = Path(path)
        if not p.exists():
            print(f"WARNING: missing {path}, skipping")
            continue
        with open(p) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                sc = d.get("score") or {}
                lp = sc.get("livability_pillars") or {}
                places.append({
                    "name": (d.get("catalog") or {}).get("name"),
                    "ao": lp.get("active_outdoors") or {},
                    "nb": lp.get("natural_beauty") or {},
                })
    return places


def main():
    places = load_places()
    print(f"Loaded {len(places)} places across {len(CATALOG_FILES)} metro files\n")

    print("=" * 70)
    print(f"AO main components ({PERCENTILE}th percentile, normalized 0-100, all places)")
    print("=" * 70)
    ao_floors = {}
    for key, cap in AO_COMPONENT_MAX.items():
        vals = []
        for place in places:
            raw = (place["ao"].get("breakdown") or {}).get(key)
            if isinstance(raw, (int, float)):
                vals.append(min(100.0, (raw / cap) * 100.0))
        floor = percentile(vals, PERCENTILE)
        ao_floors[key] = floor
        print(f"  {key:<22} n={len(vals):<4} p{PERCENTILE}={floor:.1f}" if floor is not None else f"  {key}: no data")

    print()
    print("=" * 70)
    print(f"AO waterfront sub-types ({PERCENTILE}th percentile, nonzero-only)")
    print("=" * 70)
    wf_floors = {}
    for key in WATERFRONT_SUBTYPES:
        vals = []
        for place in places:
            wb = (place["ao"].get("breakdown") or {}).get("waterfront_breakdown") or {}
            v = wb.get(key)
            if isinstance(v, (int, float)) and v > 0:
                vals.append(v)
        floor = percentile(vals, PERCENTILE)
        wf_floors[key] = floor
        n_nonzero = len(vals)
        n_total = sum(1 for place in places if (place["ao"].get("breakdown") or {}).get("waterfront_breakdown"))
        if floor is not None:
            print(f"  {key:<15} nonzero={n_nonzero}/{n_total}   p{PERCENTILE}={floor:.1f}")
        else:
            print(f"  {key}: no nonzero data")

    print()
    print("=" * 70)
    print(f"NB v9 components ({PERCENTILE}th percentile, all places)")
    print("=" * 70)
    nb_floors = {}
    for key in NB_V9_COMPONENTS:
        vals = []
        for place in places:
            v = (place["nb"].get("v9_breakdown") or {}).get(key)
            if isinstance(v, (int, float)):
                vals.append(v)
        floor = percentile(vals, PERCENTILE)
        nb_floors[key] = floor
        print(f"  {key:<18} n={len(vals):<4} p{PERCENTILE}={floor:.1f}" if floor is not None else f"  {key}: no data")

    print()
    print("=" * 70)
    print("Paste-ready TS snippets")
    print("=" * 70)
    print("\n// frontend/lib/aoPreference.ts")
    print("export const AO_PREFERENCE_FLOOR: Record<AoNumericKey, number> = {")
    for key in AO_COMPONENT_MAX:
        print(f"  {key}: {ao_floors[key]:.0f},")
    print("}")
    print("\nexport const AO_WATERFRONT_SUBTYPE_FLOOR: Record<WaterfrontSubPreference, number> = {")
    for key in WATERFRONT_SUBTYPES:
        if wf_floors[key] is not None:
            print(f"  {key}: {wf_floors[key]:.0f},")
        else:
            fallback = wf_floors.get("lake_river") or 50.0
            print(f"  {key}: {fallback:.0f},  // no nonzero {key} places in current catalog -- fallback to lake_river floor, recompute once one exists")
    print("}")

    print("\n// frontend/lib/nbPreference.ts")
    print("export const NB_PREFERENCE_FLOOR: Record<string, number> = {")
    for key in NB_V9_COMPONENTS:
        print(f"  {key}: {nb_floors[key]:.0f},")
    print("}")


if __name__ == "__main__":
    main()
