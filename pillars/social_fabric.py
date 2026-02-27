"""
Social Fabric pillar (Phase 2B, v1).

Measures structural conditions for local belonging:
- Stability: residential rootedness (Census B07003)
- Civic gathering: civic, non-commercial third places (OSM civic nodes)

Version 1 uses Stability + Civic gathering only. Diversity (race/income/age)
and Engagement (IRS BMF) can be added later without changing the core API.
"""

from typing import Dict, Tuple, Optional

from data_sources import census_api, data_quality, osm_api
from logging_config import get_logger

logger = get_logger(__name__)


def _score_stability_from_pct(same_house_pct: float) -> float:
    """
    Convert same-house-1yr percentage (0-100) into Stability score (0-100).

    Curve (x in percentage points):
      - x <= 85: score = (x / 85) * 100
      - x > 85: score = max(0, 100 - 2 * (x - 85))
    """
    try:
        x = float(same_house_pct)
    except (TypeError, ValueError):
        return 0.0

    if x <= 0:
        return 0.0
    if x <= 85.0:
        return max(0.0, min(100.0, (x / 85.0) * 100.0))
    # Gentle penalty for "stagnation" above 85%
    score = 100.0 - 2.0 * (x - 85.0)
    return max(0.0, min(100.0, score))


def _score_civic_gathering_from_count(count_civic: int) -> float:
    """
    Simple threshold-based Civic gathering score (0-100) from civic node count.

    Thresholds (can be refined later and made area-type-aware):
      - 0 -> 0
      - 1-2 -> 40
      - 3-5 -> 70
      - 6+ -> 100
    """
    try:
        n = int(count_civic)
    except (TypeError, ValueError):
        return 0.0

    if n <= 0:
        return 0.0
    if n <= 2:
        return 40.0
    if n <= 5:
        return 70.0
    return 100.0


def get_social_fabric_score(
    lat: float,
    lon: float,
    area_type: Optional[str] = None,
    density: Optional[float] = None,
    city: Optional[str] = None,
) -> Tuple[float, Dict]:
    """
    Compute Social Fabric pillar score (v1: Stability + Civic gathering).

    Returns:
        (score_0_100, details) where details has breakdown, summary, data_quality.
    """
    # Fetch Census tract once to reuse across mobility and any future Census calls.
    tract = census_api.get_census_tract(lat, lon)

    # Stability: B07003 (same house 1 year ago)
    mobility = census_api.get_mobility_data(lat, lon, tract=tract)
    if mobility is not None:
        same_house_pct = mobility.get("same_house_pct")
        stability_score = _score_stability_from_pct(same_house_pct)
    else:
        same_house_pct = None
        stability_score = 0.0

    # Civic gathering: OSM civic nodes (library, community_centre, place_of_worship, townhall, community_garden)
    civic = osm_api.query_civic_nodes(lat, lon, radius_m=800)
    nodes = (civic or {}).get("nodes", []) if civic else []
    civic_count = len(nodes)
    civic_score = _score_civic_gathering_from_count(civic_count)

    # Combine into Social Fabric Index v1.
    # v1 uses Stability + Civic only with equal 1.2 weights (see SOCIAL_FABRIC_PRD):
    #   SFI = (1.2*S + 1.2*C) / 2.4
    total_weight = 0.0
    weighted_sum = 0.0

    # Always include both components (they are required for v1).
    total_weight += 1.2
    weighted_sum += 1.2 * stability_score

    total_weight += 1.2
    weighted_sum += 1.2 * civic_score

    score = 0.0
    if total_weight > 0:
        score = weighted_sum / total_weight
    score = max(0.0, min(100.0, round(score, 1)))

    # Area type for data_quality / context
    if density is None:
        density = census_api.get_population_density(lat, lon) or 0.0
    if area_type is None:
        area_type = data_quality.detect_area_type(lat, lon, density=density, city=city)

    combined_data = {
        "stability_score": stability_score,
        "civic_score": civic_score,
        "score": score,
        "mobility": mobility,
        "civic_nodes_count": civic_count,
    }

    quality_metrics = data_quality.assess_pillar_data_quality(
        "social_fabric", combined_data, lat, lon, area_type
    )

    breakdown = {
        "stability": stability_score,
        "civic_gathering": civic_score,
        # Placeholders for future sub-indices
        "diversity": None,
        "engagement": None,
    }

    summary = {
        "same_house_pct": round(same_house_pct, 1) if same_house_pct is not None else None,
        "civic_node_count_800m": civic_count,
        "diversity_available": False,
        "engagement_available": False,
    }

    details = {
        "breakdown": breakdown,
        "summary": summary,
        "data_quality": quality_metrics,
        "area_classification": {"area_type": area_type},
        "version": "v1_stability_plus_civic",
    }

    logger.info(
        "Social Fabric Score: %s/100 (stability=%s, civic=%s, civic_nodes=%s)",
        score,
        stability_score,
        civic_score,
        civic_count,
    )
    return score, details

