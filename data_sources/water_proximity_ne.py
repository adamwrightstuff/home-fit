"""
Water proximity scoring for Natural Beauty using Natural Earth 10m data.

Uses coastline, major lakes, and major rivers for distance-based proximity.
Visibility component from GEE water landcover. No OSM water queries.

Data: Download once via scripts/baselines/download_natural_earth_water.py into
data_sources/static/ or set HOMEFIT_NE_DATA_DIR.
"""

from __future__ import annotations

import math
import os
from typing import Dict, Optional, Tuple

from logging_config import get_logger

logger = get_logger(__name__)

# Lazy-loaded GeoDataFrames (metric CRS for distance in meters)
_COASTLINE: Optional["gpd.GeoDataFrame"] = None
_MAJOR_LAKES: Optional["gpd.GeoDataFrame"] = None
_MAJOR_RIVERS: Optional["gpd.GeoDataFrame"] = None
_NE_LOADED = False
_METRIC_CRS = "EPSG:5070"  # CONUS Albers Equal Area (meters)


def _ne_data_dir() -> str:
    return os.environ.get(
        "HOMEFIT_NE_DATA_DIR",
        os.path.join(os.path.dirname(__file__), "static"),
    ).rstrip("/")


def _load_ne_data() -> bool:
    """Load Natural Earth shapefiles once; project to metric CRS. Returns True if loaded."""
    global _COASTLINE, _MAJOR_LAKES, _MAJOR_RIVERS, _NE_LOADED
    if _NE_LOADED:
        return _COASTLINE is not None

    try:
        import geopandas as gpd
    except ImportError:
        logger.warning("geopandas not installed; water proximity will use GEE visibility only")
        _NE_LOADED = True
        return False

    base = _ne_data_dir()
    coast_path = os.path.join(base, "ne_10m_coastline.shp")
    lakes_path = os.path.join(base, "ne_10m_lakes.shp")
    rivers_path = os.path.join(base, "ne_10m_rivers_lake_centerlines.shp")

    if not os.path.isfile(coast_path):
        logger.warning(
            "Natural Earth coastline not found at %s; run scripts/baselines/download_natural_earth_water.py",
            coast_path,
        )
        _NE_LOADED = True
        return False

    try:
        _COASTLINE = gpd.read_file(coast_path).to_crs(_METRIC_CRS)
        if os.path.isfile(lakes_path):
            lakes = gpd.read_file(lakes_path)
            if "scalerank" in lakes.columns:
                lakes = lakes.query("scalerank <= 2")
            _MAJOR_LAKES = lakes.to_crs(_METRIC_CRS)
        else:
            _MAJOR_LAKES = gpd.GeoDataFrame()
        if os.path.isfile(rivers_path):
            rivers = gpd.read_file(rivers_path)
            if "scalerank" in rivers.columns:
                rivers = rivers.query("scalerank <= 4")
            _MAJOR_RIVERS = rivers.to_crs(_METRIC_CRS)
        else:
            _MAJOR_RIVERS = gpd.GeoDataFrame()
        _NE_LOADED = True
        logger.info("Natural Earth water data loaded (coastline + lakes + rivers)")
        return True
    except Exception as e:
        logger.warning("Failed to load Natural Earth water data: %s", e)
        _NE_LOADED = True
        return False


def _point_in_metric(lon: float, lat: float):
    """Return a point in metric CRS for distance calculations."""
    import geopandas as gpd
    from shapely.geometry import Point
    pt = gpd.GeoDataFrame(geometry=[Point(lon, lat)], crs="EPSG:4326")
    return pt.to_crs(_METRIC_CRS).geometry.iloc[0]


def _distance_km(gdf: "gpd.GeoDataFrame", point_metric) -> float:
    """Minimum distance from point to any geometry in gdf, in km."""
    if gdf is None or gdf.empty:
        return float("inf")
    d_m = gdf.distance(point_metric).min()
    if d_m is None or (isinstance(d_m, float) and math.isnan(d_m)):
        return float("inf")
    return float(d_m) / 1000.0


def _decay_score(dist_km: float, max_dist_km: float) -> float:
    """Linear decay: 100 at 0 km, 0 at max_dist_km."""
    if dist_km <= 0:
        return 100.0
    if dist_km >= max_dist_km:
        return 0.0
    return max(0.0, 100.0 * (1.0 - dist_km / max_dist_km))


def _proximity_component(lat: float, lon: float) -> Tuple[float, Dict]:
    """
    Proximity sub-score 0-100 from Natural Earth (coast, lakes, rivers).
    Returns (score_0_100, breakdown_dict).
    """
    if not _load_ne_data() or _COASTLINE is None:
        return 0.0, {"source": "none", "coast_km": None, "lake_km": None, "river_km": None}

    try:
        point = _point_in_metric(lon, lat)
        coast_km = _distance_km(_COASTLINE, point)
        lake_km = _distance_km(_MAJOR_LAKES, point) if _MAJOR_LAKES is not None and not _MAJOR_LAKES.empty else float("inf")
        river_km = _distance_km(_MAJOR_RIVERS, point) if _MAJOR_RIVERS is not None and not _MAJOR_RIVERS.empty else float("inf")

        coast_score = _decay_score(coast_km, 50.0)
        lake_score = _decay_score(lake_km, 30.0)
        river_score = _decay_score(river_km, 20.0)

        # 60% coast, 30% lake, 10% river
        proximity = 0.60 * coast_score + 0.30 * lake_score + 0.10 * river_score
        breakdown = {
            "source": "natural_earth",
            "coast_km": round(coast_km, 2) if coast_km != float("inf") else None,
            "lake_km": round(lake_km, 2) if lake_km != float("inf") else None,
            "river_km": round(river_km, 2) if river_km != float("inf") else None,
            "coast_score": round(coast_score, 2),
            "lake_score": round(lake_score, 2),
            "river_score": round(river_score, 2),
            "proximity_raw": round(proximity, 2),
        }
        return round(min(100.0, proximity), 2), breakdown
    except Exception as e:
        logger.warning("Water proximity (Natural Earth) failed: %s", e)
        return 0.0, {"source": "error", "error": str(e)[:200]}


def _visibility_component(lat: float, lon: float, landcover: Optional[Dict] = None) -> Tuple[float, Dict]:
    """
    Visibility sub-score 0-100 from GEE water landcover (can you see water from this point).
    If landcover is provided, use its water_pct; else call GEE.
    """
    if landcover is not None:
        water_pct = float(landcover.get("water_pct") or 0.0)
        return min(100.0, water_pct), {"source": "gee_landcover_cached", "water_pct": round(water_pct, 2)}
    try:
        from data_sources.gee_api import get_landcover_context_gee
        lc = get_landcover_context_gee(lat, lon, radius_m=500)
        if not lc:
            return 0.0, {"source": "gee_landcover", "water_pct": None}
        water_pct = float(lc.get("water_pct") or 0.0)
        return min(100.0, water_pct), {"source": "gee_landcover", "water_pct": round(water_pct, 2)}
    except Exception as e:
        logger.debug("Water visibility (GEE) failed: %s", e)
        return 0.0, {"source": "error", "error": str(e)[:200]}


def calculate_water_score(
    lat: float,
    lon: float,
    landcover: Optional[Dict] = None,
) -> Tuple[float, Dict]:
    """
    Water score for Natural Beauty (30% weight). 0-100.

    Combines:
    - 50% proximity: distance to coastline, major lakes, major rivers (Natural Earth)
    - 50% visibility: GEE water landcover (micro-scale water visibility)

    Returns (score_0_100, details_dict).
    """
    prox, prox_breakdown = _proximity_component(lat, lon)
    vis, vis_breakdown = _visibility_component(lat, lon, landcover)
    score = 0.50 * prox + 0.50 * vis
    details = {
        "proximity_score": round(prox, 2),
        "visibility_score": round(vis, 2),
        "proximity_breakdown": prox_breakdown,
        "visibility_breakdown": vis_breakdown,
    }
    return round(min(100.0, score), 2), details
