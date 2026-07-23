"""
Test: waterfront_breakdown classification for two known problem cases.

1. Hudson River towns (Tarrytown, Ossining) — should be lake_river, not ocean_beach.
   Root cause: 50km regional radius from these places captures Long Island Sound
   coastline (Rye Beach 17.6km, Stamford 27.1km), making has_coastline_nearby=True
   globally, which misclassifies Hudson River beaches as ocean_beach.

2. San Fernando Valley places (Woodland Hills) — verify lake_river score comes from
   real lakes (Sepulveda Basin / Lake Balboa) not scoring artifacts.

Run from repo root:
    PYTHONPATH=. python3 scripts/test_waterfront_classification.py

Requires Overpass API access (direct internet, no .env needed).
"""

import sys
import json
import math
import requests

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# (name, lat, lon, expected_primary_category, regional_radius_km)
TEST_PLACES = [
    ("Tarrytown, NY",     41.0765, -73.8601, "lake_river", 50),
    ("Ossining, NY",      41.1626, -73.8617, "lake_river", 50),
    ("Woodland Hills, CA", 34.1683, -118.6059, "lake_river", 50),
    ("Hermosa Beach, CA", 33.8617, -118.3995, "ocean_beach", 50),  # sanity check
]

_WATERFRONT_BASE = {
    "beach": 25.0,
    "coastline": 15.0,
    "coastline_rocky": 10.0,
    "lake": 18.0,
    "swimming_area": 22.0,
    "bay": 12.0,
}

_WATERFRONT_CATEGORY_DEFAULT = {
    "beach": "ocean_beach",
    "coastline": "ocean_beach",
    "coastline_rocky": "ocean_beach",
    "lake": "lake_river",
    "swimming_area": "lake_river",
    "bay": "bay_harbor",
}


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    f1, f2 = math.radians(lat1), math.radians(lat2)
    df = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(df / 2) ** 2 + math.cos(f1) * math.cos(f2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def query_overpass(lat, lon, radius_m):
    query = f"""
[out:json][timeout:30];
(
  way["natural"~"^(beach|coastline)$"](around:{radius_m},{lat},{lon});
  relation["natural"="beach"](around:{radius_m},{lat},{lon});
  way["natural"="water"]["water"~"^(lake|bay)$"](around:{radius_m},{lat},{lon});
  relation["natural"="water"]["water"~"^(lake|bay)$"](around:{radius_m},{lat},{lon});
  way["leisure"="swimming_area"](around:{radius_m},{lat},{lon});
  relation["leisure"="swimming_area"](around:{radius_m},{lat},{lon});
);
out center tags;
"""
    r = requests.post(OVERPASS_URL, data={"data": query}, timeout=35)
    r.raise_for_status()
    return r.json().get("elements", [])


def classify_features(elements, center_lat, center_lon):
    features = []
    for e in elements:
        tags = e.get("tags", {})
        natural = tags.get("natural", "")
        leisure = tags.get("leisure", "")
        water = tags.get("water", "")

        if natural == "beach":
            surface = tags.get("surface", "")
            access = tags.get("access", "")
            if access in ("private", "no", "restricted"):
                continue
            if surface == "rock":
                feat_type = "coastline_rocky"
            else:
                feat_type = "beach"
        elif natural == "coastline":
            feat_type = "coastline"
        elif natural == "water" and water == "lake":
            feat_type = "lake"
        elif natural == "water" and water == "bay":
            feat_type = "bay"
        elif leisure == "swimming_area":
            feat_type = "swimming_area"
        else:
            continue

        # Center coords
        if "center" in e:
            elat, elon = e["center"]["lat"], e["center"]["lon"]
        elif "lat" in e:
            elat, elon = e["lat"], e["lon"]
        else:
            continue

        dist_km = haversine_km(center_lat, center_lon, elat, elon)
        features.append({
            "type": feat_type,
            "name": tags.get("name", "(unnamed)"),
            "dist_km": round(dist_km, 2),
            "osm_id": e.get("id"),
        })

    return sorted(features, key=lambda x: x["dist_km"])


def score_waterfront(features):
    has_coastline = any(f["type"] in ("coastline", "coastline_rocky") for f in features)
    effective_cat = dict(_WATERFRONT_CATEGORY_DEFAULT)
    if not has_coastline:
        effective_cat["beach"] = "lake_river"

    category_best = {"ocean_beach": 0.0, "lake_river": 0.0, "bay_harbor": 0.0}
    for f in features:
        d_m = f["dist_km"] * 1000
        base = _WATERFRONT_BASE.get(f["type"], 10.0)
        if f["type"] == "beach" and not has_coastline:
            base = _WATERFRONT_BASE["swimming_area"]
        if d_m > 3000:
            base *= math.exp(-0.00025 * (d_m - 3000))
        cat = effective_cat.get(f["type"], "lake_river")
        if base > category_best[cat]:
            category_best[cat] = base

    breakdown = {k: round(min(100.0, v / 25.0 * 100.0), 1) for k, v in category_best.items()}
    return has_coastline, breakdown


def run_tests():
    print("=" * 70)
    print("WATERFRONT CLASSIFICATION TEST")
    print("=" * 70)

    for name, lat, lon, expected_cat, radius_km in TEST_PLACES:
        radius_m = radius_km * 1000
        print(f"\n{'—'*70}")
        print(f"  {name}  (lat={lat}, lon={lon}, radius={radius_km}km)")
        print(f"  Expected primary category: {expected_cat}")

        try:
            elements = query_overpass(lat, lon, radius_m)
        except Exception as e:
            print(f"  ERROR querying Overpass: {e}")
            continue

        features = classify_features(elements, lat, lon)
        coastline_feats = [f for f in features if f["type"] in ("coastline", "coastline_rocky")]
        beach_feats = [f for f in features if f["type"] == "beach"]
        lake_feats = [f for f in features if f["type"] in ("lake", "swimming_area")]

        print(f"\n  Raw OSM features ({len(features)} total):")
        print(f"    coastline ways: {len(coastline_feats)}")
        if coastline_feats:
            for f in coastline_feats[:5]:
                print(f"      {f['name'][:40]:<40} dist={f['dist_km']:5.1f}km  id={f['osm_id']}")
        print(f"    beach ways:     {len(beach_feats)}")
        if beach_feats:
            for f in beach_feats[:5]:
                print(f"      {f['name'][:40]:<40} dist={f['dist_km']:5.1f}km")
        print(f"    lake/swim_area: {len(lake_feats)}")
        if lake_feats:
            for f in lake_feats[:5]:
                print(f"      {f['name'][:40]:<40} dist={f['dist_km']:5.1f}km  type={f['type']}")

        has_coastline, breakdown = score_waterfront(features)
        primary = max(breakdown, key=lambda k: breakdown[k])

        print(f"\n  has_coastline_nearby: {has_coastline}")
        print(f"  breakdown: ocean_beach={breakdown['ocean_beach']}  "
              f"lake_river={breakdown['lake_river']}  bay_harbor={breakdown['bay_harbor']}")
        print(f"  primary category: {primary}")

        status = "PASS" if primary == expected_cat else "FAIL"
        print(f"  → {status}  (expected {expected_cat}, got {primary})")

        # For Hudson River places: flag if coastline features are all far from the beach
        if name.endswith("NY") and has_coastline and coastline_feats and beach_feats:
            closest_coast = min(f["dist_km"] for f in coastline_feats)
            closest_beach = min(f["dist_km"] for f in beach_feats)
            print(f"\n  [DIAGNOSIS] Nearest coastline: {closest_coast:.1f}km, "
                  f"nearest beach: {closest_beach:.1f}km")
            if closest_coast > closest_beach * 3:
                print(f"  [BUG CONFIRMED] Coastline ({closest_coast:.1f}km) is far from beach "
                      f"({closest_beach:.1f}km) — heuristic is using distant LI Sound coastline "
                      f"to misclassify a Hudson River beach as ocean_beach.")

    print(f"\n{'='*70}")


if __name__ == "__main__":
    run_tests()
