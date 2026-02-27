"""
IRS BMF helpers for Social Fabric Engagement sub-score.

This module expects a preprocessed mapping from Census tract GEOID to the
count of qualifying civic organizations (NTEE A/O/P/S, active only).

Offline pipeline (not implemented here) should:
  - Geocode IRS BMF records.
  - Join to 2020 Census tracts.
  - Filter by NTEE and active status.
  - Produce:
      org_count_by_tract[geoid] = int
      neighbors_by_tract[geoid] = [neighbor_geoid, ...]  # optional, for halo
      engagement_stats_by_division[division_code] = {"mean": float, "std": float}

At runtime, if no data files are present, functions will gracefully return
None and Engagement will be omitted from the combined Social Fabric score.
"""

import json
import os
from typing import Dict, List, Optional, Tuple

from logging_config import get_logger

logger = get_logger(__name__)

# In-memory stores (populated at import time if data files are present)
org_count_by_tract: Dict[str, int] = {}
neighbors_by_tract: Dict[str, List[str]] = {}
engagement_stats_by_division: Dict[str, Dict[str, float]] = {}


def _load_json_if_exists(path: str) -> Optional[dict]:
    try:
        if not path or not os.path.exists(path):
            return None
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Failed to load IRS BMF JSON from %s: %s", path, e)
        return None


# Try to load preprocessed BMF data from environment-configured paths.
_TRACT_COUNTS_PATH = os.getenv("IRS_BMF_TRACT_COUNTS_PATH")
_TRACT_NEIGHBORS_PATH = os.getenv("IRS_BMF_TRACT_NEIGHBORS_PATH")
_ENGAGEMENT_STATS_PATH = os.getenv("IRS_BMF_ENGAGEMENT_STATS_PATH")

_tract_counts_data = _load_json_if_exists(_TRACT_COUNTS_PATH) or {}
if isinstance(_tract_counts_data, dict):
    # Expect {geoid: count}
    org_count_by_tract = {str(k): int(v) for k, v in _tract_counts_data.items()}
    if org_count_by_tract:
        logger.info("Loaded IRS BMF tract counts for %d tracts", len(org_count_by_tract))

_neighbors_data = _load_json_if_exists(_TRACT_NEIGHBORS_PATH) or {}
if isinstance(_neighbors_data, dict):
    neighbors_by_tract = {str(k): list(v) for k, v in _neighbors_data.items()}

_engagement_stats_data = _load_json_if_exists(_ENGAGEMENT_STATS_PATH) or {}
if isinstance(_engagement_stats_data, dict):
    # Expect {division_code: {"mean": float, "std": float}}
    engagement_stats_by_division = {
        str(k): {"mean": float(v.get("mean", 0.0)), "std": float(v.get("std", 0.0))}
        for k, v in _engagement_stats_data.items()
        if isinstance(v, dict)
    }
    if engagement_stats_by_division:
        logger.info(
            "Loaded IRS BMF engagement stats for %d regions", len(engagement_stats_by_division)
        )


def get_civic_orgs_per_1k(
    lat: float,
    lon: float,
    tract: Optional[Dict] = None,
    population: Optional[int] = None,
    division_code: Optional[str] = None,
) -> Optional[Tuple[float, Optional[Dict[str, float]]]]:
    """
    Return (orgs_per_1k, stats) for the tract containing (lat, lon), with a simple
    halo adjustment using neighboring tracts if neighbor data is present.

    - orgs_per_1k: float or None
    - stats: {"mean": float, "std": float} for the relevant region, or None.

    If no BMF data or population is available, returns None.
    """
    from data_sources.census_api import get_census_tract, get_population  # avoid circular import

    if not org_count_by_tract:
        # No BMF data configured
        return None

    if tract is None:
        tract = get_census_tract(lat, lon)
    if not tract:
        return None

    geoid = tract.get("geoid")
    if not geoid:
        return None

    base_count = org_count_by_tract.get(geoid, 0)

    # Halo adjustment: include neighbors if available
    neighbors = neighbors_by_tract.get(geoid, [])
    counts = [base_count]
    for n in neighbors:
        c = org_count_by_tract.get(n)
        if c is not None:
            counts.append(c)
    org_count_eff = sum(counts) / len(counts) if counts else 0.0

    if population is None:
        population = get_population(tract) or 0
    if population <= 0:
        # Industrial or non-residential tract; cannot compute density
        return None

    orgs_per_1k = (org_count_eff / float(population)) * 1000.0

    stats = None
    if division_code and engagement_stats_by_division:
        stats = engagement_stats_by_division.get(division_code)

    return orgs_per_1k, stats


