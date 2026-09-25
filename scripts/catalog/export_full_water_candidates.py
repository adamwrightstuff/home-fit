#!/usr/bin/env python3
"""
Dump EVERY water/beach candidate feature Overpass returns for each catalog place, not just
the single winner that gets persisted to the catalog. One CSV row per feature, so you can see
every beach/coastline/lake/bay that was actually considered and why a given one won or lost --
something the stored catalog and rescore log can't answer since they only keep the winner.

Hits Overpass live (same query as the waterfront rescore script) -- takes a while for a full
metro. Use --max-places to test on a handful first.

Usage:
    PYTHONPATH=. python3 scripts/catalog/export_full_water_candidates.py \\
        --input data/nyc_metro_place_catalog_scores_merged.composites_recomputed.jsonl \\
        --output nyc_water_candidates.csv

    # Test on 10 places first:
    PYTHONPATH=. python3 scripts/catalog/export_full_water_candidates.py \\
        --input data/nyc_metro_place_catalog_scores_merged.composites_recomputed.jsonl \\
        --output nyc_water_candidates_sample.csv --max-places 10
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from data_sources import osm_api  # noqa: E402
from data_sources.radius_profiles import get_radius_profile  # noqa: E402
from data_sources.utils import haversine_distance  # noqa: E402

FIELDS = [
    "place_name", "place_lat", "place_lon", "area_type",
    "feature_type", "feature_name", "feature_surface",
    "feature_distance_from_center_m", "feature_lat", "feature_lon",
    "feature_true_distance_to_coastline_m",
]


def nearest_coastline_dist(feat: Dict, coastline_feats: List[Dict]) -> Optional[float]:
    flat, flon = feat.get("lat"), feat.get("lon")
    if flat is None or not coastline_feats:
        return None
    return min(haversine_distance(flat, flon, c["lat"], c["lon"]) for c in coastline_feats)


def rows_for_place(row: dict, delay: float) -> List[Dict]:
    catalog = row.get("catalog") or {}
    lat, lon = catalog.get("lat"), catalog.get("lon")
    name = catalog.get("name", "?")
    if not row.get("success") or lat is None or lon is None:
        return []

    score = row.get("score") or {}
    ao = (score.get("livability_pillars") or {}).get("active_outdoors") or {}
    area_type = (ao.get("area_classification") or {}).get("area_type") or "suburban"
    profile = get_radius_profile("active_outdoors", area_type, None)
    radius_m = int(profile.get("regional_radius_m", 15000))

    result = osm_api.query_water_only(lat, lon, radius_m=radius_m)
    time.sleep(delay)
    if result is None:
        print(f"  {name}: Overpass call failed, skipping")
        return []

    outcome = result.get("_overpass_outcome")
    swimming = result.get("swimming") or []
    if outcome not in ("overpass_ok", "overpass_empty") and not swimming:
        print(f"  {name}: Overpass outcome={outcome}, skipping")
        return []

    coastline_feats = [
        f for f in swimming
        if f.get("type") in ("coastline", "coastline_rocky") and f.get("lat") is not None
    ]

    out = []
    for feat in swimming:
        true_coast_dist = None
        if feat.get("type") == "beach":
            d = nearest_coastline_dist(feat, coastline_feats)
            true_coast_dist = round(d) if d is not None else None
        out.append({
            "place_name": name,
            "place_lat": lat,
            "place_lon": lon,
            "area_type": area_type,
            "feature_type": feat.get("type"),
            "feature_name": feat.get("name"),
            "feature_surface": feat.get("surface"),
            "feature_distance_from_center_m": feat.get("distance_m"),
            "feature_lat": feat.get("lat"),
            "feature_lon": feat.get("lon"),
            "feature_true_distance_to_coastline_m": true_coast_dist,
        })
    print(f"  {name}: {len(out)} candidate features")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--delay", type=float, default=1.5)
    ap.add_argument("--max-places", type=int, default=0, help="Limit for testing; 0 = all")
    args = ap.parse_args()

    rows = [json.loads(l) for l in args.input.open() if l.strip()]
    if args.max_places:
        rows = rows[: args.max_places]

    total_features = 0
    with args.output.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for i, row in enumerate(rows):
            print(f"[{i+1}/{len(rows)}]", end=" ")
            place_rows = rows_for_place(row, args.delay)
            for r in place_rows:
                writer.writerow(r)
            total_features += len(place_rows)

    print(f"\nWrote {total_features} feature rows across {len(rows)} places to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
