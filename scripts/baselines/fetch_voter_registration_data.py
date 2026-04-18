#!/usr/bin/env python3
"""
Fetch tract-level voter registration data with no manual CSV.

Downloads:
- Census CVAP 2019-2023 tract-level (citizen voting-age population)
- EAVS 2022 county-level (total registered voters)

Assigns each tract its county's registration rate (registered / CVAP), then writes
the same JSONs that build_voter_registration_baselines.py produces, so the app
uses county-level registration instead of state-level fallback.

Run from project root:
  PYTHONPATH=. python3 scripts/fetch_voter_registration_data.py
"""

from __future__ import annotations

import csv
import io
import json
import math
import os
import sys
import zipfile
from collections import defaultdict
from typing import Dict, List, Tuple

import requests

# Reuse division logic from build script
from data_sources.us_census_divisions import get_division

_CVAP_ZIP_URL = "https://www2.census.gov/programs-surveys/decennial/rdo/datasets/2023/2023-cvap/CVAP_2019-2023_ACS_csv_files.zip"
_EAVS_ZIP_URL = "https://www.eac.gov/sites/default/files/2023-06/2022_EAVS_for_Public_Release_nolabel_V1_CSV.zip"

_STATE_FIPS_TO_ABBREV = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO", "09": "CT",
    "10": "DE", "11": "DC", "12": "FL", "13": "GA", "15": "HI", "16": "ID", "17": "IL",
    "18": "IN", "19": "IA", "20": "KS", "21": "KY", "22": "LA", "23": "ME", "24": "MD",
    "25": "MA", "26": "MI", "27": "MN", "28": "MS", "29": "MO", "30": "MT", "31": "NE",
    "32": "NV", "33": "NH", "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND",
    "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI", "45": "SC", "46": "SD",
    "47": "TN", "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA", "54": "WV",
    "55": "WI", "56": "WY", "72": "PR",
}


def _mean_std(values: List[float]) -> Tuple[float, float]:
    n = len(values)
    if n <= 0:
        return float("nan"), float("nan")
    mean = sum(values) / n
    var = sum((x - mean) ** 2 for x in values) / n
    return mean, math.sqrt(var)


def _division_from_geoid(geoid: str) -> str:
    if not geoid or len(geoid) < 2:
        return "unknown"
    state_abbrev = _STATE_FIPS_TO_ABBREV.get(geoid[:2])
    return get_division(state_abbrev)


def _fetch_cvap_by_tract() -> Tuple[Dict[str, int], Dict[str, int]]:
    """Return (tract_cvap, county_cvap). Tract GEOID is 11-char (state+county+tract)."""
    print("Downloading Census CVAP ZIP...")
    r = requests.get(_CVAP_ZIP_URL, timeout=120, stream=True)
    r.raise_for_status()
    zip_data = r.content
    print(f"  Got {len(zip_data) / 1e6:.1f} MB")

    tract_cvap: Dict[str, int] = {}
    county_cvap: Dict[str, int] = defaultdict(int)

    with zipfile.ZipFile(io.BytesIO(zip_data), "r") as zf:
        with zf.open("Tract.csv") as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="latin-1", errors="replace"))
            for row in reader:
                if row.get("lnnumber") != "1":
                    continue
                geoid_raw = (row.get("geoid") or "").strip()
                if not geoid_raw or "US" not in geoid_raw:
                    continue
                # e.g. 1400000US01001020100 -> 01001020100 (11 chars)
                geoid = geoid_raw.split("US")[-1].strip()
                if len(geoid) != 11:
                    continue
                try:
                    cvap = int(float(row.get("cvap_est", 0)))
                except (TypeError, ValueError):
                    continue
                if cvap < 0:
                    continue
                tract_cvap[geoid] = cvap
                county_cvap[geoid[:5]] += cvap

    print(f"  Tracts: {len(tract_cvap)}, Counties: {len(county_cvap)}")
    return tract_cvap, dict(county_cvap)


def _fetch_eavs_county_registered() -> Dict[str, int]:
    """Return county_fips (5-char) -> total registered (A1a + A1b)."""
    print("Downloading EAVS 2022 ZIP...")
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) HomeFit/1.0"}
    r = requests.get(_EAVS_ZIP_URL, timeout=60, headers=headers)
    r.raise_for_status()
    zip_data = r.content
    print(f"  Got {len(zip_data) / 1e6:.1f} MB")

    county_registered: Dict[str, int] = {}
    with zipfile.ZipFile(io.BytesIO(zip_data), "r") as zf:
        name = [n for n in zf.namelist() if n.endswith(".csv")][0]
        with zf.open(name) as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="latin-1", errors="replace"))
            for row in reader:
                fips = (row.get("FIPSCode") or "").strip()
                if len(fips) < 5:
                    continue
                county_fips = fips[:5]
                try:
                    a1a = int(float(row.get("A1a", 0) or 0))
                    a1b = int(float(row.get("A1b", 0) or 0))
                except (TypeError, ValueError):
                    continue
                if a1a < 0 or a1b < 0:
                    continue
                total = a1a + a1b
                if total > 0:
                    county_registered[county_fips] = total
    print(f"  Counties with registration: {len(county_registered)}")
    return county_registered


def main() -> None:
    data_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data"
    )
    os.makedirs(data_dir, exist_ok=True)
    rates_path = os.path.join(data_dir, "voter_registration_tract_rates.json")
    stats_path = os.path.join(data_dir, "voter_registration_engagement_stats.json")

    tract_cvap, county_cvap = _fetch_cvap_by_tract()
    county_registered = _fetch_eavs_county_registered()

    # County rate = registered / CVAP. Assign to each tract in that county.
    rate_by_tract: Dict[str, float] = {}
    for geoid, cvap in tract_cvap.items():
        county_fips = geoid[:5]
        reg = county_registered.get(county_fips, 0)
        cvap_county = county_cvap.get(county_fips, 0)
        if cvap_county <= 0:
            continue
        rate = reg / cvap_county
        rate = max(0.0, min(1.0, rate))
        rate_by_tract[geoid] = round(rate, 4)

    print(f"Tract rates assigned: {len(rate_by_tract)}")

    # Division stats for z-score normalization
    division_values: Dict[str, List[float]] = defaultdict(list)
    for geoid, rate in rate_by_tract.items():
        division_values[_division_from_geoid(geoid)].append(rate)

    engagement_stats: Dict[str, Dict[str, float]] = {}
    for division, vals in division_values.items():
        if not vals:
            continue
        mean, std = _mean_std(vals)
        if std > 0:
            engagement_stats[division] = {"mean": mean, "std": std, "n": len(vals)}

    all_vals = [r for r in rate_by_tract.values()]
    if all_vals:
        mean_all, std_all = _mean_std(all_vals)
        if std_all > 0:
            engagement_stats["all"] = {"mean": mean_all, "std": std_all, "n": len(all_vals)}

    with open(rates_path, "w", encoding="utf-8") as f:
        json.dump(rate_by_tract, f, indent=2, sort_keys=True)
    print(f"Wrote {rates_path} ({len(rate_by_tract)} tracts)")

    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(engagement_stats, f, indent=2, sort_keys=True)
    print(f"Wrote {stats_path} ({len(engagement_stats)} divisions)")
    print("Done. App will use county-level voter registration.")


if __name__ == "__main__":
    main()
    sys.exit(0)
