"""
FEMA National Flood Hazard Layer (NFHL) point-in-polygon lookup.

Queries FEMA's official NFHL MapServer (layer 28, flood hazard zones) for the zones at a (lat, lon)
point and returns the highest-risk zone that intersects it (SFHA = Special Flood Hazard Area).
Used by the climate_risk pillar for flood_zone_pts.

History: this module used to point at an ArcGIS Online copy of the NFHL that holds only 66 polygons
around one small area, so every other point found no polygon and was scored "minimal" (full points):
1,473 of 1,476 catalog places got 30/30 flood points (metro audit, 2026-10-22).  Zone X also has to be
read by ZONE_SUBTY: "AREA OF MINIMAL FLOOD HAZARD" is full points, only the shaded 0.2% annual chance
and levee-reduced X areas count as moderate.
"""

import json
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from data_sources.cache import cached, CACHE_TTL
from logging_config import get_logger

logger = get_logger(__name__)

# FEMA's official NFHL MapServer, layer 28 = flood hazard zones (S_FLD_HAZ_AR)
FEMA_NFHL_QUERY_URL = "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28/query"
FEMA_OUT_FIELDS = "FLD_ZONE,ZONE_SUBTY,SFHA_TF"

# Request timeout (seconds); the service is usually sub-second but occasionally slow
FEMA_REQUEST_TIMEOUT = 15

# Flood zone risk order: worst first. First match wins when assigning risk tier.
# SFHA = Special Flood Hazard Area (1% annual chance). Floodway = most hazardous.
# X (0.2%) = moderate. B/C = minimal. Not in any zone = best.
FLOOD_RISK_ORDER = [
    "floodway",           # AE Regulatory Floodway
    "sfha",               # A, AE (1% annual chance) - SFHA_TF = T
    "x_500yr",            # X 0.2% annual chance
    "d",                  # D - undetermined
    "minimal",            # X unshaded, B, C - minimal
]

# Max points for flood component (set by climate_risk pillar; used here for return value)
FLOOD_MAX_PTS_DEFAULT = 30.0


def _classify_zone(fld_zone: Optional[str], sfha_tf: Optional[str], zone_subty: Optional[str]) -> str:
    """Map FEMA FLD_ZONE / SFHA_TF / ZONE_SUBTY to a risk tier."""
    zone = (fld_zone or "").strip().upper()
    sfha = (sfha_tf or "").strip().upper() == "T"
    sub = (zone_subty or "").strip().upper()

    if "FLOODWAY" in sub:
        return "floodway"
    if sfha or zone in ("A", "AE", "AH", "AO", "V", "VE"):
        return "sfha"
    if zone == "D":
        return "d"
    if zone == "X" and ("0.2 PCT" in sub or "0.2%" in sub or "LEVEE" in sub):
        return "x_500yr"   # shaded X (0.2% annual chance) or area with reduced risk due to a levee
    return "minimal"       # unshaded X ("area of minimal flood hazard"), B, C


def _flood_risk_to_points(risk_tier: str, max_pts: float) -> float:
    """Convert risk tier to points (inverse risk: higher risk = fewer points)."""
    if risk_tier == "floodway":
        return 0.0
    if risk_tier == "sfha":
        return max_pts * 0.15   # 15% of max
    if risk_tier == "x_500yr":
        return max_pts * 0.55   # 55%
    if risk_tier == "d":
        return max_pts * 0.45   # 45%
    # minimal or not in any zone
    return max_pts


def fetch_flood_features(lat: float, lon: float) -> Optional[List[Dict[str, Any]]]:
    """Raw NFHL zone attributes at a point: a list of {FLD_ZONE, ZONE_SUBTY, SFHA_TF} (empty when the
    point is in no mapped polygon), or None when the request fails."""
    try:
        geometry = json.dumps({"x": float(lon), "y": float(lat)})
        full_url = (
            FEMA_NFHL_QUERY_URL
            + "?"
            + urllib.parse.urlencode(
                {
                    "where": "1=1",
                    "geometry": geometry,
                    "geometryType": "esriGeometryPoint",
                    "inSR": "4326",
                    "spatialRel": "esriSpatialRelIntersects",
                    "returnGeometry": "false",
                    "outFields": FEMA_OUT_FIELDS,
                    "f": "json",
                }
            )
        )
        req = urllib.request.Request(full_url, method="GET")
        with urllib.request.urlopen(req, timeout=FEMA_REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        logger.warning("FEMA NFHL query failed for (%s, %s): %s", lat, lon, e)
        return None
    if not isinstance(data, dict) or "features" not in data:
        return None
    return [f.get("attributes") or {} for f in data.get("features") or []]


def flood_zone_from_features(features: Optional[List[Dict[str, Any]]], max_pts: float = FLOOD_MAX_PTS_DEFAULT) -> Optional[Dict[str, Any]]:
    """Worst zone among the raw features, as the dict get_fema_flood_zone returns (None for a failed lookup)."""
    if features is None:
        return None
    if not features:
        return {"in_flood_zone": False, "risk_tier": "minimal", "flood_zone_pts": max_pts,
                "fld_zone": None, "label": None, "sfha_tf": None}
    worst_tier, worst = "minimal", None
    for attrs in features:
        tier = _classify_zone(attrs.get("FLD_ZONE"), attrs.get("SFHA_TF"), attrs.get("ZONE_SUBTY"))
        if worst is None or FLOOD_RISK_ORDER.index(tier) < FLOOD_RISK_ORDER.index(worst_tier):
            worst_tier, worst = tier, attrs
    worst = worst or {}
    return {
        "in_flood_zone": True,
        "risk_tier": worst_tier,
        "flood_zone_pts": round(_flood_risk_to_points(worst_tier, max_pts), 2),
        "fld_zone": worst.get("FLD_ZONE"),
        "label": worst.get("ZONE_SUBTY"),
        "sfha_tf": worst.get("SFHA_TF"),
    }


# The cache key includes the function name.  Results cached by the old, near-empty endpoint ("minimal"
# everywhere) are still on disk for up to 48 h, so the cached function has a new name (v2).
@cached(ttl_seconds=CACHE_TTL.get("census_data", 48 * 3600))
def _get_fema_flood_zone_v2(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    return flood_zone_from_features(fetch_flood_features(lat, lon), FLOOD_MAX_PTS_DEFAULT)


def get_fema_flood_zone(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    """
    Query FEMA NFHL for flood zone(s) containing the point.

    Returns:
        Dict with in_flood_zone, risk_tier (floodway | sfha | x_500yr | d | minimal), flood_zone_pts
        (0 to max; inverse risk), fld_zone, label (ZONE_SUBTY), sfha_tf; or None on a request error
        (caller treats that as no data).
    """
    return _get_fema_flood_zone_v2(lat, lon)
