"""
Air Travel Access Pillar

Scores how much of where Americans fly a place can reach nonstop from the airports within reach of it.

Score (0-100) = share of national domestic passenger boardings (FAA CY2023) whose airport is served nonstop
(BTS T-100 segment data, 2023) by at least one airport the traveller can reach. Each reachable airport counts
with a time credit: full credit up to PLATEAU_MIN of driving, then the share of people still willing to travel
that long (Ipsos survey for Airlines for America, 2018) relative to the share at the plateau. For each
destination the best credit among the airports serving it is used, so a destination served from two reachable
airports is not counted twice. It is an adequacy measure on a fixed national standard (design principles v2, P1).

Every parameter below carries its source and plausible range (design principles v2, P4). See
docs/PILLAR_AIR_TRAVEL.md for the evidence, sensitivity results and known limits.
"""

import json
import math
import os
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

from data_sources.data_quality import assess_pillar_data_quality

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_AIRPORTS_FILE = os.path.join(_ROOT, "data_sources", "static", "airports.json")
_COVERAGE_FILE = os.path.join(_ROOT, "data_sources", "static", "airport_nonstop_served_2023.json")

# Drive time from straight-line distance, used when no routed time is supplied (live scoring).
# Fitted to routed OSRM free-flow times for 1,474 catalog pins (median error 4 to 9 minutes by area type).
# Per area type the fit gave intercepts 9.5 to 11.4 minutes and slopes 0.92 to 0.98 minutes per km, so one line is used.
ACCESS_OVERHEAD_MIN = 10.0
MIN_PER_KM = 0.95

# Airports farther than this are ignored (their credit is below 6% at this distance).
CANDIDATE_RADIUS_KM = 400.0

# Full credit up to this many minutes. Judgment: the median maximum acceptable travel time to an airport in the
# Ipsos/A4A survey (January 2018, n=5,046). Plausible range 30 to 90 minutes; the catalog mean moves from 76 to 87.
PLATEAU_MIN = 60.0

# Share of respondents whose maximum acceptable travel time is at most x minutes (Ipsos/A4A 2018; question asked
# about travel for a cheaper flight, so beyond the plateau this is a stretch and is labelled as such). The last
# bucket (over 4 hours) is closed at 6 hours; published shares sum to 99 because of rounding.
ACCEPTABLE_TIME_CDF = [(0, 0.0), (30, 0.33), (60, 0.60), (90, 0.78), (120, 0.90), (180, 0.94), (240, 0.96), (360, 1.0)]


def _share_willing(minutes: float) -> float:
    """Share of people whose maximum acceptable time is at least `minutes` (piecewise linear between survey buckets)."""
    for (a, ca), (b, cb) in zip(ACCEPTABLE_TIME_CDF, ACCEPTABLE_TIME_CDF[1:]):
        if minutes <= b:
            return 1.0 - (ca + (cb - ca) * (minutes - a) / (b - a))
    return 0.0


def time_credit(minutes: float) -> float:
    """1.0 up to the plateau, then the survey curve relative to its value at the plateau."""
    if minutes <= PLATEAU_MIN:
        return 1.0
    return _share_willing(minutes) / _share_willing(PLATEAU_MIN)


def estimate_drive_minutes(distance_km: float) -> float:
    """Drive minutes from straight-line distance (fitted line; see ACCESS_OVERHEAD_MIN)."""
    return ACCESS_OVERHEAD_MIN + MIN_PER_KM * distance_km


@lru_cache(maxsize=1)
def _load_coverage() -> Tuple[Dict[str, frozenset], Dict[str, int], int]:
    """Nonstop destination sets per airport and national boardings. Raises if the data is unavailable."""
    try:
        with open(_COVERAGE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        served = {code: frozenset(dests) for code, dests in data["served"].items()}
        boardings = {code: int(v) for code, v in data["boardings"].items()}
    except Exception as exc:
        raise RuntimeError(f"air travel coverage data unavailable ({_COVERAGE_FILE}): {exc}") from exc
    total = sum(boardings.values())
    if not served or total <= 0:
        raise RuntimeError("air travel coverage data is empty")
    return served, boardings, total


@lru_cache(maxsize=1)
def _load_airports() -> Tuple[Dict, ...]:
    """Airports with a location. Raises if the file is unavailable."""
    try:
        with open(_AIRPORTS_FILE, "r", encoding="utf-8") as f:
            airports = json.load(f)["airports"]
    except Exception as exc:
        raise RuntimeError(f"airport database unavailable ({_AIRPORTS_FILE}): {exc}") from exc
    usable = tuple(a for a in airports if a.get("code") and a.get("lat") is not None and a.get("lon") is not None)
    if not usable:
        raise RuntimeError("airport database is empty")
    return usable


def coverage_score(minutes_by_airport: Dict[str, float]) -> Tuple[float, Dict]:
    """
    Score from drive minutes to each reachable airport (code -> minutes).

    Returns (score 0-100, detail) where detail has the best single airport and each airport's standalone
    coverage. An empty input is a genuine zero (no airport within reach), not missing data.
    """
    served, boardings, total = _load_coverage()
    credit_by_dest: Dict[str, float] = {}
    per_airport = {}
    for code, minutes in minutes_by_airport.items():
        dests = served.get(code)
        if not dests or minutes is None:
            continue
        credit = time_credit(minutes)
        own = sum(boardings.get(d, 0) for d in dests) / total
        per_airport[code] = {"minutes": minutes, "credit": credit, "coverage": own, "weighted": own * credit}
        for d in dests:
            if credit > credit_by_dest.get(d, 0.0):
                credit_by_dest[d] = credit
    score = 100.0 * sum(boardings.get(d, 0) * c for d, c in credit_by_dest.items()) / total
    best = max(per_airport, key=lambda c: per_airport[c]["weighted"]) if per_airport else None
    return score, {"best_airport": best, "per_airport": per_airport}


def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in meters."""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def score_location(lat: float, lon: float, drive_minutes: Optional[Dict[str, float]] = None) -> Tuple[float, Dict, List[Dict]]:
    """
    Score a point without any network call. Returns (score, breakdown without metadata blocks, nearby airports).

    drive_minutes: routed minutes by airport code (the offline catalog passes these); airports missing from it,
    and every airport when it is None, use the fitted line on straight-line distance.
    Raises RuntimeError when the airport or coverage data is unavailable.
    """
    airports = _load_airports()
    served, _, _ = _load_coverage()
    nearby = []
    for airport in airports:
        distance_km = _haversine_distance(lat, lon, airport["lat"], airport["lon"]) / 1000
        if distance_km <= CANDIDATE_RADIUS_KM and served.get(airport["code"]):
            nearby.append({
                "code": airport["code"], "name": airport.get("name"), "type": airport.get("type"),
                "distance_km": round(distance_km, 1), "lat": airport["lat"], "lon": airport["lon"],
                "service_level": airport.get("service_level", "unknown"),
            })
    nearby.sort(key=lambda a: a["distance_km"])

    routed = drive_minutes is not None
    minutes = {}
    for a in nearby:
        m = drive_minutes.get(a["code"]) if routed else None
        minutes[a["code"]] = m if m is not None else estimate_drive_minutes(a["distance_km"])
        a["drive_minutes"] = round(minutes[a["code"]], 1)

    score, detail = coverage_score(minutes)
    score = round(score, 1)
    best_code = detail["best_airport"]
    primary = next((a for a in nearby if a["code"] == best_code), None)
    for a in nearby:
        pa = detail["per_airport"].get(a["code"])
        a["nonstop_coverage_pct"] = round(100 * pa["coverage"], 1) if pa else None

    within_plateau = [a for a in nearby if a["drive_minutes"] <= PLATEAU_MIN]
    nearest = nearby[0] if nearby else None
    breakdown = {
        "score": score,
        "primary_airport": {
            "code": primary["code"], "name": primary["name"], "distance_km": primary["distance_km"],
            "drive_minutes": primary["drive_minutes"],
            "type": "International hub" if primary.get("service_level") == "international_hub"
            else "Major hub" if primary.get("type") == "large_airport" else "Regional airport",
        } if primary else None,
        "nearest_airports": nearby[:5],
        "summary": {
            "has_international_hub": any(a["type"] == "large_airport" for a in within_plateau),
            "has_regional_airport": any(a["type"] == "medium_airport" for a in within_plateau),
            "access_level": _get_access_level(score),
            "airport_count": len(within_plateau),
            "nearest_airport_km": nearest["distance_km"] if nearest else None,
            "nearest_airport_minutes": nearest["drive_minutes"] if nearest else None,
            "nonstop_coverage_pct": score,
            "drive_minutes_source": "routed" if routed else "estimated_from_distance",
        },
        "method": {
            "plateau_min": PLATEAU_MIN, "access_overhead_min": ACCESS_OVERHEAD_MIN, "min_per_km": MIN_PER_KM,
            "coverage_year": 2023,
        },
    }
    return score, breakdown, nearby


def get_air_travel_score(lat: float, lon: float, area_type: Optional[str] = None,
                         density: Optional[float] = None,
                         drive_minutes: Optional[Dict[str, float]] = None,
                         place_context=None) -> Tuple[float, Dict]:
    """
    Air travel access (0-100) for a location.

    Args:
        area_type: pre-computed area type (kept for response metadata; the score does not depend on it)
        drive_minutes: optional routed drive minutes by airport code; otherwise minutes are estimated from
            straight-line distance with the fitted line.

    Raises RuntimeError when the airport or coverage data is unavailable, so the pillar shows as no data.
    """
    print("✈️  Analyzing air travel access...")
    score, breakdown, nearby = score_location(lat, lon, drive_minutes)

    from data_sources.place_context import resolve_place_context
    ctx = resolve_place_context(lat, lon, place_context=place_context, area_type=area_type, density=density, need_density=True)
    area_type, density = ctx.area_type, ctx.density
    from data_sources.regional_baselines import regional_baseline_manager
    metro_name = regional_baseline_manager._detect_metro_area(None, lat, lon)
    breakdown["area_classification"] = {
        "density": density,
        "metro_name": metro_name,
        "area_type": area_type,
        "classification_confidence": regional_baseline_manager._get_classification_confidence(density, metro_name),
    }
    breakdown["data_quality"] = assess_pillar_data_quality("air_travel_access", {"airports": nearby}, lat, lon, area_type, density=density)

    if breakdown["primary_airport"]:
        nearest = nearby[0]
        print(f"✅ Air Travel Score: {score:.0f}/100 (nearest {nearest['name']} {nearest['code']}, "
              f"{nearest['drive_minutes']:.0f} min)")
    else:
        print("⚠️  Air Travel Score: 0/100 - no airport with nonstop service within reach")
    return score, breakdown


def _get_access_level(score: float) -> str:
    """Descriptive label for the score (presentation only)."""
    if score >= 90:
        return "Excellent - nearly all busy destinations nonstop"
    if score >= 75:
        return "Very Good - most busy destinations nonstop"
    if score >= 55:
        return "Good - many destinations nonstop"
    if score >= 35:
        return "Fair - limited nonstop reach"
    return "Limited - few nonstop options"
