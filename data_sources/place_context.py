"""
Place context: the facts about a location that every pillar must agree on.

Built once per request in main.py, before any pillar runs. It holds coordinates, density, census tract,
metro distance and the area type. It never holds a pillar's result.

The area type is decided here, once, from a business count that already includes the Google Places
top-up when OpenStreetMap is thin. Nothing changes it afterwards.

The circle (the top-up wants an area type, the area type wants the top-up) is broken with a provisional
type: density plus the raw OSM count. The provisional type picks the radius the amenities pillar would use
and budgets the Places top-up. It is recorded for audit and never reaches a pillar.

The top-up result depends on the radius it runs at (Flatlands: 16 grocery and bakery results at 1,200 m,
4 at 1,500 m), so the list is handed to the amenities pillar only when the pillar's own radius, for the
final area type, is the radius the list was built at. Otherwise the pillar reads and tops up for itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

from logging_config import get_logger

logger = get_logger(__name__)

# One OSM read at the widest amenities radius gives the 1 km classification count and the base list that is
# trimmed to the radius the amenities pillar will use (1,200 m or 1,500 m).
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
    # The type used only to pick the radius and budget the Places top-up. Audit field, never read by a pillar.
    provisional_area_type: Optional[str] = None
    # Request-local business list (OSM plus Places) built at prefetched_radius_m. Not cached or stored, because
    # Google's terms restrict storing Places content. None when it was not built or the OSM read failed.
    prefetched_businesses: Optional[Mapping[str, List[Dict]]] = field(default=None, repr=False, compare=False)
    prefetched_radius_m: Optional[int] = None
    prefetched_include_chains: bool = True
    places_meta: Optional[Mapping[str, Any]] = field(default=None, repr=False, compare=False)
    # The continuous factors the area type is derived from (data_sources/surrounding_density.py, 1 km circle).
    # Pillars that scale their expected values with density read these, not the category. None when the local
    # tables cannot measure the place.
    people_density_1km: Optional[float] = None   # people per square mile over the tracts in the circle
    activity_per_acre: Optional[float] = None    # people plus jobs per gross acre
    jobs_1km: Optional[float] = None             # workplace jobs in the circle (None: jobs grid does not cover it)
    density_method: Optional[str] = None         # "disk", "pin_tract" or "nearest_tract"
    in_principal_city: Optional[bool] = None     # inside a named principal city; None when unknown

    def businesses_for_radius(self, radius_m: float, include_chains: bool, vacation_mode: bool):
        """
        The prefetched list, or None when it cannot stand in for the pillar's own query.

        It stands in only when the OSM read succeeded, the chain filter matches, vacation mode is off
        (vacation mode adds tourism tags and widens the radius) and the pillar's radius is exactly the radius
        the list was built at. The Places top-up depends on the radius, so another radius is another list.
        """
        if self.prefetched_businesses is None or self.prefetched_radius_m is None or vacation_mode:
            return None
        if include_chains != self.prefetched_include_chains or int(radius_m) != int(self.prefetched_radius_m):
            return None
        return {k: list(self.prefetched_businesses.get(k) or []) for k in TIER_KEYS}


def resolve_place_context(
    lat: float,
    lon: float,
    *,
    place_context: Optional["PlaceContext"] = None,
    area_type: Optional[str] = None,
    density: Optional[float] = None,
    city: Optional[str] = None,
    need_density: bool = False,
) -> "PlaceContext":
    """
    The one way a pillar learns the area type and density of its place.

    With a context from main.py the pillar gets that context, unchanged, and any area_type or density
    argument is ignored: the context is the single source. Without one (catalog batch scripts, tests and
    other direct callers) the place is derived here, once, with the same density-first rule the pillars each
    used to carry their own copy of, and the source is recorded as "derived_by_pillar" so the audit trail
    shows the pillar did not get the request-wide answer. Density is fetched only when the area type has to be
    derived or the pillar says it needs it (need_density), so a caller that supplies a type pays for no extra call.
    """
    if place_context is not None:
        return place_context
    if density is None and (area_type is None or need_density):
        from data_sources import census_api
        density = census_api.get_population_density(lat, lon) or 0.0
    if area_type is None:
        from data_sources import data_quality
        area_type = data_quality.detect_area_type(lat, lon, density=density, city=city)
    return PlaceContext(
        lat=lat, lon=lon, city=city, area_type=area_type, density=density,
        area_type_source="derived_by_pillar" if place_context is None else "unknown",
    )


def surrounding_factors(lat: float, lon: float, census_tract: Optional[Any] = None) -> Dict[str, Any]:
    """
    The continuous factors for a place, as PlaceContext keyword arguments. Same inputs as detect_area_type, so the
    area type and these factors always come from the same measurement.
    """
    from data_sources.surrounding_density import surrounding_stats
    from data_sources.principal_city import principal_city_at
    tract = census_tract if isinstance(census_tract, dict) else {}
    geoid = None
    if tract and all(tract.get(k) for k in ("state_fips", "county_fips", "tract_fips")):
        geoid = f"{tract['state_fips']}{tract['county_fips']}{tract['tract_fips']}"
    stats = surrounding_stats(lat, lon, tract_geoid=geoid)
    in_pc = principal_city_at(lat, lon, tract.get("state_fips"))
    if stats is None:
        return {"in_principal_city": in_pc}
    return {
        "people_density_1km": stats.people_density,
        "activity_per_acre": stats.activity_per_acre,
        "jobs_1km": stats.jobs,
        "density_method": stats.density_method,
        "in_principal_city": in_pc,
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


def _trim(data: Mapping[str, List[Dict]], radius_m: float) -> Dict[str, List[Dict]]:
    return {k: [b for b in (data.get(k) or []) if b.get("distance_m", 0) <= radius_m] for k in TIER_KEYS}


def amenities_query_radius(area_type: Optional[str], location_scope: Optional[str]) -> int:
    from data_sources.radius_profiles import get_radius_profile
    return int(get_radius_profile("neighborhood_amenities", area_type, location_scope).get("query_radius_m", 1500))


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
    location_scope: Optional[str] = None,
    include_chains: bool = True,
    census_tract: Optional[Any] = None,
    detect: Optional[Callable[..., str]] = None,
    augment: Optional[Callable[..., Tuple[Dict, Dict]]] = None,
    completeness: Optional[Callable[..., float]] = None,
    radius_for: Optional[Callable[[Optional[str], Optional[str]], int]] = None,
) -> Tuple[str, str, Optional[str], Optional[Dict], Optional[Dict], Optional[int]]:
    """
    Decide the area type once.
    Returns (area_type, source, provisional, merged_businesses, places_meta, merged_radius_m).

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
    if radius_for is None:
        radius_for = amenities_query_radius

    raw_count = count_within(osm_businesses, CLASSIFICATION_RADIUS_M)
    provisional = detect(
        lat, lon, density=density, city=city, location_input=location_input,
        business_count=raw_count, built_coverage=built_coverage, metro_distance_km=metro_distance_km, census_tract=census_tract,
    )
    if osm_businesses is None:
        return provisional, "osm_only", provisional, None, None, None

    radius = radius_for(provisional, location_scope)
    if radius > PREFETCH_RADIUS_M:
        # The OSM read does not cover this radius, so no list can stand in for the pillar's own query.
        return provisional, "osm_only", provisional, None, None, None

    base = _trim(osm_businesses, radius)
    try:
        merged, meta = augment(
            base, lat, lon, float(radius), include_chains,
            float(completeness(lat, lon, base, provisional, density)),
            area_type=provisional, density=density,
        )
    except Exception as e:
        # The Places client reports its own failures in meta; an exception here means the top-up did not
        # happen. Fall back to the OSM list and say so in the audit trail.
        logger.warning("Places top-up before classification failed (%s); using OSM-only list", e)
        merged, meta = base, {"used": False, "error": f"{type(e).__name__}: {e}"}

    if not meta.get("used"):
        return provisional, "osm_only", provisional, merged, meta, radius

    final = detect(
        lat, lon, density=density, city=city, location_input=location_input,
        business_count=count_within(merged, CLASSIFICATION_RADIUS_M), built_coverage=built_coverage,
        metro_distance_km=metro_distance_km, census_tract=census_tract,
    )
    if final != provisional:
        logger.info("area_type settled after Places top-up: %s -> %s", provisional, final)
    return final, "osm_plus_places", provisional, merged, meta, radius


def _default_completeness(lat: float, lon: float, base: Mapping[str, List[Dict]], area_type: str,
                          density: Optional[float] = None) -> float:
    """Same OSM completeness the amenities pillar computes before it asks for a Places top-up."""
    from data_sources.data_quality import data_quality_manager
    expected = data_quality_manager.get_expected_minimums(lat, lon, area_type or "suburban", density=density)
    score, _ = data_quality_manager.assess_data_completeness(
        "neighborhood_amenities", {"all_businesses": _all_businesses(base)}, expected
    )
    return score
