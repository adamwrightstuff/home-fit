"""
Voter turnout for Social Fabric engagement (z-score vs area-type baselines).

Uses tract-level rates from data/voter_turnout_tract_rates.json when present;
otherwise falls back to voter_registration_tract_rates.json (same schema).
Stats: data/voter_turnout_stats_by_area_type.json (mean/std per morphological area_type).
"""

import json
import os
from typing import Dict, Optional, Tuple

from logging_config import get_logger

logger = get_logger(__name__)

_BASE_DIR = os.path.dirname(os.path.dirname(__file__))
_DEFAULT_DATA_DIR = os.path.join(_BASE_DIR, "data")

_TURNOUT_RATES_PATH = os.getenv(
    "VOTER_TURNOUT_TRACT_RATES_PATH",
    os.path.join(_DEFAULT_DATA_DIR, "voter_turnout_tract_rates.json"),
)
_FALLBACK_RATES_PATH = os.getenv(
    "VOTER_REGISTRATION_TRACT_RATES_PATH",
    os.path.join(_DEFAULT_DATA_DIR, "voter_registration_tract_rates.json"),
)
_STATS_BY_AREA_PATH = os.getenv(
    "VOTER_TURNOUT_STATS_BY_AREA_TYPE_PATH",
    os.path.join(_DEFAULT_DATA_DIR, "voter_turnout_stats_by_area_type.json"),
)

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


def _load_json(path: str) -> Optional[dict]:
    try:
        if path and os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.warning("Failed to load JSON from %s: %s", path, e)
    return None


rate_by_tract: Dict[str, float] = {}
stats_by_area_type: Dict[str, Dict[str, float]] = {}
state_rate_by_fips: Dict[str, float] = {}

_raw = _load_json(_TURNOUT_RATES_PATH) or _load_json(_FALLBACK_RATES_PATH) or {}
if isinstance(_raw, dict):
    rate_by_tract = {str(k): float(v) for k, v in _raw.items() if isinstance(v, (int, float))}
    if rate_by_tract:
        logger.info("Loaded voter turnout rates for %d tracts", len(rate_by_tract))

_stats_raw = _load_json(_STATS_BY_AREA_PATH) or {}
if isinstance(_stats_raw, dict):
    stats_by_area_type = {
        str(k): {"mean": float(v.get("mean", 0.0)), "std": float(v.get("std", 0.0))}
        for k, v in _stats_raw.items()
        if isinstance(v, dict)
    }
    if stats_by_area_type:
        logger.info("Loaded turnout stats for %d area-type keys", len(stats_by_area_type))

_state_path = os.path.join(_DEFAULT_DATA_DIR, "state_registration_rates.json")
_state_raw = _load_json(_state_path) or {}
if isinstance(_state_raw, dict):
    state_rate_by_fips = {str(k): float(v) for k, v in _state_raw.items() if isinstance(v, (int, float))}


def _z_to_score(z: float, clip_z: float = 2.5) -> float:
    z = max(-clip_z, min(clip_z, z))
    return max(0.0, min(100.0, ((z + clip_z) / (2 * clip_z)) * 100.0))


def get_voter_turnout_score(
    tract: Optional[Dict],
    area_type: Optional[str] = None,
    clip_z: float = 2.5,
) -> Optional[Tuple[float, Optional[Dict[str, float]], Optional[float]]]:
    """
    Return (score_0_100, stats_used, turnout_rate) or None.
    Rate is 0–1 (same convention as registration when using fallback data).
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

    at = (area_type or "default").lower().replace(" ", "_")
    stats = None
    if stats_by_area_type:
        stats = stats_by_area_type.get(at) or stats_by_area_type.get("default") or stats_by_area_type.get("all")
    if not stats or stats.get("std", 0) <= 0:
        return None

    mean = stats["mean"]
    std = stats["std"]
    z = (float(rate) - mean) / std
    return (_z_to_score(z, clip_z), stats, rate)
