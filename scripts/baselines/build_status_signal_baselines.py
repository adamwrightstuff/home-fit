#!/usr/bin/env python3
"""
Build data/status_signal_baselines.json for Status Signal (per-division min/max).

Samples locations from data/locations.csv, fetches Census data per tract,
aggregates by Census Division, and writes min/max for each metric so the
Status Signal scorer can normalize to 0-100.

Metrics (per division):
- wealth: mean_hh_income, wealth_gap_ratio
- education: grad_pct, bach_pct, self_employed_pct
- occupation: finance_arts_pct, white_collar_pct

Usage (from project root):

  PYTHONPATH=. python3 scripts/build_status_signal_baselines.py \\
    --input data/locations.csv \\
    --output data/status_signal_baselines.json \\
    --limit 500 \\
    --min-samples 5 \\
    --sleep 0.15
"""

from __future__ import annotations

import argparse
import json
import os
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from data_sources.census_api import CENSUS_API_KEY, CENSUS_BASE_URL, _make_request_with_retry, get_census_tract
from data_sources.geocoding import geocode
from data_sources.us_census_divisions import get_division


# Fallback cities if no CSV or file missing (no setup required)
_DEFAULT_LOCATIONS = [
    "Seattle, WA", "Portland, OR", "San Francisco, CA", "Denver, CO",
    "Austin, TX", "Chicago, IL", "Boston, MA", "New York, NY",
    "Minneapolis, MN", "Atlanta, GA", "Miami, FL", "Phoenix, AZ",
]


def _load_locations(path: str, limit: Optional[int]) -> List[str]:
    out: List[str] = []
    if path and os.path.isfile(path):
        with open(path, newline="", encoding="utf-8") as f:
            for row in f:
                row = row.strip()
                if not row or row.lower().startswith("location"):
                    continue
                loc = row.split(",")[0].strip().strip('"')
                if not loc:
                    continue
                out.append(loc)
                if limit and len(out) >= limit:
                    break
    if not out:
        out = _DEFAULT_LOCATIONS[: (limit or len(_DEFAULT_LOCATIONS))]
    return out


def _fetch_tract_values(
    tract: Dict[str, Any],
) -> Optional[Dict[str, float]]:
    """Fetch one tract's raw values for Status Signal metrics. Returns None on failure."""
    if not CENSUS_API_KEY:
        return None
    state_fips = tract.get("state_fips")
    county_fips = tract.get("county_fips")
    tract_fips = tract.get("tract_fips")
    if not all([state_fips, county_fips, tract_fips]):
        return None

    geo = f"tract:{tract_fips}"
    geo_in = f"state:{state_fips} county:{county_fips}"
    base_acs5 = f"{CENSUS_BASE_URL}/2022/acs/acs5"
    base_profile = f"{CENSUS_BASE_URL}/2022/acs/acs5/profile"
    base_subject = f"{CENSUS_BASE_URL}/2022/acs/acs5/subject"

    out: Dict[str, Optional[float]] = {}

    # ---- Median HH income (B19013), aggregate (B19025), total HH (B19001) -> mean, wealth_gap ----
    try:
        params = {
            "get": "B19013_001E,B19025_001E,B19001_001E",
            "for": geo,
            "in": geo_in,
            "key": CENSUS_API_KEY,
        }
        r = _make_request_with_retry(base_acs5, params, timeout=15, max_retries=2)
        if r and r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and len(data) >= 2:
                row = data[1]
                median_raw = row[0]
                agg_raw = row[1]
                total_hh_raw = row[2]
                median = float(median_raw) if median_raw not in (None, "", "-666666666", "-999999999") else None
                agg = float(agg_raw) if agg_raw not in (None, "", "-666666666", "-999999999") else None
                total_hh = float(total_hh_raw) if total_hh_raw not in (None, "", "-666666666", "-999999999") else None
                if median is not None:
                    out["median_hh_income"] = median
                if agg is not None and total_hh is not None and total_hh > 0:
                    out["mean_hh_income"] = agg / total_hh
                if out.get("mean_hh_income") is not None and median is not None and median > 0:
                    out["wealth_gap_ratio"] = (out["mean_hh_income"] - median) / median
    except Exception:
        pass

    # ---- S1501: bach_pct (006), grad_pct (007) ----
    try:
        params = {
            "get": "S1501_C01_006E,S1501_C01_007E",
            "for": geo,
            "in": geo_in,
            "key": CENSUS_API_KEY,
        }
        r = _make_request_with_retry(base_subject, params, timeout=15, max_retries=2)
        if r and r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and len(data) >= 2:
                row = data[1]
                for i, var in enumerate(["bach_pct", "grad_pct"]):
                    v = row[i] if i < len(row) else None
                    if v not in (None, "", "-666666666", "-999999999"):
                        try:
                            out[var] = float(v)
                        except (ValueError, TypeError):
                            pass
    except Exception:
        pass

    # ---- B24080: total employed (001), self-employed incorp (003), self-employed not incorp (004) ----
    try:
        params = {
            "get": "B24080_001E,B24080_003E,B24080_004E",
            "for": geo,
            "in": geo_in,
            "key": CENSUS_API_KEY,
        }
        r = _make_request_with_retry(base_acs5, params, timeout=15, max_retries=2)
        if r and r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and len(data) >= 2:
                row = data[1]
                total_emp = row[0]
                se_incorp = row[1] if len(row) > 1 else None
                se_not_incorp = row[2] if len(row) > 2 else None
                try:
                    t = float(total_emp) if total_emp not in (None, "", "-666666666", "-999999999") else 0
                    s1 = float(se_incorp) if se_incorp not in (None, "", "-666666666", "-999999999") else 0
                    s2 = float(se_not_incorp) if se_not_incorp not in (None, "", "-666666666", "-999999999") else 0
                    if t > 0:
                        out["self_employed_pct"] = 100.0 * (s1 + s2) / t
                except (ValueError, TypeError):
                    pass
    except Exception:
        pass

    # ---- DP03: finance_realestate (0040), leisure_hospitality (0043) -> finance_arts_pct ----
    try:
        params = {
            "get": "DP03_0040PE,DP03_0043PE",
            "for": geo,
            "in": geo_in,
            "key": CENSUS_API_KEY,
        }
        r = _make_request_with_retry(base_profile, params, timeout=15, max_retries=2)
        if r and r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and len(data) >= 2:
                row = data[1]
                v0 = row[0] if len(row) > 0 else None
                v1 = row[1] if len(row) > 1 else None
                try:
                    f = float(v0) if v0 not in (None, "", "-666666666", "-999999999") else 0
                    a = float(v1) if v1 not in (None, "", "-666666666", "-999999999") else 0
                    out["finance_arts_pct"] = f + a
                except (ValueError, TypeError):
                    pass
    except Exception:
        pass

    # ---- S2401: white collar = management + business_financial_ops + legal + computer_math + arch_engineering + education_library + health_practitioners ----
    try:
        vars_list = [
            "S2401_C01_001E", "S2401_C01_004E", "S2401_C01_005E", "S2401_C01_007E", "S2401_C01_008E",
            "S2401_C01_012E", "S2401_C01_013E", "S2401_C01_017E",
        ]
        params = {
            "get": ",".join(vars_list),
            "for": geo,
            "in": geo_in,
            "key": CENSUS_API_KEY,
        }
        r = _make_request_with_retry(base_subject, params, timeout=15, max_retries=2)
        if r and r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and len(data) >= 2:
                row = data[1]
                total = row[0]
                if total not in (None, "", "-666666666", "-999999999"):
                    try:
                        t = float(total)
                        if t > 0:
                            white = sum(
                                float(row[i]) if i < len(row) and row[i] not in (None, "", "-666666666", "-999999999") else 0
                                for i in range(1, len(vars_list))
                            )
                            out["white_collar_pct"] = 100.0 * white / t
                    except (ValueError, TypeError):
                        pass
    except Exception:
        pass

    if not out:
        return None
    return {k: v for k, v in out.items() if v is not None}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="data/locations.csv", help="CSV with location column")
    ap.add_argument("--output", default="data/status_signal_baselines.json")
    ap.add_argument("--limit", type=int, default=0, help="Max locations (0 = no limit)")
    ap.add_argument("--sleep", type=float, default=0.15)
    ap.add_argument("--min-samples", type=int, default=5, help="Min tracts per division to emit")
    args = ap.parse_args()

    if not CENSUS_API_KEY:
        print("WARNING: CENSUS_API_KEY not set; requests will fail.")
    limit = args.limit if args.limit and args.limit > 0 else None
    locations = _load_locations(args.input, limit)
    print(f"Loaded {len(locations)} locations from {args.input}")

    # Collect values by division
    division_values: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
    seen_tracts: set = set()

    for i, loc in enumerate(locations):
        try:
            g = geocode(loc)
            if not g:
                continue
            lat, lon, _zip, state, _city = g
            tract = get_census_tract(lat, lon)
            if not tract:
                continue
            tract_key = (tract.get("state_fips"), tract.get("county_fips"), tract.get("tract_fips"))
            if tract_key in seen_tracts:
                if args.sleep:
                    time.sleep(args.sleep * 0.3)
                continue
            seen_tracts.add(tract_key)
            division = get_division(state)
            vals = _fetch_tract_values(tract)
            if not vals:
                if args.sleep:
                    time.sleep(args.sleep)
                continue
            for k, v in vals.items():
                if isinstance(v, (int, float)):
                    division_values[division][k].append(float(v))
        except Exception:
            pass
        if args.sleep:
            time.sleep(args.sleep)
        if (i + 1) % 50 == 0:
            print(f"Processed {i + 1}/{len(locations)} ...")

    # Build per-division min/max
    metric_keys = [
        "mean_hh_income", "wealth_gap_ratio",
        "grad_pct", "bach_pct", "self_employed_pct",
        "finance_arts_pct", "white_collar_pct",
    ]
    result: Dict[str, Dict[str, Dict[str, Dict[str, float]]]] = {}

    for div, by_metric in division_values.items():
        if sum(len(v) for v in by_metric.values()) < args.min_samples:
            continue
        wealth: Dict[str, Dict[str, float]] = {}
        education: Dict[str, Dict[str, float]] = {}
        occupation: Dict[str, Dict[str, float]] = {}

        for m in ["mean_hh_income", "wealth_gap_ratio"]:
            v = by_metric.get(m)
            if v and len(v) >= args.min_samples:
                wealth[m] = {"min": min(v), "max": max(v)}
        for m in ["grad_pct", "bach_pct", "self_employed_pct"]:
            v = by_metric.get(m)
            if v and len(v) >= args.min_samples:
                education[m] = {"min": min(v), "max": max(v)}
        for m in ["finance_arts_pct", "white_collar_pct"]:
            v = by_metric.get(m)
            if v and len(v) >= args.min_samples:
                occupation[m] = {"min": min(v), "max": max(v)}

        if wealth or education or occupation:
            result[div] = {
                "wealth": wealth,
                "education": education,
                "occupation": occupation,
            }

    # Fallback "all" from pooled values
    all_vals: Dict[str, List[float]] = defaultdict(list)
    for by_metric in division_values.values():
        for k, v in by_metric.items():
            all_vals[k].extend(v)
    if all_vals and sum(len(v) for v in all_vals.values()) >= args.min_samples:
        wealth_all = {}
        for m in ["mean_hh_income", "wealth_gap_ratio"]:
            v = all_vals.get(m)
            if v and len(v) >= args.min_samples:
                wealth_all[m] = {"min": min(v), "max": max(v)}
        education_all = {}
        for m in ["grad_pct", "bach_pct", "self_employed_pct"]:
            v = all_vals.get(m)
            if v and len(v) >= args.min_samples:
                education_all[m] = {"min": min(v), "max": max(v)}
        occupation_all = {}
        for m in ["finance_arts_pct", "white_collar_pct"]:
            v = all_vals.get(m)
            if v and len(v) >= args.min_samples:
                occupation_all[m] = {"min": min(v), "max": max(v)}
        if wealth_all or education_all or occupation_all:
            result["all"] = {"wealth": wealth_all, "education": education_all, "occupation": occupation_all}

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, sort_keys=True)
    print(f"Wrote status signal baselines to {args.output} ({len(result)} divisions + all)")


if __name__ == "__main__":
    main()
