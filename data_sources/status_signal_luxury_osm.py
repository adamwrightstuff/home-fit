"""
Dedicated Overpass query for Status Signal luxury_presence (OSM tag–based).
Separate from neighborhood_amenities business_list. Cached by (lat, lon, radius).
"""

from __future__ import annotations

import re
import requests
from typing import Any, Dict, List, Optional, Set, Tuple

from .cache import cached, CACHE_TTL
from .osm_api import get_overpass_url, _retry_overpass, _safe_overpass_json, _overpass_timeout
from logging_config import get_logger

logger = get_logger(__name__)

# Query version — bump to invalidate caches after tag set changes
STATUS_SIGNAL_LUXURY_OSM_QUERY_VERSION = "v2"

_FINANCIAL_OFFICE = re.compile(
    r"^(financial|financial_advisor|accountant|wealth_management|investment)$", re.I
)
_TENNIS_SPORT = re.compile(r"^tennis$", re.I)

_HEALTHCARE_VALUES = frozenset(
    {"psychotherapist", "plastic_surgeon", "medical_spa", "alternative"}
)
_LUXURY_SHOPS = frozenset(
    {"watches", "wine", "art", "antiques", "bag", "interior_design"}
)


def _classify_element(tags: Dict[str, str]) -> Set[str]:
    """Return bucket keys this element contributes to (at most one increment per bucket)."""
    if not tags:
        return set()
    out: Set[str] = set()
    office = (tags.get("office") or "").strip()
    if office in ("lawyer", "estate_agent") or (office and _FINANCIAL_OFFICE.match(office)):
        out.add("wealth_offices")
    leisure = (tags.get("leisure") or "").strip()
    if leisure in ("swimming_pool", "golf_course"):
        out.add("private_recreation")
    sport = (tags.get("sport") or "").strip()
    if sport and _TENNIS_SPORT.match(sport):
        out.add("private_recreation")
    tourism = (tags.get("tourism") or "").strip()
    if tourism in ("gallery", "museum"):
        out.add("arts_culture")
    amenity = (tags.get("amenity") or "").strip()
    if amenity in ("theatre", "arts_centre"):
        out.add("arts_culture")
    hc = (tags.get("healthcare") or "").strip()
    if hc in _HEALTHCARE_VALUES:
        out.add("specialist_healthcare")
    shop = (tags.get("shop") or "").strip()
    if shop in _LUXURY_SHOPS:
        out.add("luxury_retail")
    return out


def _dedupe_elements(elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: Set[Tuple[str, int]] = set()
    unique: List[Dict[str, Any]] = []
    for el in elements:
        t = el.get("type")
        eid = el.get("id")
        if t not in ("node", "way", "relation") or eid is None:
            continue
        key = (str(t), int(eid))
        if key in seen:
            continue
        seen.add(key)
        unique.append(el)
    return unique


def _aggregate_counts(elements: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = {
        "wealth_offices": 0,
        "private_recreation": 0,
        "arts_culture": 0,
        "specialist_healthcare": 0,
        "luxury_retail": 0,
    }
    for el in _dedupe_elements(elements):
        tags = el.get("tags") or {}
        if not isinstance(tags, dict):
            continue
        tag_str = {k: str(v) for k, v in tags.items() if v is not None}
        for bucket in _classify_element(tag_str):
            counts[bucket] += 1
    return counts


@cached(ttl_seconds=CACHE_TTL["osm_queries"])
def query_status_signal_luxury_osm(
    lat: float,
    lon: float,
    radius_m: int = 1500,
    *,
    _query_version: str = STATUS_SIGNAL_LUXURY_OSM_QUERY_VERSION,
) -> Optional[Dict[str, Any]]:
    """
    Fetch OSM features for Status Signal luxury_presence buckets within radius_m.
    Returns {"counts": {...}, "raw_element_count": int} or None on hard failure.
    """
    R = int(radius_m)
    lat_f = float(lat)
    lon_f = float(lon)
    q = f"""[out:json][timeout:90];
(
  node["office"="lawyer"](around:{R},{lat_f},{lon_f});
  way["office"="lawyer"](around:{R},{lat_f},{lon_f});
  node["office"="estate_agent"](around:{R},{lat_f},{lon_f});
  way["office"="estate_agent"](around:{R},{lat_f},{lon_f});
  node["office"~"^(financial|financial_advisor|accountant|wealth_management|investment)$"](around:{R},{lat_f},{lon_f});
  way["office"~"^(financial|financial_advisor|accountant|wealth_management|investment)$"](around:{R},{lat_f},{lon_f});
  node["leisure"="swimming_pool"](around:{R},{lat_f},{lon_f});
  way["leisure"="swimming_pool"](around:{R},{lat_f},{lon_f});
  node["leisure"="golf_course"](around:{R},{lat_f},{lon_f});
  way["leisure"="golf_course"](around:{R},{lat_f},{lon_f});
  node["sport"~"^tennis$"](around:{R},{lat_f},{lon_f});
  way["sport"~"^tennis$"](around:{R},{lat_f},{lon_f});
  node["tourism"="gallery"](around:{R},{lat_f},{lon_f});
  way["tourism"="gallery"](around:{R},{lat_f},{lon_f});
  node["tourism"="museum"](around:{R},{lat_f},{lon_f});
  way["tourism"="museum"](around:{R},{lat_f},{lon_f});
  node["amenity"="theatre"](around:{R},{lat_f},{lon_f});
  way["amenity"="theatre"](around:{R},{lat_f},{lon_f});
  node["amenity"="arts_centre"](around:{R},{lat_f},{lon_f});
  way["amenity"="arts_centre"](around:{R},{lat_f},{lon_f});
  node["healthcare"="psychotherapist"](around:{R},{lat_f},{lon_f});
  way["healthcare"="psychotherapist"](around:{R},{lat_f},{lon_f});
  node["healthcare"="plastic_surgeon"](around:{R},{lat_f},{lon_f});
  way["healthcare"="plastic_surgeon"](around:{R},{lat_f},{lon_f});
  node["healthcare"="medical_spa"](around:{R},{lat_f},{lon_f});
  way["healthcare"="medical_spa"](around:{R},{lat_f},{lon_f});
  node["healthcare"="alternative"](around:{R},{lat_f},{lon_f});
  way["healthcare"="alternative"](around:{R},{lat_f},{lon_f});
  node["shop"="watches"](around:{R},{lat_f},{lon_f});
  way["shop"="watches"](around:{R},{lat_f},{lon_f});
  node["shop"="wine"](around:{R},{lat_f},{lon_f});
  way["shop"="wine"](around:{R},{lat_f},{lon_f});
  node["shop"="art"](around:{R},{lat_f},{lon_f});
  way["shop"="art"](around:{R},{lat_f},{lon_f});
  node["shop"="antiques"](around:{R},{lat_f},{lon_f});
  way["shop"="antiques"](around:{R},{lat_f},{lon_f});
  node["shop"="bag"](around:{R},{lat_f},{lon_f});
  way["shop"="bag"](around:{R},{lat_f},{lon_f});
  node["shop"="interior_design"](around:{R},{lat_f},{lon_f});
  way["shop"="interior_design"](around:{R},{lat_f},{lon_f});
);
out body;
>;
out skel qt;
"""

    def _do_request():
        r = requests.post(
            get_overpass_url(),
            data={"data": q},
            timeout=_overpass_timeout(60),
            headers={"User-Agent": "HomeFit/1.0 (Status Signal luxury)"},
        )
        if r.status_code != 200:
            raise RuntimeError(f"Overpass status={r.status_code}")
        return r

    try:
        resp = _retry_overpass(_do_request, query_type="amenities")
        if resp is None or resp.status_code != 200:
            return None
        data = _safe_overpass_json(resp, context="status_signal_luxury_osm")
        if data is None:
            return None
        elements = data.get("elements") or []
        counts = _aggregate_counts(elements)
        return {
            "counts": counts,
            "raw_element_count": len(elements),
            "radius_m": R,
            "query_version": STATUS_SIGNAL_LUXURY_OSM_QUERY_VERSION,
        }
    except Exception as e:
        logger.warning(f"status_signal_luxury_osm failed: {e}")
        return None
