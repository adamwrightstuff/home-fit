"""
Social Fabric pillar (Phase 2B).

Measures structural conditions for local belonging:
- Stability: residential rootedness (Census B07003)
- Diversity: race / income / age mix (Census B02001, B19001, B01001)
- Civic gathering: civic, non-commercial third places (OSM civic nodes)
- Engagement: civic org density (IRS BMF; optional, when data is available)

When some sub-indices are unavailable (e.g. no BMF data), the pillar
renormalizes over the available components so the combined score remains
in [0, 100].
"""

from typing import Dict, Tuple, Optional, Iterable
import json
import math
import os

from data_sources import census_api, data_quality, osm_api
from data_sources import irs_bmf
from logging_config import get_logger

logger = get_logger(__name__)

# State FIPS to 2-letter abbreviation (for division lookup from tract)
_STATE_FIPS_TO_ABBREV = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO", "09": "CT",
    "10": "DE", "11": "DC", "12": "FL", "13": "GA", "15": "HI", "16": "ID", "17": "IL",
    "18": "IN", "19": "IA", "20": "KS", "21": "KY", "22": "LA", "23": "ME", "24": "MD",
    "25": "MA", "26": "MI", "27": "MN", "28": "MS", "29": "MO", "30": "MT", "31": "NE",
    "32": "NV", "33": "NH", "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND",
    "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI", "45": "SC", "46": "SD",
    "47": "TN", "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA", "54": "WV",
    "55": "WI", "56": "WY", "72": "PR",
}

# Optional regional stability baselines: {division: {"mean": float, "std": float}}
# Built by scripts/build_stability_baselines.py. When present, stability uses z-score vs region.
_stability_baselines_path = os.getenv(
    "STABILITY_BASELINES_PATH",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "stability_baselines.json"),
)
_stability_baselines: Dict[str, Dict[str, float]] = {}
if _stability_baselines_path and os.path.isfile(_stability_baselines_path):
    try:
        with open(_stability_baselines_path, "r") as f:
            raw = json.load(f)
        for k, v in (raw or {}).items():
            if isinstance(v, dict) and "mean" in v and "std" in v:
                _stability_baselines[str(k)] = {"mean": float(v["mean"]), "std": float(v["std"])}
        if _stability_baselines:
            logger.info("Loaded stability baselines for %d regions", len(_stability_baselines))
    except Exception as e:
        logger.warning("Failed to load stability baselines from %s: %s", _stability_baselines_path, e)


def _score_stability_from_pct(same_house_pct: float) -> float:
    """
    Convert same-house-1yr percentage (0-100) into Stability score (0-100).
    Fixed curve (used when regional baselines are not available).

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


def _score_stability_from_z(same_house_pct: float, mean: float, std: float, clip_z: float = 2.5) -> float:
    """
    Regional stability: z-score of same_house_pct vs division mean/std, mapped to 0-100.
    Higher same_house_pct than region average → higher score (more rooted).
    """
    try:
        x = float(same_house_pct)
    except (TypeError, ValueError):
        return 0.0
    if std <= 0:
        return _score_stability_from_pct(x)
    z = (x - mean) / std
    z = max(-clip_z, min(clip_z, z))
    # Map [-clip_z, +clip_z] → [0, 100]
    return max(0.0, min(100.0, ((z + clip_z) / (2 * clip_z)) * 100.0))


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


def _score_civic_proximity_from_count(count_civic: int) -> float:
    """
    Softer curve for civic nodes found in 1500m "proximity" radius (drive vs walk).
    Same shape as density but slightly lower so "1 place at 1.5km" < "1 place at 800m".
    """
    try:
        n = int(count_civic)
    except (TypeError, ValueError):
        return 0.0

    if n <= 0:
        return 0.0
    if n <= 2:
        return 30.0
    if n <= 5:
        return 55.0
    return 85.0


def _entropy(counts: Iterable[int]) -> float:
    total = sum(c for c in counts if c is not None)
    if total <= 0:
        return 0.0
    h = 0.0
    for c in counts:
        if c is None or c <= 0:
            continue
        p = c / total
        h -= p * math.log(p)
    return h


def _normalized_entropy(counts: Iterable[int], n_categories: int) -> float:
    """Shannon entropy normalized to 0–100."""
    if n_categories <= 1:
        return 0.0
    h = _entropy(counts)
    h_max = math.log(n_categories)
    if h_max <= 0:
        return 0.0
    return max(0.0, min(100.0, (h / h_max) * 100.0))


def _score_engagement_from_rate(orgs_per_1k: float, mean: float, std: float, clip_z: float = 2.5) -> float:
    """
    Normalize civic org density (orgs per 1k) to a 0–100 Engagement score using a
    clipped z-score vs regional (division/CBSA) stats.
    """
    try:
        v = float(orgs_per_1k)
    except (TypeError, ValueError):
        return 0.0
    if std <= 0:
        return 0.0

    z = (v - mean) / std
    if z > clip_z:
        z = clip_z
    elif z < -clip_z:
        z = -clip_z

    # Map [-clip_z, +clip_z] → [0, 100]
    score = ((z + clip_z) / (2 * clip_z)) * 100.0
    return max(0.0, min(100.0, score))


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

    # Stability: B07003 — use rooted_pct (same house + same county) so local moves don't count as churn.
    # Use regional z-score when baselines exist; else fixed curve.
    mobility = census_api.get_mobility_data(lat, lon, tract=tract)
    if mobility is not None:
        same_house_pct = mobility.get("same_house_pct")
        rooted_pct = mobility.get("rooted_pct")  # same house + moved within same county
        stability_pct = rooted_pct if rooted_pct is not None else same_house_pct
        if stability_pct is not None:
            from data_sources.us_census_divisions import get_division
            division_code = None
            if tract:
                state_fips = tract.get("state_fips")
                state_abbrev = _STATE_FIPS_TO_ABBREV.get(state_fips) if state_fips else None
                if state_abbrev:
                    division_code = get_division(state_abbrev)
            baseline = None
            if division_code and _stability_baselines:
                baseline = _stability_baselines.get(division_code) or _stability_baselines.get("all")
            if baseline:
                stability_score = _score_stability_from_z(
                    stability_pct, baseline["mean"], baseline["std"]
                )
            else:
                stability_score = _score_stability_from_pct(stability_pct)
        else:
            stability_score = 0.0
    else:
        same_house_pct = None
        rooted_pct = None
        stability_score = 0.0

    # Diversity: Race, Income, Age entropy
    diversity_score = None
    diversity_data = census_api.get_diversity_data(lat, lon, tract=tract)
    if diversity_data:
        race_counts = diversity_data.get("race_counts") or {}
        income_counts = diversity_data.get("income_counts") or {}
        age_counts_dict = diversity_data.get("age_counts") or {}

        components = []

        if race_counts:
            n_race = sum(1 for v in race_counts.values() if v > 0)
            if n_race >= 2:
                components.append(_normalized_entropy(race_counts.values(), n_race))

        if income_counts:
            n_inc = sum(1 for v in income_counts.values() if v > 0)
            if n_inc >= 2:
                components.append(_normalized_entropy(income_counts.values(), n_inc))

        youth = age_counts_dict.get("youth", 0)
        prime = age_counts_dict.get("prime", 0)
        seniors = age_counts_dict.get("seniors", 0)
        if youth + prime + seniors > 0:
            components.append(_normalized_entropy([youth, prime, seniors], 3))

        if components:
            diversity_score = sum(components) / len(components)

    # Civic gathering: OSM civic nodes (library, community_centre, place_of_worship, townhall, community_garden)
    # If 800m returns 0, expand to 1500m and use "Proximity" score so it doesn't feel broken.
    civic = osm_api.query_civic_nodes(lat, lon, radius_m=800)
    nodes = (civic or {}).get("nodes", []) if civic else []
    civic_count = len(nodes)
    civic_radius_m = 800
    civic_score_type = "density"  # walking distance
    if civic_count == 0:
        civic_expanded = osm_api.query_civic_nodes(lat, lon, radius_m=1500)
        nodes_expanded = (civic_expanded or {}).get("nodes", []) if civic_expanded else []
        if nodes_expanded:
            civic_count = len(nodes_expanded)
            civic_radius_m = 1500
            civic_score_type = "proximity"  # ~1 mi / short drive
            civic_score = _score_civic_proximity_from_count(civic_count)
        else:
            civic_score = _score_civic_gathering_from_count(0)
    else:
        civic_score = _score_civic_gathering_from_count(civic_count)

    # Engagement: IRS BMF civic org density (optional; requires preprocessed data)
    engagement_score = None
    orgs_per_1k = None
    engagement_stats = None
    # Try to use division code from tract metadata if available
    division_code = None
    # (Could be extended later to infer division from state_fips)
    bmf_result = irs_bmf.get_civic_orgs_per_1k(lat, lon, tract=tract)
    if bmf_result is not None:
        orgs_per_1k, engagement_stats = bmf_result
        if engagement_stats and orgs_per_1k is not None:
            mean = engagement_stats.get("mean", 0.0)
            std = engagement_stats.get("std", 0.0)
            engagement_score = _score_engagement_from_rate(orgs_per_1k, mean, std)

    # Combine into Social Fabric Index.
    # Weights: Stability 1.2, Civic 1.2, Diversity 1.0, Engagement 1.0 (when present).
    weights = []
    values = []

    # Stability (always)
    weights.append(1.2)
    values.append(stability_score)

    # Civic (always)
    weights.append(1.2)
    values.append(civic_score)

    # Diversity
    if diversity_score is not None:
        weights.append(1.0)
        values.append(diversity_score)

    # Engagement
    if engagement_score is not None:
        weights.append(1.0)
        values.append(engagement_score)

    if weights:
        total_weight = sum(weights)
        weighted_sum = sum(w * v for w, v in zip(weights, values))
        score = weighted_sum / total_weight
    else:
        score = 0.0

    score = max(0.0, min(100.0, round(score, 1)))

    # Area type for data_quality / context
    if density is None:
        density = census_api.get_population_density(lat, lon) or 0.0
    if area_type is None:
        area_type = data_quality.detect_area_type(lat, lon, density=density, city=city)

    combined_data = {
        "stability_score": stability_score,
        "civic_score": civic_score,
        "diversity_score": diversity_score,
        "engagement_score": engagement_score,
        "score": score,
        "mobility": mobility,
        "civic_nodes_count": civic_count,
        "orgs_per_1k": orgs_per_1k,
    }

    quality_metrics = data_quality.assess_pillar_data_quality(
        "social_fabric", combined_data, lat, lon, area_type
    )

    breakdown = {
        "stability": stability_score,
        "civic_gathering": civic_score,
        "diversity": diversity_score,
        "engagement": engagement_score,
    }

    summary = {
        "same_house_pct": round(same_house_pct, 1) if same_house_pct is not None else None,
        "rooted_pct": round(rooted_pct, 1) if rooted_pct is not None else None,
        "civic_node_count_800m": civic_count if civic_radius_m == 800 else 0,
        "civic_node_count_1500m": civic_count if civic_radius_m == 1500 else None,
        "civic_radius_m": civic_radius_m,
        "civic_score_type": civic_score_type,
        "diversity_available": diversity_score is not None,
        "engagement_available": engagement_score is not None,
        "orgs_per_1k": orgs_per_1k,
    }

    details = {
        "breakdown": breakdown,
        "summary": summary,
        "data_quality": quality_metrics,
        "area_classification": {"area_type": area_type},
        "version": "v2_stability_diversity_civic_engagement",
    }

    logger.info(
        "Social Fabric Score: %s/100 (stability=%s, civic=%s, diversity=%s, engagement=%s, civic_nodes=%s, orgs_per_1k=%s)",
        score,
        stability_score,
        civic_score,
        diversity_score,
        engagement_score,
        civic_count,
        orgs_per_1k,
    )
    return score, details

