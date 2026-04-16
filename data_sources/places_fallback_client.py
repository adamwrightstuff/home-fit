"""
Google Places API (New) — nearby search fallback for neighborhood_amenities when OSM completeness is low.

Area-based call policy (caps per location): rural/exurban 1 call; suburban up to 2; urban core up to 4 tiered calls,
with merge, dedupe, and completeness checks per product spec.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Tuple

import requests

from logging_config import get_logger

from data_sources.data_quality import data_quality_manager

from .places_osm_mapping import (
    TIER_PLACE_TYPES,
    included_types_for_nearby_search,
    resolve_tier_and_type_from_google_types,
    tier3_and_tier4_place_types,
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
    """Deprecated: kept for env compatibility; policy no longer uses batch count."""
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


def _classify_places_policy(area_type: Optional[str], density: Optional[float]) -> str:
    """Return policy bucket: rural_exurban, suburban, or urban_core."""
    d = float(density or 0.0)
    if d > 10000 or (area_type or "").lower() == "urban_core":
        return "urban_core"
    at = (area_type or "suburban").lower()
    if at in ("rural", "exurban"):
        return "rural_exurban"
    if at in ("suburban", "urban_residential"):
        return "suburban"
    return "suburban"


def _all_businesses_from_tiers(merged: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for k in ("tier1_daily", "tier2_social", "tier3_culture", "tier4_services"):
        out.extend(merged.get(k) or [])
    return out


def _merged_completeness(
    merged: Dict[str, List[Dict[str, Any]]],
    lat: float,
    lon: float,
    area_type: Optional[str],
) -> float:
    all_businesses = _all_businesses_from_tiers(merged)
    expected = data_quality_manager.get_expected_minimums(lat, lon, area_type or "suburban")
    c, _ = data_quality_manager.assess_data_completeness(
        "neighborhood_amenities",
        {"all_businesses": all_businesses},
        expected,
    )
    return float(c)


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


def _merge_places_into_base(
    base: Dict[str, List[Dict[str, Any]]],
    places: List[Dict[str, Any]],
    center_lat: float,
    center_lon: float,
    include_chains: bool,
) -> Tuple[Dict[str, List[Dict[str, Any]]], int]:
    """Merge raw Places payloads into tier dicts; return (merged, mapped_added)."""
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

    return merged, added


def maybe_augment_business_data_with_places(
    osm_data: Dict[str, List[Dict]],
    center_lat: float,
    center_lon: float,
    radius_m: float,
    include_chains: bool,
    osm_completeness: float,
    *,
    area_type: Optional[str] = None,
    density: Optional[float] = None,
    places_already_augmented: bool = False,
) -> Tuple[Dict[str, List[Dict]], Dict[str, Any]]:
    """
    When OSM amenity completeness is below threshold and Places fallback is enabled,
    run area-based searchNearby calls, merge mapped places into tier lists (deduped).

    Returns (business_data_for_scoring, metadata for API breakdown).
    """
    thr = places_completeness_threshold()
    meta: Dict[str, Any] = {
        "triggered": False,
        "used": False,
        "reason": None,
        "request_count": 0,
        "places_returned": 0,
        "mapped_added": 0,
        "error": None,
        "osm_completeness_before": round(osm_completeness, 4),
        "completeness_before_places": round(osm_completeness, 4),
        "completeness_after_places": round(osm_completeness, 4),
        "completeness_threshold": thr,
        "http_calls_ok": 0,
        "http_calls_attempted": 0,
        "places_calls_made": 0,
        "places_stop_reason": None,
        "places_suburban_second_call": False,
    }

    base = {
        k: list(v)
        for k, v in osm_data.items()
        if k in ("tier1_daily", "tier2_social", "tier3_culture", "tier4_services")
    }

    if places_already_augmented:
        meta["reason"] = "already_augmented"
        return base, meta

    if osm_completeness >= thr:
        meta["reason"] = "completeness_above_threshold"
        return base, meta

    if not places_amenities_fallback_enabled():
        meta["reason"] = "disabled_or_no_api_key"
        meta["triggered"] = True
        return base, meta

    meta["triggered"] = True
    key = _api_key()
    if not key:
        meta["reason"] = "disabled_or_no_api_key"
        meta["error"] = "no_api_key"
        return base, meta

    policy = _classify_places_policy(area_type, density)
    # "Unfiltered" first pass = one request with union of all mapped included types (API requires includedTypes).
    broad_types = list(dict.fromkeys(included_types_for_nearby_search()))
    merged = {k: list(v) for k, v in base.items()}
    calls_made = 0
    total_places_raw = 0
    stop_reason: Optional[str] = None

    def run_one(types_filter: List[str]) -> Optional[List[Dict[str, Any]]]:
        nonlocal calls_made, total_places_raw
        if not types_filter:
            return []
        calls_made += 1
        meta["http_calls_attempted"] = calls_made
        res = _single_search_nearby(key, center_lat, center_lon, float(radius_m), types_filter)
        if res is None:
            meta["http_calls_ok"] = calls_made - 1
            return None
        meta["http_calls_ok"] = calls_made
        total_places_raw += len(res)
        return res

    total_added = 0

    if policy == "rural_exurban":
        raw = run_one(broad_types)
        if raw is None:
            meta["reason"] = "api_error_or_empty"
            meta["error"] = "places_request_failed"
            return base, meta
        merged, a = _merge_places_into_base(merged, raw, center_lat, center_lon, include_chains)
        total_added += a
        c_after = _merged_completeness(merged, center_lat, center_lon, area_type)
        meta["completeness_after_places"] = round(c_after, 4)
        stop_reason = "cap_reached"
        meta["places_calls_made"] = calls_made
        meta["places_stop_reason"] = stop_reason
        meta["request_count"] = calls_made
        meta["places_returned"] = total_places_raw
        meta["mapped_added"] = total_added
        meta["used"] = total_added > 0
        meta["reason"] = "merged" if total_added > 0 else "no_new_mapped_places"
        logger.info(
            "places_policy=rural_exurban places_calls_made=%s places_stop_reason=%s "
            "completeness_before=%s completeness_after=%s",
            meta["places_calls_made"],
            meta["places_stop_reason"],
            meta["completeness_before_places"],
            meta["completeness_after_places"],
        )
        return merged, meta

    if policy == "suburban":
        raw = run_one(broad_types)
        if raw is None:
            meta["reason"] = "api_error_or_empty"
            meta["error"] = "places_request_failed"
            return base, meta
        merged, a = _merge_places_into_base(merged, raw, center_lat, center_lon, include_chains)
        total_added += a
        c_after = _merged_completeness(merged, center_lat, center_lon, area_type)
        meta["completeness_after_places"] = round(c_after, 4)
        if c_after >= thr:
            stop_reason = "threshold_met"
        elif calls_made < 2:
            t34 = tier3_and_tier4_place_types()
            raw2 = run_one(t34)
            meta["places_suburban_second_call"] = True
            logger.info(
                "places_suburban_second_call=1 completeness_after_first=%.4f threshold=%.4f",
                c_after,
                thr,
            )
            if raw2 is not None:
                merged, a2 = _merge_places_into_base(merged, raw2, center_lat, center_lon, include_chains)
                total_added += a2
            c_after = _merged_completeness(merged, center_lat, center_lon, area_type)
            meta["completeness_after_places"] = round(c_after, 4)
            stop_reason = "threshold_met" if c_after >= thr else "cap_reached"
        else:
            stop_reason = "cap_reached"
        meta["places_calls_made"] = calls_made
        meta["places_stop_reason"] = stop_reason
        meta["request_count"] = calls_made
        meta["places_returned"] = total_places_raw
        meta["mapped_added"] = total_added
        meta["used"] = total_added > 0
        meta["reason"] = "merged" if total_added > 0 else "no_new_mapped_places"
        logger.info(
            "places_policy=suburban places_calls_made=%s places_stop_reason=%s "
            "places_suburban_second_call=%s completeness_before=%s completeness_after=%s",
            meta["places_calls_made"],
            meta["places_stop_reason"],
            meta["places_suburban_second_call"],
            meta["completeness_before_places"],
            meta["completeness_after_places"],
        )
        return merged, meta

    # urban_core — up to 4 tier calls, stop when C >= threshold
    tier_order = ["tier1", "tier2", "tier3", "tier4"]
    for tk in tier_order:
        if calls_made >= 4:
            stop_reason = "cap_reached"
            break
        types_filter = TIER_PLACE_TYPES.get(tk, [])
        raw = run_one(types_filter)
        if raw is None:
            meta["reason"] = "api_error_or_empty"
            meta["error"] = "places_request_failed"
            meta["places_calls_made"] = calls_made
            meta["places_stop_reason"] = stop_reason or "api_error"
            meta["mapped_added"] = total_added
            meta["used"] = total_added > 0
            return merged, meta
        merged, a = _merge_places_into_base(merged, raw, center_lat, center_lon, include_chains)
        total_added += a
        c_after = _merged_completeness(merged, center_lat, center_lon, area_type)
        meta["completeness_after_places"] = round(c_after, 4)
        logger.info(
            "places_urban_tier=%s calls_so_far=%s completeness=%.4f threshold=%.4f",
            tk,
            calls_made,
            c_after,
            thr,
        )
        if c_after >= thr:
            stop_reason = "threshold_met"
            break
    else:
        stop_reason = stop_reason or "cap_reached"

    if stop_reason is None:
        stop_reason = "cap_reached"

    meta["places_calls_made"] = calls_made
    meta["places_stop_reason"] = stop_reason
    meta["request_count"] = calls_made
    meta["places_returned"] = total_places_raw
    meta["mapped_added"] = total_added
    meta["used"] = total_added > 0
    meta["reason"] = "merged" if total_added > 0 else "no_new_mapped_places"
    logger.info(
        "places_policy=urban_core places_calls_made=%s places_stop_reason=%s "
        "completeness_before=%s completeness_after=%s",
        meta["places_calls_made"],
        meta["places_stop_reason"],
        meta["completeness_before_places"],
        meta["completeness_after_places"],
    )
    return merged, meta
