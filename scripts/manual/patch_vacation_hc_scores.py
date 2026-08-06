#!/usr/bin/env python3
"""
Offline patch: recompute vacation HC scores for places where stored data is wrong.

The original catalog was scored with residential HC logic, so nearest_hospital_km
was never stored in the breakdown. The offline recompute in the previous session
found None for all of these and wrote score=20.

Fix: use hardcoded coordinates for the nearest REAL local hospital, compute
haversine distance from stored place lat/lon, apply the distance-only curve.

No API calls. Run from repo root:
  PYTHONPATH=. python3 scripts/manual/patch_vacation_hc_scores.py
"""
from __future__ import annotations
import json, math
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
JSONL = REPO_ROOT / "data" / "vacation_destinations_scores.jsonl"

# location → (hospital_lat, hospital_lon, hospital_name, distance_note)
CORRECT_HOSPITALS: dict[str, tuple] = {
    "Jackson, WY":           (43.4824, -110.7634, "St. John's Medical Center",              "~0.3km"),
    "Vail, CO":              (39.6430, -106.3754, "Vail Health Hospital",                    "~1km"),
    "Steamboat Springs, CO": (40.4845, -106.8318, "Yampa Valley Medical Center",             "~0.1km"),
    "Moab, UT":              (38.5745, -109.5486, "Moab Regional Hospital",                  "~0.1km"),
    "Kill Devil Hills, NC":  (35.9520, -75.6167,  "The Outer Banks Hospital",                "~10km"),
    "Virginia Beach, VA":    (36.7872, -76.0339,  "Sentara Virginia Beach General Hospital", "~9km"),
    "Destin, FL":            (30.3699, -86.5100,  "Sacred Heart Hospital Emerald Coast",     "~3km"),
    "Bar Harbor, ME":        (44.3728, -68.2028,  "Mount Desert Island Hospital",            "~1.6km"),
    "Asheville, NC":         (35.5751, -82.5423,  "Mission Hospital Asheville",              "~2.4km"),
    "Newport, RI":           (41.4944, -71.3175,  "Newport Hospital",                        "~0.6km"),
    "South Lake Tahoe, CA":  (38.9406, -119.9626, "Barton Memorial Hospital",                "~1.7km"),
    "Hilton Head, SC":       (32.2283, -80.8519,  "Coastal Carolina Hospital",               "~12km"),
    "Monterey, CA 93940":    (36.5935, -121.9018, "Community Hospital of Monterey Peninsula","~1km"),
    "Santa Fe, NM":          (35.6909, -106.0153, "CHRISTUS St. Vincent Regional",           "~7km"),
    "Breckenridge, CO":      (39.5741, -106.0980, "Summit Health Medical Center (Frisco)",   "~11km"),
    "Telluride, CO":         (38.4784, -107.8779, "Montrose Memorial Hospital",              "~60km"),
    "Gatlinburg, TN":        (35.8717, -83.5657,  "LeConte Medical Center (Sevierville)",    "~18km"),
    "Stowe, VT":             (44.5598, -72.6232,  "Copley Hospital (Morrisville)",           "~12km"),
    "Park City, UT":         (40.6441, -111.4980, "University of Utah Health Park City",     "~0.2km"),
    "Provincetown, MA":      (41.6429, -70.2778,  "Cape Cod Hospital (Hyannis)",             "~46km"),
    "Napa, CA":              (38.3019, -122.3059, "Queen of the Valley Medical Center",      "~21km from stored coord"),
    "Austin, TX":            (30.2930, -97.7285,  "St. David's Medical Center",              "~2km"),
}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def vacation_hc_score(dist_km: float | None) -> float:
    if dist_km is None:  return 20.0
    if dist_km <= 5:     return 90.0
    if dist_km <= 15:    return 75.0
    if dist_km <= 30:    return 60.0
    if dist_km <= 60:    return 45.0
    if dist_km <= 90:    return 30.0
    return 20.0


def load_rows() -> dict:
    rows: dict[tuple, dict] = {}
    for line in JSONL.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        k = (r.get("location"), r.get("trip_type"))
        prev = rows.get(k)
        if prev is None or (r.get("total_score") or 0) > (prev.get("total_score") or 0):
            rows[k] = r
    return rows


def save_rows(rows: dict):
    lines = [json.dumps(r) for r in rows.values()]
    JSONL.write_text("\n".join(lines) + "\n")


def main():
    rows = load_rows()
    patched = 0

    for (loc, tt), row in rows.items():
        if loc not in CORRECT_HOSPITALS:
            continue

        coords = row.get("score_data", {}).get("coordinates", {})
        place_lat = coords.get("lat")
        place_lon = coords.get("lon")
        if place_lat is None or place_lon is None:
            print(f"  SKIP {loc}: no stored coordinates")
            continue

        hosp_lat, hosp_lon, hosp_name, note = CORRECT_HOSPITALS[loc]
        dist_km = haversine_km(place_lat, place_lon, hosp_lat, hosp_lon)
        new_score = vacation_hc_score(dist_km)

        old_hc = row.get("pillars", {}).get("healthcare_access", {})
        old_score = old_hc.get("score") or 0

        # Recompute total_score
        pillars = row.get("pillars", {})
        orig_weight = old_hc.get("weight") or 0
        new_hc = {**old_hc, "score": new_score}
        pillars = {**pillars, "healthcare_access": new_hc}

        total_w = sum((v.get("weight") or 0) for v in pillars.values())
        total_score = (
            sum((v.get("score") or 0) * (v.get("weight") or 0) for v in pillars.values()) / total_w
            if total_w > 0 else 0
        )

        row["pillars"] = pillars
        row["total_score"] = round(total_score, 1)
        patched += 1

        print(f"  {loc} ({tt}): HC {old_score:.0f}→{new_score:.0f}  "
              f"dist={dist_km:.1f}km  [{hosp_name}]  "
              f"total {row.get('total_score'):.1f}  {note}")

    save_rows(rows)
    print(f"\n{patched} places patched.")

    print("\nRankings:")
    ranked = sorted(rows.values(), key=lambda r: r.get("total_score") or 0, reverse=True)
    for r in ranked:
        hc = r.get("pillars", {}).get("healthcare_access", {})
        print(f"  {r.get('total_score', 0):5.1f}  {r['location']:35s} ({r['trip_type']:8s})  HC={hc.get('score','?')}")


if __name__ == "__main__":
    main()
