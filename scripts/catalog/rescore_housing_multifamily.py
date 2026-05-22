"""
Rescore housing_value for catalog entries where multi-family building value inflation
distorts the ACS B25077 median home value (landlords report whole-building value instead
of per-unit price). Detection: renter_pct > 65% AND median_value > $900k.

Fetches fresh Census data (renter_pct + median_gross_rent) per entry and re-scores
using rent-based affordability when the inflation condition is met.

Usage:
    python scripts/catalog/rescore_housing_multifamily.py [--dry-run]
    python scripts/catalog/rescore_housing_multifamily.py --metro nyc
    python scripts/catalog/rescore_housing_multifamily.py --metro la
"""

import argparse
import json
import os
import sys
import shutil
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from data_sources import census_api
from pillars.housing_value import (
    _score_rent_affordability,
    _score_local_affordability,
    _score_space,
    _score_value_efficiency,
    _build_summary,
)

CATALOGS = {
    "nyc": "data/nyc_metro_place_catalog_scores_merged.jsonl",
    "la":  "data/la_metro_place_catalog_scores_merged.jsonl",
}

RENTER_THRESHOLD = 0.55
VALUE_THRESHOLD = 900_000


def process_catalog(path: str, dry_run: bool) -> list:
    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))

    ok = skip = err = 0

    for i, entry in enumerate(entries):
        name = entry.get("catalog", {}).get("name", f"entry_{i}")
        s = entry.get("score", {})
        coords = s.get("coordinates", {})
        lat = coords.get("lat")
        lon = coords.get("lon")
        hv = s.get("livability_pillars", {}).get("housing_value")

        if not hv or not lat or not lon:
            skip += 1
            continue

        old_score = hv.get("score")
        old_afford = hv.get("breakdown", {}).get("local_affordability")
        old_summary = hv.get("summary", {})
        median_value = old_summary.get("median_home_value")
        median_income = old_summary.get("median_household_income")
        median_rooms = old_summary.get("median_rooms")

        if not median_value or not median_income or median_rooms is None:
            skip += 1
            continue

        # Fetch fresh census data to get renter_pct and median_gross_rent
        try:
            fresh = census_api.get_housing_data(lat, lon)
        except Exception as e:
            print(f"  [{name}] census fetch failed: {e}")
            err += 1
            continue

        if fresh is None:
            skip += 1
            continue

        renter_pct = fresh.get("renter_pct")
        median_gross_rent = fresh.get("median_gross_rent")

        multifamily_inflation = (
            renter_pct is not None and renter_pct > RENTER_THRESHOLD
            and median_value > VALUE_THRESHOLD
            and median_gross_rent is not None and median_gross_rent > 0
        )

        if not multifamily_inflation:
            skip += 1
            continue

        # Windsor Square (LA) has unrepresentative census tract data for this neighborhood
        if name == "Windsor Square":
            print(f"  [{name}] skipped (known unrepresentative tract data)")
            skip += 1
            continue

        # Recompute using rent-based affordability
        affordability_score = _score_rent_affordability(median_gross_rent, median_income)
        space_score = _score_space(median_rooms)
        efficiency_score = 0.0
        new_score = round(affordability_score + space_score + efficiency_score, 1)

        delta = round(new_score - old_score, 1)
        print(
            f"  [{name}] renter={renter_pct:.0%} value=${int(median_value):,} rent=${int(median_gross_rent):,}/mo  "
            f"score {old_score}→{new_score} ({delta:+.1f})  afford {old_afford}→{affordability_score:.1f}"
        )

        if not dry_run:
            weight = hv.get("weight")
            importance = hv.get("importance_level")
            hv["score"] = new_score
            hv["contribution"] = round(new_score * (weight or 0) / 100, 2)
            hv["breakdown"]["local_affordability"] = round(affordability_score, 1)
            hv["breakdown"]["value_efficiency"] = 0.0
            hv["summary"]["median_gross_rent"] = int(median_gross_rent)
            hv["summary"]["renter_pct"] = round(renter_pct, 3)
            hv["summary"]["affordability_basis"] = "rent"
            hv["summary"]["multifamily_inflation_detected"] = True

        ok += 1
        time.sleep(0.1)

    print(f"\n  rescored={ok}  skipped={skip}  errors={err}")
    return entries


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--metro", choices=["nyc", "la"], default=None)
    args = parser.parse_args()

    metros = [args.metro] if args.metro else list(CATALOGS.keys())

    for metro in metros:
        path = CATALOGS[metro]
        print(f"\n=== {metro.upper()} ({path}) ===")
        entries = process_catalog(path, args.dry_run)

        if not args.dry_run:
            ts = time.strftime("%Y%m%d-%H%M%S")
            shutil.copy(path, f"{path}.bak.{ts}")
            with open(path, "w") as f:
                for e in entries:
                    f.write(json.dumps(e, separators=(",", ":")) + "\n")
            print(f"  Wrote {len(entries)} lines to {path}")


if __name__ == "__main__":
    main()
