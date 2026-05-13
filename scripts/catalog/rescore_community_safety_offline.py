#!/usr/bin/env python3
"""
Offline rescore of the community_safety pillar for a catalog JSONL.

Reads lat/lon, area_type, city, state, and density directly from the catalog
and calls get_community_safety_score() — no HTTP round-trips, no GEE startup.

Usage:
    python3 scripts/catalog/rescore_community_safety_offline.py \\
        --input  data/nyc_metro_place_catalog_scores_merged.jsonl \\
        --in-place

    python3 scripts/catalog/rescore_community_safety_offline.py \\
        --input  data/la_metro_place_catalog_scores_merged.jsonl \\
        --in-place
"""

import argparse
import json
import math
import os
import shutil
import sys
import time
from typing import Any, Dict, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from pillars.community_safety import get_community_safety_score
from logging_config import get_logger

logger = get_logger(__name__)


def _extract_location(row: Dict):
    """Extract lat, lon, area_type, city, state from catalog row."""
    score = row.get("score", {})
    coords = score.get("coordinates", {})
    lat = coords.get("lat")
    lon = coords.get("lon")
    loc_info = score.get("location_info", {})
    # Prefer the catalog location name as city hint — it's the clean town/neighborhood
    # name (e.g. "Scarsdale") rather than the geocoder city which may be empty,
    # a village prefix ("Village of Scarsdale"), or a major city ("New York").
    catalog_name = row.get("catalog", {}).get("name", "")
    city = catalog_name or loc_info.get("city", "")
    state_full = loc_info.get("state", "")

    _state_map = {
        "New York": "NY", "New Jersey": "NJ", "Connecticut": "CT",
        "California": "CA", "Florida": "FL", "Texas": "TX",
        "Massachusetts": "MA", "Pennsylvania": "PA", "Illinois": "IL",
        "Washington": "WA", "Oregon": "OR", "Colorado": "CO",
        "Maryland": "MD", "Virginia": "VA", "Georgia": "GA",
    }
    state = _state_map.get(state_full, state_full[:2].upper() if len(state_full) >= 2 else "")

    # area_type is stored in data_quality_summary.area_classification.area_type
    dq = score.get("data_quality_summary", {})
    area_type = (
        dq.get("area_classification", {}).get("area_type")
        or dq.get("area_type")
        or ""
    )
    zip_code = loc_info.get("zip", "")
    return lat, lon, area_type, city, state, zip_code


def _pop_from_row(row: Dict) -> int:
    """Estimate residential population from catalog density and area_type radius."""
    score_payload = row.get("score", {})
    pillars = score_payload.get("livability_pillars", {})

    # Population density (people/sqmi) is in active_outdoors.area_classification.density
    # (also available in air_travel and healthcare area_classification)
    density = (
        pillars.get("active_outdoors", {}).get("area_classification", {}).get("density")
        or pillars.get("air_travel_access", {}).get("area_classification", {}).get("density")
        or pillars.get("social_fabric", {}).get("summary", {}).get("tract_population_density_sqmi")
        or 0
    )
    if isinstance(density, dict):
        density = 0  # safety guard

    dq = score_payload.get("data_quality_summary", {})
    area_type = (dq.get("area_classification", {}).get("area_type") or "").lower()

    radius_map = {
        "urban_core": 800,
        "urban_residential": 1000,
        "suburban": 2000,
        "exurban": 5000,
        "rural": 8000,
    }
    # Minimum credible population density per sq mile by area type.
    # Guards against anomalously low Census tract density values that would
    # collapse the population estimate to the 500-person floor and inflate
    # per-1k crime rates (e.g. Glendale Queens had density=16.52 stored).
    min_density_map = {
        "urban_core": 5_000,
        "urban_residential": 2_000,
        "suburban": 500,
        "exurban": 50,
        "rural": 10,
    }
    radius_m = radius_map.get(area_type, 1500)
    min_density = min_density_map.get(area_type, 500)
    sq_mi = math.pi * (radius_m / 1609.34) ** 2
    effective_density = max(float(density) if density else 0, min_density)
    return max(500, int(effective_density * sq_mi))


def rescore_catalog(input_path: str, output_path: str, dry_run: bool = False):
    rows = {}
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                key = obj.get("catalog", {}).get("place_id") or obj.get("catalog", {}).get("name")
                if key:
                    rows[key] = obj
            except json.JSONDecodeError:
                continue

    total = len(rows)
    logger.info("Loaded %d rows from %s", total, input_path)

    updated = 0
    degraded = 0
    errors = 0

    place_list = list(rows.items())
    for idx, (key, row) in enumerate(place_list, 1):
        lat, lon, area_type, city, state, zip_code = _extract_location(row)
        if lat is None or lon is None:
            logger.warning("[%d/%d] %s: no coordinates, skipping", idx, total, key)
            errors += 1
            continue

        pop = _pop_from_row(row)
        try:
            score, details = get_community_safety_score(
                lat, lon,
                area_type=area_type or None,
                city=city,
                state=state,
                zip_code=zip_code,
                population=pop,
            )
        except Exception as e:
            logger.error("[%d/%d] %s: error %s", idx, total, key, e)
            errors += 1
            continue

        if (idx % 20 == 0) or idx == total:
            logger.info("[%d/%d] %s — score=%s", idx, total, key, score)

        if not dry_run:
            # Write community_safety into the row
            pillars = row.setdefault("score", {}).setdefault("livability_pillars", {})
            pillars["community_safety"] = {
                "score": score,
                "weight": 0.0,       # recomputed by recompute_composites
                "contribution": 0.0,
                "breakdown": details,
                "summary": {},
                "confidence": 80 if details.get("data_available") else 0,
                "data_quality": {
                    "degraded": score is None,
                    "data_available": details.get("data_available", False),
                    "source": details.get("source"),
                },
                "area_classification": {},
                "status": "success" if score is not None else "degraded",
            }
            rows[key] = row

        if score is None:
            degraded += 1
        else:
            updated += 1

    if dry_run:
        logger.info("DRY RUN: would update %d, degraded %d, errors %d", updated, degraded, errors)
        return

    # Back up original
    bak = input_path + f".bak.{int(time.time())}"
    shutil.copy2(input_path, bak)
    logger.info("Backed up original to %s", bak)

    # Write updated JSONL
    with open(output_path, "w", encoding="utf-8") as f:
        for row in rows.values():
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    logger.info(
        "Written %d rows → %s  (updated=%d, degraded=%d, errors=%d)",
        len(rows), output_path, updated, degraded, errors,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output")
    parser.add_argument("--in-place", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    output = args.input if args.in_place else (args.output or args.input + ".community_safety.jsonl")
    rescore_catalog(args.input, output, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
