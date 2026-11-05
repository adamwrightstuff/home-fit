"""
Fix incorrect lat/lon pins for Maspeth (industrial dead tract) and Southport CT
(Long Island Sound water tract), then full-rescore both places via the local API
using the corrected coordinates.

Corrected pins verified by Census tract density probe:
  Maspeth:   40.7254, -73.9100 → 40.7285, -73.9045 (tract 36081051500, ~40k density)
  Southport: 41.1196, -73.2907 → 41.1230, -73.2850 (tract 09120061600, ~2600 density)

After this script, run:
  PYTHONPATH=. python3 scripts/catalog/recompute_catalog_composites.py \
    --input data/nyc_metro_place_catalog_scores_merged.jsonl \
    --output data/nyc_metro_place_catalog_scores_merged.jsonl

Usage:
  PYTHONPATH=. python3 scripts/manual/fix_bad_pin_and_rescore.py [--dry-run]
"""

import argparse
import json
import os
import sys
import requests

CORRECTED_PINS = {
    "Maspeth": {"lat": 40.7285, "lon": -73.9045},
    "Southport": {"lat": 41.1230, "lon": -73.2850},
}

# Pillars to skip rescoring — already patched from official election data
SKIP_PILLARS = {"political_lean"}

NYC_FILES = [
    "data/nyc_metro_place_catalog_scores_merged.jsonl",
    "data/nyc_metro_place_catalog_scores_merged.composites_recomputed.jsonl",
]

API_BASE = os.environ.get("HOMEFIT_API_BASE", "http://127.0.0.1:8000")
PROXY_SECRET = os.environ.get("HOMEFIT_PROXY_SECRET", "")


def patch_lat_lon(places: list, dry_run: bool) -> tuple[list, dict]:
    """Patch catalog lat/lon for target places. Returns (updated_places, {name: old_coords})."""
    changed = {}
    for p in places:
        name = p.get("catalog", {}).get("name", "")
        if name not in CORRECTED_PINS:
            continue
        old = {"lat": p["catalog"].get("lat"), "lon": p["catalog"].get("lon")}
        new = CORRECTED_PINS[name]
        if not dry_run:
            p["catalog"]["lat"] = new["lat"]
            p["catalog"]["lon"] = new["lon"]
        changed[name] = {"old": old, "new": new}
        print(f"  {'[DRY] ' if dry_run else ''}Pin {name}: ({old['lat']},{old['lon']}) → ({new['lat']},{new['lon']})")
    return places, changed


def full_rescore(name: str, lat: float, lon: float, search_query: str, timeout: int = 120) -> dict | None:
    """Call full /score with pinned lat/lon. Returns livability_pillars dict or None."""
    params = {"location": search_query or name, "lat": lat, "lon": lon, "enable_schools": "false"}
    headers = {}
    if PROXY_SECRET:
        headers["X-HomeFit-Proxy-Secret"] = PROXY_SECRET
    try:
        print(f"  Scoring {name} at ({lat},{lon}) ...", flush=True)
        r = requests.get(f"{API_BASE}/score", params=params, headers=headers, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        return data.get("livability_pillars")
    except Exception as e:
        print(f"  ERROR scoring {name}: {e}", file=sys.stderr)
        return None


def merge_pillars(existing: dict, fresh: dict) -> dict:
    """Merge fresh pillar scores into existing, skipping SKIP_PILLARS."""
    merged = dict(existing)
    for pillar, data in fresh.items():
        if pillar in SKIP_PILLARS:
            print(f"    Skipping {pillar} (manually patched)")
            continue
        merged[pillar] = data
    return merged


def write_file(path: str, places: list) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        for p in places:
            f.write(json.dumps(p) + "\n")
    os.replace(tmp, path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Patch pins but don't call API or write files")
    args = parser.parse_args()

    # Step 1: Patch lat/lon in both JSONL files
    print("=== Patching lat/lon ===")
    all_places = {}
    for path in NYC_FILES:
        if not os.path.exists(path):
            print(f"  SKIP (not found): {path}")
            continue
        with open(path) as f:
            places = [json.loads(l) for l in f if l.strip()]
        places, changed = patch_lat_lon(places, args.dry_run)
        all_places[path] = places
        if not args.dry_run and changed:
            write_file(path, places)
            print(f"  Wrote {path}")

    if args.dry_run:
        print("\n[DRY RUN] Stopping before API calls.")
        return

    # Step 2: Full rescore via API using corrected pins (only on merged, not composites_recomputed)
    merged_path = "data/nyc_metro_place_catalog_scores_merged.jsonl"
    if merged_path not in all_places:
        print("Merged file not loaded; cannot rescore.")
        return

    places = all_places[merged_path]
    rescored = {}
    for p in places:
        name = p.get("catalog", {}).get("name", "")
        if name not in CORRECTED_PINS:
            continue
        pin = CORRECTED_PINS[name]
        sq = (p.get("catalog", {}).get("search_query") or name).strip()
        fresh_pillars = full_rescore(name, pin["lat"], pin["lon"], sq)
        if fresh_pillars is None:
            print(f"  Rescore failed for {name} — lat/lon patched but pillar data unchanged")
            continue
        existing = p.get("score", {}).get("livability_pillars", {})
        p["score"]["livability_pillars"] = merge_pillars(existing, fresh_pillars)
        rescored[name] = list(fresh_pillars.keys())
        print(f"  Merged {len(fresh_pillars)} pillars for {name}: {sorted(fresh_pillars.keys())}")

    if rescored:
        write_file(merged_path, places)
        print(f"\nWrote {merged_path}")
        print("\nNext: recompute composites, then copy to composites_recomputed:")
        print("  PYTHONPATH=. python3 scripts/catalog/recompute_catalog_composites.py \\")
        print("    --input data/nyc_metro_place_catalog_scores_merged.jsonl \\")
        print("    --output data/nyc_metro_place_catalog_scores_merged.jsonl")
    else:
        print("\nNo places rescored.")


if __name__ == "__main__":
    main()
