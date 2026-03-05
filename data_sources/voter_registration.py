"""
Voter registration helpers for Social Fabric Engagement sub-score.

Expects preprocessed JSON from scripts/build_voter_registration_baselines.py:
- tract GEOID → registration rate (0–1)
- division → {mean, std} for z-score normalization.

At runtime: lookup tract rate and stats, return (score_0_100, stats) or None.
"""

import json
import os
from typing import Dict, Optional, Tuple

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

rate_by_tract: Dict[str, float] = {}
engagement_stats_by_division: Dict[str, Dict[str, float]] = {}


def _load_json_if_exists(path: str) -> Optional[dict]:
    try:
        if not path or not os.path.exists(path):
            return None
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Failed to load voter registration JSON from %s: %s", path, e)
        return None


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


def get_voter_registration_score(
    tract: Optional[Dict],
    division_code: Optional[str] = None,
    clip_z: float = 2.5,
) -> Optional[Tuple[float, Optional[Dict[str, float]], Optional[float]]]:
    """
    Return (score_0_100, stats, registration_rate) for the tract, or None if no data.

    - score: z-score of registration_rate vs division mean/std, clipped, mapped to 0–100.
    - stats: {"mean", "std"} for the region (for summary); may be None.
    - registration_rate: raw rate 0–1 for summary; may be None.
    """
    if not rate_by_tract or not tract:
        return None

    geoid = tract.get("geoid")
    if not geoid:
        return None

    rate = rate_by_tract.get(geoid)
    if rate is None:
        return None

    if division_code is None:
        state_fips = tract.get("state_fips")
        if state_fips:
            from data_sources.us_census_divisions import get_division
            STATE_FIPS_TO_ABBREV = {
                "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO", "09": "CT",
                "10": "DE", "11": "DC", "12": "FL", "13": "GA", "15": "HI", "16": "ID", "17": "IL",
                "18": "IN", "19": "IA", "20": "KS", "21": "KY", "22": "LA", "23": "ME", "24": "MD",
                "25": "MA", "26": "MI", "27": "MN", "28": "MS", "29": "MO", "30": "MT", "31": "NE",
                "32": "NV", "33": "NH", "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND",
                "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI", "45": "SC", "46": "SD",
                "47": "TN", "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA", "54": "WV",
                "55": "WI", "56": "WY", "72": "PR",
            }
            state_abbrev = STATE_FIPS_TO_ABBREV.get(state_fips)
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
