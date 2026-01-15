#!/usr/bin/env python3
"""
Wave 2 spot check for Natural Beauty percentile scaling.

Prints v1 (legacy linear scaling) vs v2 (percentile remap) for a curated set of anchors.
This is meant to be fast and deterministic (lat/lon pinned).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pillars.natural_beauty import calculate_natural_beauty


TEST_POINTS = [
    # Urban anchors
    ("Back Bay, Boston, MA (approx)", 42.3493, -71.0826, "urban_core", 27.0),
    ("Capitol Hill, Seattle, WA (approx)", 47.6256, -122.3210, "urban_core", 65.0),

    # Suburban anchors
    ("Barton Springs Pool, Austin, TX", 30.2638447, -97.7701429, "suburban", 48.0),
    ("Manhattan Beach, CA (approx)", 33.8847, -118.4109, "suburban", 68.0),

    # Rural anchors
    ("Lake Placid, NY (approx)", 44.2795, -73.9799, "rural", 93.0),
    ("Telluride, CO (approx)", 37.9375, -107.8123, "rural", 100.0),
    ("Truckee, CA (approx)", 39.3279, -120.1833, "rural", 100.0),

    # Extra coverage (not part of the 9-anchor contract, but useful sanity checks)
    ("Downtown LA (approx)", 34.0505, -118.2551, "urban_residential", None),
    ("Fremont Street, Las Vegas, NV (approx)", 36.1699, -115.1398, "urban_core", None),
]


def main() -> int:
    rows = []
    for name, lat, lon, area_type, expected in TEST_POINTS:
        r = calculate_natural_beauty(
            lat=lat,
            lon=lon,
            city=None,
            area_type=area_type,
            location_scope="city",
            location_name=name,
            overrides=None,
            enhancers_data=None,
            disable_enhancers=False,
            precomputed_tree_canopy_5km=None,
            density=None,
            form_context=None,
        )
        rows.append(
            {
                "name": name,
                "area_type": area_type,
                "score_v1": r.get("score_v1"),
                "score_v2": r.get("score_v2"),
                "delta": r.get("delta_v2_minus_v1"),
                "expected": expected,
            }
        )

    print("\nWave 2 Natural Beauty percentile scaling spot check\n")
    print(f"{'location':48} {'area':12} {'v1':>7} {'v2':>7} {'Δ':>7} {'expected':>9}")
    print("-" * 96)
    for row in rows:
        exp = "" if row["expected"] is None else f"{row['expected']:.1f}"
        v1 = "" if row["score_v1"] is None else f"{float(row['score_v1']):.1f}"
        v2 = "" if row["score_v2"] is None else f"{float(row['score_v2']):.1f}"
        d = "" if row["delta"] is None else f"{float(row['delta']):+.1f}"
        print(f"{row['name'][:48]:48} {row['area_type'][:12]:12} {v1:>7} {v2:>7} {d:>7} {exp:>9}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

