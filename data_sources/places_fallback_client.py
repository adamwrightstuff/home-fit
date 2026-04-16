"""
Google Places API (New) — nearby search fallback for neighborhood_amenities when OSM completeness is low.

Uses multiple searchNearby calls (default: five batches of includedTypes) per (lat, lon, radius);
each call may return up to 20 places; results are merged, deduped by place id, and cached.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Tuple

import requests

from logging_config import get_logger

from .cache import CACHE_TTL, cached
from .places_osm_mapping import (
    included_type_batches_for_nearby_search,
    resolve_tier_and_type_from_google_types,
)
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


def places_nearby_batch_count() -> int:
    """How many type batches to run (1–10). Default 5."""
    try:
        n = int(os.getenv("HOMEFIT_PLACES_NEARBY_BATCH_COUNT", "5"))
        return max(1, min(10, n))
    except ValueError:
        return 5


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


def _place_dedupe_key(place: Dict[str, Any]) -> Optional[str]:
    raw_id = place.get("id")
    if raw_id is not None and str(raw_id).strip():
        return str(raw_id)
    return _normalize_place_id(place.get("name"))


def _single_search_nearby(
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
                "Places searchNearby failed: status=%s types=%s body=%s",
                resp.status_code,
                included_types[:5],
                (resp.text or "")[:500],
            )
            return None
        data = resp.json()
        if not isinstance(data, dict):
            return None
        places = data.get("places")
        return places if isinstance(places, list) else []
    except requests.RequestException as e:
        logger.warning("Places searchNearby request error: %s", e)
        return None


@cached(ttl_seconds=CACHE_TTL.get("places_nearby", 2 * 3600))
def _fetch_places_nearby_batched_merged(
    lat: float, lon: float, radius_m: float
) -> Optional[Dict[str, Any]]:
    """
    Run N searchNearby calls (disjoint type batches), merge and dedupe by place id.

    Returns {"places": [...], "http_calls_ok": int, "http_calls_attempted": int} or None if no API key.
    Returns None if every HTTP call fails.
    """
    key = _api_key()
    if not key:
        return None

    batches = included_type_batches_for_nearby_search()
    max_batches = places_nearby_batch_count()
    batches = batches[:max_batches]

    merged_by_key: Dict[str, Dict[str, Any]] = {}
    http_ok = 0
    attempted = 0

    for included_types in batches:
        attempted += 1
        places = _single_search_nearby(key, lat, lon, radius_m, included_types)
        if places is None:
            continue
        http_ok += 1
        for p in places:
            if not isinstance(p, dict):
                continue
            dk = _place_dedupe_key(p)
            if not dk:
                continue
            if dk not in merged_by_key:
                merged_by_key[dk] = p

    if http_ok == 0:
        return None

    return {
        "places": list(merged_by_key.values()),
        "http_calls_ok": http_ok,
        "http_calls_attempted": attempted,
    }


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
    run batched searchNearby calls and merge mapped places into tier lists (deduped).

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
        "http_calls_ok": 0,
        "http_calls_attempted": 0,
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

    raw = _fetch_places_nearby_batched_merged(center_lat, center_lon, float(radius_m))

    if raw is None:
        meta["reason"] = "api_error_or_empty"
        meta["error"] = "places_request_failed"
        return base, meta

    meta["http_calls_ok"] = int(raw.get("http_calls_ok") or 0)
    meta["http_calls_attempted"] = int(raw.get("http_calls_attempted") or 0)
    meta["request_count"] = meta["http_calls_ok"]

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
