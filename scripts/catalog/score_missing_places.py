#!/usr/bin/env python3
"""Score places that are in the input CSV but missing from the merged JSONL catalog."""
import json, requests, sys
from pathlib import Path

BASE_URL = "http://localhost:8000"
REQUEST_TIMEOUT = 600

MISSING = [
    {"name": "Fort Greene",  "county_borough": "Brooklyn",    "state_abbr": "NY", "lat": 40.6867,  "lon": -73.9716, "catalog": "nyc"},
    {"name": "Maspeth",      "county_borough": "Queens",      "state_abbr": "NY", "lat": 40.7254,  "lon": -73.91,   "catalog": "nyc"},
    {"name": "Glendale",     "county_borough": "Queens",      "state_abbr": "NY", "lat": 40.7016,  "lon": -73.8752, "catalog": "nyc"},
    {"name": "Pelham Bay",   "county_borough": "Bronx",       "state_abbr": "NY", "lat": 40.8527,  "lon": -73.827,  "catalog": "nyc"},
    {"name": "Southport",    "county_borough": "Fairfield",   "state_abbr": "CT", "lat": 41.1196,  "lon": -73.2907, "catalog": "nyc"},
    {"name": "Glendale",     "county_borough": "Los Angeles", "state_abbr": "CA", "lat": 34.1425,  "lon": -118.2551,"catalog": "la"},
]

CATALOG_FILES = {
    "nyc": "data/nyc_metro_place_catalog_scores_merged.jsonl",
    "la":  "data/la_metro_place_catalog_scores_merged.jsonl",
}

session = requests.Session()

def score_place(p):
    location = f"{p['name']}, {p['county_borough']}, {p['state_abbr']}"
    print(f"\nScoring: {location}", flush=True)
    r = session.get(f"{BASE_URL}/score", params={
        "location": location,
        "enable_schools": "false",
        "lat": str(p["lat"]),
        "lon": str(p["lon"]),
        "test_mode": "true",
    }, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    return r.json()

results = {"nyc": [], "la": []}

for p in MISSING:
    try:
        result = score_place(p)
    except Exception as e:
        print(f"  ERROR: {e}")
        result = None
    if result:
        row = {
            "catalog": {
                "name": p["name"],
                "county_borough": p["county_borough"],
                "state_abbr": p["state_abbr"],
                "lat": p["lat"],
                "lon": p["lon"],
            },
            "success": True,
            "score": result,
        }
        results[p["catalog"]].append(row)
        print(f"  OK: total_score={result.get('total_score')}")
    else:
        print(f"  SKIPPING {p['name']} ({p['county_borough']}) — score failed")

# Append to catalog files
for catalog, rows in results.items():
    if not rows:
        continue
    path = CATALOG_FILES[catalog]
    with open(path, "a") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
    print(f"\nAppended {len(rows)} rows to {path}")

print("\nDone.")
