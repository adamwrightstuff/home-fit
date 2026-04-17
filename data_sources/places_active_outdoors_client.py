"""
Google Places API (New) — supplemental POIs for Active Outdoors v2 when OSM lists are thin.

Local: parks / playgrounds (and aligned types) near the home point.
Regional: beaches, campgrounds, RV parks within the regional radius (no marinas).

Uses searchNearby with includedTypes; merges into existing OSM-shaped lists in place.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple

import requests

from logging_config import get_logger

from data_sources.utils import haversine_distance

logger = get_logger(__name__)

PLACES_NEARBY_URL = "https://places.googleapis.com/v1/places:searchNearby"

_PARK_TYPES = frozenset(
    {"park", "national_park", "botanical_garden", "dog_park", "golf_course"}
)
_CAMP_TYPES = frozenset({"campground", "rv_park"})


def _classify_local(types: List[str]) -> Optional[str]:
    """Pick one AO-local category from Google types (order-independent)."""
    if not isinstance(types, list):
        return None
    if "marina" in types:
        return None
    if "playground" in types:
        return "playground"
    for t in ("national_park", "botanical_garden", "dog_park", "golf_course", "park"):
        if t in types:
            return t
    return None


def _classify_regional(types: List[str]) -> Optional[Tuple[str, str]]:
    """
    Returns (bucket, subtype) where bucket is swim|camp, subtype is AO feature type
    (beach / campsite with places_subtype for rv vs campground).
    """
    if not isinstance(types, list):
        return None
    if "marina" in types:
        return None
    if "beach" in types:
        return ("swim", "beach")
    if "campground" in types:
        return ("camp", "campground")
    if "rv_park" in types:
        return ("camp", "rv_park")
    return None


def _api_key() -> Optional[str]:
    return (os.getenv("GOOGLE_PLACES_API_KEY") or os.getenv("HOMEFIT_GOOGLE_PLACES_API_KEY") or "").strip() or None


def places_ao_fallback_enabled() -> bool:
    if not _api_key():
        return False
    raw = (os.getenv("HOMEFIT_PLACES_AO_FALLBACK_ENABLED") or "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _normalize_place_id(resource_name: Optional[str]) -> Optional[str]:
    if not resource_name:
        return None
    if resource_name.startswith("places/"):
        return resource_name[len("places/") :]
    return resource_name


def _place_id(place: Dict[str, Any]) -> Optional[str]:
    raw = place.get("id")
    if raw is not None and str(raw).strip():
        return str(raw)
    return _normalize_place_id(place.get("name"))


def _search_nearby(
    key: str,
    lat: float,
    lon: float,
    radius_m: float,
    included_types: List[str],
) -> Optional[List[Dict[str, Any]]]:
    if not included_types:
        return []
    body = {
        "locationRestriction": {
            "circle": {
                "center": {"latitude": lat, "longitude": lon},
                "radius": min(float(radius_m), 50000.0),
            }
        },
        "includedTypes": included_types,
        "maxResultCount": 20,
        "rankPreference": "DISTANCE",
    }
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": key,
        "X-Goog-FieldMask": "places.id,places.name,places.displayName,places.location,places.types",
    }
    try:
        resp = requests.post(PLACES_NEARBY_URL, json=body, headers=headers, timeout=20)
        if resp.status_code != 200:
            logger.warning(
                "AO Places searchNearby failed: status=%s types=%s body=%s",
                resp.status_code,
                included_types[:8],
                (resp.text or "")[:500],
            )
            return None
        data = resp.json()
        if not isinstance(data, dict):
            return None
        places = data.get("places")
        return places if isinstance(places, list) else []
    except requests.RequestException as e:
        logger.warning("AO Places searchNearby request error: %s", e)
        return None


def _min_dist_to_points(plat: float, plon: float, features: List[Dict[str, Any]], near_m: float) -> bool:
    """True if any feature has lat/lon within near_m meters."""
    for f in features:
        flat, flon = f.get("lat"), f.get("lon")
        if flat is None or flon is None:
            continue
        d = haversine_distance(plat, plon, float(flat), float(flon))
        if d < near_m:
            return True
    return False


def _place_display_name(place: Dict[str, Any]) -> Optional[str]:
    dn = place.get("displayName") or {}
    text = (dn.get("text") or "").strip()
    return text or None


def _merge_local_places(
    places: List[Dict[str, Any]],
    center_lat: float,
    center_lon: float,
    parks: List[Dict[str, Any]],
    playgrounds: List[Dict[str, Any]],
    near_dup_m: float,
    seen_ids: Set[str],
) -> int:
    added = 0
    for p in places:
        if not isinstance(p, dict):
            continue
        types = p.get("types")
        if not isinstance(types, list):
            types = []
        gtype = _classify_local(types)
        if gtype is None:
            continue
        loc = p.get("location") or {}
        plat = loc.get("latitude")
        plon = loc.get("longitude")
        if plat is None or plon is None:
            continue
        plat_f, plon_f = float(plat), float(plon)
        pid = _place_id(p)
        if pid and pid in seen_ids:
            continue
        name = _place_display_name(p)
        if not name:
            continue
        dist_m = round(haversine_distance(center_lat, center_lon, plat_f, plon_f), 0)

        if gtype == "playground":
            if _min_dist_to_points(plat_f, plon_f, playgrounds, near_dup_m):
                continue
            if _min_dist_to_points(plat_f, plon_f, parks, near_dup_m):
                continue
            row = {
                "name": name,
                "type": "playground",
                "lat": plat_f,
                "lon": plon_f,
                "distance_m": dist_m,
                "source": "google_places",
                "google_place_id": pid,
            }
            playgrounds.append(row)
            if pid:
                seen_ids.add(pid)
            added += 1
            continue

        if gtype in _PARK_TYPES:
            if _min_dist_to_points(plat_f, plon_f, parks, near_dup_m):
                continue
            if _min_dist_to_points(plat_f, plon_f, playgrounds, near_dup_m):
                continue
            row = {
                "name": name,
                "type": gtype,
                "lat": plat_f,
                "lon": plon_f,
                "distance_m": dist_m,
                "area_sqm": 0,
                "source": "google_places",
                "google_place_id": pid,
            }
            parks.append(row)
            if pid:
                seen_ids.add(pid)
            added += 1

    return added


def _merge_regional_places(
    places: List[Dict[str, Any]],
    center_lat: float,
    center_lon: float,
    swimming: List[Dict[str, Any]],
    camping: List[Dict[str, Any]],
    seen_ids: Set[str],
) -> Tuple[int, int]:
    swim_add = camp_add = 0
    sigs: Set[Tuple[float, float, str]] = set()

    def _sig(lat: float, lon: float, name: str) -> Tuple[float, float, str]:
        return (
            round(lat, 5),
            round(lon, 5),
            re.sub(r"\s+", " ", name.lower())[:48],
        )

    for p in places:
        if not isinstance(p, dict):
            continue
        types = p.get("types")
        if not isinstance(types, list):
            types = []
        cl = _classify_regional(types)
        if cl is None:
            continue
        bucket, subtype = cl
        loc = p.get("location") or {}
        plat = loc.get("latitude")
        plon = loc.get("longitude")
        if plat is None or plon is None:
            continue
        plat_f, plon_f = float(plat), float(plon)
        pid = _place_id(p)
        if pid and pid in seen_ids:
            continue
        name = _place_display_name(p)
        if not name:
            continue
        dist_m = round(haversine_distance(center_lat, center_lon, plat_f, plon_f), 0)
        sg = _sig(plat_f, plon_f, name)
        if sg in sigs:
            continue

        if bucket == "swim":
            row = {
                "type": "beach",
                "name": name,
                "distance_m": dist_m,
                "lat": plat_f,
                "lon": plon_f,
                "source": "google_places",
                "google_place_id": pid,
            }
            swimming.append(row)
            sigs.add(sg)
            if pid:
                seen_ids.add(pid)
            swim_add += 1
        elif bucket == "camp":
            row = {
                "type": "campsite",
                "name": name,
                "distance_m": dist_m,
                "lat": plat_f,
                "lon": plon_f,
                "source": "google_places",
                "google_place_id": pid,
                "places_subtype": subtype,
            }
            camping.append(row)
            sigs.add(sg)
            if pid:
                seen_ids.add(pid)
            camp_add += 1

    return swim_add, camp_add


def maybe_augment_active_outdoors_with_places(
    lat: float,
    lon: float,
    *,
    local_radius_m: int,
    regional_radius_m: int,
    parks: List[Dict[str, Any]],
    playgrounds: List[Dict[str, Any]],
    swimming: List[Dict[str, Any]],
    camping: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Optionally merge Google Places POIs into AO lists. Lists are mutated in place.

    Returns metadata for logging / API breakdown (no PII beyond counts).
    """
    meta: Dict[str, Any] = {
        "used": False,
        "triggered": False,
        "reason": "disabled_or_no_key",
        "http_calls": 0,
        "local_added": 0,
        "regional_swim_added": 0,
        "regional_camp_added": 0,
    }

    if not places_ao_fallback_enabled():
        meta["reason"] = "disabled_or_no_key"
        return meta

    key = _api_key()
    if not key:
        meta["reason"] = "disabled_or_no_key"
        return meta

    local_lt = max(0, _int_env("HOMEFIT_PLACES_AO_LOCAL_TRIGGER_LT", 3))
    swim_lt = max(0, _int_env("HOMEFIT_PLACES_AO_REGIONAL_SWIM_LT", 2))
    camp_lt = max(0, _int_env("HOMEFIT_PLACES_AO_REGIONAL_CAMP_LT", 1))
    max_calls = max(1, _int_env("HOMEFIT_PLACES_AO_MAX_HTTP_CALLS", 3))
    near_dup_m = float(_int_env("HOMEFIT_PLACES_AO_NEAR_DUP_M", 85))

    n_local = len(parks) + len(playgrounds)
    need_local = n_local < local_lt

    need_swim = len(swimming) < swim_lt
    need_camp = len(camping) < camp_lt
    need_regional = need_swim or need_camp

    if not need_local and not need_regional:
        meta["reason"] = "osm_counts_sufficient"
        return meta

    meta["triggered"] = True
    meta["reason"] = "thin_osm_signal"
    seen_ids: Set[str] = set()
    calls = 0

    if need_local and calls < max_calls:
        included = [
            "park",
            "playground",
            "national_park",
            "botanical_garden",
            "dog_park",
            "golf_course",
        ]
        raw = _search_nearby(key, lat, lon, float(local_radius_m), included)
        calls += 1
        meta["http_calls"] = calls
        if raw is not None:
            meta["local_added"] = _merge_local_places(
                raw, lat, lon, parks, playgrounds, near_dup_m, seen_ids
            )

    if need_regional and calls < max_calls:
        included: List[str] = []
        if need_swim:
            included.append("beach")
        if need_camp:
            included.extend(["campground", "rv_park"])
        # De-dupe type list for API
        included = list(dict.fromkeys(included))
        raw = _search_nearby(key, lat, lon, float(regional_radius_m), included)
        calls += 1
        meta["http_calls"] = calls
        if raw is not None:
            sa, ca = _merge_regional_places(raw, lat, lon, swimming, camping, seen_ids)
            meta["regional_swim_added"] = sa
            meta["regional_camp_added"] = ca

    meta["used"] = meta["http_calls"] > 0
    return meta
