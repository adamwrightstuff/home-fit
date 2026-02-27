"""
Layout & Street Network Pillar

Scores how the local street network supports low-stress walking and everyday
movement, using only OSM road/rail data (no POIs, no buildings).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any

from logging_config import get_logger

from data_sources.osm_api import query_layout_network
from data_sources.utils import haversine_distance
from data_sources.radius_profiles import get_radius_profile
from data_sources import data_quality

logger = get_logger(__name__)


WALKABLE_HIGHWAY_CLASSES = (
    "residential",
    "living_street",
    "unclassified",
    "tertiary",
    "secondary",
    "service",
    "footway",
    "path",
)

LOCAL_ROAD_CLASSES = (
    "residential",
    "living_street",
    "unclassified",
    "tertiary",
    "service",
)

MAJOR_ROAD_CLASSES = (
    "primary",
    "trunk",
    "motorway",
)


@dataclass
class LayoutNetworkMetrics:
    # Connectivity
    intersection_density_per_sqkm: float = 0.0
    median_block_length_m: float = 0.0
    culdesac_ratio: float = 0.0  # dead-end share on local network (0-1)

    # Hierarchy / speeds
    local_road_length_km: float = 0.0
    major_road_length_km: float = 0.0
    local_calm_speed_share: float = 0.0  # 0-1, local roads at or below calm threshold
    lane_km_major: float = 0.0

    # Barriers
    barrier_corridors: int = 0

    # Infrastructure tags
    sidewalk_share_local: float = 0.0  # 0-1
    cycleway_share: float = 0.0  # 0-1 of all roads/paths
    greenway_length_km: float = 0.0


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _piecewise_score(x: float, points: List[Tuple[float, float]]) -> float:
    """
    Simple piecewise-linear scorer.

    Args:
        x: input value
        points: list of (x, score) pairs, sorted by x
    """
    if not points:
        return 0.0
    points = sorted(points, key=lambda p: p[0])
    if x <= points[0][0]:
        return points[0][1]
    if x >= points[-1][0]:
        return points[-1][1]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x0 <= x <= x1:
            if x1 == x0:
                return y1
            t = (x - x0) / (x1 - x0)
            return y0 + t * (y1 - y0)
    return points[-1][1]


def _fetch_network(lat: float, lon: float, radius_m: int) -> Optional[Dict[str, Any]]:
    """
    Fetch OSM road + rail network around a point (cached, production-resilient).
    Delegates to data_sources.osm_api.query_layout_network which uses 6hr cache,
    longer timeout (35s), and stale cache on failure.
    """
    return query_layout_network(lat, lon, radius_m)


def _build_layout_metrics(
    lat: float,
    lon: float,
    radius_m: int,
    data: Dict[str, Any],
) -> LayoutNetworkMetrics:
    nodes: Dict[int, Dict[str, Any]] = data.get("nodes", {})
    ways: List[Dict[str, Any]] = data.get("ways", [])

    # Derived geometry helpers
    def _dist(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
        return haversine_distance(a_lat, a_lon, b_lat, b_lon)

    # Node degree for cul-de-sacs & intersections
    node_degree: Dict[int, int] = {}

    local_segments: List[Tuple[Tuple[float, float], Tuple[float, float], Dict[str, Any]]] = []
    all_road_segments: List[Tuple[Tuple[float, float], Tuple[float, float], Dict[str, Any]]] = []
    rail_segments: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []

    local_length_m = 0.0
    major_length_m = 0.0
    all_road_length_m = 0.0
    total_length_with_sidewalk_m = 0.0
    total_local_length_tagged_sidewalk_m = 0.0
    total_length_with_cycleway_m = 0.0
    greenway_length_m = 0.0
    lane_km_major = 0.0
    calm_length_m = 0.0
    calm_speed_threshold_kmh = 30.0

    for way in ways:
        tags = way.get("tags", {}) or {}
        wtype = tags.get("highway") or tags.get("railway")
        nodes_list = way.get("nodes", []) or []
        if len(nodes_list) < 2:
            continue

        coords: List[Tuple[float, float]] = []
        for nid in nodes_list:
            node = nodes.get(nid)
            if not node:
                continue
            coords.append((node["lat"], node["lon"]))
            node_degree[nid] = node_degree.get(nid, 0) + 1

        if len(coords) < 2:
            continue

        is_rail = tags.get("railway") is not None and tags.get("highway") is None
        if is_rail:
            for a, b in zip(coords, coords[1:]):
                length_m = _dist(a[0], a[1], b[0], b[1])
                if length_m <= 0:
                    continue
                rail_segments.append((a, b))
            continue

        # Roads
        highway = tags.get("highway", "")
        is_local = highway in LOCAL_ROAD_CLASSES
        is_major = highway in MAJOR_ROAD_CLASSES

        lanes = _safe_float(tags.get("lanes"), default=1.0)
        maxspeed = _safe_float(tags.get("maxspeed"), default=0.0)
        # Simple mph strings like "25 mph"
        if isinstance(tags.get("maxspeed"), str) and "mph" in tags["maxspeed"]:
            try:
                mph = float(tags["maxspeed"].split("mph")[0].strip())
                maxspeed = mph * 1.60934
            except Exception:  # noqa: BLE001
                maxspeed = 0.0

        has_sidewalk = tags.get("sidewalk") not in (None, "no")
        has_cycleway = bool(
            tags.get("cycleway")
            or tags.get("cycleway:left")
            or tags.get("cycleway:right")
            or tags.get("highway") == "cycleway"
        )

        # Treat non-adjacent footways/paths as potential greenways
        is_potential_greenway = highway in ("footway", "path") and not is_major

        for a, b in zip(coords, coords[1:]):
            length_m = _dist(a[0], a[1], b[0], b[1])
            if length_m <= 0:
                continue

            seg_meta = {
                "highway": highway,
                "lanes": lanes,
                "maxspeed_kmh": maxspeed,
                "has_sidewalk": has_sidewalk,
                "has_cycleway": has_cycleway,
                "is_local": is_local,
                "is_major": is_major,
                "is_potential_greenway": is_potential_greenway,
            }
            all_road_segments.append((a, b, seg_meta))
            all_road_length_m += length_m

            if is_local:
                local_segments.append((a, b, seg_meta))
                local_length_m += length_m

            if is_major:
                major_length_m += length_m
                lane_km_major += (length_m / 1000.0) * max(1.0, lanes)

            if has_sidewalk:
                total_length_with_sidewalk_m += length_m
                if is_local:
                    total_local_length_tagged_sidewalk_m += length_m

            if has_cycleway:
                total_length_with_cycleway_m += length_m

            if is_potential_greenway and not is_major:
                greenway_length_m += length_m

            if is_local and maxspeed > 0.0 and maxspeed <= calm_speed_threshold_kmh:
                calm_length_m += length_m

    # Connectivity: intersections, blocks, cul-de-sacs
    intersections = []
    dead_ends = 0
    for nid, deg in node_degree.items():
        node = nodes.get(nid)
        if not node:
            continue
        dist = _dist(lat, lon, node["lat"], node["lon"])
        if dist > radius_m:
            continue
        if deg >= 3:
            intersections.append((node["lat"], node["lon"]))
        elif deg == 1:
            dead_ends += 1

    total_nodes_in_radius = sum(
        1
        for nid, node in nodes.items()
        if _dist(lat, lon, node["lat"], node["lon"]) <= radius_m
    )
    culdesac_ratio = 0.0
    if total_nodes_in_radius > 0:
        culdesac_ratio = dead_ends / float(total_nodes_in_radius)

    block_lengths: List[float] = []
    for a, b, _meta in local_segments:
        length_m = _dist(a[0], a[1], b[0], b[1])
        if length_m > 0:
            block_lengths.append(length_m)

    median_block = 0.0
    if block_lengths:
        sorted_bl = sorted(block_lengths)
        mid = len(sorted_bl) // 2
        if len(sorted_bl) % 2 == 0:
            median_block = 0.5 * (sorted_bl[mid - 1] + sorted_bl[mid])
        else:
            median_block = sorted_bl[mid]

    area_sqkm = (math.pi * (radius_m / 1000.0) ** 2) if radius_m > 0 else 1.0
    intersection_density = len(intersections) / area_sqkm if area_sqkm > 0 else 0.0

    # Barriers: very simple proxy, count major road / rail corridors crossing radius
    barrier_corridors = 0
    for segs, is_rail_type in ((all_road_segments, False), ([(a, b, {}) for a, b in rail_segments], True)):
        counted = False
        for a, b, meta in segs:
            if is_rail_type:
                used = True
            else:
                used = meta.get("is_major")
            if not used:
                continue
            da = _dist(lat, lon, a[0], a[1])
            db = _dist(lat, lon, b[0], b[1])
            if (da <= radius_m and db > radius_m) or (db <= radius_m and da > radius_m):
                counted = True
                break
        if counted:
            barrier_corridors += 1

    # Infra shares
    sidewalk_share_local = (
        (total_local_length_tagged_sidewalk_m / local_length_m)
        if local_length_m > 0 and total_local_length_tagged_sidewalk_m > 0
        else 0.0
    )
    cycleway_share = (
        (total_length_with_cycleway_m / all_road_length_m)
        if all_road_length_m > 0 and total_length_with_cycleway_m > 0
        else 0.0
    )

    local_calm_speed_share = (
        (calm_length_m / local_length_m)
        if local_length_m > 0 and calm_length_m > 0
        else 0.0
    )

    return LayoutNetworkMetrics(
        intersection_density_per_sqkm=intersection_density,
        median_block_length_m=median_block,
        culdesac_ratio=culdesac_ratio,
        local_road_length_km=local_length_m / 1000.0,
        major_road_length_km=major_length_m / 1000.0,
        local_calm_speed_share=local_calm_speed_share,
        lane_km_major=lane_km_major,
        barrier_corridors=barrier_corridors,
        sidewalk_share_local=sidewalk_share_local,
        cycleway_share=cycleway_share,
        greenway_length_km=greenway_length_m / 1000.0,
    )


def _score_connectivity(metrics: LayoutNetworkMetrics, area_type: str) -> Tuple[float, Dict[str, float]]:
    # Intersection density bands by area_type
    if area_type in ("urban_core", "urban_residential"):
        inter_points = [
            (20.0, 0.0),
            (40.0, 8.0),
            (80.0, 13.0),
            (120.0, 15.0),
        ]
    elif area_type in ("suburban",):
        inter_points = [
            (10.0, 0.0),
            (25.0, 8.0),
            (50.0, 13.0),
            (80.0, 15.0),
        ]
    else:  # rural/exurban/unknown
        inter_points = [
            (5.0, 0.0),
            (15.0, 8.0),
            (30.0, 13.0),
            (50.0, 15.0),
        ]
    inter_score = _piecewise_score(metrics.intersection_density_per_sqkm, inter_points)

    # Block length bands
    bl = metrics.median_block_length_m or 0.0
    if area_type in ("urban_core", "urban_residential"):
        block_points = [
            (250.0, 0.0),
            (200.0, 3.0),
            (150.0, 6.0),
            (100.0, 8.0),
            (80.0, 10.0),
        ]
    elif area_type in ("suburban",):
        block_points = [
            (350.0, 0.0),
            (250.0, 3.0),
            (180.0, 6.0),
            (130.0, 8.0),
            (100.0, 10.0),
        ]
    else:
        block_points = [
            (500.0, 0.0),
            (350.0, 3.0),
            (250.0, 6.0),
            (180.0, 8.0),
            (130.0, 10.0),
        ]
    block_score = _piecewise_score(bl, block_points)

    # Cul-de-sac ratio (dead-end share, lower is better)
    dead = metrics.culdesac_ratio
    if area_type in ("urban_core", "urban_residential"):
        cul_points = [
            (0.40, 0.0),
            (0.30, 3.0),
            (0.20, 7.0),
            (0.10, 10.0),
        ]
    elif area_type in ("suburban",):
        cul_points = [
            (0.60, 0.0),
            (0.45, 3.0),
            (0.30, 7.0),
            (0.15, 10.0),
        ]
    else:
        cul_points = [
            (0.80, 0.0),
            (0.60, 3.0),
            (0.40, 7.0),
            (0.25, 10.0),
        ]
    cul_score = _piecewise_score(dead, cul_points)

    connectivity_score = max(0.0, min(35.0, inter_score + block_score + cul_score))
    return connectivity_score, {
        "intersection_density_score": inter_score,
        "block_length_score": block_score,
        "culdesac_score": cul_score,
    }


def _score_hierarchy(metrics: LayoutNetworkMetrics, area_type: str) -> Tuple[float, Dict[str, float]]:
    total_road_km = metrics.local_road_length_km + metrics.major_road_length_km
    local_share = (
        metrics.local_road_length_km / total_road_km if total_road_km > 0 else 0.0
    )

    if area_type in ("urban_core", "urban_residential"):
        mix_points = [
            (0.40, 0.0),
            (0.60, 7.0),
            (0.80, 12.0),
            (0.90, 15.0),
        ]
    elif area_type in ("suburban",):
        mix_points = [
            (0.30, 0.0),
            (0.55, 7.0),
            (0.75, 12.0),
            (0.90, 15.0),
        ]
    else:
        mix_points = [
            (0.20, 0.0),
            (0.45, 7.0),
            (0.70, 12.0),
            (0.90, 15.0),
        ]
    local_mix_score = _piecewise_score(local_share, mix_points)

    # Arterial dominance: lower lane-km is better
    lane_km = metrics.lane_km_major
    if area_type in ("urban_core", "urban_residential"):
        lane_points = [
            (6.0, 0.0),
            (4.0, 3.0),
            (2.0, 7.0),
            (1.0, 10.0),
        ]
    elif area_type in ("suburban",):
        lane_points = [
            (4.0, 0.0),
            (3.0, 3.0),
            (1.8, 7.0),
            (0.8, 10.0),
        ]
    else:
        lane_points = [
            (3.0, 0.0),
            (2.0, 3.0),
            (1.2, 7.0),
            (0.5, 10.0),
        ]
    arterial_score = _piecewise_score(lane_km, lane_points)

    # Speed environment on local roads
    calm_share = metrics.local_calm_speed_share
    speed_points = [
        (0.20, 0.0),
        (0.40, 2.0),
        (0.60, 4.0),
        (0.80, 5.0),
    ]
    speed_score = _piecewise_score(calm_share, speed_points)

    hierarchy_score = max(0.0, min(30.0, local_mix_score + arterial_score + speed_score))
    return hierarchy_score, {
        "local_mix_score": local_mix_score,
        "arterial_dominance_score": arterial_score,
        "speed_environment_score": speed_score,
        "local_share": local_share,
        "lane_km_major": lane_km,
    }


def _score_barriers(metrics: LayoutNetworkMetrics, area_type: str) -> Tuple[float, Dict[str, float]]:
    # Simple corridor count mapped to penalty; treat area_type uniformly for now
    corridors = metrics.barrier_corridors
    hard_penalty_points = [
        (0.0, 0.0),
        (1.0, 4.0),
        (2.0, 7.0),
        (3.0, 10.0),
        (4.0, 12.0),
    ]
    hard_penalty = _piecewise_score(float(corridors), hard_penalty_points)

    # Superblock proxy: very long blocks + low intersection density
    superblock_penalty = 0.0
    if metrics.median_block_length_m > 250.0 and metrics.intersection_density_per_sqkm < 30.0:
        excess_block = (metrics.median_block_length_m - 250.0) / 200.0
        lack_intersections = max(0.0, (30.0 - metrics.intersection_density_per_sqkm) / 30.0)
        superblock_penalty = max(0.0, min(8.0, 8.0 * excess_block * lack_intersections))

    total_penalty = min(20.0, hard_penalty + superblock_penalty)
    return total_penalty, {
        "hard_barrier_penalty": hard_penalty,
        "superblock_penalty": superblock_penalty,
        "barrier_corridors": float(corridors),
    }


def _score_infra_bonus(metrics: LayoutNetworkMetrics, area_type: str) -> Tuple[float, Dict[str, float]]:
    sidewalk_points = [
        (0.20, 0.0),
        (0.40, 3.0),
        (0.60, 5.0),
        (0.80, 8.0),
    ]
    sidewalk_score = _piecewise_score(metrics.sidewalk_share_local, sidewalk_points)

    cycle_points = [
        (0.10, 0.0),
        (0.25, 2.0),
        (0.50, 4.0),
        (0.75, 5.0),
    ]
    cycle_score = _piecewise_score(metrics.cycleway_share, cycle_points)

    path_points = [
        (0.0, 0.0),
        (0.2, 1.0),
        (0.5, 2.0),
    ]
    path_score = _piecewise_score(metrics.greenway_length_km, path_points)

    infra_bonus = min(15.0, sidewalk_score + cycle_score + path_score)
    return infra_bonus, {
        "sidewalk_bonus": sidewalk_score,
        "cycle_bonus": cycle_score,
        "greenway_bonus": path_score,
    }


def get_layout_network_score(
    lat: float,
    lon: float,
    *,
    area_type: Optional[str] = None,
    location_scope: Optional[str] = None,
    density: Optional[float] = None,
    radius_m: Optional[int] = None,
) -> Tuple[float, Dict[str, Any]]:
    """
    Calculate layout & street network score (0-100).

    Purely data-backed, no calibration. Uses OSM road + rail network only.
    """
    logger.info("🚶 Analyzing layout & street network for %s, %s", lat, lon)

    # Detect area_type if not provided
    if density is None:
        from data_sources import census_api

        density = census_api.get_population_density(lat, lon) or 0.0

    if area_type is None:
        area_type = data_quality.detect_area_type(lat, lon, density)

    # Radius profile
    profile = get_radius_profile("layout_network", area_type, location_scope)
    effective_radius = int(radius_m or profile.get("query_radius_m", 1000))

    data = _fetch_network(lat, lon, effective_radius)
    if not data:
        logger.warning("Layout network: OSM data unavailable, returning neutral score 0")
        breakdown: Dict[str, Any] = {
            "layout_score": 0.0,
            "connectivity_score": 0.0,
            "hierarchy_score": 0.0,
            "barriers_penalty": 0.0,
            "infra_bonus": 0.0,
            "metrics": {},
            "area_type": area_type,
            "radius_m": effective_radius,
            "data_warning": "osm_unavailable",
        }
        return 0.0, breakdown

    metrics = _build_layout_metrics(lat, lon, effective_radius, data)

    connectivity_score, connectivity_meta = _score_connectivity(metrics, area_type)
    hierarchy_score, hierarchy_meta = _score_hierarchy(metrics, area_type)
    barriers_penalty, barriers_meta = _score_barriers(metrics, area_type)
    infra_bonus, infra_meta = _score_infra_bonus(metrics, area_type)

    raw_score = connectivity_score + hierarchy_score - barriers_penalty + infra_bonus
    final_score = max(0.0, min(100.0, raw_score))

    breakdown = {
        "layout_score": final_score,
        "raw_score": raw_score,
        "connectivity_score": connectivity_score,
        "hierarchy_score": hierarchy_score,
        "barriers_penalty": barriers_penalty,
        "infra_bonus": infra_bonus,
        "metrics": {
            "intersection_density_per_sqkm": metrics.intersection_density_per_sqkm,
            "median_block_length_m": metrics.median_block_length_m,
            "culdesac_ratio": metrics.culdesac_ratio,
            "local_road_length_km": metrics.local_road_length_km,
            "major_road_length_km": metrics.major_road_length_km,
            "local_calm_speed_share": metrics.local_calm_speed_share,
            "lane_km_major": metrics.lane_km_major,
            "barrier_corridors": metrics.barrier_corridors,
            "sidewalk_share_local": metrics.sidewalk_share_local,
            "cycleway_share": metrics.cycleway_share,
            "greenway_length_km": metrics.greenway_length_km,
        },
        "component_details": {
            "connectivity": connectivity_meta,
            "hierarchy": hierarchy_meta,
            "barriers": barriers_meta,
            "infra_bonus": infra_meta,
        },
        "area_type": area_type,
        "radius_m": effective_radius,
    }

    return final_score, breakdown

