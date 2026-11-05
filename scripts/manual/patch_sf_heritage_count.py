#!/usr/bin/env python3
"""
Patch heritage_count into the built_environment.summary for all SF catalog places.

NYC and LA got heritage_count when they were batch-scored under a version of main.py
that had a full _extract_built_environment_summary function. That function was removed
before SF was scored, so SF summary only has effective_area_type.

heritage_count = len(charm.get('historic', [])) + nrhp_result.get('count', 0)

Two lightweight calls per place:
  - osm_api.query_charm_features  (one Overpass query, no building polygons)
  - nrhp.query_nrhp               (local SQLite RTree, no network)

Patches both _merged.jsonl and composites_recomputed.jsonl in place.
Heritage_count is metadata only — does not affect scores or composites.

Usage:
    cd /Users/adamwright/Dev/home-fit
    PYTHONPATH=. python3 scripts/manual/patch_sf_heritage_count.py [--dry-run] [--delay 2.0] [--limit N]
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from data_sources import nrhp, osm_api

RADIUS_M = 2000  # matches _score_architectural_diversity default for built_environment

MERGED = REPO_ROOT / "data" / "sf_metro_place_catalog_scores_merged.jsonl"
RECOMPUTED = REPO_ROOT / "data" / "sf_metro_place_catalog_scores_merged.composites_recomputed.jsonl"


def _fetch_heritage(lat: float, lon: float) -> Tuple[int, int]:
    """Returns (landmark_count, nrhp_count). Both are lightweight — no building polygons."""
    def _charm():
        try:
            data = osm_api.query_charm_features(lat, lon, radius_m=RADIUS_M)
            return len((data or {}).get("historic", []))
        except Exception as e:
            print(f"  warn: charm_features failed ({e})", flush=True)
            return 0

    def _nrhp():
        try:
            result = nrhp.query_nrhp(lat, lon, radius_m=RADIUS_M)
            return (result or {}).get("count", 0)
        except Exception as e:
            print(f"  warn: nrhp failed ({e})", flush=True)
            return 0

    with ThreadPoolExecutor(max_workers=2) as ex:
        f_charm = ex.submit(_charm)
        f_nrhp = ex.submit(_nrhp)
        return f_charm.result(), f_nrhp.result()


def _get_coords(entry: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    coords = entry.get("score", {}).get("coordinates") or {}
    lat, lon = coords.get("lat"), coords.get("lon")
    if lat is None or lon is None:
        cat = entry.get("catalog") or {}
        lat, lon = cat.get("lat"), cat.get("lon")
    if lat is None or lon is None:
        return None
    return float(lat), float(lon)


def _place_label(entry: Dict[str, Any]) -> str:
    cat = entry.get("catalog") or {}
    return cat.get("name") or cat.get("city") or "unknown"


def patch_file(path: Path, patches: Dict[str, int], dry_run: bool) -> int:
    """
    Apply heritage_count patches to a JSONL file keyed by (lat, lon) string.
    Returns number of records updated.
    """
    lines = path.read_text().splitlines()
    updated = 0
    out_lines = []
    for line in lines:
        if not line.strip():
            out_lines.append(line)
            continue
        entry = json.loads(line)
        coords = _get_coords(entry)
        if coords is None:
            out_lines.append(line)
            continue
        key = f"{coords[0]},{coords[1]}"
        if key in patches:
            be = (entry.get("score", {}).get("livability_pillars", {}) or {}).get("built_environment")
            if isinstance(be, dict):
                if not isinstance(be.get("summary"), dict):
                    be["summary"] = {}
                be["summary"]["heritage_count"] = patches[key]
                updated += 1
        out_lines.append(json.dumps(entry, separators=(",", ":")))
    if not dry_run:
        path.write_text("\n".join(out_lines) + "\n")
    return updated


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--delay", type=float, default=2.0,
                        help="Seconds to sleep between Overpass calls (default 2.0)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Only process first N places (for testing)")
    args = parser.parse_args()

    entries = []
    with open(MERGED) as f:
        for line in f:
            if line.strip():
                entries.append(json.loads(line))

    if args.limit:
        entries = entries[:args.limit]

    print(f"Processing {len(entries)} SF places (dry_run={args.dry_run}, delay={args.delay}s)")

    patches: Dict[str, int] = {}
    skipped = 0

    for i, entry in enumerate(entries, 1):
        label = _place_label(entry)
        coords = _get_coords(entry)
        if coords is None:
            print(f"  [{i}] {label}: no coords — skip")
            skipped += 1
            continue

        lat, lon = coords
        key = f"{lat},{lon}"

        landmarks, nrhp_count = _fetch_heritage(lat, lon)
        heritage_count = landmarks + nrhp_count
        patches[key] = heritage_count
        print(f"  [{i}/{len(entries)}] {label}: landmarks={landmarks} nrhp={nrhp_count} → heritage_count={heritage_count}")

        if i < len(entries):
            time.sleep(args.delay)

    # Backup and patch both files
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    for path in (MERGED, RECOMPUTED):
        if not path.exists():
            print(f"warn: {path.name} not found — skip")
            continue
        if not args.dry_run:
            bak = path.with_suffix(f".bak.{ts}")
            shutil.copy2(path, bak)
            print(f"backup: {bak.name}")
        n = patch_file(path, patches, dry_run=args.dry_run)
        print(f"{'[dry-run] ' if args.dry_run else ''}patched {n} records in {path.name}")

    print(f"\nDone. {len(patches)} places patched, {skipped} skipped.")


if __name__ == "__main__":
    main()
