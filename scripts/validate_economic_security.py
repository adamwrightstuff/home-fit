#!/usr/bin/env python3
"""
Validate economic security pillar: distribution check + resilience spot-check.

1. Distribution: Inspect sub-index score distributions by (division, area_bucket)
   to confirm no over-compression to 40-60.
2. Spot-check: Verify resilience behaves correctly for energy, tourism, college,
   and diversified metros.

Run from project root:
  python3 scripts/validate_economic_security.py [--api] [--base-url URL]

Without --api: calls pillar directly (slower, no server needed).
With --api: calls /score?only=economic_security (requires server on base-url).
"""

from __future__ import annotations

import argparse
import os
import sys

# Add project root for imports
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)
import json
import math
import sys
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

# 16 locations hitting key archetypes
LOCATIONS = [
    "Seattle, WA",
    "Denver, CO",
    "Austin, TX",
    "Boston, MA",
    "Washington, DC",
    "Los Angeles, CA",
    "Minneapolis, MN",
    "Atlanta, GA",
    "Midland, TX",
    "Williston, ND",
    "Las Vegas, NV",
    "Orlando, FL",
    "Madison, WI",
    "Ann Arbor, MI",
    "Fargo, ND",
    "Boise, ID",
]

ARCHETYPES = {
    "Seattle, WA": "diversified",
    "Denver, CO": "diversified",
    "Austin, TX": "diversified",
    "Boston, MA": "diversified",
    "Washington, DC": "diversified",
    "Los Angeles, CA": "major_metro",
    "Minneapolis, MN": "major_metro",
    "Atlanta, GA": "major_metro",
    "Midland, TX": "energy",
    "Williston, ND": "energy",
    "Las Vegas, NV": "tourism",
    "Orlando, FL": "tourism",
    "Madison, WI": "college",
    "Ann Arbor, MI": "college",
    "Fargo, ND": "smaller_interior",
    "Boise, ID": "smaller_interior",
}

COMPONENT_KEYS = [
    "job_market_strength",
    "business_dynamism",
    "resilience_and_diversification",
]


def _percentile(sorted_vals: List[float], p: float) -> float:
    if not sorted_vals:
        return float("nan")
    k = (len(sorted_vals) - 1) * p / 100.0
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_vals[int(f)]
    return sorted_vals[int(f)] * (c - k) + sorted_vals[int(c)] * (k - f)


def _distribution_stats(vals: List[float]) -> Dict[str, float]:
    vals = [v for v in vals if isinstance(v, (int, float)) and not math.isnan(v)]
    if not vals:
        return {"n": 0, "mean": float("nan"), "std": float("nan"), "min": float("nan"), "p25": float("nan"), "median": float("nan"), "p75": float("nan"), "max": float("nan")}
    s = sorted(vals)
    n = len(vals)
    mean = sum(vals) / n
    var = sum((x - mean) ** 2 for x in vals) / n
    std = math.sqrt(var) if var > 0 else 0.0
    return {
        "n": n,
        "mean": round(mean, 2),
        "std": round(std, 2),
        "min": round(s[0], 2),
        "p25": round(_percentile(s, 25), 2),
        "median": round(_percentile(s, 50), 2),
        "p75": round(_percentile(s, 75), 2),
        "max": round(s[-1], 2),
    }


def fetch_via_api(location: str, base_url: str, timeout: int = 120) -> Optional[Dict[str, Any]]:
    import requests
    url = f"{base_url}/score"
    params = {"location": location, "only": "economic_security"}
    try:
        r = requests.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        return data.get("livability_pillars", {}).get("economic_security")
    except Exception as e:
        print(f"  API error for {location}: {e}", file=sys.stderr)
        return None


def fetch_via_pillar(location: str, quick: bool = False) -> Optional[Dict[str, Any]]:
    try:
        from data_sources.geocoding import geocode
        from data_sources.census_api import get_census_tract, get_population_density
        from data_sources.data_quality import detect_area_type
        from pillars.economic_security import get_economic_security_score

        g = geocode(location)
        if not g:
            print(f"  Geocode failed: {location}", file=sys.stderr)
            return None
        lat, lon, _zip, state, city = g
        tract = get_census_tract(lat, lon)
        if quick:
            area_type = "suburban"
        else:
            density = get_population_density(lat, lon, tract=tract) or 0.0
            area_type = detect_area_type(lat, lon, density=density, city=city, location_input=location)
        score, details = get_economic_security_score(
            lat, lon, city=city, state=state, area_type=area_type, census_tract=tract
        )
        return {
            "score": score,
            "base_score": details.get("base_score"),
            "breakdown": details.get("breakdown", {}),
            "summary": details.get("summary", {}),
        }
    except Exception as e:
        print(f"  Pillar error for {location}: {e}", file=sys.stderr)
        return None


def main() -> None:
    ap = argparse.ArgumentParser(description="Validate economic security pillar")
    ap.add_argument("--api", action="store_true", help="Use /score API (requires server)")
    ap.add_argument("--base-url", default="http://localhost:8000", help="API base URL")
    ap.add_argument("--delay", type=float, default=1.0, help="Delay between requests (seconds)")
    ap.add_argument("--quick", action="store_true", help="Skip heavy area_type detection (use suburban for all)")
    args = ap.parse_args()

    def _fetch(loc: str):
        if args.api:
            return fetch_via_api(loc, args.base_url)
        return fetch_via_pillar(loc, quick=args.quick)

    fetch = _fetch

    print("Economic Security Pillar Validation")
    print("=" * 60)
    mode = "API" if args.api else ("Direct pillar (quick)" if args.quick else "Direct pillar")
    print(f"Mode: {mode}")
    print(f"Locations: {len(LOCATIONS)}")
    print()

    rows: List[Dict[str, Any]] = []
    for i, loc in enumerate(LOCATIONS):
        print(f"[{i+1}/{len(LOCATIONS)}] {loc} ...", end=" ", flush=True)
        ec = fetch(loc)
        if ec is None:
            print("FAIL")
            continue
        br = ec.get("breakdown") or {}
        sm = ec.get("summary") or {}
        division = sm.get("division", "unknown")
        area_bucket = sm.get("area_bucket", "all")
        if "area_bucket" not in sm and "area_type" in sm:
            at = str(sm.get("area_type", "")).lower()
            if at in {"urban_core", "urban_residential", "historic_urban", "urban_core_lowrise"}:
                area_bucket = "urban"
            elif at in {"suburban", "exurban"}:
                area_bucket = "suburban"
            elif at == "rural":
                area_bucket = "rural"
            else:
                area_bucket = "all"

        components = {}
        for k in COMPONENT_KEYS:
            b = br.get(k)
            if isinstance(b, dict) and "score" in b:
                s = b.get("score")
                if isinstance(s, (int, float)):
                    components[k] = float(s)

        row = {
            "location": loc,
            "archetype": ARCHETYPES.get(loc, "other"),
            "division": division,
            "area_bucket": area_bucket,
            "score": ec.get("score"),
            "base_score": ec.get("base_score"),
            "job_market_strength": components.get("job_market_strength"),
            "business_dynamism": components.get("business_dynamism"),
            "resilience_and_diversification": components.get("resilience_and_diversification"),
            "industry_hhi": sm.get("industry_diversity_hhi"),
            "anchored_balance": sm.get("anchored_balance"),
        }
        rows.append(row)
        print(f"score={ec.get('score')} resilience={row.get('resilience_and_diversification')}")

        if i < len(LOCATIONS) - 1 and args.delay > 0:
            time.sleep(args.delay)

    print()
    print("=" * 60)
    print("1. DISTRIBUTION BY BUCKET (division × area_bucket)")
    print("=" * 60)

    # Group by bucket
    by_bucket: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        key = (r["division"], r["area_bucket"])
        by_bucket[key].append(r)

    for (div, bucket), grp in sorted(by_bucket.items(), key=lambda x: (x[0][0], x[0][1])):
        print(f"\n  {div} / {bucket} (n={len(grp)})")
        for comp in COMPONENT_KEYS:
            vals = [r[comp] for r in grp if r.get(comp) is not None]
            if vals:
                st = _distribution_stats(vals)
                compr = "OK" if st["std"] >= 10 and (st["median"] < 35 or st["median"] > 65 or st["std"] > 15) else "CHECK"
                print(f"    {comp}: median={st['median']} std={st['std']} range=[{st['min']},{st['max']}] {compr}")

    print()
    print("=" * 60)
    print("2. RESILIENCE SPOT-CHECK BY ARCHETYPE")
    print("=" * 60)

    by_arch = defaultdict(list)
    for r in rows:
        by_arch[r["archetype"]].append(r)

    for arch in ["diversified", "major_metro", "college", "tourism", "energy", "smaller_interior"]:
        grp = by_arch.get(arch, [])
        if not grp:
            continue
        res_vals = [r["resilience_and_diversification"] for r in grp if r.get("resilience_and_diversification") is not None]
        avg = sum(res_vals) / len(res_vals) if res_vals else 0
        locs = ", ".join(r["location"] for r in grp)
        print(f"\n  {arch}: avg_resilience={round(avg, 1)} ({locs})")
        for r in grp:
            res = r.get("resilience_and_diversification")
            hhi = r.get("industry_hhi")
            ab = r.get("anchored_balance")
            print(f"    {r['location']}: resilience={res} HHI={hhi} anchored_balance={ab}")

    print()
    print("3. RAW OUTPUT (JSON)")
    print("-" * 40)
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
