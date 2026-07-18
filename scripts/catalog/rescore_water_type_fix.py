#!/usr/bin/env python3
"""
Targeted rescore of natural_beauty for NYC catalog places whose stored
water_type is 'ocean' but are not genuinely coastal (river/estuary misclassification).

Runs only=natural_beauty against the local API for each affected place,
merges the result back, and recomputes composites.

Prerequisites:
  - Local API running: PYTHONPATH=. python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
  - Run from repo root: PYTHONPATH=. python3 scripts/catalog/rescore_water_type_fix.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

INPUT = REPO_ROOT / "data" / "nyc_metro_place_catalog_scores_merged.composites_recomputed.jsonl"
API_BASE = "http://localhost:8000"
DELAY_S = 5.0

# Places that are genuinely coastal — leave these alone even if tagged ocean
GENUINE_OCEAN = {
    'Rockaway Beach', 'Far Rockaway', 'Coney Island', 'City Island', 'Tottenville',
    'Bellmore', 'Long Beach', 'Atlantic Beach', 'Lido Beach', 'Point Lookout',
    'Cedarhurst', 'Hewlett', 'Woodmere', 'Lawrence',
    'Pelham Bay', 'Mamaroneck', 'Eastchester', 'Roslyn',
    'St. George', 'Battery Park City', 'Inwood',
}


def catalog_key(row: dict) -> str:
    c = row.get("catalog", {})
    return c.get("search_query") or c.get("name", "")


def get_water_type(row: dict) -> str | None:
    nb = row.get("score", {}).get("livability_pillars", {}).get("natural_beauty", {})
    return nb.get("v9_breakdown", {}).get("inputs", {}).get("water_type")


def identify_targets(rows: list[dict]) -> list[dict]:
    targets = []
    for row in rows:
        wt = get_water_type(row)
        name = row.get("catalog", {}).get("name", "")
        if wt == "ocean" and name not in GENUINE_OCEAN:
            targets.append(row)
    return targets


def fetch_score(search_query: str, lat: float | None = None, lon: float | None = None) -> dict | None:
    url = f"{API_BASE}/score"
    params: dict = {"location": search_query, "only": "natural_beauty"}
    if lat is not None and lon is not None:
        params["lat"] = str(lat)
        params["lon"] = str(lon)
    for attempt in range(3):
        try:
            r = requests.get(url, params=params, timeout=240)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"  attempt {attempt+1}/3 failed: {e}")
            if attempt < 2:
                time.sleep(10)
    return None


def main() -> None:
    print(f"Loading {INPUT.name}...")
    rows = [json.loads(l) for l in INPUT.read_text().splitlines() if l.strip()]
    print(f"  {len(rows)} rows loaded")

    targets = identify_targets(rows)
    print(f"  {len(targets)} places need water_type fix\n")

    index = {catalog_key(r): i for i, r in enumerate(rows)}
    updated = failed = 0

    for i, target in enumerate(targets):
        name = target.get("catalog", {}).get("name", "?")
        query = catalog_key(target)
        old_wt = get_water_type(target)
        print(f"[{i+1}/{len(targets)}] {name} (was: {old_wt})")

        cat = target.get("catalog", {})
        result = fetch_score(query, lat=cat.get("lat"), lon=cat.get("lon"))
        if not result:
            failed += 1
            continue

        new_nb = result.get("livability_pillars", {}).get("natural_beauty")
        if not new_nb:
            print(f"  SKIP — no natural_beauty in response")
            failed += 1
            continue

        new_wt = new_nb.get("v9_breakdown", {}).get("inputs", {}).get("water_type", "?")
        new_score = new_nb.get("score", "?")
        print(f"  water_type: {old_wt} → {new_wt}  |  score: {new_score}")

        row_idx = index[query]
        rows[row_idx]["score"]["livability_pillars"]["natural_beauty"] = new_nb
        updated += 1

        time.sleep(DELAY_S)

    print(f"\nDone. {updated} updated, {failed} failed.")
    if updated == 0:
        print("Nothing to write.")
        return
    print(f"Writing {INPUT.name}...")
    INPUT.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    print(f"Done. Run recompute_catalog_composites.py --input {INPUT} --output {INPUT} next.")


if __name__ == "__main__":
    main()
