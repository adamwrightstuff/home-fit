#!/usr/bin/env python3
"""
Rescore ONLY waterfront_lifestyle for every place in a catalog JSONL -- no hiking,
no camping, no parks, no other pillar. Built to pick up the _beach_is_ocean fix
(pillars/active_outdoors.py) without paying for the Overpass sub-queries a full
active_outdoors rescore would otherwise repeat unchanged. See BACKLOG.md for the
bug this fix addresses and the validation data behind it.

Runs entirely offline from this script's own process -- no FastAPI server needed,
no GEE/Census/other pillar credentials required. Only needs Overpass access
(data_sources.osm_api.query_water_only), which is free and keyless.

Reads area_type from the catalog row's own active_outdoors.area_classification
(already stored, no live lookup needed). Desert-context downweighting is skipped
(assumed False) since none of the current catalog metros (NYC/SF/LA/Seattle) are
desert climates and the flag isn't persisted in the stored catalog row -- reusing
it correctly would require a live canopy/trail lookup, which is exactly what this
script exists to avoid.

Usage:
    PYTHONPATH=. python3 scripts/catalog/rescore_ao_waterfront_only.py \\
        --input data/nyc_metro_place_catalog_scores_merged.composites_recomputed.jsonl \\
        --in-place

    # Dry run first (no writes, just prints what would change):
    PYTHONPATH=. python3 scripts/catalog/rescore_ao_waterfront_only.py \\
        --input data/nyc_metro_place_catalog_scores_merged.composites_recomputed.jsonl \\
        --dry-run

    # All 4 metros:
    for f in data/nyc_metro_place_catalog_scores_merged.composites_recomputed.jsonl \\
             data/la_metro_place_catalog_scores_merged.composites_recomputed.jsonl \\
             data/sf_metro_place_catalog_scores_merged.composites_recomputed.jsonl \\
             data/seattle_metro_place_catalog_scores_merged.composites_recomputed.jsonl; do
        PYTHONPATH=. python3 scripts/catalog/rescore_ao_waterfront_only.py --input "$f" --in-place
    done

After this, run recompute_catalog_composites.py on each file to update total_score/
happiness_index/etc. from the new active_outdoors.score.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from data_sources import osm_api  # noqa: E402
from data_sources.radius_profiles import get_radius_profile  # noqa: E402
from pillars.active_outdoors import _score_water_lifestyle_v2  # noqa: E402


def rescore_row(row: dict, delay: float) -> tuple[dict, bool, str]:
    """Returns (updated_row, changed, note)."""
    catalog = row.get("catalog") or {}
    lat, lon = catalog.get("lat"), catalog.get("lon")
    name = catalog.get("name", "?")

    if not row.get("success") or lat is None or lon is None:
        return row, False, "skipped (no success/lat/lon)"

    score = row.get("score") or {}
    ao = (score.get("livability_pillars") or {}).get("active_outdoors")
    if not ao:
        return row, False, "skipped (no active_outdoors)"

    bd = ao.get("breakdown") or {}
    old_water = bd.get("waterfront_lifestyle")
    old_wb = bd.get("waterfront_breakdown")

    area_type = (ao.get("area_classification") or {}).get("area_type") or "suburban"
    profile = get_radius_profile("active_outdoors", area_type, None)
    radius_m = int(profile.get("regional_radius_m", 15000))

    result = osm_api.query_water_only(lat, lon, radius_m=radius_m)
    time.sleep(delay)
    if result is None:
        return row, False, "skipped (Overpass call failed)"

    swimming = result.get("swimming") or []
    final_water, waterfront_breakdown, best_type, best_dist = _score_water_lifestyle_v2(
        swimming, area_type, is_desert_context=False
    )
    final_water = round(final_water, 1)

    if old_water is not None and abs(final_water - old_water) < 0.05 and old_wb == waterfront_breakdown:
        return row, False, f"unchanged ({final_water})"

    daily = bd.get("daily_urban_outdoors") or 0.0
    wild = bd.get("wild_adventure") or 0.0
    new_ao_score = min(100.0, daily + wild + final_water)

    bd["waterfront_lifestyle"] = final_water
    bd["waterfront_breakdown"] = waterfront_breakdown
    ao["breakdown"] = bd
    ao["score"] = round(new_ao_score, 1)

    note = f"CHANGED water {old_water} -> {final_water} (winner: {waterfront_breakdown.get('winning_feature', {}).get('name') or best_type})"
    return row, True, note


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", type=Path, required=True, help="Source catalog JSONL")
    ap.add_argument("--in-place", action="store_true", help="Write back to --input (timestamped .bak kept unless --no-backup)")
    ap.add_argument("--no-backup", action="store_true")
    ap.add_argument("--output", type=Path, default=None, help="Alternative output path (instead of --in-place)")
    ap.add_argument("--dry-run", action="store_true", help="Print what would change, write nothing")
    ap.add_argument("--delay", type=float, default=1.5, help="Seconds between Overpass calls")
    ap.add_argument("--max-places", type=int, default=0, help="Limit for testing; 0 = all")
    args = ap.parse_args()

    if not args.input.exists():
        print(f"Input not found: {args.input}", file=sys.stderr)
        return 1

    rows = [json.loads(l) for l in args.input.open() if l.strip()]
    if args.max_places:
        rows = rows[: args.max_places]

    changed_count = 0
    skipped_count = 0
    for i, row in enumerate(rows):
        name = (row.get("catalog") or {}).get("name", "?")
        updated, changed, note = rescore_row(row, args.delay)
        rows[i] = updated
        tag = "CHANGED" if changed else "  --   "
        print(f"[{i+1}/{len(rows)}] {tag} {name}: {note}")
        if changed:
            changed_count += 1
        elif "skipped" in note:
            skipped_count += 1

    print(f"\n{changed_count} changed, {skipped_count} skipped, {len(rows) - changed_count - skipped_count} unchanged (of {len(rows)})")

    if args.dry_run:
        print("\n--dry-run: no files written.")
        return 0

    out_path = args.output or (args.input if args.in_place else None)
    if out_path is None:
        print("Nothing written: pass --in-place or --output to save results.", file=sys.stderr)
        return 1

    if args.in_place and not args.no_backup:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = args.input.with_suffix(args.input.suffix + f".{ts}.bak")
        shutil.copy2(args.input, backup)
        print(f"Backup: {backup}")

    with out_path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
    print(f"Wrote: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
