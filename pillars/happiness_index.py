"""
Happiness Index: 0–100 composite from existing pillar data (not a pillar).

Components (all 0–100, renormalized when missing):
- S (Social Fabric): Social Fabric pillar score. Strongest cross-study predictor of wellbeing.
- F (Safety): Community Safety pillar score. Fear of crime is a primary wellbeing drag (Loukaitou-Sideris 2006).
- C (Commute): existing commute score from public_transit (shorter = better).
- N (Neighborhood): Neighborhood Amenities pillar. Daily walkable engagement → positive affect.
- H (Home Space-to-Price): Home Price to Space pillar score.
- G (Green): Natural Beauty pillar score — daily nature contact → stress reduction (Bratman 2015).
- B (Built): Built Beauty pillar score (architecture and streetscape).

Base weights: S 0.30, F 0.20, C 0.20, N 0.12, H 0.10, G 0.05, B 0.03 (renormalized over available).
Note: Commute reduced from 0.35; Putnam's mechanism routes through social fabric (already at 30%)
so 35% double-penalized transit-dependent neighborhoods for the same social erosion pathway.
Safety added: when degraded/missing, renormalized over remaining components.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional, Tuple

# Weights (must sum to 1.0 before renormalization over available components)
W_SOCIAL = 0.30
W_SAFETY = 0.20
W_COMMUTE = 0.20
W_NEIGHBORHOOD = 0.12
W_HOME = 0.10
W_GREEN = 0.05
W_BUILT = 0.03

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
    if not social_fabric_details:
        return None
    score = social_fabric_details.get("score")
    if isinstance(score, (int, float)):
        return max(0.0, min(100.0, float(score)))
    return None


def _component_home_space(housing_details: Optional[Dict[str, Any]]) -> Optional[float]:
    """H: 0–100 = Home Price-to-Space pillar score (more space and quality for your money)."""
    if not housing_details:
        return None
    score = housing_details.get("score")
    if isinstance(score, (int, float)):
        return max(0.0, min(100.0, float(score)))
    return None


def _component_green(natural_beauty_details: Optional[Dict[str, Any]]) -> Optional[float]:
    """G: 0–100 = full Natural Beauty pillar score."""
    if not natural_beauty_details:
        return None
    score = natural_beauty_details.get("score")
    if isinstance(score, (int, float)):
        return max(0.0, min(100.0, float(score)))
    return None


def _component_built(built_environment_details: Optional[Dict[str, Any]]) -> Optional[float]:
    """B: 0–100 = full Built Beauty pillar score."""
    if not built_environment_details:
        return None
    score = built_environment_details.get("score")
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
    if isinstance(score, (int, float)) and float(score) > 0:
        return max(0.0, min(100.0, float(score)))
    return None


def _component_neighborhood(neighborhood_details: Optional[Dict[str, Any]]) -> Optional[float]:
    """N: 0–100 = Neighborhood Amenities pillar score."""
    if not neighborhood_details:
        return None
    score = neighborhood_details.get("score")
    if isinstance(score, (int, float)):
        return max(0.0, min(100.0, float(score)))
    return None


def compute_happiness_index_with_breakdown(
    housing_details: Optional[Dict[str, Any]],
    public_transit_details: Optional[Dict[str, Any]],
    economic_security_details: Optional[Dict[str, Any]],
    natural_beauty_details: Optional[Dict[str, Any]],
    state_abbrev: Optional[str],
    social_fabric_details: Optional[Dict[str, Any]] = None,
    built_environment_details: Optional[Dict[str, Any]] = None,
    community_safety_details: Optional[Dict[str, Any]] = None,
    neighborhood_amenities_details: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[float], Dict[str, Any]]:
    """
    Compute Happiness Index (0–100) and component breakdown.

    Returns (score, breakdown) with breakdown keys: social, safety, commute, neighborhood,
    home_space, green, built, and component_weights used (after renormalization for missing).
    Safety renormalizes out when degraded/missing — no place penalized for missing data.
    """
    from data_sources.us_census_divisions import get_division
    division = get_division(state_abbrev) if state_abbrev else "all"

    breakdown: Dict[str, Any] = {
        "social": None,
        "safety": None,
        "commute": None,
        "neighborhood": None,
        "home_space": None,
        "green": None,
        "built": None,
        "component_weights": {},
    }

    # Components
    S = _component_social(social_fabric_details)
    F = _component_safety(community_safety_details)
    C = _component_commute(public_transit_details)
    N = _component_neighborhood(neighborhood_amenities_details)
    H = _component_home_space(housing_details)
    G = _component_green(natural_beauty_details)
    B = _component_built(built_environment_details)

    breakdown["social"] = round(S, 1) if S is not None else None
    breakdown["safety"] = round(F, 1) if F is not None else None
    breakdown["commute"] = round(C, 1) if C is not None else None
    breakdown["neighborhood"] = round(N, 1) if N is not None else None
    breakdown["home_space"] = round(H, 1) if H is not None else None
    breakdown["green"] = round(G, 1) if G is not None else None
    breakdown["built"] = round(B, 1) if B is not None else None

    weights = []
    components = []
    if S is not None:
        weights.append(W_SOCIAL)
        components.append((S, "social"))
    if F is not None:
        weights.append(W_SAFETY)
        components.append((F, "safety"))
    if C is not None:
        weights.append(W_COMMUTE)
        components.append((C, "commute"))
    if N is not None:
        weights.append(W_NEIGHBORHOOD)
        components.append((N, "neighborhood"))
    if H is not None:
        weights.append(W_HOME)
        components.append((H, "home_space"))
    if G is not None:
        weights.append(W_GREEN)
        components.append((G, "green"))
    if B is not None:
        weights.append(W_BUILT)
        components.append((B, "built"))

    if not components:
        return None, breakdown

    total_w = sum(weights)
    score = sum(s * w for (s, _), w in zip(components, weights)) / total_w
    breakdown["component_weights"] = {k: round(w / total_w, 3) for (_, k), w in zip(components, weights)}
    final = round(max(0.0, min(100.0, score)), 1)
    return final, breakdown


def compute_happiness_index(
    housing_details: Optional[Dict[str, Any]],
    public_transit_details: Optional[Dict[str, Any]],
    economic_security_details: Optional[Dict[str, Any]],
    natural_beauty_details: Optional[Dict[str, Any]],
    state_abbrev: Optional[str],
    social_fabric_details: Optional[Dict[str, Any]] = None,
    built_environment_details: Optional[Dict[str, Any]] = None,
    community_safety_details: Optional[Dict[str, Any]] = None,
    neighborhood_amenities_details: Optional[Dict[str, Any]] = None,
) -> Optional[float]:
    """Convenience: return only the score."""
    result, _ = compute_happiness_index_with_breakdown(
        housing_details,
        public_transit_details,
        economic_security_details,
        natural_beauty_details,
        state_abbrev,
        social_fabric_details=social_fabric_details,
        built_environment_details=built_environment_details,
        community_safety_details=community_safety_details,
        neighborhood_amenities_details=neighborhood_amenities_details,
    )
    return result
