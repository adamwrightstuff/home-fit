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

DPv2 (2026-11-03): the shaded-X (0.2% annual chance) tier keeps points in proportion to its annual chance relative to
the 1% zone; zone D (flood hazard undetermined) and a point with no mapped polygon are no data, not a number (principle 16).
"""

import json
import math
import os
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

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

# Share of the flood points a place KEEPS in each zone. Floodway 0 and the SFHA 15% are judgments (docs/PILLAR_CLIMATE_RISK.md,
# G5). The shaded-X share is derived from FEMA's definitions: the SFHA is the 1% annual-chance flood and shaded X the 0.2%
# annual-chance flood, so shaded X loses 0.2 of what the SFHA loses. That points lost are proportional to annual chance is
# itself an assumption. Zone D and an unmapped point have no share: they are no data.
SFHA_RETAINED = 0.15
ANNUAL_CHANCE_RATIO_X500_TO_SFHA = 0.2
X500_RETAINED = round(1.0 - (1.0 - SFHA_RETAINED) * ANNUAL_CHANCE_RATIO_X500_TO_SFHA, 4)  # 0.83


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


def _flood_risk_to_points(risk_tier: str, max_pts: float) -> Optional[float]:
    """Convert risk tier to points (inverse risk: higher risk = fewer points). None when the tier cannot be measured."""
    if risk_tier == "floodway":
        return 0.0
    if risk_tier == "sfha":
        return max_pts * SFHA_RETAINED
    if risk_tier == "x_500yr":
        return max_pts * X500_RETAINED
    if risk_tier in ("d", "unmapped"):
        return None  # hazard undetermined or no map: no data, never a neutral number
    return max_pts  # minimal


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
        return {"in_flood_zone": False, "risk_tier": "unmapped", "flood_zone_pts": None,
                "fld_zone": None, "label": None, "sfha_tf": None}
    worst_tier, worst = "minimal", None
    for attrs in features:
        tier = _classify_zone(attrs.get("FLD_ZONE"), attrs.get("SFHA_TF"), attrs.get("ZONE_SUBTY"))
        if worst is None or FLOOD_RISK_ORDER.index(tier) < FLOOD_RISK_ORDER.index(worst_tier):
            worst_tier, worst = tier, attrs
    worst = worst or {}
    pts = _flood_risk_to_points(worst_tier, max_pts)
    return {
        "in_flood_zone": True,
        "risk_tier": worst_tier,
        "flood_zone_pts": None if pts is None else round(pts, 2),
        "fld_zone": worst.get("FLD_ZONE"),
        "label": worst.get("ZONE_SUBTY"),
        "sfha_tf": worst.get("SFHA_TF"),
    }


# The cache key includes the function name.  Results cached by the old, near-empty endpoint ("minimal"
# everywhere) are still on disk for up to 48 h, so the cached function has a new name. v3 (2026-11-03): shaded-X points
# changed and zone D / unmapped became no data, so results cached under v2 must not be served.
@cached(ttl_seconds=CACHE_TTL.get("census_data", 48 * 3600))
def _get_fema_flood_zone_v3(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    return flood_zone_from_features(fetch_flood_features(lat, lon), FLOOD_MAX_PTS_DEFAULT)


# ---------------------------------------------------------------------------------------------------------------------
# Disk measure (DPv2, 2026-11-03): the flood points averaged over an 800 m disk around the pin, not read at the single pin.
# A pin-shift test showed the pin lookup moves too much with small pin offsets (95th percentile 24 points at 500 m); the disk
# measure passed (5.4). Area-weighted over the mapped part of the disk only; zone D and unmapped area are left out (no data).
# Overlapping polygons are resolved worst tier first. The 800 m radius is a judgment, not a sourced value
# (docs/PILLAR_CLIMATE_RISK.md). The catalog (scripts/catalog/climate_flood_disk_catalog.py) and the live pillar both use
# these functions, so they cannot drift apart.
# ---------------------------------------------------------------------------------------------------------------------
FLOOD_DISK_RADIUS_M = 800.0
FLOOD_DISK_METHOD = "disk_800m_mean"


def flood_disk_enabled() -> bool:
    """Live pillar switch. Off by default: HOMEFIT_FLOOD_DISK=true turns the disk measure on."""
    return os.getenv("HOMEFIT_FLOOD_DISK", "false").strip().lower() in ("1", "true", "yes", "on")


def circle_rings(lat: float, lon: float, meters: float, n: int = 64) -> List[List[List[float]]]:
    dlat = meters / 111320.0
    dlon = meters / (111320.0 * math.cos(math.radians(lat)))
    ring = [[lon + dlon * math.cos(2 * math.pi * i / n), lat + dlat * math.sin(2 * math.pi * i / n)] for i in range(n)]
    ring.append(ring[0])
    return [ring]


def fetch_flood_polygons(lat: float, lon: float, fetch_m: float, attempts: int = 4, timeout: float = 90, backoff: float = 5) -> List[Dict[str, Any]]:
    """Every NFHL flood polygon (with geometry) within fetch_m of the pin. Raises RuntimeError when the service gives no answer.
    The service sometimes answers a transient 500 or resets the connection; each failed attempt is retried after a pause."""
    feats: List[Dict[str, Any]] = []
    offset = 0
    while True:
        body = urllib.parse.urlencode({
            "where": "1=1", "geometry": json.dumps({"rings": circle_rings(lat, lon, fetch_m), "spatialReference": {"wkid": 4326}}),
            "geometryType": "esriGeometryPolygon", "inSR": "4326", "outSR": "4326", "spatialRel": "esriSpatialRelIntersects",
            "returnGeometry": "true", "outFields": FEMA_OUT_FIELDS, "f": "json",
            "maxAllowableOffset": 0.00002,  # about 2 m of vertex generalization: lighter answers, no visible effect on an 800 m disk
            "resultOffset": offset, "resultRecordCount": 100,
        }).encode()
        data: Dict[str, Any] = {}
        for attempt in range(max(1, attempts)):
            try:
                with urllib.request.urlopen(urllib.request.Request(FEMA_NFHL_QUERY_URL, data=body, method="POST"), timeout=timeout) as r:
                    data = json.loads(r.read().decode())
            except Exception as e:  # noqa: BLE001
                data = {"error": str(e)}
            if isinstance(data, dict) and "features" in data:
                break
            if attempt + 1 < attempts:
                time.sleep(backoff * (attempt + 1))
        if not isinstance(data, dict) or "features" not in data:
            raise RuntimeError(f"FEMA answer without features: {str(data)[:200]}")
        feats += data["features"]
        if not data.get("exceededTransferLimit"):
            return feats
        offset += len(data["features"])


def polygon_to_geom(feature: Dict[str, Any], lat0: float, lon0: float):
    """Esri rings (lon, lat) to a shapely geometry in metres east/north of (lat0, lon0)."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    kx = 111320.0 * math.cos(math.radians(lat0))
    ky = 111320.0
    ext, holes = [], []
    for ring in (feature.get("geometry") or {}).get("rings") or []:
        pts = [((x - lon0) * kx, (y - lat0) * ky) for x, y in ring]
        if len(pts) < 4:
            continue
        area2 = sum(pts[i][0] * pts[i + 1][1] - pts[i + 1][0] * pts[i][1] for i in range(len(pts) - 1))
        (ext if area2 < 0 else holes).append(Polygon(pts).buffer(0))  # Esri: clockwise rings are outer rings
    if not ext:
        return None
    g = unary_union(ext)
    return g.difference(unary_union(holes)) if holes else g


def zones_from_polygons(feats: List[Dict[str, Any]], lat: float, lon: float) -> List[Tuple[str, Any]]:
    """[(tier, geometry in metres around the pin)] for the polygons that have a usable geometry."""
    zones = []
    for f in feats:
        at = f.get("attributes") or {}
        g = polygon_to_geom(f, lat, lon)
        if g is not None and not g.is_empty:
            zones.append((_classify_zone(at.get("FLD_ZONE"), at.get("SFHA_TF"), at.get("ZONE_SUBTY")), g))
    return zones


def disk_flood_points(zones, cx: float, cy: float, radius_m: float = FLOOD_DISK_RADIUS_M, max_pts: float = FLOOD_MAX_PTS_DEFAULT):
    """zones: [(tier, geometry)] in metres around the pin. Returns (mean points over the mapped area or None, mapped fraction, tier shares)."""
    from shapely.geometry import Point
    from shapely.ops import unary_union

    disk = Point(cx, cy).buffer(radius_m, 64)
    taken, shares = None, {}
    for tier in FLOOD_RISK_ORDER:
        gs = [g for t, g in zones if t == tier]
        if not gs:
            continue
        part = unary_union(gs).intersection(disk)
        if taken is not None:
            part = part.difference(taken)
        if part.is_empty:
            continue
        shares[tier] = part.area / disk.area
        taken = part if taken is None else taken.union(part)
    mapped = sum(shares.values())
    scored = {t: s for t, s in shares.items() if _flood_risk_to_points(t, max_pts) is not None}
    denom = sum(scored.values())
    if denom <= 0:
        return None, mapped, shares
    return sum(_flood_risk_to_points(t, max_pts) * s for t, s in scored.items()) / denom, mapped, shares


def flood_zone_from_disk(pts: Optional[float], mapped: float, shares: Dict[str, float]) -> Dict[str, Any]:
    """The dict the climate pillar reads, for a disk result. risk_tier is the worst tier present in the disk ("unmapped" when
    nothing is mapped, "d" when only zone D is); the points are the disk mean, None when no scored area is mapped."""
    tier = next((t for t in FLOOD_RISK_ORDER if shares.get(t, 0) > 0), "unmapped")
    return {
        "in_flood_zone": tier in ("floodway", "sfha", "x_500yr"),
        "risk_tier": tier,
        "flood_zone_pts": None if pts is None else round(pts, 2),
        "fld_zone": None, "label": None, "sfha_tf": None,
        "method": FLOOD_DISK_METHOD,
        "zone_shares": {t: round(s, 4) for t, s in shares.items()},
        "mapped_fraction": round(mapped, 3),
        "radius_m": FLOOD_DISK_RADIUS_M,
    }


@cached(ttl_seconds=CACHE_TTL.get("census_data", 48 * 3600))
def _get_fema_flood_disk_v1(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    # One attempt with a 20 s timeout: a live request cannot wait for the catalog's 4 retries. None on failure, so a failed
    # read is never served from the cache (the decorator treats a cached None as a miss) and the caller falls back to the pin lookup.
    try:
        feats = fetch_flood_polygons(lat, lon, FLOOD_DISK_RADIUS_M + 50, attempts=1, timeout=20)
        pts, mapped, shares = disk_flood_points(zones_from_polygons(feats, lat, lon), 0.0, 0.0)
    except Exception as e:  # noqa: BLE001
        logger.warning("FEMA NFHL disk query failed for (%s, %s): %s", lat, lon, e)
        return None
    return flood_zone_from_disk(pts, mapped, shares)


def get_fema_flood_zone(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    """
    Query FEMA NFHL for the flood zone at the point, or (HOMEFIT_FLOOD_DISK on) the flood average over an 800 m disk.

    Returns:
        Dict with in_flood_zone, risk_tier (floodway | sfha | x_500yr | d | minimal | unmapped), flood_zone_pts
        (0 to max; inverse risk; None for zone D and for a point with no mapped polygon), fld_zone, label (ZONE_SUBTY), sfha_tf;
        the disk result adds method, zone_shares, mapped_fraction. None on a request error (caller treats that as no data).
        When the disk read fails the pin lookup answers instead, with method "pin_fallback".
    """
    if flood_disk_enabled():
        disk = _get_fema_flood_disk_v1(lat, lon)
        if disk is not None:
            return disk
        pin = _get_fema_flood_zone_v3(lat, lon)
        return None if pin is None else {**pin, "method": "pin_fallback"}
    return _get_fema_flood_zone_v3(lat, lon)
