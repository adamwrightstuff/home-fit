#!/usr/bin/env python3
"""
Patch wild_adventure for the 40 places where stored ao_baseline='urban_residential'
caused them to hit the rural branch in _score_wild_adventure_v2.

Fix: the new code routes urban_residential to the suburban branch.  We can derive
the corrected score entirely from stored summary fields — no API calls needed.

Method:
  - Only touches rows where baseline_contexts.active_outdoors == 'urban_residential'
  - Reconstructs synthetic trail/camping lists from stored counts/distances
  - Calls _score_wild_adventure_v2 with area_type='urban_residential' so the
    fixed branch logic applies exactly as it would in live scoring
  - Updates breakdown.wild_adventure, ao.score, and score.total_score in-place

Usage:
  PYTHONPATH=. python3 scripts/manual/recompute_wild_adventure_urban_residential.py \
    data/nyc_metro_place_catalog_scores_merged.composites_recomputed.jsonl \
    data/la_metro_place_catalog_scores_merged.composites_recomputed.jsonl \
    data/sf_metro_place_catalog_scores_merged.composites_recomputed.jsonl
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pillars.active_outdoors import _score_wild_adventure_v2


def _recompute_total(pillars: dict) -> float:
    weighted = total_w = 0.0
    for p in pillars.values():
        if not isinstance(p, dict):
            continue
        score = p.get("score")
        weight = p.get("weight")
        if score is not None and weight is not None:
            weighted += float(score) * float(weight)
            total_w += float(weight)
    return round(weighted / total_w, 4) if total_w > 0 else 0.0


def patch_row(row: dict) -> tuple[bool, str, float, float]:
    sc = row.get("score", {})
    dq = sc.get("data_quality_summary", {})
    area_cls = dq.get("area_classification", {})
    ao_baseline = (area_cls.get("baseline_contexts") or {}).get("active_outdoors")

    if ao_baseline != "urban_residential":
        return False, "skip", 0.0, 0.0

    pillars = sc.get("livability_pillars", {})
    ao = pillars.get("active_outdoors", {})
    if not ao:
        return False, "no ao pillar", 0.0, 0.0

    summary = ao.get("summary", {})
    breakdown = ao.get("breakdown", {})

    trails_s = summary.get("trails", {})
    trail_total = int(trails_s.get("count_total") or 0)
    trail_near = int(trails_s.get("count_within_5km") or 0)

    camping_s = summary.get("camping", {})
    camping_sites = int(camping_s.get("sites") or 0)
    camping_nearest_km = float(camping_s.get("nearest_km") or 99.0)

    canopy_pct = float((summary.get("environment") or {}).get("tree_canopy_pct_5km") or 0.0)

    # Synthetic lists: trail_near within 5 km, rest at 6 km
    hiking_trails = (
        [{"distance_m": 1000}] * trail_near
        + [{"distance_m": 6000}] * max(0, trail_total - trail_near)
    )
    camping_list = (
        [{"distance_m": camping_nearest_km * 1000}] * max(1, camping_sites)
        if camping_sites > 0
        else []
    )

    old_wild = float(breakdown.get("wild_adventure") or 0.0)
    # area_type='urban_residential' → new code routes to suburban branch
    new_wild = _score_wild_adventure_v2(
        hiking_trails, camping_list, canopy_pct, "urban_residential"
    )
    new_wild_r = round(new_wild, 1)

    daily = float(breakdown.get("daily_urban_outdoors") or 0.0)
    water = float(breakdown.get("waterfront_lifestyle") or 0.0)
    new_ao_score = round(max(0.0, min(100.0, daily + new_wild_r + water)), 1)

    breakdown["wild_adventure"] = new_wild_r
    ao["score"] = new_ao_score
    sc["total_score"] = _recompute_total(pillars)

    return True, "ok", old_wild, new_wild_r


def process_file(path: Path) -> None:
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    patched = skipped = 0
    print(f"\n{path.name}")
    print(f"  {'Name':<32} {'old_wild':>8} {'new_wild':>8} {'delta':>6}")
    for row in rows:
        name = (row.get("catalog") or {}).get("name", "?")
        ok, reason, old, new = patch_row(row)
        if ok:
            patched += 1
            print(f"  {name:<32} {old:>8.1f} {new:>8.1f} {new-old:>+6.1f}")
        else:
            skipped += 1

    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    print(f"  → {patched} patched, {skipped} skipped")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    for arg in sys.argv[1:]:
        process_file(Path(arg))


if __name__ == "__main__":
    main()
