"""
Voter registration helpers for Social Fabric Engagement sub-score.

Uses (in order):
1. Preprocessed tract-level JSON from scripts/build_voter_registration_baselines.py
   (tract GEOID → registration rate 0–1, division → {mean, std}).
2. Fallback: state-level registration rates from data/state_registration_rates.json
   (state FIPS → rate 0–1). Division stats are computed from state rates at load time.
   No CSV or build step required—engagement works out of the box.

At runtime: lookup tract (or state) rate and stats, return (score_0_100, stats, rate) or None.
"""

import json
import math
import os
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from logging_config import get_logger

logger = get_logger(__name__)

_BASE_DIR = os.path.dirname(os.path.dirname(__file__))
_DEFAULT_DATA_DIR = os.path.join(_BASE_DIR, "data")

_RATES_PATH = os.getenv(
    "VOTER_REGISTRATION_TRACT_RATES_PATH",
    os.path.join(_DEFAULT_DATA_DIR, "voter_registration_tract_rates.json"),
)
_STATS_PATH = os.getenv(
    "VOTER_REGISTRATION_ENGAGEMENT_STATS_PATH",
    os.path.join(_DEFAULT_DATA_DIR, "voter_registration_engagement_stats.json"),
)
_STATE_RATES_PATH = os.getenv(
    "VOTER_REGISTRATION_STATE_RATES_PATH",
    os.path.join(_DEFAULT_DATA_DIR, "state_registration_rates.json"),
)

# State FIPS (2-digit) → 2-letter abbreviation
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

rate_by_tract: Dict[str, float] = {}
engagement_stats_by_division: Dict[str, Dict[str, float]] = {}
state_rate_by_fips: Dict[str, float] = {}


def _load_json_if_exists(path: str) -> Optional[dict]:
    try:
        if not path or not os.path.exists(path):
            return None
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Failed to load voter registration JSON from %s: %s", path, e)
        return None


def _mean_std(values: List[float]) -> Tuple[float, float]:
    n = len(values)
    if n <= 0:
        return float("nan"), float("nan")
    mean = sum(values) / n
    var = sum((x - mean) ** 2 for x in values) / n
    return mean, math.sqrt(var)


_rates_data = _load_json_if_exists(_RATES_PATH) or {}
if isinstance(_rates_data, dict):
    rate_by_tract = {str(k): float(v) for k, v in _rates_data.items() if isinstance(v, (int, float))}
    if rate_by_tract:
        logger.info("Loaded voter registration rates for %d tracts", len(rate_by_tract))

_stats_data = _load_json_if_exists(_STATS_PATH) or {}
if isinstance(_stats_data, dict):
    engagement_stats_by_division = {
        str(k): {"mean": float(v.get("mean", 0.0)), "std": float(v.get("std", 0.0))}
        for k, v in _stats_data.items()
        if isinstance(v, dict)
    }
    if engagement_stats_by_division:
        logger.info(
            "Loaded voter registration engagement stats for %d regions",
            len(engagement_stats_by_division),
        )

# State-level fallback: when tract-level data is missing, use state rates (no build step).
_state_data = _load_json_if_exists(_STATE_RATES_PATH) or {}
if isinstance(_state_data, dict):
    state_rate_by_fips = {str(k): float(v) for k, v in _state_data.items() if isinstance(v, (int, float))}
    if state_rate_by_fips:
        logger.info("Loaded state-level voter registration rates for %d states", len(state_rate_by_fips))
        # If we don't have division stats from tract build, compute from state rates.
        if not engagement_stats_by_division:
            from data_sources.us_census_divisions import get_division
            division_values: Dict[str, List[float]] = defaultdict(list)
            for state_fips, rate in state_rate_by_fips.items():
                state_abbrev = _STATE_FIPS_TO_ABBREV.get(state_fips)
                div = get_division(state_abbrev) if state_abbrev else "unknown"
                division_values[div].append(rate)
            for division, vals in division_values.items():
                if not vals:
                    continue
                mean, std = _mean_std(vals)
                if std > 0:
                    engagement_stats_by_division[division] = {"mean": mean, "std": std}
            all_vals = [r for r in state_rate_by_fips.values() if isinstance(r, (int, float))]
            if all_vals:
                mean_all, std_all = _mean_std(all_vals)
                if std_all > 0:
                    engagement_stats_by_division["all"] = {"mean": mean_all, "std": std_all}
            logger.info(
                "Computed engagement stats from state rates for %d divisions",
                len(engagement_stats_by_division),
            )


def get_voter_registration_score(
    tract: Optional[Dict],
    division_code: Optional[str] = None,
    clip_z: float = 2.5,
) -> Optional[Tuple[float, Optional[Dict[str, float]], Optional[float]]]:
    """
    Return (score_0_100, stats, registration_rate) for the tract, or None if no data.

    Uses tract-level rate if available, else state-level rate from state_registration_rates.json.
    - score: z-score of registration_rate vs division mean/std, clipped, mapped to 0–100.
    - stats: {"mean", "std"} for the region (for summary); may be None.
    - registration_rate: raw rate 0–1 for summary; may be None.
    """
    if not tract:
        return None

    geoid = tract.get("geoid")
    state_fips = tract.get("state_fips")

    rate = None
    if geoid and rate_by_tract:
        rate = rate_by_tract.get(geoid)
    if rate is None and state_fips and state_rate_by_fips:
        rate = state_rate_by_fips.get(state_fips)

    if rate is None:
        return None

    if division_code is None and state_fips:
        from data_sources.us_census_divisions import get_division
        state_abbrev = _STATE_FIPS_TO_ABBREV.get(state_fips)
        division_code = get_division(state_abbrev) if state_abbrev else None

    stats = None
    if division_code and engagement_stats_by_division:
        stats = engagement_stats_by_division.get(division_code)
        if stats is None:
            stats = engagement_stats_by_division.get("all")

    if not stats or stats.get("std", 0) <= 0:
        return None

    mean = stats["mean"]
    std = stats["std"]
    z = (float(rate) - mean) / std
    z = max(-clip_z, min(clip_z, z))
    score = ((z + clip_z) / (2 * clip_z)) * 100.0
    score = max(0.0, min(100.0, score))
    return (score, stats, rate)
