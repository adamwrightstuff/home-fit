#!/usr/bin/env python3
"""
Re-fetch ONLY the local parks Overpass query for places where overpass_local
was error/empty, then recompute daily_urban_outdoors in-place.

All other AO sub-scores (wild_adventure, waterfront_lifestyle) and all other
pillar scores are left completely untouched.

Usage:
  PYTHONPATH=. python3 scripts/catalog/refetch_ao_local_parks.py \
    --input data/nyc_metro_place_catalog_scores_merged.jsonl --in-place
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from data_sources import osm_api
from data_sources.osm_api import coerce_green_spaces_response
from data_sources.data_quality import get_baseline_context
from data_sources.regional_baselines import get_contextual_expectations
from data_sources.radius_profiles import get_radius_profile
from pillars.active_outdoors import _score_daily_urban_outdoors_v2


def _recompute_total(pillars: dict) -> float:
    total = weighted = 0.0
    for p in pillars.values():
        if not isinstance(p, dict):
            continue
        score = p.get("score")
        weight = p.get("weight")
        if score is not None and weight is not None:
            weighted += float(score) * float(weight)
            total += float(weight)
    return round(weighted / total, 4) if total > 0 else 0.0


def process_row(row: dict, delay: float = 1.5) -> tuple[bool, str]:
    score_doc = row.get("score", {})
    pillars = score_doc.get("livability_pillars", {})
    ao = pillars.get("active_outdoors")
    if not ao or ao.get("status") != "success":
        return False, "skip: no ao or not success"

    summary = ao.get("summary", {})
    overpass_local = summary.get("overpass", {}).get("local", "")
    if overpass_local not in ("overpass_error", "overpass_empty"):
        return False, f"skip: overpass_local={overpass_local}"

    # Coordinates
    coords = score_doc.get("coordinates", {})
    lat = coords.get("lat") or coords.get("latitude")
    lon = coords.get("lon") or coords.get("longitude") or coords.get("lng")
    if not lat or not lon:
        return False, "skip: no coordinates"

    area_type = (ao.get("area_classification") or {}).get("area_type", "suburban")
    profile = get_radius_profile("active_outdoors", area_type, None)
    local_radius = int(profile.get("local_radius_m", 1000))

    # Re-fetch only local parks
    time.sleep(delay)
    raw = osm_api.query_green_spaces(lat, lon, radius_m=local_radius)
    result = coerce_green_spaces_response(raw) or {}

    parks = result.get("parks") or []
    playgrounds = result.get("playgrounds") or []
    facilities = result.get("recreational_facilities") or []
    new_overpass_status = "overpass_ok" if (parks or playgrounds or facilities) else "overpass_empty"

    # Recompute daily only
    baseline_context = get_baseline_context(area_type=area_type, form_context=None, pillar_name="active_outdoors")
    expectations = get_contextual_expectations(baseline_context, "active_outdoors") or {}
    new_daily = _score_daily_urban_outdoors_v2(parks, playgrounds, facilities, area_type, expectations)

    # Preserve existing wild + waterfront untouched
    breakdown = ao.get("breakdown", {})
    wild = float(breakdown.get("wild_adventure") or 0.0)
    water = float(breakdown.get("waterfront_lifestyle") or 0.0)

    new_total = round(max(0.0, min(100.0, new_daily + wild + water)), 1)

    # Update breakdown + summary, leave everything else intact
    breakdown["daily_urban_outdoors"] = round(new_daily, 1)
    ao["score"] = new_total

    # Update local_parks summary and overpass status
    summary["local_parks"] = {
        "count": len(parks),
        "playgrounds": len(playgrounds),
        "total_park_area_ha": round(sum((p.get("area_sqm") or 0) / 10_000 for p in parks), 2),
    }
    summary.setdefault("overpass", {})["local"] = new_overpass_status

    score_doc["total_score"] = _recompute_total(pillars)
    return True, f"daily={new_daily:.1f} parks={len(parks)} {new_overpass_status}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output")
    parser.add_argument("--in-place", action="store_true")
    parser.add_argument("--delay", type=float, default=1.5, help="Seconds between Overpass calls")
    parser.add_argument("--names", help="Comma-separated place names to limit to")
    args = parser.parse_args()

    if not args.in_place and not args.output:
        print("Provide --output or --in-place")
        sys.exit(1)

    name_filter = set(n.strip() for n in args.names.split(",")) if args.names else None

    path = Path(args.input)
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    ok = skip = err = 0

    for row in rows:
        name = row.get("score", {}).get("input", "?")
        if name_filter and name not in name_filter:
            continue
        success, reason = process_row(row, delay=args.delay)
        if success:
            ok += 1
            print(f"  ✓ {name}: {reason}")
        elif reason.startswith("skip"):
            skip += 1
        else:
            err += 1
            print(f"  ✗ {name}: {reason}")

    out = Path(args.output) if args.output else path
    out.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    print(f"\nDone: {ok} refetched, {skip} skipped, {err} errors → {out}")


if __name__ == "__main__":
    main()
