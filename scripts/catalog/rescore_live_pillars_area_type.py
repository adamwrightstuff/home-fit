#!/usr/bin/env python3
"""
Live rescore of active_outdoors, public_transit_access, and economic_security
for catalog places whose effective_area_type changed (reclassified places).

These pillars use area_type for radius/bucket selection and can't be fixed offline.

Usage:
    PYTHONPATH=. python3 scripts/catalog/rescore_live_pillars_area_type.py
"""
import json
import shutil
import time
from pathlib import Path

from pillars.active_outdoors import get_active_outdoors_score
from pillars.public_transit_access import get_public_transit_score
from pillars.economic_security import get_economic_security_score

CATALOGS = [
    Path("data/nyc_metro_place_catalog_scores_merged.jsonl"),
    Path("data/la_metro_place_catalog_scores_merged.jsonl"),
]

PILLARS = {
    "active_outdoors": get_active_outdoors_score,
    "public_transit_access": get_public_transit_score,
    "economic_security": get_economic_security_score,
}


def rescore_place(row: dict) -> dict:
    score = row["score"]
    coords = score.get("coordinates", {})
    lat, lon = coords.get("lat"), coords.get("lon")
    if not lat or not lon:
        return row

    nb = score.get("livability_pillars", {}).get("neighborhood_beauty", {})
    area_type = nb.get("breakdown", {}).get("effective_area_type")
    density = nb.get("breakdown", {}).get("density")
    loc = score.get("location_info", {})
    city = loc.get("city")
    state = loc.get("state")

    pillars = score.setdefault("livability_pillars", {})

    # active_outdoors
    try:
        s, d = get_active_outdoors_score(lat, lon, city=city, area_type=area_type)
        if s is not None:
            pillars["active_outdoors"] = {**d, "score": round(float(s), 2), "status": "success"}
    except Exception as e:
        print(f"    active_outdoors error: {e}")

    # public_transit_access
    try:
        s, d = get_public_transit_score(lat, lon, area_type=area_type, city=city, density=density)
        if s is not None:
            pillars["public_transit_access"] = {**d, "score": round(float(s), 2), "status": "success"}
    except Exception as e:
        print(f"    public_transit_access error: {e}")

    # economic_security
    try:
        s, d = get_economic_security_score(lat, lon, city=city, state=state, area_type=area_type)
        if s is not None:
            pillars["economic_security"] = {**d, "score": round(float(s), 2), "status": "success"}
    except Exception as e:
        print(f"    economic_security error: {e}")

    return row


def process(path: Path):
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    updated = errors = 0

    for i, row in enumerate(rows, 1):
        name = row.get("catalog", {}).get("name", "?")
        nb = row["score"].get("livability_pillars", {}).get("neighborhood_beauty", {})
        area_type = nb.get("breakdown", {}).get("effective_area_type", "")

        # Only rescore places that are NOT suburban/exurban/rural — those didn't change
        # meaningfully, and skipping them saves ~2/3 of API calls.
        if area_type in ("suburban", "exurban", "rural", "unknown", ""):
            continue

        print(f"  [{i}/{len(rows)}] {name} ({area_type})")
        try:
            row = rescore_place(row)
            updated += 1
        except Exception as e:
            print(f"    ERROR: {e}")
            errors += 1

        if updated % 10 == 0:
            print(f"    ... {updated} rescored so far")

    bak = path.with_suffix(path.suffix + f".bak.live.{int(time.time())}")
    shutil.copy2(path, bak)
    path.write_text("\n".join(json.dumps(r, separators=(',', ':')) for r in rows) + "\n")
    print(f"{path.name}: rescored={updated} errors={errors}")


for catalog in CATALOGS:
    print(f"\n=== {catalog.name} ===")
    process(catalog)

print("\nDone. Run recompute_catalog_composites.py next.")
