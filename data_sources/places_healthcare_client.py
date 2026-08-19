"""
Google Places API (New) — supplemental POIs for Healthcare Access when OSM data is thin.

Queries hospitals, pharmacies, urgent care, clinics, and doctors near the scoring point.
Merges into existing OSM-shaped lists in place.

Policy:
- Runs only when OSM counts are below thresholds, the feature flag is on, and a key is present.
- When Overpass hard-failed (query_failed=True), blocked unless HOMEFIT_PLACES_HC_ON_OSMDOWN is set.
- Trustworthy empty OSM (zero features returned, not an error) still allows thin-signal Places.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Set

import requests

from logging_config import get_logger
from data_sources.places_env import google_places_api_key, places_hc_fallback_enabled as _env_enabled
from data_sources.utils import haversine_distance

logger = get_logger(__name__)

PLACES_NEARBY_URL = "https://places.googleapis.com/v1/places:searchNearby"

_HOSPITAL_TYPES = frozenset({"hospital"})
_PHARMACY_TYPES = frozenset({"pharmacy", "drugstore"})
_URGENT_CARE_TYPES = frozenset({"urgent_care_facility"})
_DOCTOR_TYPES = frozenset({"doctor", "dentist", "physiotherapist", "optometrist"})
_CLINIC_TYPES = frozenset({"medical_lab"})


def _env_truthy(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in ("1", "true", "yes", "on")


def _classify_hc(types: List[str]) -> Optional[str]:
    if not isinstance(types, list):
        return None
    if any(t in _HOSPITAL_TYPES for t in types):
        return "hospital"
    if any(t in _URGENT_CARE_TYPES for t in types):
        return "urgent_care"
    if any(t in _PHARMACY_TYPES for t in types):
        return "pharmacy"
    if any(t in _DOCTOR_TYPES for t in types):
        return "doctor"
    if any(t in _CLINIC_TYPES for t in types):
        return "clinic"
    return None


def _place_id(place: Dict[str, Any]) -> Optional[str]:
    raw = place.get("id")
    if raw and str(raw).strip():
        return str(raw)
    name = place.get("name") or ""
    if name.startswith("places/"):
        return name[len("places/"):]
    return None


def _place_display_name(place: Dict[str, Any]) -> Optional[str]:
    dn = place.get("displayName") or {}
    return (dn.get("text") or "").strip() or None


def _search_nearby(
    key: str,
    lat: float,
    lon: float,
    radius_m: float,
    included_types: List[str],
    max_results: int = 20,
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
        "maxResultCount": max_results,
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
                "HC Places searchNearby failed: status=%s types=%s body=%s",
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
        logger.warning("HC Places searchNearby request error: %s", e)
        return None


def _merge_places(
    places: List[Dict[str, Any]],
    center_lat: float,
    center_lon: float,
    hospitals: List[Dict[str, Any]],
    urgent_care: List[Dict[str, Any]],
    pharmacies: List[Dict[str, Any]],
    clinics: List[Dict[str, Any]],
    doctors: List[Dict[str, Any]],
    seen_ids: Set[str],
) -> Dict[str, int]:
    counts: Dict[str, int] = {
        "hospitals": 0, "urgent_care": 0, "pharmacies": 0, "clinics": 0, "doctors": 0
    }
    for p in places:
        if not isinstance(p, dict):
            continue
        types = p.get("types") or []
        bucket = _classify_hc(types)
        if bucket is None:
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
        dist_km = round(haversine_distance(center_lat, center_lon, plat_f, plon_f) / 1000.0, 3)
        row: Dict[str, Any] = {
            "name": name,
            "distance_km": dist_km,
            "source": "google_places",
        }
        if pid:
            row["google_place_id"] = pid
            seen_ids.add(pid)
        if bucket == "hospital":
            row["tags"] = {"emergency": "yes", "healthcare": "hospital"}
            hospitals.append(row)
            counts["hospitals"] += 1
        elif bucket == "urgent_care":
            urgent_care.append(row)
            counts["urgent_care"] += 1
        elif bucket == "pharmacy":
            pharmacies.append(row)
            counts["pharmacies"] += 1
        elif bucket == "clinic":
            clinics.append(row)
            counts["clinics"] += 1
        elif bucket == "doctor":
            doctors.append(row)
            counts["doctors"] += 1
    return counts


def maybe_augment_healthcare_with_places(
    lat: float,
    lon: float,
    *,
    radius_m: int,
    hospitals: List[Dict[str, Any]],
    urgent_care: List[Dict[str, Any]],
    pharmacies: List[Dict[str, Any]],
    clinics: List[Dict[str, Any]],
    doctors: List[Dict[str, Any]],
    query_failed: bool = False,
) -> Dict[str, Any]:
    """
    Optionally merge Google Places healthcare POIs into HC lists. Lists are mutated in place.

    Returns metadata dict with counts and reason (no PII beyond counts).
    """
    meta: Dict[str, Any] = {
        "used": False,
        "triggered": False,
        "reason": "disabled_or_no_key",
        "http_calls": 0,
        "hospitals_added": 0,
        "urgent_care_added": 0,
        "pharmacies_added": 0,
        "clinics_added": 0,
        "doctors_added": 0,
        "degraded_osm_substitute": False,
    }

    if not _env_enabled():
        return meta

    key = google_places_api_key()
    if not key:
        return meta

    need_hospitals = len(hospitals) == 0
    need_pharmacies = len(pharmacies) == 0
    need_primary = len(clinics) == 0 and len(doctors) == 0

    if not need_hospitals and not need_pharmacies and not need_primary:
        meta["reason"] = "osm_counts_sufficient"
        return meta

    meta["triggered"] = True

    if query_failed and not _env_truthy("HOMEFIT_PLACES_HC_ON_OSMDOWN"):
        meta["reason"] = "blocked_osm_hard_failure"
        return meta

    if query_failed:
        meta["degraded_osm_substitute"] = True
        meta["reason"] = "degraded_osm_substitute"
    else:
        meta["reason"] = "thin_osm_signal"

    seen_ids: Set[str] = set()

    # Query 1: hospitals (and urgent care if primary is also thin)
    if need_hospitals:
        types = ["hospital"]
        if need_primary:
            types.append("urgent_care_facility")
        raw = _search_nearby(key, lat, lon, float(radius_m), types)
        meta["http_calls"] += 1
        if raw is not None:
            added = _merge_places(raw, lat, lon, hospitals, urgent_care, pharmacies, clinics, doctors, seen_ids)
            meta["hospitals_added"] += added["hospitals"]
            meta["urgent_care_added"] += added["urgent_care"]

    # Query 2: pharmacies and primary care providers
    if need_pharmacies or need_primary:
        types = []
        if need_pharmacies:
            types.append("pharmacy")
        if need_primary:
            types.extend(["doctor", "dentist", "physiotherapist"])
        raw = _search_nearby(key, lat, lon, float(radius_m), types)
        meta["http_calls"] += 1
        if raw is not None:
            added = _merge_places(raw, lat, lon, hospitals, urgent_care, pharmacies, clinics, doctors, seen_ids)
            meta["pharmacies_added"] += added["pharmacies"]
            meta["clinics_added"] += added["clinics"]
            meta["doctors_added"] += added["doctors"]

    meta["used"] = meta["http_calls"] > 0
    return meta
