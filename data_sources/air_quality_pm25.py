"""
Annual PM2.5 by census tract, from a stored table (data/pm25_tract_annual.json).

Built by scripts/baselines/build_pm25_tract_table.py from the CDC Tracking Network daily tract PM2.5 predictions
(EPA Downscaler model, monitors fused with CMAQ), averaged over the available years. Replaces the retired
Sentinel-5P aerosol-index "PM2.5 proxy", which tracked desert dust and smoke, not fine particulate pollution.
A tract that is missing from the table (for example Connecticut, whose tract codes changed after 2021) is matched to
the nearest tract centroid in the same state within MAX_MATCH_KM and flagged (match="nearest_centroid"); beyond that
distance, or with no tract, it means no data (None), never a made-up value. PM2.5 is a smooth model surface, so a
tract a few km away is a small error.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Dict, Optional

TABLE_PATH = Path(os.getenv("PM25_TRACT_TABLE_PATH", str(Path(__file__).resolve().parents[1] / "data" / "pm25_tract_annual.json")))

MAX_MATCH_KM = 5.0

_cache: Optional[Dict] = None
_cache_mtime: Optional[float] = None


def load_table() -> Dict:
    """Return {"tracts": {geoid: ug/m3}, "_meta": {...}}; empty dicts when the file is missing."""
    global _cache, _cache_mtime
    try:
        mtime = TABLE_PATH.stat().st_mtime
    except OSError:
        return {"tracts": {}, "_meta": {}}
    if _cache is None or _cache_mtime != mtime:
        _cache = json.loads(TABLE_PATH.read_text(encoding="utf-8"))
        _cache_mtime = mtime
    return _cache


def get_pm25_for_tract(geoid: Optional[str]) -> Optional[Dict]:
    """{"pm25_ugm3", "years", "source"} for an 11-digit tract GEOID, or None when the tract has no value."""
    if not geoid:
        return None
    t = load_table()
    v = (t.get("tracts") or {}).get(str(geoid))
    if v is None:
        return None
    meta = t.get("_meta") or {}
    return {"pm25_ugm3": float(v), "years": meta.get("years"), "source": "cdc_tracking_epa_downscaler"}


def _km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p = math.pi / 180
    a = math.sin((lat2 - lat1) * p / 2) ** 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2
    return 12742.0 * math.asin(math.sqrt(a))


def get_pm25_for_point(geoid: Optional[str], lat: float, lon: float) -> Optional[Dict]:
    """Exact tract value, else the nearest tract centroid in the same state within MAX_MATCH_KM (flagged), else None."""
    got = get_pm25_for_tract(geoid)
    if got is not None:
        return {**got, "match": "exact", "match_km": 0.0}
    if not geoid:
        return None
    t = load_table()
    best = None
    for g, (la, lo) in (t.get("centroids") or {}).items():
        if g[:2] != str(geoid)[:2]:
            continue
        d = _km(lat, lon, la, lo)
        if d <= MAX_MATCH_KM and (best is None or d < best[0]):
            best = (d, g)
    if best is None:
        return None
    meta = t.get("_meta") or {}
    return {"pm25_ugm3": float(t["tracts"][best[1]]), "years": meta.get("years"), "source": "cdc_tracking_epa_downscaler",
            "match": "nearest_centroid", "match_km": round(best[0], 2)}


def get_pm25(lat: float, lon: float) -> Optional[Dict]:
    """PM2.5 for the tract containing (lat, lon); None when the tract or its value is unavailable."""
    from data_sources.census_api import get_census_tract

    tract = get_census_tract(lat, lon)
    return get_pm25_for_point((tract or {}).get("geoid"), lat, lon)
