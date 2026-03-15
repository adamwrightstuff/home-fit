#!/usr/bin/env python3
"""
Build data/economic_baselines.json from data/results.csv (collector output).

Reads scored API responses from results.csv, extracts economic_security summary
metrics and (division, area_bucket) from each row, aggregates by division and
area_bucket, and writes mean/std per metric so the economic_security pillar
normalization uses observed ranges.

Metrics extracted from summary: unemployment_rate, emp_pop_ratio,
net_estab_entry_per_1k, estabs_per_1k, wage_p25_annual, wage_p75_annual,
qcew_employment_per_1k, qcew_employment_growth_pct, industry_hhi, anchored_balance.

Usage (from project root):
  PYTHONPATH=. python3 scripts/build_economic_baselines_from_results.py
  PYTHONPATH=. python3 scripts/build_economic_baselines_from_results.py --input data/results.csv --output data/economic_baselines.json --min-samples 3
  PYTHONPATH=. python3 scripts/build_economic_baselines_from_results.py --last 100
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)

# Summary key -> baseline metric name (for normalization.py)
SUMMARY_TO_METRIC = {
    "unemployment_rate_pct": "unemployment_rate",
    "employment_to_population_pct": "emp_pop_ratio",
    "net_estab_entry_per_1k": "net_estab_entry_per_1k",
    "estabs_per_1k": "estabs_per_1k",
    "wage_p25_annual": "wage_p25_annual",
    "wage_p75_annual": "wage_p75_annual",
    "qcew_employment_per_1k": "qcew_employment_per_1k",
    "qcew_employment_growth_pct": "qcew_employment_growth_pct",
    "industry_diversity_hhi": "industry_hhi",
    "anchored_balance": "anchored_balance",
}


def _mean_std(values: List[float]) -> Tuple[float, float]:
    n = len(values)
    if n <= 0:
        return float("nan"), float("nan")
    mean = sum(values) / n
    var = sum((x - mean) ** 2 for x in values) / n
    return mean, math.sqrt(var)


def extract_economic_metrics(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return (division, area_bucket, metrics_dict) or None."""
    pillars = raw.get("livability_pillars") or {}
    econ = pillars.get("economic_security") or {}
    summary = econ.get("summary") or {}
    division = summary.get("division")
    area_bucket = summary.get("area_bucket") or "all"
    if not division:
        return None
    metrics: Dict[str, float] = {}
    for summary_key, metric_name in SUMMARY_TO_METRIC.items():
        v = summary.get(summary_key)
        if v is not None and isinstance(v, (int, float)):
            metrics[metric_name] = float(v)
    if not metrics:
        return None
    return {"division": str(division), "area_bucket": str(area_bucket), "metrics": metrics}


def main() -> None:
    ap = argparse.ArgumentParser(description="Build economic_baselines.json from results.csv")
    ap.add_argument("--input", default=os.path.join(ROOT, "data", "results.csv"))
    ap.add_argument("--output", default=os.path.join(ROOT, "data", "economic_baselines.json"))
    ap.add_argument("--min-samples", type=int, default=3)
    ap.add_argument("--last", type=int, default=None, help="Use only the last N rows")
    args = ap.parse_args()

    if not os.path.isfile(args.input):
        print(f"Error: {args.input} not found.")
        return

    # (division, area_bucket) -> metric -> list of values
    by_key: Dict[Tuple[str, str], Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
    seen = 0
    used = 0

    with open(args.input, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if not header or len(header) < 3 or header[0].strip().lower() != "location":
            print("Error: expected CSV with columns location,timestamp,raw_json")
            return
        rows = list(reader)

    if args.last is not None and args.last > 0:
        rows = rows[-args.last:]
        print(f"Using only last {args.last} rows.")

    for row in rows:
        if len(row) < 3:
            continue
        seen += 1
        try:
            raw = json.loads(row[2])
        except json.JSONDecodeError:
            continue
        out = extract_economic_metrics(raw)
        if not out:
            continue
        used += 1
        key = (out["division"], out["area_bucket"])
        for m, v in out["metrics"].items():
            by_key[key][m].append(v)

    print(f"Read {seen} rows from {args.input}, extracted economic metrics from {used} responses.")

    # Build result: division -> area_bucket -> metric -> {mean, std, n}
    result: Dict[str, Dict[str, Dict[str, Dict[str, float]]]] = {}
    for (division, area_bucket), metric_lists in by_key.items():
        if division == "unknown":
            continue
        if division not in result:
            result[division] = {}
        if area_bucket not in result[division]:
            result[division][area_bucket] = {}
        for metric, values in metric_lists.items():
            if len(values) < args.min_samples:
                continue
            mean, std = _mean_std(values)
            result[division][area_bucket][metric] = {"mean": mean, "std": std, "n": len(values)}

    # Preserve us_median_household_income from existing file if present
    if os.path.isfile(args.output):
        try:
            with open(args.output, "r", encoding="utf-8") as f:
                existing = json.load(f)
            if isinstance(existing.get("us_median_household_income"), (int, float)):
                result["us_median_household_income"] = existing["us_median_household_income"]
        except Exception:
            pass

    out_final = {}
    for k, v in result.items():
        if k == "us_median_household_income":
            out_final[k] = v
        elif isinstance(v, dict):
            out_final[k] = v
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out_final, f, indent=2, sort_keys=True)
    n_divisions = sum(1 for k, v in out_final.items() if k != "us_median_household_income" and isinstance(v, dict))
    print(f"Wrote economic baselines to {args.output} ({n_divisions} divisions)")


if __name__ == "__main__":
    main()
