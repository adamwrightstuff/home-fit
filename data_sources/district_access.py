"""Which levels a school district fills by lottery even though it also publishes attendance-area maps.

Data, not scoring: data/school_geo/district_access.json lists district IDs (Census LEAID) with the levels whose
seats are assigned by application, with the source and date of the rule. A level listed here is scored as the
district's pool average; the attendance-area school (a tiebreaker there) is shown beside it. Add a district only
from the district's own published rules, and re-check yearly.
"""
from __future__ import annotations

import json
import os
from typing import Iterable, Optional, Set

_cache: dict = {}


def _table() -> dict:
    if "t" not in _cache:
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "data", "school_geo", "district_access.json")
        try:
            with open(path) as f:
                _cache["t"] = json.load(f).get("districts") or {}
        except Exception:
            _cache["t"] = {}
    return _cache["t"]


def lottery_levels_for(district_ids: Iterable[str]) -> Optional[Set[str]]:
    levels: Set[str] = set()
    for did in district_ids:
        levels.update((_table().get(str(did)) or {}).get("lottery_levels", []))
    return levels or None
