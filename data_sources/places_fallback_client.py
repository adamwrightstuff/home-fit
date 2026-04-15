"""
Google Places API (New) — nearby search fallback for neighborhood_amenities when OSM completeness is low.

Uses one searchNearby call per (lat, lon, radius) with multiple includedTypes; results are cached.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Tuple

import requests

from logging_config import get_logger

from .cache import CACHE_TTL, cached
from .places_osm_mapping import included_types_for_nearby_search, resolve_tier_and_type_from_google_types
from .utils import haversine_distance

logger = get_logger(__name__)

PLACES_NEARBY_URL = "https://places.googleapis.com/v1/places:searchNearby"

# Substring match on display name (lowercase) — mirrors OSM brand filtering intent for Places.
_CHAIN_NAME_SUBSTRINGS = frozenset(
    {
        "starbucks",
        "dunkin",
        "mcdonald",
        "burger king",
        "wendy",
        "subway",
        "chipotle",
        "taco bell",
        "kfc",
        "popeyes",
        "domino",
        "pizza hut",
        "7-eleven",
        "7 eleven",
        "walgreens",
        "cvs ",
        " cvs",
        "rite aid",
        "target",
        "walmart",
        "whole foods",
        "trader joe",
        "costco",
        "sam's club",
        "panera",
        "dunkin'",
    }
)


def _api_key() -> Optional[str]:
    return (os.getenv("GOOGLE_PLACES_API_KEY") or os.getenv("HOMEFIT_GOOGLE_PLACES_API_KEY") or "").strip() or None


def places_amenities_fallback_enabled() -> bool:
    if not _api_key():
        return False
    raw = (os.getenv("HOMEFIT_PLACES_FALLBACK_ENABLED") or "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def places_completeness_threshold() -> float:
    try:
        return float(os.getenv("HOMEFIT_PLACES_COMPLETENESS_THRESHOLD", "0.6"))
    except ValueError:
        return 0.6


def _is_likely_chain_name(name: Optional[str]) -> bool:
    if not name:
        return False
    lower = name.lower()
    return any(s in lower for s in _CHAIN_NAME_SUBSTRINGS)


def _normalize_place_id(resource_name: Optional[str]) -> Optional[str]:
    if not resource_name:
        return None
    if resource_name.startswith("places/"):
        return resource_name[len("places/") :]
    return resource_name


@cached(ttl_seconds=CACHE_TTL.get("places_nearby", 2 * 3600))
def _fetch_places_nearby_raw(
    lat: float, lon: float, radius_m: float
) -> Optional[Dict[str, Any]]:
    """
    Returns API JSON dict with key "places" or None on failure.
    Cached by lat/lon/radius.
    """
    key = _api_key()
    if not key:
        return None

    body = {
        "locationRestriction": {
            "circle": {
                "center": {"latitude": lat, "longitude": lon},
                "radius": min(float(radius_m), 50000.0),
            }
        },
        "includedTypes": included_types_for_nearby_search(),
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
                "Places searchNearby failed: status=%s body=%s",
                resp.status_code,
                (resp.text or "")[:500],
            )
            return None
        data = resp.json()
        if not isinstance(data, dict):
            return None
        return data
    except requests.RequestException as e:
        logger.warning("Places searchNearby request error: %s", e)
        return None


def place_json_to_business(
    place: Dict[str, Any], center_lat: float, center_lon: float, include_chains: bool
) -> Optional[Dict[str, Any]]:
    """Convert one Places API place object to OSM-shaped business dict, or None if skipped."""
    loc = place.get("location") or {}
    plat = loc.get("latitude")
    plon = loc.get("longitude")
    if plat is None or plon is None:
        return None

    dn = place.get("displayName") or {}
    name = (dn.get("text") or "").strip() or None
    if not name:
        return None

    if not include_chains and _is_likely_chain_name(name):
        return None

    types = place.get("types")
    if not isinstance(types, list):
        types = []
    resolved = resolve_tier_and_type_from_google_types(types)
    if not resolved:
        return None

    tier_key, biz_type = resolved
    distance_m = round(haversine_distance(center_lat, center_lon, float(plat), float(plon)), 0)

    raw_id = place.get("id")
    pid = str(raw_id) if raw_id is not None else _normalize_place_id(place.get("name"))

    return {
        "name": name,
        "lat": float(plat),
        "lon": float(plon),
        "distance_m": distance_m,
        "type": biz_type,
        "shop": None,
        "leisure": None,
        "amenity": None,
        "source": "google_places",
        "google_place_id": pid,
        "_tier_key": tier_key,
    }


def maybe_augment_business_data_with_places(
    osm_data: Dict[str, List[Dict]],
    center_lat: float,
    center_lon: float,
    radius_m: float,
    include_chains: bool,
    osm_completeness: float,
) -> Tuple[Dict[str, List[Dict]], Dict[str, Any]]:
    """
    When OSM amenity completeness is below threshold and Places fallback is enabled,
    run one searchNearby and merge mapped places into tier lists (deduped).

    Returns (business_data_for_scoring, metadata for API breakdown).
    """
    meta: Dict[str, Any] = {
        "triggered": False,
        "used": False,
        "reason": None,
        "request_count": 0,
        "places_returned": 0,
        "mapped_added": 0,
        "error": None,
        "osm_completeness_before": round(osm_completeness, 4),
        "completeness_threshold": places_completeness_threshold(),
    }

    base = {
        k: list(v)
        for k, v in osm_data.items()
        if k in ("tier1_daily", "tier2_social", "tier3_culture", "tier4_services")
    }

    thr = places_completeness_threshold()
    if osm_completeness >= thr:
        meta["reason"] = "completeness_above_threshold"
        return base, meta

    if not places_amenities_fallback_enabled():
        meta["reason"] = "disabled_or_no_api_key"
        meta["triggered"] = True
        return base, meta

    meta["triggered"] = True

    raw = _fetch_places_nearby_raw(center_lat, center_lon, float(radius_m))
    meta["request_count"] = 1

    if raw is None:
        meta["reason"] = "api_error_or_empty"
        meta["error"] = "places_request_failed"
        return base, meta

    places = raw.get("places")
    if not isinstance(places, list):
        meta["reason"] = "invalid_response"
        return base, meta

    meta["places_returned"] = len(places)

    merged = {k: list(v) for k, v in base.items()}

    def _sig(b: Dict[str, Any]) -> Tuple[float, float, str]:
        return (
            round(float(b["lat"]), 5),
            round(float(b["lon"]), 5),
            re.sub(r"\s+", " ", (b.get("name") or "").lower())[:48],
        )

    sigs: set = set()
    for tier in merged.values():
        for b in tier:
            sigs.add(_sig(b))

    added = 0
    for p in places:
        if not isinstance(p, dict):
            continue
        biz = place_json_to_business(p, center_lat, center_lon, include_chains)
        if not biz:
            continue
        tk = biz.pop("_tier_key", None)
        if tk not in merged:
            continue
        if _sig(biz) in sigs:
            continue
        sigs.add(_sig(biz))
        merged[tk].append(biz)
        added += 1

    meta["mapped_added"] = added
    meta["used"] = added > 0
    meta["reason"] = "merged" if added > 0 else "no_new_mapped_places"
    return merged, meta
