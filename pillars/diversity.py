"""
Diversity opt-in filter (not a scored pillar, see pillar_registry.FILTER_PILLARS): a life-stage preference scored as the
percentile of the place's age-cohort share among US tracts. No preference means no score. Also returns the education and
self-employment values Status Signal reads. The old race, income and age entropy headline is retired.
"""

from __future__ import annotations

import json
import math
from typing import Any, Dict, List, Optional, Tuple

from data_sources import census_api, data_quality
from data_sources.place_context import resolve_place_context
from logging_config import get_logger

logger = get_logger(__name__)

# Life-stage preference (owner decision 2026-10-28): which age cohorts the user wants more of. No preference means no score.
VALID_DIVERSITY_PREFERENCE: Tuple[str, ...] = ("children", "working_age", "older", "young_professionals")


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


_AGE_TABLE: Optional[Dict[str, List[float]]] = None
_TRACT_AGE_COUNTS: Optional[Dict[str, Tuple[int, int, int, Optional[int]]]] = None
# Tract-level places pool the age counts of every tract whose center is within this radius (plus the place's own tract), because a
# single tract moved a median 2 to 4 and a 95th percentile of about 60 percentile points under a 500 m pin shift (pooled: about 20).
AGE_POOL_RADIUS_M = 1400


def _tract_age_counts() -> Dict[str, Tuple[int, int, int, Optional[int]]]:
    global _TRACT_AGE_COUNTS
    if _TRACT_AGE_COUNTS is None:
        import os
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "tract_age_counts.parquet")
        try:
            import pyarrow.parquet as pq
            t = pq.read_table(path).to_pydict()
            yp = t.get("age_25_34") or [None] * len(t["geoid"])  # 25 to 34, a subset of prime; None if the parquet predates it
            _TRACT_AGE_COUNTS = {g: (y, p, s, a) for g, y, p, s, a in zip(t["geoid"], t["youth"], t["prime"], t["seniors"], yp)}
        except Exception:
            _TRACT_AGE_COUNTS = {}
    return _TRACT_AGE_COUNTS


def pooled_age_counts(lat: float, lon: float, own_geoid: Optional[str] = None, radius_m: float = AGE_POOL_RADIUS_M):
    """(youth, prime, seniors, n_tracts, age_25_34 or None) summed over tracts within radius_m of the pin plus the pin's own tract, or None."""
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
    tot, n, yp = [0, 0, 0], 0, 0
    for g in ids:
        c = counts.get(g)
        if c:
            tot = [tot[0] + c[0], tot[1] + c[1], tot[2] + c[2]]
            yp = None if (yp is None or c[3] is None) else yp + c[3]
            n += 1
    return (tot[0], tot[1], tot[2], n, yp) if sum(tot) > 0 else None



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

    diversity_preference: optional list of "children", "working_age", "older", "young_professionals" (25 to 34). The score is the mean age-share percentile of the
    chosen cohorts. None = no score (score is None, summary.diversity_score_mode is "no_preference").
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
    young_pros = age.get("young_professionals")
    breakdown: Dict = {}
    pooled_note = None  # age shares rank the place's own geography (the tract itself for tract-level places), no pooling
    total_age = youth + prime + seniors
    pref = parse_diversity_preference(diversity_preference)
    score: Optional[float] = None
    if total_age > 0:
        shares = {"children": youth / total_age * 100.0, "working_age": prime / total_age * 100.0, "older": seniors / total_age * 100.0}
        if young_pros is not None:
            shares["young_professionals"] = young_pros / total_age * 100.0
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
