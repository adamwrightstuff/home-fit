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
        paths = glob.glob(os.path.join(_root(), f"tl_2024_{fips}_{kind}", "*.shp"))
        if paths:
            try:
                import geopandas as gpd

                frame = gpd.read_file(paths[0], columns=["GEOID", "NAME"])
                if frame.crs is not None and frame.crs.to_epsg() != 4326:
                    frame = frame.to_crs(4326)
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
