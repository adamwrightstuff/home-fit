"""NYC middle school pools from the DOE directory (data/school_geo/nyc_middle_directory.json).

The directory lists every middle school program of each community district with its admissions method. A family's
realistic middle school pool is the schools of its home district (district priority), including 6-12 and K-8 schools
that SchoolDigger files under another level. Schools whose programs are all screened (grades, test, audition) are
kept apart: they are not part of the typical pool. Built by scripts/catalog/build_nyc_middle_directory.py.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

_cache: Dict[str, Any] = {}


def _bundle() -> Optional[List[Dict[str, Any]]]:
    if "schools" not in _cache:
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "data", "school_geo", "nyc_middle_directory.json")
        try:
            with open(path) as f:
                _cache["schools"] = json.load(f).get("schools") or []
        except Exception:
            _cache["schools"] = None
    return _cache["schools"]


def district_pool(district: Optional[int]) -> Optional[List[Dict[str, Any]]]:
    """SchoolDigger schools (as middle-level copies tagged `_dir_class`: open | mixed | selective) of a community
    district's middle school programs, or None when there is no directory or the district is unknown."""
    from data_sources.school_snapshot import school_by_id

    rows = _bundle()
    if not rows or district is None:
        return None
    out = []
    for r in rows:
        if r["district"] != district or not r.get("schoolid") or r["class"] == "other":
            continue
        sc = school_by_id(r["schoolid"])
        if not sc:
            continue
        cp = dict(sc)
        cp["schoolLevel"] = "Middle"
        cp["schoolid"] = f"{sc.get('schoolid')}-dirmid"
        cp["_dir_class"] = r["class"]
        out.append(cp)
    return out or None
