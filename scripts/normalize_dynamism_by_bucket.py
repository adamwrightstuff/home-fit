#!/usr/bin/env python3
"""
Normalize the business-dynamism subcomponent by (division × area_bucket).

For each location in the input CSV, computes:
  - raw: net_estab_entry_per_1k, estabs_per_1k
  - normalized 0–100 for each using data/economic_baselines.json (same fallback
    order as the pillar: division+bucket → division+all → all+bucket → all+all)
  - dynamism_score = 0.5 * norm_net_entry + 0.5 * norm_estabs (reweight if one missing)

Output: CSV of location, division, area_bucket, raw metrics, normalized scores,
and dynamism_score; plus a short summary by (division, area_bucket).

Run from project root:
  PYTHONPATH=. python3 scripts/normalize_dynamism_by_bucket.py --input data/locations.csv
  PYTHONPATH=. python3 scripts/normalize_dynamism_by_bucket.py --input data/locations.csv --output analysis/dynamism_by_bucket.csv --limit 40
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _load_locations(path: str, limit: Optional[int]) -> List[str]:
    out: List[str] = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.reader(f):
            if not row or not row[0].strip() or row[0].strip().lower() == "location":
                continue
            out.append(row[0].strip())
            if limit and len(out) >= limit:
                break
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Normalize business-dynamism metrics by division × area_bucket.")
    ap.add_argument("--input", default=os.path.join(ROOT, "data", "locations.csv"), help="CSV with first column = location.")
    ap.add_argument("--output", default="", help="If set, write full table to this CSV.")
    ap.add_argument("--limit", type=int, default=0, help="Max locations to process (0 = no limit).")
    ap.add_argument("--sleep", type=float, default=0.1, help="Sleep between locations (seconds).")
    args = ap.parse_args()

    from data_sources.geocoding import geocode
    from data_sources.census_api import get_census_tract
    from data_sources.data_quality import detect_area_type
    from data_sources.us_census_divisions import get_division
    from data_sources.normalization import normalize_metric_to_0_100
    from scripts.build_economic_baselines import _compute_raw_metrics, _area_bucket
    from data_sources.census_api import get_population_density
    import time

    limit = args.limit if args.limit and args.limit > 0 else None
    locations = _load_locations(args.input, limit)
    print(f"Loaded {len(locations)} locations from {args.input}")
    print("Using baselines: data/economic_baselines.json (via normalization.load_economic_baselines)")
    print()

    rows: List[Dict[str, Any]] = []
    by_bucket: Dict[Tuple[str, str], List[float]] = defaultdict(list)

    for i, loc in enumerate(locations):
        try:
            g = geocode(loc)
            if not g:
                rows.append({
                    "location": loc,
                    "division": "",
                    "area_bucket": "",
                    "raw_net_entry_per_1k": None,
                    "raw_estabs_per_1k": None,
                    "norm_net_entry": None,
                    "norm_estabs": None,
                    "dynamism_score": None,
                })
                continue
            lat, lon, zip_code, state, city = g
            density = get_population_density(lat, lon)
            area_type = detect_area_type(lat, lon, density=density, city=city, location_input=loc)
            div = get_division(state)
            bucket = _area_bucket(area_type)

            raw = _compute_raw_metrics(lat, lon, state, area_type)
            if not raw:
                rows.append({
                    "location": loc,
                    "division": div,
                    "area_bucket": bucket,
                    "raw_net_entry_per_1k": None,
                    "raw_estabs_per_1k": None,
                    "norm_net_entry": None,
                    "norm_estabs": None,
                    "dynamism_score": None,
                })
                continue

            r_net = raw.get("net_estab_entry_per_1k")
            r_estabs = raw.get("estabs_per_1k")
            n_net = normalize_metric_to_0_100(metric="net_estab_entry_per_1k", value=r_net, division=div, area_bucket=bucket)
            n_estabs = normalize_metric_to_0_100(metric="estabs_per_1k", value=r_estabs, division=div, area_bucket=bucket)

            # 50/50 component; if one missing, use the other with weight 1.0
            if isinstance(n_net, (int, float)) and isinstance(n_estabs, (int, float)):
                dynamism = 0.5 * float(n_net) + 0.5 * float(n_estabs)
            elif isinstance(n_net, (int, float)):
                dynamism = float(n_net)
            elif isinstance(n_estabs, (int, float)):
                dynamism = float(n_estabs)
            else:
                dynamism = None

            if isinstance(dynamism, (int, float)):
                by_bucket[(div, bucket)].append(float(dynamism))

            rows.append({
                "location": loc,
                "division": div,
                "area_bucket": bucket,
                "raw_net_entry_per_1k": round(r_net, 4) if isinstance(r_net, (int, float)) else None,
                "raw_estabs_per_1k": round(r_estabs, 2) if isinstance(r_estabs, (int, float)) else None,
                "norm_net_entry": round(n_net, 1) if isinstance(n_net, (int, float)) else None,
                "norm_estabs": round(n_estabs, 1) if isinstance(n_estabs, (int, float)) else None,
                "dynamism_score": round(dynamism, 1) if isinstance(dynamism, (int, float)) else None,
            })
        except Exception as e:
            rows.append({
                "location": loc,
                "division": "",
                "area_bucket": "",
                "raw_net_entry_per_1k": None,
                "raw_estabs_per_1k": None,
                "norm_net_entry": None,
                "norm_estabs": None,
                "dynamism_score": None,
            })
            print(f"  Error for '{loc}': {e}", file=sys.stderr)

        if args.sleep and i < len(locations) - 1:
            time.sleep(args.sleep)

    # Summary by bucket
    print("Summary by (division, area_bucket) — business_dynamism (0–100):")
    print("-" * 60)
    for (div, bucket), scores in sorted(by_bucket.items(), key=lambda x: (-len(x[1]), x[0][0], x[0][1])):
        n = len(scores)
        avg = sum(scores) / n if n else 0
        print(f"  {div or 'all':20}  {bucket or 'all':12}  n={n:3}  mean={avg:.1f}")
    print()

    # Table output
    if args.output:
        outpath = os.path.join(ROOT, args.output) if not os.path.isabs(args.output) else args.output
        os.makedirs(os.path.dirname(outpath) or ".", exist_ok=True)
        fieldnames = ["location", "division", "area_bucket", "raw_net_entry_per_1k", "raw_estabs_per_1k", "norm_net_entry", "norm_estabs", "dynamism_score"]
        with open(outpath, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        print(f"Wrote {len(rows)} rows to {outpath}")
    else:
        print("First 10 rows (use --output <path> to write full CSV):")
        fieldnames = ["location", "division", "area_bucket", "raw_net_entry_per_1k", "raw_estabs_per_1k", "norm_net_entry", "norm_estabs", "dynamism_score"]
        for r in rows[:10]:
            print("  ", {k: r.get(k) for k in fieldnames})


if __name__ == "__main__":
    main()
