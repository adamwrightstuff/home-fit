#!/usr/bin/env python3
"""
Targeted rescore of neighborhood_beauty for NYC catalog places whose stored
water_type is 'ocean' but are not genuinely coastal (river/estuary misclassification).

Runs only=neighborhood_beauty against the local API for each affected place,
merges the result back, and recomputes composites.

Prerequisites:
  - Local API running with the OSM water fix: PYTHONPATH=. python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
  - Run from repo root: PYTHONPATH=. python3 scripts/catalog/rescore_water_type_fix.py

Estimated time: ~60-120s per place × 65 places = 1-2 hours.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

INPUT = REPO_ROOT / "data" / "nyc_metro_place_catalog_scores_merged.jsonl"
API_BASE = "http://localhost:8000"
DELAY_S = 1.0  # pause between requests to avoid hammering OSM

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


def identify_targets(rows: list[dict]) -> list[dict]:
    targets = []
    for row in rows:
        nb = row.get("score", {}).get("livability_pillars", {}).get("neighborhood_beauty", {})
        v9 = nb.get("details", {}).get("natural_beauty", {}).get("v9_breakdown", {})
        wt = v9.get("inputs", {}).get("water_type")
        name = row.get("catalog", {}).get("name", "")
        if wt == "ocean" and name not in GENUINE_OCEAN:
            targets.append(row)
    return targets


def fetch_nb_score(search_query: str) -> dict | None:
    url = f"{API_BASE}/score"
    params = {"location": search_query, "only": "neighborhood_beauty"}
    try:
        r = requests.get(url, params=params, timeout=120)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  ERROR fetching {search_query}: {e}")
        return None


def recompute_total(pillars: dict) -> float:
    weighted = total = 0.0
    for p in pillars.values():
        if not isinstance(p, dict):
            continue
        score = p.get("score")
        weight = p.get("weight")
        if score is not None and weight is not None:
            weighted += float(score) * float(weight)
            total += float(weight)
    return round(weighted / total, 4) if total > 0 else 0.0


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
        old_wt = (
            target.get("score", {})
            .get("livability_pillars", {})
            .get("neighborhood_beauty", {})
            .get("details", {})
            .get("natural_beauty", {})
            .get("v9_breakdown", {})
            .get("inputs", {})
            .get("water_type", "?")
        )
        print(f"[{i+1}/{len(targets)}] {name} (was: {old_wt})")

        result = fetch_nb_score(query)
        if not result:
            failed += 1
            continue

        new_nb = result.get("livability_pillars", {}).get("neighborhood_beauty")
        if not new_nb:
            print(f"  SKIP — no neighborhood_beauty in response")
            failed += 1
            continue

        new_wt = (
            new_nb.get("details", {})
            .get("natural_beauty", {})
            .get("v9_breakdown", {})
            .get("inputs", {})
            .get("water_type", "?")
        )
        new_score = new_nb.get("score", "?")
        print(f"  water_type: {old_wt} → {new_wt}  |  nb_score: {new_score}")

        # Merge new neighborhood_beauty into the row
        row_idx = index[query]
        rows[row_idx]["score"]["livability_pillars"]["neighborhood_beauty"] = new_nb
        rows[row_idx]["score"]["total_score"] = recompute_total(
            rows[row_idx]["score"]["livability_pillars"]
        )
        updated += 1

        time.sleep(DELAY_S)

    print(f"\nDone. {updated} updated, {failed} failed.")
    print(f"Writing {INPUT.name}...")
    INPUT.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    print("Done.")


if __name__ == "__main__":
    main()
