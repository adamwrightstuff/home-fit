"""
Optional automatic catalog pillar aggregates (Supabase).

When HOMEFIT_CATALOG_CONTRIBUTIONS_ENABLED=1 and SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY
are set, successful score responses that resolve to a row in data/nyc_metro_place_catalog.csv
call merge_catalog_contribution via PostgREST (non-blocking daemon thread).

Skips: request cache hits (metadata.cache_hit), missing env, or no catalog match.
"""

from __future__ import annotations

import csv
import json
import math
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from logging_config import get_logger

logger = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_CATALOG_CSV = REPO_ROOT / "data" / "nyc_metro_place_catalog.csv"

# Max distance (km) to match by coordinates if search string does not match.
_MAX_NEAREST_KM = 5.0


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


def _norm_query(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def _catalog_key_row(row: Dict[str, str]) -> str:
    return f"{row.get('name', '')}|{row.get('county_borough', '')}|{row.get('state_abbr', '')}"


def _haversine_km(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    r = 6371.0
    p = math.pi / 180.0
    a = 0.5 - math.cos((lat2 - lat1) * p) / 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * (1 - math.cos((lon2 - lon1) * p)) / 2
    return 2 * r * math.asin(math.sqrt(a))


class _CatalogLookup:
    """Lazy-loaded search_query / coordinate -> catalog_key."""

    _instance: Optional["_CatalogLookup"] = None

    def __init__(self) -> None:
        self.by_query: Dict[str, str] = {}
        self.rows: List[Tuple[str, float, float, str]] = []
        path = Path(os.getenv("HOMEFIT_CATALOG_CSV", str(DEFAULT_CATALOG_CSV))).resolve()
        if not path.is_file():
            logger.warning("catalog_contribution: catalog CSV not found at %s", path)
            return
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = _catalog_key_row(row)
                sq = (row.get("search_query") or "").strip()
                if sq:
                    self.by_query[_norm_query(sq)] = key
                try:
                    lat = float(row.get("lat") or "")
                    lon = float(row.get("lon") or "")
                except (TypeError, ValueError):
                    continue
                self.rows.append((key, lat, lon, sq))

    @classmethod
    def get(cls) -> "_CatalogLookup":
        if cls._instance is None:
            cls._instance = _CatalogLookup()
        return cls._instance

    def resolve(self, input_str: str, lat: Optional[float], lon: Optional[float]) -> Optional[str]:
        if self.by_query or self.rows:
            pass
        else:
            return None
        n = _norm_query(input_str)
        if n and n in self.by_query:
            return self.by_query[n]
        if lat is None or lon is None or not self.rows:
            return None
        if not (math.isfinite(lat) and math.isfinite(lon)):
            return None
        best_k: Optional[str] = None
        best_d = float("inf")
        for key, rlat, rlon, _ in self.rows:
            d = _haversine_km(lat, lon, rlat, rlon)
            if d < best_d:
                best_d = d
                best_k = key
        if best_k is not None and best_d <= _MAX_NEAREST_KM:
            return best_k
        return None


def _scores_from_result(result: Dict[str, Any]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    pillars = result.get("livability_pillars") or {}
    if not isinstance(pillars, dict):
        return out
    for k, v in pillars.items():
        if not isinstance(v, dict):
            continue
        if v.get("status") == "failed" or v.get("error"):
            continue
        s = v.get("score")
        if isinstance(s, (int, float)) and math.isfinite(float(s)):
            out[str(k)] = round(float(s), 4)
    return out


def _post_merge(catalog_key: str, scores: Dict[str, float], api_version: Optional[str]) -> None:
    url = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
    key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not url or not key:
        logger.debug("catalog_contribution: SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set")
        return
    endpoint = f"{url}/rest/v1/rpc/merge_catalog_contribution"
    r = requests.post(
        endpoint,
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        json={
            "p_catalog_key": catalog_key,
            "p_scores": scores,
            "p_api_version": api_version,
        },
        timeout=12,
    )
    if r.status_code >= 400:
        logger.warning(
            "catalog_contribution: Supabase RPC failed %s %s",
            r.status_code,
            (r.text or "")[:500],
        )


def try_record_catalog_contribution(result: Dict[str, Any]) -> None:
    """Synchronous record attempt; use schedule_catalog_contribution from request path."""
    if not _env_bool("HOMEFIT_CATALOG_CONTRIBUTIONS_ENABLED", default=False):
        return
    if not isinstance(result, dict):
        return
    meta = result.get("metadata") or {}
    if isinstance(meta, dict) and meta.get("cache_hit") is True:
        return
    if isinstance(meta, dict) and meta.get("test_mode") is True:
        return

    inp = (result.get("input") or "").strip()
    coords = result.get("coordinates") or {}
    lat = coords.get("lat")
    lon = coords.get("lon")
    try:
        lat_f = float(lat) if lat is not None else None
        lon_f = float(lon) if lon is not None else None
    except (TypeError, ValueError):
        lat_f, lon_f = None, None

    catalog_key = _CatalogLookup.get().resolve(inp, lat_f, lon_f)
    if not catalog_key:
        return

    scores = _scores_from_result(result)
    if not scores:
        return

    api_ver = None
    if isinstance(meta, dict):
        v = meta.get("version")
        if isinstance(v, str) and v.strip():
            api_ver = v.strip()
        iv = meta.get("indices_version")
        if isinstance(iv, dict) and iv:
            api_ver = (api_ver + " | " if api_ver else "") + json.dumps(iv, sort_keys=True)[:400]

    _post_merge(catalog_key, scores, api_ver)


def schedule_catalog_contribution(result: Dict[str, Any]) -> None:
    """Fire-and-forget; does not block scoring."""

    def run() -> None:
        try:
            try_record_catalog_contribution(result)
        except Exception as e:
            logger.debug("catalog_contribution: skipped: %s", e)

    threading.Thread(target=run, daemon=True).start()
