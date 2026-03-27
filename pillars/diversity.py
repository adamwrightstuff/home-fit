"""
Diversity pillar: race, income, and age mix (entropy) at tract level.
Formerly part of Social Fabric; standalone for weighting and Status Signal inputs.
"""

from __future__ import annotations

import math
from typing import Dict, Iterable, Optional, Tuple

from data_sources import census_api, data_quality
from logging_config import get_logger

logger = get_logger(__name__)


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
    if n_categories <= 1:
        return 0.0
    h = _entropy(counts)
    h_max = math.log(n_categories)
    if h_max <= 0:
        return 0.0
    return max(0.0, min(100.0, (h / h_max) * 100.0))


def get_diversity_score(
    lat: float,
    lon: float,
    area_type: Optional[str] = None,
    density: Optional[float] = None,
    city: Optional[str] = None,
) -> Tuple[float, Dict]:
    """
    Returns (score_0_100, details) with education_attainment / self_employed_pct for Status Signal.
    """
    tract = census_api.get_census_tract(lat, lon)
    if density is None:
        density = census_api.get_population_density(lat, lon) or 0.0
    if area_type is None:
        area_type = data_quality.detect_area_type(lat, lon, density=density, city=city)

    diversity_data = census_api.get_diversity_data(lat, lon, tract=tract)
    diversity_score = None
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

    if diversity_score is None:
        diversity_score = 0.0

    score = max(0.0, min(100.0, round(float(diversity_score), 1)))

    details: Dict = {
        "breakdown": {"diversity_score": score},
        "summary": {
            "diversity_entropy_score": score,
        },
        "data_quality": data_quality.assess_pillar_data_quality(
            "diversity",
            {"score": score, "diversity_score": diversity_score},
            lat,
            lon,
            area_type,
        ),
        "area_classification": {"area_type": area_type},
        "version": "v1_entropy_standalone",
    }
    if diversity_data:
        if diversity_data.get("education_attainment") is not None:
            details["education_attainment"] = diversity_data["education_attainment"]
        if diversity_data.get("self_employed_pct") is not None:
            details["self_employed_pct"] = diversity_data["self_employed_pct"]

    logger.info("Diversity Score: %s/100", score)
    return score, details
