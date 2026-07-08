#!/usr/bin/env python3
"""Test vacation scoring for 5 representative destinations."""

import requests
import json
import time

BASE_URL = "https://home-fit-production.up.railway.app"
HEADERS = {"X-HomeFit-Proxy-Secret": "733f5a583601c3d63883954365e4b653a36f47ee45c5d84877884536abcfc7da"}

TESTS = [
    ("Aspen, CO",        "mountain", 7),
    ("Santa Barbara, CA","beach",    7),
    ("Sedona, AZ",       "mountain", 4),
    ("Myrtle Beach, SC", "beach",    7),
    ("Nashville, TN",    "city",     10),
]

def test_location(location, trip_type, month):
    params = {
        "location": location,
        "mode": "vacation",
        "trip_type": trip_type,
        "travel_month": month,
    }
    if trip_type == "beach":
        params["natural_beauty_preference"] = '["ocean"]'
    elif trip_type == "mountain":
        params["natural_beauty_preference"] = '["mountains"]'

    print(f"\n{'='*60}")
    print(f"  {location} | {trip_type} | month={month}")
    print(f"{'='*60}")
    t0 = time.time()
    try:
        r = requests.get(f"{BASE_URL}/score", params=params, headers=HEADERS, timeout=360)
        elapsed = time.time() - t0
        if r.status_code != 200:
            print(f"  ERROR {r.status_code}: {r.text[:200]}")
            return

        d = r.json()
        print(f"  Total score : {d.get('total_score', '?'):.1f}/100  ({elapsed:.1f}s)")

        pillars = d.get("livability_pillars", {})
        print(f"  {'PILLAR':<28} {'SCORE':>6}  {'WEIGHT':>7}  {'CONF':>6}")
        print(f"  {'-'*52}")
        for key, pdata in sorted(pillars.items(), key=lambda x: -x[1].get("weight", 0)):
            score  = pdata.get("score")
            weight = pdata.get("weight", 0)
            conf   = pdata.get("confidence", "?")
            if weight == 0:
                continue
            score_str = f"{score:.1f}" if isinstance(score, (int, float)) else "N/A"
            print(f"  {key:<28} {score_str:>6}  {weight:>6.1f}%  {conf:>5}%")

        alloc = d.get("metadata", {}).get("allocation_type", "?")
        print(f"\n  allocation_type: {alloc}")
        cache = d.get("metadata", {}).get("cache_hit", False)
        print(f"  cache_hit: {cache}")

        # Print error/status for any 0-score pillar
        for key, pdata in pillars.items():
            if pdata.get("weight", 0) > 0 and (pdata.get("score") or 0) == 0:
                err = pdata.get("error") or pdata.get("data_quality", {}).get("reason") or pdata.get("status")
                if err:
                    print(f"  [0-score] {key}: {err}")

    except requests.exceptions.Timeout:
        elapsed = time.time() - t0
        print(f"  TIMEOUT after {elapsed:.0f}s")
    except Exception as e:
        print(f"  EXCEPTION: {e}")

if __name__ == "__main__":
    print(f"Testing vacation scoring against {BASE_URL}")
    print(f"Running {len(TESTS)} locations...\n")
    for loc, tt, month in TESTS:
        test_location(loc, tt, month)
    print(f"\n{'='*60}")
    print("Done.")
