#!/usr/bin/env python3
"""
Targeted rescore of active_outdoors for catalog places whose stored AO data
has overpass_error on the trail query (wild_adventure is 0 or near-0) or
the regional query with wf=0 (waterfront data missing from an actual waterway).

These cannot be fixed offline — we have no stored trail counts to work from.

Detection:
  - trail=overpass_error  → wild_adventure is effectively 0, needs re-fetch
  - regional=overpass_error AND waterfront_lifestyle=0  → water query failed

After this script, run recompute_catalog_composites.py to update composites.

Prerequisites:
  Local API running: PYTHONPATH=. python3 -m uvicorn main:app --host 0.0.0.0 --port 8000

Usage:
  # Dry run — show affected places, no API calls:
  PYTHONPATH=. python3 scripts/catalog/rescore_ao_overpass_errors.py \
    --input data/la_metro_place_catalog_scores_merged.jsonl --dry-run
  PYTHONPATH=. python3 scripts/catalog/rescore_ao_overpass_errors.py \
    --input data/nyc_metro_place_catalog_scores_merged.jsonl --dry-run

  # Rescore in-place:
  for f in data/la_metro_place_catalog_scores_merged.jsonl \
            data/nyc_metro_place_catalog_scores_merged.jsonl; do
    PYTHONPATH=. python3 scripts/catalog/rescore_ao_overpass_errors.py \
      --input $f --in-place
  done
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


def _overpass(row: dict) -> dict:
    ao = row.get("score", {}).get("livability_pillars", {}).get("active_outdoors", {})
    return ao.get("summary", {}).get("overpass", {})


def _ao_breakdown(row: dict) -> dict:
    ao = row.get("score", {}).get("livability_pillars", {}).get("active_outdoors", {})
    return ao.get("breakdown") or {}


def _is_affected(row: dict) -> bool:
    op = _overpass(row)
    trail_err = op.get("trail") == "overpass_error"
    reg_err = op.get("regional") == "overpass_error"
    if trail_err:
        return True
    # regional error only — flag if waterfront is also 0 (data went missing)
    if reg_err and (_ao_breakdown(row).get("waterfront_lifestyle") or 0) == 0:
        return True
    return False


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
    targets.sort(key=lambda r: r.get("score", {}).get("livability_pillars", {})
                 .get("active_outdoors", {}).get("score", 99))
    print(f"Affected (trail=overpass_error or reg=error+wf=0): {len(targets)}")
    print()

    if args.dry_run:
        for t in targets:
            name = t.get("catalog", {}).get("name", "?")
            op = _overpass(t)
            bd = _ao_breakdown(t)
            ao_score = t.get("score", {}).get("livability_pillars", {}).get("active_outdoors", {}).get("score", 0)
            print(
                f"  {name:35s}  ao={ao_score:5.1f}"
                f"  wild={bd.get('wild_adventure', 0):5.1f}"
                f"  wf={bd.get('waterfront_lifestyle', 0):5.1f}"
                f"  trail={op.get('trail', '?')}"
                f"  reg={op.get('regional', '?')}"
            )
        print(f"\nDry run — no API calls made.")
        return

    index = {_catalog_key(r): i for i, r in enumerate(rows)}
    updated = failed = 0

    for i, target in enumerate(targets):
        name = target.get("catalog", {}).get("name", "?")
        query = _catalog_key(target)
        op = _overpass(target)
        bd = _ao_breakdown(target)
        old_ao = target.get("score", {}).get("livability_pillars", {}).get("active_outdoors", {}).get("score", 0)
        print(
            f"[{i+1}/{len(targets)}] {name}"
            f"  ao={old_ao:.1f}  wild={bd.get('wild_adventure', 0):.1f}"
            f"  wf={bd.get('waterfront_lifestyle', 0):.1f}"
            f"  trail={op.get('trail')}  reg={op.get('regional')}"
        )

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

        new_bd = new_ao.get("breakdown") or {}
        new_op = (new_ao.get("summary") or {}).get("overpass", {})
        print(
            f"  → ao={new_ao.get('score', '?')}"
            f"  wild={new_bd.get('wild_adventure', '?')}"
            f"  wf={new_bd.get('waterfront_lifestyle', '?')}"
            f"  trail={new_op.get('trail', '?')}"
            f"  reg={new_op.get('regional', '?')}"
        )

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
