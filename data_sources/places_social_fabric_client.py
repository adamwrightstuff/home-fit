"""
Google Places API (New) — civic gathering fallback for Social Fabric when OSM/Overpass fails.

Maps Places types to OSM-shaped civic nodes (library, community_centre, place_of_worship,
townhall, community_garden); dedupes by Places id. Trigger: Overpass returns source_status error only.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Set, Tuple

import requests

from logging_config import get_logger

from data_sources.utils import haversine_distance

logger = get_logger(__name__)

PLACES_NEARBY_URL = "https://places.googleapis.com/v1/places:searchNearby"

# Google primary types that correspond to civic third places (non-commercial).
CIVIC_INCLUDED_TYPES: List[str] = [
    "library",
    "church",
    "mosque",
    "synagogue",
    "hindu_temple",
    "community_center",
    "city_hall",
    "local_government_office",
    "botanical_garden",
]

_WORSHIP_TYPES = frozenset(
    {"church", "mosque", "synagogue", "hindu_temple", "buddhist_temple"}
)


def _api_key() -> Optional[str]:
    return (os.getenv("GOOGLE_PLACES_API_KEY") or os.getenv("HOMEFIT_GOOGLE_PLACES_API_KEY") or "").strip() or None


def places_social_fabric_fallback_enabled() -> bool:
    if not _api_key():
        return False
    raw = (os.getenv("HOMEFIT_PLACES_SF_FALLBACK_ENABLED") or "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _classify_civic_node_type(types: Optional[List[str]]) -> Optional[str]:
    """
    Map Google `types` to OSM civic `type` strings used by social_fabric / query_civic_nodes.
    """
    if not types or not isinstance(types, list):
        return None
    ts = set(types)
    if "library" in ts:
        return "library"
    if "community_center" in ts:
        return "community_centre"
    if ts & _WORSHIP_TYPES:
        return "place_of_worship"
    if "city_hall" in ts or "local_government_office" in ts:
        return "townhall"
    if "botanical_garden" in ts:
        return "community_garden"
    return None


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


def _place_display_name(place: Dict[str, Any]) -> Optional[str]:
    dn = place.get("displayName") or {}
    text = (dn.get("text") or "").strip()
    return text or None


def _search_nearby_civic(
    key: str,
    lat: float,
    lon: float,
    radius_m: float,
) -> Optional[List[Dict[str, Any]]]:
    body = {
        "locationRestriction": {
            "circle": {
                "center": {"latitude": lat, "longitude": lon},
                "radius": min(float(radius_m), 50000.0),
            }
        },
        "includedTypes": CIVIC_INCLUDED_TYPES,
        "maxResultCount": 20,
        "rankPreference": "DISTANCE",
    }
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": key,
        "X-Goog-FieldMask": "places.id,places.name,places.displayName,places.location,places.types",
    }
    try:
        resp = requests.post(PLACES_NEARBY_URL, json=body, headers=headers, timeout=25)
        if resp.status_code != 200:
            logger.warning(
                "SF Places searchNearby failed: status=%s body=%s",
                resp.status_code,
                (resp.text or "")[:500],
            )
            return None
        data = resp.json()
        if not isinstance(data, dict):
            return None
        places = data.get("places")
        return places if isinstance(places, list) else []
    except requests.RequestException as e:
        logger.warning("SF Places searchNearby request error: %s", e)
        return None


def maybe_augment_civic_nodes_with_places(
    civic: Dict[str, Any],
    lat: float,
    lon: float,
    radius_m: int,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    When OSM civic query failed (Overpass error), optionally fill nodes from Google Places
    searchNearby (same radius). Returns (civic_dict_for_scoring, metadata).
    """
    meta: Dict[str, Any] = {
        "used": False,
        "reason": "skipped",
        "http_ok": False,
        "http_calls": 0,
        "places_returned": 0,
        "nodes_added": 0,
    }

    osm_cs = civic.get("source_status")
    meta["osm_source_status"] = osm_cs

    if osm_cs != "error":
        meta["reason"] = "osm_not_error"
        return civic, meta

    if not places_social_fabric_fallback_enabled():
        meta["reason"] = "disabled_or_no_key"
        return civic, meta

    key = _api_key()
    if not key:
        meta["reason"] = "disabled_or_no_key"
        return civic, meta

    places = _search_nearby_civic(key, lat, lon, float(radius_m))
    meta["http_calls"] = 1

    if places is None:
        meta["reason"] = "places_http_error"
        return civic, meta

    meta["http_ok"] = True
    meta["places_returned"] = len(places)
    meta["used"] = True
    meta["reason"] = "osm_overpass_error"

    nodes: List[Dict[str, Any]] = []
    seen_ids: Set[str] = set()

    for p in places:
        if not isinstance(p, dict):
            continue
        types = p.get("types")
        if not isinstance(types, list):
            types = []
        node_type = _classify_civic_node_type(types)
        if not node_type:
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
        if pid:
            seen_ids.add(pid)
        name = _place_display_name(p)
        dist_m = round(haversine_distance(lat, lon, plat_f, plon_f), 1)
        nodes.append(
            {
                "name": name,
                "lat": plat_f,
                "lon": plon_f,
                "distance_m": dist_m,
                "type": node_type,
                "place_id": pid,
                "source": "google_places",
            }
        )

    meta["nodes_added"] = len(nodes)

    out = dict(civic)
    out["osm_source_status"] = "error"
    out["places_civic_fallback"] = meta
    out["nodes"] = nodes
    out["source_status"] = "ok" if nodes else "empty"
    out["error"] = None

    return out, meta
