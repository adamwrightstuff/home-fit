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

    if violent_per_1k <= 0 or property_per_1k <= 0:
        return multiplier, meta

    pv = property_per_1k / max(1e-9, violent_per_1k)
    if pv < _MIN_PROPERTY_VIOLENT_RATIO:
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
