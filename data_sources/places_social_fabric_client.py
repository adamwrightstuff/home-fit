"""
Google Places API (New) — civic gathering fallback for Social Fabric.

Maps Places types to OSM-shaped civic nodes (library, community_centre, place_of_worship,
townhall, community_garden); dedupes by Places id and near-duplicate lat/lon.

Triggers (aligned with neighborhood_amenities Places policy):
- Overpass returns source_status error; or
- OSM succeeded but civic completeness / count vs expected minimum is low (thin OSM).
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


def places_sf_completeness_threshold() -> float:
    """Match NA default; override with HOMEFIT_PLACES_SF_COMPLETENESS_THRESHOLD or HOMEFIT_PLACES_COMPLETENESS_THRESHOLD."""
    raw = (os.getenv("HOMEFIT_PLACES_SF_COMPLETENESS_THRESHOLD") or "").strip()
    if not raw:
        raw = (os.getenv("HOMEFIT_PLACES_COMPLETENESS_THRESHOLD") or "").strip()
    if not raw:
        raw = "0.6"
    try:
        return float(raw)
    except ValueError:
        return 0.6


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


def _places_api_to_nodes(
    places: List[Dict[str, Any]],
    center_lat: float,
    center_lon: float,
) -> Tuple[List[Dict[str, Any]], int]:
    """Map Places API results to civic node dicts; dedupe by place id."""
    nodes: List[Dict[str, Any]] = []
    seen_ids: Set[str] = set()
    raw_skipped = 0

    for p in places:
        if not isinstance(p, dict):
            continue
        types = p.get("types")
        if not isinstance(types, list):
            types = []
        node_type = _classify_civic_node_type(types)
        if not node_type:
            raw_skipped += 1
            continue
        loc = p.get("location") or {}
        plat = loc.get("latitude")
        plon = loc.get("longitude")
        if plat is None or plon is None:
            raw_skipped += 1
            continue
        plat_f, plon_f = float(plat), float(plon)
        pid = _place_id(p)
        if pid and pid in seen_ids:
            continue
        if pid:
            seen_ids.add(pid)
        name = _place_display_name(p)
        dist_m = round(haversine_distance(center_lat, center_lon, plat_f, plon_f), 1)
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

    return nodes, raw_skipped


def _node_key(n: Dict[str, Any]) -> Tuple[float, float, str]:
    lat = float(n.get("lat") or 0.0)
    lon = float(n.get("lon") or 0.0)
    typ = str(n.get("type") or "")
    return (round(lat, 5), round(lon, 5), typ)


def _merge_osm_and_places_nodes(
    osm_nodes: List[Dict[str, Any]],
    places_nodes: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Keep OSM nodes; append Places nodes that are not near-duplicates."""
    seen: Set[Tuple[float, float, str]] = set()
    out: List[Dict[str, Any]] = []
    for n in osm_nodes:
        if not isinstance(n, dict):
            continue
        k = _node_key(n)
        seen.add(k)
        out.append(n)
    for n in places_nodes:
        k = _node_key(n)
        if k in seen:
            continue
        pid = n.get("place_id")
        if pid and any(x.get("place_id") == pid for x in out):
            continue
        seen.add(k)
        out.append(n)
    return out


def maybe_augment_civic_nodes_with_places(
    civic: Dict[str, Any],
    lat: float,
    lon: float,
    radius_m: int,
    *,
    osm_completeness: float = 1.0,
    civic_min_expected: int = 3,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Optionally fill or augment civic nodes from Google Places searchNearby.

    Triggers: Overpass error; or low OSM completeness vs expected civic count; or count thin
    (mirrors neighborhood_amenities Places policy).

    Returns (civic_dict_for_scoring, metadata).
    """
    meta: Dict[str, Any] = {
        "used": False,
        "reason": "skipped",
        "trigger": None,
        "http_ok": False,
        "http_calls": 0,
        "places_returned": 0,
        "nodes_added": 0,
        "osm_completeness_before": round(osm_completeness, 4),
        "completeness_threshold": places_sf_completeness_threshold(),
        "civic_min_expected": int(civic_min_expected),
    }

    osm_cs = civic.get("source_status")
    meta["osm_source_status"] = osm_cs

    existing = [n for n in (civic.get("nodes") or []) if isinstance(n, dict)]
    n_osm = len(existing)
    thr = places_sf_completeness_threshold()
    min_floor = max(1, int(civic_min_expected))
    min_count_thin = max(2, int(round(min_floor * 0.45)))
    count_too_thin = n_osm < min_count_thin

    should_try_places = False
    trigger: Optional[str] = None

    if osm_cs == "error":
        should_try_places = True
        trigger = "osm_overpass_error"
    elif osm_cs in ("ok", "empty"):
        # Mirror NA: skip only when completeness >= threshold and count is not thin.
        if osm_completeness >= thr and not count_too_thin:
            should_try_places = False
        else:
            should_try_places = True
            if osm_completeness >= thr and count_too_thin:
                trigger = "completeness_high_but_count_thin_try_places"
            elif osm_completeness < thr and count_too_thin:
                trigger = "low_completeness_and_thin_count"
            else:
                trigger = "low_osm_completeness"

    if not should_try_places:
        meta["reason"] = "completeness_above_threshold" if osm_cs in ("ok", "empty") else "osm_not_error"
        return civic, meta

    meta["trigger"] = trigger

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
    meta["reason"] = trigger or "places"

    places_nodes, _raw_skip = _places_api_to_nodes(places, lat, lon)
    meta["nodes_added"] = len(places_nodes)

    out = dict(civic)

    if osm_cs == "error":
        out["osm_source_status"] = "error"
        out["places_civic_fallback"] = meta
        out["nodes"] = places_nodes
        out["source_status"] = "ok" if places_nodes else "empty"
        out["error"] = None
        return out, meta

    # Successful Overpass but thin data: merge OSM + Places nodes.
    merged = _merge_osm_and_places_nodes(existing, places_nodes)
    meta["nodes_added"] = max(0, len(merged) - n_osm)
    preserved = osm_cs or "ok"
    out["osm_source_status"] = preserved
    out["places_civic_fallback"] = meta
    out["nodes"] = merged
    out["source_status"] = "ok" if merged else ("empty" if osm_cs == "empty" else "ok")
    if "error" in out:
        out["error"] = None
    return out, meta
