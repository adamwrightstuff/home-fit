#!/usr/bin/env python3
"""
Wave 2 spot check for Natural Beauty percentile scaling.

Prints v1 (legacy linear scaling) vs v2 (percentile remap) for a curated set of points.
This script is intentionally lightweight and does NOT hard-fail; it is for manual review.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pillars.natural_beauty import calculate_natural_beauty


TEST_POINTS = [
    # Urban examples
    ("Back Bay, Boston, MA (approx)", 42.3493, -71.0826, "urban_core"),
    ("Capitol Hill, Seattle, WA (approx)", 47.6256, -122.3210, "urban_core"),

    # Suburban examples
    ("Barton Springs Pool, Austin, TX", 30.2638447, -97.7701429, "suburban"),
    ("Manhattan Beach, CA (approx)", 33.8847, -118.4109, "suburban"),

    # Rural examples
    ("Lake Placid, NY (approx)", 44.2795, -73.9799, "rural"),
    ("Telluride, CO (approx)", 37.9375, -107.8123, "rural"),
    ("Truckee, CA (approx)", 39.3279, -120.1833, "rural"),

    # Extra coverage
    ("Downtown LA (approx)", 34.0505, -118.2551, "urban_residential"),
    ("Fremont Street, Las Vegas, NV (approx)", 36.1699, -115.1398, "urban_core"),
]


def main() -> int:
    rows = []
    for name, lat, lon, area_type in TEST_POINTS:
        r = calculate_natural_beauty(
            lat=lat,
            lon=lon,
            city=None,
            area_type=area_type,
            location_scope="city",
            location_name=name,
            overrides=None,
            enhancers_data=None,
            # Disable enhancers (viewpoints) to reduce OSM pressure; context still uses OSM for parks/water.
            disable_enhancers=True,
            precomputed_tree_canopy_5km=None,
            density=None,
            form_context=None,
        )
        rows.append(
            {
                "name": name,
                "area_type": area_type,
                "score": r.get("score"),
                "score_v1": r.get("score_v1"),
                "score_v2": r.get("score_v2"),
                "delta": r.get("delta_v2_minus_v1"),
                "enabled": r.get("percentile_scaling_enabled"),
            }
        )

    print("\nWave 2 Natural Beauty percentile scaling spot check\n")
    print(f"{'location':48} {'area':12} {'score':>7} {'v1':>7} {'v2':>7} {'Δ':>7} {'on?':>5}")
    print("-" * 96)
    for row in rows:
        s = "" if row["score"] is None else f"{float(row['score']):.1f}"
        v1 = "" if row["score_v1"] is None else f"{float(row['score_v1']):.1f}"
        v2 = "" if row["score_v2"] is None else f"{float(row['score_v2']):.1f}"
        d = "" if row["delta"] is None else f"{float(row['delta']):+.1f}"
        on = "yes" if row.get("enabled") else "no"
        print(f"{row['name'][:48]:48} {row['area_type'][:12]:12} {s:>7} {v1:>7} {v2:>7} {d:>7} {on:>5}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
Wave 2 spot check for Natural Beauty percentile scaling.

Prints v1 (legacy linear scaling) vs v2 (percentile remap) for a curated set of points.
This script is intentionally lightweight and does NOT hard-fail; it is for manual review.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pillars.natural_beauty import calculate_natural_beauty


TEST_POINTS = [
    # Urban examples
    ("Back Bay, Boston, MA (approx)", 42.3493, -71.0826, "urban_core"),
    ("Capitol Hill, Seattle, WA (approx)", 47.6256, -122.3210, "urban_core"),

    # Suburban examples
    ("Barton Springs Pool, Austin, TX", 30.2638447, -97.7701429, "suburban"),
    ("Manhattan Beach, CA (approx)", 33.8847, -118.4109, "suburban"),

    # Rural examples
    ("Lake Placid, NY (approx)", 44.2795, -73.9799, "rural"),
    ("Telluride, CO (approx)", 37.9375, -107.8123, "rural"),
    ("Truckee, CA (approx)", 39.3279, -120.1833, "rural"),

    # Extra coverage
    ("Downtown LA (approx)", 34.0505, -118.2551, "urban_residential"),
    ("Fremont Street, Las Vegas, NV (approx)", 36.1699, -115.1398, "urban_core"),
]


def main() -> int:
    rows = []
    for name, lat, lon, area_type in TEST_POINTS:
        r = calculate_natural_beauty(
            lat=lat,
            lon=lon,
            city=None,
            area_type=area_type,
            location_scope="city",
            location_name=name,
            overrides=None,
            enhancers_data=None,
            # Disable enhancers (viewpoints) to reduce OSM pressure; context still uses OSM for parks/water.
            disable_enhancers=True,
            precomputed_tree_canopy_5km=None,
            density=None,
            form_context=None,
        )
        rows.append(
            {
                "name": name,
                "area_type": area_type,
                "score": r.get("score"),
                "score_v1": r.get("score_v1"),
                "score_v2": r.get("score_v2"),
                "delta": r.get("delta_v2_minus_v1"),
                "enabled": r.get("percentile_scaling_enabled"),
            }
        )

    print("\nWave 2 Natural Beauty percentile scaling spot check\n")
    print(f"{'location':48} {'area':12} {'score':>7} {'v1':>7} {'v2':>7} {'Δ':>7} {'on?':>5}")
    print("-" * 96)
    for row in rows:
        s = "" if row["score"] is None else f"{float(row['score']):.1f}"
        v1 = "" if row["score_v1"] is None else f"{float(row['score_v1']):.1f}"
        v2 = "" if row["score_v2"] is None else f"{float(row['score_v2']):.1f}"
        d = "" if row["delta"] is None else f"{float(row['delta']):+.1f}"
        on = "yes" if row.get("enabled") else "no"
        print(f"{row['name'][:48]:48} {row['area_type'][:12]:12} {s:>7} {v1:>7} {v2:>7} {d:>7} {on:>5}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

