"""
Batch-fetch ERA5 monthly climate normals for every catalog place via Open-Meteo.
Stores results in data/catalog_climate_profiles.jsonl (one record per place).

Run from project root:
    PYTHONPATH=. python3 scripts/catalog/batch_climate_profiles.py

No API key required. 5 parallel workers. ~3-5 minutes for all 454 places.
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from data_sources.nasa_power_climate import get_climate_normals
from logging_config import get_logger

logger = get_logger(__name__)

CATALOG_FILES = [
    ("data/sf_metro_place_catalog_scores_merged.composites_recomputed.jsonl", "sf_metro"),
    ("data/nyc_metro_place_catalog_scores_merged.composites_recomputed.jsonl", "nyc_metro"),
    ("data/la_metro_place_catalog_scores_merged.composites_recomputed.jsonl", "la_metro"),
    ("data/vacation_destinations_scores.jsonl", "vacation"),
]

OUTPUT_PATH = Path("data/catalog_climate_profiles.jsonl")
MAX_WORKERS = 1
INTER_REQUEST_DELAY = 3.0  # seconds between requests — avoids rate limiting on free tier


def extract_place(record: dict, source: str) -> dict | None:
    if source == "vacation":
        coords = record.get("score_data", {}).get("coordinates", {})
        lat, lon = coords.get("lat"), coords.get("lon")
        name = record.get("location", "unknown")
    else:
        cat = record.get("catalog", {})
        lat, lon = cat.get("lat"), cat.get("lon")
        name = cat.get("name", "unknown")

    if lat is None or lon is None:
        return None
    return {"name": name, "source": source, "lat": float(lat), "lon": float(lon)}


def load_places() -> list[dict]:
    places = []
    root = Path(__file__).resolve().parents[2]
    for rel_path, source in CATALOG_FILES:
        path = root / rel_path
        if not path.exists():
            logger.warning(f"Catalog file not found: {path}")
            continue
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    place = extract_place(json.loads(line), source)
                    if place:
                        places.append(place)
                except json.JSONDecodeError:
                    pass
    return places


def fetch_one(place: dict) -> dict:
    t0 = time.perf_counter()
    profile = get_climate_normals(place["lat"], place["lon"])
    elapsed = round(time.perf_counter() - t0, 1)
    return {
        "name": place["name"],
        "source": place["source"],
        "lat": place["lat"],
        "lon": place["lon"],
        "climate": profile,
        "_fetch_s": elapsed,
    }


def main():
    places = load_places()
    print(f"Loaded {len(places)} places")

    done_keys: set[str] = set()
    if OUTPUT_PATH.exists():
        with open(OUTPUT_PATH) as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    if rec.get("climate") is not None:  # only skip successful fetches
                        done_keys.add(f"{rec['source']}:{rec['name']}")
                except Exception:
                    pass
        if done_keys:
            print(f"Resuming — {len(done_keys)} already have data, re-fetching nulls")

    remaining = [p for p in places if f"{p['source']}:{p['name']}" not in done_keys]
    if not remaining:
        print("All places already fetched.")
        return

    success = 0
    null_count = 0
    completed = 0

    with open(OUTPUT_PATH, "a") as out:
        for place in remaining:
            result = fetch_one(place)
            out.write(json.dumps(result) + "\n")
            out.flush()
            completed += 1
            if result["climate"]:
                success += 1
            else:
                null_count += 1
            print(f"[{completed}/{len(remaining)}] {result['name']} ({result['source']}) — {'OK' if result['climate'] else 'null'} {result['_fetch_s']}s")
            time.sleep(INTER_REQUEST_DELAY)

    total = success + null_count
    print(f"\nDone. {success}/{total} profiles fetched, {null_count} null.")
    print(f"Output: {OUTPUT_PATH}")

    sunshine_count = sum(
        1 for line in open(OUTPUT_PATH)
        if any(m.get("sunshine_hrs_per_day") is not None
               for m in (json.loads(line).get("climate") or {}).get("months", []))
    )
    print(f"Sunshine coverage: {sunshine_count}/{total} places")


if __name__ == "__main__":
    main()
