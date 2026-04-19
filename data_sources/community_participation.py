"""
Community participation sub-score for Social Fabric (breakdown.engagement).

Combines: refined IRS BMF (40%), CPS/AmeriCorps-style volunteering proxy by state (40%),
precinct or tract voter turnout (20%). Missing-data rules per product spec.
"""

from __future__ import annotations

import json
import math
import os
from typing import Any, Dict, Optional, Tuple

from data_sources import irs_bmf
from data_sources import voter_turnout
from logging_config import get_logger

logger = get_logger(__name__)

_BASE_DIR = os.path.dirname(os.path.dirname(__file__))
_DEFAULT_DATA_DIR = os.path.join(_BASE_DIR, "data")

_VOLUNTEER_STATE_PATH = os.getenv(
    "CPS_VOLUNTEERING_STATE_RATES_PATH",
    os.path.join(_DEFAULT_DATA_DIR, "cps_volunteering_state_rates.json"),
)
_PRECINCT_TURNOUT_PATH = os.getenv(
    "PRECINCT_TURNOUT_BY_TRACT_PATH",
    os.path.join(_DEFAULT_DATA_DIR, "precinct_turnout_by_tract.json"),
)

_state_rates: Dict[str, float] = {}
_volunteer_national_mean: float = 0.25
_volunteer_national_std: float = 0.05
_precinct_turnout_by_tract: Dict[str, float] = {}


def _load_json(path: str) -> Optional[dict]:
    try:
        if path and os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.warning("community_participation: failed to load %s: %s", path, e)
    return None


_raw_vol = _load_json(_VOLUNTEER_STATE_PATH) or {}
if isinstance(_raw_vol, dict):
    _state_rates = {str(k): float(v) for k, v in _raw_vol.items() if isinstance(v, (int, float))}
    if _state_rates:
        vals = list(_state_rates.values())
        _volunteer_national_mean = sum(vals) / len(vals)
        var = sum((x - _volunteer_national_mean) ** 2 for x in vals) / max(len(vals), 1)
        _volunteer_national_std = math.sqrt(var) if var > 0 else 0.05
        logger.info(
            "Loaded CPS volunteering state rates (%d states), mean=%.4f std=%.4f",
            len(_state_rates),
            _volunteer_national_mean,
            _volunteer_national_std,
        )

_pt = _load_json(_PRECINCT_TURNOUT_PATH) or {}
if isinstance(_pt, dict):
    _precinct_turnout_by_tract = {str(k): float(v) for k, v in _pt.items() if isinstance(v, (int, float))}
    if _precinct_turnout_by_tract:
        logger.info("Loaded precinct turnout for %d tracts", len(_precinct_turnout_by_tract))


def _rate_to_z_score(
    value: float,
    mean: float,
    std: float,
    clip_z: float = 2.5,
) -> float:
    if std <= 0:
        return 50.0
    z = (float(value) - mean) / std
    z = max(-clip_z, min(clip_z, z))
    return max(0.0, min(100.0, ((z + clip_z) / (2 * clip_z)) * 100.0))


def _bmf_z_from_result(
    result: Optional[Tuple[float, Optional[Dict[str, float]]]],
) -> Optional[float]:
    if result is None:
        return None
    orgs, stats = result
    if orgs is None or stats is None:
        return None
    mean = float(stats.get("mean", 0.0) or 0.0)
    std = float(stats.get("std", 0.0) or 0.0)
    if std <= 0:
        return None
    return _rate_to_z_score(orgs, mean, std)


def get_volunteering_score_for_tract(tract: Optional[Dict]) -> Optional[Tuple[float, str]]:
    """
    Map state volunteering rate to 0-100 z-score vs national distribution of state rates.
    Returns (score, resolution) where resolution is 'state'.
    """
    if not tract or not _state_rates:
        return None
    sf = tract.get("state_fips")
    if not sf:
        return None
    key = str(sf).zfill(2)
    rate = _state_rates.get(key)
    if rate is None:
        return None
    z = _rate_to_z_score(rate, _volunteer_national_mean, max(_volunteer_national_std, 1e-6))
    return z, "state"


def get_precinct_or_voter_turnout(
    lat: float,
    lon: float,
    tract: Optional[Dict],
    area_type: Optional[str],
) -> Tuple[Optional[Tuple[float, Any, Optional[float]]], str]:
    """
    Returns (score_0_100, stats, rate) like voter_turnout, or None; and source_tag.
    source_tag: 'precinct' or 'tract_turnout'.
    """
    if tract and _precinct_turnout_by_tract:
        geoid = tract.get("geoid")
        if geoid and str(geoid) in _precinct_turnout_by_tract:
            rate = float(_precinct_turnout_by_tract[str(geoid)])
            sc = _rate_to_z_score(rate, 0.45, 0.12)
            return (sc, {"mean": 0.45, "std": 0.12}, rate), "precinct"
    res = voter_turnout.get_voter_turnout_score(tract=tract, area_type=area_type)
    return res, "tract_turnout"


def compute_participation_score(
    lat: float,
    lon: float,
    tract: Optional[Dict],
    area_type: Optional[str],
    division_code: Optional[str],
) -> Tuple[Optional[float], Dict[str, Any]]:
    """
    Return (participation 0-100 or None, diagnostics dict for summary/source_status).
    """
    diag: Dict[str, Any] = {
        "bmf_refined_z": None,
        "bmf_legacy_z": None,
        "volunteering_z": None,
        "turnout_z": None,
        "mix": None,
        "volunteering_resolution": None,
        "turnout_source": None,
    }

    r_ref = irs_bmf.get_civic_orgs_per_1k(
        lat,
        lon,
        tract=tract,
        division_code=division_code,
        area_type=area_type,
        counts_mode="refined",
    )
    r_leg = irs_bmf.get_civic_orgs_per_1k(
        lat,
        lon,
        tract=tract,
        division_code=division_code,
        area_type=area_type,
        counts_mode="legacy",
    )

    z_ref = _bmf_z_from_result(r_ref)
    z_leg = _bmf_z_from_result(r_leg)
    diag["bmf_refined_z"] = z_ref
    diag["bmf_legacy_z"] = z_leg

    bmf_slot = z_ref if z_ref is not None else z_leg

    vol = get_volunteering_score_for_tract(tract)
    if vol:
        diag["volunteering_z"], diag["volunteering_resolution"] = vol[0], vol[1]
    z_vol = vol[0] if vol else None

    turnout_res, tsrc = get_precinct_or_voter_turnout(lat, lon, tract, area_type)
    diag["turnout_source"] = tsrc
    z_turn: Optional[float] = None
    turn_rate: Optional[float] = None
    if turnout_res is not None:
        z_turn, _st, turn_rate = turnout_res[0], turnout_res[1], turnout_res[2]
    diag["turnout_z"] = z_turn
    diag["turnout_rate"] = turn_rate

    score: Optional[float]
    if bmf_slot is not None and z_vol is not None and z_turn is not None:
        score = 0.40 * bmf_slot + 0.40 * z_vol + 0.20 * z_turn
        diag["mix"] = "full"
    elif z_vol is None and bmf_slot is not None and z_turn is not None:
        score = 0.60 * bmf_slot + 0.40 * z_turn
        diag["mix"] = "no_vol_60_40_bmf_turn"
    elif z_turn is None and bmf_slot is not None and z_vol is not None:
        score = 0.60 * bmf_slot + 0.40 * z_vol
        diag["mix"] = "no_turn_60_40_bmf_vol"
    elif bmf_slot is not None and z_vol is not None:
        score = 0.60 * bmf_slot + 0.40 * z_vol
        diag["mix"] = "bmf_vol_only"
    elif bmf_slot is not None and z_turn is not None:
        score = 0.60 * bmf_slot + 0.40 * z_turn
        diag["mix"] = "bmf_turn_only"
    elif bmf_slot is None and z_vol is not None and z_turn is not None:
        score = 0.50 * z_vol + 0.50 * z_turn
        diag["mix"] = "vol_turn_no_bmf"
    elif bmf_slot is not None:
        score = bmf_slot
        diag["mix"] = "bmf_only"
    elif z_vol is not None:
        score = z_vol
        diag["mix"] = "vol_only"
    elif z_turn is not None:
        score = z_turn
        diag["mix"] = "turn_only"
    else:
        score = 50.0
        diag["mix"] = "median_fallback"
        diag["median_fallback"] = True

    if score is not None:
        score = max(0.0, min(100.0, float(score)))

    return score, diag
