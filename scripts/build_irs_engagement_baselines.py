#!/usr/bin/env python3
"""
Build IRS BMF-based engagement baselines for the Social Fabric pillar.

This script reads raw IRS Exempt Organizations BMF CSVs, filters to
qualifying civic orgs (NTEE A/O/P/S, roughly active), assigns them to
2020 Census tracts via ZIP→lat/lon→tract lookup, and writes:

- data/irs_bmf_tract_counts.json
    {geoid: count_of_qualifying_orgs_in_tract}

- data/irs_bmf_engagement_stats.json
    {division_code: {"mean": float, "std": float, "n": int}}
    where orgs_per_1k is computed per-tract using ACS population.

Neighbors/halo are optional and not produced here; the runtime helper
will gracefully fall back to tract-only counts.

Typical usage (from project root):

  PYTHONPATH=. python3 scripts/build_irs_engagement_baselines.py \\
    --bmf-dir data/irs_bmf_raw \\
    --output-tract-counts data/irs_bmf_tract_counts.json \\
    --output-engagement-stats data/irs_bmf_engagement_stats.json \\
    --sleep 0.05

You can also pass --max-rows for a dry-run or sampling.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import time
from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Tuple

from data_sources.geocoding import geocode
from data_sources.census_api import get_census_tract, get_population
from data_sources.us_census_divisions import get_division


def _mean_std(values: List[float]) -> Tuple[float, float]:
    """Population mean/std (std uses N in denominator)."""
    n = len(values)
    if n <= 0:
        return float("nan"), float("nan")
    mean = sum(values) / n
    var = sum((x - mean) ** 2 for x in values) / n
    return mean, math.sqrt(var)


def _clean_zip(raw: str) -> Optional[str]:
    digits = "".join(ch for ch in (raw or "") if ch.isdigit())
    if len(digits) < 5:
        return None
    return digits[:5]


def _is_qualifying_org(row: Dict[str, str]) -> bool:
    """
    Rough filter for "civic" orgs:
    - NTEE major group in {A, O, P, S}
    - STATUS in {01, 02, 03} when present (unconditional/conditional)
    - Has 2-letter state and 5-digit ZIP
    """
    state = (row.get("STATE") or "").strip().upper()
    if not state or len(state) != 2:
        return False

    zip5 = _clean_zip(row.get("ZIP") or "")
    if not zip5:
        return False

    ntee = (row.get("NTEE_CD") or "").strip().upper()
    if not ntee or ntee[0] not in {"A", "O", "P", "S"}:
        return False

    status = (row.get("STATUS") or "").strip()
    if status and status not in {"01", "02", "03"}:
        return False

    return True


def _lookup_tract_for_zip(zip5: str, *, sleep: float = 0.0) -> Optional[Dict]:
    """
    Use Census geocoder via `geocode(zip)` to get a representative point,
    then map to a Census tract.
    """
    if sleep > 0:
        time.sleep(sleep)

    loc = geocode(zip5)
    if not loc:
        return None
    lat, lon, _zip_code, _state, _city = loc
    return get_census_tract(lat, lon)


def _iter_bmf_rows(bmf_dir: str) -> Iterable[Dict[str, str]]:
    for fname in sorted(os.listdir(bmf_dir)):
        if not fname.lower().endswith(".csv"):
            continue
        path = os.path.join(bmf_dir, fname)
        with open(path, newline="", encoding="latin-1") as f:
            reader = csv.DictReader(f)
            for row in reader:
                yield row


def build_engagement_baselines(
    bmf_dir: str,
    output_tract_counts: str,
    output_engagement_stats: str,
    *,
    max_rows: int = 0,
    sleep_per_new_zip: float = 0.0,
) -> None:
    """
    Main pipeline:
    1) Stream BMF rows, filter qualifying orgs.
    2) For each (state, zip5) combo, geocode once to a tract.
    3) Count qualifying orgs per tract GEOID.
    4) For each tract, fetch ACS population and compute orgs_per_1k.
    5) Aggregate orgs_per_1k by Census Division and compute mean/std.
    6) Write JSON files expected by `data_sources.irs_bmf`.
    """
    if not os.path.isdir(bmf_dir):
        raise SystemExit(f"BMF dir not found: {bmf_dir}")

    zip_to_tract: Dict[Tuple[str, str], Optional[Dict]] = {}
    org_count_by_tract: Dict[str, int] = defaultdict(int)
    tract_meta: Dict[str, Dict] = {}

    total_rows = 0
    kept_rows = 0

    for row in _iter_bmf_rows(bmf_dir):
        total_rows += 1
        if max_rows and total_rows > max_rows:
            break

        if not _is_qualifying_org(row):
            continue

        state = (row.get("STATE") or "").strip().upper()
        zip5 = _clean_zip(row.get("ZIP") or "")
        if not state or not zip5:
            continue

        key = (state, zip5)
        if key not in zip_to_tract:
            tract = _lookup_tract_for_zip(zip5, sleep=sleep_per_new_zip)
            zip_to_tract[key] = tract
        tract = zip_to_tract.get(key)
        if not tract:
            continue

        geoid = tract.get("geoid")
        if not geoid:
            continue

        org_count_by_tract[geoid] += 1
        if geoid not in tract_meta:
            tract_meta[geoid] = {
                "state_abbrev": state,
                "tract": tract,
            }

        kept_rows += 1
        if kept_rows and kept_rows % 5000 == 0:
            print(f"Processed {total_rows} rows, kept {kept_rows}, unique tracts={len(org_count_by_tract)}")

    print(
        f"Finished pass over BMF rows: total={total_rows}, "
        f"kept={kept_rows}, unique_zips={len(zip_to_tract)}, unique_tracts={len(org_count_by_tract)}"
    )

    # Write tract counts JSON
    os.makedirs(os.path.dirname(output_tract_counts) or ".", exist_ok=True)
    with open(output_tract_counts, "w", encoding="utf-8") as f:
        json.dump(org_count_by_tract, f, indent=2, sort_keys=True)
    print(f"Wrote tract counts to {output_tract_counts} ({len(org_count_by_tract)} tracts)")

    # Build per-division orgs_per_1k baselines
    division_values: Dict[str, List[float]] = defaultdict(list)
    failed_pop = 0

    for geoid, count in org_count_by_tract.items():
        meta = tract_meta.get(geoid)
        if not meta:
            continue
        tract = meta["tract"]
        state_abbrev = meta["state_abbrev"]

        population = get_population(tract) or 0
        if population <= 0:
            failed_pop += 1
            continue

        orgs_per_1k = (float(count) / float(population)) * 1000.0
        division = get_division(state_abbrev)
        division_values[division].append(orgs_per_1k)

    print(
        f"Computed orgs_per_1k for {sum(len(v) for v in division_values.values())} tracts; "
        f"population lookup failed for {failed_pop} tracts"
    )

    engagement_stats: Dict[str, Dict[str, float]] = {}
    for division, vals in division_values.items():
        clean_vals = [v for v in vals if isinstance(v, (int, float)) and not math.isnan(v)]
        if not clean_vals:
            continue
        mean, std = _mean_std(clean_vals)
        engagement_stats[division] = {"mean": mean, "std": std, "n": len(clean_vals)}

    os.makedirs(os.path.dirname(output_engagement_stats) or ".", exist_ok=True)
    with open(output_engagement_stats, "w", encoding="utf-8") as f:
        json.dump(engagement_stats, f, indent=2, sort_keys=True)
    print(f"Wrote engagement stats to {output_engagement_stats} ({len(engagement_stats)} divisions)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--bmf-dir",
        default="data/irs_bmf_raw",
        help="Directory containing raw IRS BMF CSVs (default: data/irs_bmf_raw)",
    )
    ap.add_argument(
        "--output-tract-counts",
        default="data/irs_bmf_tract_counts.json",
        help="Output JSON for tract→org_count mapping",
    )
    ap.add_argument(
        "--output-engagement-stats",
        default="data/irs_bmf_engagement_stats.json",
        help="Output JSON for division→{mean,std,n} baseline stats",
    )
    ap.add_argument(
        "--max-rows",
        type=int,
        default=0,
        help="Optional limit on number of BMF rows to process (0 = no limit)",
    )
    ap.add_argument(
        "--sleep",
        type=float,
        default=0.0,
        help="Sleep seconds before each new ZIP geocode (to be gentle on APIs)",
    )
    args = ap.parse_args()

    build_engagement_baselines(
        bmf_dir=args.bmf_dir,
        output_tract_counts=args.output_tract_counts,
        output_engagement_stats=args.output_engagement_stats,
        max_rows=args.max_rows,
        sleep_per_new_zip=args.sleep,
    )


if __name__ == "__main__":
    main()

