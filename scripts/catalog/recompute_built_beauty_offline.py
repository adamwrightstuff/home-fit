#!/usr/bin/env python3
"""
Offline built_beauty score recompute from stored catalog signals.

Uses only what's already in the JSONL — no API calls. Approximates
HistoricCoherence from stored myr + nrhp_count (covers >95% of cases
identically to the live path). Fixes stale 100s introduced by the HC
override regression without a full rescore.

Usage:
    PYTHONPATH=. python3 scripts/catalog/recompute_built_beauty_offline.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from pillars.architectural_beauty_calibrated import compute_calibrated_architectural_beauty_score
from pillars import neighborhood_beauty as nb_pillar

CATALOGS = [
    REPO / "data/nyc_metro_place_catalog_scores_merged.jsonl",
    REPO / "data/la_metro_place_catalog_scores_merged.jsonl",
]


def _hc_from_stored(myr, nrhp_count, block_grain, streetwall) -> float:
    """Approximate HistoricCoherence from stored catalog fields."""
    myr_val = int(myr) if myr else 2000
    nrhp = int(nrhp_count or 0)

    # Primary: myr < 1950 → historic tag → HC floor 92
    historic = myr_val < 1950 or nrhp >= 10
    if not historic:
        return 0.0

    # Rowhouse proxy: low block_grain (fine grain) + high streetwall + pre-war
    # mirrors rowhouse tag heuristic in built_beauty.py
    bg = float(block_grain or 0)
    sw = float(streetwall or 0)
    rowhouse_like = (bg < 55 and sw > 20 and myr_val <= 1955)

    if rowhouse_like:
        return 95.0
    return 92.0


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

        h = summary_bb.get("height_diversity") or 0
        t = summary_bb.get("type_diversity") or 0
        f = summary_bb.get("footprint_variation") or 0
        c = summary_bb.get("built_coverage_ratio") or 0
        myr = hist_ctx.get("median_year_built") or summary_bb.get("median_year_built")
        nrhp = hist_ctx.get("nrhp_count") or 0
        bg = metrics.get("block_grain") or 0
        sw = metrics.get("streetwall_continuity") or 0
        parking_frac = arch.get("parking_share_estimate")

        block_size = None
        if bg:
            block_size = max(60.0, min(700.0, 420.0 - 3.5 * float(bg)))

        hc = _hc_from_stored(myr, nrhp, bg, sw)

        row = {
            "height_diversity":    h,
            "type_diversity":      t,
            "footprint_variation": f,
            "built_coverage":      c,
            "FrontageContinuity":  sw,
            "BlockSize":           block_size,
            "HistoricCoherence":   hc,
            "ParkingFraction":     parking_frac,
        }

        new_score = round(compute_calibrated_architectural_beauty_score(row), 2)
        old_score = (nb.get("breakdown") or {}).get("built_beauty_score")

        if old_score is not None and abs(new_score - float(old_score)) > 0.1:
            name = d.get("catalog", {}).get("name", "?")
            # Re-blend neighborhood_beauty
            bkd = nb.get("breakdown") or {}
            nat_score = bkd.get("natural_beauty_score") or 0.0
            density_val = bkd.get("density")
            eff_at = bkd.get("effective_area_type")
            blend = nb_pillar.blend_scores(new_score, nat_score, density_val, eff_at)
            old_nb = nb.get("score")
            new_nb = round(blend["score"], 4)
            print(f"  {name:35s}  bb {old_score:5.1f}→{new_score:5.1f}  nb {old_nb}→{new_nb}  (HC={hc:.0f})")
            # Patch in-place
            nb["breakdown"]["built_beauty_score"] = new_score
            nb["score"] = new_nb
            if "summary" in nb and "built_beauty" in nb["summary"]:
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
