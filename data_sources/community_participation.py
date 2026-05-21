"""
Community participation sub-score for Social Fabric (breakdown.engagement).

Combines: refined IRS BMF (50%), volunteering proxy (50%).

Voter turnout excluded: it's an outcome of social capital, not a driver (Putnam),
and state-level rates have no within-metro discrimination power.

Volunteering source priority:
  1. Social Capital Atlas (ZIP-level) — Facebook-derived volunteering_rate_zip
  2. CPS/AmeriCorps state-level rates — fallback when ZIP not in SCA
"""

from __future__ import annotations

import csv
import json
import math
import os
import statistics
from typing import Any, Dict, Optional, Tuple

from data_sources import irs_bmf
from logging_config import get_logger

logger = get_logger(__name__)

_BASE_DIR = os.path.dirname(os.path.dirname(__file__))
_DEFAULT_DATA_DIR = os.path.join(_BASE_DIR, "data")

_VOLUNTEER_STATE_PATH = os.getenv(
    "CPS_VOLUNTEERING_STATE_RATES_PATH",
    os.path.join(_DEFAULT_DATA_DIR, "cps_volunteering_state_rates.json"),
)
_SCA_ZIP_PATH = os.getenv(
    "SCA_ZIP_PATH",
    os.path.join(_DEFAULT_DATA_DIR, "social_capital_zip.csv"),
)

_state_rates: Dict[str, float] = {}
_volunteer_national_mean: float = 0.25
_volunteer_national_std: float = 0.05

# Social Capital Atlas ZIP-level volunteering rates
_sca_vol_by_zip: Dict[str, float] = {}
_sca_vol_mean: float = 0.0768
_sca_vol_std: float = 0.0369


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

# Load Social Capital Atlas ZIP-level volunteering rates
try:
    if _SCA_ZIP_PATH and os.path.isfile(_SCA_ZIP_PATH):
        _sca_vals = []
        with open(_SCA_ZIP_PATH, newline="", encoding="utf-8") as _f:
            for row in csv.DictReader(_f):
                z = str(row.get("zip", "")).zfill(5)
                v = row.get("volunteering_rate_zip", "")
                if z and v and v != "NA":
                    _sca_vol_by_zip[z] = float(v)
                    _sca_vals.append(float(v))
        if _sca_vals:
            _sca_vol_mean = statistics.mean(_sca_vals)
            _sca_vol_std = statistics.stdev(_sca_vals)
        logger.info(
            "Loaded SCA volunteering rates for %d ZIPs, mean=%.4f std=%.4f",
            len(_sca_vol_by_zip), _sca_vol_mean, _sca_vol_std,
        )
except Exception as _e:
    logger.warning("community_participation: failed to load SCA data: %s", _e)


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


def get_volunteering_score(
    zip_code: Optional[str],
    tract: Optional[Dict],
) -> Optional[Tuple[float, str]]:
    """
    Returns (score 0-100, resolution) for volunteering engagement.

    Priority:
      1. Social Capital Atlas ZIP-level volunteering_rate_zip — neighborhood signal
      2. CPS state-level rate — fallback when ZIP missing from SCA
    """
    # 1. SCA ZIP-level (preferred)
    if zip_code and _sca_vol_by_zip:
        key = str(zip_code).split("-")[0].zfill(5)
        rate = _sca_vol_by_zip.get(key)
        if rate is not None:
            z = _rate_to_z_score(rate, _sca_vol_mean, max(_sca_vol_std, 1e-6))
            return z, "sca_zip"

    # 2. CPS state fallback
    if tract and _state_rates:
        sf = tract.get("state_fips")
        if sf:
            state_rate = _state_rates.get(str(sf).zfill(2))
            if state_rate is not None:
                z = _rate_to_z_score(state_rate, _volunteer_national_mean, max(_volunteer_national_std, 1e-6))
                return z, "cps_state"

    return None


def compute_participation_score(
    lat: float,
    lon: float,
    tract: Optional[Dict],
    area_type: Optional[str],
    division_code: Optional[str],
    zip_code: Optional[str] = None,
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
        "turnout_in_engagement_blend": False,
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

    vol = get_volunteering_score(zip_code, tract)
    if vol:
        diag["volunteering_z"], diag["volunteering_resolution"] = vol[0], vol[1]
    z_vol = vol[0] if vol else None

    score: Optional[float]
    if bmf_slot is not None and z_vol is not None:
        score = 0.50 * bmf_slot + 0.50 * z_vol
        diag["mix"] = "full"
    elif bmf_slot is not None:
        score = bmf_slot
        diag["mix"] = "bmf_only"
    elif z_vol is not None:
        score = z_vol
        diag["mix"] = "vol_only"
    else:
        score = 50.0
        diag["mix"] = "median_fallback"
        diag["median_fallback"] = True

    if score is not None:
        score = max(0.0, min(100.0, float(score)))

    return score, diag
