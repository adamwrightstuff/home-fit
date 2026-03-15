#!/usr/bin/env python3
"""
Build data/status_signal_baselines.json from data/results.csv (collector output).

Reads scored API responses from results.csv, extracts the same metrics used by
Status Signal (wealth, education, occupation), aggregates by Census Division,
and writes min/max per metric so Status Signal normalization matches observed
ranges from your scored locations.

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
ROOT = os.path.dirname(SCRIPT_DIR)


def get_division(state_abbrev: Optional[str]) -> str:
    """Census division for state; 'unknown' if missing."""
    if not state_abbrev:
        return "unknown"
    from data_sources.us_census_divisions import get_division as _gd
    return _gd(state_abbrev)


def extract_metrics_from_response(raw: Dict[str, Any]) -> Optional[Dict[str, float]]:
    """Extract Status Signal input metrics from one API response. Returns None if too little data."""
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

    # Education: social_fabric
    social = pillars.get("social_fabric") or {}
    edu = social.get("education_attainment") or {}
    bach = edu.get("bachelor_pct")
    grad = edu.get("grad_pct")
    if bach is not None and isinstance(bach, (int, float)):
        out["bach_pct"] = float(bach)
    if grad is not None and isinstance(grad, (int, float)):
        out["grad_pct"] = float(grad)
    self_emp = social.get("self_employed_pct")
    if self_emp is not None and isinstance(self_emp, (int, float)):
        out["self_employed_pct"] = float(self_emp)

    # Occupation: economic_security industry_shares_pct (finance_arts; white_collar not in response)
    econ = pillars.get("economic_security") or {}
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

    if not out:
        return None
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Build status_signal_baselines.json from results.csv")
    ap.add_argument("--input", default=os.path.join(ROOT, "data", "results.csv"), help="Path to results.csv")
    ap.add_argument("--output", default=os.path.join(ROOT, "data", "status_signal_baselines.json"))
    ap.add_argument("--min-samples", type=int, default=3, help="Min samples per division to emit")
    ap.add_argument("--last", type=int, default=None, help="Use only the last N rows from results (e.g. 50 for latest run)")
    args = ap.parse_args()

    if not os.path.isfile(args.input):
        print(f"Error: {args.input} not found.")
        return

    division_values: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
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
            division = get_division(state)
            metrics = extract_metrics_from_response(raw)
            if not metrics:
                continue
            used += 1
            for k, v in metrics.items():
                if isinstance(v, (int, float)):
                    division_values[division][k].append(float(v))
                    all_vals[k].append(float(v))

    print(f"Read {seen} rows from {args.input}, extracted metrics from {used} responses.")

    metric_keys = [
        "mean_hh_income", "wealth_gap_ratio",
        "grad_pct", "bach_pct", "self_employed_pct",
        "finance_arts_pct", "white_collar_pct",
    ]
    result: Dict[str, Dict[str, Dict[str, Dict[str, float]]]] = {}

    for div, by_metric in division_values.items():
        if div == "unknown":
            continue
        if sum(len(v) for v in by_metric.values()) < args.min_samples:
            continue
        wealth = {}
        for m in ["mean_hh_income", "wealth_gap_ratio"]:
            v = by_metric.get(m)
            if v and len(v) >= args.min_samples:
                mn, mx = min(v), max(v)
                if m == "wealth_gap_ratio" and mn == 0 and mx == 0:
                    continue  # no variation; let merge keep existing baseline
                wealth[m] = {"min": mn, "max": mx}
        education = {}
        for m in ["grad_pct", "bach_pct", "self_employed_pct"]:
            v = by_metric.get(m)
            if v and len(v) >= args.min_samples:
                education[m] = {"min": min(v), "max": max(v)}
        occupation = {}
        for m in ["finance_arts_pct", "white_collar_pct"]:
            v = by_metric.get(m)
            if v and len(v) >= args.min_samples:
                occupation[m] = {"min": min(v), "max": max(v)}
        if wealth or education or occupation:
            result[div] = {"wealth": wealth, "education": education, "occupation": occupation}

    # Pool "all" from all divisions (including values that were in unknown-state rows)
    if all_vals and sum(len(v) for v in all_vals.values()) >= args.min_samples:
        wealth_all = {}
        for m in ["mean_hh_income", "wealth_gap_ratio"]:
            v = all_vals.get(m)
            if v and len(v) >= args.min_samples:
                mn, mx = min(v), max(v)
                if m == "wealth_gap_ratio" and mn == 0 and mx == 0:
                    continue
                wealth_all[m] = {"min": mn, "max": mx}
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

    # Merge with existing baselines so we don't drop education/occupation when results lack them
    if os.path.isfile(args.output):
        try:
            with open(args.output, "r", encoding="utf-8") as f:
                existing = json.load(f)
            for div, comps in existing.items():
                if div not in result:
                    result[div] = {"wealth": {}, "education": {}, "occupation": {}}
                for comp in ["wealth", "education", "occupation"]:
                    existing_comp = (comps or {}).get(comp) or {}
                    result_comp = result[div].get(comp) or {}
                    for m, minmax in existing_comp.items():
                        if m not in result_comp and isinstance(minmax, dict) and "min" in minmax and "max" in minmax:
                            result_comp[m] = minmax
                    result[div][comp] = result_comp
        except Exception as e:
            print(f"Note: could not merge with existing file: {e}")

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, sort_keys=True)
    print(f"Wrote status signal baselines to {args.output} ({len(result)} divisions + all).")


if __name__ == "__main__":
    main()
