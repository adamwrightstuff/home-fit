"""
Happiness Index: 0–100 composite from existing pillar data (not a pillar).

Components (all 0–100, renormalized when missing):
- C (Commute): existing commute score from public_transit (shorter = better).
- H (Housing): 2 × local_affordability from housing_value (price-to-income).
- U (Unemployment): baseline-normalized unemployment (division × area_bucket), inverted.
- E (Equality): peer-normalized wealth gap (mean vs median) from status_signal baselines; higher gap = lower E.
- G (Green): full Natural Beauty pillar score (canopy, parks, water, scenery).

Weights: C 0.25, H 0.25, U 0.20, E 0.15, G 0.15.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional, Tuple

# Weights (must sum to 1.0)
W_COMMUTE = 0.25
W_HOUSING = 0.25
W_UNEMPLOYMENT = 0.20
W_EQUALITY = 0.15
W_GREEN = 0.15

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


def _component_housing(housing_details: Optional[Dict[str, Any]]) -> Optional[float]:
    """H: 0–100 = 2 × local_affordability (0–50)."""
    if not housing_details:
        return None
    breakdown = housing_details.get("breakdown") or {}
    aff = breakdown.get("local_affordability")
    if isinstance(aff, (int, float)):
        return max(0.0, min(100.0, 2.0 * float(aff)))
    return None


def _component_unemployment(
    economic_security_details: Optional[Dict[str, Any]],
) -> Optional[float]:
    """U: 0–100 from baseline-normalized unemployment (inverted: lower unemp = higher U)."""
    if not economic_security_details:
        return None
    summary = economic_security_details.get("summary") or {}
    rate = summary.get("unemployment_rate_pct")
    division = summary.get("division")
    area_bucket = summary.get("area_bucket")
    if not isinstance(rate, (int, float)) or division is None or area_bucket is None:
        return None
    try:
        from data_sources.normalization import normalize_metric_to_0_100
        u = normalize_metric_to_0_100(
            metric="unemployment_rate",
            value=float(rate),
            division=str(division),
            area_bucket=str(area_bucket),
            invert=True,
        )
        return u
    except Exception:
        # Fallback: wider band so 4–8% doesn't cluster at 85–95
        r = float(rate)
        if r <= 2.0:
            return 100.0
        if r >= 10.0:
            return 0.0
        return max(0.0, min(100.0, 100.0 - (r - 2.0) * (100.0 / 8.0)))


def _component_equality(
    housing_details: Optional[Dict[str, Any]],
    division: str,
) -> Optional[float]:
    """E: 0–100 from peer-normalized wealth gap (higher gap = lower E)."""
    if not housing_details:
        return None
    summary = housing_details.get("summary") or housing_details
    mean_income = summary.get("mean_household_income")
    median_income = summary.get("median_household_income")
    if median_income is None or not isinstance(median_income, (int, float)) or median_income <= 0:
        return None
    if mean_income is None or not isinstance(mean_income, (int, float)):
        mean_income = median_income
    gap = (float(mean_income) - float(median_income)) / float(median_income)

    baselines = _load_status_signal_baselines()
    min_gap, max_gap = _get_wealth_gap_baseline(baselines, division)
    if min_gap is not None and max_gap is not None:
        # Peer-normalized: higher gap → lower score
        n = _normalize_min_max(gap, min_gap, max_gap)
        return max(0.0, min(100.0, 100.0 - n))
    # Fallback: absolute band so high-cost metros don't all hit 0
    return max(0.0, min(100.0, 100.0 - 100.0 * gap))


def _component_green(natural_beauty_details: Optional[Dict[str, Any]]) -> Optional[float]:
    """G: 0–100 = full Natural Beauty pillar score."""
    if not natural_beauty_details:
        return None
    score = natural_beauty_details.get("score")
    if isinstance(score, (int, float)):
        return max(0.0, min(100.0, float(score)))
    return None


def compute_happiness_index_with_breakdown(
    housing_details: Optional[Dict[str, Any]],
    public_transit_details: Optional[Dict[str, Any]],
    economic_security_details: Optional[Dict[str, Any]],
    natural_beauty_details: Optional[Dict[str, Any]],
    state_abbrev: Optional[str],
) -> Tuple[Optional[float], Dict[str, Any]]:
    """
    Compute Happiness Index (0–100) and component breakdown.

    Returns (score, breakdown) with breakdown keys: commute, housing, unemployment, equality, green,
    and component_weights used (after renormalization for missing components).
    """
    from data_sources.us_census_divisions import get_division
    division = get_division(state_abbrev) if state_abbrev else "all"

    breakdown: Dict[str, Any] = {
        "commute": None,
        "housing": None,
        "unemployment": None,
        "equality": None,
        "green": None,
        "component_weights": {},
    }

    C = _component_commute(public_transit_details)
    H = _component_housing(housing_details)
    U = _component_unemployment(economic_security_details)
    E = _component_equality(housing_details, division)
    G = _component_green(natural_beauty_details)

    breakdown["commute"] = round(C, 1) if C is not None else None
    breakdown["housing"] = round(H, 1) if H is not None else None
    breakdown["unemployment"] = round(U, 1) if U is not None else None
    breakdown["equality"] = round(E, 1) if E is not None else None
    breakdown["green"] = round(G, 1) if G is not None else None

    weights = []
    components = []
    if C is not None:
        weights.append(W_COMMUTE)
        components.append((C, "commute"))
    if H is not None:
        weights.append(W_HOUSING)
        components.append((H, "housing"))
    if U is not None:
        weights.append(W_UNEMPLOYMENT)
        components.append((U, "unemployment"))
    if E is not None:
        weights.append(W_EQUALITY)
        components.append((E, "equality"))
    if G is not None:
        weights.append(W_GREEN)
        components.append((G, "green"))

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
) -> Optional[float]:
    """Convenience: return only the score."""
    result, _ = compute_happiness_index_with_breakdown(
        housing_details,
        public_transit_details,
        economic_security_details,
        natural_beauty_details,
        state_abbrev,
    )
    return result
