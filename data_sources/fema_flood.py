"""
FEMA National Flood Hazard Layer (NFHL) point-in-polygon lookup.

Uses the FEMA ArcGIS FeatureServer to query flood zones at a (lat, lon) point.
Returns the highest-risk zone that intersects the point (SFHA = Special Flood Hazard Area).
Used by the climate_risk pillar for flood_zone_pts.
"""

import json
import urllib.parse
import urllib.request
from typing import Optional, Dict, Any

from data_sources.cache import cached, CACHE_TTL
from logging_config import get_logger

logger = get_logger(__name__)

# FEMA NFHL FeatureServer (layer 0 = flood zones)
FEMA_NFHL_QUERY_URL = "https://services.arcgis.com/2gdL2gxYNFY2TOUb/arcgis/rest/services/FEMA_National_Flood_Hazard_Layer/FeatureServer/0/query"

# Request timeout (seconds)
FEMA_REQUEST_TIMEOUT = 10

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


def _classify_zone(fld_zone: Optional[str], sfha_tf: Optional[str], label: Optional[str]) -> str:
    """Map FEMA FLD_ZONE / SFHA_TF / LABEL to a risk tier."""
    zone = (fld_zone or "").strip().upper()
    sfha = (sfha_tf or "").strip().upper() == "T"
    lab = (label or "").lower()

    if "floodway" in lab or "regulatory floodway" in lab:
        return "floodway"
    if sfha or zone in ("A", "AE", "AH", "AO", "V", "VE"):
        return "sfha"
    if "0.2%" in (label or "") or zone == "X":
        return "x_500yr"
    if zone == "D":
        return "d"
    return "minimal"


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


@cached(ttl_seconds=CACHE_TTL.get("census_data", 48 * 3600))
def get_fema_flood_zone(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    """
    Query FEMA NFHL for flood zone(s) containing the point.

    Returns:
        Dict with:
          - in_flood_zone: bool (True if point intersects any NFHL polygon)
          - risk_tier: str (floodway | sfha | x_500yr | d | minimal)
          - flood_zone_pts: float (0 to max_pts; inverse risk)
          - fld_zone: str (raw FLD_ZONE from FEMA)
          - label: str (FEMA LABEL)
          - sfha_tf: str (T/F)
        Or None on request error (no cache; caller can treat as no data).
    """
    max_pts = FLOOD_MAX_PTS_DEFAULT
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
                    "outFields": "FLD_ZONE,SFHA_TF,LABEL",
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

    if not isinstance(data, dict):
        return None
    features = data.get("features") or []
    if not features:
        return {
            "in_flood_zone": False,
            "risk_tier": "minimal",
            "flood_zone_pts": max_pts,
            "fld_zone": None,
            "label": None,
            "sfha_tf": None,
        }

    worst_tier = "minimal"
    worst_fld_zone = None
    worst_label = None
    worst_sfha = None
    for f in features:
        attrs = f.get("attributes") or {}
        fld_zone = attrs.get("FLD_ZONE")
        sfha_tf = attrs.get("SFHA_TF")
        label = attrs.get("LABEL")
        tier = _classify_zone(fld_zone, sfha_tf, label)
        if FLOOD_RISK_ORDER.index(tier) < FLOOD_RISK_ORDER.index(worst_tier):
            worst_tier = tier
            worst_fld_zone = fld_zone
            worst_label = label
            worst_sfha = sfha_tf

    flood_zone_pts = _flood_risk_to_points(worst_tier, max_pts)

    return {
        "in_flood_zone": True,
        "risk_tier": worst_tier,
        "flood_zone_pts": round(flood_zone_pts, 2),
        "fld_zone": worst_fld_zone,
        "label": worst_label,
        "sfha_tf": worst_sfha,
    }
