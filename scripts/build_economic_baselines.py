#!/usr/bin/env python3
"""
Build `data/economic_baselines.json` for the economic_security pillar.

This script samples locations, computes raw economic-security submetrics at the
pillar's evaluation geography (CBSA preferred, county fallback), then produces
mean/std per (census_division × area_bucket × metric).

Typical see-once usage:
  python3 scripts/build_economic_baselines.py \\
    --input data/locations.csv \\
    --output data/economic_baselines.json \\
    --limit 500
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import time
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Any

from data_sources.geocoding import geocode
from data_sources.census_api import get_census_tract, get_population_density
from data_sources.data_quality import detect_area_type
from data_sources.economic_security_data import (
    get_economic_geography,
    fetch_acs_profile_dp03,
    fetch_acs_table,
    fetch_bds_establishment_dynamics,
    compute_industry_hhi,
    compute_anchored_vs_cyclical_balance,
)
from data_sources.us_census_divisions import get_division
from data_sources.job_category_overlays import (
    JOB_CATEGORIES,
    CATEGORY_GROUPS,
    S2401_TOTAL_EMPLOYED,
    S2401_COUNTS,
    B24011_MEDIANS,
    B08301_TOTAL,
    B08301_WFH,
    B24031_PUBLIC_ADMIN,
)


CURRENT_ACS_YEAR = 2022


def _area_bucket(area_type: Optional[str]) -> str:
    if not area_type:
        return "all"
    at = area_type.lower()
    if at in {"urban_core", "urban_residential", "historic_urban", "urban_core_lowrise"}:
        return "urban"
    if at in {"suburban", "exurban"}:
        return "suburban"
    if at == "rural":
        return "rural"
    return "all"


def _mean_std(values: List[float]) -> Tuple[float, float]:
    """
    Population mean/std (std uses N in denominator).
    """
    n = len(values)
    if n <= 0:
        return float("nan"), float("nan")
    mean = sum(values) / n
    var = sum((x - mean) ** 2 for x in values) / n
    return mean, math.sqrt(var)


def _load_locations_from_csv(path: str, limit: Optional[int]) -> List[str]:
    out: List[str] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            loc = row[0].strip()
            if not loc or loc.lower() == "location":
                continue
            out.append(loc)
            if limit and len(out) >= limit:
                break
    return out


def _compute_raw_metrics(lat: float, lon: float, state_abbrev: str, area_type: str) -> Optional[Dict[str, float]]:
    tract = get_census_tract(lat, lon)
    geo = get_economic_geography(lat, lon, tract=tract)
    if not geo:
        return None

    year_now = CURRENT_ACS_YEAR

    dp03_vars = [
        "DP03_0001E",
        "DP03_0004E",
        "DP03_0009PE",
        "DP03_0092E",
        "DP03_0033PE",
        "DP03_0034PE",
        "DP03_0035PE",
        "DP03_0036PE",
        "DP03_0037PE",
        "DP03_0038PE",
        "DP03_0039PE",
        "DP03_0040PE",
        "DP03_0041PE",
        "DP03_0042PE",
        "DP03_0043PE",
        "DP03_0044PE",
        "DP03_0045PE",
    ]

    dp03_now = fetch_acs_profile_dp03(year=year_now, geo=geo, variables=dp03_vars) or {}

    rent_row = fetch_acs_table(year=year_now, geo=geo, variables=["B25064_001E"]) or {}
    pop_row = fetch_acs_table(year=year_now, geo=geo, variables=["B01001_001E"]) or {}
    bds_row = fetch_bds_establishment_dynamics(year=year_now, geo=geo) or {}

    pop16 = dp03_now.get("DP03_0001E")
    employed = dp03_now.get("DP03_0004E")
    unemp_rate = dp03_now.get("DP03_0009PE")
    earnings = dp03_now.get("DP03_0092E")
    rent = rent_row.get("B25064_001E")
    total_pop = pop_row.get("B01001_001E")

    if not isinstance(unemp_rate, (int, float)):
        return None

    emp_pop_ratio = None
    if isinstance(pop16, (int, float)) and pop16 > 0 and isinstance(employed, (int, float)):
        emp_pop_ratio = 100.0 * float(employed) / float(pop16)

    earnings_to_rent = None
    if isinstance(earnings, (int, float)) and isinstance(rent, (int, float)) and rent > 0:
        earnings_to_rent = float(earnings) / (float(rent) * 12.0)

    industry_shares = {
        "ag_mining": dp03_now.get("DP03_0033PE"),
        "construction": dp03_now.get("DP03_0034PE"),
        "manufacturing": dp03_now.get("DP03_0035PE"),
        "wholesale": dp03_now.get("DP03_0036PE"),
        "retail": dp03_now.get("DP03_0037PE"),
        "transport_util": dp03_now.get("DP03_0038PE"),
        "information": dp03_now.get("DP03_0039PE"),
        "finance_realestate": dp03_now.get("DP03_0040PE"),
        "prof_services": dp03_now.get("DP03_0041PE"),
        "educ_health": dp03_now.get("DP03_0042PE"),
        "leisure_hospitality": dp03_now.get("DP03_0043PE"),
        "other_services": dp03_now.get("DP03_0044PE"),
        "public_admin": dp03_now.get("DP03_0045PE"),
    }
    industry_hhi = compute_industry_hhi(industry_shares)
    anchored_balance = compute_anchored_vs_cyclical_balance(industry_shares)

    net_estab_entry_per_1k = None
    if isinstance(total_pop, (int, float)) and total_pop > 0:
        entry = bds_row.get("ESTABS_ENTRY")
        exit_ = bds_row.get("ESTABS_EXIT")
        if isinstance(entry, (int, float)) and isinstance(exit_, (int, float)):
            net_estab_entry_per_1k = (float(entry) - float(exit_)) / float(total_pop) * 1000.0

    out: Dict[str, float] = {"unemployment_rate": float(unemp_rate)}
    if isinstance(emp_pop_ratio, (int, float)):
        out["emp_pop_ratio"] = float(emp_pop_ratio)
    if isinstance(earnings_to_rent, (int, float)):
        out["earnings_to_rent"] = float(earnings_to_rent)
    if isinstance(net_estab_entry_per_1k, (int, float)):
        out["net_estab_entry_per_1k"] = float(net_estab_entry_per_1k)
    if isinstance(industry_hhi, (int, float)):
        out["industry_hhi"] = float(industry_hhi)
    if isinstance(anchored_balance, (int, float)):
        out["anchored_balance"] = float(anchored_balance)

    # ------------------------------------------------------------------
    # Job category overlay baselines (raw metrics only)
    # ------------------------------------------------------------------
    annual_rent = float(rent) * 12.0 if isinstance(rent, (int, float)) and rent > 0 else None

    def _earnings_to_rent(v: Optional[float]) -> Optional[float]:
        if not isinstance(v, (int, float)) or v <= 0 or not isinstance(annual_rent, (int, float)) or annual_rent <= 0:
            return None
        return float(v) / float(annual_rent)

    # Occupation counts (S2401 subject table) + occupation median earnings (B24011)
    s2401_vars = [S2401_TOTAL_EMPLOYED, *sorted(set(S2401_COUNTS.values()))]
    s2401_row = fetch_acs_table(year=year_now, geo=geo, variables=s2401_vars, dataset="acs/acs5/subject") or {}
    b24011_row = fetch_acs_table(year=year_now, geo=geo, variables=sorted(set(B24011_MEDIANS.values())), dataset="acs/acs5") or {}
    wfh_row = fetch_acs_table(year=year_now, geo=geo, variables=[B08301_TOTAL, B08301_WFH], dataset="acs/acs5") or {}
    b24031_row = fetch_acs_table(year=year_now, geo=geo, variables=[B24031_PUBLIC_ADMIN], dataset="acs/acs5") or {}

    total_emp = s2401_row.get(S2401_TOTAL_EMPLOYED)

    for cat in JOB_CATEGORIES:
        density_share: Optional[float] = None
        earn_ratio: Optional[float] = None

        if cat in CATEGORY_GROUPS:
            groups = CATEGORY_GROUPS[cat]
            if isinstance(total_emp, (int, float)) and total_emp > 0:
                num = 0.0
                ok = False
                for gk in groups:
                    var = S2401_COUNTS.get(gk)
                    v = s2401_row.get(var) if var else None
                    if isinstance(v, (int, float)) and v >= 0:
                        num += float(v)
                        ok = True
                if ok:
                    density_share = num / float(total_emp)

            # Weighted mean of occupation medians, weighted by counts.
            pairs = []
            for gk in groups:
                med_var = B24011_MEDIANS.get(gk)
                cnt_var = S2401_COUNTS.get(gk)
                med = b24011_row.get(med_var) if med_var else None
                cnt = s2401_row.get(cnt_var) if cnt_var else None
                if isinstance(med, (int, float)) and med > 0 and isinstance(cnt, (int, float)) and cnt > 0:
                    pairs.append((float(med), float(cnt)))
            if pairs:
                total_w = sum(w for _, w in pairs)
                if total_w > 0:
                    cat_med = sum(v * w for v, w in pairs) / total_w
                    earn_ratio = _earnings_to_rent(cat_med)

        elif cat == "public_sector_nonprofit":
            public_pct = dp03_now.get("DP03_0045PE")
            if isinstance(public_pct, (int, float)):
                density_share = max(0.0, min(1.0, float(public_pct) / 100.0))
            pub_earn = b24031_row.get(B24031_PUBLIC_ADMIN)
            if isinstance(pub_earn, (int, float)) and pub_earn > 0:
                earn_ratio = _earnings_to_rent(float(pub_earn))

        elif cat == "remote_flexible":
            tot = wfh_row.get(B08301_TOTAL)
            wfh = wfh_row.get(B08301_WFH)
            if isinstance(tot, (int, float)) and tot > 0 and isinstance(wfh, (int, float)) and wfh >= 0:
                density_share = float(wfh) / float(tot)
            if isinstance(earnings, (int, float)) and earnings > 0:
                earn_ratio = _earnings_to_rent(float(earnings))

        if isinstance(density_share, (int, float)):
            out[f"jobcat_density_{cat}"] = float(density_share)
        if isinstance(earn_ratio, (int, float)):
            out[f"jobcat_earnings_to_rent_{cat}"] = float(earn_ratio)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="CSV with a 'location' column (first column).")
    ap.add_argument("--output", default="data/economic_baselines.json")
    ap.add_argument("--limit", type=int, default=0, help="Max rows to process (0 = no limit).")
    ap.add_argument("--sleep", type=float, default=0.1, help="Sleep seconds between locations (reduce API load).")
    args = ap.parse_args()

    limit = args.limit if args.limit and args.limit > 0 else None
    locations = _load_locations_from_csv(args.input, limit)
    print(f"Loaded {len(locations)} locations from {args.input}")

    # values[division][bucket][metric] -> list[float]
    values: Dict[str, Dict[str, Dict[str, List[float]]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    processed = 0
    for loc in locations:
        processed += 1
        try:
            g = geocode(loc)
            if not g:
                continue
            lat, lon, zip_code, state, city = g
            density = get_population_density(lat, lon)
            area_type = detect_area_type(lat, lon, density=density, city=city, location_input=loc)
            div = get_division(state)
            bucket = _area_bucket(area_type)
            raw = _compute_raw_metrics(lat, lon, state, area_type)
            if not raw:
                continue
            for metric, v in raw.items():
                values[div][bucket][metric].append(float(v))
        except Exception:
            # Keep going; this is a batch script.
            pass

        if args.sleep:
            time.sleep(args.sleep)

        if processed % 25 == 0:
            print(f"Processed {processed}/{len(locations)} ...")

    # Build mean/std
    out: Dict[str, Dict[str, Dict[str, Dict[str, float]]]] = {}
    for div, buckets in values.items():
        out.setdefault(div, {})
        for bucket, metrics in buckets.items():
            out[div].setdefault(bucket, {})
            for metric, vals in metrics.items():
                vals = [v for v in vals if isinstance(v, (int, float)) and not math.isnan(v)]
                if len(vals) < 20:
                    continue
                mean, std = _mean_std(vals)
                out[div][bucket][metric] = {"mean": mean, "std": std, "n": len(vals)}

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, sort_keys=True)
    print(f"Wrote baselines to {args.output}")


if __name__ == "__main__":
    main()

