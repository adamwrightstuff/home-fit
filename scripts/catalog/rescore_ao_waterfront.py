#!/usr/bin/env python3
"""
Targeted rescore of active_outdoors for catalog places whose stored
waterfront_lifestyle score came from an inland park beach (natural=beach without
a nearby natural=coastline to confirm it as ocean).

These places received wf=25.0 (ocean beach max) from OSM park/lake beaches
and should score ~22.0 (swimming_area level) instead.

Detection: waterfront_lifestyle > 22.0 AND NB water_type not in (ocean, bay, coastline).

After this script, run recompute_catalog_composites.py to update composite indices.

Prerequisites:
  Local API running: PYTHONPATH=. python3 -m uvicorn main:app --host 0.0.0.0 --port 8000

Usage:
  PYTHONPATH=. python3 scripts/catalog/rescore_ao_waterfront.py \\
    --input data/nyc_metro_place_catalog_scores_merged.jsonl --in-place

  # Dry run (preview affected places, no writes):
  PYTHONPATH=. python3 scripts/catalog/rescore_ao_waterfront.py \\
    --input data/nyc_metro_place_catalog_scores_merged.jsonl --dry-run

  # Both catalogs:
  PYTHONPATH=. python3 scripts/catalog/rescore_ao_waterfront.py \\
    --input data/nyc_metro_place_catalog_scores_merged.jsonl --in-place
  PYTHONPATH=. python3 scripts/catalog/rescore_ao_waterfront.py \\
    --input data/la_metro_place_catalog_scores_merged.jsonl --in-place
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
DELAY_S = 5.0

_PROXY_SECRET = os.environ.get("HOMEFIT_PROXY_SECRET", "")
_HEADERS = {"X-HomeFit-Proxy-Secret": _PROXY_SECRET} if _PROXY_SECRET else {}


def _ao_waterfront(row: dict) -> float:
    ao = row.get("score", {}).get("livability_pillars", {}).get("active_outdoors", {})
    return float((ao.get("breakdown") or {}).get("waterfront_lifestyle") or 0)


def _nb_water_type(row: dict) -> str:
    nb = row.get("score", {}).get("livability_pillars", {}).get("natural_beauty", {})
    v9 = nb.get("details", {}).get("v9_breakdown") or nb.get("v9_breakdown") or {}
    return str((v9.get("inputs") or {}).get("water_type") or "").lower()


def _is_affected(row: dict) -> bool:
    wf = _ao_waterfront(row)
    if wf <= 22.0:
        return False
    wt = _nb_water_type(row)
    return wt not in ("ocean", "bay", "coastline")


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
    args = parser.parse_args()

    if not args.dry_run and not args.in_place and not args.output:
        print("Provide --output, --in-place, or --dry-run")
        sys.exit(1)

    path = Path(args.input)
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    print(f"Loaded {len(rows)} rows from {path.name}")

    targets = [r for r in rows if _is_affected(r)]
    print(f"Affected (wf>22 + non-coastal water_type): {len(targets)}")
    print()

    if args.dry_run:
        for t in sorted(targets, key=lambda r: -_ao_waterfront(r)):
            name = t.get("catalog", {}).get("name", "?")
            print(f"  {name:35s}  wf={_ao_waterfront(t):.1f}  water_type={_nb_water_type(t)}")
        print(f"\nDry run — no changes written.")
        return

    index = {_catalog_key(r): i for i, r in enumerate(rows)}
    updated = failed = 0

    for i, target in enumerate(targets):
        name = target.get("catalog", {}).get("name", "?")
        query = _catalog_key(target)
        old_wf = _ao_waterfront(target)
        print(f"[{i+1}/{len(targets)}] {name}  (wf={old_wf:.1f}, water_type={_nb_water_type(target)})")

        cat = target.get("catalog", {})
        result = fetch_ao(query, lat=cat.get("lat"), lon=cat.get("lon"))
        if not result:
            print(f"  FAILED — no response")
            failed += 1
            continue

        new_ao = result.get("livability_pillars", {}).get("active_outdoors")
        if not new_ao:
            print(f"  FAILED — no active_outdoors in response")
            failed += 1
            continue

        new_wf = (new_ao.get("breakdown") or {}).get("waterfront_lifestyle", "?")
        new_score = new_ao.get("score", "?")
        wb = (new_ao.get("breakdown") or {}).get("waterfront_breakdown", {})
        print(f"  wf: {old_wf:.1f} → {new_wf}  |  ao_score: {new_score}  |  breakdown: {wb}")

        row_idx = index[query]
        rows[row_idx]["score"]["livability_pillars"]["active_outdoors"] = new_ao
        updated += 1

        time.sleep(DELAY_S)

    print(f"\nDone. {updated} updated, {failed} failed.")
    if updated == 0:
        print("Nothing to write.")
        return

    out = Path(args.output) if args.output else path
    out.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    print(f"Written → {out}")
    print(f"\nNext: PYTHONPATH=. python3 scripts/catalog/recompute_catalog_composites.py --input {out} --in-place")


if __name__ == "__main__":
    main()
