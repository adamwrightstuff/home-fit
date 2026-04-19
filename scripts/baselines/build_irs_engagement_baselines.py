#!/usr/bin/env python3
"""
Build IRS BMF-based engagement baselines for the Social Fabric pillar.

This script reads raw IRS Exempt Organizations BMF CSVs, filters orgs, assigns them to
2020 Census tracts via ZIP→lat/lon→tract lookup, and writes:

- data/irs_bmf_tract_counts.json — **refined** civic-facing NTEE only (N, P, S, W)
- data/irs_bmf_tract_counts_legacy.json — legacy filter (A, O, P, S) for fallback scoring

- data/irs_bmf_engagement_stats.json — mean/std from refined orgs_per_1k by division
- data/irs_bmf_engagement_stats_legacy.json — mean/std from legacy orgs_per_1k

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


def _row_base_ok(row: Dict[str, str]) -> bool:
    state = (row.get("STATE") or "").strip().upper()
    if not state or len(state) != 2:
        return False
    zip5 = _clean_zip(row.get("ZIP") or "")
    if not zip5:
        return False
    status = (row.get("STATUS") or "").strip()
    if status and status not in {"01", "02", "03"}:
        return False
    return True


def _is_qualifying_org_refined(row: Dict[str, str]) -> bool:
    """Civic-facing NTEE: community (S), recreation (N), human services (P), public benefit (W)."""
    if not _row_base_ok(row):
        return False
    ntee = (row.get("NTEE_CD") or "").strip().upper()
    if not ntee or ntee[0] not in {"N", "P", "S", "W"}:
        return False
    return True


def _is_qualifying_org_legacy(row: Dict[str, str]) -> bool:
    """Legacy filter: NTEE A/O/P/S (arts + open space + human services + community)."""
    if not _row_base_ok(row):
        return False
    ntee = (row.get("NTEE_CD") or "").strip().upper()
    if not ntee or ntee[0] not in {"A", "O", "P", "S"}:
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


def _write_engagement_stats(
    org_count_by_tract: Dict[str, int],
    tract_meta: Dict[str, Dict],
    output_path: str,
) -> None:
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

    all_vals: List[float] = []
    for vals in division_values.values():
        all_vals.extend(v for v in vals if isinstance(v, (int, float)) and not math.isnan(v))
    if all_vals:
        mean_all, std_all = _mean_std(all_vals)
        engagement_stats["all"] = {"mean": mean_all, "std": std_all, "n": len(all_vals)}

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(engagement_stats, f, indent=2, sort_keys=True)
    print(f"Wrote engagement stats to {output_path} ({len(engagement_stats)} divisions)")


def build_engagement_baselines(
    bmf_dir: str,
    output_tract_counts: str,
    output_engagement_stats: str,
    *,
    output_tract_counts_legacy: Optional[str] = None,
    output_engagement_stats_legacy: Optional[str] = None,
    max_rows: int = 0,
    sleep_per_new_zip: float = 0.0,
) -> None:
    """
    Main pipeline:
    1) Stream BMF rows; count refined (N/P/S/W) and legacy (A/O/P/S) per tract.
    2) Geocode ZIP once per (state, zip5).
    3) Write refined + legacy tract JSON and division stats for each.
    """
    if not os.path.isdir(bmf_dir):
        raise SystemExit(f"BMF dir not found: {bmf_dir}")

    base_dir = os.path.dirname(output_tract_counts) or "."
    if output_tract_counts_legacy is None:
        output_tract_counts_legacy = os.path.join(base_dir, "irs_bmf_tract_counts_legacy.json")
    if output_engagement_stats_legacy is None:
        output_engagement_stats_legacy = os.path.join(
            os.path.dirname(output_engagement_stats) or ".",
            "irs_bmf_engagement_stats_legacy.json",
        )

    zip_to_tract: Dict[Tuple[str, str], Optional[Dict]] = {}
    org_refined: Dict[str, int] = defaultdict(int)
    org_legacy: Dict[str, int] = defaultdict(int)
    tract_meta: Dict[str, Dict] = {}

    total_rows = 0
    kept_refined = 0
    kept_legacy = 0

    for row in _iter_bmf_rows(bmf_dir):
        total_rows += 1
        if max_rows and total_rows > max_rows:
            break

        is_r = _is_qualifying_org_refined(row)
        is_l = _is_qualifying_org_legacy(row)
        if not is_r and not is_l:
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

        if is_r:
            org_refined[geoid] += 1
            kept_refined += 1
        if is_l:
            org_legacy[geoid] += 1
            kept_legacy += 1

        if geoid not in tract_meta:
            tract_meta[geoid] = {
                "state_abbrev": state,
                "tract": tract,
            }

        if (kept_refined + kept_legacy) and (kept_refined + kept_legacy) % 5000 == 0:
            print(
                f"Processed {total_rows} rows, refined={kept_refined}, legacy={kept_legacy}, "
                f"unique_tracts={len(tract_meta)}"
            )

    print(
        f"Finished pass over BMF rows: total={total_rows}, refined_hits={kept_refined}, "
        f"legacy_hits={kept_legacy}, unique_zips={len(zip_to_tract)}, unique_tracts={len(tract_meta)}"
    )

    os.makedirs(os.path.dirname(output_tract_counts) or ".", exist_ok=True)
    with open(output_tract_counts, "w", encoding="utf-8") as f:
        json.dump(dict(org_refined), f, indent=2, sort_keys=True)
    print(f"Wrote refined tract counts to {output_tract_counts} ({len(org_refined)} tracts)")

    with open(output_tract_counts_legacy, "w", encoding="utf-8") as f:
        json.dump(dict(org_legacy), f, indent=2, sort_keys=True)
    print(f"Wrote legacy tract counts to {output_tract_counts_legacy} ({len(org_legacy)} tracts)")

    _write_engagement_stats(org_refined, tract_meta, output_engagement_stats)
    _write_engagement_stats(org_legacy, tract_meta, output_engagement_stats_legacy)


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
        help="Output JSON for division→{mean,std,n} (refined N/P/S/W)",
    )
    ap.add_argument(
        "--output-tract-counts-legacy",
        default="data/irs_bmf_tract_counts_legacy.json",
        help="Legacy A/O/P/S tract counts",
    )
    ap.add_argument(
        "--output-engagement-stats-legacy",
        default="data/irs_bmf_engagement_stats_legacy.json",
        help="Division stats from legacy orgs_per_1k",
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
        output_tract_counts_legacy=args.output_tract_counts_legacy,
        output_engagement_stats_legacy=args.output_engagement_stats_legacy,
        max_rows=args.max_rows,
        sleep_per_new_zip=args.sleep,
    )


if __name__ == "__main__":
    main()

