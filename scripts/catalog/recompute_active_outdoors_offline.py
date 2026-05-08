#!/usr/bin/env python3
"""
Offline active_outdoors recompute using stored OSM counts + updated baselines.

Re-runs daily and wild sub-scores from stored summary data with the new
empirically-calibrated expectations in regional_baselines.py.
Water (waterfront_lifestyle) sub-score is preserved unchanged — its
expectations didn't change and the feature type isn't stored.

Max error vs live rescore: ~3 pts (recreational_facilities not stored).

Usage:
  PYTHONPATH=. python3 scripts/catalog/recompute_active_outdoors_offline.py \
    --input data/nyc_metro_place_catalog_scores_merged.jsonl \
    --output data/nyc_metro_place_catalog_scores_merged.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pillars.active_outdoors import _score_daily_urban_outdoors_v2, _score_wild_adventure_v2
from data_sources.regional_baselines import get_contextual_expectations


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


def recompute_row(row: dict) -> tuple[bool, str]:
    score_doc = row.get("score", {})
    pillars = score_doc.get("livability_pillars", {})
    ao = pillars.get("active_outdoors")
    if not ao or ao.get("status") != "success":
        return False, "no active_outdoors or not success"

    summary = ao.get("summary", {})
    breakdown = ao.get("breakdown", {})
    area_type = (ao.get("area_classification") or {}).get("area_type", "suburban")

    local = summary.get("local_parks", {})
    park_count = int(local.get("count") or 0)
    playgrounds_count = int(local.get("playgrounds") or 0)
    total_area_ha = float(local.get("total_park_area_ha") or 0.0)

    trails_summary = summary.get("trails", {})
    trail_total = int(trails_summary.get("count_total") or 0)
    trail_near = int(trails_summary.get("count_within_5km") or 0)

    camping_summary = summary.get("camping", {})
    camping_sites = int(camping_summary.get("sites") or 0)
    camping_nearest_km = float(camping_summary.get("nearest_km") or 99.0)

    canopy_pct = float((summary.get("environment") or {}).get("tree_canopy_pct_5km") or 0.0)

    stored_water_score = float(breakdown.get("waterfront_lifestyle") or 0.0)

    # Synthetic park list: one park with all area, rest with zero
    parks = [{"area_sqm": total_area_ha * 10_000}] if total_area_ha > 0 else []
    parks += [{"area_sqm": 0.0}] * max(0, park_count - len(parks))

    playgrounds = [{}] * playgrounds_count
    recreational_facilities = []  # not stored; max 3pt error

    # Synthetic trail list: trail_near within 5km, rest outside
    hiking_trails = (
        [{"distance_m": 1000}] * trail_near +
        [{"distance_m": 6000}] * max(0, trail_total - trail_near)
    )

    # Synthetic camping list
    camping = [{"distance_km": camping_nearest_km}] * camping_sites

    expectations = get_contextual_expectations(area_type, "active_outdoors") or {}

    daily = _score_daily_urban_outdoors_v2(
        parks, playgrounds, recreational_facilities, area_type, expectations
    )
    wild = _score_wild_adventure_v2(
        hiking_trails, camping, canopy_pct, area_type
    )

    new_total = round(max(0.0, min(100.0, daily + wild + stored_water_score)), 1)

    breakdown["daily_urban_outdoors"] = round(daily, 1)
    breakdown["wild_adventure"] = round(wild, 1)
    ao["score"] = new_total
    score_doc["total_score"] = _recompute_total(pillars)
    return True, "ok"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    rows = [json.loads(l) for l in Path(args.input).read_text().splitlines() if l.strip()]
    ok = skip = err = 0

    for row in rows:
        success, reason = recompute_row(row)
        if success:
            ok += 1
        elif "no active_outdoors" in reason:
            skip += 1
        else:
            err += 1
            print(f"  ERROR: {reason}")

    Path(args.output).write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    print(f"Done: {ok} recomputed, {skip} skipped, {err} errors")


if __name__ == "__main__":
    main()
