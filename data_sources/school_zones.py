"""
Zoned (attendance-zone) schools for a point, from district-published zone maps.

A district's zone map says which elementary / middle / high school an address is assigned to.
Each map is a polygon layer; adding a metro means adding layers to ZONE_LAYERS (files live in
data_cache/zone_maps/<folder>/, override the root with HOMEFIT_ZONE_MAPS_DIR). A point is looked
up in every layer, so no metro argument is needed.

Known limits (kept in each layer's `caveat` and echoed in results):
- Vintages differ and some maps are old; the result carries the map's school year.
- Zones cover district-run neighborhood schools only. Charters, magnets and choice programs
  have no zone, so callers still need a nearby-schools search for those.
- No maps for a place -> an empty result, never an error.
"""
from __future__ import annotations

import glob
import os
import threading
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ZoneLayer:
    folder: str
    level: str                  # 'elementary' | 'middle' | 'high'
    name_fields: tuple          # first non-empty wins
    id_field: str
    vintage: str
    state: str
    covers: tuple = ()          # extra levels this zone serves (Chicago K-8 elementary zones)
    only_where: Optional[tuple] = None   # (field, value): keep only features with field == value
    caveat: str = ""


ZONE_LAYERS: List[ZoneLayer] = [
    ZoneLayer("chicago_elementary_2526", "elementary", ("short_name",), "school_id", "2025-26", "IL",
              covers=("middle",), caveat="K-8 zones; selective, magnet and charter schools have no zone"),
    ZoneLayer("chicago_high_2425", "high", ("school_nam",), "school_id", "2024-25", "IL",
              caveat="neighborhood high schools only; most CPS high schools admit by application"),
    ZoneLayer("austin_elementary_2122", "elementary", ("ELEM_PLAN9",), "CAMPUS_ID", "2021-22", "TX",
              caveat="Austin ISD consolidated schools for 2026-27; zones may be stale"),
    ZoneLayer("austin_middle_2021", "middle", ("MID_NAME", "CAMPUS"), "CAMPUS_ID", "2020-21", "TX",
              caveat="Austin ISD consolidated schools for 2026-27; zones may be stale"),
    ZoneLayer("austin_high_2021", "high", ("HIGH_NAME", "CAMPUS"), "CAMPUS_ID", "2020-21", "TX",
              caveat="Austin ISD consolidated schools for 2026-27; zones may be stale"),
    ZoneLayer("sf_elementary_2425", "elementary", ("sch_lng_na", "synergy_na", "e_aa_name"), "e_aa_schno",
              "2024-25", "CA", caveat="SFUSD elementary attendance areas only; middle and high are choice"),
    ZoneLayer("nyc_elementary_2425", "elementary", ("dbn",), "dbn", "2024-25", "NY",
              caveat="some NYC districts admit by choice or priority, not strictly by zone"),
    ZoneLayer("nyc_middle_2425", "middle", ("dbn",), "dbn", "2024-25", "NY",
              caveat="several NYC districts use choice-based middle school admissions"),
    ZoneLayer("nyc_high_2425", "high", ("sch_name", "dbn"), "dbn", "2024-25", "NY",
              only_where=("catchment", "1"),
              caveat="only a few NYC high schools have a zone; most admit citywide by application"),
    # LA (LAUSD) layers are downloaded but carry only numeric keys; add them once the LAUSD key
    # table that maps those keys to school names is available.
]

_lock = threading.Lock()
_frames: Dict[str, Any] = {}


def _root() -> str:
    default = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "data_cache", "zone_maps")
    return os.getenv("HOMEFIT_ZONE_MAPS_DIR", default)


def _load(layer: ZoneLayer):
    with _lock:
        if layer.folder in _frames:
            return _frames[layer.folder]
        frame = None
        files = glob.glob(os.path.join(_root(), layer.folder, "*.geojson")) or \
            glob.glob(os.path.join(_root(), layer.folder, "*.shp"))
        if files:
            try:
                import geopandas as gpd

                frame = gpd.read_file(files[0])
                if frame.crs is None:
                    frame = frame.set_crs(4326)
                frame = frame.to_crs(4326)
                if layer.only_where:
                    field, value = layer.only_where
                    frame = frame[frame[field].astype(str) == value]
                frame.sindex  # build the spatial index once
            except Exception:
                frame = None
        _frames[layer.folder] = frame
        return frame


def zoned_schools(lat: float, lon: float) -> List[Dict[str, Any]]:
    """Zoned schools for the point, one entry per layer it falls in ([] when no map covers it)."""
    if lat is None or lon is None:
        return []
    from shapely.geometry import Point

    pt = Point(lon, lat)
    out: List[Dict[str, Any]] = []
    for layer in ZONE_LAYERS:
        frame = _load(layer)
        if frame is None or len(frame) == 0:
            continue
        for idx in frame.sindex.query(pt, predicate="intersects"):
            row = frame.iloc[int(idx)]
            names = [str(row[f]).strip() for f in layer.name_fields
                     if f in row and str(row[f]).strip() not in ("", "None", "nan")]
            # a blank name or a "citywide ... choice" polygon means the zone assigns no school
            if not names or any("citywide" in n.lower() for n in names):
                continue
            out.append({
                "level": layer.level,
                "also_serves": list(layer.covers),
                "name": names[0] if names else "",
                "names": names,
                "id": str(row.get(layer.id_field, "")),
                "source": layer.folder,
                "vintage": layer.vintage,
                "state": layer.state,
                "caveat": layer.caveat,
            })
    return out


_STOP = {
    "elementary", "elem", "school", "sch", "middle", "mid", "high", "hs", "ms", "es", "is", "jr", "junior",
    "senior", "the", "of", "and", "for", "at", "dr", "mr", "st", "campus", "intermediate", "primary", "k8",
}


def _tokens(name: str) -> set:
    import re

    return {t for t in re.findall(r"[a-z0-9]+", (name or "").lower()) if len(t) > 1 and t not in _STOP}


def _nyc_dbn_tokens(dbn: str) -> set:
    """30Q152 -> {'152'}: SchoolDigger names NYC schools 'Ps 152 ...', 'Is 125 ...'."""
    import re

    m = re.match(r"^\d{2}[KMQXR](\d+)$", (dbn or "").strip().upper())
    return {str(int(m.group(1)))} if m else set()


def match_zoned_to_schools(zoned: Dict[str, Any], schools: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Find the SchoolDigger school that a zone assigns to. The zone's name tokens must all appear in
    the school's name, the school level must fit, and ties go to the nearest school. None when no
    school matches (callers should report it as unmatched, not guess).
    """
    levels = {zoned["level"], *zoned.get("also_serves", [])}
    want_sets = []
    for n in zoned.get("names") or [zoned.get("name", "")]:
        t = _nyc_dbn_tokens(n) or _tokens(n)
        if t:
            want_sets.append(t)
    best, best_key = None, None
    for s in schools:
        lvl = (s.get("schoolLevel") or "").lower()
        lvl_ok = any(l in lvl for l in levels) or (
            "elementary" in levels and ("primary" in lvl)) or not lvl
        if not lvl_ok or s.get("isPrivate"):
            continue
        have = _tokens(s.get("schoolName", ""))
        for want in want_sets:
            if want <= have:
                key = (len(want) / max(1, len(have)), -(s.get("distance") or 99))
                if best_key is None or key > best_key:
                    best, best_key = s, key
                break
    return best
