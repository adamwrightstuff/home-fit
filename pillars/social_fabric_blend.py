"""Fail-loud blend for the social fabric pillar. No heavy imports so offline scripts and composite_indices can use it."""

from __future__ import annotations

from typing import Dict, Optional, Tuple


# DPv2 (2026-11-03, owner-approved): economic connectedness (Chetty et al. 2022, the Atlas input that predicts upward
# mobility) takes 0.20; the four earlier components keep their proportions (0.60/0.20/0.10/0.10 x 0.80).
# The 0.20 is a judgment call with plausible range 0.15 to 0.45, not a sourced value (docs/PILLAR_SOCIAL_FABRIC.md).
EC_WEIGHT = 0.20
SF_BASE_WEIGHTS = {
    "participation": round(0.60 * (1 - EC_WEIGHT), 4),
    "cohesion": round(0.20 * (1 - EC_WEIGHT), 4),
    "rootedness": round(0.10 * (1 - EC_WEIGHT), 4),
    "civic": round(0.10 * (1 - EC_WEIGHT), 4),
    "economic_connectedness": EC_WEIGHT,
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
    missing = [k for k in SF_BASE_WEIGHTS if k not in present]
    if "participation" not in present or len(present) < 2:
        raise RuntimeError(f"Social fabric: not enough components to score (missing: {', '.join(missing)})")
    total = sum(SF_BASE_WEIGHTS[k] for k in present)
    weights = {k: SF_BASE_WEIGHTS[k] / total for k in present}
    score = sum(weights[k] * present[k] for k in present)
    return max(0.0, min(100.0, round(score, 1))), weights, missing
