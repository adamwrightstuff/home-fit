"""
NRHP (National Register of Historic Places) lookup.

This module reads a local SQLite (RTree) index built during deploy/build
(e.g. on Railway) by `scripts/build_nrhp_db.py`.

Why this approach:
- No per-request external API calls (performance + reliability)
- No hosted DB required (it is just a file shipped with the backend build)
- Scales to any city/neighborhood (full dataset)
"""

from __future__ import annotations

import math
import os
import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from logging_config import get_logger

from .osm_api import haversine_distance

logger = get_logger(__name__)

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data_cache" / "nrhp.sqlite"


def _db_path() -> Path:
    env = os.getenv("NRHP_DB_PATH")
    return Path(env).resolve() if env else DEFAULT_DB_PATH


@lru_cache(maxsize=1)
def _has_db() -> bool:
    p = _db_path()
    exists = p.exists()
    if not exists:
        logger.warning("NRHP DB missing at %s; NRHP signals disabled.", p)
    return exists


@lru_cache(maxsize=1)
def _connect_ro_cached() -> Optional[sqlite3.Connection]:
    if not _has_db():
        return None
    p = _db_path()
    try:
        return sqlite3.connect(f"file:{p}?mode=ro", uri=True, check_same_thread=False)
    except Exception:
        return sqlite3.connect(str(p), check_same_thread=False)


def query_nrhp(lat: float, lon: float, radius_m: int = 2000) -> Dict[str, Any]:
    """
    Query local NRHP SQLite (RTree) index within `radius_m` of (lat, lon).

    Returns summary signals suitable for scoring and metadata.
    """
    conn = _connect_ro_cached()
    if conn is None:
        return {
            "count": 0,
            "nearest_distance_m": None,
            "styles": [],
            "periods": [],
        }

    # Bounding-box prefilter (rough degrees conversion; lon scaled by latitude).
    radius_deg_lat = float(radius_m) / 111_000.0
    cos_lat = math.cos(math.radians(lat))
    radius_deg_lon = float(radius_m) / (111_000.0 * max(0.2, cos_lat))
    min_lat = lat - radius_deg_lat
    max_lat = lat + radius_deg_lat
    min_lon = lon - radius_deg_lon
    max_lon = lon + radius_deg_lon

    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT n.lat, n.lon
            FROM nrhp_index i
            JOIN nrhp n ON n.id = i.id
            WHERE i.min_lon <= ? AND i.max_lon >= ?
              AND i.min_lat <= ? AND i.max_lat >= ?;
            """,
            (max_lon, min_lon, max_lat, min_lat),
        )
        candidates = cur.fetchall()
    except Exception as exc:
        logger.warning("NRHP DB query failed: %s", exc)
        return {
            "count": 0,
            "nearest_distance_m": None,
            "styles": [],
            "periods": [],
        }

    count = 0
    nearest: Optional[float] = None
    # The current NPS layer does not expose consistent style/period fields.
    styles: List[str] = []
    periods: List[str] = []

    for (c_lat, c_lon) in candidates:
        if not isinstance(c_lat, (int, float)) or not isinstance(c_lon, (int, float)):
            continue
        d = haversine_distance(lat, lon, float(c_lat), float(c_lon))
        if d > radius_m:
            continue
        count += 1
        if nearest is None or d < nearest:
            nearest = d

    return {
        "count": int(count),
        "nearest_distance_m": round(nearest, 0) if nearest is not None else None,
        "styles": sorted(set(styles)),
        "periods": sorted(set(periods)),
    }

