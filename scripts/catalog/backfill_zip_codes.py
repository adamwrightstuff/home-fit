#!/usr/bin/env python3
"""
Backfill missing ZIP codes in catalog JSONL files using Nominatim reverse geocode.

For places where location_info.zip is empty, looks up the postcode from Nominatim
using the lat/lon stored in the catalog entry. Writes results back in-place.

Usage:
    PYTHONPATH=. python3 scripts/catalog/backfill_zip_codes.py \
        --input data/nyc_metro_place_catalog_scores_merged.jsonl
"""

import argparse
import json
import time
import urllib.request
import urllib.parse
from pathlib import Path


def reverse_geocode_zip(lat: float, lon: float) -> str | None:
    """Return postcode for lat/lon via Nominatim, or None if unavailable."""
    params = urllib.parse.urlencode({
        "lat": lat,
        "lon": lon,
        "format": "jsonv2",
        "addressdetails": 1,
        "zoom": 16,
    })
    url = f"https://nominatim.openstreetmap.org/reverse?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "homefit-zip-backfill/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        return data.get("address", {}).get("postcode") or None
    except Exception as e:
        print(f"  Nominatim error: {e}")
        return None


def census_geocoder_zip(lat: float, lon: float) -> str | None:
    """Fallback: Census Geocoder ZCTA lookup by coordinates."""
    params = urllib.parse.urlencode({
        "x": lon,
        "y": lat,
        "benchmark": "Public_AR_Current",
        "vintage": "Current_Current",
        "layers": "86",  # layer 86 = ZIP Code Tabulation Areas
        "format": "json",
    })
    url = f"https://geocoding.geo.census.gov/geocoder/geographies/coordinates?{params}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read())
        zctas = (data.get("result", {})
                     .get("geographies", {})
                     .get("2020 ZIP Code Tabulation Areas", []))
        if zctas:
            return str(zctas[0].get("ZCTA5", "")).zfill(5) or None
    except Exception as e:
        print(f"  Census geocoder error: {e}")
    return None


def backfill_zips(input_path: str) -> None:
    path = Path(input_path)
    rows = []
    with open(path) as f:
        for line in f:
            rows.append(json.loads(line))

    needs_zip = [(i, r) for i, r in enumerate(rows)
                 if not r.get("score", {}).get("location_info", {}).get("zip")]

    print(f"{path.name}: {len(rows)} total, {len(needs_zip)} need ZIP backfill")

    updated = 0
    for i, row in needs_zip:
        name = row.get("catalog", {}).get("name", "?")
        lat = float(row["catalog"]["lat"])
        lon = float(row["catalog"]["lon"])

        zip_code = reverse_geocode_zip(lat, lon)
        time.sleep(1.1)  # Nominatim rate limit: 1 req/sec

        if not zip_code:
            print(f"  [{name}] Nominatim failed, trying Census geocoder...")
            zip_code = census_geocoder_zip(lat, lon)
            time.sleep(0.5)

        if zip_code:
            # Keep only the 5-digit base ZIP
            zip_code = zip_code.split("-")[0].zfill(5)
            rows[i]["score"]["location_info"]["zip"] = zip_code
            print(f"  [{name}] -> {zip_code}")
            updated += 1
        else:
            print(f"  [{name}] -> no ZIP found")

    print(f"\nUpdated {updated}/{len(needs_zip)} places. Writing back...")
    with open(path, "w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
    print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to catalog JSONL")
    args = parser.parse_args()
    backfill_zips(args.input)
