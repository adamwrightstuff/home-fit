#!/usr/bin/env python3
"""
Build data/pm25_tract_annual.json: annual mean PM2.5 (ug/m3) by census tract.

Source: CDC National Environmental Public Health Tracking Network, "Daily Census Tract-Level PM2.5
Concentrations" (data.cdc.gov dataset vpk8-vfhm): daily predictions from EPA's Downscaler model (monitors fused
with CMAQ), 2021 to 2022 so far and being extended to 2025. The annual mean per tract and year is taken
server-side (SoQL avg by ctfips), then averaged over the available years. Wildfire smoke is part of PM2.5 and
is kept. Per-state, per-year results are cached in --cache-dir so an interrupted run resumes.

  PYTHONPATH=. python3 scripts/baselines/build_pm25_tract_table.py --cache-dir /tmp/pm25_cache           # all states
  PYTHONPATH=. python3 scripts/baselines/build_pm25_tract_table.py --states 36 --years 2022 --dry-run   # try one
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.parse
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
URL = "https://data.cdc.gov/resource/vpk8-vfhm.json"
STATE_FIPS = ["01", "02", "04", "05", "06", "08", "09", "10", "11", "12", "13", "15", "16", "17", "18", "19", "20", "21",
              "22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32", "33", "34", "35", "36", "37", "38", "39",
              "40", "41", "42", "44", "45", "46", "47", "48", "49", "50", "51", "53", "54", "55", "56"]


def _get(params: dict, tries: int = 4):
    url = URL + "?" + urllib.parse.urlencode(params)
    for k in range(tries):
        r = subprocess.run(["curl", "-s", "-m", "280", url], capture_output=True, text=True)
        try:
            data = json.loads(r.stdout)
            if isinstance(data, list):
                return data
        except Exception:
            pass
        time.sleep(5 * (k + 1))
    return None


def state_year(state: str, year: int):
    """{ctfips: (mean, mean_stderr, days)} for one state-year, or None on failure."""
    rows = _get({"$select": "ctfips,avg(ds_pm_pred) as pm,avg(ds_pm_stdd) as se,count(*) as n",
                 "$where": f"statefips='{state}' AND year='{year}'", "$group": "ctfips", "$limit": "50000"})
    if rows is None:
        return None
    return {r["ctfips"]: (float(r["pm"]), float(r["se"]), int(r["n"])) for r in rows if r.get("pm") is not None}


def centroids(year: int):
    """{ctfips: (lat, lon)} from one day of the dataset. The dataset's latitude and longitude columns are
    swapped (latitude holds the longitude), so they are swapped back here."""
    rows = _get({"$select": "ctfips,latitude,longitude", "$where": f"date='01JAN{year}' AND year='{year}'", "$limit": "100000"})
    out = {}
    for r in rows or []:
        try:
            lat, lon = float(r["longitude"]), float(r["latitude"])
        except (KeyError, TypeError, ValueError):
            continue
        if 15 < lat < 72 and -180 < lon < -60:  # sanity check that the swap is right
            out[r["ctfips"]] = (round(lat, 4), round(lon, 4))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache-dir", default="/tmp/pm25_cache")
    ap.add_argument("--states", nargs="*", default=STATE_FIPS)
    ap.add_argument("--years", nargs="*", type=int)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--output", default=str(ROOT / "data" / "pm25_tract_annual.json"))
    a = ap.parse_args()
    if a.years:
        years = a.years
    else:
        yrs = _get({"$select": "year", "$group": "year"}) or []
        years = sorted(int(r["year"]) for r in yrs if r.get("year"))
    print("years:", years, flush=True)
    cache = Path(a.cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    per = {}
    for y in years:
        for s in a.states:
            f = cache / f"{s}_{y}.json"
            if f.exists():
                data = {k: tuple(v) for k, v in json.loads(f.read_text()).items()}
            else:
                t0 = time.time()
                data = state_year(s, y)
                if data is None:
                    print(f"FAILED state {s} year {y}", file=sys.stderr, flush=True)
                    continue
                f.write_text(json.dumps(data))
                print(f"state {s} {y}: {len(data)} tracts ({time.time() - t0:.0f}s)", flush=True)
            for k, (pm, se, n) in data.items():
                if n >= 300:  # require nearly a full year of days
                    per.setdefault(k, {})[y] = pm
    table = {k: round(sum(v.values()) / len(v), 3) for k, v in per.items()}
    cen = centroids(max(years)) if not a.dry_run else {}
    cen = {k: v for k, v in cen.items() if k in table}
    print("tract centroids:", len(cen))
    out = {"_meta": {"source": "CDC Tracking Network daily tract PM2.5 (EPA Downscaler), data.cdc.gov vpk8-vfhm",
                     "years": years, "built": str(date.today()), "units": "ug/m3 annual mean",
                     "tracts": len(table)},
           "tracts": table, "centroids": {k: list(v) for k, v in cen.items()}}
    print("tracts with a value:", len(table), "years:", years)
    if a.dry_run:
        print("dry run: nothing written")
        return
    Path(a.output).write_text(json.dumps(out, separators=(",", ":")))
    print("wrote", a.output)


if __name__ == "__main__":
    main()
