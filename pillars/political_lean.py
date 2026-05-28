"""
Political lean pillar: 2020/2024 presidential precinct results → preference-aligned score.

Score is directional: requires political_preference ("progressive" or "conservative").
Without a declared preference, score is None and weight should be zeroed out.

Lean formula: (dem - rep) / (dem + rep), range [-1, +1].
Progressive score: (lean + 1) / 2 * 100  → 100 when all-D, 0 when all-R
Conservative score: (1 - lean) / 2 * 100 → 100 when all-R, 0 when all-D
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from data_sources.political_lean import lean_label, lookup_political_lean
from logging_config import get_logger

logger = get_logger(__name__)

VALID_POLITICAL_PREFERENCES = ("progressive", "conservative")


def parse_political_preference(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    s = str(raw).strip().lower()
    if s in VALID_POLITICAL_PREFERENCES:
        return s
    return None


def get_political_lean_score(
    lat: float,
    lon: float,
    state_abbr: Optional[str] = None,
    political_preference: Optional[str] = None,
) -> Tuple[Optional[float], Dict]:
    """
    Returns (score_0_100_or_None, details).

    score is None when no preference is declared — caller should zero out the weight.
    """
    if not state_abbr:
        return None, {"error": "no_state", "data_quality": {"confidence": 0.0}}

    pref = parse_political_preference(political_preference)

    result = lookup_political_lean(lat, lon, state_abbr)
    if result is None:
        return None, {
            "error": "no_data",
            "state": state_abbr,
            "data_quality": {"confidence": 0.0},
        }

    lean = result["lean_2024"]
    label = lean_label(lean)

    if pref == "progressive":
        score = (lean + 1.0) / 2.0 * 100.0
    elif pref == "conservative":
        score = (1.0 - lean) / 2.0 * 100.0
    else:
        score = None

    breakdown = {
        "lean_2024": result["lean_2024"],
        "lean_2020": result["lean_2020"],
        "trend": result["trend"],
        "label": label,
        "dem_pct_2024": round(result["dem_2024"] / (result["dem_2024"] + result["rep_2024"]) * 100, 1)
        if (result["dem_2024"] + result["rep_2024"]) > 0 else None,
        "rep_pct_2024": round(result["rep_2024"] / (result["dem_2024"] + result["rep_2024"]) * 100, 1)
        if (result["dem_2024"] + result["rep_2024"]) > 0 else None,
        "precinct_count": result["precinct_count"],
        "preference": pref,
    }

    return (round(score, 1) if score is not None else None), {
        "breakdown": breakdown,
        "state": state_abbr,
        "data_quality": {"confidence": 1.0 if result["precinct_count"] >= 3 else 0.6},
    }
