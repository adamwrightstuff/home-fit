"""Raw Overpass response cache for batch scoring (off unless HOMEFIT_OSM_CACHE_DIR is set; production never sets it).

Every Overpass query is a POST through ``requests.post``. When enabled, this wraps ``requests.post`` for Overpass URLs only:

  * a query answered before is replayed from disk instead of asking Overpass again (so rescoring after a logic change
    needs no network, and a place with 3 of 4 queries done only re-asks the 4th);
  * only VERIFIED-GOOD answers are saved: HTTP 200, valid JSON with a non-empty ``elements`` list, and no error remark.
    Empty answers are never saved (an overloaded server can return a silent empty), so rural places re-ask, which is cheap;
  * entries expire (HOMEFIT_OSM_CACHE_TTL_DAYS, default 180) so map edits eventually flow in.

HOMEFIT_OSM_CACHE_MODE: ``readwrite`` (default), ``replay`` (never touches the network; a missing entry raises, so a test
metro scores fully offline and any gap is explicit) or ``off``.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Optional

import requests

_ERROR_REMARKS = ("runtime error", "timed out", "out of memory", "too many requests", "rate_limit")
_installed = False
_real_post = requests.post


def _enabled_dir() -> Optional[Path]:
    d = os.getenv("HOMEFIT_OSM_CACHE_DIR", "").strip()
    return Path(d) if d and os.getenv("HOMEFIT_OSM_CACHE_MODE", "readwrite").lower() != "off" else None


def _is_overpass(url: Any) -> bool:
    u = str(url or "")
    return "/api/interpreter" in u


def _query_text(kwargs: dict, args: tuple) -> Optional[str]:
    data = kwargs.get("data")
    if data is None and len(args) > 1:
        data = args[1]
    if isinstance(data, dict):
        data = data.get("data")
    return data if isinstance(data, str) else None


def _key(query: str) -> str:
    return hashlib.sha256(" ".join(query.split()).encode()).hexdigest()


def is_verified_good(status: int, body: bytes) -> bool:
    if status != 200:
        return False
    try:
        data = json.loads(body.decode("utf-8"))
    except Exception:  # noqa: BLE001
        return False
    if not isinstance(data, dict) or not isinstance(data.get("elements"), list) or not data["elements"]:
        return False
    remark = str(data.get("remark") or "").lower()
    return not any(m in remark for m in _ERROR_REMARKS)


def _response(body: bytes, url: str) -> requests.Response:
    r = requests.Response()
    r.status_code = 200
    r._content = body
    r.headers["Content-Type"] = "application/json"
    r.url = url
    r.encoding = "utf-8"
    return r


def cached_post(url, *args, **kwargs):
    d = _enabled_dir()
    query = _query_text(kwargs, args) if d and _is_overpass(url) else None
    if query is None:
        return _real_post(url, *args, **kwargs)
    path = d / (_key(query) + ".json")
    ttl = float(os.getenv("HOMEFIT_OSM_CACHE_TTL_DAYS", "180")) * 86400
    try:
        if path.is_file() and time.time() - path.stat().st_mtime < ttl:
            return _response(path.read_bytes(), str(url))
    except OSError:
        pass
    if os.getenv("HOMEFIT_OSM_CACHE_MODE", "readwrite").lower() == "replay":
        raise requests.ConnectionError("overpass cache replay: query not recorded (run once with the network to record it)")
    resp = _real_post(url, *args, **kwargs)
    try:
        if is_verified_good(resp.status_code, resp.content):
            d.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(f".{os.getpid()}.tmp")
            tmp.write_bytes(resp.content)
            os.replace(tmp, path)
    except Exception:  # noqa: BLE001 - caching must never break scoring
        pass
    return resp


def install() -> None:
    """Patch requests.post once; a no-op unless HOMEFIT_OSM_CACHE_DIR is set."""
    global _installed
    if _installed or _enabled_dir() is None:
        return
    requests.post = cached_post
    _installed = True
