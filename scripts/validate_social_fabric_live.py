#!/usr/bin/env python3
"""Live validation of the redesigned Social Fabric pillar on a morphology-spanning sample.

Pulls lat/lon + old catalog score from the merged catalogs, runs the live pillar
(OSM + Places + Census + Atlas cohesion), and prints old vs new with channel breakdown.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pillars import social_fabric  # noqa: E402

SAMPLE = [
    # dense urban core
    "SoHo", "Park Slope", "Carroll Gardens", "Astoria", "Chinatown",
    # immigrant / working-class (the equity test)
    "Jackson Heights", "East New York",
    # mixed urban
    "Hoboken", "Fort Lee",
    # cohesive suburb
    "Glen Ridge", "Leonia", "Larchmont Village",
    # car-dependent
    "Marina del Rey", "Hollywood Hills",
    # exurban/rural
    "Franklin Village",
]


def load_catalog():
    out = {}
    for fname in (
        "data/nyc_metro_place_catalog_scores_merged.jsonl",
        "data/la_metro_place_catalog_scores_merged.jsonl",
    ):
        if not os.path.isfile(fname):
            continue
        for line in open(fname):
            try:
                r = json.loads(line)
            except Exception:
                continue
            cat = r.get("catalog", {})
            name = cat.get("name", "")
            sc = r.get("score", {})
            sf = sc.get("livability_pillars", {}).get("social_fabric", {})
            if name and sf:
                try:
                    _lat = float(cat.get("lat"))
                    _lon = float(cat.get("lon"))
                except (TypeError, ValueError):
                    _lat = _lon = None
                out[name] = {
                    "lat": _lat,
                    "lon": _lon,
                    "old": sf.get("score"),
                    "city": cat.get("county_borough", ""),
                    "zip": str(sc.get("location_info", {}).get("zip", "")),
                }
    return out


def main():
    cat = load_catalog()
    print(f"{'neighborhood':18s} {'old':>5s} {'new':>5s} | {'cohes':>5s} {'A-bond':>6s} {'B-infra':>7s} {'eng':>4s} | dens/km2")
    print("-" * 80)
    rows = []
    for name in SAMPLE:
        info = cat.get(name)
        if not info or info["lat"] is None:
            print(f"{name:18s}  (not in catalog)")
            continue
        try:
            score, details = social_fabric.get_social_fabric_score(
                info["lat"], info["lon"], city=info["city"], zip_code=info.get("zip")
            )
        except Exception as e:
            print(f"{name:18s}  ERROR: {e}")
            continue
        s = details.get("summary", {})
        bd = details.get("breakdown", {})
        old = info["old"] or 0
        rows.append((name, old, score))
        print(
            f"{name:18s} {old:5.1f} {score:5.1f} | "
            f"{str(bd.get('cohesion')):>5s} {bd.get('bonding_cohesion', 0):6.1f} "
            f"{bd.get('infrastructure_density', 0):7.1f} {(bd.get('engagement') or 0):4.0f} | "
            f"{s.get('civic_density_per_km2')}"
        )
    if rows:
        import statistics
        print("-" * 80)
        print(f"mean old={statistics.mean(r[1] for r in rows):.1f}  mean new={statistics.mean(r[2] for r in rows):.1f}")


if __name__ == "__main__":
    main()
