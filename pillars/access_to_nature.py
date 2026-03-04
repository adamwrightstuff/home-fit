"""
Access to Nature Pillar

Question: If I walk out my front door, how quickly can I be in a natural
environment – trees/greenery, water, or meaningful elevation change?

This pillar is intentionally distinct from Active Outdoors:
- Active Outdoors = recreation opportunities (trails, camping, swimming, facilities)
- Access to Nature = living in nature / everyday exposure and downshift

Scoring (0–100, no calibration):

    greenery = local-biased canopy + neighborhood canopy + park access
    water    = proximity + visibility, via Natural Earth + GEE
    elev     = local relief / topographic variety (5km radius)

    score = 0.35 * greenery + 0.35 * water + 0.30 * elev

Implementation notes:
- Reuses existing data sources: GEE canopy/topography, Census canopy, Natural Earth
  water proximity, and OSM green spaces.
- Designed to be fast and robust; all components are optional and fail-safe to 0.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple
import math

from logging_config import get_logger

from data_sources import census_api, data_quality
from data_sources.gee_api import get_tree_canopy_gee, get_topography_context
from data_sources.water_proximity_ne import calculate_water_score
from data_sources import osm_api

logger = get_logger(__name__)


GREENERY_WEIGHT = 0.35
WATER_WEIGHT = 0.35
ELEVATION_WEIGHT = 0.30


def _distance_decay(dist_km: Optional[float], max_dist_km: float) -> float:
    """
    Simple linear decay: 0 km → 100, max_dist_km → 0.
    """
    if dist_km is None:
        return 0.0
    if dist_km <= 0:
        return 100.0
    if dist_km >= max_dist_km:
        return 0.0
    return max(0.0, 100.0 * (1.0 - (dist_km / max_dist_km)))


def _safe_float(val: object, default: float = 0.0) -> float:
    try:
        f = float(val)
    except (TypeError, ValueError):
        return default
    return default if math.isnan(f) else f


def _greenery_access_score(
    lat: float,
    lon: float,
    area_type: Optional[str] = None,
) -> Tuple[float, Dict]:
    """
    Greenery access (0–100).

    Intent: front-door greenery feel, favoring local canopy and neighborhood parks.

    Components:
    - Local canopy (radius ~1000m), blended GEE + Census when available
    - Neighborhood canopy (radius ~3000m) from GEE
    - Distance to nearest park / large green space (~5km search, 10+ acre preference)
    """
    details: Dict = {}

    # Canopy: local and neighborhood
    canopy_local = None  # 1000m radius
    canopy_neighborhood = None  # 3000m radius
    census_canopy = None

    try:
        canopy_local = get_tree_canopy_gee(lat, lon, radius_m=1000, area_type=area_type)
    except Exception as e:
        logger.debug(f"AccessToNature greenery: GEE local canopy failed: {e}")

    try:
        canopy_neighborhood = get_tree_canopy_gee(lat, lon, radius_m=3000, area_type=area_type)
    except Exception as e:
        logger.debug(f"AccessToNature greenery: GEE neighborhood canopy failed: {e}")

    try:
        census_canopy = census_api.get_tree_canopy(lat, lon)
    except Exception as e:
        logger.debug(f"AccessToNature greenery: census canopy failed: {e}")

    canopy_local_val = 0.0
    if canopy_local is not None and census_canopy is not None:
        canopy_local_val = 0.7 * _safe_float(canopy_local) + 0.3 * _safe_float(census_canopy)
    elif canopy_local is not None:
        canopy_local_val = _safe_float(canopy_local)
    elif census_canopy is not None:
        canopy_local_val = _safe_float(census_canopy)

    canopy_neighborhood_val = _safe_float(canopy_neighborhood)

    local_canopy_score = min(100.0, canopy_local_val * 2.0)  # 50% canopy → 100 pts
    neighborhood_canopy_score = min(100.0, canopy_neighborhood_val * 1.5)  # 67% → 100 pts

    # Park access: nearest park / large green space within ~5km.
    park_dist_km: Optional[float] = None
    parks_count = 0
    try:
        parks_data = osm_api.query_green_spaces(lat, lon, radius_m=5000) or {}
        parks = parks_data.get("parks", []) or []
        parks_count = len(parks)
        min_dist_m = None
        for p in parks:
            d_m = p.get("distance_m")
            if isinstance(d_m, (int, float)) and not math.isnan(d_m):
                if min_dist_m is None or d_m < min_dist_m:
                    min_dist_m = d_m
        if min_dist_m is not None:
            park_dist_km = max(0.0, float(min_dist_m) / 1000.0)
        elif parks:
            # Parks returned but no distances; treat as within search radius.
            park_dist_km = 5.0
    except Exception as e:
        logger.debug(f"AccessToNature greenery: OSM parks failed: {e}")

    park_access_score = _distance_decay(park_dist_km, max_dist_km=5.0)

    greenery = (
        0.50 * local_canopy_score
        + 0.20 * neighborhood_canopy_score
        + 0.30 * park_access_score
    )

    details.update(
        {
            "canopy_local_pct": round(canopy_local_val, 2),
            "canopy_neighborhood_pct": round(canopy_neighborhood_val, 2),
            "census_canopy_pct": round(_safe_float(census_canopy), 2) if census_canopy is not None else None,
            "local_canopy_score": round(local_canopy_score, 1),
            "neighborhood_canopy_score": round(neighborhood_canopy_score, 1),
            "parks_within_5km": parks_count,
            "nearest_park_km": round(park_dist_km, 2) if park_dist_km is not None else None,
            "park_access_score": round(park_access_score, 1),
        }
    )

    return max(0.0, min(100.0, greenery)), details


def _water_access_score(
    lat: float,
    lon: float,
    landcover: Optional[Dict] = None,
) -> Tuple[float, Dict]:
    """
    Water access (0–100) from Natural Earth proximity + GEE visibility.

    Reuses calculate_water_score, which already blends:
    - 50% proximity to coastline / major lakes / major rivers
    - 50% visibility from landcover water_pct
    """
    try:
        score, details = calculate_water_score(lat, lon, landcover=landcover)
        return max(0.0, min(100.0, float(score))), details
    except Exception as e:
        logger.debug(f"AccessToNature water: failed, returning 0. Error: {e}")
        return 0.0, {"error": str(e)[:200]}


def _elevation_access_score(
    lat: float,
    lon: float,
) -> Tuple[float, Dict]:
    """
    Elevation access (0–100) based purely on local relief / variety.

    Intent: capture the presence of nearby hills/mountains, not absolute altitude.
    """
    topo: Optional[Dict] = None
    try:
        topo = get_topography_context(lat, lon, radius_m=5000)
    except Exception as e:
        logger.debug(f"AccessToNature elevation: topography fetch failed: {e}")

    if not isinstance(topo, dict):
        return 0.0, {"relief_m": None}

    relief_m = _safe_float(topo.get("relief_range_m"), 0.0)

    # Piecewise mapping from relief to 0–100.
    # 0m → 0, 100m → 25, 500m → 75, 1000m+ → 100.
    if relief_m <= 0.0:
        score = 0.0
    elif relief_m <= 100.0:
        score = 25.0 * (relief_m / 100.0)
    elif relief_m <= 500.0:
        score = 25.0 + 50.0 * ((relief_m - 100.0) / 400.0)
    else:
        score = 75.0 + 25.0 * min(1.0, (relief_m - 500.0) / 500.0)

    return max(0.0, min(100.0, score)), {
        "relief_m": round(relief_m, 1),
        "source": topo.get("source"),
    }


def calculate_access_to_nature(
    lat: float,
    lon: float,
    city: Optional[str] = None,
    area_type: Optional[str] = None,
    location_scope: Optional[str] = None,
    location_name: Optional[str] = None,
) -> Dict:
    """
    Main entry point for Access to Nature pillar.

    Returns:
        {
            "score": float,
            "details": {...},
            "source": "access_to_nature",
            "components": {...},
            "data_quality": {...},
        }
    """
    if area_type is None:
        try:
            # Use same detection as other pillars
            density = None
            try:
                from data_sources.census_api import get_population_density

                density = get_population_density(lat, lon)
            except Exception:
                density = None
            area_type = data_quality.detect_area_type(
                lat, lon, density=density, city=city, location_input=location_name
            )
        except Exception:
            area_type = "unknown"

    # Landcover is optional; if available, it can be reused by water.
    landcover = None
    try:
        from data_sources.gee_api import get_landcover_context_gee

        landcover = get_landcover_context_gee(lat, lon, radius_m=3000)
    except Exception as e:
        logger.debug(f"AccessToNature: landcover fetch failed (non-fatal): {e}")

    greenery_score, greenery_details = _greenery_access_score(lat, lon, area_type=area_type)
    water_score, water_details = _water_access_score(lat, lon, landcover=landcover)
    elevation_score, elevation_details = _elevation_access_score(lat, lon)

    final_score = (
        GREENERY_WEIGHT * greenery_score
        + WATER_WEIGHT * water_score
        + ELEVATION_WEIGHT * elevation_score
    )
    final_score = max(0.0, min(100.0, final_score))

    components = {
        "greenery": round(greenery_score, 2),
        "water": round(water_score, 2),
        "elevation": round(elevation_score, 2),
        "weights": {
            "greenery": GREENERY_WEIGHT,
            "water": WATER_WEIGHT,
            "elevation": ELEVATION_WEIGHT,
        },
    }

    try:
        quality = data_quality.assess_pillar_data_quality(
            "access_to_nature",
            {
                "greenery": greenery_score,
                "water": water_score,
                "elevation": elevation_score,
            },
            lat,
            lon,
            area_type or "unknown",
        )
    except Exception:
        quality = {}

    details = {
        "source": "access_to_nature",
        "components": components,
        "greenery_details": greenery_details,
        "water_details": water_details,
        "elevation_details": elevation_details,
    }

    return {
        "score": final_score,
        "details": details,
        "data_quality": quality,
    }

