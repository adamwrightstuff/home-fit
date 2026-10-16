"""
School district for a point, from the Census TIGER/Line school district boundaries.

SchoolDigger's Pro plan cannot say which district contains an address (the address lookup is
Enterprise only), and its "nearest district" is measured to the district office, which is wrong
for big or odd-shaped districts. The Census publishes the actual boundary polygons, and the GEOID
is the NCES LEA ID, the same ID SchoolDigger uses as `districtID`.

A point sits in one unified district, or in an elementary district plus a secondary (high
school) district where a place has split districts (Cupertino Union + Fremont Union High).

Files: data_cache/tiger_sd_2024/tl_2024_<state fips>_{unsd,elsd,scsd}/*.shp
(override the folder with HOMEFIT_TIGER_SD_DIR). Missing files for a state mean "no answer",
and callers fall back to the SchoolDigger-based lookup.
"""
from __future__ import annotations

import glob
import math
import os
import threading
from typing import Dict, List, Optional

_STATE_FIPS = {
    "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06", "CO": "08", "CT": "09",
    "DE": "10", "DC": "11", "FL": "12", "GA": "13", "HI": "15", "ID": "16", "IL": "17",
    "IN": "18", "IA": "19", "KS": "20", "KY": "21", "LA": "22", "ME": "23", "MD": "24",
    "MA": "25", "MI": "26", "MN": "27", "MS": "28", "MO": "29", "MT": "30", "NE": "31",
    "NV": "32", "NH": "33", "NJ": "34", "NM": "35", "NY": "36", "NC": "37", "ND": "38",
    "OH": "39", "OK": "40", "OR": "41", "PA": "42", "RI": "44", "SC": "45", "SD": "46",
    "TN": "47", "TX": "48", "UT": "49", "VT": "50", "VA": "51", "WA": "53", "WV": "54",
    "WI": "55", "WY": "56",
}
_KINDS = ("unsd", "elsd", "scsd")

_lock = threading.Lock()
_cache: Dict[tuple, object] = {}  # (state fips, kind) -> GeoDataFrame or None


def _root() -> str:
    default = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data_cache", "tiger_sd_2024"
    )
    return os.getenv("HOMEFIT_TIGER_SD_DIR", default)


def _load(fips: str, kind: str):
    key = (fips, kind)
    with _lock:
        if key in _cache:
            return _cache[key]
        frame = None
        try:
            from data_sources.geo_layers import read_layer

            frame = read_layer(f"district_{fips}_{kind}", os.path.join(_root(), f"tl_2024_{fips}_{kind}"), ["GEOID", "NAME"])
            if frame is not None:
                frame.sindex  # build the spatial index once
        except Exception:
            frame = None
        _cache[key] = frame
        return frame


def have_state(state_abbr: Optional[str]) -> bool:
    fips = _STATE_FIPS.get((state_abbr or "").upper())
    return bool(fips and _load(fips, "unsd") is not None)


def districts_for_point(lat: float, lon: float, state_abbr: Optional[str]) -> List[Dict[str, str]]:
    """[{'id': NCES LEA ID, 'name': ..., 'kind': 'unsd'|'elsd'|'scsd'}] for the point; [] if unknown."""
    fips = _STATE_FIPS.get((state_abbr or "").upper())
    if not fips or lat is None or lon is None:
        return []
    from shapely.geometry import Point

    pt = Point(lon, lat)
    out: List[Dict[str, str]] = []
    for kind in _KINDS:
        frame = _load(fips, kind)
        if frame is None:
            continue
        for idx in frame.sindex.query(pt, predicate="intersects"):
            row = frame.iloc[int(idx)]
            out.append({"id": str(row["GEOID"]), "name": str(row["NAME"]), "kind": kind})
    return out


def point_agreement(lat: float, lon: float, state_abbr: Optional[str], radius_m: float = 400.0) -> float:
    """
    Share of 8 compass points around the place (radius_m out) that fall in the same district
    set as the place point. Low values mean the point is near a district line, so the
    place's own coordinate is a weaker proxy for the place.
    """
    base = {d["id"] for d in districts_for_point(lat, lon, state_abbr)}
    if not base:
        return 0.0
    same = 0
    for k in range(8):
        ang = math.radians(45 * k)
        dlat = (radius_m * math.cos(ang)) / 111_320.0
        dlon = (radius_m * math.sin(ang)) / (111_320.0 * max(0.1, math.cos(math.radians(lat))))
        here = {d["id"] for d in districts_for_point(lat + dlat, lon + dlon, state_abbr)}
        same += 1 if here == base else 0
    return same / 8.0


# ---------------------------------------------------------------------------------------------
# Place outlines: a hamlet's coordinate can sit just across a district line (Cold Spring Harbor's
# catalog point is inside Huntington's district). When a Census place with the requested name exists
# near the point, the district(s) covering most of that place's outline win over the single point.
# ---------------------------------------------------------------------------------------------
_place_cache: Dict[str, object] = {}
MAX_PLACE_SQ_MI = 12.0     # city-sized places say nothing about one neighborhood
MIN_OVERLAP_SHARE = 0.5


def _place_root() -> str:
    default = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "data_cache", "tiger_place_2024")
    return os.getenv("HOMEFIT_TIGER_PLACE_DIR", default)


def _load_places(fips: str):
    with _lock:
        if fips in _place_cache:
            return _place_cache[fips]
        frame = None
        try:
            from data_sources.geo_layers import read_layer

            frame = read_layer(f"place_{fips}", os.path.join(_place_root(), f"tl_2024_{fips}_place"), ["NAME", "GEOID"])
            if frame is not None:
                frame["_key"] = frame["NAME"].map(_norm_place)
                frame.sindex
        except Exception:
            frame = None
        _place_cache[fips] = frame
        return frame


def _norm_place(name: str) -> str:
    import re

    n = re.sub(r"\b(village|town|city|borough|township|hamlet|cdp|of)\b", " ", (name or "").lower())
    return re.sub(r"[^a-z0-9]+", " ", n).strip()


def districts_for_place(lat: float, lon: float, state_abbr: Optional[str],
                        place_name: Optional[str]) -> List[Dict[str, str]]:
    """
    Districts for a place: the point's districts, replaced by the districts covering most of the Census
    place outline when the point's districts cover less than half of it. Same shape as districts_for_point.
    """
    base = districts_for_point(lat, lon, state_abbr)
    fips = _STATE_FIPS.get((state_abbr or "").upper())
    if not (fips and place_name and base):
        return base
    places = _load_places(fips)
    if places is None:
        return base
    from shapely.geometry import Point

    key = _norm_place(place_name)
    if not key:
        return base
    pt = Point(lon, lat)
    # same-named places within ~3 km of the point (0.03 degrees)
    cand = places[places["_key"] == key]
    if len(cand) == 0:
        return base
    cand = cand[cand.geometry.distance(pt) < 0.03]
    if len(cand) == 0:
        return base
    place = cand.iloc[0].geometry
    import geopandas as gpd

    area_sq_mi = gpd.GeoSeries([place], crs=4326).to_crs(5070).area.iloc[0] / 2_589_988.11
    if area_sq_mi > MAX_PLACE_SQ_MI or area_sq_mi <= 0:
        return base
    place_area = gpd.GeoSeries([place], crs=4326).to_crs(5070).area.iloc[0]

    # Per kind (unified / elementary / secondary): replace the point's district only on a clear disagreement,
    # i.e. the replacement covers at least half of the place and the point's own district covers a quarter or less.
    by_kind = {d["kind"]: d for d in base}
    result: List[Dict[str, str]] = []
    weak: set = set()
    for kind in _KINDS:
        frame = _load(fips, kind)
        mine = by_kind.get(kind)
        if frame is None:
            if mine:
                result.append(mine)
            continue
        hits = frame.iloc[list(frame.sindex.query(place, predicate="intersects"))]
        shares = {}
        for _, row in hits.iterrows():
            shares[str(row["GEOID"])] = (gpd.GeoSeries([place.intersection(row.geometry)], crs=4326)
                                         .to_crs(5070).area.iloc[0] / place_area, row)
        pick = mine
        weak_mine = False
        if shares:
            gid, (share, row) = max(shares.items(), key=lambda kv: kv[1][0])
            mine_share = shares.get(mine["id"], (0.0, None))[0] if mine else 0.0
            if share >= MIN_OVERLAP_SHARE and mine_share <= 0.25 and (mine is None or gid != mine["id"]):
                pick = {"id": gid, "name": str(row["NAME"]), "kind": kind}
            elif mine is not None and mine_share <= 0.25:
                weak_mine = True   # the point's district barely touches the place
        if pick:
            result.append(pick)
            if weak_mine and pick is mine:
                weak.add(kind)
    # a unified district that barely touches the place is dropped when elementary/secondary districts replaced it
    changed_split = any(d["kind"] in ("elsd", "scsd") and d["id"] not in {b["id"] for b in base} for d in result)
    if changed_split:
        result = [d for d in result if d["kind"] not in weak]
    return result or base
