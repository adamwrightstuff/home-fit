#!/usr/bin/env python3
"""
Build IRS BMF-based engagement baselines for the Social Fabric pillar.

This script reads raw IRS Exempt Organizations BMF CSVs, filters orgs, assigns them to
2020 Census tracts via ZIP→tract weighted allocation, and writes:

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


_STATE_FIPS_TO_ABBREV = {
    "01": "AL",
    "02": "AK",
    "04": "AZ",
    "05": "AR",
    "06": "CA",
    "08": "CO",
    "09": "CT",
    "10": "DE",
    "11": "DC",
    "12": "FL",
    "13": "GA",
    "15": "HI",
    "16": "ID",
    "17": "IL",
    "18": "IN",
    "19": "IA",
    "20": "KS",
    "21": "KY",
    "22": "LA",
    "23": "ME",
    "24": "MD",
    "25": "MA",
    "26": "MI",
    "27": "MN",
    "28": "MS",
    "29": "MO",
    "30": "MT",
    "31": "NE",
    "32": "NV",
    "33": "NH",
    "34": "NJ",
    "35": "NM",
    "36": "NY",
    "37": "NC",
    "38": "ND",
    "39": "OH",
    "40": "OK",
    "41": "OR",
    "42": "PA",
    "44": "RI",
    "45": "SC",
    "46": "SD",
    "47": "TN",
    "48": "TX",
    "49": "UT",
    "50": "VT",
    "51": "VA",
    "53": "WA",
    "54": "WV",
    "55": "WI",
    "56": "WY",
    "72": "PR",
}


def _find_col(row: Dict[str, str], names: List[str]) -> Optional[str]:
    key_map = {k.lower(): k for k in row.keys()}
    for name in names:
        hit = key_map.get(name.lower())
        if hit:
            return hit
    return None


def _safe_float(raw: str) -> Optional[float]:
    try:
        if raw is None:
            return None
        s = str(raw).strip()
        if not s:
            return None
        return float(s)
    except Exception:
        return None


def _tract_from_geoid(geoid: str) -> Optional[Dict[str, str]]:
    g = "".join(ch for ch in str(geoid or "") if ch.isdigit())
    if len(g) != 11:
        return None
    return {
        "state_fips": g[:2],
        "county_fips": g[2:5],
        "tract_fips": g[5:],
        "geoid": g,
    }


def _load_zip_tract_crosswalk(
    crosswalk_path: str,
    *,
    weight_column_hint: str = "res_ratio",
) -> Tuple[Dict[Tuple[str, str], List[Tuple[str, float]]], Dict[str, List[Tuple[str, float]]]]:
    """
    Load ZIP→tract weighted mappings.

    Supports HUD-style columns (ZIP, GEOID, RES_RATIO/TOT_RATIO) and Census
    relationship columns (GEOID_ZCTA5_20, GEOID_TRACT_20, AREALAND_PART, AREALAND_ZCTA5_20).
    Returns:
      - state+zip keyed map: (state_abbrev, zip5) -> [(tract_geoid, weight), ...]
      - zip-only keyed map: zip5 -> [(tract_geoid, weight), ...]
    """
    by_state_zip: Dict[Tuple[str, str], List[Tuple[str, float]]] = defaultdict(list)
    by_zip: Dict[str, List[Tuple[str, float]]] = defaultdict(list)
    rows = 0
    used_rows = 0
    with open(crosswalk_path, newline="", encoding="utf-8-sig") as f:
        sample = f.read(4096)
        f.seek(0)
        delimiter = "|" if sample.count("|") > sample.count(",") else ","
        reader = csv.DictReader(f, delimiter=delimiter)
        if not reader.fieldnames:
            raise SystemExit(f"Crosswalk file appears empty: {crosswalk_path}")

        zip_col = _find_col(reader.fieldnames and {c: c for c in reader.fieldnames} or {}, [
            "ZIP",
            "ZIP5",
            "zip",
            "geoid_zcta5_20",
            "zcta5",
            "zcta",
        ])
        tract_col = _find_col(reader.fieldnames and {c: c for c in reader.fieldnames} or {}, [
            "TRACT",
            "GEOID",
            "geoid_tract_20",
            "tract",
            "tract_geoid",
        ])
        state_col = _find_col(reader.fieldnames and {c: c for c in reader.fieldnames} or {}, [
            "STATE",
            "state",
            "state_abbrev",
        ])
        weight_col = _find_col(reader.fieldnames and {c: c for c in reader.fieldnames} or {}, [
            weight_column_hint,
            "RES_RATIO",
            "res_ratio",
            "TOT_RATIO",
            "tot_ratio",
        ])
        area_part_col = _find_col(reader.fieldnames and {c: c for c in reader.fieldnames} or {}, [
            "AREALAND_PART",
            "arealand_part",
        ])
        area_zip_col = _find_col(reader.fieldnames and {c: c for c in reader.fieldnames} or {}, [
            "AREALAND_ZCTA5_20",
            "arealand_zcta5_20",
        ])

        if not zip_col or not tract_col:
            raise SystemExit(
                f"Crosswalk missing required ZIP/tract columns: zip_col={zip_col}, tract_col={tract_col}"
            )

        for row in reader:
            rows += 1
            zip5 = _clean_zip(row.get(zip_col) or "")
            tract = _tract_from_geoid(row.get(tract_col) or "")
            if not zip5 or not tract:
                continue
            weight = _safe_float(row.get(weight_col) if weight_col else None)
            if (weight is None or weight < 0.0) and area_part_col and area_zip_col:
                a_part = _safe_float(row.get(area_part_col))
                a_zip = _safe_float(row.get(area_zip_col))
                if a_part is not None and a_zip and a_zip > 0:
                    weight = max(0.0, float(a_part) / float(a_zip))
            if weight is None or weight <= 0:
                continue

            geoid = tract["geoid"]
            used_rows += 1
            by_zip[zip5].append((geoid, weight))

            if state_col:
                st = (row.get(state_col) or "").strip().upper()
                if len(st) == 2:
                    by_state_zip[(st, zip5)].append((geoid, weight))

    def _normalize(bucket: Dict) -> None:
        for key, vals in list(bucket.items()):
            total = sum(w for _, w in vals if w > 0)
            if total <= 0:
                del bucket[key]
                continue
            bucket[key] = [(g, w / total) for g, w in vals if w > 0]

    _normalize(by_zip)
    _normalize(by_state_zip)

    print(
        f"Loaded ZIP→tract crosswalk from {crosswalk_path}: "
        f"rows={rows}, usable_rows={used_rows}, zip_keys={len(by_zip)}, state_zip_keys={len(by_state_zip)}"
    )
    return dict(by_state_zip), dict(by_zip)


def _allocate_integer_counts(total: int, weights: List[Tuple[str, float]]) -> Dict[str, int]:
    """
    Split an integer count across tracts by normalized weights while preserving the total.
    Uses largest-remainder apportionment.
    """
    if total <= 0 or not weights:
        return {}
    norm_total = sum(w for _, w in weights if w > 0)
    if norm_total <= 0:
        return {}
    raw = [(g, (w / norm_total) * float(total)) for g, w in weights if w > 0]
    floors = {g: int(math.floor(v)) for g, v in raw}
    remainder = total - sum(floors.values())
    ranked = sorted(((v - math.floor(v), g) for g, v in raw), reverse=True)
    for _frac, geoid in ranked[: max(0, remainder)]:
        floors[geoid] = floors.get(geoid, 0) + 1
    return {g: c for g, c in floors.items() if c > 0}


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
    zip_tract_crosswalk_path: Optional[str] = None,
    crosswalk_weight_column: str = "res_ratio",
    max_rows: int = 0,
    sleep_per_new_zip: float = 0.0,
) -> None:
    """
    Main pipeline:
    1) Stream BMF rows; count refined (N/P/S/W) and legacy (A/O/P/S) per ZIP.
    2) Allocate ZIP counts to tracts via weighted crosswalk (preferred), with ZIP centroid fallback.
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
    zip_refined: Dict[Tuple[str, str], int] = defaultdict(int)
    zip_legacy: Dict[Tuple[str, str], int] = defaultdict(int)
    org_refined: Dict[str, int] = defaultdict(int)
    org_legacy: Dict[str, int] = defaultdict(int)
    tract_meta: Dict[str, Dict] = {}
    crosswalk_by_state_zip: Dict[Tuple[str, str], List[Tuple[str, float]]] = {}
    crosswalk_by_zip: Dict[str, List[Tuple[str, float]]] = {}

    if zip_tract_crosswalk_path:
        if not os.path.exists(zip_tract_crosswalk_path):
            raise SystemExit(f"ZIP→tract crosswalk not found: {zip_tract_crosswalk_path}")
        crosswalk_by_state_zip, crosswalk_by_zip = _load_zip_tract_crosswalk(
            zip_tract_crosswalk_path,
            weight_column_hint=crosswalk_weight_column,
        )

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

        if is_r:
            kept_refined += 1
            zip_refined[(state, zip5)] += 1
        if is_l:
            kept_legacy += 1
            zip_legacy[(state, zip5)] += 1

        if (kept_refined + kept_legacy) and (kept_refined + kept_legacy) % 5000 == 0:
            print(
                f"Processed {total_rows} rows, refined={kept_refined}, legacy={kept_legacy}, "
                f"unique_zips={len(set(zip_refined) | set(zip_legacy))}"
            )

    all_zip_keys = sorted(set(zip_refined) | set(zip_legacy))
    crosswalk_allocated = 0
    fallback_allocated = 0
    missing_allocations = 0
    for state, zip5 in all_zip_keys:
        weights = crosswalk_by_state_zip.get((state, zip5)) or crosswalk_by_zip.get(zip5)
        if weights:
            alloc_r = _allocate_integer_counts(zip_refined.get((state, zip5), 0), weights)
            alloc_l = _allocate_integer_counts(zip_legacy.get((state, zip5), 0), weights)
            crosswalk_allocated += 1
            for geoid, c in alloc_r.items():
                org_refined[geoid] += c
            for geoid, c in alloc_l.items():
                org_legacy[geoid] += c
            for geoid, _w in weights:
                if geoid in tract_meta:
                    continue
                tract = _tract_from_geoid(geoid)
                if not tract:
                    continue
                state_abbrev = _STATE_FIPS_TO_ABBREV.get(tract["state_fips"], state)
                tract_meta[geoid] = {"state_abbrev": state_abbrev, "tract": tract}
            continue

        key = (state, zip5)
        if key not in zip_to_tract:
            tract = _lookup_tract_for_zip(zip5, sleep=sleep_per_new_zip)
            zip_to_tract[key] = tract
        tract = zip_to_tract.get(key)
        if not tract or not tract.get("geoid"):
            missing_allocations += 1
            continue
        geoid = str(tract["geoid"])
        fallback_allocated += 1
        org_refined[geoid] += int(zip_refined.get((state, zip5), 0))
        org_legacy[geoid] += int(zip_legacy.get((state, zip5), 0))
        if geoid not in tract_meta:
            tract_meta[geoid] = {"state_abbrev": state, "tract": tract}

    print(
        f"Finished pass over BMF rows: total={total_rows}, refined_hits={kept_refined}, "
        f"legacy_hits={kept_legacy}, unique_zips={len(all_zip_keys)}, unique_tracts={len(tract_meta)}, "
        f"crosswalk_allocated_zips={crosswalk_allocated}, fallback_allocated_zips={fallback_allocated}, "
        f"unallocated_zips={missing_allocations}"
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
        "--zip-tract-crosswalk",
        default="data/crosswalks/tab20_zcta520_tract20_natl.txt",
        help=(
            "ZIP→tract crosswalk file (HUD USPS preferred with RES_RATIO/TOT_RATIO; "
            "Census relationship file also supported). Use '' to disable."
        ),
    )
    ap.add_argument(
        "--crosswalk-weight-column",
        default="res_ratio",
        help="Preferred crosswalk weight column (default: res_ratio)",
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
        zip_tract_crosswalk_path=(args.zip_tract_crosswalk or "").strip() or None,
        crosswalk_weight_column=args.crosswalk_weight_column,
        max_rows=args.max_rows,
        sleep_per_new_zip=args.sleep,
    )


if __name__ == "__main__":
    main()

