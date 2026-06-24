#!/usr/bin/env python3
"""
Apply compute_built_beauty_v3 to catalog using stored form metrics.
No API calls — reads signals from JSONL.

Differences from the old HC-based offline patcher:
  - Uses density-scaled floor for dense urban (no more myr<1950 HC floor).
  - Passes built_coverage_ratio to blend_scores so the BCR ceiling is applied.
  - Overrides blend area_type for low-density (<10k) misclassified historic_urban/
    urban_core places so the 0.65 built-weight floor doesn't inflate them.

    PYTHONPATH=. python3 scripts/catalog/apply_v3_beauty_to_catalog.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from pillars.architectural_beauty_calibrated import compute_built_beauty_v3
from pillars import neighborhood_beauty as nb_pillar

CATALOGS = [
    REPO / "data/nyc_metro_place_catalog_scores_merged.jsonl",
    REPO / "data/la_metro_place_catalog_scores_merged.jsonl",
]


def _blend_area_type(eff_at: str | None, density: float) -> str | None:
    """Correct area_type for blend_scores when the classifier mislabeled low-density
    places as historic_urban/urban_core: their 0.65 built-weight floor is wrong."""
    if eff_at in ("historic_urban", "urban_core") and (density or 0) < 10_000:
        return "suburban"
    return eff_at


def recompute(path: Path, dry_run: bool) -> dict:
    lines = path.read_text().splitlines()
    out_lines = []
    stats = {"total": 0, "changed": 0, "skipped": 0}

    for raw in lines:
        raw = raw.strip()
        if not raw:
            out_lines.append(raw)
            continue
        try:
            d = json.loads(raw)
        except json.JSONDecodeError:
            out_lines.append(raw)
            stats["skipped"] += 1
            continue

        stats["total"] += 1
        nb = d.get("score", {}).get("livability_pillars", {}).get("neighborhood_beauty", {})
        summary_bb = (nb.get("summary") or {}).get("built_beauty") or {}
        det_bb = (nb.get("details") or {}).get("built_beauty") or {}
        arch = det_bb.get("architectural_analysis") or {}
        metrics = arch.get("metrics") or {}
        hist_ctx = arch.get("historic_context") or {}
        bkd = nb.get("breakdown") or {}

        h   = summary_bb.get("height_diversity") or 0
        t   = summary_bb.get("type_diversity") or 0
        f   = summary_bb.get("footprint_variation") or 0
        c   = summary_bb.get("built_coverage_ratio") or 0
        sw  = metrics.get("streetwall_continuity") or 0
        bg  = metrics.get("block_grain") or 0
        myr = hist_ctx.get("median_year_built") or summary_bb.get("median_year_built")
        nrhp       = hist_ctx.get("nrhp_count") or 0
        parking_frac = arch.get("parking_share_estimate")
        density    = bkd.get("density") or 0
        eff_at     = bkd.get("effective_area_type")

        row = {
            "height_diversity":    h,
            "type_diversity":      t,
            "footprint_variation": f,
            "built_coverage":      c,
            "StreetwallContinuity": sw,
            "BlockGrain":           bg,
            "NrhpCount":            nrhp,
            "MedianYearBuilt":      myr,
            "ParkingFraction":      parking_frac,
        }

        new_score = round(compute_built_beauty_v3(row, area_type=eff_at or "suburban",
                                                   density=density or 0.0), 2)
        old_score = bkd.get("built_beauty_score")

        if old_score is not None and abs(new_score - float(old_score)) > 0.1:
            nat_score  = bkd.get("natural_beauty_score") or 0.0
            blend_at   = _blend_area_type(eff_at, density)
            # Only pass BCR when coverage is meaningfully measured (>0.05).
            # coverage=0 in OSM often means missing data, not a genuinely bare site.
            bcr = float(c) if (c and float(c) > 0.05) else None
            blend = nb_pillar.blend_scores(
                new_score, nat_score, density, blend_at,
                built_coverage_ratio=bcr,
            )
            new_nb = round(blend["score"], 4)
            old_nb = nb.get("score")
            name   = d.get("catalog", {}).get("name", "?")
            print(f"  {name:35s}  bb {float(old_score):5.1f}→{new_score:5.1f}  "
                  f"nb {old_nb}→{new_nb}  bw={blend['built_weight']:.2f}")

            nb["breakdown"]["built_beauty_score"] = new_score
            nb["score"] = new_nb
            if "built_beauty" in (nb.get("summary") or {}):
                nb["summary"]["built_beauty"]["component_score"] = new_score
            stats["changed"] += 1

        out_lines.append(json.dumps(d, separators=(",", ":")))

    if not dry_run:
        shutil.copy(path, path.with_suffix(".jsonl.bak"))
        path.write_text("\n".join(out_lines) + "\n")

    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.dry_run:
        print("DRY RUN — no files written\n")

    for path in CATALOGS:
        if not path.exists():
            print(f"  skipping {path.name} (not found)")
            continue
        print(f"\n=== {path.name} ===")
        stats = recompute(path, args.dry_run)
        print(f"  {stats['changed']} changed / {stats['total']} total")


if __name__ == "__main__":
    main()
