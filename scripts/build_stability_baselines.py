#!/usr/bin/env python3
"""
Build data/stability_baselines.json for Social Fabric Stability (regional z-score).

Samples locations, fetches B07003 rooted % (same house + same county) per tract,
aggregates by Census Division, and writes mean/std so the pillar can score
stability as z-score vs region.

Typical usage (from project root):

  PYTHONPATH=. python3 scripts/build_stability_baselines.py \\
    --input data/locations.csv \\
    --output data/stability_baselines.json \\
    --limit 500 \\
    --min-samples 10

When baselines are present, 50% same-house in a high-churn region (e.g. Manhattan)
scores higher than 50% in a low-churn region (e.g. rural suburb).
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import time
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from data_sources.geocoding import geocode
from data_sources.census_api import get_census_tract, get_mobility_data
from data_sources.us_census_divisions import get_division


def _mean_std(values: List[float]) -> Tuple[float, float]:
    n = len(values)
    if n <= 0:
        return float("nan"), float("nan")
    mean = sum(values) / n
    var = sum((x - mean) ** 2 for x in values) / n
    return mean, math.sqrt(var)


def _load_locations(path: str, limit: Optional[int]) -> List[str]:
    out: List[str] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            loc = row[0].strip()
            if not loc or loc.lower() in ("location", "location,city,state,division,area_bucket"):
                continue
            out.append(loc)
            if limit and len(out) >= limit:
                break
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="data/locations.csv", help="CSV with location column")
    ap.add_argument("--output", default="data/stability_baselines.json")
    ap.add_argument("--limit", type=int, default=0, help="Max locations (0 = no limit)")
    ap.add_argument("--sleep", type=float, default=0.1)
    ap.add_argument("--min-samples", type=int, default=10, help="Min tracts per division to emit")
    args = ap.parse_args()

    limit = args.limit if args.limit and args.limit > 0 else None
    locations = _load_locations(args.input, limit)
    print(f"Loaded {len(locations)} locations from {args.input}")

    division_values: Dict[str, List[float]] = defaultdict(list)

    for i, loc in enumerate(locations):
        try:
            g = geocode(loc)
            if not g:
                continue
            lat, lon, _zip, state, _city = g
            tract = get_census_tract(lat, lon)
            if not tract:
                continue
            mobility = get_mobility_data(lat, lon, tract=tract)
            if not mobility:
                continue
            pct = mobility.get("rooted_pct")
            if pct is None or not isinstance(pct, (int, float)):
                continue
            division = get_division(state)
            division_values[division].append(float(pct))
        except Exception:
            pass
        if args.sleep:
            time.sleep(args.sleep)
        if (i + 1) % 50 == 0:
            print(f"Processed {i + 1}/{len(locations)} ...")

    # Add "all" for fallback when division is missing
    all_vals: List[float] = []
    for vals in division_values.values():
        all_vals.extend(vals)

    out: Dict[str, Dict[str, float]] = {}
    for div, vals in division_values.items():
        if len(vals) < args.min_samples:
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
