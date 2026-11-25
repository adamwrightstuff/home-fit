"""Fail-loud blend for the social fabric pillar. No heavy imports so offline scripts and composite_indices can use it."""

from __future__ import annotations

from typing import Dict, Optional, Tuple


# DPv2 (2026-11-03, owner-approved): economic connectedness (Chetty et al. 2022, the Atlas input that predicts upward
# mobility) takes 0.20; the four earlier components keep their proportions (0.60/0.20/0.10/0.10 x 0.80).
# The 0.20 is a judgment call with plausible range 0.15 to 0.45, not a sourced value (docs/PILLAR_SOCIAL_FABRIC.md).
# v21 (2026-11-25): weight 0. EC is cross-income friendship share, not neighborly community, and it penalizes
# high-income, high-inequality places. Still computed and shown as a diagnostic.
EC_WEIGHT = 0.0
# v20 (2026-11-24): OSM civic gathering spots are shown but not scored (weight 0). Against CDC PLACES felt-connection
# measures (analysis/social_fabric_felt_validation_2026-11-24.md) they showed no relation (support +0.06, loneliness
# -0.06) and dropping them from the blend raised the match slightly. The other four v18 weights keep their proportions
# (0.48 / 0.16 / 0.08 / 0.20 divided by 0.92). Judgment call, not a sourced value.
_V18_WEIGHTS = {"participation": 0.48, "cohesion": 0.16, "rootedness": 0.08, "economic_connectedness": EC_WEIGHT}
_V18_SCORED_SUM = sum(_V18_WEIGHTS.values())
SF_BASE_WEIGHTS = {
    "participation": round(_V18_WEIGHTS["participation"] / _V18_SCORED_SUM, 4),
    "cohesion": round(_V18_WEIGHTS["cohesion"] / _V18_SCORED_SUM, 4),
    "rootedness": round(_V18_WEIGHTS["rootedness"] / _V18_SCORED_SUM, 4),
    "civic": 0.0,
    "economic_connectedness": round(_V18_WEIGHTS["economic_connectedness"] / _V18_SCORED_SUM, 4),
}


def blend_social_fabric(
    *,
    participation: Optional[float],
    cohesion: Optional[float],
    rootedness: Optional[float],
    civic: Optional[float],
    economic_connectedness: Optional[float] = None,
) -> Tuple[float, Dict[str, float], list]:
    """
    Fail-loud blend: components that are None are left out and the remaining base weights are scaled
    proportionally to sum to 1. Returns (score 0-100 rounded to 0.1, weights used, names left out).
    Raises when participation is missing or fewer than two components are present (no score).
    Shared by the live pillar, the F15 correction in composite_indices and the offline catalog recompute.
    """
    values = {"participation": participation, "cohesion": cohesion, "rootedness": rootedness, "civic": civic,
              "economic_connectedness": economic_connectedness}
    present = {k: float(v) for k, v in values.items() if v is not None}
    # A component with weight 0 (civic since v20) is a diagnostic: its absence is not a data gap.
    missing = [k for k in SF_BASE_WEIGHTS if k not in present and SF_BASE_WEIGHTS[k] > 0]
    scored = [k for k in present if SF_BASE_WEIGHTS[k] > 0]
    if "participation" not in present or len(scored) < 2:
        raise RuntimeError(f"Social fabric: not enough components to score (missing: {', '.join(missing)})")
    total = sum(SF_BASE_WEIGHTS[k] for k in present)
    weights = {k: SF_BASE_WEIGHTS[k] / total for k in present}
    score = sum(weights[k] * present[k] for k in present)
    return max(0.0, min(100.0, round(score, 1))), weights, missing
