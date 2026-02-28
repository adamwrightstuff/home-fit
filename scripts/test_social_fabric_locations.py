#!/usr/bin/env python3
"""One-off test: run Social Fabric pillar only for given locations."""

import sys
import os

# Allow importing from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_sources.geocoding import geocode
from pillars.social_fabric import get_social_fabric_score


def main():
    locations = [
        "Larchmont NY",
        "Carroll Gardens Brooklyn NY",
        "Estes Park CO",
    ]
    for loc in locations:
        print(f"\n{'='*60}")
        print(f"  {loc}")
        print("=" * 60)
        g = geocode(loc)
        if not g:
            print("  Geocode failed.")
            continue
        lat, lon, zip_code, state, city = g
        print(f"  Geocoded: {city}, {state} {zip_code}  ({lat:.5f}, {lon:.5f})")
        score, details = get_social_fabric_score(lat, lon, city=city)
        print(f"  Social Fabric score: {score:.1f}/100")
        b = details.get("breakdown", {})
        print(f"  Breakdown: stability={b.get('stability')}, diversity={b.get('diversity')}, "
              f"civic_gathering={b.get('civic_gathering')}, engagement={b.get('engagement')}")
        s = details.get("summary", {})
        print(f"  Summary: same_house_pct={s.get('same_house_pct')}, civic_node_count_800m={s.get('civic_node_count_800m')}, "
              f"orgs_per_1k={s.get('orgs_per_1k')}, engagement_available={s.get('engagement_available')}")
    print("\nDone.")


if __name__ == "__main__":
    main()
