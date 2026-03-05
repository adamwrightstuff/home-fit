#!/usr/bin/env python3
"""
Build voter-registration engagement baselines for the Social Fabric pillar.

Reads a tract-level CSV of registration rates (or registered/cvap counts),
computes division-level mean/std for z-score normalization, and writes:

- data/voter_registration_tract_rates.json
    {geoid: registration_rate}  (rate in 0–1)

- data/voter_registration_engagement_stats.json
    {division_code: {"mean": float, "std": float, "n": int}}

If --input-csv is missing or empty, writes empty dicts. At runtime, the pillar
uses state-level registration rates from data/state_registration_rates.json instead
(no build step required—engagement works out of the box).

Input CSV format (one of):
  - geoid, registration_rate   (rate 0–1)
  - geoid, registered, cvap    (counts; rate = registered/cvap)

Typical usage (from project root):

  PYTHONPATH=. python3 scripts/build_voter_registration_baselines.py \\
    --input-csv data/voter_registration_raw.csv \\
    --output-rates data/voter_registration_tract_rates.json \\
    --output-stats data/voter_registration_engagement_stats.json
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from data_sources.us_census_divisions import get_division

# State FIPS (2-digit) → 2-letter abbreviation (for division lookup from tract GEOID)
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
    """Population mean/std (std uses N in denominator)."""
    n = len(values)
    if n <= 0:
        return float("nan"), float("nan")
    mean = sum(values) / n
    var = sum((x - mean) ** 2 for x in values) / n
    return mean, math.sqrt(var)


def _division_from_geoid(geoid: str) -> str:
    """Return Census Division code for a tract GEOID (first 2 chars = state FIPS)."""
    if not geoid or len(geoid) < 2:
        return "unknown"
    state_fips = geoid[:2]
    state_abbrev = _STATE_FIPS_TO_ABBREV.get(state_fips)
    return get_division(state_abbrev)


def build_voter_registration_baselines(
    input_csv: Optional[str],
    output_rates: str,
    output_stats: str,
) -> None:
    """
    Read tract-level registration data, compute division stats, write JSONs.
    If input_csv is None or file missing/empty, write empty dicts.
    """
    rate_by_tract: Dict[str, float] = {}
    if input_csv and os.path.isfile(input_csv):
        with open(input_csv, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            if not rows:
                print("Input CSV is empty")
            else:
                cols = list(rows[0].keys())
                for row in rows:
                    geoid = (row.get("geoid") or "").strip()
                    if not geoid:
                        continue
                    if "registration_rate" in cols:
                        try:
                            r = float(row.get("registration_rate", 0))
                        except (TypeError, ValueError):
                            continue
                        if 0 <= r <= 1:
                            rate_by_tract[geoid] = r
                    elif "registered" in cols and "cvap" in cols:
                        try:
                            reg = int(row.get("registered", 0))
                            cvap = int(row.get("cvap", 0))
                        except (TypeError, ValueError):
                            continue
                        if cvap > 0 and 0 <= reg <= cvap:
                            rate_by_tract[geoid] = reg / float(cvap)
                print(f"Loaded {len(rate_by_tract)} tract registration rates from {input_csv}")
    else:
        if input_csv:
            print(f"Input CSV not found: {input_csv}")
        else:
            print("No --input-csv provided; writing empty outputs")

    # Division-level stats for z-score normalization
    division_values: Dict[str, List[float]] = defaultdict(list)
    for geoid, rate in rate_by_tract.items():
        div = _division_from_geoid(geoid)
        division_values[div].append(rate)

    engagement_stats: Dict[str, Dict[str, float]] = {}
    for division, vals in division_values.items():
        clean = [v for v in vals if isinstance(v, (int, float)) and not math.isnan(v)]
        if not clean:
            continue
        mean, std = _mean_std(clean)
        engagement_stats[division] = {"mean": mean, "std": std, "n": len(clean)}

    # National fallback
    all_vals: List[float] = []
    for vals in division_values.values():
        all_vals.extend(v for v in vals if isinstance(v, (int, float)) and not math.isnan(v))
    if all_vals:
        mean_all, std_all = _mean_std(all_vals)
        engagement_stats["all"] = {"mean": mean_all, "std": std_all, "n": len(all_vals)}

    os.makedirs(os.path.dirname(output_rates) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(output_stats) or ".", exist_ok=True)

    with open(output_rates, "w", encoding="utf-8") as f:
        json.dump(rate_by_tract, f, indent=2, sort_keys=True)
    print(f"Wrote tract rates to {output_rates} ({len(rate_by_tract)} tracts)")

    with open(output_stats, "w", encoding="utf-8") as f:
        json.dump(engagement_stats, f, indent=2, sort_keys=True)
    print(f"Wrote engagement stats to {output_stats} ({len(engagement_stats)} divisions)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--input-csv",
        default=None,
        help="Input CSV: geoid, registration_rate (0–1) OR geoid, registered, cvap",
    )
    ap.add_argument(
        "--output-rates",
        default="data/voter_registration_tract_rates.json",
        help="Output JSON for tract→registration_rate mapping",
    )
    ap.add_argument(
        "--output-stats",
        default="data/voter_registration_engagement_stats.json",
        help="Output JSON for division→{mean,std,n} baseline stats",
    )
    args = ap.parse_args()

    build_voter_registration_baselines(
        input_csv=args.input_csv,
        output_rates=args.output_rates,
        output_stats=args.output_stats,
    )


if __name__ == "__main__":
    main()
