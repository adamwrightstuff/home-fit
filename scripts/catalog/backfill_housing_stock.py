#!/usr/bin/env python3
"""
Backfill housing stock type data from Census ACS B25024 (Units in Structure)
into catalog JSONL files.

Adds score.housing_stock with:
  pct_low_density  — share of units in 1–4 unit structures (detached SFH,
                     attached/rowhouse, 2-unit, 3-4 unit)
  total_units      — total housing units from B25024_001E
  source           — 'acs5_2022_tract'

Low-density stock clearly separates brownstone Brooklyn / SFH suburbs from
Manhattan's apartment core: pct_low_density ≥ 0.25 is the recommended
filter threshold for "meaningful SF/townhouse inventory".

Usage:
  PYTHONPATH=. python3 scripts/catalog/backfill_housing_stock.py \\
      --input data/nyc_metro_place_catalog_scores_merged.composites_recomputed.jsonl \\
      --output data/nyc_metro_place_catalog_scores_merged.composites_recomputed.jsonl

  # Dry-run (print results, don't write):
  PYTHONPATH=. python3 scripts/catalog/backfill_housing_stock.py \\
      --input data/la_metro_place_catalog_scores_merged.composites_recomputed.jsonl \\
      --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()

CENSUS_API_KEY = os.getenv("CENSUS_API_KEY")
CENSUS_BASE_URL = "https://api.census.gov/data"

# B25024 — Units in Structure (ACS 5-year 2022)
# 001E = Total housing units
# 002E = 1-unit, detached        \
# 003E = 1-unit, attached         |  "low density" = SF + townhouse + small multifamily
# 004E = 2 units                  |
# 005E = 3 or 4 units            /
B25024_VARS = "B25024_001E,B25024_002E,B25024_003E,B25024_004E,B25024_005E"


def _census_int(val) -> Optional[int]:
    if val is None:
        return None
    s = str(val).strip()
    if s in ("-666666666", "-999999999", "-888888888", "-555555555") or (s.startswith("-") and len(s) > 1):
        return None
    try:
        v = int(float(s))
        return v if v >= 0 else None
    except (ValueError, TypeError):
        return None


def get_census_tract(lat: float, lon: float) -> Optional[dict]:
    """Resolve Census tract for a lat/lon via the Census geocoder."""
    try:
        url = "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"
        params = {
            "x": lon,
            "y": lat,
            "benchmark": "Public_AR_Current",
            "vintage": "Current_Current",
            "layers": "Census Tracts",
            "format": "json",
        }
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        tracts = data.get("result", {}).get("geographies", {}).get("Census Tracts", [])
        if not tracts:
            return None
        t = tracts[0]
        return {
            "state_fips": t.get("STATE"),
            "county_fips": t.get("COUNTY"),
            "tract_fips": t.get("TRACT"),
        }
    except Exception as e:
        print(f"    Geocoder error: {e}")
        return None


def fetch_b25024(tract: dict) -> Optional[dict]:
    """Fetch B25024 for a tract. Returns parsed dict or None."""
    try:
        url = f"{CENSUS_BASE_URL}/2022/acs/acs5"
        params = {
            "get": B25024_VARS,
            "for": f"tract:{tract['tract_fips']}",
            "in": f"state:{tract['state_fips']} county:{tract['county_fips']}",
            "key": CENSUS_API_KEY,
        }
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        if len(data) < 2:
            return None
        # header row + data row; no NAME column so indices match variable order
        row = data[1]
        total    = _census_int(row[0])
        det      = _census_int(row[1])  # 1-unit detached
        att      = _census_int(row[2])  # 1-unit attached / rowhouse
        two      = _census_int(row[3])  # 2 units
        three_four = _census_int(row[4])  # 3–4 units
        if total is None or total == 0:
            return None
        low_density = sum(v for v in (det, att, two, three_four) if v is not None)
        pct = round(low_density / total, 4)
        return {
            "pct_low_density": pct,
            "total_units": total,
            "source": "acs5_2022_tract",
        }
    except Exception as e:
        print(f"    B25024 fetch error: {e}")
        return None


def backfill(input_path: str, output_path: str, dry_run: bool = False, skip_existing: bool = True) -> None:
    path = Path(input_path)
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    needs_backfill = []
    for i, row in enumerate(rows):
        existing = row.get("score", {}).get("housing_stock")
        if skip_existing and existing and existing.get("pct_low_density") is not None:
            continue
        needs_backfill.append(i)

    print(f"{path.name}: {len(rows)} total, {len(needs_backfill)} need housing stock backfill")

    updated = 0
    failed = 0
    for idx, i in enumerate(needs_backfill):
        row = rows[i]
        name = row.get("catalog", {}).get("name", "?")
        lat = float(row["catalog"]["lat"])
        lon = float(row["catalog"]["lon"])
        print(f"  [{idx+1}/{len(needs_backfill)}] {name} ({lat:.4f}, {lon:.4f})")

        tract = get_census_tract(lat, lon)
        if not tract:
            print(f"    ✗ no tract")
            failed += 1
            time.sleep(0.5)
            continue

        time.sleep(0.3)  # stay well under Census rate limits

        result = fetch_b25024(tract)
        if not result:
            print(f"    ✗ B25024 fetch failed")
            failed += 1
            time.sleep(0.5)
            continue

        pct = result["pct_low_density"]
        total = result["total_units"]
        print(f"    ✓ pct_low_density={pct:.1%}  total_units={total:,}")

        if "score" not in row:
            row["score"] = {}
        row["score"]["housing_stock"] = result
        updated += 1
        time.sleep(0.2)

    print(f"\nDone: {updated} updated, {failed} failed, {len(rows) - len(needs_backfill)} already had data")

    if dry_run:
        print("(dry-run — not writing)")
        return

    out_path = Path(output_path)
    with open(out_path, "w") as f:
        for row in rows:
            f.write(json.dumps(row, separators=(",", ":")) + "\n")
    print(f"Wrote {out_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-skip-existing", action="store_true",
                        help="Re-fetch even rows that already have housing_stock data")
    args = parser.parse_args()

    output = args.output or args.input
    backfill(args.input, output, dry_run=args.dry_run, skip_existing=not args.no_skip_existing)


if __name__ == "__main__":
    main()
