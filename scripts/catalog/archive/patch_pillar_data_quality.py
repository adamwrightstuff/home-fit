#!/usr/bin/env python3
"""
Patch data_quality labels for three pillars where stored quality_tier is inaccurate:

  1. active_outdoors  -- 53 NYC / 12 LA rows have quality_tier='poor' (completeness=0.4)
     Root cause: quality was assessed on the FIRST overpass attempt (which failed), then
     retry/augmentation populated real park data, but quality_tier was never updated.
     Fix: recompute completeness from the summary park counts that are actually stored.

  2. natural_beauty   -- 150 NYC / 94 LA rows have data_quality={}
     Root cause: old batch scored before assess_pillar_data_quality was added.
     Fix: compute quality from the tree_analysis blob already present in the record.

  3. healthcare_access -- 113 NYC / 73 LA rows have quality_tier='very_poor' / api_error
     Root cause: OSM hospital query timed out so _query_failed=True cascaded to very_poor,
     but the score was computed from MAJOR_HOSPITALS static DB + NPI data (real, valid data).
     Fix: estimate completeness from breakdown component scores; set fallback_used=True.

Usage:
  PYTHONPATH=. python3 scripts/catalog/patch_pillar_data_quality.py
  PYTHONPATH=. python3 scripts/catalog/patch_pillar_data_quality.py --dry-run
  PYTHONPATH=. python3 scripts/catalog/patch_pillar_data_quality.py --metro nyc
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]

DATA_FILES = {
    "nyc": REPO_ROOT / "data" / "nyc_metro_place_catalog_scores_merged.jsonl",
    "la":  REPO_ROOT / "data" / "la_metro_place_catalog_scores_merged.jsonl",
}

QUALITY_THRESHOLDS = [
    ("excellent", 0.9),
    ("good",      0.7),
    ("fair",      0.5),
    ("poor",      0.3),
    ("very_poor", 0.0),
]

OSM_SOURCE_QUALITY = 0.9


def _get_quality_tier(completeness: float) -> str:
    for tier, threshold in QUALITY_THRESHOLDS:
        if completeness >= threshold:
            return tier
    return "very_poor"


def _confidence_from_completeness(completeness: float, source_quality: float = OSM_SOURCE_QUALITY) -> int:
    return min(99, int(completeness * 100 * source_quality))


# ---------------------------------------------------------------------------
# Active outdoors patch
# ---------------------------------------------------------------------------

def _patch_active_outdoors(pillar: Dict, name: str) -> Optional[Dict]:
    """
    Return updated data_quality dict if quality_tier='poor' with real data present,
    else return None (no change needed).
    """
    dq = pillar.get("data_quality", {})
    if dq.get("quality_tier") != "poor":
        return None

    summary = pillar.get("summary", {})
    if isinstance(summary, str):
        try:
            summary = eval(summary)  # noqa: S307 -- only internal catalog data
        except Exception:
            return None

    local_parks = summary.get("local_parks", {}) if isinstance(summary, dict) else {}
    parks_count = local_parks.get("count", 0)
    playground_count = local_parks.get("playgrounds", 0)

    trails_info = summary.get("trails", {})
    hiking_count = trails_info.get("count_total", 0) if isinstance(trails_info, dict) else 0

    camping_info = summary.get("camping", {})
    camping_count = camping_info.get("sites", 0) if isinstance(camping_info, dict) else 0

    expected = dq.get("expected_minimums", {})
    expected_local = max(1, expected.get("local_facilities", 5))
    expected_regional = max(1, expected.get("regional_facilities", 3))

    local_score = min(1.0, (parks_count + playground_count) / expected_local)
    regional_score = min(1.0, (hiking_count + camping_count) / expected_regional)
    completeness = (local_score * 0.6) + (regional_score * 0.4)

    new_tier = _get_quality_tier(completeness)
    if new_tier == "poor":
        # Still poor -- park counts genuinely low (Cold Spring Harbor, Nyack type)
        return None

    updated_dq = dict(dq)
    updated_dq["completeness"] = round(completeness, 4)
    updated_dq["quality_tier"] = new_tier
    updated_dq["confidence"] = _confidence_from_completeness(completeness)
    updated_dq["degraded"] = False
    updated_dq["degraded_reasons"] = [r for r in dq.get("degraded_reasons", []) if r != "low_completeness"]
    if not updated_dq["degraded_reasons"]:
        updated_dq["degraded"] = False

    return updated_dq


# ---------------------------------------------------------------------------
# Natural beauty patch
# ---------------------------------------------------------------------------

def _patch_natural_beauty(pillar: Dict, name: str) -> Optional[Dict]:
    """
    Return a new data_quality dict for old-batch NB rows that have data_quality={}.
    """
    dq = pillar.get("data_quality", {})
    if dq:  # already populated -- skip
        return None

    # Old batch format: keys are at top level of the pillar dict.
    tree_analysis = pillar.get("tree_analysis", {})
    if not isinstance(tree_analysis, dict) or not tree_analysis:
        return None

    has_canopy = ("gee_canopy_pct" in tree_analysis or "canopy_pct" in tree_analysis)
    has_natural_context = "natural_context" in tree_analysis
    has_data_availability = "data_availability" in tree_analysis
    has_multi_radius = "multi_radius_canopy" in tree_analysis

    tree_score = sum([has_canopy, has_natural_context, has_data_availability, has_multi_radius]) / 4.0
    # Old batch format doesn't use 'enhancers' or 'scenic_metadata' keys
    enhancer_score = 0.0
    scenic_score = 0.0
    completeness = (tree_score * 0.7) + (enhancer_score * 0.2) + (scenic_score * 0.1)

    data_availability = tree_analysis.get("data_availability", {})
    overall_tier = data_availability.get("overall_tier", "unknown") if isinstance(data_availability, dict) else "unknown"

    sources = []
    if tree_analysis.get("gee_canopy_pct") is not None or tree_analysis.get("canopy_pct") is not None:
        sources.append("gee")
    gvi = pillar.get("green_view_index") or tree_analysis.get("green_view_index")
    if gvi is not None:
        sources.append("gvi")

    return {
        "completeness": round(completeness, 4),
        "quality_tier": _get_quality_tier(completeness),
        "needs_fallback": False,
        "fallback_score": None,
        "fallback_used": False,
        "fallback_metadata": {"fallback_used": False},
        "confidence": _confidence_from_completeness(completeness),
        "data_sources": sources or ["gee"],
        "degraded": False,
        "degraded_reasons": [],
        "data_warnings": [],
        "inferred_from_old_batch": True,
        "data_availability_tier": overall_tier,
    }


# ---------------------------------------------------------------------------
# Healthcare patch
# ---------------------------------------------------------------------------

def _patch_healthcare(pillar: Dict, name: str) -> Optional[Dict]:
    """
    Return updated data_quality dict for api_error cases where score reflects real data.
    """
    dq = pillar.get("data_quality", {})
    if dq.get("data_warning") != "api_error" or dq.get("quality_tier") != "very_poor":
        return None

    score = pillar.get("score") or 0
    breakdown = pillar.get("breakdown", {})

    hospital_access = breakdown.get("hospital_access", 0) or 0
    primary_care = breakdown.get("primary_care", 0) or 0
    pharmacies = breakdown.get("pharmacies", 0) or 0
    specialized_care = breakdown.get("specialized_care", 0) or 0
    emergency_services = breakdown.get("emergency_services", 0) or 0

    # All confirmed api_error cases have hospital_access > 0 (MAJOR_HOSPITALS static DB used).
    # Score itself is the best completeness proxy we have without raw facility counts.
    # Cap at 0.88 (< 'excellent' threshold of 0.9) since hospitals came from a static fallback DB.
    proxy_completeness = min(0.88, score / 100.0) if score else 0.0

    # Count how many components contributed non-trivially
    contributing = sum([
        hospital_access > 5,
        primary_care > 0,
        pharmacies > 0,
        specialized_care > 0,
        emergency_services > 0,
    ])

    if proxy_completeness < 0.3:
        # Score is genuinely low -- still fairly poor quality data
        return None

    npi_count = dq.get("npi_specialty_count", 0) or 0
    source_quality = 0.85 if npi_count > 0 else 0.75

    updated_dq = dict(dq)
    updated_dq["completeness"] = round(proxy_completeness, 4)
    updated_dq["quality_tier"] = _get_quality_tier(proxy_completeness)
    updated_dq["confidence"] = _confidence_from_completeness(proxy_completeness, source_quality)
    updated_dq["fallback_used"] = True
    updated_dq["fallback_metadata"] = {
        "fallback_used": True,
        "fallback_source": "MAJOR_HOSPITALS_static_db",
        "osm_hospital_query_failed": True,
        "contributing_components": contributing,
    }
    updated_dq["data_warning"] = "api_error_recovered"
    updated_dq["data_warnings"] = ["api_error_recovered"]
    updated_dq["degraded"] = False
    updated_dq["degraded_reasons"] = []

    return updated_dq


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

PILLAR_PATCHERS = {
    "active_outdoors": _patch_active_outdoors,
    "natural_beauty":  _patch_natural_beauty,
    "healthcare_access": _patch_healthcare,
}


def patch_file(path: Path, dry_run: bool, verbose: bool) -> Dict[str, int]:
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    counters: Dict[str, int] = {
        "active_outdoors_patched": 0,
        "active_outdoors_skipped_still_poor": 0,
        "natural_beauty_patched": 0,
        "natural_beauty_skipped_no_tree_data": 0,
        "healthcare_access_patched": 0,
        "healthcare_access_skipped_score_too_low": 0,
        "total_rows": len(rows),
    }

    for row in rows:
        place_name = row.get("catalog", {}).get("name", "?")
        pillars = row["score"]["livability_pillars"]

        for pillar_key, patcher in PILLAR_PATCHERS.items():
            pillar = pillars.get(pillar_key)
            if not pillar:
                continue

            new_dq = patcher(pillar, place_name)
            if new_dq is None:
                if pillar_key == "active_outdoors" and pillar.get("data_quality", {}).get("quality_tier") == "poor":
                    counters["active_outdoors_skipped_still_poor"] += 1
                elif pillar_key == "natural_beauty" and not pillar.get("data_quality", {}):
                    counters["natural_beauty_skipped_no_tree_data"] += 1
                elif pillar_key == "healthcare_access" and pillar.get("data_quality", {}).get("quality_tier") == "very_poor":
                    counters["healthcare_access_skipped_score_too_low"] += 1
                continue

            old_tier = pillar.get("data_quality", {}).get("quality_tier", "MISSING")
            new_tier = new_dq["quality_tier"]
            counter_key = f"{pillar_key}_patched"
            counters[counter_key] += 1

            if verbose:
                print(f"  [{pillar_key}] {place_name}: {old_tier} -> {new_tier}  "
                      f"completeness={new_dq.get('completeness', '?'):.3f}  "
                      f"confidence={new_dq.get('confidence', '?')}")

            if not dry_run:
                pillar["data_quality"] = new_dq

    if not dry_run:
        with open(path, "w") as f:
            for row in rows:
                f.write(json.dumps(row, separators=(",", ":")) + "\n")

    return counters


def main() -> None:
    ap = argparse.ArgumentParser(description="Patch pillar data_quality labels in catalog JSONL files")
    ap.add_argument("--dry-run", action="store_true", help="Show what would change without writing")
    ap.add_argument("--metro", choices=["nyc", "la"], help="Process only one metro (default: both)")
    ap.add_argument("--verbose", "-v", action="store_true", help="Print each changed row")
    args = ap.parse_args()

    metros = [args.metro] if args.metro else ["nyc", "la"]

    for metro in metros:
        path = DATA_FILES[metro]
        if not path.exists():
            print(f"[{metro.upper()}] File not found: {path}", file=sys.stderr)
            continue

        prefix = "[DRY RUN] " if args.dry_run else ""
        print(f"\n{prefix}=== {metro.upper()} ({path.name}) ===")
        counters = patch_file(path, dry_run=args.dry_run, verbose=args.verbose)

        print(f"  Total rows: {counters['total_rows']}")
        print(f"  active_outdoors patched:  {counters['active_outdoors_patched']}  "
              f"(skipped still-poor: {counters['active_outdoors_skipped_still_poor']})")
        print(f"  natural_beauty patched:   {counters['natural_beauty_patched']}  "
              f"(skipped no-tree-data: {counters['natural_beauty_skipped_no_tree_data']})")
        print(f"  healthcare patched:       {counters['healthcare_access_patched']}  "
              f"(skipped score-too-low: {counters['healthcare_access_skipped_score_too_low']})")
        if not args.dry_run:
            print(f"  Written -> {path}")


if __name__ == "__main__":
    main()
