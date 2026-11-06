#!/usr/bin/env python3
"""
Raw ACS 2022 5-year household type pull for the "Who lives here" panel (docs/PRODUCT_MODEL_PLAN.md step 5). One call per state
and geography (tract, place, and county subdivision in the New England catalog states). Raw JSON only: no scoring, no catalog
write. Cached files are never re-fetched. Writes to its own folder, outside the repo.

Tables: B11001 household type (family, married couple, other family, nonfamily, living alone), B11005 households by presence
of people under 18, B11007 households by presence of people 65 and over.
Checked 2026-11-05: 68,195 rows, B11001 family plus nonfamily and B11005 with plus without people under 18 equal the total in every row.

  set -a && . /Users/adamwright/Dev/home-fit/.env && set +a
  cd /Users/adamwright/Dev/home-fit-status-signal && python3 scripts/catalog/pull_census_household_type.py --states 10   # trial, Delaware
  cd /Users/adamwright/Dev/home-fit-status-signal && python3 scripts/catalog/pull_census_household_type.py               # the 18 catalog states
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests

BASE = "https://api.census.gov/data/2022/acs/acs5"
# States that hold catalog places: AZ CA CO CT DE FL GA IL IN MA MD NC NJ NV NY PA TX WA
CATALOG_STATES = ["04", "06", "08", "09", "10", "12", "13", "17", "18", "24", "25", "32", "34", "36", "37", "42", "48", "53"]
NEW_ENGLAND = {"09", "25"}  # catalog states where towns are county subdivisions
VARS = (
    [f"B11001_{i:03d}E" for i in range(1, 10)]          # 001 total, 002 family, 003 married couple, 004 other family, 005 male no spouse, 006 female no spouse, 007 nonfamily, 008 living alone, 009 not alone
    + ["B11005_001E", "B11005_002E", "B11005_011E"]     # total households, with people under 18, with none under 18
    + ["B11007_001E", "B11007_002E"]                    # total households, with people 65 and over (B11007_003E is a sub-row, not "none"; none = 001 minus 002)
)
DEFAULT_OUT = "/Users/adamwright/Dev/home-fit-archive-2026-11-05/data/census_pull_household_type_2026-11-05"


def fetch(params, tries=4):
    err = ""
    for k in range(tries):
        try:
            r = requests.get(BASE, params=params, timeout=60)
            if r.status_code == 200:
                return r.json()
            err = f"HTTP {r.status_code}: {r.text[:120]}"
        except Exception as e:  # noqa: BLE001
            err = type(e).__name__
        time.sleep(2 * (k + 1))
    return {"error": err}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--states", nargs="*", default=CATALOG_STATES)
    ap.add_argument("--out", default=DEFAULT_OUT)
    a = ap.parse_args()
    key = os.environ.get("CENSUS_API_KEY")
    if not key:
        sys.exit("CENSUS_API_KEY not set")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    jobs = []
    for st in a.states:
        jobs.append((f"hh_tract_{st}", "tract:*", f"state:{st}"))
        jobs.append((f"hh_place_{st}", "place:*", f"state:{st}"))
        if st in NEW_ENGLAND:
            jobs.append((f"hh_cousub_{st}", "county subdivision:*", f"state:{st} county:*"))
    print(f"{len(jobs)} calls planned, output {out}")
    done = failed = 0
    for name, geo_for, geo_in in jobs:
        f = out / f"{name}.json"
        if f.exists():
            continue
        data = fetch({"get": ",".join(VARS) + ",NAME", "for": geo_for, "in": geo_in, "key": key})
        if isinstance(data, dict) and "error" in data:
            failed += 1
            print(f"FAILED {name}: {data['error']}")
            continue
        f.write_text(json.dumps(data))
        done += 1
        print(f"ok {name}: {len(data) - 1} rows")
        time.sleep(1)
    print(f"done {done}, failed {failed}, files in {out}: {len(list(out.glob('*.json')))}")


if __name__ == "__main__":
    main()
