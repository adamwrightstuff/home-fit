"""
Pre-compute NPI specialty counts for all catalog places and write to
data/npi_specialty_by_city_state.json.

Run from project root:
    PYTHONPATH=. python3 scripts/baselines/build_npi_specialty_baselines.py

Skips cities already in the cache, so safe to re-run incrementally.
Uses the same city-resolution logic as the pillar to ensure cache hits.
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from data_sources.npi_specialty_client import (  # noqa: E402
    get_specialty_count,
    nppes_city_from_catalog,
    state_from_latlon,
    _nppes_city_from_latlon,
    _nppes_city_from_latlon_ca,
)

CATALOG_FILES = [
    REPO_ROOT / "data" / "nyc_metro_place_catalog_scores_merged.composites_recomputed.jsonl",
    REPO_ROOT / "data" / "sf_metro_place_catalog_scores_merged.composites_recomputed.jsonl",
    REPO_ROOT / "data" / "la_metro_place_catalog_scores_merged.composites_recomputed.jsonl",
]


def resolve_nppes_city(name: str, county_borough: str, state: str, lat: float, lon: float) -> str:
    """Resolve to the same city key the pillar would use at scoring time."""
    state_up = state.strip().upper()
    if state_up == "NY":
        city = _nppes_city_from_latlon(lat, lon, state_up) or name
    elif state_up == "CA":
        city = _nppes_city_from_latlon_ca(lat, lon) or name
    else:
        city = nppes_city_from_catalog(name, county_borough, state)
    return city


def load_places():
    seen = set()
    places = []
    for fpath in CATALOG_FILES:
        if not fpath.exists():
            print(f"  skip (not found): {fpath.name}")
            continue
        with open(fpath) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                cat = rec.get("catalog", {})
                name = cat.get("name", "")
                state = cat.get("state_abbr", "")
                county_borough = cat.get("county_borough", "")
                lat = float(cat.get("lat") or 0)
                lon = float(cat.get("lon") or 0)
                city = resolve_nppes_city(name, county_borough, state, lat, lon)
                key = f"{city.strip().title()},{state.strip().upper()}"
                if key not in seen:
                    seen.add(key)
                    places.append({"city": city, "state": state, "key": key, "lat": lat, "lon": lon})
    return places


def main():
    places = load_places()
    print(f"Found {len(places)} unique city/state pairs across catalogs")

    for i, p in enumerate(places, 1):
        city, state = p["city"], p["state"]
        print(f"[{i}/{len(places)}] {city}, {state} ...", end=" ", flush=True)
        count = get_specialty_count(city, state, lat=p["lat"], lon=p["lon"])
        print(f"{count} specialties")

    print("\nDone. Cache written to data/npi_specialty_by_city_state.json")


if __name__ == "__main__":
    main()
