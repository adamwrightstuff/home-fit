"""
Recompute social_fabric stability scores for catalog entries using the new
80/20 B25038/B07003 blend (was 60/40).

Fetches tract B25038 long-tenure from Census API (one call per entry).
Uses stored same_house_pct_b07003 and place_same_house_pct from the summary.
Rewrites stability_score and top-level score in-place; civic and engagement unchanged.

Usage:
    python scripts/catalog/recompute_stability_blend.py [--dry-run]
    python scripts/catalog/recompute_stability_blend.py --metro nyc
    python scripts/catalog/recompute_stability_blend.py --metro la
"""

import argparse
import json
import os
import sys
import time
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from data_sources import census_api, social_fabric_bands
from data_sources.us_census_divisions import get_division

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

CATALOGS = {
    "nyc": "data/nyc_metro_place_catalog_scores_merged.jsonl",
    "la": "data/la_metro_place_catalog_scores_merged.jsonl",
}


def recompute_stability(
    tract_long_tenure_pct: float,
    same_house_pct_b07003: Optional[float],
    same_house_pct: Optional[float],
    place_same_house_pct: Optional[float],
    place_long_tenure_pct: Optional[float],
    division_code: Optional[str],
    bands,
) -> tuple:
    """Returns (new_stability_pct, new_stability_score)."""
    tract_rooted = None
    if tract_long_tenure_pct is not None and same_house_pct_b07003 is not None:
        tract_rooted = 0.8 * tract_long_tenure_pct + 0.2 * same_house_pct_b07003
    elif same_house_pct is not None:
        tract_rooted = same_house_pct

    place_rooted = None
    if place_same_house_pct is not None:
        if place_long_tenure_pct is not None:
            place_rooted = 0.8 * place_long_tenure_pct + 0.2 * place_same_house_pct
        else:
            place_rooted = place_same_house_pct

    if tract_rooted is not None:
        if place_rooted is not None:
            stability_pct = 0.7 * tract_rooted + 0.3 * place_rooted
        else:
            stability_pct = tract_rooted
    elif place_rooted is not None:
        stability_pct = place_rooted
    else:
        return None, None

    if bands:
        stability_score = social_fabric_bands.score_stability_from_bands(
            stability_pct, division_code, bands
        )
        rooted_pct_adjusted = social_fabric_bands.adjust_rooted_pct_for_regional_bands(
            stability_pct, division_code, bands
        )
    else:
        stability_score = None
        rooted_pct_adjusted = None

    return stability_pct, stability_score, rooted_pct_adjusted


def process_catalog(path: str, dry_run: bool) -> dict:
    bands = social_fabric_bands.load_bands()
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
        sf = s.get("livability_pillars", {}).get("social_fabric")

        if not sf or not lat or not lon:
            skip += 1
            continue

        sm = sf.get("summary", {})
        bk = sf.get("breakdown", {})

        same_house_pct = sm.get("same_house_pct")
        same_house_pct_b07003 = sm.get("same_house_pct_b07003")
        place_same_house_pct = sm.get("place_same_house_pct")
        place_long_tenure_pct = sm.get("place_long_tenure_pct")  # may be None in old entries
        civic_score = bk.get("civic_gathering")
        engagement_score = bk.get("engagement")
        old_stability = bk.get("stability")
        old_score = sf.get("score")

        # Get division for band scoring
        tract = census_api.get_census_tract(lat, lon)
        division_code = None
        if tract:
            state_fips = tract.get("state_fips")
            abbrev = _STATE_FIPS_TO_ABBREV.get(state_fips)
            if abbrev:
                division_code = get_division(abbrev)

        # Fetch B25038 for this tract
        tract_long_tenure_pct = None
        try:
            tract_long_tenure_pct = census_api.get_tract_long_tenure_housing_pct(tract)
        except Exception as e:
            print(f"  [{name}] B25038 fetch failed: {e}")
            err += 1
            continue

        if tract_long_tenure_pct is None:
            print(f"  [{name}] no B25038 data, skipping")
            skip += 1
            continue

        result = recompute_stability(
            tract_long_tenure_pct,
            same_house_pct_b07003,
            same_house_pct,
            place_same_house_pct,
            place_long_tenure_pct,
            division_code,
            bands,
        )
        new_stability_pct, new_stability_score, new_rooted_adjusted = result

        if new_stability_score is None:
            skip += 1
            continue

        raw = 1.2 * new_stability_score + 1.2 * civic_score + 1.2 * engagement_score
        new_score = max(0.0, min(100.0, round(raw / 3.6, 1)))

        delta_stability = round(new_stability_score - old_stability, 1)
        delta_score = round(new_score - old_score, 1)
        deltas.append(delta_score)

        if abs(delta_score) >= 0.5:
            print(f"  {name}: score {old_score}→{new_score} ({delta_score:+.1f})  stability {old_stability:.1f}→{new_stability_score:.1f} ({delta_stability:+.1f})")

        if not dry_run:
            sf["breakdown"]["stability"] = round(new_stability_score, 4)
            sf["score"] = new_score
            sm["stability_blend_pct"] = round(new_stability_pct, 1)
            sm["tract_long_tenure_pct"] = round(tract_long_tenure_pct, 2)
            sm["rooted_pct_adjusted_for_bands"] = round(new_rooted_adjusted, 2) if new_rooted_adjusted is not None else None

        ok += 1
        time.sleep(0.05)

    import statistics
    print(f"\n  processed={ok} skipped={skip} errors={err}")
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
            import shutil, time as t
            ts = t.strftime("%Y%m%d-%H%M%S")
            shutil.copy(path, f"{path}.bak.{ts}")
            with open(path, "w") as f:
                for entry in entries:
                    f.write(json.dumps(entry, separators=(",", ":")) + "\n")
            print(f"  Wrote {len(entries)} lines to {path}")


if __name__ == "__main__":
    main()
