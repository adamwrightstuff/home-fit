"""
Diversity pillar: race, income, and age mix (entropy) at tract level.
Formerly part of Social Fabric; standalone for weighting and Status Signal inputs.
"""

from __future__ import annotations

import json
import math
from typing import Any, Dict, Iterable, List, Optional, Tuple

from data_sources import census_api, data_quality
from logging_config import get_logger

logger = get_logger(__name__)

# Optional request weighting: which Census mix dimensions to emphasize (default: average all available).
VALID_DIVERSITY_PREFERENCE: Tuple[str, ...] = ("race", "income", "age")


def parse_diversity_preference(raw: Optional[Any]) -> Optional[List[str]]:
    """
    Parse JSON array or list of dimension keys: race, income, age.
    Returns None to mean "use default (average all available dimensions)".
    Returns a non-empty ordered-unique list if the client requested specific dimensions.
    """
    if raw is None:
        return None
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return None
        try:
            raw = json.loads(s)
        except json.JSONDecodeError:
            return None
    if not isinstance(raw, list) or not raw:
        return None
    out: List[str] = []
    for x in raw:
        key = str(x).strip().lower()
        if key in VALID_DIVERSITY_PREFERENCE and key not in out:
            out.append(key)
    return out if out else None


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
    diversity_preference: Optional[List[str]] = None,
) -> Tuple[float, Dict]:
    """
    Returns (score_0_100, details) with education_attainment / self_employed_pct for Status Signal.

    diversity_preference: optional list of "race", "income", "age" to weight the headline score
    (mean of selected dimensions that have data). None = average all available (legacy behavior).
    """
    tract = census_api.get_census_tract(lat, lon)
    if density is None:
        density = census_api.get_population_density(lat, lon) or 0.0
    if area_type is None:
        area_type = data_quality.detect_area_type(lat, lon, density=density, city=city)

    diversity_data = census_api.get_diversity_data(lat, lon, tract=tract)
    diversity_score: Optional[float] = None
    components_present: list[str] = []
    breakdown: Dict = {}
    if diversity_data:
        race_counts = diversity_data.get("race_counts") or {}
        income_counts = diversity_data.get("income_counts") or {}
        age_counts_dict = diversity_data.get("age_counts") or {}
        if race_counts:
            n_race = sum(1 for v in race_counts.values() if v > 0)
            if n_race >= 2:
                race_e = _normalized_entropy(race_counts.values(), n_race)
                components_present.append("race")
                breakdown["race_entropy"] = round(race_e, 1)
        if income_counts:
            n_inc = sum(1 for v in income_counts.values() if v > 0)
            if n_inc >= 2:
                inc_e = _normalized_entropy(income_counts.values(), n_inc)
                components_present.append("income")
                breakdown["income_entropy"] = round(inc_e, 1)
        youth = age_counts_dict.get("youth", 0)
        prime = age_counts_dict.get("prime", 0)
        seniors = age_counts_dict.get("seniors", 0)
        if youth + prime + seniors > 0:
            age_e = _normalized_entropy([youth, prime, seniors], 3)
            components_present.append("age")
            breakdown["age_entropy"] = round(age_e, 1)

        by_dim: Dict[str, float] = {}
        if "race" in components_present and breakdown.get("race_entropy") is not None:
            by_dim["race"] = float(breakdown["race_entropy"])
        if "income" in components_present and breakdown.get("income_entropy") is not None:
            by_dim["income"] = float(breakdown["income_entropy"])
        if "age" in components_present and breakdown.get("age_entropy") is not None:
            by_dim["age"] = float(breakdown["age_entropy"])

        pref = parse_diversity_preference(diversity_preference)
        if by_dim:
            if pref:
                selected_vals = [by_dim[k] for k in pref if k in by_dim]
                if selected_vals:
                    diversity_score = sum(selected_vals) / len(selected_vals)
                else:
                    diversity_score = 0.0
            else:
                diversity_score = sum(by_dim.values()) / len(by_dim)

    if diversity_score is None:
        diversity_score = 0.0

    score = max(0.0, min(100.0, round(float(diversity_score), 1)))
    breakdown["diversity_score"] = score

    pref_parsed = parse_diversity_preference(diversity_preference)
    details: Dict = {
        "breakdown": breakdown,
        "summary": {
            "diversity_entropy_score": score,
            "components_included": components_present,
            "diversity_preference": pref_parsed,
            "diversity_score_mode": (
                "selected_dimensions" if pref_parsed else "all_dimensions_available"
            ),
        },
        "data_quality": data_quality.assess_pillar_data_quality(
            "diversity",
            {
                "diversity_data_loaded": bool(diversity_data),
                "components_present": components_present,
            },
            lat,
            lon,
            area_type,
        ),
        "area_classification": {"area_type": area_type},
        "version": "v2_preference_optional",
    }
    if diversity_data:
        if diversity_data.get("education_attainment") is not None:
            details["education_attainment"] = diversity_data["education_attainment"]
        if diversity_data.get("self_employed_pct") is not None:
            details["self_employed_pct"] = diversity_data["self_employed_pct"]

    logger.info("Diversity Score: %s/100", score)
    return score, details
