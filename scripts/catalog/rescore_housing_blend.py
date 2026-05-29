"""
Rescore housing_value for all catalog entries using the tenure-weighted blend:
  affordability = owner_pct * owner_score + renter_pct * rent_score
  value_efficiency = owner_efficiency * owner_pct

Fetches fresh Census data (renter_pct + median_gross_rent) per entry.

Usage:
    python scripts/catalog/rescore_housing_blend.py [--dry-run]
    python scripts/catalog/rescore_housing_blend.py --metro nyc
    python scripts/catalog/rescore_housing_blend.py --metro la
"""

import argparse
import json
import os
import sys
import shutil
import time
import statistics

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from data_sources import census_api
from data_sources.zillow_home_values import get_home_value, CENSUS_CAP
from pillars.housing_value import (
    _score_rent_affordability,
    _score_local_affordability,
    _score_space,
    _score_value_efficiency,
)

CATALOGS = {
    "nyc": "data/nyc_metro_place_catalog_scores_merged.jsonl",
    "la":  "data/la_metro_place_catalog_scores_merged.jsonl",
}


def process_catalog(path: str, dry_run: bool) -> list:
    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))

    ok = skip = err = 0
    deltas = []

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
        old_summary = hv.get("summary", {})
        median_value = old_summary.get("median_home_value")
        median_income = old_summary.get("median_household_income")
        median_rooms = old_summary.get("median_rooms")

        if not median_income or median_rooms is None:
            skip += 1
            continue

        # Use stored tenure data when available — re-fetching can land on a different tract
        # at the boundary and introduce instability. Only fetch fresh for entries that
        # are missing renter_pct or median_gross_rent from a prior rescore run.
        stored_renter_pct = old_summary.get("renter_pct")
        stored_gross_rent = old_summary.get("median_gross_rent")

        if stored_renter_pct is not None and stored_gross_rent is not None:
            renter_pct = stored_renter_pct
            median_gross_rent = stored_gross_rent
            fresh_geo_level = old_summary.get("geo_level")
        else:
            # Neighborhoods are within large cities — tract is more granular than city place.
            # Suburbs are their own municipalities — place-level is correct.
            catalog_type = entry.get("catalog", {}).get("type", "")
            area_type_hint = "urban_core" if catalog_type == "neighborhood" else None

            try:
                fresh = census_api.get_housing_data(lat, lon, area_type=area_type_hint)
            except Exception as e:
                print(f"  [{name}] census fetch failed: {e}")
                err += 1
                continue

            if fresh is None:
                skip += 1
                continue

            renter_pct = fresh.get("renter_pct")
            median_gross_rent = fresh.get("median_gross_rent")
            fresh_geo_level = fresh.get("geo_level")

        # Apply Zillow override on top of the stored home value when Census is capped.
        zip_code = s.get("location_info", {}).get("zip")
        fresh_value, _zillow_used = get_home_value(median_value, zip_code)
        if _zillow_used:
            print(f"  [{name}] Zillow override: Census capped → ${fresh_value:,} (ZIP {zip_code})")

        owner_pct = (1.0 - renter_pct) if renter_pct is not None else None
        has_rent = median_gross_rent is not None and median_gross_rent > 0
        has_value = fresh_value is not None

        if has_value and has_rent and owner_pct is not None:
            owner_afford = _score_local_affordability(fresh_value, median_income)
            rent_afford = _score_rent_affordability(median_gross_rent, median_income)
            affordability_score = owner_pct * owner_afford + renter_pct * rent_afford
            space_score = _score_space(median_rooms)
            efficiency_score = _score_value_efficiency(fresh_value, median_rooms) * owner_pct
        elif not has_value and has_rent:
            affordability_score = _score_rent_affordability(median_gross_rent, median_income)
            space_score = _score_space(median_rooms)
            efficiency_score = 0.0
        else:
            # No new data to blend with — leave unchanged
            skip += 1
            continue

        new_score = round(affordability_score + space_score + efficiency_score, 1)
        delta = round(new_score - old_score, 1)
        deltas.append(delta)

        if abs(delta) >= 1.0:
            tenure = f"{owner_pct:.0%}own/{renter_pct:.0%}rent" if owner_pct else "rent-only"
            print(f"  [{name}] {tenure}  score {old_score}→{new_score} ({delta:+.1f})")

        if not dry_run:
            hv["score"] = new_score
            weight = hv.get("weight")
            if weight:
                hv["contribution"] = round(new_score * weight / 100, 2)
            hv["breakdown"]["local_affordability"] = round(affordability_score, 1)
            hv["breakdown"]["space"] = round(space_score, 1)
            hv["breakdown"]["value_efficiency"] = round(efficiency_score, 1)
            hv["summary"]["renter_pct"] = round(renter_pct, 3) if renter_pct is not None else None
            if median_gross_rent:
                hv["summary"]["median_gross_rent"] = int(median_gross_rent)
            if _zillow_used:
                hv["summary"]["median_home_value"] = fresh_value
                hv["summary"]["zillow_value_used"] = True
            if fresh_geo_level:
                hv["summary"]["geo_level"] = fresh_geo_level
            # Clear stale inflation flag if present
            hv["summary"].pop("multifamily_inflation_detected", None)
            hv["summary"].pop("affordability_basis", None)

        ok += 1
        time.sleep(0.05)

    print(f"\n  processed={ok}  skipped={skip}  errors={err}")
    if deltas:
        print(f"  score delta: mean={statistics.mean(deltas):+.2f}  median={statistics.median(deltas):+.2f}  range=[{min(deltas):+.1f}, {max(deltas):+.1f}]")

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
