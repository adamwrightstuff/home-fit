"""
Re-fetch Census density and reclassify area_type for places stuck at 'unknown'
due to missing density at original scoring time. Patches area_type in-place in
both the merged and composites_recomputed JSONL files.

Usage:
    PYTHONPATH=. python3 scripts/manual/reclassify_unknown_area_types.py
"""

import json
import os
import sys
from pathlib import Path

from data_sources.census_api import get_population_density
from data_sources.data_quality import classify_morphology

METRO_FILES = {
    "nyc": (
        "data/nyc_metro_place_catalog_scores_merged.jsonl",
        "data/nyc_metro_place_catalog_scores_merged.composites_recomputed.jsonl",
    ),
    "sf": (
        "data/sf_metro_place_catalog_scores_merged.jsonl",
        "data/sf_metro_place_catalog_scores_merged.composites_recomputed.jsonl",
    ),
    "la": (
        "data/la_metro_place_catalog_scores_merged.jsonl",
        "data/la_metro_place_catalog_scores_merged.composites_recomputed.jsonl",
    ),
}


def _biz_count_from_place(p: dict) -> int | None:
    """Pull the 1km business count stored in neighborhood_amenities breakdown."""
    na = p.get("score", {}).get("livability_pillars", {}).get("neighborhood_amenities", {})
    biz = na.get("breakdown", {}).get("home_walkability", {}).get("businesses_within_walk")
    return int(biz) if isinstance(biz, (int, float)) else None


def reclassify_file(path: str) -> dict[str, str]:
    """
    Load the JSONL, reclassify unknown-area_type places, overwrite in-place.
    Returns a dict of {name: new_area_type} for places that were changed.
    """
    if not os.path.exists(path):
        print(f"  SKIP (not found): {path}")
        return {}

    with open(path) as f:
        places = [json.loads(l) for l in f if l.strip()]

    changes: dict[str, str] = {}
    for p in places:
        ac = p.get("score", {}).get("data_quality_summary", {}).get("area_classification", {})
        if ac.get("area_type") != "unknown":
            continue

        name = p.get("catalog", {}).get("name", "?")
        lat = p.get("catalog", {}).get("lat")
        lon = p.get("catalog", {}).get("lon")
        if lat is None or lon is None:
            print(f"  SKIP {name}: no lat/lon")
            continue

        print(f"  Fetching density for {name} ({lat}, {lon}) ...", end=" ", flush=True)
        density = get_population_density(lat, lon)
        biz = _biz_count_from_place(p)
        new_type = classify_morphology(density, None, biz, None)
        print(f"density={density:.0f} biz={biz} → {new_type}")

        ac["area_type"] = new_type
        # Also patch effective_area_type if it was also 'unknown'
        if ac.get("effective_area_type") == "unknown":
            ac["effective_area_type"] = new_type

        changes[name] = new_type

    if changes:
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            for p in places:
                f.write(json.dumps(p) + "\n")
        os.replace(tmp, path)
        print(f"  Wrote {path} ({len(changes)} change(s))")
    else:
        print(f"  No changes in {path}")

    return changes


def main():
    for metro, (merged, recomputed) in METRO_FILES.items():
        print(f"\n=== {metro.upper()} ===")
        for path in (merged, recomputed):
            print(f"\n{path}:")
            reclassify_file(path)


if __name__ == "__main__":
    main()
