"""
Job accessibility (gravity model) for economic security.

Economic security = the job market a place's residents can actually REACH, not the metro it's
administratively filed under and not its current residents' outcomes. This computes a
distance-decayed sum of nearby jobs from the LODES H8 workplace-job grid:

    access(lat, lon) = Σ_hex  workplace_jobs(hex) · exp(−distance_km / D0)   over hexes < CUTOFF_KM

so a place near a big job center scores high (Harlem ~97, Greenwich anchors to NYC not
Bridgeport), an isolated town scores low, and within a metro, proximity to jobs differentiates.
Returns a 0–100 score (or None if the LODES grid doesn't cover the area — caller should fall
back to the regional market score).

Data: data/lodes_h8_commuter.parquet (build: scripts/baselines/build_lodes_h8_commuter.py
--states ...). H3 resolution 8 (~0.46 km edge).
"""
from __future__ import annotations

import math
import os
from typing import Optional

import logging

logger = logging.getLogger(__name__)

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PARQUET = os.path.join(_REPO_ROOT, "data", "lodes_h8_commuter.parquet")

D0_KM = 20.0           # commute distance decay (mean metro commute ~25-30 km by car)
CUTOFF_KM = 75.0       # ignore jobs beyond a plausible commute
# log10(gravity) is mapped linearly to 0-100 between these. LO ~ a small local economy,
# HI ~ a dense central-city job mass (NYC core log10 ~6.55).
_LOG_LO = 2.5
_LOG_HI = 6.6

_LOADED = False
_CLAT = None  # radians
_CLON = None
_JOBS = None


def _load():
    global _LOADED, _CLAT, _CLON, _JOBS
    if _LOADED:
        return
    _LOADED = True
    try:
        import numpy as np
        import pyarrow.parquet as pq
        import h3
        d = pq.read_table(_PARQUET).to_pydict()
        cells = d["h8"]
        centers = np.array([h3.cell_to_latlng(c) for c in cells])
        _CLAT = np.radians(centers[:, 0])
        _CLON = np.radians(centers[:, 1])
        _JOBS = np.array(d["workplace_jobs"], dtype=float)
        logger.info("Loaded LODES job-accessibility grid: %d hexes", len(cells))
    except Exception as e:
        logger.warning("Job-accessibility grid unavailable: %s", e)
        _CLAT = _CLON = _JOBS = None


def gravity_jobs(lat: float, lon: float) -> Optional[float]:
    """Distance-decayed reachable-job sum, or None if the grid doesn't cover this point."""
    _load()
    if _JOBS is None:
        return None
    import numpy as np
    la, lo = math.radians(lat), math.radians(lon)
    dlat = _CLAT - la
    dlon = _CLON - lo
    a = np.sin(dlat / 2) ** 2 + np.cos(la) * np.cos(_CLAT) * np.sin(dlon / 2) ** 2
    dist = 6371.0 * 2 * np.arcsin(np.sqrt(a))
    m = dist < CUTOFF_KM
    if not m.any():
        return None
    total = float(np.sum(_JOBS[m] * np.exp(-dist[m] / D0_KM)))
    # No reachable jobs within range but grid covers the area => genuinely isolated (not "no data")
    return total


def job_access_score(lat: float, lon: float) -> Optional[float]:
    """0–100 reachable-market score. None if the LODES grid doesn't cover the area."""
    g = gravity_jobs(lat, lon)
    if g is None:
        return None
    if g <= 0:
        return 0.0
    log_g = math.log10(g + 1.0)
    score = (log_g - _LOG_LO) / (_LOG_HI - _LOG_LO) * 100.0
    return round(max(0.0, min(100.0, score)), 1)
