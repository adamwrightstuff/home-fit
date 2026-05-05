#!/usr/bin/env python3
"""
Rebuild la_metro and nyc_metro baselines in data/status_signal_baselines.json
from actual Census ACS 5-year tract data for CBSA 31080 (LA) and 35620 (NYC).

Fetches all tracts across all counties in each CBSA, computes p5/p95 for:
  - mean_hh_income (wealth)
  - median_home_value (home_cost)
  - white_collar_pct (occupation)
  - bach_pct, grad_pct (education)

Then patches cbsa_to_baseline to route these CBSAs to the rebuilt entries.

Usage (from project root):
  PYTHONPATH=. python3 scripts/baselines/build_metro_baselines_from_cbsa.py
"""

from __future__ import annotations

import json
import math
import os
import time
from typing import Dict, List, Optional, Tuple

import requests

CENSUS_BASE_URL = "https://api.census.gov/data"
ACS5_YEAR = "2022"
SLEEP_S = 0.15

# state FIPS → [county FIPS] for each CBSA
CBSA_COUNTIES: Dict[str, Dict[str, List[str]]] = {
    "31080": {  # Los Angeles-Long Beach-Anaheim, CA
        "06": ["037", "059"],  # Los Angeles + Orange
    },
    "35620": {  # New York-Newark-Jersey City, NY-NJ-PA
        "36": ["005", "047", "059", "061", "071", "079", "081", "085", "087", "103", "119"],
        "34": ["003", "013", "017", "019", "023", "025", "027", "029", "031", "035", "037", "039", "041"],
        "42": ["103"],  # Pike County PA
    },
}

CBSA_TO_KEY = {
    "31080": "la_metro",
    "35620": "nyc_metro",
}

# S2401 white-collar component variables (management through health practitioners)
S2401_VARS = [
    "S2401_C01_001E",  # total employed
    "S2401_C01_004E",  # management
    "S2401_C01_005E",  # business & financial ops
    "S2401_C01_007E",  # computer & math
    "S2401_C01_008E",  # arch & engineering
    "S2401_C01_012E",  # legal
    "S2401_C01_013E",  # education & library
    "S2401_C01_017E",  # health practitioners
]

BAD = frozenset(("-666666666", "-999999999", "", None))


def _pct(v: str) -> Optional[float]:
    if v in BAD:
        return None
    try:
        f = float(v)
        return f if f >= 0 else None
    except (ValueError, TypeError):
        return None


def linear_percentile(values: List[float], p: float) -> float:
    s = sorted(values)
    n = len(s)
    if n == 1:
        return float(s[0])
    k = (n - 1) * (p / 100.0)
    lo = int(math.floor(k))
    hi = min(int(math.ceil(k)), n - 1)
    w = k - lo
    return float(s[lo] * (1 - w) + s[hi] * w)


def fetch_county_tracts_wealth(state: str, county: str) -> List[Tuple[Optional[float], Optional[float]]]:
    """Returns list of (mean_hh_income, median_home_value) per tract."""
    r = requests.get(
        f"{CENSUS_BASE_URL}/{ACS5_YEAR}/acs/acs5",
        params={
            "get": "B19025_001E,B19001_001E,B25077_001E",
            "for": "tract:*",
            "in": f"state:{state} county:{county}",
        },
        timeout=30,
    )
    if r.status_code != 200:
        print(f"  WARN wealth {state}/{county}: HTTP {r.status_code}")
        return []
    rows = r.json()
    out: List[Tuple[Optional[float], Optional[float]]] = []
    for row in rows[1:]:
        agg_s, hh_s, hv_s = row[0], row[1], row[2]
        mean_inc: Optional[float] = None
        if agg_s not in BAD and hh_s not in BAD:
            try:
                agg = float(agg_s)
                hh = float(hh_s)
                if hh > 0 and agg >= 0:
                    mean_inc = agg / hh
            except (ValueError, TypeError):
                pass
        home_val: Optional[float] = None
        if hv_s not in BAD:
            try:
                v = float(hv_s)
                if v > 0:
                    home_val = v
            except (ValueError, TypeError):
                pass
        out.append((mean_inc, home_val))
    return out


def fetch_county_tracts_occupation(state: str, county: str) -> List[Optional[float]]:
    """Returns list of white_collar_pct per tract (or None)."""
    r = requests.get(
        f"{CENSUS_BASE_URL}/{ACS5_YEAR}/acs/acs5/subject",
        params={
            "get": ",".join(S2401_VARS),
            "for": "tract:*",
            "in": f"state:{state} county:{county}",
        },
        timeout=30,
    )
    if r.status_code != 200:
        print(f"  WARN occupation {state}/{county}: HTTP {r.status_code}")
        return []
    rows = r.json()
    out: List[Optional[float]] = []
    for row in rows[1:]:
        total_s = row[0]
        if total_s in BAD:
            out.append(None)
            continue
        try:
            t = float(total_s)
            if t <= 0:
                out.append(None)
                continue
            white = sum(
                float(row[i]) if i < len(row) and row[i] not in BAD else 0.0
                for i in range(1, len(S2401_VARS))
            )
            out.append(100.0 * white / t)
        except (ValueError, TypeError):
            out.append(None)
    return out


def fetch_county_tracts_education(state: str, county: str) -> List[Tuple[Optional[float], Optional[float]]]:
    """Returns list of (bach_pct, grad_pct) per tract (S1501 C02 = percent columns)."""
    r = requests.get(
        f"{CENSUS_BASE_URL}/{ACS5_YEAR}/acs/acs5/subject",
        params={
            "get": "S1501_C02_015E,S1501_C02_013E",
            "for": "tract:*",
            "in": f"state:{state} county:{county}",
        },
        timeout=30,
    )
    if r.status_code != 200:
        print(f"  WARN education {state}/{county}: HTTP {r.status_code}")
        return []
    rows = r.json()
    out: List[Tuple[Optional[float], Optional[float]]] = []
    for row in rows[1:]:
        bach = _pct(row[0])
        grad = _pct(row[1])
        out.append((bach, grad))
    return out


def build_cbsa_baselines(cbsa_code: str) -> Dict:
    counties_by_state = CBSA_COUNTIES[cbsa_code]
    mean_incomes: List[float] = []
    home_values: List[float] = []
    white_collar: List[float] = []
    bach_pcts: List[float] = []
    grad_pcts: List[float] = []

    total_counties = sum(len(v) for v in counties_by_state.values())
    done = 0
    for state, counties in counties_by_state.items():
        for county in counties:
            done += 1
            print(f"  [{done}/{total_counties}] state={state} county={county} ...", end="", flush=True)

            wealth_rows = fetch_county_tracts_wealth(state, county)
            time.sleep(SLEEP_S)
            occ_rows = fetch_county_tracts_occupation(state, county)
            time.sleep(SLEEP_S)
            edu_rows = fetch_county_tracts_education(state, county)
            time.sleep(SLEEP_S)

            for mi, hv in wealth_rows:
                if mi is not None:
                    mean_incomes.append(mi)
                if hv is not None:
                    home_values.append(hv)
            for wc in occ_rows:
                if wc is not None:
                    white_collar.append(wc)
            for bp, gp in edu_rows:
                if bp is not None:
                    bach_pcts.append(bp)
                if gp is not None:
                    grad_pcts.append(gp)

            print(f" inc={len(mean_incomes)} hv={len(home_values)} wc={len(white_collar)} edu={len(bach_pcts)}")

    def p5p95(vals: List[float], label: str) -> Dict[str, float]:
        lo = linear_percentile(vals, 5.0)
        hi = linear_percentile(vals, 95.0)
        print(f"    {label}: n={len(vals)}, p5={lo:.2f}, p95={hi:.2f}")
        return {"min": round(lo, 4), "max": round(hi, 4)}

    print(f"\n  Computing p5/p95 for CBSA {cbsa_code}:")
    result: Dict = {}
    # Intentionally omit wealth (mean_hh_income) from metro baselines:
    # income is meaningful nationally so "all" baseline ($28k-$175k) gives appropriate credit
    # for LA/NYC households. Home values ARE metro-relative, so home_cost uses metro bounds.
    if len(home_values) >= 10:
        result["home_cost"] = {"median_home_value": p5p95(home_values, "median_home_value")}
    if len(white_collar) >= 10:
        result["occupation"] = {"white_collar_pct": p5p95(white_collar, "white_collar_pct")}
    edu: Dict = {}
    if len(bach_pcts) >= 10:
        edu["bach_pct"] = p5p95(bach_pcts, "bach_pct")
    if len(grad_pcts) >= 10:
        edu["grad_pct"] = p5p95(grad_pcts, "grad_pct")
    if edu:
        result["education"] = edu

    return result


def main() -> None:
    baselines_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "data", "status_signal_baselines.json",
    )
    with open(baselines_path, "r", encoding="utf-8") as f:
        baselines = json.load(f)

    for cbsa_code, key in CBSA_TO_KEY.items():
        print(f"\n=== CBSA {cbsa_code} → {key} ===")
        metro_data = build_cbsa_baselines(cbsa_code)
        if not metro_data:
            print(f"  ERROR: no data collected for CBSA {cbsa_code}")
            continue
        baselines[key] = metro_data
        print(f"  Updated {key} in baselines")

    baselines["cbsa_to_baseline"] = {cbsa: key for cbsa, key in CBSA_TO_KEY.items()}
    print(f"\ncbsa_to_baseline set to {baselines['cbsa_to_baseline']}")

    with open(baselines_path, "w", encoding="utf-8") as f:
        json.dump(baselines, f, indent=2, sort_keys=True)
    print(f"\nWrote {baselines_path}")


if __name__ == "__main__":
    main()
