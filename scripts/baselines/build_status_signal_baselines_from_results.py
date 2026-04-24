#!/usr/bin/env python3
"""
Build data/status_signal_baselines.json from data/results.csv (collector output).

Reads scored API responses from results.csv, extracts the same metrics used by
Status Signal (wealth, education, occupation), aggregates by Census Division,
and writes min/max per metric so Status Signal normalization matches observed
ranges from your scored locations. Percent-style metrics (*_pct) are only written
when min/max are within [0, 100]; otherwise the metric is skipped (logged). The
output is passed through a sanitizer that coerces bad legacy min/max and fills
nyc_metro / la_metro education when still missing.

Usage (from project root):

  PYTHONPATH=. python3 scripts/build_status_signal_baselines_from_results.py
  PYTHONPATH=. python3 scripts/build_status_signal_baselines_from_results.py --input data/results.csv --output data/status_signal_baselines.json --min-samples 3
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from collections import defaultdict
from typing import Any, Dict, List, Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))

import importlib.util

_spec_pct = importlib.util.spec_from_file_location(
    "status_signal_baseline_pct",
    os.path.join(ROOT, "scripts", "baselines", "status_signal_baseline_pct.py"),
)
_ssbp = importlib.util.module_from_spec(_spec_pct)
assert _spec_pct and _spec_pct.loader
_spec_pct.loader.exec_module(_ssbp)


def get_cbsa_key(city: str, state: str) -> str:
    """Approximate CBSA key from city/state; extend as needed for richer grouping.

    This groups obvious metro clusters (e.g. NYC core + rich suburbs) so that
    wealth/home_cost baselines reflect the true upper end of that metro rather
    than an entire Census division.
    """
    key = f"{city}, {state}".strip()

    # NYC metro: core (boroughs/neighborhoods) and nearby suburbs.
    # Include both abbreviated (NY, CT, NJ) and full state names so API
    # location_info matches (e.g. "City of New York", "New York").
    nyc_cluster = {
        "New York, NY",
        "Brooklyn, NY",
        "Queens, NY",
        "Bronx, NY",
        "Scarsdale, NY",
        "The Hamptons, NY",
        "Greenwich, CT",
        "Westport, CT",
        "Princeton, NJ",
        "Ithaca, NY",
        "New York, New York",
        "City of New York, New York",
        "Brooklyn, New York",
        "Queens, New York",
        "Bronx, New York",
        "Scarsdale, New York",
        "Village of Scarsdale, New York",
        "The Hamptons, New York",
        "Greenwich, Connecticut",
        "Westport, Connecticut",
        "Princeton, New Jersey",
        "Ithaca, New York",
    }
    if key in nyc_cluster:
        return "nyc_metro"

    philly_cluster = {
        "Philadelphia, PA",
        # Extend with Main Line suburbs if desired.
    }
    if key in philly_cluster:
        return "philly_metro"

    dc_cluster = {
        "Washington, DC",
        "Bethesda, MD",
        "Arlington, VA",
        "Fairfax, VA",
    }
    if key in dc_cluster:
        return "dc_metro"

    # Los Angeles — Long Beach — Anaheim CBSA 31080 (core + common city names from location_info)
    la_cluster = {
        "Los Angeles, CA",
        "Long Beach, CA",
        "Pasadena, CA",
        "Glendale, CA",
        "Santa Monica, CA",
        "Beverly Hills, CA",
        "Torrance, CA",
        "Compton, CA",
        "Irvine, CA",
        "Anaheim, CA",
        "Santa Ana, CA",
        "Huntington Beach, CA",
        "Los Angeles, California",
        "Long Beach, California",
    }
    if key in la_cluster:
        return "la_metro"

    # Fallback: treat each city, state as its own cbsa-style bucket
    return key.lower().replace(" ", "_")


def get_division(state_abbrev: Optional[str]) -> str:
    """Census division for state; 'unknown' if missing."""
    if not state_abbrev:
        return "unknown"
    from data_sources.us_census_divisions import get_division as _gd
    return _gd(state_abbrev)


def paired_wealth_minmax(
    mean_list: Optional[List[float]],
    gap_list: Optional[List[float]],
    min_samples: int,
) -> Dict[str, Dict[str, float]]:
    """
    Status Signal resolves min/max per metric from the same baseline key; income and gap
    must share one distributional context. Emit both or neither (no split sourcing).
    """
    out: Dict[str, Dict[str, float]] = {}
    if not mean_list or len(mean_list) < min_samples:
        return out
    if not gap_list or len(gap_list) < min_samples:
        return out
    mn_g, mx_g = min(gap_list), max(gap_list)
    if mn_g == 0.0 and mx_g == 0.0:
        return out
    out["mean_hh_income"] = {"min": min(mean_list), "max": max(mean_list)}
    out["wealth_gap_ratio"] = {"min": mn_g, "max": mx_g}
    return out


def enforce_paired_wealth(wealth: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """If only one of mean_hh_income / wealth_gap_ratio is present, drop both orphans."""
    if not wealth:
        return {}
    w = dict(wealth)
    has_i = "mean_hh_income" in w and isinstance(w.get("mean_hh_income"), dict)
    has_g = "wealth_gap_ratio" in w and isinstance(w.get("wealth_gap_ratio"), dict)
    if has_i and not has_g:
        w.pop("mean_hh_income", None)
    if has_g and not has_i:
        w.pop("wealth_gap_ratio", None)
    return w


def _emit_pct_minmax(
    metric: str,
    values: Optional[List[float]],
    min_samples: int,
    log_label: str,
) -> Optional[Dict[str, float]]:
    if not values or len(values) < min_samples:
        return None
    mn, mx = min(values), max(values)
    if not _ssbp.validate_pct_for_build(metric, float(mn), float(mx)):
        print(
            f"  [skip] {log_label} {metric}: invalid pct min={mn} max={mx} (leave unwritten; check results scale)"
        )
        return None
    return {"min": float(mn), "max": float(mx)}


def extract_metrics_from_response(
    raw: Dict[str, Any],
    recompute_education: bool = False,
    recompute_occupation: bool = False,
) -> Optional[Dict[str, float]]:
    """Extract Status Signal input metrics from one API response. Returns None if too little data.
    If recompute_education is True, fetch fresh education (0-100%%) from Census B15003 for this location.
    If recompute_occupation is True and white_collar_pct is missing, fetch S2401 for this location."""
    out: Dict[str, float] = {}

    # Wealth: housing_value summary
    pillars = raw.get("livability_pillars") or {}
    housing = pillars.get("housing_value") or {}
    summary = housing.get("summary") or housing
    mean_income = summary.get("mean_household_income")
    median_income = summary.get("median_household_income")
    if median_income is not None and isinstance(median_income, (int, float)) and median_income > 0:
        if mean_income is None or not isinstance(mean_income, (int, float)):
            mean_income = median_income
        out["mean_hh_income"] = float(mean_income)
        out["wealth_gap_ratio"] = (float(mean_income) - float(median_income)) / float(median_income)

    median_home = summary.get("median_home_value")
    if median_home is not None and isinstance(median_home, (int, float)) and median_home > 0:
        out["median_home_value"] = float(median_home)

    # Education: from response or recompute from Census (0-100% scale)
    social = pillars.get("social_fabric") or {}
    edu = social.get("education_attainment") or {}
    if recompute_education:
        coords = raw.get("coordinates") or {}
        lat, lon = coords.get("lat"), coords.get("lon")
        if lat is not None and lon is not None:
            try:
                from data_sources.census_api import get_census_tract, get_diversity_data
                tract = get_census_tract(float(lat), float(lon))
                div_data = get_diversity_data(float(lat), float(lon), tract) if tract else None
                if div_data and div_data.get("education_attainment"):
                    edu = div_data["education_attainment"]
            except Exception:
                pass
    bach = edu.get("bachelor_pct")
    grad = edu.get("grad_pct")
    if bach is not None and isinstance(bach, (int, float)):
        out["bach_pct"] = float(bach)
    if grad is not None and isinstance(grad, (int, float)):
        out["grad_pct"] = float(grad)
    self_emp = social.get("self_employed_pct")
    if self_emp is not None and isinstance(self_emp, (int, float)):
        out["self_employed_pct"] = float(self_emp)

    # Occupation: economic_security industry_shares_pct + white_collar_pct from breakdown or S2401
    econ = pillars.get("economic_security") or {}
    breakdown = econ.get("breakdown") or {}
    industry = econ.get("industry_shares_pct") or {}
    fr = industry.get("finance_realestate")
    lh = industry.get("leisure_hospitality")
    if fr is not None or lh is not None:
        fa = 0.0
        if fr is not None:
            fa += float(fr)
        if lh is not None:
            fa += float(lh)
        out["finance_arts_pct"] = fa

    white_collar_pct = breakdown.get("white_collar_pct")
    if white_collar_pct is None and recompute_occupation:
        coords = raw.get("coordinates") or {}
        lat, lon = coords.get("lat"), coords.get("lon")
        if lat is not None and lon is not None:
            try:
                from data_sources.census_api import get_census_tract
                from pillars.status_signal import _fetch_white_collar_pct_tract
                tract = get_census_tract(float(lat), float(lon))
                if tract:
                    white_collar_pct = _fetch_white_collar_pct_tract(tract)
            except Exception:
                pass
    if white_collar_pct is not None and isinstance(white_collar_pct, (int, float)):
        out["white_collar_pct"] = float(white_collar_pct)

    # Brand: raw luxury-presence score 0-100 from business_list (for baseline normalization)
    na = pillars.get("neighborhood_amenities") or {}
    business_list = (na.get("breakdown") or {}).get("business_list") or na.get("business_list") or []
    if business_list:
        from pillars.status_signal import brand_raw_score
        out["brand_raw_score"] = float(brand_raw_score(business_list))

    if not out:
        return None
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Build status_signal_baselines.json from results.csv")
    ap.add_argument("--input", default=os.path.join(ROOT, "data", "results.csv"), help="Path to results.csv")
    ap.add_argument("--output", default=os.path.join(ROOT, "data", "status_signal_baselines.json"))
    ap.add_argument("--min-samples", type=int, default=3, help="Min samples per division to emit")
    ap.add_argument("--last", type=int, default=None, help="Use only the last N rows from results (e.g. 50 for latest run)")
    ap.add_argument("--recompute-education", action="store_true", help="Fetch education (0-100%%) from Census B15003 per row so baselines match current API scale")
    ap.add_argument("--recompute-occupation", action="store_true", help="Fetch white_collar_pct from S2401 per row when missing in response")
    args = ap.parse_args()

    if not os.path.isfile(args.input):
        print(f"Error: {args.input} not found.")
        return

    division_values: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
    cbsa_values: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
    all_vals: Dict[str, List[float]] = defaultdict(list)
    seen = 0
    used = 0

    with open(args.input, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if not header or (len(header) < 3 or header[0].strip().lower() != "location"):
            print("Error: expected CSV with columns location,timestamp,raw_json")
            return
        rows = list(reader)
    if args.last is not None and args.last > 0:
        rows = rows[-args.last:]
        print(f"Using only last {args.last} rows.")
    for row in rows:
            if len(row) < 3:
                continue
            location, _ts, json_str = row[0], row[1], row[2]
            seen += 1
            try:
                raw = json.loads(json_str)
            except json.JSONDecodeError:
                continue
            state = (raw.get("location_info") or {}).get("state")
            loc_info = raw.get("location_info") or {}
            city = str(loc_info.get("city") or "").strip()
            state_str = str(state or "").strip()
            division = get_division(state)
            cbsa = get_cbsa_key(city, state_str)
            metrics = extract_metrics_from_response(
                raw,
                recompute_education=args.recompute_education,
                recompute_occupation=args.recompute_occupation,
            )
            if not metrics:
                continue
            used += 1
            for k, v in metrics.items():
                if isinstance(v, (int, float)):
                    val_f = float(v)
                    division_values[division][k].append(val_f)
                    all_vals[k].append(val_f)
                    if k in {
                        "mean_hh_income",
                        "wealth_gap_ratio",
                        "median_home_value",
                        "grad_pct",
                        "bach_pct",
                        "self_employed_pct",
                    }:
                        cbsa_values[cbsa][k].append(val_f)

    print(f"Read {seen} rows from {args.input}, extracted metrics from {used} responses.")

    result: Dict[str, Dict[str, Dict[str, Dict[str, float]]]] = {}

    for div, by_metric in division_values.items():
        if div == "unknown":
            continue
        if sum(len(v) for v in by_metric.values()) < args.min_samples:
            continue
        wealth = paired_wealth_minmax(
            by_metric.get("mean_hh_income"),
            by_metric.get("wealth_gap_ratio"),
            args.min_samples,
        )
        education = {}
        for m in ["grad_pct", "bach_pct", "self_employed_pct"]:
            mm = _emit_pct_minmax(m, by_metric.get(m), args.min_samples, f"division={div!r}")
            if mm is not None:
                education[m] = mm
        occupation = {}
        for m in ["finance_arts_pct", "white_collar_pct", "self_employed_pct"]:
            mm = _emit_pct_minmax(m, by_metric.get(m), args.min_samples, f"division={div!r}")
            if mm is not None:
                occupation[m] = mm
        brand = {}
        v = by_metric.get("brand_raw_score")
        if v and len(v) >= args.min_samples:
            brand["brand_raw_score"] = {"min": min(v), "max": max(v)}
        home_cost = {}
        v = by_metric.get("median_home_value")
        if v and len(v) >= args.min_samples:
            home_cost["median_home_value"] = {"min": min(v), "max": max(v)}
        if wealth or education or occupation or brand or home_cost:
            result[div] = {"wealth": wealth, "education": education, "occupation": occupation, "brand": brand, "home_cost": home_cost}

    # Build CBSA-level baselines: wealth, home_cost, and education (same keys as nyc_metro / la_metro)
    for cbsa_key, by_metric in cbsa_values.items():
        if sum(len(v) for v in by_metric.values()) < args.min_samples:
            continue
        wealth = paired_wealth_minmax(
            by_metric.get("mean_hh_income"),
            by_metric.get("wealth_gap_ratio"),
            args.min_samples,
        )
        home_cost = {}
        v_home = by_metric.get("median_home_value")
        if v_home and len(v_home) >= args.min_samples:
            home_cost["median_home_value"] = {"min": min(v_home), "max": max(v_home)}
        education_cbsa = {}
        for m in ["grad_pct", "bach_pct", "self_employed_pct"]:
            mm = _emit_pct_minmax(
                m, by_metric.get(m), args.min_samples, f"cbsa={cbsa_key!r}"
            )
            if mm is not None:
                education_cbsa[m] = mm
        if wealth or home_cost or education_cbsa:
            existing = result.get(cbsa_key) or {}
            merged_edu = {**(existing.get("education") or {}), **education_cbsa}
            result[cbsa_key] = {
                "wealth": wealth,
                "education": merged_edu,
                "occupation": existing.get("occupation", {}),
                "brand": existing.get("brand", {}),
                "home_cost": home_cost,
            }

    # Pool "all" from all divisions (including values that were in unknown-state rows)
    if all_vals and sum(len(v) for v in all_vals.values()) >= args.min_samples:
        wealth_all = paired_wealth_minmax(
            all_vals.get("mean_hh_income"),
            all_vals.get("wealth_gap_ratio"),
            args.min_samples,
        )
        education_all = {}
        for m in ["grad_pct", "bach_pct", "self_employed_pct"]:
            mm = _emit_pct_minmax(m, all_vals.get(m), args.min_samples, "all pool")
            if mm is not None:
                education_all[m] = mm
        occupation_all = {}
        for m in ["finance_arts_pct", "white_collar_pct", "self_employed_pct"]:
            mm = _emit_pct_minmax(m, all_vals.get(m), args.min_samples, "all pool")
            if mm is not None:
                occupation_all[m] = mm
        brand_all = {}
        v = all_vals.get("brand_raw_score")
        if v and len(v) >= args.min_samples:
            brand_all["brand_raw_score"] = {"min": min(v), "max": max(v)}
        home_cost_all = {}
        v = all_vals.get("median_home_value")
        if v and len(v) >= args.min_samples:
            home_cost_all["median_home_value"] = {"min": min(v), "max": max(v)}
        if wealth_all or education_all or occupation_all or brand_all or home_cost_all:
            result["all"] = {"wealth": wealth_all, "education": education_all, "occupation": occupation_all, "brand": brand_all, "home_cost": home_cost_all}

    # Merge with existing baselines so we don't drop education/occupation when results lack them
    # When --recompute-education was used, do not merge in old education (it was count-scale).
    if os.path.isfile(args.output):
        try:
            with open(args.output, "r", encoding="utf-8") as f:
                existing = json.load(f)
            for div, comps in existing.items():
                if div not in result:
                    result[div] = {"wealth": {}, "education": {}, "occupation": {}, "brand": {}, "home_cost": {}}
                for comp in ["wealth", "education", "occupation", "brand", "home_cost"]:
                    if comp == "education" and args.recompute_education:
                        continue  # keep only newly computed education (0-100 scale)
                    if comp == "occupation" and args.recompute_occupation:
                        continue  # keep only newly computed occupation (white_collar_pct from S2401)
                    if comp not in result[div]:
                        result[div][comp] = {}
                    existing_comp = (comps or {}).get(comp) or {}
                    result_comp = result[div].get(comp) or {}
                    for m, minmax in existing_comp.items():
                        if m not in result_comp and isinstance(minmax, dict) and "min" in minmax and "max" in minmax:
                            result_comp[m] = minmax
                    result[div][comp] = result_comp
        except Exception as e:
            print(f"Note: could not merge with existing file: {e}")

    # Merge can reintroduce orphan mean_hh_income or wealth_gap_ratio from older JSON.
    for _key, comps in result.items():
        if isinstance(comps, dict) and "wealth" in comps:
            comps["wealth"] = enforce_paired_wealth(comps.get("wealth"))

    result = _ssbp.sanitize_full_baselines_file(result, apply_metro_overrides=True)

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, sort_keys=True)
    print(f"Wrote status signal baselines to {args.output} ({len(result)} divisions + all).")


if __name__ == "__main__":
    main()
