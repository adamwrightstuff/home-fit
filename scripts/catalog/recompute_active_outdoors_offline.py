#!/usr/bin/env python3
"""
Offline active_outdoors recompute using stored OSM summary data.

What gets recomputed vs preserved:
  - wild_adventure: fully recomputed from stored trail counts, canopy, camping distance
  - daily_urban_outdoors: count + play + facilities from stored; s_nearest=0 (not stored)
  - waterfront_lifestyle: scaled from stored score (cap 20->25), type not stored so can't re-score

For exact waterfront re-scoring, run a targeted water re-fetch (separate script).

Usage:
  PYTHONPATH=. python3 scripts/catalog/recompute_active_outdoors_offline.py \
    --input data/nyc_metro_place_catalog_scores_merged.jsonl \
    --in-place
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from data_sources.regional_baselines import get_contextual_expectations
from data_sources.data_quality import get_baseline_context
from pillars.active_outdoors import _score_wild_adventure_v2


def _sat_ratio_v2(value: float, expected: float, max_score: float) -> float:
    if expected <= 0:
        return 0.0
    ratio = value / expected
    return max_score * (1 - math.exp(-2.5 * ratio))


def _recompute_daily(local: dict, area_type: str, expectations: dict) -> float:
    park_count = int(local.get("count") or 0)
    playground_count = int(local.get("playgrounds") or 0)

    exp_park_count = expectations.get("expected_parks_within_1km", 8.0)
    exp_play = expectations.get("expected_playgrounds_within_1km", 2.0)
    exp_facilities = expectations.get("expected_recreational_facilities_within_1km", 3.0)

    s_count = _sat_ratio_v2(park_count, exp_park_count, 22.0)
    s_play = _sat_ratio_v2(playground_count, exp_play, 5.0)
    # facilities not stored; use 0 (max 3pt error)
    s_facilities = 0.0
    # s_nearest not stored; use 0 (conservative — parks without distance data get no proximity bonus)
    s_nearest = 0.0

    return min(35.0, s_count + s_nearest + s_play + s_facilities)


def _recompute_wild(summary: dict, area_type: str) -> float:
    trails = summary.get("trails", {})
    trail_total = int(trails.get("count_total") or 0)
    trail_near = int(trails.get("count_within_5km") or 0)

    camping_s = summary.get("camping", {})
    camping_sites = int(camping_s.get("sites") or 0)
    camping_nearest_km = float(camping_s.get("nearest_km") or 99.0)

    canopy_pct = float((summary.get("environment") or {}).get("tree_canopy_pct_5km") or 0.0)

    # Synthetic trail list: trail_near within 5km, rest outside
    hiking_trails = (
        [{"distance_m": 1000}] * trail_near +
        [{"distance_m": 6000}] * max(0, trail_total - trail_near)
    )
    # Synthetic camping list with distance_m
    camping = [{"distance_m": camping_nearest_km * 1000}] * camping_sites

    return _score_wild_adventure_v2(hiking_trails, camping, canopy_pct, area_type)


def _scale_waterfront(stored_water: float) -> float:
    # Old cap was 20, new cap is 25. Scale proportionally.
    # A place that scored 20/20 should now score 25/25.
    if stored_water <= 0:
        return 0.0
    return min(25.0, stored_water * (25.0 / 20.0))


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

    baseline_context = get_baseline_context(area_type=area_type, form_context=None, pillar_name="active_outdoors")
    expectations = get_contextual_expectations(baseline_context, "active_outdoors") or {}

    stored_water = float(breakdown.get("waterfront_lifestyle") or 0.0)

    daily = _recompute_daily(summary.get("local_parks", {}), area_type, expectations)
    wild = _recompute_wild(summary, area_type)
    water = _scale_waterfront(stored_water)

    new_total = round(max(0.0, min(100.0, daily + wild + water)), 1)

    breakdown["daily_urban_outdoors"] = round(daily, 1)
    breakdown["wild_adventure"] = round(wild, 1)
    breakdown["waterfront_lifestyle"] = round(water, 1)
    ao["score"] = new_total
    score_doc["total_score"] = _recompute_total(pillars)
    return True, "ok"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output")
    parser.add_argument("--in-place", action="store_true")
    args = parser.parse_args()

    if not args.in_place and not args.output:
        print("Provide --output or --in-place")
        sys.exit(1)

    path = Path(args.input)
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
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

    out = Path(args.output) if args.output else path
    out.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    print(f"Done: {ok} recomputed, {skip} skipped, {err} errors → {out}")


if __name__ == "__main__":
    main()
