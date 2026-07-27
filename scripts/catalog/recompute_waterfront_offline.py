#!/usr/bin/env python3
"""
Offline correction for waterfront_lifestyle = 16.9 catalog artifact.

Background:
  All coastal places were scored under old code where beach features weren't
  returned by Overpass — only coastline (base 15.0). The suburban downweight
  made the coastline score 13.5. An offline recompute then scaled that by
  25/20 = 16.875 → 16.9 for the entire catalog.

  Current code correctly finds beach features (base 25.0, no downweight for
  suburban). This script derives the correct score offline from stored fields:
    - waterfront_breakdown category  (ocean_beach / lake_river / bay_harbor)
    - ao.area_classification.area_type
    - ao.summary.water.nearest_km

  ocean_beach + suburban/exurban   → beach confirmed, score 25.0
  ocean_beach + urban_residential  → coastline (river/harbor), 15.0 × 0.9 = 13.5
  ocean_beach + urban_core         → coastline, 15.0 × 0.4 = 6.0
  lake_river                       → swimming_area, 22.0 × area_downweight × decay
  bay_harbor                       → bay, 12.0 × area_downweight × decay

  Exceptions:
    BEACH_WHITELIST  — urban_residential places known to have actual beach → 25.0
    COAST_BLACKLIST  — suburban area_type but river/harbor, not beach → coastline score

Usage:
  PYTHONPATH=. python3 scripts/catalog/recompute_waterfront_offline.py --dry-run
  PYTHONPATH=. python3 scripts/catalog/recompute_waterfront_offline.py --in-place
  # Both catalogs:
  for f in data/la_metro_place_catalog_scores_merged.jsonl \\
            data/nyc_metro_place_catalog_scores_merged.jsonl; do
    PYTHONPATH=. python3 scripts/catalog/recompute_waterfront_offline.py --input $f --in-place
  done

After running, regenerate composites:
  PYTHONPATH=. python3 scripts/catalog/recompute_catalog_composites.py \\
    --input data/la_metro_place_catalog_scores_merged.jsonl --in-place
  PYTHONPATH=. python3 scripts/catalog/recompute_catalog_composites.py \\
    --input data/nyc_metro_place_catalog_scores_merged.jsonl --in-place
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

SENTINEL = 16.9  # the artifact value we're fixing

# urban_residential places that genuinely have an ocean beach feature
BEACH_WHITELIST: set[str] = {
    "Coney Island",   # Atlantic beach
}

# suburban area_type but river/harbor — use coastline score not beach
COAST_BLACKLIST: set[str] = {
    "Midtown East",   # East River
    "Weehawken",      # Hudson River (NJ)
    "Edgewater",      # Hudson River (NJ)
}


def _wb_category(ao: dict) -> str:
    wb = (ao.get("breakdown") or {}).get("waterfront_breakdown") or {}
    return max(wb, key=wb.get) if wb else ""


def _area_type(ao: dict) -> str:
    return (ao.get("area_classification") or {}).get("area_type", "suburban")


def _nearest_m(ao: dict) -> float:
    km = (ao.get("summary") or {}).get("water", {}).get("nearest_km") or 99.0
    return float(km) * 1000.0


def _downweight(area_type: str, feature_is_beach_or_lake: bool) -> float:
    if feature_is_beach_or_lake:
        return 1.0
    if area_type == "urban_core":
        return 0.4
    if area_type in ("suburban", "urban_residential"):
        return 0.9
    return 1.0  # rural, exurban — no downweight


def _decay(dist_m: float) -> float:
    return math.exp(-0.00025 * (dist_m - 3000)) if dist_m > 3000 else 1.0


def compute_corrected_waterfront(name: str, ao: dict) -> float | None:
    """Return corrected waterfront score, or None if this row is not the artifact."""
    current = (ao.get("breakdown") or {}).get("waterfront_lifestyle")
    if current != SENTINEL:
        return None

    cat = _wb_category(ao)
    at = _area_type(ao)
    dist_m = _nearest_m(ao)

    if cat == "ocean_beach":
        if name in COAST_BLACKLIST or (at not in ("suburban", "exurban") and name not in BEACH_WHITELIST):
            # river/harbor coastline
            dw = _downweight(at, feature_is_beach_or_lake=False)
            return round(min(25.0, 15.0 * dw * _decay(dist_m)), 1)
        else:
            # actual ocean beach — no downweight, 25.0 base
            return round(min(25.0, 25.0 * _decay(dist_m)), 1)

    elif cat == "lake_river":
        # swimming_area (conservative — rivers usually not lake-tier)
        dw = _downweight(at, feature_is_beach_or_lake=False)
        return round(min(25.0, 22.0 * dw * _decay(dist_m)), 1)

    elif cat == "bay_harbor":
        dw = _downweight(at, feature_is_beach_or_lake=False)
        return round(min(25.0, 12.0 * dw * _decay(dist_m)), 1)

    return None


def _wb_breakdown(cat: str, new_wf: float) -> dict:
    """Rebuild waterfront_breakdown for the corrected score."""
    norm = round(min(100.0, new_wf / 25.0 * 100.0), 1)
    bd: dict = {"ocean_beach": 0.0, "lake_river": 0.0, "bay_harbor": 0.0}
    if cat in bd:
        bd[cat] = norm
    return bd


def _recompute_ao_total(breakdown: dict) -> float:
    return round(max(0.0, min(100.0,
        (breakdown.get("daily_urban_outdoors") or 0.0)
        + (breakdown.get("wild_adventure") or 0.0)
        + (breakdown.get("waterfront_lifestyle") or 0.0)
    )), 1)


def _recompute_total_score(pillars: dict) -> float:
    total = weighted = 0.0
    for p in pillars.values():
        if not isinstance(p, dict):
            continue
        score = p.get("score")
        weight = p.get("weight")
        if score is not None and weight is not None:
            weighted += float(score) * float(weight)
            total += float(weight)
    return round(weighted / total, 2) if total > 0 else 0.0


def process_row(row: dict) -> tuple[bool, str, float, float]:
    """Returns (changed, name, old_wf, new_wf)."""
    name = row.get("catalog", {}).get("name", "?")
    score_doc = row.get("score", {})
    pillars = score_doc.get("livability_pillars", {})
    ao = pillars.get("active_outdoors")
    if not ao:
        return False, name, 0.0, 0.0

    new_wf = compute_corrected_waterfront(name, ao)
    if new_wf is None:
        return False, name, 0.0, 0.0

    old_wf = float((ao.get("breakdown") or {}).get("waterfront_lifestyle", 0.0))
    bd = ao.setdefault("breakdown", {})
    cat = _wb_category(ao)

    bd["waterfront_lifestyle"] = new_wf
    bd["waterfront_breakdown"] = _wb_breakdown(cat, new_wf)
    ao["score"] = _recompute_ao_total(bd)
    score_doc["total_score"] = _recompute_total_score(pillars)

    return True, name, old_wf, new_wf


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output")
    parser.add_argument("--in-place", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.dry_run and not args.in_place and not args.output:
        print("Provide --output, --in-place, or --dry-run")
        return

    path = Path(args.input)
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    print(f"Loaded {len(rows)} rows from {path.name}")

    changed = 0
    for row in rows:
        ok, name, old_wf, new_wf = process_row(row)
        if ok:
            changed += 1
            direction = "↑" if new_wf > old_wf else "↓"
            print(f"  {direction} {name}: {old_wf} → {new_wf}")

    print(f"\n{changed} rows updated.")

    if args.dry_run or changed == 0:
        return

    out = Path(args.output) if args.output else path
    out.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    print(f"Written → {out}")
    print(f"\nNext: run recompute_catalog_composites.py --input {out} --in-place")


if __name__ == "__main__":
    main()
