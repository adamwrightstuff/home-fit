#!/usr/bin/env python3
"""
Patch best_feature_type and best_feature_dist_m into the stored AO summary
for every catalog place that has waterfront_lifestyle > 0.

The new code in _score_water_lifestyle_v2 now tracks the winning water feature's
type and distance. This script bakes those fields into the catalog WITHOUT
touching any scores, breakdowns, or other fields.

Safe by design: only writes the two new metadata fields; scores are untouched.
If a place Overpass-errors during this run, the old data is preserved as-is.

Usage:
  # Dry run (show what would be patched, no API calls):
  PYTHONPATH=. python3 scripts/catalog/patch_ao_water_winner.py \
    --input data/la_metro_place_catalog_scores_merged.jsonl --dry-run
  PYTHONPATH=. python3 scripts/catalog/patch_ao_water_winner.py \
    --input data/nyc_metro_place_catalog_scores_merged.jsonl --dry-run

  # Patch in-place:
  for f in data/la_metro_place_catalog_scores_merged.jsonl \
            data/nyc_metro_place_catalog_scores_merged.jsonl; do
    PYTHONPATH=. python3 scripts/catalog/patch_ao_water_winner.py \
      --input $f --in-place
  done

Prerequisites:
  Local API running: PYTHONPATH=. python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

API_BASE = "http://localhost:8000"
DELAY_S = 3.0

_PROXY_SECRET = os.environ.get("HOMEFIT_PROXY_SECRET", "")
_HEADERS = {"X-HomeFit-Proxy-Secret": _PROXY_SECRET} if _PROXY_SECRET else {}


def _ao(row: dict) -> dict:
    return row.get("score", {}).get("livability_pillars", {}).get("active_outdoors", {})


def _is_waterfront_place(row: dict) -> bool:
    bd = _ao(row).get("breakdown") or {}
    return (bd.get("waterfront_lifestyle") or 0) > 0


def _already_patched(row: dict) -> bool:
    water = (_ao(row).get("summary") or {}).get("water") or {}
    return "best_feature_type" in water


def _catalog_key(row: dict) -> str:
    c = row.get("catalog", {})
    return c.get("search_query") or c.get("name", "")


def fetch_ao(search_query: str, lat: float | None, lon: float | None) -> dict | None:
    params: dict = {"location": search_query, "only": "active_outdoors"}
    if lat is not None and lon is not None:
        params["lat"] = str(lat)
        params["lon"] = str(lon)
    for attempt in range(3):
        try:
            r = requests.get(
                f"{API_BASE}/score", params=params, timeout=300, headers=_HEADERS
            )
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"  attempt {attempt+1}/3 failed: {e}")
            if attempt < 2:
                time.sleep(10)
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output")
    parser.add_argument("--in-place", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-already-patched", action="store_true", default=True,
                        help="Skip places that already have best_feature_type (default on)")
    parser.add_argument("--force-all", action="store_true",
                        help="Re-patch even places that already have best_feature_type")
    args = parser.parse_args()

    if not args.dry_run and not args.in_place and not args.output:
        print("Provide --output, --in-place, or --dry-run")
        sys.exit(1)

    path = Path(args.input)
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    print(f"Loaded {len(rows)} rows from {path.name}")

    targets = [r for r in rows if _is_waterfront_place(r)]
    if args.skip_already_patched and not args.force_all:
        already = [r for r in targets if _already_patched(r)]
        targets = [r for r in targets if not _already_patched(r)]
        print(f"Waterfront places: {len(targets) + len(already)}  (already patched: {len(already)}, to patch: {len(targets)})")
    else:
        print(f"Waterfront places to patch: {len(targets)}")

    if args.dry_run:
        for t in targets:
            name = t.get("catalog", {}).get("name", "?")
            bd = (_ao(t).get("breakdown") or {})
            wf = bd.get("waterfront_lifestyle", 0)
            wb = bd.get("waterfront_breakdown") or {}
            print(f"  {name:35s}  wf={wf:5.1f}  breakdown={wb}")
        print(f"\nDry run — no API calls. Would patch {len(targets)} places.")
        return

    index = {_catalog_key(r): i for i, r in enumerate(rows)}
    patched = failed = skipped = 0

    for i, target in enumerate(targets):
        name = target.get("catalog", {}).get("name", "?")
        query = _catalog_key(target)
        bd = (_ao(target).get("breakdown") or {})
        wf = bd.get("waterfront_lifestyle", 0)
        print(f"[{i+1}/{len(targets)}] {name}  wf={wf:.1f}", end="  ", flush=True)

        cat = target.get("catalog", {})
        result = fetch_ao(query, lat=cat.get("lat"), lon=cat.get("lon"))
        if not result:
            print("FAILED — no response")
            failed += 1
            continue

        new_ao = result.get("livability_pillars", {}).get("active_outdoors")
        if not new_ao:
            print("FAILED — no active_outdoors in response")
            failed += 1
            continue

        new_water = (new_ao.get("summary") or {}).get("water") or {}
        feat_type = new_water.get("best_feature_type")
        feat_dist = new_water.get("best_feature_dist_m")

        if feat_type is None:
            print(f"SKIP — no best_feature_type in response (Overpass may have errored)")
            skipped += 1
            time.sleep(DELAY_S)
            continue

        # Surgical patch: only write the two new fields, leave everything else untouched
        row_idx = index[query]
        ao_data = rows[row_idx]["score"]["livability_pillars"]["active_outdoors"]
        if "summary" not in ao_data:
            ao_data["summary"] = {}
        if "water" not in ao_data["summary"]:
            ao_data["summary"]["water"] = {}
        ao_data["summary"]["water"]["best_feature_type"] = feat_type
        if feat_dist is not None:
            ao_data["summary"]["water"]["best_feature_dist_m"] = feat_dist

        print(f"→ {feat_type} @ {feat_dist:.0f}m" if feat_dist else f"→ {feat_type}")
        patched += 1
        time.sleep(DELAY_S)

    print(f"\nDone. {patched} patched, {skipped} skipped (no winner), {failed} failed.")
    if patched == 0:
        print("Nothing to write.")
        return

    out = Path(args.output) if args.output else path
    out.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    print(f"Written → {out}")
    print(f"\nNo composites recompute needed — scores unchanged.")


if __name__ == "__main__":
    main()
