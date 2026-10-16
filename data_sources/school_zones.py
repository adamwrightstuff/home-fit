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
    resolver: Optional[str] = None       # 'nyc_dbn': turn a DOE school code into a school name via NCES
    spatial_only: bool = False           # layer has no school names: match the school by the zone it sits in
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
    ZoneLayer("nyc_elementary_2425", "elementary", ("dbn",), "dbn", "2024-25", "NY", resolver="nyc_dbn",
              caveat="some NYC districts admit by choice or priority, not strictly by zone"),
    ZoneLayer("nyc_middle_2425", "middle", ("dbn",), "dbn", "2024-25", "NY", resolver="nyc_dbn",
              caveat="several NYC districts use choice-based middle school admissions"),
    ZoneLayer("nyc_high_2425", "high", ("sch_name", "dbn"), "dbn", "2024-25", "NY",
              only_where=("catchment", "1"), resolver="nyc_dbn",
              caveat="only a few NYC high schools have a zone; most admit citywide by application"),
    ZoneLayer("la_elementary_2018_2020", "elementary", (), "KEY_", "2018", "CA", spatial_only=True,
              caveat="LAUSD elementary zones last updated 2018; school found by the campus inside the zone"),
    ZoneLayer("la_middle_2018_2020", "middle", (), "KEY_", "2020", "CA", spatial_only=True,
              caveat="LAUSD middle zones last updated 2020; school found by the campus inside the zone"),
    ZoneLayer("la_high_2018_2020", "high", (), "KEY_", "2018", "CA", spatial_only=True,
              caveat="LAUSD high zones last updated 2018; school found by the campus inside the zone"),
    ZoneLayer("seattle_elementary_2324", "elementary", ("es_zone",), "es_sch", "2023-24", "WA",
              caveat="Seattle Public Schools 2023-24 map; Seattle has many option-school seats"),
    ZoneLayer("seattle_middle_2324", "middle", ("ms_zone",), "ms_sch", "2023-24", "WA",
              caveat="Seattle Public Schools 2023-24 map"),
    ZoneLayer("seattle_high_2324", "high", ("HS_ZONE",), "HS_SCH", "2023-24", "WA",
              caveat="Seattle Public Schools 2023-24 map"),
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
        try:
            from data_sources.geo_layers import read_layer

            frame = read_layer(f"zone_{layer.folder}", os.path.join(_root(), layer.folder))
            if frame is not None:
                if layer.only_where:
                    field, value = layer.only_where
                    frame = frame[frame[field].astype(str) == value]
                frame.sindex  # build the spatial index once
        except Exception:
            frame = None
        _frames[layer.folder] = frame
        return frame


_nyc_lock = threading.Lock()
_nyc_names_cache: Dict[str, Any] = {}


def _nces_csv() -> str:
    return os.getenv("HOMEFIT_NCES_CCD_CSV", os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data_cache", "nces_ccd_2324", "ccd_sch_029_2324_w_1a_073124.csv"))


def _nyc_name_for_dbn(dbn: str) -> str:
    """'30Q126' -> 'ALBERT SHANKER SCHOOL FOR VISUAL AND PERFORMING ARTS' (NCES: geographic district + last 4 digits of the state school ID)."""
    import re

    m = re.match(r"^(\d{2})[KMQXR](\d+)$", (dbn or "").strip().upper())
    if not m:
        return ""
    with _nyc_lock:
        if "map" not in _nyc_names_cache:
            table: Dict[tuple, str] = {}
            try:
                import json as _json
                from data_sources.geo_layers import bundle_dir

                packed = os.path.join(bundle_dir(), "nyc_dbn_names.json")
                if os.path.isfile(packed):
                    with open(packed) as f:
                        for k, v in _json.load(f).items():
                            d, n = k.split(":")
                            table[(int(d), int(n))] = v
            except Exception:
                table = {}
            try:
                if table:
                    raise StopIteration  # bundle found, skip the raw NCES file
                import pandas as pd

                df = pd.read_csv(_nces_csv(), dtype=str, low_memory=False,
                                 usecols=["ST", "SCH_NAME", "ST_SCHID", "LEA_NAME"])
                ny = df[(df.ST == "NY") & df.LEA_NAME.str.contains("GEOGRAPHIC DISTRICT", na=False)]
                for lea, sid, name in zip(ny.LEA_NAME, ny.ST_SCHID, ny.SCH_NAME):
                    d = re.search(r"#\s*(\d+)", str(lea))
                    if d and str(sid)[-4:].isdigit():
                        table[(int(d.group(1)), int(str(sid)[-4:]))] = str(name)
            except StopIteration:
                pass
            except Exception:
                table = {}
            _nyc_names_cache["map"] = table
    return _nyc_names_cache["map"].get((int(m.group(1)), int(m.group(2))), "")


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
            alts: List[List[str]] = []
            if layer.resolver == "nyc_dbn":
                dbns = [d.strip() for d in str(row.get(layer.id_field, "")).split(",") if d.strip()]
                for d in dbns:                       # a few zones list several schools: '10X363,10X447'
                    full = _nyc_name_for_dbn(d)
                    alts.append(([full] if full else []) + [d])
                if len(dbns) <= 1:
                    full = _nyc_name_for_dbn(dbns[0]) if dbns else ""
                    names = ([full] if full else []) + names
                else:
                    names = [n for a in alts for n in a]
            # a blank name or a "citywide ... choice" polygon means the zone assigns no school
            if not layer.spatial_only and (not names or any("citywide" in n.lower() for n in names)):
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
                "alts": alts if len(alts) > 1 else [],
                "_geom": row.geometry,
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
    if best is None:
        return match_zone_by_location(zoned, schools)
    return best


def _school_point(s: Dict[str, Any]):
    from shapely.geometry import Point

    ll = (s.get("address") or {}).get("latLong") or {}
    if ll.get("latitude") is None or ll.get("longitude") is None:
        return None
    return Point(float(ll["longitude"]), float(ll["latitude"]))


def match_zone_by_location(zoned: Dict[str, Any], schools: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    The school a zone assigns, found by where the schools sit: the rated school of the right level whose campus
    is inside the zone polygon. `schools` must already be the home district's schools, so a charter in the list is
    a district-affiliated charter (a neighborhood school in LAUSD, for example). Used when names do not line up
    (Seattle "Denny Int'l" vs "Denny International") or the map has no names (LA). Preference: regular school,
    then affiliated charter, then magnet; None unless one school is left (ties go to the school sharing a word
    with the zone's name).
    """
    geom = zoned.get("_geom")
    if geom is None:
        return None
    levels = {zoned["level"], *zoned.get("also_serves", [])}
    tiers: Dict[int, List[Dict[str, Any]]] = {0: [], 1: [], 2: []}
    for s in schools:
        lvl = (s.get("schoolLevel") or "").lower()
        if s.get("isPrivate") or not (s.get("rankHistory") or []):
            continue
        if not any(l in lvl for l in levels) and not ("elementary" in levels and "primary" in lvl):
            continue
        pt = _school_point(s)
        if pt is None or not geom.contains(pt):
            continue
        tier = 2 if s.get("isMagnetSchool") == "Yes" else (1 if s.get("isCharterSchool") == "Yes" else 0)
        tiers[tier].append(s)
    inside = next((tiers[t] for t in (0, 1, 2) if tiers[t]), [])
    if len(inside) == 1:
        return inside[0]
    if len(inside) > 1:
        want = set().union(*[_tokens(n) for n in zoned["names"]]) if zoned.get("names") else set()
        scored = sorted(inside, key=lambda s: -len(want & _tokens(s.get("schoolName", ""))))
        if want and len(want & _tokens(scored[0].get("schoolName", ""))) > 0:
            return scored[0]
    return None


def match_zoned_schools(zoned: Dict[str, Any], schools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Every school a zone assigns, as a list: usually one. More than one when a zone lists several schools
    (NYC '10X363,10X447'), or when a map with no names puts several schools of the level on the resident campus
    (LA's large high schools are split into small schools sharing one building; a student zoned there attends
    one of them, so callers average them). Empty when nothing is found.
    """
    if zoned.get("alts"):
        found = []
        for names in zoned["alts"]:
            m = match_zoned_to_schools({**zoned, "names": names, "name": names[0], "alts": [], "_geom": None}, schools)
            if m is not None and m not in found:
                found.append(m)
        return found
    m = match_zoned_to_schools(zoned, schools)
    if m is not None:
        return [m]
    if not zoned.get("names"):       # nameless map: the whole resident campus
        return _campus_schools(zoned, schools)
    return []


def _campus_schools(zoned: Dict[str, Any], schools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    geom = zoned.get("_geom")
    if geom is None:
        return []
    levels = {zoned["level"], *zoned.get("also_serves", [])}
    tiers: Dict[int, List[Dict[str, Any]]] = {0: [], 1: [], 2: []}
    for s in schools:
        lvl = (s.get("schoolLevel") or "").lower()
        if s.get("isPrivate") or not (s.get("rankHistory") or []):
            continue
        if not any(l in lvl for l in levels) and not ("elementary" in levels and "primary" in lvl):
            continue
        pt = _school_point(s)
        if pt is None or not geom.contains(pt):
            continue
        tiers[2 if s.get("isMagnetSchool") == "Yes" else (1 if s.get("isCharterSchool") == "Yes" else 0)].append(s)
    return next((tiers[t] for t in (0, 1, 2) if tiers[t]), [])[:8]
