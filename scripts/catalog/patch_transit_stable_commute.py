#!/usr/bin/env python3
"""
Patch public_transit_access commute_time in catalog JSONL using the stable
population-weighted Census lookup, without re-running Transitland.

For each place:
  1. Call get_commute_time_stable(lat, lon) directly (9 Census ACS API calls,
     no Transitland).
  2. Back-calculate base transit score from stored final + stored commute blend.
  3. Re-blend with new commute score (COMMUTE_WEIGHT=0.05).
  4. Patch score, summary.mean_commute_minutes, and breakdown.commute_time in
     place.

Note: commuter-rail suburb commute bonus (_calculate_commute_bonus) is baked
into the stored base score and is NOT recomputed — the error is at most ±5pts
on a small subset of places and doesn't affect the dealbreaker gate.

Usage:
  cd /path/to/home-fit
  PYTHONPATH=. python3 scripts/catalog/patch_transit_stable_commute.py \
    --input data/nyc_metro_place_catalog_scores_merged.jsonl \
    --output data/nyc_metro_place_catalog_scores_merged.jsonl
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from data_sources.census_api import get_commute_time_stable
from pillars.public_transit_access import _score_commute_time

COMMUTE_WEIGHT = 0.05


def patch_file(input_path: str, output_path: str, delay: float, dry_run: bool) -> None:
    rows = []
    with open(input_path) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    changed = 0
    skipped = 0
    failed = 0

    for i, row in enumerate(rows):
        name = row.get("catalog", {}).get("name", f"row_{i}")
        lat = row.get("catalog", {}).get("lat")
        lon = row.get("catalog", {}).get("lon")
        score_block = row.get("score", {})
        pillars = score_block.get("livability_pillars", {})
        pt = pillars.get("public_transit_access", {})

        if not pt or pt.get("score") is None:
            skipped += 1
            continue
        if lat is None or lon is None:
            skipped += 1
            continue

        stored_final = pt["score"]
        stored_summary = pt.get("summary", {})
        stored_commute_min = stored_summary.get("mean_commute_minutes")
        commute_detail = pt.get("details", {}).get("commute_time", {})
        # commute_time detail is a dict: {mean_minutes, score, weight, note}
        stored_commute_score = commute_detail.get("score") if isinstance(commute_detail, dict) else commute_detail
        area_type = stored_summary.get("area_type") or pt.get("details", {}).get("area_type")

        try:
            new_commute_min = get_commute_time_stable(float(lat), float(lon))
        except Exception as e:
            print(f"  ⚠️  {name}: stable lookup failed ({e}), skipping")
            failed += 1
            time.sleep(delay)
            continue

        if new_commute_min is None or new_commute_min <= 0:
            print(f"  ⚠️  {name}: no commute data returned, skipping")
            skipped += 1
            time.sleep(delay)
            continue

        new_commute_score = _score_commute_time(new_commute_min, area_type)

        # Back-calculate base transit score (Transitland portion) from stored values.
        # If stored commute blend was applied: final = base*0.95 + commute*0.05
        # If stored commute was not applied (old rows without commute data): base ≈ final
        if stored_commute_score is not None:
            base_transit = (stored_final - stored_commute_score * COMMUTE_WEIGHT) / (1.0 - COMMUTE_WEIGHT)
        else:
            base_transit = stored_final

        base_transit = max(0.0, min(100.0, base_transit))
        new_final = base_transit * (1.0 - COMMUTE_WEIGHT) + new_commute_score * COMMUTE_WEIGHT
        new_final = round(max(0.0, min(100.0, new_final)), 1)

        delta_min = round(new_commute_min - (stored_commute_min or 0), 1)
        delta_score = round(new_final - stored_final, 1)
        print(f"  {name}: {stored_commute_min or '?'}→{new_commute_min:.1f}min  score {stored_final}→{new_final} (Δ{delta_score:+.1f})")

        if not dry_run:
            pt["score"] = new_final
            if "summary" not in pt:
                pt["summary"] = {}
            pt["summary"]["mean_commute_minutes"] = round(new_commute_min, 1)
            if "details" not in pt:
                pt["details"] = {}
            ct = pt["details"].get("commute_time", {})
            if isinstance(ct, dict):
                ct["mean_minutes"] = round(new_commute_min, 1)
                ct["score"] = round(new_commute_score, 1)
                pt["details"]["commute_time"] = ct
            else:
                pt["details"]["commute_time"] = {
                    "mean_minutes": round(new_commute_min, 1),
                    "score": round(new_commute_score, 1),
                    "weight": COMMUTE_WEIGHT,
                    "note": "Mean commute time (ACS stable) blended into transit score",
                }

        changed += 1
        time.sleep(delay)

    print(f"\nDone: {changed} updated, {skipped} skipped (no data), {failed} failed")

    if not dry_run:
        with open(output_path, "w") as f:
            for row in rows:
                f.write(json.dumps(row) + "\n")
        print(f"Written → {output_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--delay", type=float, default=0.5, help="Seconds between Census API calls (default 0.5)")
    ap.add_argument("--dry-run", action="store_true", help="Print changes without writing")
    args = ap.parse_args()
    patch_file(args.input, args.output, args.delay, args.dry_run)


if __name__ == "__main__":
    main()
