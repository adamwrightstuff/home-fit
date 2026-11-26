"""
Surroundings ("Around here"): median household income, median home value and community safety around a place,
next to the place's own figures. Display only: no pillar, no weight, not counted in any score (docs/SURROUNDINGS.md).

Offline over stored catalog numbers (housing_value.summary, Census ACS 2022; community_safety score and breakdown).
Used by scripts/catalog/build_catalog_surroundings.py (stored figures for catalog places) and by
catalog_api's /catalog/surroundings (any scored point, e.g. a live search on the results page).

"Around" is a weighted average over catalog places within MAX_MILES, each weighted exp(-(d / SCALE_MILES)^2), so the
closest count most. Only catalog places count. Too little nearby weight (under MIN_WEIGHT) gives no figure.
Values at the Census cap count at the cap (so an average with capped neighbors is a floor); a place itself at the cap
gets no comparison for that figure. Safety uses only places whose rate is their own (see safety_key).
"""
from __future__ import annotations

import csv
import json
import math
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

import catalog_api

# Judgment calls, not fitted to any research (docs/SURROUNDINGS.md): about a short drive.
MAX_MILES = 8.0
SCALE_MILES = 3.0
MIN_WEIGHT = 1.0
INCOME_CAP = 250_001
HOME_CAP = 2_000_001
FIELDS = (("income", "median_household_income", INCOME_CAP), ("home_value", "median_home_value", HOME_CAP))
ALL_FIELDS = [(f, cap) for f, _, cap in FIELDS] + [("safety", math.inf)]
# A searched point this close to a catalog place with the same name is that place, not its neighbor.
SAME_PLACE_MILES = 2.0
# Any catalog pin this close to a searched point is taken as the same place whatever the geocoder named it
# ("Village of Hempstead" vs "Hempstead").
SAME_PIN_MILES = 0.25

# Neighbor taxonomy (docs/SURROUNDINGS.md): how a signal from neighbor B behaves across the line into focal place A.
# Every neighbor signal carries one of these tags. Tags describe; they never feed a pillar or a weight.
NEIGHBOR_CATEGORIES = {
    "accessible_amenities": "Parks, transit stops, groceries, services and recreation in B that a resident of A can "
                            "reach and use (weighted by travel time and barrier friction).",
    "spillover_externalities": "Traffic cut-throughs, parking pressure, noise, runoff, flood exposure or crime that can "
                               "flow into A from B (weighted by direction and physical or road links).",
    "boundary_locked_rules": "School catchments, municipal lines, tax rates and zoning that stay tied to legal "
                             "boundaries rather than blending across them.",
    "cost_space_arbitrage": "Differences in housing cost, layout or carrying costs between A and B, and whether using "
                            "B's perks or commuting from B erases the savings.",
    "social_stability_context": "Turnover, demographic and household mix, and community continuity in B that show "
                                "whether nearby social networks or pressures spill over or stay isolated.",
}
# Category of each figure this module reports. Income is relative standing (Luttmer 2005), home value is the cost
# gap, safety is crime crossing the line (Morenoff, Sampson and Raudenbush 2001).
FIELD_CATEGORY = {
    "income": "social_stability_context",
    "home_value": "cost_space_arbitrage",
    "safety": "spillover_externalities",
}
# Categories with no neighbor figure here, and why (so the gap is stated, not silent).
CATEGORY_NOT_SHOWN = {
    "accessible_amenities": "Already counted by radius inside the amenities, active outdoors, transit and healthcare "
                            "pillars, so neighbors' amenities are in the score.",
    "boundary_locked_rules": "Schools follow the district line; a better district next door does nothing without moving.",
}
assert set(FIELD_CATEGORY.values()) | set(CATEGORY_NOT_SHOWN) == set(NEIGHBOR_CATEGORIES)

_AGENCY_SOURCES = {"fbi_nibrs_agency", "fbi_ucr_agency", "ny_state_ucr", "ca_doj_ucr"}


def miles(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    r = 3958.8
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dlat, dlon = p2 - p1, math.radians(b[1] - a[1])
    x = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(x))


def num(v: Any) -> Optional[float]:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0 else None


def safety_key(place_type: Optional[str], b: Dict[str, Any]) -> Optional[Tuple[str, str]]:
    """(source, agency) when the safety score might be the place's own rate, else None.

    Own rate: measured in a circle around the place from a city incident feed (*_open_data), or the yearly total of a
    police department that is not a sheriff or county force and does not cover a city neighborhood. Never own: county
    agencies, LASD station totals, state aggregates. An agency total shared by several catalog places is a city-wide
    or area-wide rate; callers check that against the catalog."""
    src = str(b.get("source") or "")
    if src.endswith("_open_data"):
        return (src, "")
    agency = str(b.get("agency_name") or "")
    if src not in _AGENCY_SOURCES or not agency or place_type == "neighborhood":
        return None
    if "sheriff" in agency.lower() or "county" in agency.lower():
        return None
    return (src, agency)


def _place_list_pins(metro: str) -> Dict[str, Tuple[float, float]]:
    path = catalog_api.DATA_DIR / f"{metro}_metro_place_catalog.csv"
    if not path.is_file():
        return {}
    with path.open(newline="", encoding="utf-8") as fh:
        return {catalog_api.row_key(r): (float(r["lat"]), float(r["lon"])) for r in csv.DictReader(fh)}


def metro_rows(metro: str, log=None) -> List[Dict[str, Any]]:
    """Catalog rows with a usable pin. A row scored at a pin the place list has since moved is left out entirely
    (no figure, and not anyone's neighbor), since its stored numbers describe the wrong spot."""
    pins = _place_list_pins(metro)
    out = []
    for line in catalog_api._metro_file(metro).open(encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        cat, score = row.get("catalog") or {}, row.get("score") or {}
        if not row.get("success") or not cat or not score:
            continue
        try:
            ll = (float(cat["lat"]), float(cat["lon"]))
        except (KeyError, TypeError, ValueError):
            continue
        want = pins.get(catalog_api.row_key(cat))
        if want and (abs(want[0] - ll[0]) > 0.0005 or abs(want[1] - ll[1]) > 0.0005):
            if log:
                log(f"  {metro}: skipping {cat.get('name')} (scored at an old pin)")
            continue
        pillars = score.get("livability_pillars") or {}
        hv = (pillars.get("housing_value") or {}).get("summary") or {}
        cs = pillars.get("community_safety") or {}
        sv = cs.get("score")
        sv = float(sv) if isinstance(sv, (int, float)) and not isinstance(sv, bool) else None
        b = cs.get("breakdown") or {}
        skey = safety_key(cat.get("type"), b) if sv is not None else None
        out.append({"key": catalog_api.row_key(cat), "name": cat.get("name"), "ll": ll,
                    **{f: num(hv.get(src)) for f, src, _ in FIELDS},
                    "safety": sv if skey else None, "agency_key": skey,
                    # Every agency a catalog place is scored on (own rate or not), to spot city-wide rates.
                    "agency_any": (str(b.get("source") or ""), str(b.get("agency_name") or "")) if b.get("agency_name") else None})
    shared = _agency_counts(out)
    for r in out:
        k = r["agency_key"]
        if k and k[1] and shared[k] > 1:
            r["safety"] = None
    return out


def _agency_counts(rows: List[Dict[str, Any]]) -> Dict[Tuple[str, str], int]:
    counts: Dict[Tuple[str, str], int] = {}
    for r in rows:
        k = r.get("agency_key")
        if k and k[1]:
            counts[k] = counts.get(k, 0) + 1
    return counts


def figures(here: Dict[str, Optional[float]], near: List[Tuple[float, Dict[str, Any]]]) -> Dict[str, Any]:
    """{field: {here, around}} plus the three closest names, from (weight, neighbor row) pairs; {} when nothing qualifies."""
    entry: Dict[str, Any] = {}
    for f, cap in ALL_FIELDS:
        h = here.get(f)
        vals = [(w, o[f]) for w, o in near if o.get(f) is not None]
        total_w = sum(w for w, _ in vals)
        if h is None or h >= cap or total_w < MIN_WEIGHT:
            continue
        entry[f] = {"here": round(h), "around": round(sum(w * v for w, v in vals) / total_w)}
    if entry:
        entry["neighbors"] = [o["name"] for _, o in sorted(near, key=lambda t: -t[0])[:3]]
    return entry


def _near(ll: Tuple[float, float], rows: List[Dict[str, Any]], skip) -> List[Tuple[float, Dict[str, Any]]]:
    out = []
    for o in rows:
        if skip(o):
            continue
        d = miles(ll, o["ll"])
        if d <= MAX_MILES:
            out.append((math.exp(-((d / SCALE_MILES) ** 2)), o))
    return out


def surroundings_for(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Stored figures for every catalog row, keyed by row key (one metro's rows)."""
    result: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        entry = figures(r, _near(r["ll"], rows, lambda o, r=r: o is r))
        if entry:
            result[r["key"]] = entry
    return result


@lru_cache(maxsize=1)
def all_catalog_rows() -> Tuple[Dict[str, Any], ...]:
    rows: List[Dict[str, Any]] = []
    for metro in catalog_api.live_metros():
        if catalog_api._metro_file(metro).is_file():
            rows.extend(metro_rows(metro))
    return tuple(rows)


def for_point(lat: float, lon: float, *, name: Optional[str] = None, place_type: Optional[str] = None,
              income: Optional[float] = None, home_value: Optional[float] = None, safety: Optional[float] = None,
              safety_source: Optional[str] = None, agency_name: Optional[str] = None) -> Dict[str, Any]:
    """Figures for any scored point (a live search), against every catalog place nearby. A catalog place with the
    same name within SAME_PLACE_MILES is treated as the point itself and left out of its own surroundings. Its safety
    counts only when its rate is its own: a feed circle, or an agency no other-named catalog place uses."""
    rows = all_catalog_rows()
    ll = (float(lat), float(lon))
    same = (name or "").strip().lower()

    def is_self(o: Dict[str, Any]) -> bool:
        d = miles(ll, o["ll"])
        if d <= SAME_PIN_MILES:
            return True
        return bool(same) and str(o.get("name") or "").strip().lower() == same and d <= SAME_PLACE_MILES

    skey = safety_key(place_type, {"source": safety_source, "agency_name": agency_name}) \
        if isinstance(safety, (int, float)) and not isinstance(safety, bool) else None
    if skey and skey[1] and any(o.get("agency_any") == skey and not is_self(o) for o in rows):
        skey = None
    here = {"income": num(income), "home_value": num(home_value), "safety": float(safety) if skey else None}
    return figures(here, _near(ll, list(rows), is_self))
