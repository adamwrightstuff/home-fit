#!/usr/bin/env python3
"""
Offline recalibration of catalog waterfront scores using revised base values.
No API calls — derives new scores from stored waterfront_breakdown + area_type.

Old → new _WATERFRONT_BASE:
  beach:           25 → 25  (no change)
  bay:             12 → 20
  swimming_area:   22 → 20
  lake:            22 → 17
  coastline:       15 → 18
  coastline_rocky: 10 → 10  (no change)

Old → new downweights:
  urban_core non-beach:    0.40 → 0.75
  suburban bay:            0.90 → 1.00  (removed)
  suburban lake:           1.00 → 0.95  (added)
  suburban other:          0.90 → 0.90  (unchanged)

Ratio method: new_score = old_score × (new_eff / old_eff)
  where old_eff = old_base × old_downweight (distance decay cancels out)

Feature type assumed per category (waterfront_breakdown only tracks categories):
  bay_harbor  → bay            (only type in category; exact)
  lake_river  → lake           (dominant natural feature)
  ocean_beach → beach if score is high; coastline if score is low in urban/suburban

After running this, run recompute_catalog_composites.py --no-census --in-place.

Usage:
  PYTHONPATH=. python3 scripts/catalog/recalibrate_waterfront_offline.py \\
    --input data/la_metro_place_catalog_scores_merged.jsonl --dry-run
  for f in data/la_metro_place_catalog_scores_merged.jsonl \\
            data/nyc_metro_place_catalog_scores_merged.jsonl; do
    PYTHONPATH=. python3 scripts/catalog/recalibrate_waterfront_offline.py \\
      --input $f --in-place
  done
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


# Scaling ratio = new_effective / old_effective (distance decay cancels)
# effective = base × downweight

def _bay_ratio(area_type: str) -> float:
    if area_type == "urban_core":
        return (20.0 * 0.75) / (12.0 * 0.40)   # 15.0 / 4.8  = 3.125
    if area_type in {"suburban", "urban_residential"}:
        return (20.0 * 1.00) / (12.0 * 0.90)   # 20.0 / 10.8 = 1.852
    return (20.0 * 1.00) / (12.0 * 1.00)        # 20.0 / 12.0 = 1.667


def _lake_ratio(area_type: str) -> float:
    if area_type == "urban_core":
        return (17.0 * 0.75) / (22.0 * 0.40)   # 12.75 / 8.8  = 1.449
    if area_type in {"suburban", "urban_residential"}:
        return (17.0 * 0.95) / (22.0 * 1.00)   # 16.15 / 22.0 = 0.734
    return (17.0 * 1.00) / (22.0 * 1.00)        # 17.0  / 22.0 = 0.773


def _ocean_beach_ratio(old_score: float, area_type: str) -> float:
    """
    Beach (25→25) has ratio 1.0 (no change).
    Coastline (15→18) has ratio > 1.0.
    Heuristic: low scores in urban/suburban contexts imply coastline, not beach.
    Beach with downweight exemption always gives scores ≥ 25×decay; coastline is capped lower.
    """
    if area_type == "urban_core" and old_score <= 12.0:
        # Coastline urban_core: 15×0.4=6 → 18×0.75=13.5
        return (18.0 * 0.75) / (15.0 * 0.40)   # = 2.25
    if area_type in {"suburban", "urban_residential"} and old_score <= 14.0:
        # Coastline suburban: 15×0.9=13.5 → 18×0.9=16.2
        return (18.0 * 0.90) / (15.0 * 0.90)   # = 1.20
    # Beach: no change
    return 1.0


def _new_category_score(old_score: float, category: str, area_type: str) -> float:
    if old_score <= 0:
        return 0.0
    if category == "bay_harbor":
        ratio = _bay_ratio(area_type)
    elif category == "lake_river":
        ratio = _lake_ratio(area_type)
    elif category == "ocean_beach":
        ratio = _ocean_beach_ratio(old_score, area_type)
    else:
        return old_score
    return min(25.0, old_score * ratio)


def recalibrate_row(row: dict) -> dict | None:
    """
    Returns the updated row, or None if no waterfront score to update.
    Modifies breakdown fields and AO score in-place on a copy.
    """
    import copy
    ao = row.get("score", {}).get("livability_pillars", {}).get("active_outdoors", {})
    bd = ao.get("breakdown") or {}
    old_wf = bd.get("waterfront_lifestyle") or 0.0
    wb = bd.get("waterfront_breakdown") or {}

    if old_wf <= 0:
        return None

    ao_area = ao.get("area_classification") or {}
    area_type = ao_area.get("area_type") or "suburban"

    # Compute new score per category
    categories = ["ocean_beach", "lake_river", "bay_harbor"]
    new_cat_scores: dict[str, float] = {}
    for cat in categories:
        old_cat_score = (wb.get(cat, 0.0) / 100.0) * 25.0  # pct → raw score
        new_cat_scores[cat] = _new_category_score(old_cat_score, cat, area_type)

    new_wf = min(25.0, max(new_cat_scores.values()))
    new_wb = {cat: round(min(100.0, v / 25.0 * 100.0), 1) for cat, v in new_cat_scores.items()}

    if abs(new_wf - old_wf) < 0.05 and new_wb == wb:
        return None  # No meaningful change

    row = copy.deepcopy(row)
    ao_ref = row["score"]["livability_pillars"]["active_outdoors"]
    ao_ref["breakdown"]["waterfront_lifestyle"] = round(new_wf, 1)
    ao_ref["breakdown"]["waterfront_breakdown"] = new_wb

    # Recompute AO total score
    daily = bd.get("daily_urban_outdoors") or 0.0
    wild = bd.get("wild_adventure") or 0.0
    old_ao = ao.get("score") or 0.0
    new_ao = min(100.0, daily + wild + new_wf)
    ao_ref["score"] = round(new_ao, 1)

    return row, old_wf, new_wf, old_ao, new_ao


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output")
    parser.add_argument("--in-place", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.dry_run and not args.in_place and not args.output:
        print("Provide --output, --in-place, or --dry-run")
        raise SystemExit(1)

    path = Path(args.input)
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    print(f"Loaded {len(rows)} rows from {path.name}")

    changes = []
    out_rows = []
    for row in rows:
        result = recalibrate_row(row)
        if result is None:
            out_rows.append(row)
        else:
            new_row, old_wf, new_wf, old_ao, new_ao = result
            out_rows.append(new_row)
            name = row.get("catalog", {}).get("name", "?")
            _ao_disp = row.get("score", {}).get("livability_pillars", {}).get("active_outdoors", {})
            area_type = (_ao_disp.get("area_classification") or {}).get("area_type", "?")
            wb = (row.get("score", {}).get("livability_pillars", {})
                  .get("active_outdoors", {}).get("breakdown") or {}).get("waterfront_breakdown") or {}
            changes.append((name, area_type, old_wf, new_wf, old_ao, new_ao, wb))

    print(f"\n{'Place':<35} {'area_type':<18} {'wf_old':>6} {'wf_new':>6} {'ao_old':>6} {'ao_new':>6}  winning_cat")
    print("-" * 100)
    for name, area_type, old_wf, new_wf, old_ao, new_ao, wb in sorted(changes, key=lambda x: x[3]-x[2]):
        winning_cat = max(wb, key=wb.get) if wb else "?"
        print(f"{name:<35} {area_type:<18} {old_wf:>6.1f} {new_wf:>6.1f} {old_ao:>6.1f} {new_ao:>6.1f}  {winning_cat}")
    print(f"\n{len(changes)} places updated.")

    if args.dry_run:
        print("Dry run — nothing written.")
        return

    out = Path(args.output) if args.output else path
    out.write_text("\n".join(json.dumps(r) for r in out_rows) + "\n")
    print(f"Written → {out}")
    print(f"\nNext: PYTHONPATH=. python3 scripts/catalog/recompute_catalog_composites.py --input {out} --in-place --no-census")


if __name__ == "__main__":
    main()
