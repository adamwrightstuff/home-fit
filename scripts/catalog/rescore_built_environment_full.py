#!/usr/bin/env python3
"""
Full built beauty rescore for both catalog files.

Reuses stored OSM building metrics (height/type/footprint/coverage) to skip
the slow Overpass building-footprint query. Still calls:
  - Census API  → pre_1940_pct, median_year_built
  - OSM charm   → OSM historic landmark count
  - NRHP (local SQLite) → NRHP listing count (fast, no network)

Then applies the current formula (including rowhouse coherence gate + VintageFabric).

Usage:
    cd /path/to/home-fit
    PYTHONPATH=. python3 scripts/catalog/rescore_built_environment_full.py
"""
from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from pillars.built_environment import _fetch_historic_data, calculate_built_environment
from main import _extract_built_environment_summary

CATALOGS = [
    REPO / "data" / "nyc_metro_place_catalog_scores_merged.jsonl",
    REPO / "data" / "la_metro_place_catalog_scores_merged.jsonl",
]

DELAY = 2.0  # seconds between Census/OSM calls


def _get_coords(entry: Dict[str, Any]):
    sc = entry.get("score") or entry
    coords = sc.get("coordinates") or {}
    lat, lon = coords.get("lat"), coords.get("lon")
    if lat is None or lon is None:
        cat = entry.get("catalog") or {}
        lat, lon = cat.get("lat"), cat.get("lon")
    try:
        return float(lat), float(lon)
    except (TypeError, ValueError):
        return None, None


def _stored_arch_diversity(summary: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Reconstruct arch_diversity metrics dict from stored catalog summary."""
    ht = summary.get("height_diversity")
    tp = summary.get("type_diversity")
    ft = summary.get("footprint_variation")
    cov = summary.get("built_coverage_ratio")
    # Require at least one non-zero real metric
    if not any(v for v in [ht, tp, ft, cov] if v):
        return None
    return {
        "levels_entropy": float(ht or 0),
        "building_type_diversity": float(tp or 0),
        "footprint_area_cv": float(ft or 0),
        "built_coverage_ratio": float(cov or 0),
        "diversity_score": float(summary.get("diversity_score") or 0),
        # These signal that data is present (not an error state)
        "beauty_valid": True,
        "confidence_0_1": 1.0,
    }


def rescore_entry(entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    lat, lon = _get_coords(entry)
    if lat is None:
        return None

    sc = entry.get("score") or entry
    loc = sc.get("location_info") or {}
    city = (loc.get("city") or "").strip() or None

    bb = sc.get("livability_pillars", {}).get("built_environment", {})
    summary = bb.get("summary") or {}

    # Reuse stored OSM building metrics — skip Overpass building query
    precomputed = _stored_arch_diversity(summary)

    result = calculate_built_environment(
        lat, lon,
        city=city,
        precomputed_arch_diversity=precomputed,
    )

    new_score = result.get("score")
    if new_score is None:
        return None

    built_details = result.get("details") or {}
    new_summary = _extract_built_environment_summary(built_details)
    data_quality = result.get("data_quality") or {}

    old_weight = bb.get("weight")
    old_importance = bb.get("importance_level")
    old_contribution = bb.get("contribution")

    new_bb = {
        "score": round(float(new_score), 1),
        "weight": old_weight,
        "importance_level": old_importance,
        "contribution": old_contribution,
        "breakdown": {
            "component_score_0_50": round(result.get("component_score_0_50") or 0, 2),
            "enhancer_bonus_raw": round(result.get("built_bonus_raw") or 0, 2),
        },
        "summary": new_summary,
        "confidence": 90,
        "data_quality": data_quality,
        "status": "success",
    }
    return new_bb


def process_catalog(path: Path) -> None:
    print(f"\n{'='*60}")
    print(f"Processing: {path.name}")
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    backup = path.with_suffix(".jsonl.bak.full_bb_rescore")
    shutil.copy2(path, backup)
    print(f"Backup: {backup.name}")
    print(f"Places: {len(rows)}")

    succeeded = failed = 0
    for i, row in enumerate(rows):
        name = (row.get("catalog") or {}).get("name", "?")
        sc = row.get("score") or row
        old_bb = sc.get("livability_pillars", {}).get("built_environment", {})
        old_score = old_bb.get("score") or 0

        print(f"[{i+1}/{len(rows)}] {name} (old={old_score:.1f}) ...", end=" ", flush=True)
        try:
            new_bb = rescore_entry(row)
            if new_bb is None:
                print("SKIP — no coordinates or no result")
                failed += 1
            else:
                new_score = new_bb["score"]
                sc["livability_pillars"]["built_environment"] = new_bb
                delta = new_score - old_score
                print(f"{old_score:.1f} → {new_score:.1f}  ({delta:+.1f})")
                succeeded += 1
        except Exception as exc:
            print(f"ERROR: {exc}")
            failed += 1

        if i < len(rows) - 1:
            time.sleep(DELAY)

    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, separators=(",", ":")) + "\n")

    print(f"\nDone: succeeded={succeeded}  failed={failed}")
    print(f"Written: {path.name}")


if __name__ == "__main__":
    for catalog in CATALOGS:
        if catalog.exists():
            process_catalog(catalog)
        else:
            print(f"Not found: {catalog}")
