"""
Local snapshot of SchoolDigger schools, one file per state.

SchoolDigger lets one request return 500 schools, so a whole state is a handful of calls. Everything
the scorer needs (a district's schools, a state's charters, distances) is then computed locally, so a
new place, a new metro in the same state, or a scoring change costs no API calls. Ratings change once a
year, so refresh each state about once a year with scripts/catalog/fetch_school_snapshot.py.

Files: data/school_snapshot/<ST>.json.gz (committed, about 3 MB for 9 states)  (override with HOMEFIT_SCHOOL_SNAPSHOT_DIR)
Each school keeps only what scoring and the Explorer need, in the same shape the API returns
(rankHistory list, district dict, address.latLong), so callers can use API results and snapshot
results interchangeably.
"""
from __future__ import annotations

import gzip
import json
import os
import threading
import time
from typing import Any, Dict, List, Optional

import requests

SCHOOLDIGGER_BASE = "https://api.schooldigger.com/v2.1"
PER_PAGE = 500  # SchoolDigger maximum

_lock = threading.Lock()
_mem: Dict[str, Optional[Dict[str, Any]]] = {}


def snapshot_dir() -> str:
    default = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "data", "school_snapshot")
    return os.getenv("HOMEFIT_SCHOOL_SNAPSHOT_DIR", default)


def _path(state: str) -> str:
    return os.path.join(snapshot_dir(), f"{state.upper()}.json.gz")


def slim(school: Dict[str, Any]) -> Dict[str, Any]:
    """Keep the fields scoring and the Explorer use, in the API's own shape."""
    rh = (school.get("rankHistory") or [])[:1]
    yd = (school.get("schoolYearlyDetails") or [])[:1]
    ll = (school.get("address") or {}).get("latLong") or {}
    d = school.get("district") or {}
    return {
        "schoolid": school.get("schoolid"),
        "schoolName": school.get("schoolName"),
        "schoolLevel": school.get("schoolLevel"),
        "lowGrade": school.get("lowGrade"),
        "highGrade": school.get("highGrade"),
        "isCharterSchool": school.get("isCharterSchool"),
        "isMagnetSchool": school.get("isMagnetSchool"),
        "isPrivate": bool(school.get("isPrivate")),
        "address": {"city": (school.get("address") or {}).get("city"),
                    "zip": (school.get("address") or {}).get("zip"),
                    "latLong": {"latitude": ll.get("latitude"), "longitude": ll.get("longitude")}},
        "district": {"districtID": d.get("districtID"), "districtName": d.get("districtName")} if d else None,
        "county": (school.get("county") or {}).get("countyName") if isinstance(school.get("county"), dict) else school.get("county"),
        "rankHistory": [{k: rh[0].get(k) for k in ("year", "rankStars", "rankStatewidePercentage", "rankMovement")}] if rh else [],
        "rankMovement": school.get("rankMovement"),
        "schoolYearlyDetails": [{"pupilTeacherRatio": yd[0].get("pupilTeacherRatio"),
                                 "numberOfStudents": yd[0].get("numberOfStudents")}] if yd else [],
    }


def fetch_state(state: str, app_id: str, app_key: str, log=print) -> Dict[str, Any]:
    """Pull every school in the state (500 per request) and write the snapshot. Returns its metadata."""
    state = state.upper()
    schools: List[Dict[str, Any]] = []
    calls = 0
    page = 1
    while True:
        resp = requests.get(f"{SCHOOLDIGGER_BASE}/schools", timeout=120, params={
            "appID": app_id, "appKey": app_key, "st": state, "perPage": PER_PAGE, "page": page})
        calls += 1
        if resp.status_code != 200:
            raise RuntimeError(f"{state} page {page}: HTTP {resp.status_code} {resp.text[:200]}")
        data = resp.json()
        lst = data.get("schoolList") or []
        if lst and str(lst[0].get("schoolName", "")).startswith("School #"):
            raise RuntimeError(f"{state}: SchoolDigger returned obfuscated data (quota or key problem)")
        schools.extend(slim(s) for s in lst)
        pages = int(data.get("numberOfPages") or 1)
        log(f"  {state} page {page}/{pages}: {len(lst)} schools")
        if page >= pages or not lst:
            break
        page += 1
        time.sleep(0.5)
    meta = {"state": state, "fetched_at": time.strftime("%Y-%m-%d"), "count": len(schools), "calls": calls}
    os.makedirs(snapshot_dir(), exist_ok=True)
    tmp = _path(state) + ".tmp"
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        json.dump({"meta": meta, "schools": schools}, f, separators=(",", ":"))
    os.replace(tmp, _path(state))
    with _lock:
        _mem.pop(state, None)
    return meta


def load_state(state: Optional[str]) -> Optional[Dict[str, Any]]:
    """{'meta': {...}, 'schools': [...], 'by_district': {id: [schools]}, 'charters': [...]} or None."""
    if not state:
        return None
    state = state.upper()
    with _lock:
        if state in _mem:
            return _mem[state]
        data = None
        p = _path(state)
        if os.path.isfile(p):
            try:
                with gzip.open(p, "rt", encoding="utf-8") as f:
                    data = json.load(f)
                by: Dict[str, List[Dict[str, Any]]] = {}
                for s in data["schools"]:
                    did = (s.get("district") or {}).get("districtID")
                    if did:
                        by.setdefault(str(did), []).append(s)
                data["by_district"] = by
                data["charters"] = [s for s in data["schools"] if s.get("isCharterSchool") == "Yes"]
            except Exception:
                data = None
        _mem[state] = data
        return data


def district_schools(state: str, district_id: str) -> Optional[List[Dict[str, Any]]]:
    snap = load_state(state)
    if not snap:
        return None
    return snap["by_district"].get(str(district_id), [])


def state_charters(state: str) -> Optional[List[Dict[str, Any]]]:
    snap = load_state(state)
    return None if not snap else snap["charters"]
