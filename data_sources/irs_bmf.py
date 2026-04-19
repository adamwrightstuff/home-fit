"""
IRS BMF helpers for Social Fabric participation sub-score.

Primary tract counts: **refined** civic-facing NTEE (N, P, S, W). Legacy file
(A, O, P, S) is used when refined effective count is zero after halo (same
ZIP/tract pipeline as build_irs_engagement_baselines.py).

At runtime, when a tract has 0 orgs we use a "runtime halo": sample nearby
points (~800m) and average org counts from those tracts so PO-box / adjacent
addresses don't put the tract in a data shadow.
"""

import json
import math
import os
from typing import Dict, List, Optional, Tuple

from logging_config import get_logger

logger = get_logger(__name__)

# Halo radius in meters when tract has 0 orgs (pull from surrounding ~1.5km context)
_HALO_RADIUS_M = 800


def _point_at_bearing(lat: float, lon: float, bearing_deg: float, distance_m: float) -> Tuple[float, float]:
    """Return (lat, lon) at given bearing and distance from (lat, lon)."""
    R = 6371000.0  # Earth radius in meters
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    br = math.radians(bearing_deg)
    lat2 = math.asin(
        math.sin(lat_rad) * math.cos(distance_m / R)
        + math.cos(lat_rad) * math.sin(distance_m / R) * math.cos(br)
    )
    lon2 = lon_rad + math.atan2(
        math.sin(br) * math.sin(distance_m / R) * math.cos(lat_rad),
        math.cos(distance_m / R) - math.sin(lat_rad) * math.sin(lat2),
    )
    return math.degrees(lat2), math.degrees(lon2)

# In-memory stores (populated at import time if data files are present)
org_count_by_tract: Dict[str, int] = {}
org_count_by_tract_legacy: Dict[str, int] = {}
neighbors_by_tract: Dict[str, List[str]] = {}
engagement_stats_by_division: Dict[str, Dict[str, float]] = {}
engagement_stats_by_division_legacy: Dict[str, Dict[str, float]] = {}
engagement_stats_by_area_type: Dict[str, Dict[str, float]] = {}


def _load_json_if_exists(path: str) -> Optional[dict]:
    try:
        if not path or not os.path.exists(path):
            return None
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Failed to load IRS BMF JSON from %s: %s", path, e)
        return None


# Default data locations (relative to repo root) with env var overrides.
_BASE_DIR = os.path.dirname(os.path.dirname(__file__))
_DEFAULT_DATA_DIR = os.path.join(_BASE_DIR, "data")

_TRACT_COUNTS_PATH = os.getenv(
    "IRS_BMF_TRACT_COUNTS_PATH",
    os.path.join(_DEFAULT_DATA_DIR, "irs_bmf_tract_counts.json"),
)
_TRACT_COUNTS_LEGACY_PATH = os.getenv(
    "IRS_BMF_TRACT_COUNTS_LEGACY_PATH",
    os.path.join(_DEFAULT_DATA_DIR, "irs_bmf_tract_counts_legacy.json"),
)
_TRACT_NEIGHBORS_PATH = os.getenv(
    "IRS_BMF_TRACT_NEIGHBORS_PATH",
    os.path.join(_DEFAULT_DATA_DIR, "irs_bmf_tract_neighbors.json"),
)
_ENGAGEMENT_STATS_PATH = os.getenv(
    "IRS_BMF_ENGAGEMENT_STATS_PATH",
    os.path.join(_DEFAULT_DATA_DIR, "irs_bmf_engagement_stats.json"),
)
_ENGAGEMENT_STATS_LEGACY_PATH = os.getenv(
    "IRS_BMF_ENGAGEMENT_STATS_LEGACY_PATH",
    os.path.join(_DEFAULT_DATA_DIR, "irs_bmf_engagement_stats_legacy.json"),
)
_ENGAGEMENT_STATS_AREA_PATH = os.getenv(
    "IRS_BMF_ENGAGEMENT_STATS_BY_AREA_TYPE_PATH",
    os.path.join(_DEFAULT_DATA_DIR, "irs_bmf_engagement_stats_by_area_type.json"),
)

_tract_counts_data = _load_json_if_exists(_TRACT_COUNTS_PATH) or {}
if isinstance(_tract_counts_data, dict):
    # Expect {geoid: count} refined N/P/S/W
    org_count_by_tract = {str(k): int(v) for k, v in _tract_counts_data.items()}
    if org_count_by_tract:
        logger.info("Loaded IRS BMF refined tract counts for %d tracts", len(org_count_by_tract))

_legacy_counts_data = _load_json_if_exists(_TRACT_COUNTS_LEGACY_PATH) or {}
if isinstance(_legacy_counts_data, dict):
    org_count_by_tract_legacy = {str(k): int(v) for k, v in _legacy_counts_data.items()}
    if org_count_by_tract_legacy:
        logger.info("Loaded IRS BMF legacy tract counts for %d tracts", len(org_count_by_tract_legacy))

_neighbors_data = _load_json_if_exists(_TRACT_NEIGHBORS_PATH) or {}
if isinstance(_neighbors_data, dict):
    neighbors_by_tract = {str(k): list(v) for k, v in _neighbors_data.items()}

_engagement_stats_data = _load_json_if_exists(_ENGAGEMENT_STATS_PATH) or {}
if isinstance(_engagement_stats_data, dict):
    engagement_stats_by_division = {
        str(k): {"mean": float(v.get("mean", 0.0)), "std": float(v.get("std", 0.0))}
        for k, v in _engagement_stats_data.items()
        if isinstance(v, dict)
    }
    if engagement_stats_by_division:
        logger.info(
            "Loaded IRS BMF refined engagement stats for %d regions", len(engagement_stats_by_division)
        )

_legacy_stats_data = _load_json_if_exists(_ENGAGEMENT_STATS_LEGACY_PATH) or {}
if isinstance(_legacy_stats_data, dict):
    engagement_stats_by_division_legacy = {
        str(k): {"mean": float(v.get("mean", 0.0)), "std": float(v.get("std", 0.0))}
        for k, v in _legacy_stats_data.items()
        if isinstance(v, dict)
    }
    if engagement_stats_by_division_legacy:
        logger.info(
            "Loaded IRS BMF legacy engagement stats for %d regions",
            len(engagement_stats_by_division_legacy),
        )

_area_stats_data = _load_json_if_exists(_ENGAGEMENT_STATS_AREA_PATH) or {}
if isinstance(_area_stats_data, dict):
    engagement_stats_by_area_type = {
        str(k): {"mean": float(v.get("mean", 0.0)), "std": float(v.get("std", 0.0))}
        for k, v in _area_stats_data.items()
        if isinstance(v, dict)
    }
    if engagement_stats_by_area_type:
        logger.info(
            "Loaded IRS BMF engagement stats for %d area types", len(engagement_stats_by_area_type)
        )


STATE_FIPS_TO_ABBREV_IRS: Dict[str, str] = {
    "01": "AL",
    "02": "AK",
    "04": "AZ",
    "05": "AR",
    "06": "CA",
    "08": "CO",
    "09": "CT",
    "10": "DE",
    "11": "DC",
    "12": "FL",
    "13": "GA",
    "15": "HI",
    "16": "ID",
    "17": "IL",
    "18": "IN",
    "19": "IA",
    "20": "KS",
    "21": "KY",
    "22": "LA",
    "23": "ME",
    "24": "MD",
    "25": "MA",
    "26": "MI",
    "27": "MN",
    "28": "MS",
    "29": "MO",
    "30": "MT",
    "31": "NE",
    "32": "NV",
    "33": "NH",
    "34": "NJ",
    "35": "NM",
    "36": "NY",
    "37": "NC",
    "38": "ND",
    "39": "OH",
    "40": "OK",
    "41": "OR",
    "42": "PA",
    "44": "RI",
    "45": "SC",
    "46": "SD",
    "47": "TN",
    "48": "TX",
    "49": "UT",
    "50": "VT",
    "51": "VA",
    "53": "WA",
    "54": "WV",
    "55": "WI",
    "56": "WY",
    "72": "PR",
}


def _effective_org_count_eff(
    geoid: str,
    lat: float,
    lon: float,
    count_map: Dict[str, int],
) -> float:
    """Halo-adjusted effective org count for a tract using count_map."""
    from data_sources.census_api import get_census_tract

    base_count = count_map.get(geoid, 0)
    neighbors = neighbors_by_tract.get(geoid, [])
    counts: List[float] = [float(base_count)]
    for n in neighbors:
        c = count_map.get(n)
        if c is not None:
            counts.append(float(c))

    if base_count == 0 and not neighbors:
        seen = {geoid}
        for bearing in (0, 90, 180, 270, 45, 135, 225, 315):
            lat2, lon2 = _point_at_bearing(lat, lon, bearing, _HALO_RADIUS_M)
            t = get_census_tract(lat2, lon2)
            if t and t.get("geoid") and t["geoid"] not in seen:
                seen.add(t["geoid"])
                c = float(count_map.get(t["geoid"], 0))
                counts.append(c)
        if len(counts) > 1:
            return sum(counts) / len(counts)
        return 0.0
    return sum(counts) / len(counts) if counts else 0.0


def _pick_engagement_stats(
    division_code: Optional[str],
    area_type: Optional[str],
    *,
    use_legacy: bool,
) -> Optional[Dict[str, float]]:
    div_stats = engagement_stats_by_division_legacy if use_legacy else engagement_stats_by_division
    area_stats = engagement_stats_by_area_type

    at = (area_type or "").lower().replace(" ", "_") if area_type else None
    stats = None
    if at and area_stats:
        stats = area_stats.get(at) or area_stats.get("default")
        if stats is None:
            stats = area_stats.get("all")
    if stats is None and division_code and div_stats:
        stats = div_stats.get(division_code)
        if stats is None:
            stats = div_stats.get("all")
    return stats


def get_civic_orgs_per_1k(
    lat: float,
    lon: float,
    tract: Optional[Dict] = None,
    population: Optional[int] = None,
    division_code: Optional[str] = None,
    area_type: Optional[str] = None,
    *,
    counts_mode: str = "auto",
) -> Optional[Tuple[float, Optional[Dict[str, float]]]]:
    """
    Return (orgs_per_1k, stats) for the tract containing (lat, lon), with halo adjustment.

    Uses **refined** N/P/S/W counts first; if effective refined count is 0 and legacy
    counts exist, falls back to legacy A/O/P/S for the rate and z-score baselines.

    counts_mode: ``auto`` (refined then legacy fallback), ``refined`` (refined only),
    ``legacy`` (legacy A/O/P/S only).

    If no BMF data or population is available, returns None.
    """
    from data_sources.census_api import get_census_tract, get_population  # avoid circular import
    from data_sources.us_census_divisions import get_division

    mode = (counts_mode or "auto").strip().lower()
    if mode not in ("auto", "refined", "legacy"):
        mode = "auto"

    if mode == "refined" and not org_count_by_tract:
        return None
    if mode == "legacy" and not org_count_by_tract_legacy:
        return None
    if mode == "auto" and not org_count_by_tract and not org_count_by_tract_legacy:
        return None

    if tract is None:
        tract = get_census_tract(lat, lon)
    if not tract:
        return None

    geoid = tract.get("geoid")
    if not geoid:
        return None

    use_legacy = False
    if mode == "legacy":
        count_map = org_count_by_tract_legacy
        use_legacy = True
    elif mode == "refined":
        count_map = org_count_by_tract
        use_legacy = False
    else:
        eff_refined = _effective_org_count_eff(geoid, lat, lon, org_count_by_tract) if org_count_by_tract else 0.0
        use_legacy = eff_refined <= 0.0 and bool(org_count_by_tract_legacy)
        count_map = org_count_by_tract_legacy if use_legacy else org_count_by_tract
        if not count_map:
            return None

    org_count_eff = _effective_org_count_eff(geoid, lat, lon, count_map)

    if population is None:
        population = get_population(tract) or 0
    if population <= 0:
        return None

    orgs_per_1k = (org_count_eff / float(population)) * 1000.0

    if division_code is None:
        state_fips = tract.get("state_fips")
        state_abbrev = STATE_FIPS_TO_ABBREV_IRS.get(state_fips) if state_fips else None
        division_code = get_division(state_abbrev) if state_abbrev else None

    stats = _pick_engagement_stats(division_code, area_type, use_legacy=use_legacy)

    return orgs_per_1k, stats


def get_civic_orgs_per_1k_detailed(
    lat: float,
    lon: float,
    tract: Optional[Dict] = None,
    population: Optional[int] = None,
    division_code: Optional[str] = None,
    area_type: Optional[str] = None,
) -> Optional[Tuple[float, Optional[Dict[str, float]], str]]:
    """
    Like get_civic_orgs_per_1k but returns (orgs_per_1k, stats, source) where source is
    'refined' or 'legacy'.
    """
    base = get_civic_orgs_per_1k(
        lat, lon, tract=tract, population=population, division_code=division_code, area_type=area_type
    )
    if base is None:
        return None
    orgs, stats = base
    from data_sources.census_api import get_census_tract, get_population
    from data_sources.us_census_divisions import get_division

    if tract is None:
        tract = get_census_tract(lat, lon)
    if not tract or not tract.get("geoid"):
        return orgs, stats, "refined"
    geoid = tract["geoid"]
    eff_r = _effective_org_count_eff(geoid, lat, lon, org_count_by_tract) if org_count_by_tract else 0.0
    src = "legacy" if eff_r <= 0.0 and org_count_by_tract_legacy else "refined"
    return orgs, stats, src


