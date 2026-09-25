#!/usr/bin/env python3
"""
Dump the stored waterfront_lifestyle data for every place in a catalog JSONL to CSV --
name, lat/lon, area_type, score, the three category percentages, and everything currently
saved about the winning feature (type, name, surface, distances). Read-only, no API calls,
just what's already on disk.

Usage:
    PYTHONPATH=. python3 scripts/catalog/export_waterfront_csv.py \\
        --input data/nyc_metro_place_catalog_scores_merged.composites_recomputed.jsonl \\
        --output nyc_waterfront_export.csv
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    fields = [
        "name", "lat", "lon", "area_type",
        "waterfront_lifestyle_score",
        "ocean_beach_pct", "lake_river_pct", "bay_harbor_pct",
        "winner_type", "winner_name", "winner_surface",
        "winner_distance_from_center_m", "winner_true_distance_to_coastline_m",
    ]

    n = 0
    with args.output.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for line in args.input.open():
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            catalog = row.get("catalog") or {}
            score = row.get("score") or {}
            ao = (score.get("livability_pillars") or {}).get("active_outdoors") or {}
            bd = ao.get("breakdown") or {}
            wb = bd.get("waterfront_breakdown") or {}
            wf = wb.get("winning_feature") or {}
            writer.writerow({
                "name": catalog.get("name"),
                "lat": catalog.get("lat"),
                "lon": catalog.get("lon"),
                "area_type": (ao.get("area_classification") or {}).get("area_type"),
                "waterfront_lifestyle_score": bd.get("waterfront_lifestyle"),
                "ocean_beach_pct": wb.get("ocean_beach"),
                "lake_river_pct": wb.get("lake_river"),
                "bay_harbor_pct": wb.get("bay_harbor"),
                "winner_type": wf.get("type"),
                "winner_name": wf.get("name"),
                "winner_surface": wf.get("surface"),
                "winner_distance_from_center_m": wf.get("distance_from_center_m"),
                "winner_true_distance_to_coastline_m": wf.get("true_distance_to_coastline_m"),
            })
            n += 1

    print(f"Wrote {n} rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
