#!/usr/bin/env python3
"""
Raw ACS 2022 5-year pull, one call per state and geography, for the housing pooling test and the diversity re-pull.
Writes raw JSON only. No scoring, no catalog write. Cached files are never re-fetched.

  cd /Users/adamwright/Dev/home-fit && PYTHONPATH=. python3 scripts/catalog/pull_census_state_tables.py --states 10     # test, Delaware
  cd /Users/adamwright/Dev/home-fit && PYTHONPATH=. python3 scripts/catalog/pull_census_state_tables.py               # all states

Needs CENSUS_API_KEY in the environment (set -a && . ./.env && set +a).
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
STATES = [f"{i:02d}" for i in list(range(1, 57)) if i not in (3, 7, 14, 43, 52)] + ["72"]
NEW_ENGLAND = {"09", "23", "25", "33", "44", "50"}
CHUNK = 40  # Census allows 50 variables per call

HOUSING = [f"B19013_001{s}" for s in "EM"] + [f"B25077_001{s}" for s in "EM"] + [f"B25064_001{s}" for s in "EM"] \
    + [f"B25018_001{s}" for s in "EM"] + ["B25003_001E"]
HOUSING2 = ["B25003_002E", "B25003_003E"]  # owner and renter occupied (renter share for the housing blend)
HISPANIC = ["B03002_001E", "B03002_002E", "B03002_003E", "B03002_004E", "B03002_005E", "B03002_006E", "B03002_007E", "B03002_008E", "B03002_009E", "B03002_012E"]
DIVERSITY = (
    [f"B02001_{i:03d}E" for i in range(1, 11)]
    + [f"B19001_{i:03d}E" for i in range(1, 18)]
    + [f"B01001_{i:03d}E" for i in list(range(3, 26)) + list(range(27, 50))]
    + ["B15003_001E", "B15003_022E", "B15003_023E", "B15003_024E", "B15003_025E"]
)


def chunks(v):
    return [v[i:i + CHUNK] for i in range(0, len(v), CHUNK)]


def fetch(params, tries=4):
    for k in range(tries):
        try:
            r = requests.get(BASE, params=params, timeout=60)
            if r.status_code == 200:
                return r.json()
            err = f"HTTP {r.status_code}: {r.text[:120]}"
        except Exception as e:  # noqa: BLE001
            err = repr(e)
        time.sleep(2 * (k + 1))
    return {"error": err}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--states", nargs="*", default=STATES)
    ap.add_argument("--out", default="data/census_pull_2026-10-28")
    a = ap.parse_args()
    key = os.environ.get("CENSUS_API_KEY")
    if not key:
        sys.exit("CENSUS_API_KEY not set")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    jobs = []
    for st in a.states:
        for i, c in enumerate(chunks(HOUSING)):
            jobs.append((f"housing_tract_{st}_{i}", c, "tract:*", f"state:{st}"))
        for geo_name, gf, gi in (("tract", "tract:*", f"state:{st}"), ("place", "place:*", f"state:{st}")) + ((("cousub", "county subdivision:*", f"state:{st} county:*"),) if st in NEW_ENGLAND else ()):
            jobs.append((f"hisp_{geo_name}_{st}_0", HISPANIC, gf, gi))
        jobs.append((f"housing2_tract_{st}_0", HOUSING2, "tract:*", f"state:{st}"))
        for i, c in enumerate(chunks(DIVERSITY)):
            jobs.append((f"div_tract_{st}_{i}", c, "tract:*", f"state:{st}"))
            jobs.append((f"div_place_{st}_{i}", c, "place:*", f"state:{st}"))
            if st in NEW_ENGLAND:
                jobs.append((f"div_cousub_{st}_{i}", c, "county subdivision:*", f"state:{st} county:*"))
    done = failed = 0
    for name, vars_, geo_for, geo_in in jobs:
        f = out / f"{name}.json"
        if f.exists():
            continue
        data = fetch({"get": ",".join(vars_), "for": geo_for, "in": geo_in, "key": key})
        if isinstance(data, dict) and "error" in data:
            failed += 1
            print(f"FAILED {name}: {data['error']}")
            continue
        f.write_text(json.dumps(data))
        done += 1
        time.sleep(1)
    print(f"done {done}, failed {failed}, cached files in {out}: {len(list(out.glob('*.json')))}")


if __name__ == "__main__":
    main()
