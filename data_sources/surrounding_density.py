"""
Surrounding-area density for the area type.

The area type used to read the population density of the one Census tract under the pin and a count of
OSM businesses. A pin on a sparse tract inside a busy area read as suburban or rural whatever surrounded it.
This module measures the circle around the pin instead:

  people_density  people per square mile over the 2020 tracts whose center lies within the radius
  activity        people plus jobs per gross acre over the same circle (jobs: LODES workplace jobs,
                  H3 res-8 cells weighted by the share of each cell inside the circle)

Both come from local files (no Census or other API call at request time):
  data/tract_pop_area_centers.parquet   built by scripts/baselines/build_tract_table.py
  data/lodes_h8_jobs_national.parquet   LODES 2022 workplace jobs, also used by job_accessibility

Evidence and open questions: analysis/area_type_activity_density_proposal_2026-10-27.md.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from logging_config import get_logger

logger = get_logger(__name__)

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TRACTS = os.getenv("HOMEFIT_TRACT_TABLE", os.path.join(_REPO_ROOT, "data", "tract_pop_area_centers.parquet"))
_JOBS = os.getenv("LODES_H8_JOBS_PARQUET", os.path.join(_REPO_ROOT, "data", "lodes_h8_jobs_national.parquet"))

RADIUS_M = 1000  # same footprint as the 1 km business count
SQ_M_PER_ACRE = 4046.86
SQ_MI_PER_ACRE = 1.0 / 640.0
NEAREST_TRACT_MAX_M = 100_000  # no tract center within the radius: use the nearest, but not from farther than this.
# Rural tracts can be huge (west Texas, Alaska), so their centers sit far from a pin. The nearest center is an
# approximation of the pin's own tract, recorded as method 'nearest_tract'; such places read rural either way.
JOBS_COVERAGE_RINGS = 6  # a point counts as covered by the jobs grid if an indexed cell is within 6 rings (~2.8 km)

_tract = None  # (lat, lon, pop, land_sqmi) numpy arrays
_geoid_index = None  # geoid -> row
_jobs = None   # (sorted int cell ids, jobs) numpy arrays


@dataclass(frozen=True)
class SurroundingStats:
    people_density: float          # people per square mile in the circle
    n_tracts: int                  # tracts whose center is in the circle (0 = nearest tract was used)
    density_method: str            # "disk", "pin_tract" or "nearest_tract"
    jobs: Optional[float]          # workplace jobs in the circle, None when the jobs grid does not cover the place
    activity_per_acre: float       # people plus jobs per gross acre (people only when jobs is None)
    radius_m: int = RADIUS_M

    @property
    def jobs_known(self) -> bool:
        return self.jobs is not None


def _load_tracts():
    global _tract, _geoid_index
    if _tract is None:
        if not os.path.isfile(_TRACTS):
            raise RuntimeError(f"tract table missing: {_TRACTS} (build it with scripts/baselines/build_tract_table.py)")
        import numpy as np
        import pyarrow.parquet as pq
        t = pq.read_table(_TRACTS).to_pydict()
        _geoid_index = {g: i for i, g in enumerate(t["geoid"])}
        _tract = tuple(np.asarray(t[k], dtype="float64") for k in ("lat", "lon", "pop", "land_sqmi"))
    return _tract


def _load_jobs():
    global _jobs
    if _jobs is None:
        if not os.path.isfile(_JOBS):
            return None
        import h3
        import numpy as np
        import pyarrow.parquet as pq
        t = pq.read_table(_JOBS, columns=["h8", "workplace_jobs"]).to_pydict()
        ids = np.fromiter((h3.str_to_int(c) for c in t["h8"]), dtype="uint64", count=len(t["h8"]))
        jobs = np.asarray(t["workplace_jobs"], dtype="float64")
        order = np.argsort(ids)
        _jobs = (ids[order], jobs[order])
    return _jobs


def people_density_in_disk(lat: float, lon: float, radius_m: float = RADIUS_M, tract_geoid: Optional[str] = None):
    """
    (people per sq mi, tracts used, method), or None when no tract center is near enough.
    When no tract center lies in the circle (large tracts), the pin's own tract is used if its 11-digit
    GEOID is given (method 'pin_tract'); otherwise the nearest tract center stands in ('nearest_tract').
    """
    import numpy as np
    tlat, tlon, tpop, tland = _load_tracts()
    for box in (0.2, 1.0):  # degrees: about 22 km, then about 110 km for the sparse-area fallback
        m = (np.abs(tlat - lat) < box) & (np.abs(tlon - lon) < box)
        if m.any():
            break
    if not m.any():
        return None
    dy = (tlat[m] - lat) * 110_540.0
    dx = (tlon[m] - lon) * 111_320.0 * math.cos(math.radians(lat))
    d = np.hypot(dx, dy)
    pop, land = tpop[m], tland[m]
    inside = d <= radius_m
    if inside.any():
        return float(pop[inside].sum() / land[inside].sum()), int(inside.sum()), "disk"
    if tract_geoid and tract_geoid in _geoid_index:
        k = _geoid_index[tract_geoid]
        if tland[k] > 0:
            return float(tpop[k] / tland[k]), 0, "pin_tract"
    i = int(np.argmin(d))
    if d[i] > NEAREST_TRACT_MAX_M:
        return None
    return float(pop[i] / land[i]), 0, "nearest_tract"


def jobs_in_disk(lat: float, lon: float, radius_m: float = RADIUS_M) -> Optional[float]:
    """Workplace jobs in the circle, or None when the jobs grid does not cover the place (not zero)."""
    import h3
    import numpy as np
    loaded = _load_jobs()
    if loaded is None:
        return None
    ids, jobs = loaded
    center = h3.latlng_to_cell(lat, lon, 8)

    def lookup(cell_int):
        i = int(np.searchsorted(ids, cell_int))
        return float(jobs[i]) if i < len(ids) and ids[i] == cell_int else None

    if not any(lookup(h3.str_to_int(c)) is not None for c in h3.grid_disk(center, JOBS_COVERAGE_RINGS)):
        return None  # outside the grid: unavailable, not zero
    n = 12  # (2n+1)^2 sample points over the circle's bounding square
    step = radius_m / n
    dlat = step / 111_000.0
    dlon = step / (111_000.0 * max(0.1, math.cos(math.radians(lat))))
    pt_km2 = (step / 1000.0) ** 2
    cell_km2 = h3.average_hexagon_area(8, unit="km^2")
    hits = {}
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            if (i * i + j * j) * step * step > radius_m * radius_m:
                continue
            c = h3.latlng_to_cell(lat + i * dlat, lon + j * dlon, 8)
            hits[c] = hits.get(c, 0) + 1
    total = 0.0
    for c, count in hits.items():
        v = lookup(h3.str_to_int(c))
        if v:
            total += v * min(1.0, count * pt_km2 / cell_km2)
    return total


@lru_cache(maxsize=4096)
def _stats_cached(lat4: float, lon4: float, radius_m: int, tract_geoid: Optional[str]) -> Optional[SurroundingStats]:
    pd = people_density_in_disk(lat4, lon4, radius_m, tract_geoid)
    if pd is None:
        return None
    density, n, method = pd
    jobs = jobs_in_disk(lat4, lon4, radius_m)
    acres = math.pi * radius_m ** 2 / SQ_M_PER_ACRE
    activity = density * SQ_MI_PER_ACRE + ((jobs or 0.0) / acres)
    if jobs is None:
        logger.warning("jobs grid does not cover (%.4f, %.4f): activity density uses people only", lat4, lon4)
    return SurroundingStats(density, n, method, jobs, activity, radius_m)


def surrounding_stats(lat: float, lon: float, radius_m: int = RADIUS_M,
                      tract_geoid: Optional[str] = None) -> Optional[SurroundingStats]:
    """Density measures for the circle around a pin; None when no tract is near enough to measure."""
    return _stats_cached(round(float(lat), 4), round(float(lon), 4), int(radius_m), tract_geoid)


# Cutoffs (owner decisions 2026-10-27, see the proposal).
# URBAN_ACTIVITY_PER_ACRE: 25 people plus jobs per gross acre (owner decision 2026-10-27).
#   - HUD's Urbanization Perceptions Small Area Index (tract labels modeled from how households describe
#     their neighborhood, American Housing Survey 2017): across 1,409 catalog places the activity cutoff that
#     best matches HUD's urban label is about 24 per acre (accuracy 0.81; 45 gives 0.74, 30 gives 0.79).
#   - Behavior: Puget Sound Regional Council's transit density paper cites Pivo and Frank (1994): transit gains
#     begin past 30 activity units per gross acre and are largest past 45 to 50; in the catalog median transit
#     commuting is 7% to 8% at 20 to 45 per acre against 1% to 3% below 20.
#   The first version used 45 and labeled dense city neighborhoods (Logan Square, Albany Park, Dorchester)
#   suburban; HUD calls 35 of those 40 places urban.
# SUBURBAN / EXURBAN: kept from the previous classifier. Close to the Degree of Urbanisation values
#   (urban center 1,500 per km2 = 3,885 per sq mi; moderate density 300 per km2 = 777 per sq mi) but not
#   those values. TODO: the exact choice of 3,000 and 800 is unsourced.
URBAN_ACTIVITY_PER_ACRE = 25.0
SUBURBAN_PEOPLE_PER_SQMI = 3000.0
EXURBAN_PEOPLE_PER_SQMI = 800.0


def classify_surrounding(stats: Optional[SurroundingStats]) -> str:
    if stats is None or (stats.people_density <= 0 and stats.activity_per_acre <= 0):
        return "unknown"
    if stats.activity_per_acre >= URBAN_ACTIVITY_PER_ACRE:
        return "urban_residential"
    if stats.people_density >= SUBURBAN_PEOPLE_PER_SQMI:
        return "suburban"
    if stats.people_density >= EXURBAN_PEOPLE_PER_SQMI:
        return "exurban"
    return "rural"
