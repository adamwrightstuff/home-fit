#!/usr/bin/env python3
"""
Build data/stability_baselines.json from data/results.csv (collector output).

Reads scored API responses from results.csv, extracts social_fabric stability
(rooted_pct or same_house_pct) and division from each row, aggregates by Census
division, and writes mean/std so the Social Fabric pillar can score stability
as z-score vs region.

Usage (from project root):
  PYTHONPATH=. python3 scripts/build_stability_baselines_from_results.py
  PYTHONPATH=. python3 scripts/build_stability_baselines_from_results.py --input data/results.csv --output data/stability_baselines.json --min-samples 3
  PYTHONPATH=. python3 scripts/build_stability_baselines_from_results.py --last 50
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
from collections import defaultdict
from typing import Dict, List

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))


def get_division(state_abbrev: str | None) -> str:
    if not state_abbrev:
        return "unknown"
    try:
        from data_sources.us_census_divisions import get_division as _gd
        return _gd(state_abbrev)
    except Exception:
        return "unknown"


def _mean_std(values: List[float]) -> tuple[float, float]:
    n = len(values)
    if n <= 0:
        return float("nan"), float("nan")
    mean = sum(values) / n
    var = sum((x - mean) ** 2 for x in values) / n
    return mean, math.sqrt(var)


def main() -> None:
    ap = argparse.ArgumentParser(description="Build stability_baselines.json from results.csv")
    ap.add_argument("--input", default=os.path.join(ROOT, "data", "results.csv"), help="Path to results.csv")
    ap.add_argument("--output", default=os.path.join(ROOT, "data", "stability_baselines.json"))
    ap.add_argument("--min-samples", type=int, default=3)
    ap.add_argument("--last", type=int, default=None, help="Use only the last N rows")
    args = ap.parse_args()

    if not os.path.isfile(args.input):
        print(f"Error: {args.input} not found.")
        return

    division_values: Dict[str, List[float]] = defaultdict(list)
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
        pillars = raw.get("livability_pillars") or {}
        social = pillars.get("social_fabric") or {}
        summary = social.get("summary") or {}
        rooted_pct = summary.get("rooted_pct")
        same_house_pct = summary.get("same_house_pct")
        stability_pct = rooted_pct if rooted_pct is not None else same_house_pct
        if stability_pct is None or not isinstance(stability_pct, (int, float)):
            continue
        state = (raw.get("location_info") or {}).get("state")
        division = get_division(state)
        if division == "unknown":
            continue
        division_values[division].append(float(stability_pct))
        used += 1

    print(f"Read {seen} rows from {args.input}, extracted stability from {used} responses.")

    all_vals: List[float] = []
    for vals in division_values.values():
        all_vals.extend(vals)

    out: Dict[str, Dict[str, float]] = {}
    for div, vals in division_values.items():
        if div == "unknown" or len(vals) < args.min_samples:
            continue
        mean, std = _mean_std(vals)
        out[div] = {"mean": mean, "std": std, "n": len(vals)}

    if all_vals and len(all_vals) >= args.min_samples:
        mean_all, std_all = _mean_std(all_vals)
        out["all"] = {"mean": mean_all, "std": std_all, "n": len(all_vals)}

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, sort_keys=True)
    print(f"Wrote stability baselines to {args.output} ({len(out)} divisions + all)")


if __name__ == "__main__":
    main()
