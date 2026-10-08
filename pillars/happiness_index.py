"""
Happiness Index: 0–100 composite from existing pillar data (not a pillar).

Version 5. Weights follow docs/HAPPINESS_WEIGHTS_PROPOSAL.md; evidence and sources are in
docs/HAPPINESS_EVIDENCE_NOTES.md. A pillar carries weight only where individual-level research and
our own catalog check do not contradict each other. The weights are judgment, not a fit: county-level
fits against CDC PLACES were shown to be confounded by wealth and place type.

Components (all 0–100, renormalized over those available):
- S (Social Fabric) 0.26: relationship quality and trust are among the strongest wellbeing predictors.
- F (Safety) 0.18: strongest predictor in the catalog check; research clearer on trust than life satisfaction.
- H (Housing cost burden and space) 0.14: cost burden raises depression, mostly for renters.
- G (Natural beauty) 0.12: moving to greener areas improved mental health in panel data.
- X (Economic opportunity) 0.08: reachable jobs and market quality (individual evidence is indirect).
- A (Active outdoors) 0.07: exercise and nature contact protect against depression.
- L (Climate and air) 0.06: heat, air quality, flood and trend (higher = safer). No noise data yet.
- C (Commute) 0.05: small mood and leisure cost; also a personal score for the user's own workplace.
- N (Neighborhood amenities) 0.04: walkability raises walking; no wellbeing outcome found.
Schools, healthcare, diversity, air travel and the other pillars carry zero weight (education is still
reported in the breakdown for display).
Safety and any missing component renormalize out.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional, Tuple

# Weights (must sum to 1.0 before renormalization over available components)
W_SOCIAL = 0.26
W_SAFETY = 0.18
W_HOME = 0.14
W_GREEN = 0.12
W_ECONOMIC = 0.08
W_ACTIVE = 0.07
W_CLIMATE = 0.06
W_COMMUTE = 0.05
W_NEIGHBORHOOD = 0.04
W_EDUCATION = 0.0  # no individual-level support; still reported in the breakdown

_BASELINES_CACHE: Optional[Dict[str, Any]] = None


def _load_status_signal_baselines() -> Dict[str, Any]:
    """Reuse status_signal baselines for E (wealth_gap) peer normalization."""
    global _BASELINES_CACHE
    if _BASELINES_CACHE is not None:
        return _BASELINES_CACHE
    path = os.getenv(
        "STATUS_SIGNAL_BASELINES_PATH",
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "status_signal_baselines.json"),
    )
    if not path or not os.path.isfile(path):
        _BASELINES_CACHE = {}
        return _BASELINES_CACHE
    try:
        with open(path, "r", encoding="utf-8") as f:
            _BASELINES_CACHE = json.load(f)
    except Exception:
        _BASELINES_CACHE = {}
    return _BASELINES_CACHE


def _normalize_min_max(value: float, min_val: float, max_val: float) -> float:
    if max_val <= min_val:
        return 50.0
    x = (value - min_val) / (max_val - min_val)
    return max(0.0, min(100.0, x * 100.0))


def _get_wealth_gap_baseline(baselines: Dict[str, Any], division: str) -> Tuple[Optional[float], Optional[float]]:
    div_data = baselines.get(division) or baselines.get("all") or {}
    wealth = div_data.get("wealth", {})
    gap_block = wealth.get("wealth_gap_ratio", {})
    if isinstance(gap_block, dict) and "min" in gap_block and "max" in gap_block:
        return float(gap_block["min"]), float(gap_block["max"])
    return None, None


def _failed(details: Optional[Dict[str, Any]]) -> bool:
    """A pillar that failed to score is stored as 0 with status 'failed' / confidence 0; that is missing
    data, not a real zero, so it must renormalize out instead of dragging the index down."""
    if not details:
        return True
    if details.get("status") == "failed":
        return True
    return details.get("confidence") == 0 and details.get("score") == 0


def _component_commute(public_transit_details: Optional[Dict[str, Any]]) -> Optional[float]:
    """C: 0–100 from public_transit commute_time (already scored)."""
    if not public_transit_details:
        return None
    breakdown = public_transit_details.get("breakdown") or {}
    commute = breakdown.get("commute_time")
    if isinstance(commute, (int, float)):
        return max(0.0, min(100.0, float(commute)))
    details = public_transit_details.get("details") or {}
    commute_from_details = details.get("commute_time", {}).get("score")
    if isinstance(commute_from_details, (int, float)):
        return max(0.0, min(100.0, float(commute_from_details)))
    return None
 
def _component_social(social_fabric_details: Optional[Dict[str, Any]]) -> Optional[float]:
    """S: 0–100 = Social Fabric pillar score (neighbors, civic spaces, rootedness)."""
    if _failed(social_fabric_details):
        return None
    score = social_fabric_details.get("score")
    if isinstance(score, (int, float)):
        return max(0.0, min(100.0, float(score)))
    return None


def _component_home_space(housing_details: Optional[Dict[str, Any]]) -> Optional[float]:
    """H: 0–100 = Home Price-to-Space pillar score (more space and quality for your money)."""
    if _failed(housing_details):
        return None
    score = housing_details.get("score")
    if isinstance(score, (int, float)):
        return max(0.0, min(100.0, float(score)))
    return None


def _component_green(natural_beauty_details: Optional[Dict[str, Any]]) -> Optional[float]:
    """G: 0–100 = full Natural Beauty pillar score."""
    if _failed(natural_beauty_details):
        return None
    score = natural_beauty_details.get("score")
    if isinstance(score, (int, float)):
        return max(0.0, min(100.0, float(score)))
    return None



def _component_safety(community_safety_details: Optional[Dict[str, Any]]) -> Optional[float]:
    """F: 0–100 = Community Safety pillar score. Missing/degraded → None (renormalized out)."""
    if not community_safety_details:
        return None
    if community_safety_details.get("status") not in ("success", None):
        return None
    score = community_safety_details.get("score")
    if isinstance(score, (int, float)) and float(score) >= 0:
        return max(0.0, min(100.0, float(score)))
    return None


def _component_neighborhood(neighborhood_details: Optional[Dict[str, Any]]) -> Optional[float]:
    """N: 0–100 = Neighborhood Amenities pillar score."""
    if _failed(neighborhood_details):
        return None
    score = neighborhood_details.get("score")
    if isinstance(score, (int, float)):
        return max(0.0, min(100.0, float(score)))
    return None


def _component_score(details: Optional[Dict[str, Any]]) -> Optional[float]:
    """0–100 = a pillar's own score; missing or non-numeric → None (renormalized out)."""
    if _failed(details):
        return None
    score = details.get("score")
    if isinstance(score, (int, float)):
        return max(0.0, min(100.0, float(score)))
    return None


def _component_education(education_details: Optional[Dict[str, Any]]) -> Optional[float]:
    """E: 0–100 = Quality Education pillar score. Excluded when confidence=0 (scoring disabled)."""
    if not education_details:
        return None
    if (education_details.get("confidence") or 1) == 0:
        return None
    score = education_details.get("score")
    if isinstance(score, (int, float)):
        return max(0.0, min(100.0, float(score)))
    return None


def compute_happiness_index_with_breakdown(
    housing_details: Optional[Dict[str, Any]],
    public_transit_details: Optional[Dict[str, Any]],
    economic_opportunity_details: Optional[Dict[str, Any]],
    natural_beauty_details: Optional[Dict[str, Any]],
    state_abbrev: Optional[str],
    social_fabric_details: Optional[Dict[str, Any]] = None,
    community_safety_details: Optional[Dict[str, Any]] = None,
    neighborhood_amenities_details: Optional[Dict[str, Any]] = None,
    education_details: Optional[Dict[str, Any]] = None,
    climate_risk_details: Optional[Dict[str, Any]] = None,
    active_outdoors_details: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[float], Dict[str, Any]]:
    """
    Compute Happiness Index (0–100) and component breakdown.

    Returns (score, breakdown) with breakdown keys: social, safety, commute, neighborhood,
    home_space, green, economic, active_outdoors, climate, education (reported only, zero weight),
    and component_weights used (after renormalization for missing components).
    """
    breakdown: Dict[str, Any] = {
        "social": None,
        "safety": None,
        "commute": None,
        "neighborhood": None,
        "home_space": None,
        "green": None,
        "economic": None,
        "active_outdoors": None,
        "climate": None,
        "education": None,
        "eco_modifier": 1.0,  # retained for stored-data compatibility; the modifier was removed in v5
        "component_weights": {},
    }

    values = {
        "social": _component_social(social_fabric_details),
        "safety": _component_safety(community_safety_details),
        "home_space": _component_home_space(housing_details),
        "green": _component_green(natural_beauty_details),
        "economic": _component_score(economic_opportunity_details),
        "active_outdoors": _component_score(active_outdoors_details),
        "climate": _component_score(climate_risk_details),
        "commute": _component_commute(public_transit_details),
        "neighborhood": _component_neighborhood(neighborhood_amenities_details),
        "education": _component_education(education_details),
    }
    base_weights = {
        "social": W_SOCIAL,
        "safety": W_SAFETY,
        "home_space": W_HOME,
        "green": W_GREEN,
        "economic": W_ECONOMIC,
        "active_outdoors": W_ACTIVE,
        "climate": W_CLIMATE,
        "commute": W_COMMUTE,
        "neighborhood": W_NEIGHBORHOOD,
        "education": W_EDUCATION,
    }
    for key, val in values.items():
        breakdown[key] = round(val, 1) if val is not None else None

    used = [(key, val, base_weights[key]) for key, val in values.items() if val is not None and base_weights[key] > 0]
    if not used:
        return None, breakdown

    total_w = sum(w for _, _, w in used)
    score = sum(val * w for _, val, w in used) / total_w
    breakdown["component_weights"] = {key: round(w / total_w, 3) for key, _, w in used}
    return round(max(0.0, min(100.0, score)), 1), breakdown


def compute_happiness_index(
    housing_details: Optional[Dict[str, Any]],
    public_transit_details: Optional[Dict[str, Any]],
    economic_opportunity_details: Optional[Dict[str, Any]],
    natural_beauty_details: Optional[Dict[str, Any]],
    state_abbrev: Optional[str],
    social_fabric_details: Optional[Dict[str, Any]] = None,
    community_safety_details: Optional[Dict[str, Any]] = None,
    neighborhood_amenities_details: Optional[Dict[str, Any]] = None,
    education_details: Optional[Dict[str, Any]] = None,
    climate_risk_details: Optional[Dict[str, Any]] = None,
    active_outdoors_details: Optional[Dict[str, Any]] = None,
) -> Optional[float]:
    """Convenience: return only the score."""
    result, _ = compute_happiness_index_with_breakdown(
        housing_details,
        public_transit_details,
        economic_opportunity_details,
        natural_beauty_details,
        state_abbrev,
        social_fabric_details=social_fabric_details,
        community_safety_details=community_safety_details,
        neighborhood_amenities_details=neighborhood_amenities_details,
        education_details=education_details,
        climate_risk_details=climate_risk_details,
        active_outdoors_details=active_outdoors_details,
    )
    return result
