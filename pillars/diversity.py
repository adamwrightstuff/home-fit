"""
Diversity pillar: race, income, and age mix (entropy) at tract level.
Formerly part of Social Fabric; standalone for weighting and Status Signal inputs.
"""

from __future__ import annotations

import json
import math
from typing import Any, Dict, Iterable, List, Optional, Tuple

from data_sources import census_api, data_quality
from data_sources.place_context import resolve_place_context
from logging_config import get_logger

logger = get_logger(__name__)

# Life-stage preference (owner decision 2026-10-28): which age cohorts the user wants more of. No preference means no score.
VALID_DIVERSITY_PREFERENCE: Tuple[str, ...] = ("children", "working_age", "older")


def parse_diversity_preference(raw: Optional[Any]) -> Optional[List[str]]:
    """
    Parse JSON array or list of dimension keys: race, income, age.
    Returns None to mean "use default (average all available dimensions)".
    Returns a non-empty ordered-unique list if the client requested specific dimensions.
    """
    if raw is None:
        return None
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return None
        try:
            raw = json.loads(s)
        except json.JSONDecodeError:
            return None
    if not isinstance(raw, list) or not raw:
        return None
    out: List[str] = []
    for x in raw:
        key = str(x).strip().lower()
        if key in VALID_DIVERSITY_PREFERENCE and key not in out:
            out.append(key)
    return out if out else None


# ACS B02001: six single-race groups plus "two or more races" (_008). _009 and _010 split _008.
RACE_CATEGORY_COUNT = 7
# Race and ethnicity term (owner decision 2026-10-28): ACS B03002, Hispanic origin plus seven non-Hispanic race groups.
ETHNICITY_CATEGORY_COUNT = 8
# Income term (owner decision 2026-10-28): ACS B19001 has 16 household income brackets; entropy is normalized by all 16,
# not by the number of non-empty ones, so a bracket that is empty in a small area cannot swing the score.
INCOME_BRACKET_COUNT = 16
RACE_SUBSET_KEYS: Tuple[str, ...] = ("B02001_009E", "B02001_010E")


def _entropy(counts: Iterable[int]) -> float:
    total = sum(c for c in counts if c is not None)
    if total <= 0:
        return 0.0
    h = 0.0
    for c in counts:
        if c is None or c <= 0:
            continue
        p = c / total
        h -= p * math.log(p)
    return h


def _normalized_entropy(counts: Iterable[int], n_categories: int) -> float:
    if n_categories <= 1:
        return 0.0
    h = _entropy(counts)
    h_max = math.log(n_categories)
    if h_max <= 0:
        return 0.0
    return max(0.0, min(100.0, (h / h_max) * 100.0))


_AGE_TABLE: Optional[Dict[str, List[float]]] = None
_TRACT_AGE_COUNTS: Optional[Dict[str, Tuple[int, int, int]]] = None
# Tract-level places pool the age counts of every tract whose center is within this radius (plus the place's own tract), because a
# single tract moved a median 2 to 4 and a 95th percentile of about 60 percentile points under a 500 m pin shift (pooled: about 20).
AGE_POOL_RADIUS_M = 1400


def _tract_age_counts() -> Dict[str, Tuple[int, int, int]]:
    global _TRACT_AGE_COUNTS
    if _TRACT_AGE_COUNTS is None:
        import os
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "tract_age_counts.parquet")
        try:
            import pyarrow.parquet as pq
            t = pq.read_table(path).to_pydict()
            _TRACT_AGE_COUNTS = {g: (y, p, s) for g, y, p, s in zip(t["geoid"], t["youth"], t["prime"], t["seniors"])}
        except Exception:
            _TRACT_AGE_COUNTS = {}
    return _TRACT_AGE_COUNTS


def pooled_age_counts(lat: float, lon: float, own_geoid: Optional[str] = None, radius_m: float = AGE_POOL_RADIUS_M):
    """(youth, prime, seniors, n_tracts) summed over tracts within radius_m of the pin plus the pin's own tract, or None."""
    counts = _tract_age_counts()
    if not counts:
        return None
    import math
    import numpy as np
    from data_sources import surrounding_density as sd
    lats, lons, _pop, _land = sd._load_tracts()
    geoids = list(sd._geoid_index.keys())
    p, q = math.radians(lat), math.radians(lon)
    la, lo = np.radians(lats), np.radians(lons)
    a = np.sin((la - p) / 2) ** 2 + np.cos(la) * math.cos(p) * np.sin((lo - q) / 2) ** 2
    d = 2 * 6371000 * np.arcsin(np.sqrt(a))
    ids = {geoids[i] for i in np.where(d <= radius_m)[0]}
    if own_geoid:
        ids.add(own_geoid)
    tot, n = [0, 0, 0], 0
    for g in ids:
        c = counts.get(g)
        if c:
            tot = [tot[0] + c[0], tot[1] + c[1], tot[2] + c[2]]
            n += 1
    return (tot[0], tot[1], tot[2], n) if sum(tot) > 0 else None



def _age_percentile(cohort: str, share: float) -> Optional[float]:
    """Percentile (0 to 100) of a cohort share among US tracts, from data/age_share_percentiles.json."""
    global _AGE_TABLE
    if _AGE_TABLE is None:
        import os
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "age_share_percentiles.json")
        try:
            with open(path, encoding="utf-8") as fh:
                _AGE_TABLE = json.load(fh)["percentile_points"]
        except Exception:
            _AGE_TABLE = {}
    pts = _AGE_TABLE.get(cohort)
    if not pts:
        return None
    import bisect
    return 100.0 * bisect.bisect_right(pts, share) / len(pts)


def get_diversity_score(
    lat: float,
    lon: float,
    area_type: Optional[str] = None,
    density: Optional[float] = None,
    city: Optional[str] = None,
    diversity_preference: Optional[List[str]] = None,
    place_context=None,
) -> Tuple[Optional[float], Dict]:
    """
    Returns (score_0_100, details) with education_attainment / self_employed_pct for Status Signal.

    diversity_preference: optional list of "race", "income", "age" to weight the headline score
    (mean of selected dimensions that have data). None = average all available (legacy behavior).
    """
    tract = census_api.get_census_tract(lat, lon)
    ctx = resolve_place_context(lat, lon, place_context=place_context, area_type=area_type, density=density, city=city, need_density=True)
    area_type = ctx.area_type

    diversity_data = census_api.get_diversity_data(lat, lon, tract=tract, area_type=area_type)
    if not diversity_data:
        # No Census data at all is a genuine absence of information, not a measured zero: raising routes through
        # main.py's pillar-failure path, which is excluded from the headline.
        raise RuntimeError(f"No Census diversity data available for ({lat}, {lon})")
    age = diversity_data.get("age_counts") or {}
    youth, prime, seniors = age.get("youth", 0), age.get("prime", 0), age.get("seniors", 0)
    breakdown: Dict = {}
    pooled_note = None
    if diversity_data.get("geo_level") == "tract":
        own = (tract or {}).get("geoid") if isinstance(tract, dict) else None
        pooled = pooled_age_counts(lat, lon, own)
        if pooled:
            youth, prime, seniors = pooled[0], pooled[1], pooled[2]
            breakdown["age_pooled_tracts"] = pooled[3]
        else:
            pooled_note = "age_pooling_unavailable: single tract used"
    total_age = youth + prime + seniors
    pref = parse_diversity_preference(diversity_preference)
    score: Optional[float] = None
    if total_age > 0:
        shares = {"children": youth / total_age * 100.0, "working_age": prime / total_age * 100.0, "older": seniors / total_age * 100.0}
        pcts = {k: _age_percentile(k, v) for k, v in shares.items()}
        breakdown["age_shares"] = {k: round(v, 1) for k, v in shares.items()}
        breakdown["age_percentiles"] = {k: round(v, 1) for k, v in pcts.items() if v is not None}
        picked = [pcts[k] for k in (pref or []) if pcts.get(k) is not None]
        if picked:
            score = round(max(0.0, min(100.0, sum(picked) / len(picked))), 1)
    breakdown["diversity_score"] = score
    components_present = [k for k, v in (("race", diversity_data.get("ethnicity_counts")), ("income", diversity_data.get("income_counts")), ("age", age)) if v]

    pref_parsed = parse_diversity_preference(diversity_preference)
    details: Dict = {
        "breakdown": breakdown,
        "summary": {
            "components_included": components_present,
            "diversity_preference": pref_parsed,
            "diversity_score_mode": "life_stage_preference" if score is not None else "no_preference",
        },
        "data_quality": data_quality.assess_pillar_data_quality(
            "diversity",
            {
                "diversity_data_loaded": bool(diversity_data),
                "components_present": components_present,
            },
            lat,
            lon,
            area_type,
            density=ctx.density,
        ),
        "area_classification": {"area_type": area_type},
        "measured_area": {"geo_level": (diversity_data or {}).get("geo_level"), "total_population": (diversity_data or {}).get("total_population")},
        "version": "v3_life_stage_preference",
    }
    if pooled_note:
        details["data_quality"]["degraded"] = True
        details["data_quality"]["degraded_reasons"] = list(details["data_quality"].get("degraded_reasons") or []) + [pooled_note]
    if diversity_data:
        if diversity_data.get("education_attainment") is not None:
            details["education_attainment"] = diversity_data["education_attainment"]
        if diversity_data.get("self_employed_pct") is not None:
            details["self_employed_pct"] = diversity_data["self_employed_pct"]

    logger.info("Diversity preference score: %s", score)
    return score, details
