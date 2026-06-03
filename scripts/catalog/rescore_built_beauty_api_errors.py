#!/usr/bin/env python3
"""
Rescore built_beauty for catalog entries where the Overpass API failed during
the original batch run (data_warnings contains "api_error"), leaving all OSM
building metrics at zero.

Runs entirely offline against the pillar code — no API server required.

Usage:
    cd /path/to/home-fit
    PYTHONPATH=. python3 scripts/catalog/rescore_built_beauty_api_errors.py \
        --input data/nyc_metro_place_catalog_scores_merged.jsonl \
        --output data/nyc_metro_place_catalog_scores_merged.jsonl \
        [--dry-run] [--delay 3.0] [--limit N]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from pillars.built_beauty import calculate_built_beauty


def _is_api_error(entry: Dict[str, Any]) -> bool:
    bb = (entry.get("score") or entry).get("livability_pillars", {}).get("built_beauty", {})
    if not isinstance(bb, dict):
        return False
    dq = bb.get("data_quality") or {}
    return "api_error" in (dq.get("data_warnings") or [])


def _extract_built_beauty_summary(built_details: Dict) -> Dict:
    """Mirror of main.py _extract_built_beauty_summary."""
    summary: Dict[str, Any] = {}
    arch_analysis = built_details.get("architectural_analysis") or {}

    if isinstance(arch_analysis, dict):
        metrics = arch_analysis.get("metrics") or {}
        summary["height_diversity"] = round(metrics.get("height_diversity") or arch_analysis.get("height_diversity") or 0, 2)
        summary["type_diversity"] = round(metrics.get("type_diversity") or arch_analysis.get("type_diversity") or 0, 2)
        summary["footprint_variation"] = round(metrics.get("footprint_variation") or arch_analysis.get("footprint_variation") or 0, 2)
        summary["built_coverage_ratio"] = round(metrics.get("built_coverage_ratio") or arch_analysis.get("built_coverage_ratio") or 0, 3)
        summary["diversity_score"] = round(metrics.get("diversity_score") or arch_analysis.get("diversity_score") or 0, 2)

        classification = arch_analysis.get("classification") or {}
        if isinstance(classification, dict):
            eat = classification.get("effective_area_type")
            label_map = {
                "historic_urban": "Historic urban fabric",
                "urban_core": "Urban core",
                "urban_residential": "Urban residential",
                "suburban": "Suburban",
                "exurban": "Exurban",
                "rural": "Rural",
            }
            if isinstance(eat, str) and eat in label_map:
                summary["built_form_label"] = label_map[eat]
            tags = classification.get("contextual_tags")
            if isinstance(tags, list) and tags:
                summary["built_context_tags"] = ", ".join(
                    str(t).replace("_", " ").strip().title() for t in tags if t
                )

        historic_ctx = arch_analysis.get("historic_context") or {}
        median_yb = arch_analysis.get("median_year_built")
        if median_yb is None and isinstance(historic_ctx, dict):
            median_yb = historic_ctx.get("median_year_built")
        if median_yb is not None:
            try:
                summary["median_year_built"] = int(median_yb)
            except (TypeError, ValueError):
                pass

        if isinstance(historic_ctx, dict):
            landmarks = int(historic_ctx.get("landmarks") or 0)
            nrhp = int(historic_ctx.get("nrhp_count") or 0)
            summary["heritage_count"] = landmarks + nrhp

    summary["component_score"] = round(built_details.get("component_score_0_50") or 0, 2)
    summary["enhancer_bonus"] = round(built_details.get("enhancer_bonus_scaled") or 0, 2)
    return summary


def rescore_entry(entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Call calculate_built_beauty for one catalog entry.
    Returns the new built_beauty pillar dict, or None on failure.
    """
    score_block = entry.get("score") or entry
    coords = score_block.get("coordinates") or {}
    lat = coords.get("lat")
    lon = coords.get("lon")
    if lat is None or lon is None:
        # Try catalog coordinates
        cat = entry.get("catalog") or {}
        lat = cat.get("lat")
        lon = cat.get("lon")
    if lat is None or lon is None:
        return None

    lat, lon = float(lat), float(lon)
    loc = score_block.get("location_info") or {}
    city = (loc.get("city") or "").strip() or None

    existing_bb = score_block.get("livability_pillars", {}).get("built_beauty", {})
    old_weight = existing_bb.get("weight")
    old_importance = existing_bb.get("importance_level")
    old_contribution = existing_bb.get("contribution")

    result = calculate_built_beauty(lat, lon, city=city)

    new_score = result.get("score")
    if new_score is None:
        return None

    built_details = result.get("details") or {}
    data_quality = result.get("data_quality") or {}

    # Check if we actually got real data this time
    arch = result.get("architectural_details") or built_details.get("architectural_analysis") or {}
    got_data = bool(
        (arch.get("metrics") or {}).get("footprint_variation") or
        (arch.get("metrics") or {}).get("height_diversity") or
        arch.get("footprint_variation") or
        arch.get("height_diversity")
    )

    new_bb = {
        "score": round(float(new_score), 1),
        "weight": old_weight,
        "importance_level": old_importance,
        "contribution": old_contribution,
        "breakdown": {
            "component_score_0_50": round(result.get("component_score_0_50") or 0, 2),
            "enhancer_bonus_raw": round(result.get("built_bonus_raw") or 0, 2),
        },
        "summary": _extract_built_beauty_summary(built_details),
        "confidence": 90 if got_data else 50,
        "data_quality": data_quality,
        "status": "success" if got_data else "fallback",
    }
    return new_bb, got_data


def main() -> None:
    parser = argparse.ArgumentParser(description="Rescore built_beauty for api_error catalog entries")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--delay", type=float, default=3.0, help="Seconds between Overpass calls")
    parser.add_argument("--limit", type=int, default=0, help="Max entries to rescore (0 = all)")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    # Load all rows
    rows = []
    with open(input_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    targets = [(i, r) for i, r in enumerate(rows) if _is_api_error(r)]
    print(f"Total rows: {len(rows)}")
    print(f"api_error entries to rescore: {len(targets)}")
    if args.limit:
        targets = targets[: args.limit]
        print(f"Limiting to {args.limit}")
    if args.dry_run:
        for _, r in targets:
            name = (r.get("catalog") or {}).get("name", "?")
            score = (r.get("score") or r).get("livability_pillars", {}).get("built_beauty", {}).get("score")
            print(f"  would rescore: {name} (current={score})")
        return

    # Backup
    backup = input_path.with_suffix(".bak.bb_rescore")
    shutil.copy2(input_path, backup)
    print(f"Backup: {backup}")

    succeeded = failed = already_good = 0
    for i, (row_idx, row) in enumerate(targets):
        name = (row.get("catalog") or {}).get("name", "?")
        old_score = (row.get("score") or row).get("livability_pillars", {}).get("built_beauty", {}).get("score")
        print(f"[{i+1}/{len(targets)}] {name} (old={old_score}) ...", end=" ", flush=True)

        try:
            result = rescore_entry(row)
            if result is None:
                print("SKIP — no coordinates")
                failed += 1
                continue

            new_bb, got_data = result
            new_score = new_bb["score"]

            if not got_data:
                print(f"STILL NO DATA → {new_score:.1f} (api_error persists, keeping old score)")
                failed += 1
            else:
                # Patch the row
                score_block = row.get("score") or row
                score_block["livability_pillars"]["built_beauty"].update(new_bb)
                print(f"OK  {old_score:.1f} → {new_score:.1f}")
                succeeded += 1

        except Exception as exc:
            print(f"ERROR: {exc}")
            failed += 1

        if i < len(targets) - 1:
            time.sleep(args.delay)

    # Write output
    with open(output_path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, separators=(",", ":")) + "\n")

    print(f"\nDone. Succeeded={succeeded}  Failed/no-data={failed}")
    print(f"Written to {output_path}")
    print(f"Backup at {backup}")


if __name__ == "__main__":
    main()
