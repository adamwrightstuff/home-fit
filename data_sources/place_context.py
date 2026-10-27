"""
Place context: the facts about a location that every pillar must agree on.

Built once per request in main.py, before any pillar runs. It holds coordinates, density, census tract,
metro distance and the area type. It never holds a pillar's result.

The area type is decided here, once, from a business count that already includes the Google Places
top-up when OpenStreetMap is thin. Nothing changes it afterwards.

The circle (the top-up wants an area type, the area type wants the top-up) is broken with a provisional
type: density plus the raw OSM count. The provisional type only sets the Places call budget and whether the
list is thin enough to top up. It is recorded for audit and never reaches a pillar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

from logging_config import get_logger

logger = get_logger(__name__)

# One OSM query (plus at most one Places top-up) covers both the 1 km classification count and the
# widest amenities query (neighborhood_amenities uses 1,200 m for urban core and 1,500 m otherwise).
PREFETCH_RADIUS_M = 1500
CLASSIFICATION_RADIUS_M = 1000

TIER_KEYS = ("tier1_daily", "tier2_social", "tier3_culture", "tier4_services")


@dataclass(frozen=True)
class PlaceContext:
    lat: float
    lon: float
    city: Optional[str]
    area_type: str
    density: Optional[float]
    census_tract: Optional[Any] = None
    metro_distance_km: Optional[float] = None
    # How the area type was reached: "osm_only", "osm_plus_places", "cache" or "unknown".
    area_type_source: str = "unknown"
    # The type used only to budget the Places top-up. Audit field, never read by a pillar.
    provisional_area_type: Optional[str] = None
    # Request-local business list (OSM plus Places) at PREFETCH_RADIUS_M. Not cached or stored, because
    # Google's terms restrict storing Places content. None when it was not fetched or the OSM read failed.
    prefetched_businesses: Optional[Mapping[str, List[Dict]]] = field(default=None, repr=False, compare=False)
    prefetched_include_chains: bool = True
    places_meta: Optional[Mapping[str, Any]] = field(default=None, repr=False, compare=False)

    def businesses_for_radius(self, radius_m: float, include_chains: bool, vacation_mode: bool):
        """
        The prefetched list trimmed to radius_m, or None when it cannot stand in for the pillar's own query.

        It can stand in only when the OSM read succeeded, the chain filter matches, vacation mode is off
        (vacation mode adds tourism tags and widens the radius) and the radius fits inside what was fetched.
        """
        if self.prefetched_businesses is None or vacation_mode:
            return None
        if include_chains != self.prefetched_include_chains or radius_m > PREFETCH_RADIUS_M:
            return None
        return {
            k: [b for b in (self.prefetched_businesses.get(k) or []) if b.get("distance_m", 0) <= radius_m]
            for k in TIER_KEYS
        }


def _all_businesses(data: Optional[Mapping[str, List[Dict]]]) -> List[Dict]:
    if not data:
        return []
    out: List[Dict] = []
    for k in TIER_KEYS:
        out.extend(data.get(k) or [])
    return out


def count_within(data: Optional[Mapping[str, List[Dict]]], radius_m: float) -> int:
    return sum(1 for b in _all_businesses(data) if b.get("distance_m", 0) <= radius_m)


def resolve_area_type(
    lat: float,
    lon: float,
    *,
    city: Optional[str],
    location_input: Optional[str],
    density: Optional[float],
    osm_businesses: Optional[Mapping[str, List[Dict]]],
    built_coverage: Optional[float],
    metro_distance_km: Optional[float],
    include_chains: bool = True,
    detect: Optional[Callable[..., str]] = None,
    augment: Optional[Callable[..., Tuple[Dict, Dict]]] = None,
    completeness: Optional[Callable[..., float]] = None,
) -> Tuple[str, str, Optional[str], Optional[Dict], Optional[Dict]]:
    """
    Decide the area type once. Returns (area_type, source, provisional, merged_businesses, places_meta).

    osm_businesses is the raw OSM answer at PREFETCH_RADIUS_M, or None when the read failed. When it failed
    there is nothing to top up and nothing to hand to amenities: the type comes from density alone (count 0,
    the same as the old first pass) and merged_businesses is None so amenities makes its own read.
    """
    if detect is None:
        from data_sources import data_quality as _dq
        detect = _dq.detect_area_type
    if augment is None:
        from data_sources.places_fallback_client import maybe_augment_business_data_with_places as augment
    if completeness is None:
        completeness = _default_completeness

    raw_count = count_within(osm_businesses, CLASSIFICATION_RADIUS_M)
    provisional = detect(
        lat, lon, density=density, city=city, location_input=location_input,
        business_count=raw_count, built_coverage=built_coverage, metro_distance_km=metro_distance_km,
    )
    if osm_businesses is None:
        return provisional, "osm_only", provisional, None, None

    base = {k: list(osm_businesses.get(k) or []) for k in TIER_KEYS}
    try:
        merged, meta = augment(
            base, lat, lon, float(PREFETCH_RADIUS_M), include_chains,
            float(completeness(lat, lon, base, provisional, density)),
            area_type=provisional, density=density,
        )
    except Exception as e:
        # The Places client reports its own failures in meta; an exception here means the top-up did not
        # happen. Fall back to the OSM list and say so in the audit trail.
        logger.warning("Places top-up before classification failed (%s); using OSM-only list", e)
        merged, meta = base, {"used": False, "error": f"{type(e).__name__}: {e}"}

    if not meta.get("used"):
        return provisional, "osm_only", provisional, merged, meta

    final = detect(
        lat, lon, density=density, city=city, location_input=location_input,
        business_count=count_within(merged, CLASSIFICATION_RADIUS_M), built_coverage=built_coverage,
        metro_distance_km=metro_distance_km,
    )
    if final != provisional:
        logger.info("area_type settled after Places top-up: %s -> %s", provisional, final)
    return final, "osm_plus_places", provisional, merged, meta


def _default_completeness(lat: float, lon: float, base: Mapping[str, List[Dict]], area_type: str,
                          density: Optional[float] = None) -> float:
    """Same OSM completeness the amenities pillar computes before it asks for a Places top-up."""
    from data_sources.data_quality import data_quality_manager
    expected = data_quality_manager.get_expected_minimums(lat, lon, area_type or "suburban", density=density)
    score, _ = data_quality_manager.assess_data_completeness(
        "neighborhood_amenities", {"all_businesses": _all_businesses(base)}, expected
    )
    return score
