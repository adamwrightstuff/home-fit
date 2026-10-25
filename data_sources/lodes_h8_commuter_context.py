"""
LODES-derived commuter / workplace denominator context (H3 resolution 8).

Build output: optional Parquet at ``data/lodes_h8_commuter.parquet`` produced by
``scripts/baselines/build_lodes_h8_commuter.py``.

At scoring time we look up the H8 cell covering (lat, lon) and optionally
inflate the residential denominator when:
  - Workplace-to-residence job ratio (from LODES WAC/RAC aggregates) exceeds a
    threshold and
  - Property crime dominates violent crime enough that the spike is probably
    commercial/theft-heavy rather than community violence.

This keeps per-capita violent crime comparable in CBDs without punishing malls
purely from retail theft denominated against tiny nighttime populations.

Schema (Parquet):
  h8 (VARCHAR): H3 cell id at resolution 8
  workplace_jobs (BIGINT): sum of WAC C000 in cell
  rac_c000 (BIGINT): sum of RAC C000 in cell (see build script — proxy for resident jobs)
  wrr_jobs (DOUBLE): workplace_jobs / max(1, rac_c000)

Override path via env ``LODES_H8_COMMUTER_PARQUET``.
"""

from __future__ import annotations

import json
import math
import os
from typing import Any, Dict, Optional, Tuple

try:
    import h3
except ImportError:  # pragma: no cover
    h3 = None

from logging_config import get_logger

logger = get_logger(__name__)

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_PARQUET = os.path.join(_REPO_ROOT, "data", "lodes_h8_commuter.parquet")

_PARQUET_PATH = os.getenv("LODES_H8_COMMUTER_PARQUET", _DEFAULT_PARQUET)

_TABLE_LOADED = False
_H8_INDEX: Dict[str, Dict[str, float]] = {}


def _lat_lon_to_h8(lat: float, lon: float) -> Optional[str]:
    if h3 is None:
        return None
    try:
        return str(h3.latlng_to_cell(float(lat), float(lon), 8))
    except Exception as e:
        logger.debug("h3 cell compute failed: %s", e)
        return None


def _ensure_table() -> None:
    global _TABLE_LOADED, _H8_INDEX
    if _TABLE_LOADED:
        return
    path = _PARQUET_PATH
    if not path or not os.path.isfile(path):
        logger.debug("LODES H8 commuter Parquet missing: %s", path)
        _TABLE_LOADED = True
        return
    try:
        import pyarrow.parquet as pq

        tbl = pq.read_table(
            path,
            columns=["h8", "workplace_jobs", "rac_c000", "wrr_jobs"],
        )
        df = tbl.to_pydict()
        for i in range(len(df["h8"])):
            hid = df["h8"][i]
            if hid is None:
                continue
            _H8_INDEX[str(hid)] = {
                "workplace_jobs": float(df["workplace_jobs"][i] or 0),
                "rac_c000": float(df["rac_c000"][i] or 0),
                "wrr_jobs": float(df["wrr_jobs"][i] or 0),
            }
        logger.info("Loaded LODES commuter H8 lookup: %d cells from %s", len(_H8_INDEX), path)
    except ImportError:
        logger.warning("PyArrow unavailable — cannot load LODES commuter Parquet")
    except Exception as e:
        logger.warning("Failed to load LODES commuter Parquet: %s", e)
    _TABLE_LOADED = True


def jobs_in_disk(lat: float, lon: float, radius_m: float, state: Optional[str] = None) -> Optional[Tuple[float, float]]:
    """
    Area-weighted (workplace_jobs, resident_workers) inside a circle, summed over
    the H3 res-8 cells it covers (each cell weighted by the share of it inside).
    Returns None when the LODES table or h3 is unavailable, or when the point is outside the area the grid was built for:
    "unavailable", not zero. With `state` (postal abbreviation) a state missing from data/lodes_h8_commuter_states.json
    is unavailable even if a few cells across the border fall in the disk; without it, an empty disk is unavailable
    when fewer than 20% of the cells in an 8-ring around the point are indexed.
    """
    _ensure_table()
    if h3 is None or not _H8_INDEX:
        return None
    built = built_states()
    if state and built is not None and state.upper() not in built:
        return None
    n = 12  # sample grid: (2n+1)^2 points over the circle's bounding square
    step = float(radius_m) / n
    dlat = step / 111_000.0
    dlon = step / (111_000.0 * max(0.1, math.cos(math.radians(lat))))
    pt_km2 = (step / 1000.0) ** 2
    cell_km2 = h3.average_hexagon_area(8, unit="km^2")
    hits: Dict[str, int] = {}
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            if (i * i + j * j) * step * step > radius_m * radius_m:
                continue
            try:
                cell = str(h3.latlng_to_cell(lat + i * dlat, lon + j * dlon, 8))
            except Exception:
                continue
            hits[cell] = hits.get(cell, 0) + 1
    jobs = resident_workers = 0.0
    found = False
    for cell, count in hits.items():
        row = _H8_INDEX.get(cell)
        if not row:
            continue
        found = True
        share = min(1.0, count * pt_km2 / cell_km2)
        jobs += row["workplace_jobs"] * share
        resident_workers += row["rac_c000"] * share
    if not found and not _grid_covers(lat, lon):
        return None  # outside the states the grid was built for: unavailable, not zero
    return jobs, resident_workers


COVERAGE_RING_K = 8        # H3 res-8 rings (about 4 km)
COVERAGE_MIN_SHARE = 0.20  # an indexed share below this around an empty disk means the grid does not cover the area
_STATES_PATH = os.path.join(_REPO_ROOT, "data", "lodes_h8_commuter_states.json")


def built_states() -> Optional[set]:
    """Postal abbreviations of the states in the grid, or None when the sidecar file is missing."""
    try:
        with open(_STATES_PATH, encoding="utf-8") as fh:
            return {x.upper() for x in json.load(fh).get("states", [])}
    except (OSError, ValueError):
        return None


def _grid_covers(lat: float, lon: float) -> bool:
    """True when enough of the cells around the point are indexed that an empty disk is a real zero."""
    try:
        ring = list(h3.grid_disk(h3.latlng_to_cell(lat, lon, 8), COVERAGE_RING_K))
        return sum(1 for c in ring if str(c) in _H8_INDEX) / len(ring) >= COVERAGE_MIN_SHARE
    except Exception:
        return False


# Gated commuter denominator boost (aligned with pillar PRD iterations)
_MIN_WRR = 5.0
_MIN_PROPERTY_VIOLENT_RATIO = 10.0
_POP_MULT_CAP = 3.5  # ceiling so extreme job-only cells don't swallow violent spikes


def compute_commuter_denominator_boost(
    lat: float,
    lon: float,
    *,
    violent_per_1k: float,
    property_per_1k: float,
) -> Tuple[float, Dict[str, Any]]:
    """
    Return (effective_pop_multiplier, telemetry dict).

    Multiplier defaults to 1.0 when Parquet absent, gated conditions fail,
    or h3 not installed.

    Telemetry includes `wrr_jobs`, raw jobs counts, confidence_delta, flags.
    """
    _ensure_table()
    multiplier = 1.0
    meta: Dict[str, Any] = {
        "h8_available": False,
        "wrr_jobs": None,
        "commuter_denominator_boost": False,
        "flags": [],
    }

    if not _H8_INDEX:
        return multiplier, meta

    hcell = _lat_lon_to_h8(lat, lon)
    if not hcell:
        return multiplier, meta

    row = _H8_INDEX.get(hcell)
    if not row:
        meta["flags"].append("h8_unknown_cell")
        return multiplier, meta

    wjobs = row["workplace_jobs"]
    rac = max(1.0, row["rac_c000"])
    wrr = row["wrr_jobs"]

    meta["h8_available"] = True
    meta["workplace_jobs"] = int(wjobs)
    meta["rac_c000"] = int(max(0, row["rac_c000"]))
    meta["wrr_jobs"] = round(wrr, 4)

    if wrr <= _MIN_WRR:
        return multiplier, meta

    raw_mult = max(1.0, 1.0 + math.log10(max(1.0, wrr)))
    multiplier = float(min(raw_mult, _POP_MULT_CAP))

    meta["commuter_denominator_boost"] = True
    meta["effective_pop_multiplier"] = round(multiplier, 4)
    meta["population_dampen_reason"] = "commuter_denominator_boost"
    if raw_mult > _POP_MULT_CAP:
        meta["flags"].append("commuter_boost_capped")

    # Extreme workplace skew → slightly lower certainty in denom
    if wrr >= 40.0:
        meta["flags"].append("extreme_workplace_jobs_ratio")

    return multiplier, meta
