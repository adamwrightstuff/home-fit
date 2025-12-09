"""
Centralized default radius profiles per pillar.

These profiles unify how default radii are chosen based on the detected
area_type and location_scope without exposing any new public API params.

area_type: one of {"urban_core", "suburban", "exurban", "rural", "unknown"}
location_scope: one of {"neighborhood", "city", "unknown"}
"""

from typing import Dict


def _normalize(area_type: str | None, scope: str | None) -> tuple[str, str]:
    a = (area_type or "unknown").lower()
    s = (scope or "unknown").lower()
    # Keep original area_type for beauty radius checks (needs to preserve subtypes)
    # Only normalize scope
    if s not in {"neighborhood", "city", "unknown"}:
        s = "unknown"
    return a, s


def get_radius_profile(pillar: str, area_type: str | None, scope: str | None) -> Dict:
    """
    Return a dict of default radii for a pillar given area/context.

    The returned keys are pillar-specific:
    - active_outdoors: {local_radius_m, trail_radius_m, regional_radius_m}
    - neighborhood_amenities: {query_radius_m, walkable_distance_m}
    - public_transit_access: {routes_radius_m}
    - healthcare_access: {fac_radius_m, pharm_radius_m}
    - built_beauty: {architectural_diversity_radius_m}
    - natural_beauty: {tree_canopy_radius_m, context_radius_m (optional)}
    - air_travel_access: {search_radius_km}
    - quality_education: {search_radius_miles}
    """
    a, s = _normalize(area_type, scope)
    p = (pillar or "").lower()

    if p == "active_outdoors":
        # Research-based radii: parks (local), trails (separate), water/camping (regional)
        # NOTE: Trail radii align with expected-values research windows (15km) so that
        # OSM sampling and contextual expectations use the same footprint.
        # Urban parks: 800m = 10-minute walk (research: 70-80% within 800m)
        # Trails: 15km window used for expectations (even in dense cores)
        # Suburban/exurban trails already relied on wider radii (15km+)
        if a == "urban_core":
            return {
                "local_radius_m": 800,      # Parks: 10-minute walk
                "trail_radius_m": 15000,    # Trails: Align with expected-values window
                "regional_radius_m": 15000  # Water/camping: Unchanged
            }
        elif a == "suburban":
            return {
                "local_radius_m": 1500,     # Parks: Car-oriented access
                "trail_radius_m": 15000,    # Trails: Align with expected-values window
                "regional_radius_m": 15000  # Water/camping: Unchanged
            }
        else:  # exurban, rural, unknown
            return {
                "local_radius_m": 2000,     # Parks: Wider search
                "trail_radius_m": 15000,     # Trails: Natural trail access
                "regional_radius_m": 50000  # Water/camping: Wider for rural
            }

    if p == "neighborhood_amenities":
        # Neighborhood scope uses smaller radii to avoid bleeding into adjacent areas
        if s == "neighborhood":
            return {"query_radius_m": 1000, "walkable_distance_m": 800}
        return {"query_radius_m": 1500, "walkable_distance_m": 1000}

    if p == "public_transit_access":
        # Area-type-specific radii: larger metros need larger search radii
        # Urban cores have extensive transit networks that extend beyond 1.5km
        # Rationale: Dense metros have more routes spread over larger areas
        # This is objective (area-type based) and scalable (works for all locations)
        if a == "urban_core":
            return {"routes_radius_m": 3000}  # 3km for dense metros
        elif a == "suburban":
            return {"routes_radius_m": 2000}  # 2km for suburbs
        else:  # exurban, rural, unknown
            return {"routes_radius_m": 1500}  # 1.5km for sparse areas

    if p == "healthcare_access":
        # Mirrors existing thresholds based on area type
        if a == "urban_core":
            return {"fac_radius_m": 5000, "pharm_radius_m": 2000}
        if a == "suburban":
            return {"fac_radius_m": 10000, "pharm_radius_m": 3000}
        if a == "exurban":
            return {"fac_radius_m": 15000, "pharm_radius_m": 5000}
        # rural or unknown
        return {"fac_radius_m": 20000, "pharm_radius_m": 8000}

    if p in {"built_beauty", "natural_beauty", "neighborhood_beauty"}:
        # Tree radius adjustments:
        # - urban_historic and urban_residential: 800m (tighter for dense urban areas)
        # - urban_core: 1000m
        # - suburban: 1000-2000m (keep wider for suburban)
        # - neighborhood scope: 1000m (stays within neighborhood boundaries)
        if s == "neighborhood":
            return {"tree_canopy_radius_m": 1000, "architectural_diversity_radius_m": 2000}
        # Check for urban_historic/urban_residential first (before urban_core check)
        # Use original area_type (a) which may be lowercase, check both cases
        a_lower = a.lower()
        if a_lower in ("urban_historic", "historic_urban", "urban_residential"):
            return {"tree_canopy_radius_m": 800, "architectural_diversity_radius_m": 2000}
        if a_lower == "urban_core":
            return {"tree_canopy_radius_m": 1000, "architectural_diversity_radius_m": 2000}
        # suburban, exurban, rural: keep 1-2km radius
        return {"tree_canopy_radius_m": 2000, "architectural_diversity_radius_m": 2000}

    if p == "air_travel_access":
        # Search within 100km for airports by default
        return {"search_radius_km": 100}

    if p == "quality_education":
        # Conservative school search radii to avoid catching unrelated schools
        # Urban: 1.5 miles (tight for dense neighborhoods)
        # Suburban: 2 miles (moderate for car-oriented access)
        # Rural/Exurban: 3 miles (wider for sparse areas)
        if a == "urban_core":
            return {"search_radius_miles": 1.5}
        elif a == "suburban":
            return {"search_radius_miles": 2.0}
        else:  # exurban, rural, unknown
            return {"search_radius_miles": 3.0}

    return {}


