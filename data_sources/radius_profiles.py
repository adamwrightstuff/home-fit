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
    - active_outdoors: {local_radius_m, regional_radius_m}
    - neighborhood_amenities: {query_radius_m, walkable_distance_m}
    - public_transit_access: {routes_radius_m}
    - healthcare_access: {fac_radius_m, pharm_radius_m}
    - neighborhood_beauty: {tree_canopy_radius_m, architectural_diversity_radius_m}
    - air_travel_access: {search_radius_km}
    """
    a, s = _normalize(area_type, scope)
    p = (pillar or "").lower()

    if p == "active_outdoors":
        # Matches existing logic: urban/suburban tighter local and regional; rural/exurban wider
        if a in {"urban_core", "suburban"}:
            return {"local_radius_m": 1500, "regional_radius_m": 15000}
        else:  # exurban, rural, unknown
            return {"local_radius_m": 2000, "regional_radius_m": 50000}

    if p == "neighborhood_amenities":
        # Neighborhood scope uses smaller radii to avoid bleeding into adjacent areas
        if s == "neighborhood":
            return {"query_radius_m": 1000, "walkable_distance_m": 800}
        return {"query_radius_m": 1500, "walkable_distance_m": 1000}

    if p == "public_transit_access":
        # Default nearby route search radius
        return {"routes_radius_m": 1500}

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

    if p == "neighborhood_beauty":
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

    return {}


