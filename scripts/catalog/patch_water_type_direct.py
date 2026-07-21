#!/usr/bin/env python3
"""
Patch water_type for NYC catalog places misclassified as 'ocean' by re-classifying
using query_water_features directly (in-process, no API), then recomputing v9 scores.
"""
from __future__ import annotations
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from data_sources.osm_api import query_water_features
from pillars.natural_beauty import _v9_score_water

INPUT = REPO_ROOT / "data" / "nyc_metro_place_catalog_scores_merged.jsonl"
DELAY_S = 2.0
OWA_WEIGHTS = [0.62, 0.25, 0.10, 0.02, 0.01, 0.00]

GENUINE_OCEAN = {
    'Rockaway Beach', 'Far Rockaway', 'Coney Island', 'City Island', 'Tottenville',
    'Bellmore', 'Long Beach', 'Atlantic Beach', 'Lido Beach', 'Point Lookout',
    'Cedarhurst', 'Hewlett', 'Woodmere', 'Lawrence',
    'Pelham Bay', 'Mamaroneck', 'Eastchester', 'Roslyn',
    'St. George', 'Battery Park City', 'Inwood',
}


def get_water_type(row: dict) -> str | None:
    nb = row.get("score", {}).get("livability_pillars", {}).get("natural_beauty", {})
    return nb.get("details", {}).get("v9_breakdown", {}).get("inputs", {}).get("water_type")


def recompute_owa(v9: dict, new_water_score: float) -> float:
    scores = [
        new_water_score,
        v9.get("gvi_score", 0.0),
        v9.get("canopy_score", 0.0),
        v9.get("topo_score", 0.0),
        v9.get("landcover_score", 0.0),
        v9.get("bio_score", 0.0),
    ]
    ranked = sorted(scores, reverse=True)
    return round(sum(w * s for w, s in zip(OWA_WEIGHTS, ranked)), 2)


def main() -> None:
    print(f"Loading {INPUT.name}...")
    rows = [json.loads(l) for l in INPUT.read_text().splitlines() if l.strip()]
    print(f"  {len(rows)} rows loaded")

    targets = [
        r for r in rows
        if get_water_type(r) == "ocean"
        and r.get("catalog", {}).get("name", "") not in GENUINE_OCEAN
    ]
    print(f"  {len(targets)} places need water_type fix\n")

    index = {
        (r.get("catalog", {}).get("search_query") or r.get("catalog", {}).get("name", "")): i
        for i, r in enumerate(rows)
    }

    updated = skipped = 0

    for i, target in enumerate(targets):
        name = target.get("catalog", {}).get("name", "?")
        cat = target.get("catalog", {})
        lat, lon = cat.get("lat"), cat.get("lon")
        if lat is None or lon is None:
            print(f"[{i+1}/{len(targets)}] {name} — no coordinates, skip")
            skipped += 1
            continue

        print(f"[{i+1}/{len(targets)}] {name} ({lat}, {lon})")
        water_data = query_water_features(float(lat), float(lon))
        if not water_data:
            print(f"  OSM query failed, skip")
            skipped += 1
            time.sleep(DELAY_S)
            continue

        nb_osm = water_data.get("nearest_waterbody") or {}
        new_type = nb_osm.get("type") or "ocean"
        new_dist = water_data.get("nearest_distance_km")

        nb = target["score"]["livability_pillars"]["natural_beauty"]
        v9 = nb.get("details", {}).get("v9_breakdown", {})
        old_type = v9.get("inputs", {}).get("water_type")
        old_dist = v9.get("inputs", {}).get("water_dist_km")

        if new_dist is None:
            new_dist = old_dist

        print(f"  {old_type} → {new_type}  (dist: {new_dist})")

        if new_type == old_type:
            print(f"  no change")
            skipped += 1
            time.sleep(DELAY_S)
            continue

        new_water_score = round(_v9_score_water(new_dist, new_type), 2)
        old_water_score = v9.get("water_score", 0.0)
        new_owa = recompute_owa(v9, new_water_score)
        old_owa = v9.get("owa_score", 0.0)
        print(f"  water_score: {old_water_score} → {new_water_score}  |  owa: {old_owa} → {new_owa}")

        key = cat.get("search_query") or name
        row_idx = index[key]

        v9["inputs"]["water_type"] = new_type
        v9["inputs"]["water_dist_km"] = new_dist
        v9["water_score"] = new_water_score
        v9["owa_score"] = new_owa
        v9["owa_components"] = sorted(
            [new_water_score, v9.get("gvi_score", 0), v9.get("canopy_score", 0),
             v9.get("topo_score", 0), v9.get("landcover_score", 0), v9.get("bio_score", 0)],
            reverse=True
        )
        nb["score"] = new_owa
        updated += 1
        time.sleep(DELAY_S)

    print(f"\nDone. {updated} updated, {skipped} skipped.")
    if updated == 0:
        print("Nothing to write.")
        return
    print(f"Writing {INPUT.name}...")
    INPUT.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    print(f"Done. Run recompute_catalog_composites.py next.")


if __name__ == "__main__":
    main()
